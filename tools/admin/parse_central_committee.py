"""parse_central_committee.py -- Stage 3: central-committee filings -> intermediate JSON.

Dispatcher over three adapters that all emit ONE intermediate schema to
local/working/captain_filings_{county}_{party}.json, so Stage 5
(build_precinct_captains.py) consumes a single shape regardless of source.

Adapter detection order (first match wins; CLAUDE.md section 5 -- a source that
yields nothing logs a gap and emits empty filings, never halts):
  1. electedofficials.csv has DISTTYPE == 'PRECINCT' rows for county+party -> CSVAdapter
  2. a central-committee PDF for county+party                              -> PDFAdapter
  3. local/patches/captain_override_{county}_{party}.json                   -> ManualJSONAdapter

PDF parsing reads the PDF geometry with PyMuPDF (fitz), NOT the pymupdf4llm
markdown: the BoE report places ONE candidate per physical line, and the
markdown converter flattens positionally-distinct candidates onto one line,
destroying the boundaries (e.g. 'DAVID L. BRAUN MALIK SIMON JACQUELINE ANN
TOUSSAINT-BARKER' is three filers, unsplittable from text alone). Iterating the
y-sorted lines makes the split deterministic.

Intermediate schema (one filing per candidate):
  { "county_slug": "montgomery", "party": "D", "source": "boe_pdf",
    "retrieved_date": "2026-05-02", "coverage": "complete",
    "lists_all_precincts": true, "source_file": "DEM-CENTRAL-COMMITTEE-5-2-26.pdf",
    "filings": [ { "ballot_number": "0070", "precinct_name": "BUTLER TWP C",
                   "name_raw": "GREGORY A. BRUSH", "name_normalized": "Gregory A. Brush",
                   "party": "D", "write_in": false, "contested": true } ],
    "gaps": ["0650", "1430"] }

`coverage` tells Stage 5 how to treat a precinct with no filing:
  complete -> nobody filed -> "vacant"        (D full report, L minor-party report)
  partial  -> data not yet loaded -> "data_pending" (R, only the CSV incumbent known)

Usage:
    python tools/admin/parse_central_committee.py --county montgomery --party D
    python tools/admin/parse_central_committee.py --county montgomery --all-parties
    python tools/admin/parse_central_committee.py --county montgomery --party D --source path/to.pdf
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import (  # noqa: E402
    COUNTY_NUMBER,
    PrecinctCrosswalk,
    ROOT,
    load_precinct_crosswalk,
    name_from_parts,
    normalize_name,
    atomic_write_json,
)

LOCAL_SOURCE = ROOT / "local" / "source"
WORKING_DIR = ROOT / "local" / "working"
ERRORS_DIR = WORKING_DIR / "errors"
PATCHES_DIR = ROOT / "local" / "patches"
ELECTED_CSV = LOCAL_SOURCE / "electedofficials.csv"

PARTY_WORD = {"D": "DEMOCRATIC", "L": "LIBERTARIAN", "R": "REPUBLICAN"}

# Per-source provenance/policy for known county+party filings. BoE filenames are
# idiosyncratic (no slug convention), so the real files are registered here;
# unknown county+party fall back to a glob + defaults.
SOURCE_HINTS: dict[tuple[str, str], dict] = {
    ("montgomery", "D"): {
        "pdf": "DEM-CENTRAL-COMMITTEE-5-2-26.pdf",
        "retrieved_date": "2026-05-02",
        "lists_all_precincts": True,    # report enumerates every precinct
        "has_address": False,           # NAME column only
    },
    ("montgomery", "L"): {
        "pdf": "LIB-CENTRAL-COMMITTEE.pdf",
        "retrieved_date": "2026-02-20",
        "lists_all_precincts": False,   # minor-party report lists only filed precincts
        "has_address": True,            # NAME + ADDRESS columns
    },
}


def _log_gap(county: str, party: str, message: str) -> None:
    ERRORS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = ERRORS_DIR / f"central_committee_{county}_{party}.log"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{date.today().isoformat()}  {message}\n")


# -- line-level parsing --------------------------------------------------------

_HEADER_RE = re.compile(
    r"^(\d{4})\s+.+?\s+(DEMOCRATIC|LIBERTARIAN|REPUBLICAN)\s+CENTRAL\s+COMMITTEE\s*$",
    re.I,
)
_PREAMBLE_RE = re.compile(r"^VOTE FOR NO MORE THAN", re.I)
_NOISE_RE = re.compile(
    r"^(MONTGOMERY COUNTY( BOARD OF ELECTIONS)?(\s+\d{2}:\d{2}:\d{2})?|"
    r"\d+\s+W\s+THIRD\s+ST|451 W THIRD ST|DAYTON,?\s+OH\s+\d{5}|"
    r"PRIMARY ELECTION.*|NAME( ADDRESS)?|ADDRESS|"
    r"\d{1,2}/\d{1,2}/\d{2,4}(\s+\d+)?|\d{2}:\d{2}:\d{2}|\d{1,4})\s*$",
    re.I,
)
_MARKER_RE = re.compile(r"\(([DLR])\)")
_WRITEIN_RE = re.compile(r"WRITE[\s-]*IN\s*:?", re.I)
_STREET_WORDS = {
    "APT", "AVE", "ST", "DR", "RD", "BLVD", "LN", "CT", "PL", "WAY", "CIR",
    "TER", "SQ", "HWY", "PKWY", "PT", "UNIT", "APARTMENT", "BOX", "PO",
}


def _is_address_token(tok: str) -> bool:
    if any(ch.isdigit() for ch in tok):
        return True
    return tok.upper().rstrip(".") in _STREET_WORDS


def _looks_like_address_line(line: str) -> bool:
    """An address-continuation line: no party marker and contains a digit.

    Candidate names never contain digits, so a digit on a marker-less line
    (street number, apt, zip) means it is the prior candidate's address.
    """
    return not _MARKER_RE.search(line) and any(ch.isdigit() for ch in line)


def _clean_candidate(seg: str, has_address: bool) -> tuple[str, bool]:
    """Return (name_raw, write_in) for one candidate segment, or ('', False)."""
    write_in = bool(_WRITEIN_RE.search(seg))
    seg = _WRITEIN_RE.sub(" ", seg)
    seg = re.sub(r"\s+", " ", seg).strip().strip(",").strip()
    if not seg:
        return "", write_in
    if has_address:
        # The name is the trailing run of name tokens (a street address may lead
        # the segment when a prior candidate's address shares the line).
        kept: list[str] = []
        for tok in reversed(seg.split(" ")):
            if _is_address_token(tok):
                if kept:
                    break
                continue
            kept.append(tok)
        seg = " ".join(reversed(kept)).strip()
    return seg, write_in


def split_line_candidates(line: str, has_address: bool) -> list[dict]:
    """Split one report line into [{name_raw, party, write_in}].

    Usually one candidate per line; handles the occasional two-per-line case via
    the (D)/(L)/(R) markers, with a trailing no-suffix name in a name-only report.
    """
    line = re.sub(r"\s+", " ", line).strip()
    if not line or "NO CANDIDATE FILED" in line.upper():
        return []

    out: list[dict] = []
    matches = list(_MARKER_RE.finditer(line))
    last = 0
    for m in matches:
        name, write_in = _clean_candidate(line[last:m.start()], has_address)
        last = m.end()
        if name:
            out.append({"name_raw": name, "party": m.group(1), "write_in": write_in})

    tail = line[last:].strip()
    if matches:
        if not has_address:                       # trailing no-suffix candidate
            name, write_in = _clean_candidate(tail, has_address)
            if name:
                out.append({"name_raw": name, "party": None, "write_in": write_in})
        # has_address: trailing text is a street address -> discard
    else:
        name, write_in = _clean_candidate(line, has_address)
        if name:
            out.append({"name_raw": name, "party": None, "write_in": write_in})
    return out


# -- adapters ------------------------------------------------------------------

def _pdf_lines(pdf_path: Path) -> list[str]:
    """Y-sorted physical lines across all pages (one candidate per line)."""
    import fitz  # PyMuPDF; ships with pymupdf4llm

    doc = fitz.open(str(pdf_path))
    lines: list[str] = []
    for pno in range(doc.page_count):
        rows = []
        for block in doc[pno].get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                text = re.sub(r"\s+", " ", "".join(s["text"] for s in ln["spans"])).strip()
                if text:
                    rows.append((round(ln["bbox"][1], 1), round(ln["bbox"][0], 1), text))
        rows.sort()
        lines.extend(t for _, _, t in rows)
    doc.close()
    return lines


def pdf_adapter(county: str, party: str, pdf_path: Path, hint: dict) -> dict:
    """Parse a central-committee PDF by physical line geometry."""
    has_address = hint.get("has_address", False)
    lists_all = hint.get("lists_all_precincts", party == "D")
    party_word = PARTY_WORD[party]

    blocks: list[tuple[str, list[str]]] = []
    ballot: str | None = None
    body: list[str] = []
    for line in _pdf_lines(pdf_path):
        header = _HEADER_RE.match(line)
        if header:
            if ballot is not None:
                blocks.append((ballot, body))
                ballot, body = None, []
            if header.group(2).upper() == party_word:
                ballot, body = header.group(1), []
            continue
        if ballot is None:
            continue
        if _PREAMBLE_RE.match(line) or _NOISE_RE.match(line):
            continue
        body.append(line)
    if ballot is not None:
        blocks.append((ballot, body))

    parsed: list[tuple[str, list[dict]]] = []
    for bal, lines in blocks:
        cands: list[dict] = []
        for line in lines:
            if has_address and _looks_like_address_line(line):
                continue
            cands.extend(split_line_candidates(line, has_address))
        parsed.append((bal, cands))

    return _assemble(county, party, parsed, lists_all, "boe_pdf",
                     hint.get("retrieved_date"), pdf_path.name, coverage="complete")


def csv_adapter(county: str, party: str) -> dict:
    """Build filings from electedofficials.csv DISTTYPE == 'PRECINCT' rows."""
    rows = [
        r for r in csv.DictReader(ELECTED_CSV.open(encoding="utf-8"))
        if r["DISTTYPE"].strip() == "PRECINCT" and r["PARTY"].strip() == party
    ]
    parsed: list[tuple[str, list[dict]]] = []
    for r in rows:
        ballot = r["DISTNAME"].strip()      # PRECINCT rows put the ballot number here
        name = name_from_parts(r["FIRSTN"], r["MIDDLEN"], r["LASTN"], r.get("SUFFIXN", ""))
        parsed.append((ballot, [{"name_raw": name, "party": party, "write_in": False}]))
    return _assemble(county, party, parsed, lists_all=False, source="csv",
                     retrieved_date=None, source_file=ELECTED_CSV.name, coverage="partial")


def manual_adapter(county: str, party: str, path: Path) -> dict:
    """Load a hand-authored override already in the intermediate schema."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("county_slug", county)
    data.setdefault("party", party)
    data.setdefault("source", "manual_json")
    data.setdefault("coverage", "partial")
    data.setdefault("lists_all_precincts", False)
    data.setdefault("gaps", [])
    data.setdefault("source_file", path.name)
    for f in data.get("filings", []):
        f.setdefault("name_normalized", normalize_name(f.get("name_raw", "")))
    return data


