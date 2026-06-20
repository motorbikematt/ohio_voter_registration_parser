"""
precinct_key_manager.py
══════════════════════
Unified utility for sourcing and aggregating Ohio precinct keys.

This script combines the functionality of the vtrapp scraper and the Excel 
aggregator. It allows for the extraction of precinct metadata directly from 
county Board of Elections portals and the compilation of those keys into a 
single master reference workbook.

Functions:
──────────
1. SCRAPE: Extracts the "Beginning Precinct" (cmb_precfrom) dropdown from 
   Ohio county BoE vtrapp pages. 
   Source: https://lookup.boe.ohio.gov/vtrapp/{county}/vtrreport.aspx
   
   Sub-field rule: last token is a sub iff it matches ^[A-Z]$ or ^\\d+-[A-Z]$
   Everything else after the leading code is treated as part of the name.

2. AGGREGATE: Compiles all individual {county}_precincts.csv files into a 
   single multi-tab Excel workbook with formatted headers, auto-filters, 
   and frozen panes.

Output:
───────
- CSVs: ./source/precinct_keys/{county}_precincts.csv
- XLSX: ./precinct_keys_master.xlsx

Usage:
──────
    python tools/precinct_key_manager.py

Requires: curl_cffi, beautifulsoup4, xlsxwriter
"""

import csv
import random
import re
import sys
import time
import logging
from pathlib import Path

# Third-party imports
try:
    from curl_cffi import requests
    from curl_cffi.requests.exceptions import HTTPError, RequestException, Timeout
    from bs4 import BeautifulSoup
    import xlsxwriter
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install curl_cffi beautifulsoup4 xlsxwriter")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
# Note: Since this script lives in /tools, BASE_DIR points to the project root.
BASE_DIR = Path(__file__).parent.parent
OUT_DIR  = BASE_DIR / "local" / "source" / "precinct_keys"  # PATCH: Rerouted to local/ workspace
LOG_DIR  = BASE_DIR / "local" / "working"  # PATCH: Rerouted to local/ workspace
MASTER_XLSX = BASE_DIR / "precinct_keys_master.xlsx"

OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "vtrapp_scrape.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Scraping Configuration ───────────────────────────────────────────────────

SUBSCRIBER_COUNTIES = [
    "adams",      "allen",      "ashland",    "ashtabula",  "athens",
    "auglaize",   "belmont",    "brown",      "carroll",    "champaign",
    "clark",      "clinton",    "columbiana", "coshocton",  "darke",
    "defiance",   "delaware",   "erie",       "fairfield",  "fayette",
    "fulton",     "gallia",     "geauga",     "greene",     "guernsey",
    "hardin",     "harrison",   "highland",   "hocking",    "holmes",
    "huron",      "jackson",    "jefferson",  "knox",       "lake",
    "lawrence",   "licking",    "logan",      "lorain",     "lucas",
    "madison",    "mahoning",   "marion",     "medina",     "meigs",
    "miami",      "monroe",     "montgomery", "morgan",     "muskingum",
    "noble",      "paulding",   "perry",      "pickaway",   "pike",
    "portage",    "preble",     "putnam",     "richland",   "ross",
    "scioto",     "seneca",     "shelby",     "summit",     "tuscarawas",
    "union",      "vanwert",    "vinton",     "warren",     "washington",
    "wayne",      "williams",
]

BASE_URL = "https://lookup.boe.ohio.gov/vtrapp/{county}/vtrreport.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Site": "none",
}

DELAY_MEAN, DELAY_SIGMA = 2.5, 0.8
MAX_RETRIES = 3
_SUB_RE = re.compile(r"^(?:[A-Z]|\d+-[A-Z])$")
_NOT_SUBSCRIBED = object()

class BlockedError(Exception):
    """Raised on HTTP 403."""

# ── Scraping Logic ───────────────────────────────────────────────────────────

def human_delay():
    delay = max(1.2, min(5.0, random.gauss(DELAY_MEAN, DELAY_SIGMA)))
    time.sleep(delay)

def parse_label(text: str) -> tuple[str, str, str]:
    parts = text.strip().split()
    if not parts: return "", "", ""
    code = parts[0]
    if len(parts) == 1: return code, "", ""
    if len(parts) >= 3 and _SUB_RE.match(parts[-1]):
        return code, " ".join(parts[1:-1]), parts[-1]
    return code, " ".join(parts[1:]), ""

