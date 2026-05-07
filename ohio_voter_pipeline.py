"""
ohio_voter_pipeline.py
─────────────────────
1. Optionally checks the Ohio SOS voter file page for updated file dates
2. Downloads any new/updated .gz archives (if scrape succeeded)
3. Decompresses them into source/State Voter Files/
4. Prompts for the next analysis step

Usage:  python ohio_voter_pipeline.py

Note: The Parquet cache is a hard requirement for single-county and
multi-county runs.  On first use, run option [1] or [2] to build it from
the raw SWVF txt files (one-time, ~4 min).  All subsequent runs load from
the cache in under 60 s.
"""

import os
import gzip
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
SOURCE_DIR = BASE_DIR / "source"
TXT_DIR    = SOURCE_DIR / "State Voter Files"
MANIFEST   = BASE_DIR / "download_manifest.json"

SOS_URL    = "https://www6.ohiosos.gov/ords/f?p=VOTERFTP:STWD"
SOS_BASE   = "https://www6.ohiosos.gov"

SWVF_NAMES = [
    "SWVF_1_22.txt.gz",
    "SWVF_23_44.txt.gz",
    "SWVF_45_66.txt.gz",
    "SWVF_67_88.txt.gz",
]

REQ_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ohio-voter-pipeline/1.0)"}
TIMEOUT     = 60


# ── Manifest ──────────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_manifest(data: dict):
    MANIFEST.write_text(json.dumps(data, indent=2, default=str))


# ── Scraping ──────────────────────────────────────────────────────────────────

