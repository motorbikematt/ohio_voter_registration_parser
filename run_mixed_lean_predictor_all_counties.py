"""
run_mixed_lean_predictor_all_counties.py
========================================
Driver for mixed_lean_predictor.py. Iterates every *_MIXED_targets.csv in the
UNC_Exports/Mixed directory and runs the per-voter lean predictor against each,
writing one *_scored.csv and one *_summary.csv per county. Aggregates a
statewide summary at the end.

Assumes the upstream UNC export step has already produced one MIXED file per
county, named like:  <county_name>_MIXED_targets.csv

Usage (Windows, from the project root):
    python run_mixed_lean_predictor_all_counties.py

Optional flags:
    --counties montgomery,franklin,cuyahoga    # restrict to a subset
    --skip-existing                            # don't re-score files that already have a *_scored.csv
    --workers N                                # parallelism (default: 1)

The predictor itself is mixed_lean_predictor.py and reads its CONFIG from
environment variables MIXED_INPUT_CSV / MIXED_OUTPUT_CSV / MIXED_SUMMARY_CSV.
All tunables (decay, thresholds, AS_OF_DATE) live inside that script -- edit
them once there and every county gets the same parameters.
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
MIXED_DIR = PROJECT_ROOT / "UNC_Exports" / "Mixed"
STATEWIDE_SUMMARY = MIXED_DIR / "_statewide_MIXED_summary.csv"
STATEWIDE_DETAILS = MIXED_DIR / "_statewide_MIXED_summary_by_county.csv"

TARGET_RE = re.compile(r"^(?P<county>.+)_MIXED_targets\.csv$", re.IGNORECASE)


def discover_counties(mixed_dir: Path, restrict: list[str] | None) -> list[tuple[str, Path]]:
    """Return [(county_name, input_csv_path), ...] sorted by county name."""
    found = []
    for p in mixed_dir.glob("*_MIXED_targets.csv"):
        m = TARGET_RE.match(p.name)
        if not m:
            continue
        county = m.group("county").lower()
        if restrict and county not in restrict:
            continue
        found.append((county, p))
    return sorted(found, key=lambda x: x[0])


def run_one(county: str, input_csv: Path, skip_existing: bool) -> dict:
    """Invoke the predictor as a subprocess for a single county."""
    output_csv = input_csv.with_name(f"{county}_MIXED_scored.csv")
    summary_csv = input_csv.with_name(f"{county}_MIXED_summary.csv")

    if skip_existing and output_csv.exists() and summary_csv.exists():
        return {"county": county, "status": "skipped", "scored": output_csv, "summary": summary_csv}

    env = os.environ.copy()
    env["MIXED_INPUT_CSV"] = str(input_csv)
    env["MIXED_OUTPUT_CSV"] = str(output_csv)
    env["MIXED_SUMMARY_CSV"] = str(summary_csv)

    print(f"[run] {county}: {input_csv.name}", flush=True)
    proc = subprocess.run(
        [sys.executable, str(PREDICTOR)],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"[fail] {county} (exit {proc.returncode})\n--stdout--\n{proc.stdout}\n--stderr--\n{proc.stderr}",
              flush=True)
        return {
            "county": county,
            "status": "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    return {
        "county": county,
        "status": "ok",
        "scored": output_csv,
        "summary": summary_csv,
    }


def aggregate_summaries(results: list[dict]) -> None:
    """Stitch every per-county *_summary.csv into a statewide rollup."""
    rows = []
    for r in results:
        if r.get("status") != "ok":
            continue
        sp = r["summary"]
        if not Path(sp).exists():
            continue
        try:
            df = pl.read_csv(sp)
            df = df.with_columns(pl.lit(r["county"]).alias("county"))
            rows.append(df)
        except Exception as e:
            print(f"[warn] could not read {sp}: {e}")

    if not rows:
        print("[agg] no per-county summaries to aggregate")
        return

    all_county = pl.concat(rows, how="diagonal_relaxed")
    by_county_path = STATEWIDE_DETAILS
    all_county.write_csv(by_county_path)
    print(f"[write] {by_county_path}")

    statewide = (
        all_county.group_by("prediction")
        .agg([
            pl.col("n").sum().alias("n"),
            (pl.col("mean_lean") * pl.col("n")).sum().alias("_lean_num"),
            pl.col("n").sum().alias("_lean_den"),
        ])
        .with_columns((pl.col("_lean_num") / pl.col("_lean_den")).round(3).alias("mean_lean"))
        .drop(["_lean_num", "_lean_den"])
        .sort("n", descending=True)
    )
    statewide.write_csv(STATEWIDE_SUMMARY)
    print(f"[write] {STATEWIDE_SUMMARY}")
    with pl.Config(tbl_rows=20):
        print("\n[statewide totals]")
        print(statewide)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--counties", default="", help="comma-separated subset, e.g. montgomery,franklin")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip counties whose *_scored.csv and *_summary.csv already exist")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel worker processes (default 1; bump to ~CPU cores for speed)")
    args = ap.parse_args()

    if not PREDICTOR.exists():
        sys.exit(f"predictor script not found: {PREDICTOR}")
    if not MIXED_DIR.exists():
        sys.exit(f"mixed input dir not found: {MIXED_DIR}")

    restrict = [c.strip().lower() for c in args.counties.split(",") if c.strip()] or None
    counties = discover_counties(MIXED_DIR, restrict)
    if not counties:
        sys.exit("no *_MIXED_targets.csv files matched")
    print(f"[plan] {len(counties)} counties to score, workers={args.workers}, "
          f"skip_existing={args.skip_existing}")

    results: list[dict] = []
    if args.workers <= 1:
        for county, p in counties:
            results.append(run_one(county, p, args.skip_existing))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(run_one, c, p, args.skip_existing): c for c, p in counties}
            for f in as_completed(futs):
                results.append(f.result())

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = [r for r in results if r["status"] == "failed"]
    print(f"\n[done] ok={ok}, skipped={skipped}, failed={len(failed)}")
    for r in failed:
        print(f"  - {r['county']}: rc={r['returncode']}")

    aggregate_summaries(results)


if __name__ == "__main__":
    main()
