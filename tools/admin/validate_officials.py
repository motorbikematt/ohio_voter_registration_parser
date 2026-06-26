"""validate_officials.py -- Stage 8: integrity gate for the officials pipeline.

Bounded checks (CLAUDE.md §7) across every serve/*.json plus the Stage-7 output,
and the schema drift gate. Loud failure on any problem; non-zero exit (CLAUDE.md §5).
This is the build's quality bar -- run it after every producer/consumer change and
on every new SWVF drop, the same role tools/admin/validate_jurisdiction_fields.py
plays for the voter pipeline.

Checks:
  1. precinct_captains keys are exact parquet PRECINCT_NAME values (no slugs).
  2. captain `status` values are in the known vocabulary.
  3. DEM `_meta.parties.D.gaps` ballots map to precincts marked `vacant`
     (gaps are gaps, not silent drops).
  4. every person object across officials/candidates has name + party/nonpartisan.
  5. partisan_profiles.json (if present) is well-formed: known labels, gaps surfaced.
  6. schema drift: dump_schema regenerates the inventory; STALE blocks fail the build.

Usage:
    python tools/admin/validate_officials.py --county montgomery
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import (  # noqa: E402
    COUNTY_NUMBER,
    ROOT,
    load_parquet_precinct_names,
    load_precinct_crosswalk,
)
import csv  # noqa: E402
import dump_schema  # noqa: E402
import ingest_elected_officials as ingest  # noqa: E402  (single district resolver)

SERVE_DIR = ROOT / "serve"

CAPTAIN_STATUSES = {"uncontested", "contested", "vacant", "data_pending"}
PROFILE_LABELS = {
    "Pure D", "Lapsed D", "Pure R", "Lapsed R",
    "Crossover (D-leaning)", "Crossover (R-leaning)", "Crossover (Mixed)",
    "Non-Partisan Voter", "No Primary History",
}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        self.checks += 1
        if ok:
            print(f"  [pass] {label}")
        else:
            print(f"  [FAIL] {label}: {detail}")
            self.failures.append(f"{label}: {detail}")


# -- person walkers ------------------------------------------------------------

def _iter_people(obj: dict):
    """Yield person dicts from officials.json / candidates.json structures."""
    for section, body in obj.items():
        if section.startswith("_"):
            continue
        for key, entry in body.items():
            inc = entry.get("incumbent")
            if isinstance(inc, dict):
                yield section, key, inc
            for bucket in ("incumbents", "challengers", "candidates"):
                for p in entry.get(bucket, []) or []:
                    yield section, key, p
            for off in entry.get("offices", []) or []:
                vinc = off.get("incumbent")
                if isinstance(vinc, dict):
                    yield section, key, vinc


# -- checks --------------------------------------------------------------------

def check_captains(rep: Report, county_slug: str) -> None:
    print("\n[precinct_captains.json]")
    captains = json.loads((SERVE_DIR / "precinct_captains.json").read_text(encoding="utf-8"))
    valid_names = load_parquet_precinct_names(county_slug)

    keys = [k for k in captains if not k.startswith("_")]
    bad_keys = [k for k in keys if k not in valid_names]
    rep.check(not bad_keys, "captain keys are exact parquet PRECINCT_NAME values",
              f"{len(bad_keys)} unknown: {bad_keys[:5]}")

    bad_status = []
    for pname in keys:
        for party_letter, pobj in captains[pname].items():
            st = pobj.get("status")
            if st not in CAPTAIN_STATUSES:
                bad_status.append(f"{pname}/{party_letter}={st!r}")
    rep.check(not bad_status, "captain status values are in the known vocabulary",
              f"{len(bad_status)} bad: {bad_status[:5]}")

    # gaps are gaps: DEM gap ballots must resolve to vacant precincts.
    meta = captains.get("_meta", {})
    gaps = (meta.get("parties", {}).get("D", {}) or {}).get("gaps", []) or []
    if gaps:
        xwalk = load_precinct_crosswalk(county_slug)
        not_vacant = []
        for ballot in gaps:
            pname = xwalk.resolve(ballot)
            if pname is None:
                not_vacant.append(f"{ballot}=unresolved")
            elif captains.get(pname, {}).get("D", {}).get("status") != "vacant":
                not_vacant.append(f"{ballot}->{pname}")
        rep.check(not not_vacant, "DEM gap ballots map to vacant precincts",
                  f"{len(not_vacant)}: {not_vacant[:5]}")
    else:
        print("  [skip] no DEM gaps recorded")


def check_people(rep: Report, fname: str) -> None:
    print(f"\n[{fname}]")
    obj = json.loads((SERVE_DIR / fname).read_text(encoding="utf-8"))
    missing_name = []
    bad_party = []
    for section, key, p in _iter_people(obj):
        if not (p.get("name") or "").strip():
            missing_name.append(f"{section}/{key}")
        # party must be a letter, OR null with nonpartisan:true (a charter fact, §schema)
        party = p.get("party")
        if party is None and not p.get("nonpartisan"):
            bad_party.append(f"{section}/{key}/{p.get('name')}")
    rep.check(not missing_name, "every person has a non-empty name",
              f"{len(missing_name)}: {missing_name[:5]}")
    rep.check(not bad_party, "null party is always flagged nonpartisan:true",
              f"{len(bad_party)}: {bad_party[:5]}")


def check_profiles(rep: Report) -> None:
    path = SERVE_DIR / "partisan_profiles.json"
    print("\n[partisan_profiles.json]")
    if not path.exists():
        print("  [skip] not generated yet (run match_to_voters.py)")
        return
    obj = json.loads(path.read_text(encoding="utf-8"))
    rep.check("_meta" in obj and "unmatched" in obj.get("_meta", {}),
              "_meta.unmatched is present (gaps surfaced)", "missing")
    bad_label, missing_id = [], []
    for et in ("incumbent", "captain_candidate", "general_candidate"):
        for prof in obj.get(et, []) or []:
            if prof.get("partisan_profile_label") not in PROFILE_LABELS:
                bad_label.append(f"{et}/{prof.get('name')}={prof.get('partisan_profile_label')!r}")
            if not (prof.get("sos_voterid") or "").strip():
                missing_id.append(f"{et}/{prof.get('name')}")
    rep.check(not bad_label, "all partisan_profile_label values are known",
              f"{len(bad_label)}: {bad_label[:5]}")
    rep.check(not missing_id, "every matched profile has a sos_voterid",
              f"{len(missing_id)}: {missing_id[:5]}")


def check_district_reconciliation(rep: Report) -> None:
    """Stage-8 gate: district incumbency must reconcile against the CSV holder.

    Re-derives the district sections from electedofficials.csv + candidates.json
    via the single resolver, then asserts the committed officials.json agrees.
    Open seat / incumbent-ran-for-higher-office (no marked filer) is expected and
    passes; a marker that names a different person than the CSV holder fails.
    """
    print("\n[district incumbency reconciliation]")
    officials = json.loads((SERVE_DIR / "officials.json").read_text(encoding="utf-8"))
    candidates = json.loads((SERVE_DIR / "candidates.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(ingest.DEFAULT_CSV.open(encoding="utf-8")))
    district_rows = [r for r in rows if r["DISTTYPE"] in ingest.DISTRICT_SECTION]
    derived = ingest.build_district_sections(district_rows, candidates)

    unreconciled = [
        f"{section}/{key}"
        for section, body in derived.items()
        for key, entry in body.items()
        if not entry["reconciled"]
    ]
    rep.check(not unreconciled,
              "every district race-incumbent (marker) agrees with the CSV holder",
              f"{len(unreconciled)}: {unreconciled[:5]}")

    drift = []
    for section, body in derived.items():
        for key, entry in body.items():
            want = (entry["incumbent"] or {}).get("name")
            got = ((officials.get(section, {}).get(key, {}) or {}).get("incumbent") or {}).get("name")
            if want != got:
                drift.append(f"{section}/{key}: officials={got!r} derived={want!r}")
    rep.check(not drift,
              "officials.json district incumbents match a fresh CSV derivation",
              f"{len(drift)}: {drift[:5]}")


def check_drift(rep: Report) -> None:
    print("\n[schema drift]")
    problems = dump_schema.check_drift()
    rep.check(not problems, "schema inventory in sync with live artifacts",
              "; ".join(problems))


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 8: validate the officials pipeline.")
    ap.add_argument("--county", default="montgomery")
    args = ap.parse_args()
    if args.county not in COUNTY_NUMBER:
        print(f"[abort] unknown county slug {args.county!r}", file=sys.stderr)
        return 1

    rep = Report()
    check_captains(rep, args.county)
    check_people(rep, "officials.json")
    check_people(rep, "candidates.json")
    check_profiles(rep)
    check_district_reconciliation(rep)
    check_drift(rep)

    print(f"\n{'=' * 56}")
    if rep.failures:
        print(f"VALIDATION FAILED: {len(rep.failures)}/{rep.checks} checks failed")
        for f in rep.failures:
            print(f"  - {f}")
        return 1
    print(f"VALIDATION PASSED: {rep.checks}/{rep.checks} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
