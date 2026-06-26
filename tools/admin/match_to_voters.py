"""match_to_voters.py -- Stage 7: cross-reference every filer against the voter file.

The "consumer" stage of the officials/captains/candidates pipeline. It reads the
three frozen serve files produced by Session 1 --

  * serve/officials.json          -> entity_type "incumbent"
  * serve/precinct_captains.json  -> entity_type "captain_candidate"
  * serve/candidates.json         -> entity_type "general_candidate"

-- finds each person's own voter-registration record in the enriched parquet, and
attaches a `partisan_profile` (their lean score, primary history, and a plain-English
label). The combined result is written to serve/partisan_profiles.json.

SINGLE-RESOLVER RULE (CLAUDE.md section 5).  There is exactly ONE voter-matching
function, `match_entity`. The three entity types differ only in the *location
constraint* used to disambiguate same-name voters -- a zip code or a precinct name --
which is passed in as an optional parameter. We do NOT write a matcher per entity.

SWVF SCHEMA NOTES (CLAUDE.md section 4) honored here:
  * VOTER_STATUS is filtered to ACTIVE / CONFIRMATION only (the only two values).
  * COUNTY_NUMBER is a String -- filtered with == "57", never an int.
  * The lapse signal is PARTY_AFFILIATION == "" (SOS already applied the
    2-calendar-year window). We NEVER gate the profile label on a year threshold.
    Verified 2026-06-25: county-57 blanks are stored as "" (0 nulls); we still treat
    a null defensively as "" so the signal can never be silently skipped.
  * Home zip is HZIPCODE (electedofficials.csv) -- NEVER OZIPCODE (office address).
  * Postal fields are never used as a jurisdiction signal; zip is a name tiebreaker.

DATA NOTE -- temporary captain sources (2026-06). Captain data is a stopgap: DEM
and LIB come from one-off central-committee filing PDFs, and the Republican
committee report is absent (only the single CSV incumbent). The BoE's canonical
source for ALL elected officials -- including precinct captains -- is supposed to
be electedofficials.csv, which is not yet complete. This consumer is
source-agnostic: it reads whatever the frozen serve schema carries (see
serve/precinct_captains.json _meta.parties[*].coverage/source), so a future
complete electedofficials.csv does NOT change this file -- the data simply fills in.

Usage:
    python tools/admin/match_to_voters.py --county montgomery
    python tools/admin/match_to_voters.py --county montgomery --verbose
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import (  # noqa: E402
    COUNTY_NUMBER,
    ENRICHED_PARQUET,
    ROOT,
    atomic_write_json,
)

SERVE_DIR = ROOT / "serve"
ELECTED_CSV = ROOT / "local" / "source" / "electedofficials.csv"
OUTPUT = SERVE_DIR / "partisan_profiles.json"

# Parquet columns Stage 7 reads. Source cols stay ALL_CAPS; derived stay snake_case.
SCORING_COLS = [
    "SOS_VOTERID", "LAST_NAME", "FIRST_NAME", "MIDDLE_NAME",
    "VOTER_STATUS", "PARTY_AFFILIATION", "REGISTRATION_DATE",
    "RESIDENTIAL_ZIP", "PRECINCT_NAME", "COUNTY_NUMBER",
    "lean_score", "confidence", "cohort", "cohort_family", "crossover_class",
    "d_primaries", "r_primaries", "x_primaries", "total_primaries",
    "partisan_primaries", "recent_5yr_lean", "last_three_party",
    "years_since_last_partisan", "switch_count",
]


# -- voter index --------------------------------------------------------------

def load_voter_index(county_slug: str) -> dict[str, list[dict]]:
    """Load county voters once and bucket them by UPPER last name for fast matching.

    Filters to ACTIVE / CONFIRMATION (the only two VOTER_STATUS values, section 4)
    and to the target county (COUNTY_NUMBER is a String). Returns
    { upper_last_name: [voter_row_dict, ...] }.
    """
    import polars as pl  # local import; only this path needs polars

    number = COUNTY_NUMBER[county_slug]
    df = (
        pl.scan_parquet(ENRICHED_PARQUET)
        .filter(pl.col("COUNTY_NUMBER") == number)
        .filter(pl.col("VOTER_STATUS").is_in(["ACTIVE", "CONFIRMATION"]))
        .select(SCORING_COLS)
        .collect()
    )

    index: dict[str, list[dict]] = {}
    for row in df.iter_rows(named=True):
        # Matching keys (transient, not persisted): UPPER name parts.
        row["_last_u"] = (row["LAST_NAME"] or "").strip().upper()
        row["_first_u"] = (row["FIRST_NAME"] or "").strip().upper()
        row["_middle_u"] = (row["MIDDLE_NAME"] or "").strip().upper()
        index.setdefault(row["_last_u"], []).append(row)
    return index


# -- the single voter-matching resolver ---------------------------------------

def match_entity(
    index: dict[str, list[dict]],
    last: str,
    first: str,
    constraint: tuple[str, str] | None,
    fuzz,
    process,
) -> tuple[dict | None, str, int | None]:
    """Find the one voter record for a filer. The ONLY voter-matcher (section 5).

    constraint is ("zip", "45402") | ("precinct", "DAYTON 3-E") | None and is the
    sole per-entity-type difference. Two-pass strategy mirrors the proven template
    in tools/lookup/match_officials_to_voters.py: exact last + first[:3] prefix,
    then rapidfuzz token_sort_ratio (cutoff 80). Returns (row|None, method, score).
    """
    last_u = last.strip().upper()
    first_u = first.strip().upper()
    bucket = index.get(last_u, [])
    if not bucket:
        return None, "no_last_match", None

    prefix = first_u[:3]
    pass1 = [r for r in bucket if r["_first_u"].startswith(prefix)]
    pool = pass1 if pass1 else bucket

    # Apply the optional location constraint to disambiguate same-name voters.
    if constraint is not None:
        kind, val = constraint
        if kind == "zip":
            hits = [r for r in pool if (r["RESIDENTIAL_ZIP"] or "") == val]
        elif kind == "precinct":
            hits = [r for r in pool if (r["PRECINCT_NAME"] or "") == val]
        else:
            raise ValueError(f"unknown constraint kind: {kind!r}")
        if len(hits) == 1:
            return hits[0], f"exact_prefix+{kind}", 100
        if hits:
            pool = hits  # narrowed but still ambiguous -> fall through to fuzzy

    if len(pool) == 1:
        return pool[0], "exact_prefix", 100

    # Pass 2: fuzzy on the full name within the remaining pool.
    query_name = f"{first_u} {last_u}".strip()
    choice_map = {
        f"{r['_first_u']} {r['_middle_u']} {r['_last_u']}".strip(): r for r in pool
    }
    best = process.extractOne(
        query_name, choice_map.keys(),
        scorer=fuzz.token_sort_ratio, score_cutoff=80,
    )
    if best:
        return choice_map[best[0]], "fuzzy", int(best[1])
    return None, "ambiguous", None


# -- name parsing -------------------------------------------------------------

_SUFFIXES = {"JR", "SR", "II", "III", "IV", "V", "JR.", "SR."}


def split_display_name(name: str) -> tuple[str, str]:
    """Split a display name into (first, last) for voter matching.

    Serve names are first-last order (never "LAST, FIRST" -- the only commas are
    suffix commas, per officials_common.normalize_name). We drop middle tokens and
    trailing suffixes: "Gregory A. Brush" -> ("Gregory", "Brush");
    "Hugh M. Quill, Jr" -> ("Hugh", "Quill").
    """
    cleaned = name.replace(",", " ").strip()
    tokens = [t for t in cleaned.split() if t]
    tokens = [t for t in tokens if t.upper().rstrip(".") not in
              {s.rstrip(".") for s in _SUFFIXES}]
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return "", tokens[0]
    return tokens[0], tokens[-1]


# -- partisan_profile builder -------------------------------------------------

def derive_profile_label(party_aff: str, d_prim: int, r_prim: int,
                         x_prim: int, cohort: str | None) -> str:
    """Plain-English partisan label. Gate on PARTY_AFFILIATION + primary counts
    (+ cohort for crossover direction), NEVER on years_since_last_partisan
    (CLAUDE.md section 4; handoff Stage 7).
    """
    pa = (party_aff or "").strip()  # null defensively folded to "" (lapse signal)
    if d_prim and not r_prim:
        return "Pure D" if pa == "D" else "Lapsed D"
    if r_prim and not d_prim:
        return "Pure R" if pa == "R" else "Lapsed R"
    if d_prim and r_prim:
        if cohort == "CROSSOVER_D":
            return "Crossover (D-leaning)"
        if cohort == "CROSSOVER_R":
            return "Crossover (R-leaning)"
        return "Crossover (Mixed)"
    if x_prim and not d_prim and not r_prim:
        return "Non-Partisan Voter"
    return "No Primary History"


def build_profile(entity_type: str, identity: dict, row: dict,
                  method: str, score: int | None) -> dict:
    """Assemble the partisan_profile record for one matched filer.

    Source cols keep ALL_CAPS (PARTY_AFFILIATION, VOTER_STATUS); derived cols are
    snake_case; the label is Title Case (CLAUDE.md section 6).
    """
    d_prim = int(row["d_primaries"] or 0)
    r_prim = int(row["r_primaries"] or 0)
    x_prim = int(row["x_primaries"] or 0)
    label = derive_profile_label(row["PARTY_AFFILIATION"], d_prim, r_prim, x_prim,
                                 row["cohort"])
    profile = {
        "entity_type": entity_type,
        "match_method": method,
        "match_score": score,
        "sos_voterid": row["SOS_VOTERID"],
        "voter_status": row["VOTER_STATUS"],
        "registration_date": str(row["REGISTRATION_DATE"]) if row["REGISTRATION_DATE"] else None,
        "residential_zip": row["RESIDENTIAL_ZIP"],
        "PARTY_AFFILIATION": row["PARTY_AFFILIATION"],
        "lean_score": row["lean_score"],
        "lean_confidence": row["confidence"],      # source col `confidence`, renamed
        "cohort": row["cohort"],
        "cohort_family": row["cohort_family"],
        "crossover_class": row["crossover_class"],
        "d_primaries": d_prim,
        "r_primaries": r_prim,
        "x_primaries": x_prim,
        "total_primaries": int(row["total_primaries"] or 0),
        "recent_5yr_lean": row["recent_5yr_lean"],
        "last_three_party": row["last_three_party"],
        "years_since_last_partisan": row["years_since_last_partisan"],
        "switch_count": int(row["switch_count"] or 0),
        "partisan_profile_label": label,
    }
    profile.update(identity)  # name, office/precinct/section -- traceability
    return profile


# -- entity extraction (per serve file) ---------------------------------------

def _persons_in_officials(officials: dict):
    """Yield (identity_dict, person_dict) for every incumbent in officials.json.

    Walks district sections (incumbent + challengers) and jurisdiction sections
    (incumbents[]/challengers[], plus VILLAGE's nested offices[].incumbent).
    """
    for section, body in officials.items():
        if section.startswith("_"):
            continue
        for key, entry in body.items():
            office = entry.get("office", "")
            # district-style: single `incumbent` + `challengers`
            inc = entry.get("incumbent")
            if isinstance(inc, dict) and inc.get("name"):
                yield {"name": inc["name"], "section": section, "key": key,
                       "office": office, "role": "incumbent"}, inc
            for ch in entry.get("challengers", []) or []:
                if ch.get("name"):
                    yield {"name": ch["name"], "section": section, "key": key,
                           "office": office, "role": "challenger"}, ch
            # jurisdiction-style: incumbents[]
            for person in entry.get("incumbents", []) or []:
                if person.get("name"):
                    yield {"name": person["name"], "section": section, "key": key,
                           "office": office, "role": "incumbent"}, person
            # VILLAGE: nested offices[].incumbent
            for off in entry.get("offices", []) or []:
                vinc = off.get("incumbent")
                if isinstance(vinc, dict) and vinc.get("name"):
                    yield {"name": vinc["name"], "section": section, "key": key,
                           "office": off.get("office", office),
                           "role": "incumbent"}, vinc


def _home_zip_index() -> dict[tuple[str, str], str]:
    """Build (LASTN_upper, FIRSTN_upper) -> HZIPCODE from electedofficials.csv.

    HZIPCODE only (home zip). NEVER OZIPCODE (office address) -- section 4.
    """
    out: dict[tuple[str, str], str] = {}
    for row in csv.DictReader(ELECTED_CSV.open(encoding="utf-8")):
        hz = (row.get("HZIPCODE") or "").strip()
        if not hz:
            continue
        key = ((row.get("LASTN") or "").strip().upper(),
               (row.get("FIRSTN") or "").strip().upper())
        out[key] = hz.zfill(5)
    return out


# -- driver -------------------------------------------------------------------

def run(county_slug: str, verbose: bool) -> dict:
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        print("ERROR: rapidfuzz not installed. Run: uv add rapidfuzz", file=sys.stderr)
        sys.exit(1)

    index = load_voter_index(county_slug)
    n_voters = sum(len(v) for v in index.values())
    print(f"Loaded {n_voters:,} ACTIVE/CONFIRMATION voters for {county_slug} "
          f"({len(index):,} distinct surnames)")

    officials = json.loads((SERVE_DIR / "officials.json").read_text(encoding="utf-8"))
    captains = json.loads((SERVE_DIR / "precinct_captains.json").read_text(encoding="utf-8"))
    candidates = json.loads((SERVE_DIR / "candidates.json").read_text(encoding="utf-8"))
    hz_index = _home_zip_index()

    out: dict[str, list[dict]] = {"incumbent": [], "captain_candidate": [], "general_candidate": []}
    unmatched: dict[str, list[str]] = {"incumbent": [], "captain_candidate": [], "general_candidate": []}

    def _record(entity_type, identity, last, first, constraint):
        row, method, score = match_entity(index, last, first, constraint, fuzz, process)
        if row is None:
            unmatched[entity_type].append(identity["name"])
            if verbose:
                print(f"  MISS [{entity_type}] {identity['name']} ({method})")
            return
        out[entity_type].append(build_profile(entity_type, identity, row, method, score))
        if verbose:
            print(f"  HIT  [{entity_type}/{method}/{score}] {identity['name']} "
                  f"-> {row['SOS_VOTERID']}")

    # incumbent -- zip from HZIPCODE (home), name-only when no CSV row exists.
    for identity, _person in _persons_in_officials(officials):
        # Office-level signal alongside the voter-derived partisan_profile: the
        # office being nonpartisan (charter fact) is independent of the holder's
        # actual party. Carry both so a consumer sees them in one record (Q1).
        identity["nonpartisan_office"] = bool(_person.get("nonpartisan"))
        identity["filing_party"] = _person.get("party")
        first, last = split_display_name(identity["name"])
        hz = hz_index.get((last.upper(), first.upper()))
        constraint = ("zip", hz) if hz else None
        _record("incumbent", identity, last, first, constraint)

    # captain_candidate -- no zip anywhere; constrain by PRECINCT_NAME (the serve key).
    for precinct_name, parties in captains.items():
        if precinct_name.startswith("_"):
            continue
        for party_letter, pobj in parties.items():
            for person in pobj.get("candidates", []) or []:
                if person.get("write_in"):
                    continue  # write-ins are not registered filers we can locate
                first, last = split_display_name(person["name"])
                identity = {"name": person["name"], "precinct_name": precinct_name,
                            # party_letter = which party committee they filed for;
                            # filing_party = the (D)/(L)/(R) suffix (null for a
                            # crossfiler in another party's primary). Central
                            # committee is partisan -> nonpartisan_office False.
                            "party_letter": party_letter,
                            "filing_party": person.get("party"),
                            "nonpartisan_office": False,
                            "status": pobj.get("status")}
                _record("captain_candidate", identity, last, first,
                        ("precinct", precinct_name))

    # general_candidate -- zip from address.zip; name-only when withheld ("On File").
    for section, body in candidates.items():
        if section.startswith("_"):
            continue
        for key, entry in body.items():
            office = entry.get("office", "")
            for person in entry.get("candidates", []) or []:
                first, last = split_display_name(person["name"])
                addr = person.get("address") or {}
                z = (addr.get("zip") or "").strip()
                constraint = ("zip", z.zfill(5)) if z else None
                identity = {"name": person["name"], "section": section, "key": key,
                            "office": office,
                            # filing/ballot party -- may be "I" or another party
                            # even when primary history leans differently (Q1); the
                            # behavior-derived party lives in partisan_profile.
                            "filing_party": person.get("party"),
                            "nonpartisan_office": bool(person.get("nonpartisan"))}
                _record("general_candidate", identity, last, first, constraint)

    meta = {
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "county": county_slug,
        "county_number": COUNTY_NUMBER[county_slug],
        "source_files": {
            "officials": "serve/officials.json",
            "precinct_captains": "serve/precinct_captains.json",
            "candidates": "serve/candidates.json",
            "voters": str(ENRICHED_PARQUET.relative_to(ROOT)),
        },
        "match_summary": {
            et: {"matched": len(out[et]), "unmatched": len(unmatched[et])}
            for et in out
        },
        "unmatched": unmatched,  # gaps are surfaced, not silently dropped (section 5)
        "notes": [
            "captain_candidate matches are name + PRECINCT_NAME only (no zip exists); "
            "treat as lower-confidence than zip-disambiguated matches.",
            "lapse signal = PARTY_AFFILIATION == '' (section 4); label never gates on "
            "years_since_last_partisan.",
        ],
    }
    result = {"_meta": meta}
    result.update(out)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 7: match filers to voter records.")
    ap.add_argument("--county", default="montgomery", help="county slug (default montgomery)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.county not in COUNTY_NUMBER:
        print(f"[abort] unknown county slug {args.county!r}; known: {list(COUNTY_NUMBER)}",
              file=sys.stderr)
        return 1

    result = run(args.county, args.verbose)
    nbytes = atomic_write_json(OUTPUT, result)
    s = result["_meta"]["match_summary"]
    print(f"\nWrote {OUTPUT.relative_to(ROOT)} ({nbytes:,} bytes)")
    for et, c in s.items():
        print(f"  {et:18s} matched {c['matched']:4d}  unmatched {c['unmatched']:4d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
