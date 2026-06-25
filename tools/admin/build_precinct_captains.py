"""build_precinct_captains.py -- Stage 5: intermediate captain filings -> serve JSON.

Reads the three Stage-3 intermediate files (captain_filings_{county}_{D,L,R}.json)
and the precinct crosswalk, and writes serve/precinct_captains.json keyed by exact
parquet PRECINCT_NAME -- the file the captain UI and the roster API read.

Per precinct, per party:
  filings present  -> "contested" (>=2) or "uncontested" (1), with the candidate list
  no filing, coverage == "complete" -> "vacant"        (nobody filed)
  no filing, coverage == "partial"  -> "data_pending"   (data not yet loaded, e.g. R)

The `coverage` flag from Stage 3 is what separates "nobody filed" from "we don't
have the data yet" -- without it, R precincts with no CSV row would be mislabeled
vacant instead of data_pending.

Usage:
    python tools/admin/build_precinct_captains.py --county montgomery
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import (  # noqa: E402
    COUNTY_NUMBER,
    ROOT,
    load_precinct_crosswalk,
    atomic_write_json,
)

WORKING_DIR = ROOT / "local" / "working"
SERVE_JSON = ROOT / "serve" / "precinct_captains.json"
PARTIES = ("D", "L", "R")

# Constant per-party context for _meta (term dates are fixed per the BoE reports).
PARTY_LABEL = {"D": "Democratic", "L": "Libertarian", "R": "Republican"}


def _load_intermediate(county: str, party: str) -> dict:
    path = WORKING_DIR / f"captain_filings_{county}_{party}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path.name}; run parse_central_committee.py --county {county} --all-parties first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build(county: str) -> dict:
    xw = load_precinct_crosswalk(county)
    intermediates = {p: _load_intermediate(county, p) for p in PARTIES}

    # index filings by (party, precinct_name)
    by_precinct: dict[str, dict[str, list]] = defaultdict(lambda: {p: [] for p in PARTIES})
    for party, data in intermediates.items():
        for f in data["filings"]:
            by_precinct[f["precinct_name"]][party].append(f)

    out: dict = {}
    for ballot in xw.all_ballots:                      # ballot-number order (stable)
        precinct = xw.resolve(ballot)
        entry: dict = {}
        for party in PARTIES:
            filings = by_precinct[precinct][party]
            coverage = intermediates[party]["coverage"]
            if filings:
                status = "contested" if len(filings) >= 2 else "uncontested"
                candidates = [
                    {"name": f["name_normalized"], "party": f["party"], "write_in": f["write_in"]}
                    for f in filings
                ]
            else:
                status = "vacant" if coverage == "complete" else "data_pending"
                candidates = []
            entry[party] = {"status": status, "candidates": candidates}
        out[precinct] = entry

    meta = _build_meta(county, intermediates, out)
    return {"_meta": meta, **out}


def _build_meta(county: str, intermediates: dict, out: dict) -> dict:
    from collections import Counter

    party_meta = {}
    sources = []
    for party in PARTIES:
        data = intermediates[party]
        tally = Counter(out[p][party]["status"] for p in out)
        party_meta[party] = {
            "label": PARTY_LABEL[party],
            "source": data["source"],
            "source_file": data.get("source_file"),
            "retrieved_date": data.get("retrieved_date"),
            "coverage": data["coverage"],
            "filings": len(data["filings"]),
            "gaps": data.get("gaps", []),
            "status_counts": dict(tally),
        }
        if data.get("source_file"):
            sources.append(f"{data['source_file']} ({PARTY_LABEL[party]}, retrieved {data.get('retrieved_date')})")

    return {
        "generated": date.today().isoformat(),
        "county": county.title(),
        "county_number": int(COUNTY_NUMBER[county]),
        "primary_date": "2026-05-05",
        "keyed_by": "PRECINCT_NAME (exact enriched_voters.parquet values)",
        "parties": party_meta,
        "sources": sources,
        "status_semantics": {
            "uncontested": "single filer (elected unopposed in the primary)",
            "contested": "2+ filers; certified primary result needed to pick the winner",
            "vacant": "no one filed (source covers every precinct)",
            "data_pending": "filings not yet loaded for this party (e.g. R awaiting the BoE PDF)",
        },
        "notes": [
            "Keys match exact PRECINCT_NAME values in enriched_voters.parquet.",
            "Candidate 'party' is null when the BoE filing carried no party suffix "
            "(crossfiler / unaffiliated registrant running in that party's primary).",
            "D/L statuses come from 2026 primary central-committee filing reports "
            "(pre-certification); R comes from the elected-officials CSV (current "
            "officeholder), so R precincts without a CSV row are data_pending, not vacant.",
            "Contested races are frozen at the filer list; the certified-result pass "
            "(Session 2) resolves winners.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build serve/precinct_captains.json from Stage-3 filings.")
    ap.add_argument("--county", default="montgomery")
    args = ap.parse_args()
    if args.county not in COUNTY_NUMBER:
        print(f"ERROR: unknown county slug {args.county!r}", file=sys.stderr)
        sys.exit(1)

    result = build(args.county)
    n = atomic_write_json(SERVE_JSON, result)

    from collections import Counter
    print(f"-> {SERVE_JSON.relative_to(ROOT)}: {len(result) - 1} precincts ({n:,} bytes)")
    for party in PARTIES:
        tally = Counter(result[p][party]["status"] for p in result if p != "_meta")
        print(f"   {party}: {dict(tally)}")


if __name__ == "__main__":
    main()
