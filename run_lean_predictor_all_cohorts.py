"""
run_lean_predictor_all_cohorts.py
=================================
Driver for mixed_lean_predictor.py. Iterates every *_targets.csv in any of
the cohort subdirectories of UNC_Exports/ and runs the per-voter lean
predictor against each, writing one *_scored.csv and one *_summary.csv per
(cohort, county). Aggregates a statewide summary at the end.

Cohorts handled:
    Mixed/        ->  *_MIXED_targets.csv        (UNC, MIXED ballot history)
    Lifetime_D/   ->  *_LIFETIME_D_targets.csv   (UNC, only D primaries)
    Lifetime_R/   ->  *_LIFETIME_R_targets.csv   (UNC, only R primaries)
    Current_D/    ->  *_CURRENT_D_targets.csv    (currently affiliated D)
    Current_R/    ->  *_CURRENT_R_targets.csv    (currently affiliated R)

No_History is intentionally excluded (zero partisan ballots -> nothing to score).

Usage (Windows, from the project root):
    python run_lean_predictor_all_cohorts.py
    python run_lean_predictor_all_cohorts.py --cohorts Mixed,Current_D
    python run_lean_predictor_all_cohorts.py --counties montgomery,franklin
    python run_lean_predictor_all_cohorts.py --workers 8 --skip-existing

The predictor itself is mixed_lean_predictor.py and reads its CONFIG from
environment variables MIXED_INPUT_CSV / MIXED_OUTPUT_CSV / MIXED_SUMMARY_CSV.
All tunables (decay, thresholds, AS_OF_DATE) live inside that script.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import polars as pl

# --- CONFIG --------------------------------------------------------------
PROJECT_ROOT = Path(r"D:\vibe\election-data (1)")
PREDICTOR = PROJECT_ROOT / "mixed_lean_predictor.py"
EXPORT_ROOT = PROJECT_ROOT / "UNC_Exports"
STATEWIDE_DIR = EXPORT_ROOT / "_Statewide"

# Cohort subdir -> filename suffix used to identify input targets.
COHORTS: dict[str, str] = {
    "Mixed":      "MIXED",
    "Lifetime_D": "LIFETIME_D",
    "Lifetime_R": "LIFETIME_R",
    "Current_D":  "CURRENT_D",
    "Current_R":  "CURRENT_R",
}


def discover(cohort_dir: Path, suffix: str,
             restrict: list[str] | None) -> list[tuple[str, Path]]:
    """Return [(county_name, input_csv_path), ...] for one cohort."""
    pattern = re.compile(rf"^(?P<county>.+)_{suffix}_targets\.csv$", re.IGNORECASE)
    found = []
    if not cohort_dir.exists():
        return found
    for p in cohort_dir.glob(f"*_{suffix}_targets.csv"):
        m = pattern.match(p.name)
        if not m:
            continue
        county = m.group("county").lower()
        if restrict and county not in restrict:
            continue
        found.append((county, p))
    return sorted(found, key=lambda x: x[0])


def run_one(cohort: str, suffix: str, county: str,
            input_csv: Path, skip_existing: bool) -> dict:
    """Invoke the predictor as a subprocess for a single (cohort, county)."""
    output_csv = input_csv.with_name(f"{county}_{suffix}_scored.csv")
    summary_csv = input_csv.with_name(f"{county}_{suffix}_summary.csv")

    if skip_existing and output_csv.exists() and summary_csv.exists():
        return {"cohort": cohort, "county": county, "status": "skipped",
                "scored": output_csv, "summary": summary_csv}

    env = os.environ.copy()
    env["MIXED_INPUT_CSV"] = str(input_csv)
    env["MIXED_OUTPUT_CSV"] = str(output_csv)
    env["MIXED_SUMMARY_CSV"] = str(summary_csv)

    print(f"[run] {cohort}/{county}: {input_csv.name}", flush=True)
    proc = subprocess.run(
        [sys.executable, str(PREDICTOR)],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"[fail] {cohort}/{county} (exit {proc.returncode})\n"
              f"--stdout--\n{proc.stdout}\n--stderr--\n{proc.stderr}", flush=True)
        return {
            "cohort": cohort, "county": county, "status": "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr,
        }
    return {
        "cohort": cohort, "county": county, "status": "ok",
        "scored": output_csv, "summary": summary_csv,
    }


def aggregate_summaries(results: list[dict]) -> None:
    """Stitch every per-(cohort, county) *_summary.csv into statewide rollups."""
    rows = []
    for r in results:
        if r.get("status") != "ok":
            continue
        sp = r["summary"]
        if not Path(sp).exists():
            continue
        try:
            df = pl.read_csv(sp)
            df = df.with_columns([
                pl.lit(r["cohort"]).alias("cohort"),
                pl.lit(r["county"]).alias("county"),
            ])
            rows.append(df)
        except Exception as e:
            print(f"[warn] could not read {sp}: {e}")

    if not rows:
        print("[agg] no per-county summaries to aggregate")
        return

    STATEWIDE_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = pl.concat(rows, how="diagonal_relaxed")
    by_county_path = STATEWIDE_DIR / "_statewide_summary_by_county.csv"
    all_rows.write_csv(by_county_path)
    print(f"[write] {by_county_path}")

    statewide = (
        all_rows.group_by(["cohort", "prediction"])
        .agg([
            pl.col("n").sum().alias("n"),
            (pl.col("mean_lean") * pl.col("n")).sum().alias("_lean_num"),
            pl.col("n").sum().alias("_lean_den"),
        ])
        .with_columns((pl.col("_lean_num") / pl.col("_lean_den")).round(3).alias("mean_lean"))
        .drop(["_lean_num", "_lean_den"])
        .sort(["cohort", "n"], descending=[False, True])
    )
    statewide_path = STATEWIDE_DIR / "_statewide_summary.csv"
    statewide.write_csv(statewide_path)
    print(f"[write] {statewide_path}")
    with pl.Config(tbl_rows=50):
        print("\n[statewide totals by cohort]")
        print(statewide)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--counties", default="",
                    help="comma-separated subset, e.g. montgomery,franklin")
    ap.add_argument("--cohorts", default="",
                    help=f"comma-separated subset of {list(COHORTS.keys())}")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip jobs whose *_scored.csv and *_summary.csv already exist")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel worker processes (default 1)")
    args = ap.parse_args()

    if not PREDICTOR.exists():
        sys.exit(f"predictor script not found: {PREDICTOR}")
    if not EXPORT_ROOT.exists():
        sys.exit(f"export root not found: {EXPORT_ROOT}")

    restrict_counties = [c.strip().lower() for c in args.counties.split(",") if c.strip()] or None
    restrict_cohorts = [c.strip() for c in args.cohorts.split(",") if c.strip()] or None
    cohorts = {k: v for k, v in COHORTS.items() if not restrict_cohorts or k in restrict_cohorts}
    if not cohorts:
        sys.exit(f"no cohorts matched. Available: {list(COHORTS.keys())}")

    jobs: list[tuple[str, str, str, Path]] = []
    for cohort, suffix in cohorts.items():
        cohort_dir = EXPORT_ROOT / cohort
        for county, p in discover(cohort_dir, suffix, restrict_counties):
            jobs.append((cohort, suffix, county, p))

    if not jobs:
        sys.exit("no *_targets.csv files matched")
    print(f"[plan] {len(jobs)} (cohort, county) jobs across {len(cohorts)} cohort(s), "
          f"workers={args.workers}, skip_existing={args.skip_existing}")

    results: list[dict] = []
    if args.workers <= 1:
        for cohort, suffix, county, p in jobs:
            results.append(run_one(cohort, suffix, county, p, args.skip_existing))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(run_one, cohort, suffix, county, p, args.skip_existing):
                    (cohort, county) for cohort, suffix, county, p in jobs}
            for f in as_completed(futs):
                results.append(f.result())

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = [r for r in results if r["status"] == "failed"]
    print(f"\n[done] ok={ok}, skipped={skipped}, failed={len(failed)}")
    for r in failed:
        print(f"  - {r['cohort']}/{r['county']}: rc={r['returncode']}")

    aggregate_summaries(results)


if __name__ == "__main__":
    main()