# -- assembly ------------------------------------------------------------------

_CROSSWALK_CACHE: dict[str, PrecinctCrosswalk] = {}


def _assemble(county, party, parsed, lists_all, source, retrieved_date,
              source_file, coverage) -> dict:
    """Resolve precincts, mark contested, and compute gaps."""
    xw = _CROSSWALK_CACHE.setdefault(county, load_precinct_crosswalk(county))

    filings: list[dict] = []
    seen_ballots: set[str] = set()
    for ballot, cands in parsed:
        ballot = ballot.zfill(4)
        seen_ballots.add(ballot)
        precinct_name = xw.resolve(ballot)
        if precinct_name is None:
            _log_gap(county, party, f"ballot {ballot} not in crosswalk; skipped")
            continue
        contested = len(cands) >= 2
        for c in cands:
            filings.append({
                "ballot_number": ballot,
                "precinct_name": precinct_name,
                "name_raw": c["name_raw"],
                "name_normalized": normalize_name(c["name_raw"]),
                "party": c.get("party"),
                "write_in": c.get("write_in", False),
                "contested": contested,
            })

    gaps = sorted(set(xw.all_ballots) - seen_ballots) if lists_all else []
    return {
        "county_slug": county,
        "party": party,
        "source": source,
        "retrieved_date": retrieved_date,
        "coverage": coverage,
        "lists_all_precincts": lists_all,
        "source_file": source_file,
        "filings": filings,
        "gaps": gaps,
    }


