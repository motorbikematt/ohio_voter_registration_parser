"""parse_candidate_petitions.py -- Stage 4: BoE candidate petition report -> intermediate JSON.

Source: local/source/6.1.2026-Candidate-Petition-Report.pdf (converted to .md by
tools/admin/pdf_to_markdown.py first -- the PDF is rotated, so raw geometry is
transposed, but pymupdf4llm reconstructs the wide table into clean rows).

The report lists every 2026 general-election contest on a Montgomery ballot, with
the candidate's mailing address (the zip feeds Session-2 voter matching). BoE
updates it weekly, so `retrieved_date` is recorded and the file should be
re-fetched periodically.

Output: local/working/candidate_filings_{county}.json
  { "county_slug": "montgomery", "source": "boe_candidate_petition_pdf",
    "retrieved_date": "2026-06-01", "election_date": "2026-11-03",
    "source_file": "6.1.2026-Candidate-Petition-Report.pdf",
    "filings": [ { "office_raw": "State Representative- 36th District (1)",
                   "office_section": "STATE_REPRESENTATIVE_DISTRICT", "office_id": "36",
                   "name_raw": "Rose Lounsbury", "name_normalized": "Rose Lounsbury",
                   "party": "D",
                   "address": {"street": "222 Wonderly Ave.", "city": "Dayton", "zip": "45419"},
                   "petition_filed": "2025-12-04", "petition_certified": "2026-01-20",
                   "date_of_election": "2026-11-03" } ] }

Field detection is content-based (party token, zip regex, date regex), not fixed
column position -- the markdown drops empty cells unevenly between the statewide
(no address) and district (full address) pages.

Usage:
    python tools/admin/parse_candidate_petitions.py --county montgomery
    python tools/admin/parse_candidate_petitions.py --county montgomery --retrieved-date 2026-06-01
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import COUNTY_NUMBER, ROOT, normalize_name, atomic_write_json  # noqa: E402

LOCAL_SOURCE = ROOT / "local" / "source"
WORKING_DIR = ROOT / "local" / "working"

PETITION_PDF = "6.1.2026-Candidate-Petition-Report.pdf"

PARTY_TOKEN = {"DEM": "D", "REP": "R", "LIB": "L", "IND": "I", "NON": None}
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
# Table header / label cells to ignore when classifying a row.
_LABELS = {
    "party", "candidate", "address", "petition", "election", "office",
    "incumbent", "picked-up", "deadline", "filed", "certified", "date of",
}


def _to_iso(mdy: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", mdy.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def classify_office(office_raw: str) -> tuple[str, str | None]:
    """Map an office label to a serve section + id (mirrors officials.json keys)."""
    o = re.sub(r"\s+", " ", office_raw).strip()
    low = o.lower()

    m = re.search(r"congress[^0-9]*?(\d+)(?:st|nd|rd|th)?\s+district", low)
    if m:
        return "CONGRESSIONAL_DISTRICT", f"{int(m.group(1)):02d}"
    m = re.search(r"state senator[^0-9]*?(\d+)(?:st|nd|rd|th)?\s+district", low)
    if m:
        return "STATE_SENATE_DISTRICT", f"{int(m.group(1)):02d}"
    m = re.search(r"state representative[^0-9]*?(\d+)(?:st|nd|rd|th)?\s+district", low)
    if m:
        return "STATE_REPRESENTATIVE_DISTRICT", f"{int(m.group(1)):02d}"
    if "county commissioner" in low:
        return "COUNTY_COMMISSIONER", None
    if "county auditor" in low:
        return "COUNTY_AUDITOR", None
    if low.startswith("judge") or "court of" in low:
        return "JUDICIAL", None
    return "STATEWIDE", None


def _cells(line: str) -> list[str]:
    """Split a markdown table row into stripped cells (markup removed)."""
    inner = line.strip().strip("|")
    return [re.sub(r"\s+", " ", re.sub(r"<br>|\*", " ", c)).strip() for c in inner.split("|")]


def _is_header_row(cells: list[str]) -> bool:
    nonempty = [c for c in cells if c]
    if not nonempty:
        return True
    labelish = sum(1 for c in nonempty if c.lower() in _LABELS)
    return labelish >= 2


def parse_petition_md(md_path: Path) -> tuple[list[dict], str | None]:
    """Parse the petition markdown into flat candidate filings."""
    filings: list[dict] = []
    current_office: str | None = None
    election_date: str | None = None

    for raw in md_path.read_text(encoding="utf-8").splitlines():
        if not raw.lstrip().startswith("|"):
            continue
        if re.match(r"^\s*\|[\s|:-]+\|\s*$", raw):     # |---|---| separator
            continue
        cells = _cells(raw)
        if _is_header_row(cells):
            continue

        party = next((PARTY_TOKEN[c.upper()] for c in cells if c.upper() in PARTY_TOKEN), "NONE")
        has_date = any(_DATE_RE.match(c) for c in cells)
        has_party_cell = any(c.upper() in PARTY_TOKEN for c in cells)

        if not has_date and not has_party_cell:
            # Office header row: join the bold office text spread across cells.
            office_text = " ".join(c for c in cells if c).strip()
            if office_text:
                current_office = office_text
            continue

        # Data row.
        filing = _parse_data_row(cells, current_office)
        if filing:
            if filing.get("date_of_election"):
                election_date = filing["date_of_election"]
            filings.append(filing)

    return filings, election_date


def _parse_data_row(cells: list[str], office_raw: str | None) -> dict | None:
    party = None
    p_idx = None
    for i, c in enumerate(cells):
        if c.upper() in PARTY_TOKEN:
            party = PARTY_TOKEN[c.upper()]
            p_idx = i
            break

    # name: first substantial alpha cell after the party (or from the start)
    name = None
    n_idx = None
    for i in range((p_idx + 1) if p_idx is not None else 0, len(cells)):
        c = cells[i]
        if c and not _DATE_RE.match(c) and not _ZIP_RE.match(c) and c.upper() not in PARTY_TOKEN:
            name, n_idx = c, i
            break
    if not name:
        return None

    # address region: non-empty cells between name and the first date cell
    zip_code = city = street = None
    region: list[str] = []
    for i in range(n_idx + 1, len(cells)):
        c = cells[i]
        if _DATE_RE.match(c):
            break
        if c:
            region.append(c)
    if region:
        if _ZIP_RE.match(region[-1]):
            zip_code = region[-1]
            region = region[:-1]
        if region and (zip_code or len(region) >= 2):
            city = region[-1]
            region = region[:-1]
        if region:
            street = " ".join(region)

    dates = [_to_iso(c) for c in cells if _DATE_RE.match(c)]
    # Column order in a full-address row: picked-up, deadline, filed, certified, election.
    petition_filed = petition_certified = date_of_election = None
    if dates:
        date_of_election = dates[-1]
        body = dates[:-1]
        if len(body) >= 2:
            petition_certified = body[-1]
            petition_filed = body[-2]

    section, office_id = classify_office(office_raw or "")
    address = {"street": street, "city": city, "zip": zip_code}
    return {
        "office_raw": office_raw,
        "office_section": section,
        "office_id": office_id,
        "name_raw": name,
        "name_normalized": normalize_name(name),
        "party": party,
        "address": address if any(address.values()) else None,
        "petition_filed": petition_filed,
        "petition_certified": petition_certified,
        "date_of_election": date_of_election,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse the BoE candidate petition report.")
    ap.add_argument("--county", default="montgomery")
    ap.add_argument("--pdf", type=Path, help="Override petition PDF path")
    ap.add_argument("--retrieved-date", help="ISO date the report was downloaded (default: from filename)")
    args = ap.parse_args()

    if args.county not in COUNTY_NUMBER:
        print(f"ERROR: unknown county slug {args.county!r}", file=sys.stderr)
        sys.exit(1)

    pdf_path = args.pdf or (LOCAL_SOURCE / PETITION_PDF)
    md_path = pdf_path.with_suffix(".md")
    if not md_path.exists():
        print(f"ERROR: markdown not found: {md_path}\n"
              f"Run: python tools/admin/pdf_to_markdown.py {pdf_path}", file=sys.stderr)
        sys.exit(1)

    retrieved = args.retrieved_date
    if not retrieved:
        m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})", pdf_path.name)
        retrieved = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None

    filings, election_date = parse_petition_md(md_path)
    result = {
        "county_slug": args.county,
        "source": "boe_candidate_petition_pdf",
        "retrieved_date": retrieved,
        "election_date": election_date,
        "source_file": pdf_path.name,
        "filings": filings,
    }
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    out = WORKING_DIR / f"candidate_filings_{args.county}.json"
    n = atomic_write_json(out, result)

    from collections import Counter
    by_section = Counter(f["office_section"] for f in filings)
    print(f"-> {out.name}: {len(filings)} filings ({n:,} bytes)")
    for sec, c in by_section.most_common():
        print(f"   {sec}: {c}")


if __name__ == "__main__":
    main()
