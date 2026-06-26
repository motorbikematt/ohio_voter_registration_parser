"""build_candidates.py -- Stage 6: candidate filings -> serve/candidates.json.

Reads the Stage-4 intermediate (candidate_filings_{county}.json) and writes
serve/candidates.json, the 2026 general-election candidate roster the dashboard
reads alongside serve/officials.json. Section keys are ALL_CAPS and mirror the
jurisdiction columns (CONGRESSIONAL_DISTRICT, STATE_SENATE_DISTRICT, ...);
candidate sub-keys are snake_case (CLAUDE.md section 6).

Shape (parallels officials.json):
  { "_meta": {...},
    "CONGRESSIONAL_DISTRICT": { "10": { "office": "...", "candidates": [ {...} ] } },
    "STATE_REPRESENTATIVE_DISTRICT": { "36": {...}, "37": {...} },
    "COUNTY_COMMISSIONER": { "county": {...} },
    "STATEWIDE": { "governor-lt-governor": {...} },
    "JUDICIAL": { "court-of-common-pleas-term-begins-1-1-2027": {...} } }

District sections key by the district id (matching officials.json); statewide,
judicial, and county offices key by an office slug. A candidate entry carries the
mailing address (zip feeds Session-2 voter matching) and petition dates.

Usage:
    python tools/admin/build_candidates.py --county montgomery
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import COUNTY_NUMBER, ROOT, atomic_write_json  # noqa: E402

WORKING_DIR = ROOT / "local" / "working"
SERVE_JSON = ROOT / "serve" / "candidates.json"

DISTRICT_SECTIONS = {"CONGRESSIONAL_DISTRICT", "STATE_SENATE_DISTRICT", "STATE_REPRESENTATIVE_DISTRICT"}
COUNTY_SECTIONS = {"COUNTY_COMMISSIONER", "COUNTY_AUDITOR"}
# Section emit order (districts first, then county, then statewide / judicial).
SECTION_ORDER = [
    "CONGRESSIONAL_DISTRICT", "STATE_SENATE_DISTRICT", "STATE_REPRESENTATIVE_DISTRICT",
    "COUNTY_COMMISSIONER", "COUNTY_AUDITOR", "STATEWIDE", "JUDICIAL",
]


def _office_slug(office_raw: str) -> str:
    """Slug an office label, dropping the '(1)' seat-count marker."""
    o = re.sub(r"\(\d+\)", " ", office_raw or "")
    o = re.sub(r"[^a-z0-9]+", "-", o.lower()).strip("-")
    return o or "office"


def _candidate_entry(f: dict) -> dict:
    entry = {
        "name": f["name_normalized"],
        "party": f["party"],
        "address": f.get("address"),
        "petition_filed": f.get("petition_filed"),
        "petition_certified": f.get("petition_certified"),
    }
    if f["party"] is None:
        entry["nonpartisan"] = True
    # Incumbency marker captured from the petition checkbox geometry (parse stage).
    # Carry it through so Stage 7/8 and the district reconciliation gate can see it;
    # stamp the source only on positives to keep non-incumbent entries clean.
    entry["is_incumbent"] = bool(f.get("is_incumbent", False))
    if entry["is_incumbent"]:
        entry["incumbent_source"] = "petition_marker"
    return entry


def build(county: str) -> dict:
    paths = list(WORKING_DIR.glob(f"*_candidate_filings_{county}.json"))
    if not paths:
        raise FileNotFoundError(
            f"missing candidate_filings_{county}.json; run parse_candidate_petitions.py --county {county} first"
        )
    path = paths[0]
    data = json.loads(path.read_text(encoding="utf-8"))

    sections: dict[str, "OrderedDict[str, dict]"] = {s: OrderedDict() for s in SECTION_ORDER}
    for f in data["filings"]:
        sec = f["office_section"]
        if f.get("office_id"):
            key = f["office_id"]
        elif sec in COUNTY_SECTIONS:
            key = "county"
        else:
            key = _office_slug(f["office_raw"])
        bucket = sections.setdefault(sec, OrderedDict())
        if key not in bucket:
            bucket[key] = {"office": f["office_raw"], "candidates": []}
        bucket[key]["candidates"].append(_candidate_entry(f))

    out: dict = {"_meta": _build_meta(county, data, sections)}
    for sec in SECTION_ORDER:
        if sections.get(sec):
            out[sec] = dict(sections[sec])
    return out


def _build_meta(county: str, data: dict, sections: dict) -> dict:
    counts = {s: len(b) for s, b in sections.items() if b}
    total = sum(len(b["candidates"]) for sec in sections.values() for b in sec.values())
    return {
        "generated": date.today().isoformat(),
        "county": county.title(),
        "county_number": int(COUNTY_NUMBER[county]),
        "election_date": data.get("election_date"),
        "valid_through": data.get("election_date") or "2026-11-03",
        "retrieved_date": data.get("retrieved_date"),
        "source": data.get("source"),
        "source_file": data.get("source_file"),
        "total_candidates": total,
        "offices_per_section": counts,
        "notes": [
            "2026 general-election candidates from the Montgomery County BoE "
            "Candidate Petition Report. BoE updates the report weekly; re-run "
            "parse_candidate_petitions.py and this builder on each refresh.",
            "District section keys (CONGRESSIONAL_DISTRICT, STATE_*_DISTRICT) match "
            "officials.json and the enriched_voters.parquet jurisdiction columns; "
            "STATEWIDE/JUDICIAL key by office slug (no parquet jurisdiction).",
            "party is null for nonpartisan offices (most judicial seats); a 'nonpartisan' "
            "flag marks those entries.",
            "address.zip feeds the Session-2 voter-matching pass; 'On File' means the "
            "BoE withheld the street address.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build serve/candidates.json from Stage-4 filings.")
    ap.add_argument("--county", default="montgomery")
    args = ap.parse_args()
    if args.county not in COUNTY_NUMBER:
        print(f"ERROR: unknown county slug {args.county!r}", file=sys.stderr)
        sys.exit(1)

    result = build(args.county)
    n = atomic_write_json(SERVE_JSON, result)
    print(f"-> {SERVE_JSON.relative_to(ROOT)}: {result['_meta']['total_candidates']} candidates ({n:,} bytes)")
    for sec, c in result["_meta"]["offices_per_section"].items():
        print(f"   {sec}: {c} offices")


if __name__ == "__main__":
    main()