def fetch_county(session, county: str):
    url = BASE_URL.format(county=county)
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            if HEADERS.get("Sec-Fetch-Site") == "none":
                HEADERS["Sec-Fetch-Site"] = "same-origin"
            break
        except HTTPError as exc:
            if exc.response.status_code == 403: raise BlockedError(county)
            return None
        except Exception:
            if attempt + 1 < MAX_RETRIES: time.sleep(4 * (2 ** attempt))
            else: return None

    soup = BeautifulSoup(resp.text, "html.parser")
    if "does not subscribe" in soup.get_text().lower(): return _NOT_SUBSCRIBED

    select = soup.find("select", {"id": "cmb_precfrom"}) or soup.find("select", {"name": "cmb_precfrom"})
    if not select: return None

    rows = []
    for opt in select.find_all("option"):
        val = opt.get("value", "").strip()
        if not val: continue
        label = opt.get_text(strip=True)
        # Note: Following current cleanup directive, we only keep county, code, and label
        rows.append({
            "county": county,
            "precinct_code": val,
            "precinct_label": label
        })
    log.info(f"  {len(rows)} precincts")
    return rows

def run_scraper():
    """Executes the CSV export logic (formerly scrape_vtrapp_precincts.py)"""
    targets = [c for c in SUBSCRIBER_COUNTIES if not (OUT_DIR / f"{c}_precincts.csv").exists()]
    if not targets:
        log.info("All county CSVs already exist. Skipping scrape.")
        return True

    log.info(f"Scraping {len(targets)} counties...")
    random.shuffle(targets)
    session = requests.Session(impersonate="chrome131")
    
    success_count = 0
    try:
        for i, county in enumerate(targets, 1):
            log.info(f"[{i}/{len(targets)}] {county}")
            rows = fetch_county(session, county)
            if rows and rows is not _NOT_SUBSCRIBED:
                path = OUT_DIR / f"{county}_precincts.csv"
                with path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["county", "precinct_code", "precinct_label"])
                    writer.writeheader()
                    writer.writerows(rows)
                success_count += 1
            if i < len(targets): human_delay()
    except BlockedError:
        log.error("Scrape aborted due to 403 Forbidden.")
        return False
    
    log.info(f"Scrape complete. {success_count} new files created.")
    return True

# ── Aggregation Logic ────────────────────────────────────────────────────────

def run_aggregation():
    """Executes the Excel workbook logic (formerly aggregate_precinct_keys.py)"""
    csv_files = sorted(list(OUT_DIR.glob("*_precincts.csv")))
    if not csv_files:
        log.error("No CSV files found to aggregate.")
        return False

    log.info(f"Aggregating {len(csv_files)} files into {MASTER_XLSX.name}...")
    workbook = xlsxwriter.Workbook(str(MASTER_XLSX))
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
    
    for csv_file in csv_files:
        sheet_name = csv_file.name.replace("_precincts.csv", "")[:31]
        ws = workbook.add_worksheet(sheet_name)
        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for r_idx, row in enumerate(reader):
                    for c_idx, val in enumerate(row):
                        ws.write(r_idx, c_idx, val, header_fmt if r_idx == 0 else None)
            ws.autofilter(0, 0, 0, 2)
            ws.freeze_panes(1, 0)
            ws.set_column(0, 1, 15)
            ws.set_column(2, 2, 40)
        except Exception as e:
            log.error(f"Error indexing {csv_file.name}: {e}")

    workbook.close()
    log.info(f"Successfully created {MASTER_XLSX.name}")
    return True

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n  Ohio Precinct Key Manager")
    print("  " + "═" * 25)
    print("  1. Export CSVs Only (Scrape)")
    print("  2. Master Workbook Only (Aggregate)")
    print("  3. Both (Scrape & Aggregate)")
    print("  Q. Quit")
    
    choice = input("\n  Select [1-3, Q]: ").strip().upper()
    
    if choice == "1":
        run_scraper()
    elif choice == "2":
        run_aggregation()
    elif choice == "3":
        if run_scraper():
            run_aggregation()
    elif choice == "Q":
        sys.exit(0)
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
