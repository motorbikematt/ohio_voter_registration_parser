"""
ohio_voter_pipeline_wrapper.py
==============================
Master interactive wrapper for the Ohio voter registration pipeline.

Orchestrates the end-to-end flow:

    1. (Optional) UNC + Current_D / Current_R cohort export from raw SWVF files
    2. (Optional) Per-voter lean scoring across all six cohorts
    3. Stakeholder deliverables -- Excel rollup and/or web JSON for the SPA

The wrapper is interactive: it asks at each stage whether to run that stage
and confirms parameters before doing work. Each stage can also be invoked
non-interactively via flags so this same script can be wired into CI or a
scheduled task later.

Usage (interactive):
    python ohio_voter_pipeline_wrapper.py

Usage (scripted; skip prompts and run a specific stage):
    python ohio_voter_pipeline_wrapper.py --stage export --county 57 --county-name montgomery
    python ohio_voter_pipeline_wrapper.py --stage score --counties montgomery --workers 4
    python ohio_voter_pipeline_wrapper.py --stage deliver --format excel
    python ohio_voter_pipeline_wrapper.py --stage all     # run every stage with prompts

The wrapper does not duplicate logic from the underlying scripts; it shells
out to them with the appropriate arguments and environment.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import polars as pl

# --- CONFIG --------------------------------------------------------------
PROJECT_ROOT = Path(r"D:\vibe\election-data (1)")
EXPORT_SCRIPT = PROJECT_ROOT / "export_unc_targets.py"
PREDICTOR = PROJECT_ROOT / "mixed_lean_predictor.py"
RUNNER = PROJECT_ROOT / "run_lean_predictor_all_cohorts.py"

SOURCE_DIR = PROJECT_ROOT / "source"
EXPORT_ROOT = PROJECT_ROOT / "UNC_Exports"
STATEWIDE_DIR = EXPORT_ROOT / "_Statewide"
DELIVERABLE_DIR = PROJECT_ROOT / "Deliverables"

DEFAULT_SWVF_FILES = [
    SOURCE_DIR / "SWVF_1_22.txt",
    SOURCE_DIR / "SWVF_23_44.txt",
    SOURCE_DIR / "SWVF_45_66.txt",
    SOURCE_DIR / "SWVF_67_88.txt",
]

# Map county number -> slug for the export step.
# Extend as needed; the wrapper falls back to the county number if missing.
COUNTY_NAME_BY_NUMBER: dict[str, str] = {
    "57": "montgomery",
    # Add more here as you process them. e.g. '25': 'franklin', '18': 'cuyahoga'
}


# --- PROMPT HELPERS ------------------------------------------------------
def confirm(question: str, default: bool = True) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        ans = input(question + suffix).strip().lower()
        if not ans:
            return default
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False


def ask(question: str, default: str = "") -> str:
    suffix = f" [{default}] " if default else " "
    ans = input(question + suffix).strip()
    return ans or default


# --- STAGE 1: EXPORT -----------------------------------------------------
def stage_export(args: argparse.Namespace, interactive: bool) -> int:
    """Run export_unc_targets.py for one or more counties."""
    if not EXPORT_SCRIPT.exists():
        print(f"[abort] export script not found: {EXPORT_SCRIPT}")
        return 1

    counties: list[tuple[str, str]] = []  # [(number, slug)]
    if args.county and args.county_name:
        counties.append((args.county.strip().zfill(2), args.county_name.strip().lower()))
    elif interactive:
        print("\n=== STAGE 1: UNC + Current D/R Export ===")
        if not confirm("Export UNC and Current D/R cohort CSVs from raw SWVF files?"):
            return 0
        nums = ask("Enter county number(s), comma-separated (e.g. 57,25,18)").strip()
        if not nums:
            print("[skip] no counties given")
            return 0
        for n in [x.strip() for x in nums.split(",") if x.strip()]:
            n_padded = n.zfill(2)
            slug_default = COUNTY_NAME_BY_NUMBER.get(n_padded, n_padded)
            slug = ask(f"  slug for county {n_padded}", default=slug_default).lower()
            counties.append((n_padded, slug))
    else:
        print("[abort] export stage requires --county and --county-name in non-interactive mode")
        return 1

    swvf_files = [p for p in DEFAULT_SWVF_FILES if p.exists()]
    if not swvf_files:
        print(f"[abort] no SWVF_*.txt files found under {SOURCE_DIR}")
        return 1

    rc_total = 0
    for number, slug in counties:
        cmd = [sys.executable, str(EXPORT_SCRIPT),
               "--county", number,
               "--county-name", slug]
        for p in swvf_files:
            cmd += ["--input", str(p)]
        print(f"\n[exec] {' '.join(cmd)}")
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"[fail] export for county {number} returned {rc}")
            rc_total |= 1
    return rc_total


# --- STAGE 2: SCORE ------------------------------------------------------
def stage_score(args: argparse.Namespace, interactive: bool) -> int:
    if not RUNNER.exists() or not PREDICTOR.exists():
        print(f"[abort] runner or predictor missing: {RUNNER}, {PREDICTOR}")
        return 1

    if interactive:
        print("\n=== STAGE 2: Per-voter Lean Scoring ===")
        if not confirm("Run lean scoring across cohorts?"):
            return 0
        cohorts = ask("Cohorts (comma-separated, blank = all)",
                      default=args.cohorts or "").strip()
        counties = ask("Counties (comma-separated, blank = all discovered)",
                       default=args.counties or "").strip()
        workers = ask("Worker processes", default=str(args.workers or 4))
        skip_existing = confirm("Skip already-scored files?", default=True)
    else:
        cohorts = (args.cohorts or "").strip()
        counties = (args.counties or "").strip()
        workers = str(args.workers or 1)
        skip_existing = bool(args.skip_existing)

    cmd = [sys.executable, str(RUNNER), "--workers", str(workers)]
    if cohorts:
        cmd += ["--cohorts", cohorts]
    if counties:
        cmd += ["--counties", counties]
    if skip_existing:
        cmd.append("--skip-existing")
    print(f"\n[exec] {' '.join(cmd)}")
    return subprocess.call(cmd)


# --- STAGE 3: DELIVER ----------------------------------------------------
def stage_deliver(args: argparse.Namespace, interactive: bool) -> int:
    """Build stakeholder deliverables from the scored outputs."""
    if interactive:
        print("\n=== STAGE 3: Deliverables ===")
        if not confirm("Build stakeholder deliverables now?"):
            return 0
        fmt = ask("Format: excel / web / both", default=args.format or "excel").lower()
    else:
        fmt = (args.format or "excel").lower()
    if fmt not in {"excel", "web", "both"}:
        print(f"[abort] unknown format: {fmt}")
        return 1

    DELIVERABLE_DIR.mkdir(parents=True, exist_ok=True)

    statewide_summary = STATEWIDE_DIR / "_statewide_summary.csv"
    statewide_by_county = STATEWIDE_DIR / "_statewide_summary_by_county.csv"
    if not statewide_summary.exists() or not statewide_by_county.exists():
        print(f"[abort] statewide summaries missing under {STATEWIDE_DIR}. "
              f"Run stage 2 first.")
        return 1

    rc = 0
    if fmt in {"excel", "both"}:
        rc |= _build_excel(statewide_summary, statewide_by_county)
    if fmt in {"web", "both"}:
        rc |= _build_web(statewide_summary, statewide_by_county)
    return rc


def _build_excel(statewide_summary: Path, statewide_by_county: Path) -> int:
    out_path = DELIVERABLE_DIR / "ohio_voter_lean_summary.xlsx"
    print(f"[deliver] building Excel rollup -> {out_path}")
    try:
        # Try xlsxwriter first (per CLAUDE.md preference); fall back to openpyxl.
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except ImportError:
            engine = "openpyxl"

        summary_df = pl.read_csv(statewide_summary).to_pandas()
        by_county_df = pl.read_csv(statewide_by_county).to_pandas()
        import pandas as pd
        with pd.ExcelWriter(out_path, engine=engine) as writer:
            summary_df.to_excel(writer, sheet_name="Statewide_Summary", index=False)
            by_county_df.to_excel(writer, sheet_name="By_County", index=False)
            if engine == "xlsxwriter":
                wb = writer.book
                bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD"})
                for sheet_name, df in [("Statewide_Summary", summary_df),
                                        ("By_County", by_county_df)]:
                    ws = writer.sheets[sheet_name]
                    ws.freeze_panes(1, 0)
                    ws.set_row(0, None, bold)
                    for i, col in enumerate(df.columns):
                        width = max(12, min(40, int(df[col].astype(str).str.len().max() or 12) + 2))
                        ws.set_column(i, i, width)
                    ws.autofilter(0, 0, len(df), len(df.columns) - 1)
        print(f"[ok] {out_path}")
        return 0
    except Exception as e:
        print(f"[fail] excel build: {e}")
        return 1


def _build_web(statewide_summary: Path, statewide_by_county: Path) -> int:
    """Emit JSON the SPA can lazy-load."""
    import json
    web_dir = DELIVERABLE_DIR / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    try:
        summary = pl.read_csv(statewide_summary).to_dicts()
        by_county = pl.read_csv(statewide_by_county).to_dicts()
        (web_dir / "statewide_summary.json").write_text(json.dumps(summary, indent=2))
        (web_dir / "statewide_summary_by_county.json").write_text(json.dumps(by_county, indent=2))
        print(f"[ok] {web_dir / 'statewide_summary.json'}")
        print(f"[ok] {web_dir / 'statewide_summary_by_county.json'}")
        return 0
    except Exception as e:
        print(f"[fail] web build: {e}")
        return 1


# --- ENTRYPOINT ----------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["export", "score", "deliver", "all"], default=None,
                    help="run a specific stage non-interactively (default: interactive menu)")

    # export-stage flags
    ap.add_argument("--county")
    ap.add_argument("--county-name")

    # score-stage flags
    ap.add_argument("--cohorts", default="")
    ap.add_argument("--counties", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-existing", action="store_true")

    # deliver-stage flags
    ap.add_argument("--format", choices=["excel", "web", "both"], default=None)

    args = ap.parse_args()
    interactive = args.stage in (None, "all")

    if args.stage == "export":
        return stage_export(args, interactive=False)
    if args.stage == "score":
        return stage_score(args, interactive=False)
    if args.stage == "deliver":
        return stage_deliver(args, interactive=False)

    # Interactive / "all" path
    print("=" * 64)
    print("Ohio Voter Registration Pipeline -- Master Wrapper")
    print("=" * 64)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Export root  : {EXPORT_ROOT}")
    print(f"Deliverables : {DELIVERABLE_DIR}")

    rc = 0
    rc |= stage_export(args, interactive=True)
    rc |= stage_score(args, interactive=True)
    rc |= stage_deliver(args, interactive=True)
    print("\n[done] wrapper finished.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
