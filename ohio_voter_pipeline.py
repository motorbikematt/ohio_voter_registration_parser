"""
ohio_voter_pipeline.py
─────────────────────
1. Scrapes the Ohio SOS voter file page for updated file dates
2. Downloads any new/updated .gz archives
3. Decompresses them into source/State Voter Files/
4. Prompts for the next analysis step

Usage:  python ohio_voter_pipeline.py
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

# Derive BASE_DIR from the location of this script so the repo works
# regardless of where it is cloned or what OS it runs on.
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
            stem = name.removesuffix(".gz")           # e.g. SWVF_1_22.txt
            if name in href or stem in href:
                url = href if href.startswith("http") else SOS_BASE + href
                links[name] = url
                break
        else:
            # Broader match: any link containing SWVF
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
        total     = int(r.headers.get("content-length", 0))
        received  = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):   # 2 MB
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
        shutil.copyfileobj(f_in, f_out, length=8 * 1024 * 1024)   # 8 MB buffer
    size = out_path.stat().st_size
    print(f"\r  ✓ {out_path.name}  ({size/1e9:.2f} GB)              ")
    return out_path


# ── Prompt ────────────────────────────────────────────────────────────────────

def prompt_next_step(txt_files: list[Path]) -> str:
    total_rows_est = sum(f.stat().st_size for f in txt_files) // 140   # rough ~140 bytes/row
    from pathlib import Path as _Path
    parquet_dir = BASE_DIR / "source" / "parquet"
    parquet_ready = parquet_dir.exists() and any(parquet_dir.iterdir())
    cache_label   = "  ✓ Parquet cache ready (fast load)" if parquet_ready else "  ○ No Parquet cache yet (will build on first run)"
    print(f"\n{'='*60}")
    print(f"  {len(txt_files)} voter file(s) ready  (~{total_rows_est:,.0f} records estimated)")
    for f in txt_files:
        print(f"    {f.name}  {f.stat().st_size/1e9:.2f} GB")
    print(f"  {cache_label}")
    print("="*60)
    print("\n  Next step:")
    print("  [1]  Full Ohio → web dashboard JSON only  (fastest; recommended)")
    print("  [2]  Full Ohio → web dashboard JSON + summary Excel workbook")
    print("  [3]  Single-county → web dashboard JSON + full Excel workbook")
    print("  [4]  Exit  (files are ready for manual use)")
    print()
    return input("  Choice (1/2/3/4): ").strip()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  OHIO VOTER FILE PIPELINE")
    print("=" * 60)

    manifest = load_manifest()

    # 1 ── scrape page for download links (non-fatal — SOS site may block scrapers)
    links = {}
    try:
        links = scrape_download_links()
        if not links:
            print("  ⚠  No SWVF download links found on SOS page (page layout may have changed).")
            print(f"     Check manually: {SOS_URL}")
        else:
            print(f"  Found {len(links)} download link(s).\n")
    except RuntimeError as e:
        print(f"  ⚠  Could not reach SOS page: {e}")
        print("     Skipping download check — will use any files already on disk.\n")

    # 2 ── if we got links, compare remote Last-Modified against manifest
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

    # 3 ── if nothing to download (or scrape failed), jump straight to prompt
    txt_files = sorted(TXT_DIR.glob("SWVF_*.txt")) if TXT_DIR.exists() else []
    if not to_download:
        if txt_files:
            print("\n✓ Using files already on disk — no download needed.")
            choice = prompt_next_step(txt_files)
            _dispatch(choice, txt_files)
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
        choice = prompt_next_step(txt_files)
        _dispatch(choice, txt_files)


def _dispatch(choice: str, txt_files: list[Path]):
    import voter_data_cleaner_v2 as v2

    _log = v2.setup_logging('pipeline')
    src_date = v2.get_source_date(_log)

    if choice == "1":
        # Web dashboard JSON only — no Excel
        v2.run_ohio_analysis(txt_files, use_parquet=True)

    elif choice == "2":
        # Web dashboard JSON + summary Excel workbook
        v2.run_ohio_analysis(txt_files, use_parquet=True)
        out = BASE_DIR / f"ohio_analysis_src{src_date}.xlsx"
        v2.run_ohio_excel(txt_files, output_path=out, use_parquet=True)

    elif choice == "3":
        county = input("\n  County number (e.g. 57 for Montgomery County): ").strip().zfill(2)
        out = BASE_DIR / f"county_{county}_analysis_src{src_date}.xlsx"
        v2.run_county_analysis(txt_files, county_number=county, output_path=out, use_parquet=True)

    else:
        print("\nExiting. Voter files are in:")
        for f in txt_files:
            print(f"  {f}")


if __name__ == "__main__":
    main()