def scrape_download_links() -> dict[str, str]:
    """
    Fetch the SOS voter file page and return {filename: url} for the 4 SWVF gz files.
    Falls back to constructing URLs from any href containing 'SWVF'.
    """
    print(f"Fetching {SOS_URL} ...")
    try:
        resp = requests.get(SOS_URL, headers=REQ_HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Could not reach SOS page: {e}")

    soup  = BeautifulSoup(resp.text, "html.parser")
    links = {}

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        for name in SWVF_NAMES:
            stem = name.removesuffix(".gz")
            if name in href or stem in href:
                url = href if href.startswith("http") else SOS_BASE + href
                links[name] = url
                break
        else:
            if "SWVF" in href.upper():
                url  = href if href.startswith("http") else SOS_BASE + href
                name = Path(href.split("?")[0]).name
                if not name.endswith(".gz"):
                    name += ".gz"
                if name not in links:
                    links[name] = url

    return links


def head_last_modified(url: str) -> str:
    """Return Last-Modified header value, or 'unknown'."""
    try:
        r = requests.head(url, headers=REQ_HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return r.headers.get("Last-Modified", "unknown")
    except Exception:
        return "unknown"


# ── Download & decompress ─────────────────────────────────────────────────────

def download_file(url: str, dest: Path):
    """Stream download with a simple progress counter."""
    with requests.get(url, headers=REQ_HEADERS, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        total    = int(r.headers.get("content-length", 0))
        received = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                f.write(chunk)
                received += len(chunk)
                if total:
                    pct = received / total * 100
                    print(f"\r  ↓ {dest.name}  {pct:.0f}%  ({received/1e6:.0f}/{total/1e6:.0f} MB)",
                          end="", flush=True)
    print(f"\r  ✓ {dest.name}  ({received/1e6:.0f} MB)                    ")


def decompress_gz(gz_path: Path, out_dir: Path) -> Path:
    """Decompress gz_path into out_dir; return path to decompressed file."""
    out_path = out_dir / gz_path.name.removesuffix(".gz")
    print(f"  Decompressing → {out_path.name} ...", end="", flush=True)
    with gzip.open(gz_path, "rb") as f_in, open(out_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out, length=8 * 1024 * 1024)
    size = out_path.stat().st_size
    print(f"\r  ✓ {out_path.name}  ({size/1e9:.2f} GB)              ")
    return out_path


# ── County lookup helpers ─────────────────────────────────────────────────────

def _get_ohio_counties() -> dict[str, str]:
    """Return the OHIO_COUNTIES dict from voter_data_cleaner_v2 without a full import."""
    import voter_data_cleaner_v2 as v2
    return v2.OHIO_COUNTIES   # dict[str, str]  e.g. {'01': 'Adams', ...}


def print_county_list():
    """Print all 88 Ohio counties with their official state numbers, 3-up."""
    counties = _get_ohio_counties()
    items    = sorted(counties.items(), key=lambda kv: int(kv[0]))
    cols     = 3
    col_w    = 22
    print()
    print("  Ohio counties — official SOS numbering (alphabetical, 01–88)")
    print("  " + "─" * (cols * col_w))
    for i in range(0, len(items), cols):
        row = items[i:i + cols]
        line = "  ".join(f"  {num}  {name:<{col_w - 6}}" for num, name in row)
        print(line)
    print()


def resolve_counties(raw: str) -> list[str] | None:
    """
    Parse a comma-separated string of county numbers and/or names.
    Returns a sorted list of zero-padded two-digit county number strings,
    or None if the input contained unresolvable tokens (after prompting user).

    Supports:
      - Numbers:      "57"  "057"  "57, 29"
      - Exact names:  "Montgomery"  "montgomery"
      - Partials:     "mont" → Montgomery (prompts if ambiguous)
      - Mixed:        "57, Greene, 29"
    """
    counties   = _get_ohio_counties()
    name_to_num = {v.lower(): k for k, v in counties.items()}
    resolved   = []

    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue

        # ── Numeric input ──────────────────────────────────────────────────
        if token.isdigit():
            num = token.zfill(2)
            if num in counties:
                resolved.append(num)
            else:
                print(f"  ✗ No county with number {token}. Use [L] to list all counties.")
                return None
            continue

        # ── Exact name match (case-insensitive) ────────────────────────────
        lower = token.lower()
        if lower in name_to_num:
            resolved.append(name_to_num[lower])
            continue

        # ── Partial name match ─────────────────────────────────────────────
        matches = [(num, name) for num, name in counties.items()
                   if lower in name.lower()]

        if len(matches) == 1:
            resolved.append(matches[0][0])
            print(f"  → Resolved '{token}' to {matches[0][1]} ({matches[0][0]})")
            continue

        if len(matches) == 0:
            print(f"  ✗ No county matching '{token}'. Use [L] to list all counties.")
            return None

        # Ambiguous — ask the user to pick
        print(f"\n  '{token}' matches {len(matches)} counties:")
        for i, (num, name) in enumerate(matches, 1):
            print(f"    [{i}]  {num}  {name}")
        pick = input(f"  Enter number (1–{len(matches)}): ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(matches):
            resolved.append(matches[int(pick) - 1][0])
        else:
            print("  ✗ Invalid selection. Please re-enter county.")
            return None

    return sorted(set(resolved)) if resolved else None


# ── Prompts ───────────────────────────────────────────────────────────────────

def prompt_check_for_updates() -> bool:
    """Ask whether to attempt scraping the SOS page for new voter files."""
    print()
    print("  Check Ohio SOS website for updated voter files?")
    print("  Note: the SOS site blocks automated requests with 403/CAPTCHA.")
    print("  [Y]  Yes — attempt scrape (may fail silently)")
    print("  [N]  No  — skip to analysis with files already on disk  (default; press Enter)")
    print()
    ans = input("  Check for updates? (Y/N) [N]: ").strip().upper()
    return ans == "Y"


def prompt_precinct_charts() -> bool:
    """Ask whether to also generate per-precinct chart JSON files."""
    print()
    print("  Per-precinct chart JSON (party doughnut + UNC shadow per precinct):")
    print("  [Y]  Yes — build precinct-level charts for selected counties")
    print("  [N]  No  — county-level charts only  (default; press Enter)")
    print()
    ans = input("  Include precinct charts? (Y/N) [N]: ").strip().upper()
    return ans == "Y"


def prompt_county_selection() -> list[str] | None:
    """
    Prompt the user to enter one or more counties by number or name.
    Returns a list of resolved zero-padded county number strings, or None to cancel.
    Loops until valid input is provided or the user cancels.
    """
    print()
    print("  Enter county number(s) or name(s), comma-separated.")
    print("  Examples:  57              → Montgomery only")
    print("             57, 29          → Montgomery and Greene")
    print("             Montgomery      → same as 57")
    print("             mont            → resolves to Montgomery (clarifies if ambiguous)")
    print("             57, Greene, 31  → mix of numbers and names")
    print("  [L] to list all 88 counties   [0] to cancel")
    print()

    while True:
        raw = input("  County: ").strip()
        if not raw:
            continue
        if raw.upper() == "L":
            print_county_list()
            continue
        if raw == "0":
            return None

        result = resolve_counties(raw)
        if result:
            counties = _get_ohio_counties()
            names    = [counties.get(n, n) for n in result]
            print(f"\n  Selected: {', '.join(f'{n} ({num})' for n, num in zip(names, result))}")
            confirm = input("  Proceed? (Y/N) [Y]: ").strip().upper()
            if confirm in ("", "Y"):
                return result
            # User said no — loop back
        # resolve_counties already printed the error; loop back


def prompt_next_step(txt_files: list[Path]) -> tuple[str, bool, list[str] | None]:
    """
    Returns (choice, include_precincts, county_numbers).
    county_numbers is None for full-Ohio runs, a list of strings for targeted runs.
    """
    total_rows_est = sum(f.stat().st_size for f in txt_files) // 140
    parquet_dir    = BASE_DIR / "source" / "parquet"
    parquet_ready  = parquet_dir.exists() and any(parquet_dir.iterdir())
    cache_label    = "  ✓ Parquet cache ready (fast load)" if parquet_ready else "  ○ No Parquet cache yet (will build on first run)"

    print(f"\n{'='*60}")
    print(f"  {len(txt_files)} voter file(s) ready  (~{total_rows_est:,.0f} records estimated)")
    for f in txt_files:
        print(f"    {f.name}  {f.stat().st_size/1e9:.2f} GB")
    print(f"  {cache_label}")
    print("="*60)
    print()
    print("  Next step:")
    print("  [1]  Full Ohio (88 counties) → web dashboard JSON only  (default; press Enter)")
    print("  [2]  Full Ohio (88 counties) → web dashboard JSON + Excel workbook")
    print("  [3]  Selected counties only  → web dashboard JSON")
    print("  [L]  List all 88 counties with official state numbers")
    print("  [0]  Exit")
    print()

    while True:
        choice = input("  Choice (1/2/3/L/0) [1]: ").strip().upper() or "1"

        if choice == "L":
            print_county_list()
            continue

        if choice == "0":
            return "0", False, None

        if choice in ("1", "2"):
            include_precincts = prompt_precinct_charts()
            return choice, include_precincts, None

        if choice == "3":
            county_nums = prompt_county_selection()
            if county_nums is None:
                # User cancelled — re-show main menu
                continue
            include_precincts = prompt_precinct_charts()
            return "3", include_precincts, county_nums

        print("  Invalid choice. Enter 1, 2, 3, L, or 0.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  OHIO VOTER FILE PIPELINE")
    print("=" * 60)

    manifest = load_manifest()

    # 1 ── optionally scrape the SOS page for updated file links
    links = {}
    if prompt_check_for_updates():
        try:
            links = scrape_download_links()
            if not links:
                print("  ⚠  No SWVF download links found (page layout may have changed).")
                print(f"     Check manually: {SOS_URL}")
            else:
                print(f"  Found {len(links)} download link(s).\n")
        except RuntimeError as e:
            print(f"  ⚠  Could not reach SOS page: {e}")
            print("     Skipping download check — will use files already on disk.\n")
    else:
        print("  Skipping SOS scrape — using files already on disk.\n")

    # 2 ── compare remote Last-Modified against manifest
    to_download: dict[str, tuple[str, str]] = {}
    for name, url in links.items():
        remote_dt = head_last_modified(url)
        cached_dt = manifest.get(name, {}).get("last_modified")
        if remote_dt == "unknown" or remote_dt != cached_dt:
            label = "NEW" if not cached_dt else f"updated  {cached_dt} → {remote_dt}"
            print(f"  {name}:  {label}")
            to_download[name] = (url, remote_dt)
        else:
            print(f"  {name}:  current  ({remote_dt})")

    # 3 ── if nothing to download (or scrape skipped), jump straight to prompt
    txt_files = sorted(TXT_DIR.glob("SWVF_*.txt")) if TXT_DIR.exists() else []
    if not to_download:
        if txt_files:
            print("✓ Using files already on disk — no download needed.")
            choice, include_precincts, county_nums = prompt_next_step(txt_files)
            _dispatch(choice, txt_files, include_precincts, county_nums)
        else:
            print("\n✗ No SWVF_*.txt files found and download unavailable.")
            print(f"  Place files manually in: {TXT_DIR}")
            sys.exit(1)
        return

    # 4 ── create dirs
    today_str = date.today().strftime("%Y-%m-%d")
    gz_dir    = SOURCE_DIR / f"{today_str} gz"
    gz_dir.mkdir(parents=True, exist_ok=True)
    TXT_DIR.mkdir(parents=True, exist_ok=True)

    # 5 ── download + decompress
    print(f"\nDownloading to {gz_dir}\n")
    newly_txt = []
    for name, (url, remote_dt) in to_download.items():
        gz_path = gz_dir / name
        try:
            download_file(url, gz_path)
        except Exception as e:
            print(f"\n  ✗ Download failed for {name}: {e}")
            continue

        try:
            txt_path = decompress_gz(gz_path, TXT_DIR)
            newly_txt.append(txt_path)
        except Exception as e:
            print(f"\n  ✗ Decompression failed for {name}: {e}")
            continue

        manifest.setdefault(name, {}).update({
            "last_modified": remote_dt,
            "downloaded":    datetime.now().isoformat(),
            "gz_path":       str(gz_path),
            "txt_path":      str(txt_path),
        })

    manifest["last_run"] = datetime.now().isoformat()
    save_manifest(manifest)
    print(f"\n✓ Manifest saved → {MANIFEST}")

    # 6 ── prompt
    txt_files = sorted(TXT_DIR.glob("SWVF_*.txt"))
    if txt_files:
        choice, include_precincts, county_nums = prompt_next_step(txt_files)
        _dispatch(choice, txt_files, include_precincts, county_nums)


def _dispatch(
    choice:            str,
    txt_files:         list[Path],
    include_precincts: bool            = False,
    county_nums:       list[str] | None = None,
):
    import voter_data_cleaner_v2 as v2

    _log     = v2.setup_logging('pipeline')
    src_date = v2.get_source_date(_log)

    if choice == "1":
        v2.run_ohio_analysis(txt_files, use_parquet=True,
                             include_precinct_charts=include_precincts)

    elif choice == "2":
        v2.run_ohio_analysis(txt_files, use_parquet=True,
                             include_precinct_charts=include_precincts)
        out = BASE_DIR / f"ohio_analysis_src{src_date}.xlsx"
        v2.run_ohio_excel(txt_files, output_path=out, use_parquet=True)

    elif choice == "3" and county_nums:
        v2.run_county_subset(
            txt_files,
            county_numbers=county_nums,
            use_parquet=True,
            include_precinct_charts=include_precincts,
        )

    else:
        print("\nExiting. Voter files are in:")
        for f in txt_files:
            print(f"  {f}")


if __name__ == "__main__":
    main()
