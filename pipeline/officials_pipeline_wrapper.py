"""
officials_pipeline_wrapper.py
=============================
Master wrapper for the officials / captains / candidates pipeline (Stages 1-8).

The pipeline is a fan-in: three independent producer chains feed one shared
consumer, then a validator:

    Officials  : Stage 1            -> serve/officials.json
    Captains   : Stage 2,3 -> 5     -> serve/precinct_captains.json
    Candidates : Stage 4   -> 6     -> serve/candidates.json
    Convergence: Stage 7 (match)    -> serve/partisan_profiles.json
    Quality    : Stage 8 (validate + schema drift gate)

Like ohio_voter_pipeline_wrapper.py, this wrapper does NOT duplicate any logic --
it shells out to the underlying scripts with the right arguments. It is interactive
by default and can run a single stage non-interactively via --stage for CI.

Usage (interactive menu):
    python pipeline/officials_pipeline_wrapper.py

Usage (scripted, one stage):
    python pipeline/officials_pipeline_wrapper.py --stage ingest
    python pipeline/officials_pipeline_wrapper.py --stage captains   --county montgomery
    python pipeline/officials_pipeline_wrapper.py --stage candidates --county montgomery
    python pipeline/officials_pipeline_wrapper.py --stage match      --county montgomery
    python pipeline/officials_pipeline_wrapper.py --stage validate   --county montgomery
    python pipeline/officials_pipeline_wrapper.py --stage all        --county montgomery
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import json
import csv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADMIN = PROJECT_ROOT / "tools" / "admin"
PRECINCT_KEYS_DIR = PROJECT_ROOT / "local" / "source" / "precinct_keys"

sys.path.append(str(ADMIN))
from officials_common import COUNTY_NUMBER

# --- SETUP HELPER --------------------------------------------------------
def setup_county_manifest(county: str, force_remap: bool = False):
    county_code = COUNTY_NUMBER.get(county)
    if not county_code:
        print(f"[abort] Unknown county slug {county!r}")
        sys.exit(1)
        
    county_dir = PROJECT_ROOT / "local" / "source" / "County Data Files" / f"{county_code}_{county.capitalize()}"
    county_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_path = county_dir / "manifest.json"
    
    if force_remap and manifest_path.exists():
        manifest_path.unlink()
        print(f"\n[info] Deleted existing manifest.json for {county.capitalize()}. Starting fresh.")
        
    if manifest_path.exists():
        print(f"\n[info] Found existing manifest.json for {county.capitalize()} County.")
        print(f"       Using previously saved mappings. (To remap from scratch, run with --remap)")
        return
        
    print(f"\n=== Setting up {county.capitalize()} County ===")
    print(f"I didn't find a manifest.json in {county_dir.name}.")
    
    valid_files = [f for f in county_dir.glob("*.*") if f.suffix.lower() in [".pdf", ".csv", ".xlsx"]]
    if not valid_files:
        print(f"[abort] No PDF, CSV, or XLSX files found in {county_dir.relative_to(PROJECT_ROOT)}.")
        print("Please place the raw Board of Elections files there first!")
        sys.exit(1)
        
    print(f"I found {len(valid_files)} files in the folder:")
    for i, f in enumerate(valid_files, 1):
        print(f"  [{i}] {f.name}")
        
    manifest = {}
    
    import re
    def get_file_guess(keywords: list[str]) -> str | None:
        pattern = re.compile(r"\b(" + "|".join(keywords) + r")\b", re.IGNORECASE)
        for f in valid_files:
            if pattern.search(f.name):
                return f.name
        return None
        
    auto_files = {
        "candidate_petitions": get_file_guess(["cand", "petition"]),
        "central_committee_D": get_file_guess(["dem", "democrat"]),
        "central_committee_R": get_file_guess(["rep", "republican", "gop"]),
        "central_committee_L": get_file_guess(["lib", "libertarian"]),
    }
    
    print("\nI can auto-map these files for you:")
    print(f"  Candidate Petitions: {auto_files['candidate_petitions'] or '(Not Found)'}")
    print(f"          Democrat CC: {auto_files['central_committee_D'] or '(Not Found)'}")
    print(f"        Republican CC: {auto_files['central_committee_R'] or '(Not Found)'}")
    print(f"       Libertarian CC: {auto_files['central_committee_L'] or '(Not Found)'}")
    
    if confirm("\nDoes this file mapping look correct?", default=True):
        manifest.update(auto_files)
    else:
        print("\nOkay, let's map them manually.")
        def prompt_file(prompt_text: str) -> str | None:
            while True:
                ans = input(f"\n{prompt_text} (Type 1-{len(valid_files)}, or type 0 to skip):\n> ").strip()
                if not ans.isdigit():
                    continue
                idx = int(ans)
                if idx == 0:
                    return None
                if 1 <= idx <= len(valid_files):
                    return valid_files[idx-1].name
                    
        manifest["candidate_petitions"] = prompt_file("Which file has the General Candidate Petitions?")
        manifest["central_committee_D"] = prompt_file("Which file has the Democrat Central Committee report?")
        manifest["central_committee_R"] = prompt_file("Which file has the Republican Central Committee report?")
        manifest["central_committee_L"] = prompt_file("Which file has the Libertarian Central Committee report?")
    
    manifest["csv_mappings"] = {}
    for key, filename in list(manifest.items()):
        if key == "csv_mappings" or not filename:
            continue
            
        ext = filename.lower().split(".")[-1]
        if ext in ["csv", "xlsx"]:
            print(f"\nI see you picked a {ext.upper()} file for {key}: {filename}")
            print("Let's match the columns.")
            
            headers = []
            tab_name = None
            filepath = county_dir / filename
            if ext == "csv":
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    headers = next(csv.reader(f), [])
            elif ext == "xlsx":
                import openpyxl
                wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
                
                sheet_names = wb.sheetnames
                if len(sheet_names) > 1:
                    print("\nThis Excel file has multiple tabs:")
                    for i, sn in enumerate(sheet_names, 1):
                        print(f"  [{i}] {sn}")
                    while True:
                        ans = input(f"Which tab contains the data? (Type 1-{len(sheet_names)}, or 0 to use active sheet):\n> ").strip()
                        if not ans or not ans.isdigit():
                            continue
                        idx = int(ans)
                        if idx == 0:
                            ws = wb.active
                            break
                        if 1 <= idx <= len(sheet_names):
                            tab_name = sheet_names[idx-1]
                            ws = wb[tab_name]
                            break
                else:
                    ws = wb.active
                    
                ws_rows = list(ws.rows)
                if ws_rows:
                    headers = [str(cell.value) if cell.value is not None else f"Col_{i}" for i, cell in enumerate(ws_rows[0], 1)]
                wb.close()
                
            if not headers:
                print("Warning: File appears to be empty or has no headers.")
                continue
                
            print("Here are the columns in your file:")
            for i, h in enumerate(headers, 1):
                print(f"  [{i}] {h}")
                
            def get_guess(keywords: list[str]) -> int | None:
                pattern = re.compile(r"\b(" + "|".join(keywords) + r")\b", re.IGNORECASE)
                for i, h in enumerate(headers, 1):
                    if pattern.search(str(h)):
                        return i
                return None
                
            def prompt_col(prompt_text: str, guess_idx: int = None) -> str | None:
                guess_str = f" [Press Enter to accept: {guess_idx}]" if guess_idx else ""
                while True:
                    ans = input(f"\n{prompt_text} (Type 1-{len(headers)}, or 0 to skip){guess_str}:\n> ").strip()
                    if not ans and guess_idx:
                        return headers[guess_idx-1]
                    if not ans or not ans.isdigit():
                        continue
                    idx = int(ans)
                    if idx == 0:
                        return None
                    if 1 <= idx <= len(headers):
                        return headers[idx-1]
                        
            # Try to auto-map everything first
            auto_map = {}
            if key == "candidate_petitions":
                auto_map = {
                    "name": get_guess(["name", "cand"]),
                    "office": get_guess(["office", "position"]),
                    "party": get_guess(["party"]),
                    "term": get_guess(["term", "date"]),
                    "status": get_guess(["status", "cert"]),
                }
            else:
                auto_map = {
                    "name": get_guess(["name", "cand"]),
                    "party": get_guess(["party"]),
                    "precinct": get_guess(["precinct", "pct", "ward"]),
                }
                
            print("\nI can auto-map these columns for you:")
            for field, idx in auto_map.items():
                if idx is None and key.startswith("central_committee_") and field == "party":
                    val = "(Derived from file type)"
                else:
                    val = headers[idx-1] if idx else "(Skipped/Not Found)"
                print(f"  {field.capitalize():>10}: {val}")
                
            if confirm("\nDoes this mapping look correct?", default=True):
                mapping = {"tab_name": tab_name}
                mapping.update({k: (headers[v-1] if v else None) for k, v in auto_map.items()})
                manifest["csv_mappings"][key] = mapping
            else:
                print("\nOkay, let's map them manually.")
                if key == "candidate_petitions":
                    manifest["csv_mappings"][key] = {
                        "tab_name": tab_name,
                        "name": prompt_col("Which column has the Candidate's Name?", auto_map["name"]),
                        "office": prompt_col("Which column has the Office?", auto_map["office"]),
                        "party": prompt_col("Which column has the Party?", auto_map["party"]),
                        "term": prompt_col("Which column has the Term?", auto_map["term"]),
                        "status": prompt_col("Which column has the Status?", auto_map["status"]),
                    }
                else:
                    manifest["csv_mappings"][key] = {
                        "tab_name": tab_name,
                        "name": prompt_col("Which column has the Candidate's Name?", auto_map["name"]),
                        "party": prompt_col("Which column has the Party? (Type 0 if the file only contains this specific party)", auto_map["party"]),
                        "precinct": prompt_col("Which column has the Precinct?", auto_map["precinct"]),
                    }
            
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[done] Saved your choices to {manifest_path.relative_to(PROJECT_ROOT)}.\n")

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
    return input(question + suffix).strip() or default


def run_script(script: str, *args: str) -> int:
    """Shell out to a pipeline script; return its exit code."""
    path = ADMIN / script
    if not path.exists():
        print(f"[abort] script not found: {path}")
        return 1
    cmd = [sys.executable, str(path), *args]
    print(f"\n[exec] {' '.join(cmd)}")
    return subprocess.call(cmd)


# --- STAGE 1: OFFICIALS --------------------------------------------------
def stage_ingest(county: str, interactive: bool) -> int:
    if interactive:
        print("\n=== STAGE 1: Ingest elected officials ===")
        if not confirm("Populate serve/officials.json jurisdiction sections from the SOS CSV?"):
            return 0
    return run_script("ingest_elected_officials.py", "--write")


# --- STAGES 2,3,5: CAPTAINS ----------------------------------------------
def stage_captains(county: str, interactive: bool) -> int:
    if interactive:
        print("\n=== STAGES 2/3/5: Precinct captains ===")
        if not confirm("Build serve/precinct_captains.json?"):
            return 0

    # Stage 2 -- precinct key CSV. precinct_key_manager.py is an interactive menu and
    # cannot be driven here; the CSV is a one-time artifact, so we require it to exist.
    key_csv = PRECINCT_KEYS_DIR / f"{county}_precincts.csv"
    if not key_csv.exists():
        print(f"[abort] precinct key file missing: {key_csv}")
        print("        Run it once interactively:  "
              f"python {ADMIN / 'precinct_key_manager.py'}")
        return 1
    print(f"[skip] Stage 2: precinct keys present ({key_csv.name})")

    rc = run_script("parse_central_committee.py", "--county", county, "--all-parties")
    if rc != 0:
        return rc
    return run_script("build_precinct_captains.py", "--county", county)


# --- STAGES 4,6: CANDIDATES ----------------------------------------------
def stage_candidates(county: str, interactive: bool) -> int:
    if interactive:
        print("\n=== STAGES 4/6: General-election candidates ===")
        if not confirm("Build serve/candidates.json?"):
            return 0

    rc = run_script("pdf_to_markdown.py", "--all")  # petition PDF -> markdown (Stage 4 prereq)
    if rc != 0:
        return rc
    rc = run_script("parse_candidate_petitions.py", "--county", county)
    if rc != 0:
        return rc
    return run_script("build_candidates.py", "--county", county)


# --- STAGE 7: MATCH ------------------------------------------------------
def stage_match(county: str, interactive: bool) -> int:
    if interactive:
        print("\n=== STAGE 7: Cross-reference filers to the voter file ===")
        if not confirm("Build serve/partisan_profiles.json?"):
            return 0
    return run_script("match_to_voters.py", "--county", county)


# --- STAGE 8: VALIDATE ---------------------------------------------------
def stage_validate(county: str, interactive: bool) -> int:
    if interactive:
        print("\n=== STAGE 8: Validate + refresh schema inventory ===")
        if not confirm("Refresh schema inventory and run the validator?"):
            return 0
    rc = run_script("dump_schema.py")  # refresh generated inventory blocks first
    if rc != 0:
        return rc
    return run_script("validate_officials.py", "--county", county)


STAGES = {
    "ingest": stage_ingest,
    "captains": stage_captains,
    "candidates": stage_candidates,
    "match": stage_match,
    "validate": stage_validate,
}
ORDER = ["ingest", "captains", "candidates", "match", "validate"]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=[*ORDER, "all"], default=None,
                    help="run one stage non-interactively (default: interactive menu)")
    ap.add_argument("--county", default="montgomery", help="county slug (default montgomery)")
    ap.add_argument("--remap", action="store_true", help="delete the existing manifest.json and start mapping from scratch")
    args = ap.parse_args()
    
    if args.stage and args.stage != "all":
        # 0. Ensure county is mapped before running a specific stage
        setup_county_manifest(args.county, force_remap=args.remap)
        return STAGES[args.stage](args.county, interactive=False)

    print("================================================================")
    print("Officials / Captains / Candidates Pipeline -- Master Wrapper")
    print("================================================================")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"County       : {args.county}")
    
    # 0. Ensure county is mapped
    setup_county_manifest(args.county, force_remap=args.remap)

    rc = 0
    for name in ORDER:
        rc |= STAGES[name](args.county, interactive=True)
    print("\n[done] wrapper finished.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