# -- dispatch ------------------------------------------------------------------

def detect_and_parse(county: str, party: str, source_override: Path | None) -> dict:
    """Run the first matching adapter for a county+party (documented order)."""
    # 1. CSV (DISTTYPE == PRECINCT rows)
    if source_override is None and ELECTED_CSV.exists():
        has_precinct_rows = any(
            r["DISTTYPE"].strip() == "PRECINCT" and r["PARTY"].strip() == party
            for r in csv.DictReader(ELECTED_CSV.open(encoding="utf-8"))
        )
        if has_precinct_rows:
            print(f"  [{party}] CSVAdapter (electedofficials.csv PRECINCT rows)")
            return csv_adapter(county, party)

    # 2. PDF
    hint = SOURCE_HINTS.get((county, party), {})
    pdf_path = None
    if source_override is not None:
        pdf_path = source_override
    elif hint.get("pdf"):
        pdf_path = LOCAL_SOURCE / hint["pdf"]
    else:
        globs = list(LOCAL_SOURCE.glob(f"{county}_{party}_central_committee*.pdf"))
        globs += [p for p in LOCAL_SOURCE.glob("*.pdf")
                  if PARTY_WORD[party][:3] in p.name.upper() and "CENTRAL" in p.name.upper()]
        pdf_path = globs[0] if globs else None
    if pdf_path and pdf_path.exists():
        print(f"  [{party}] PDFAdapter ({pdf_path.name})")
        return pdf_adapter(county, party, pdf_path, hint)

    # 3. Manual override
    override = PATCHES_DIR / f"captain_override_{county}_{party}.json"
    if override.exists():
        print(f"  [{party}] ManualJSONAdapter ({override.name})")
        return manual_adapter(county, party, override)

    # 4. Nothing -> log gap, emit empty partial (Stage 5 -> data_pending)
    print(f"  [{party}] no source found -> empty (data_pending)")
    _log_gap(county, party, "no adapter matched; emitted empty filings")
    return {
        "county_slug": county, "party": party, "source": "none",
        "retrieved_date": None, "coverage": "partial", "lists_all_precincts": False,
        "source_file": None, "filings": [], "gaps": [],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse central-committee filings to intermediate JSON.")
    ap.add_argument("--county", default="montgomery")
    ap.add_argument("--party", choices=["D", "L", "R"])
    ap.add_argument("--all-parties", action="store_true", help="Run D, L, R")
    ap.add_argument("--source", type=Path, help="Override source PDF path")
    args = ap.parse_args()

    if args.county not in COUNTY_NUMBER:
        print(f"ERROR: unknown county slug {args.county!r}", file=sys.stderr)
        sys.exit(1)
    if not args.all_parties and not args.party:
        ap.error("pass --party D|L|R or --all-parties")

    parties = ["D", "L", "R"] if args.all_parties else [args.party]
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    for party in parties:
        result = detect_and_parse(args.county, party, args.source)
        out = WORKING_DIR / f"captain_filings_{args.county}_{party}.json"
        n = atomic_write_json(out, result)
        print(f"  -> {out.name}: {len(result['filings'])} filings, "
              f"{len(result['gaps'])} gaps, coverage={result['coverage']} ({n:,} bytes)")


if __name__ == "__main__":
    main()
