"""
scrape_vtrapp_precincts.py
──────────────────────────
Scrapes the "Beginning Precinct" (cmb_precfrom) dropdown from Ohio county
BoE vtrapp pages at https://lookup.boe.ohio.gov/vtrapp/{county}/vtrreport.aspx

Observed text formats across counties
  Montgomery : "0010 BROOKVILLE A"      → code + name + sub-letter
  Greene     : "275 BATH TWP"           → code + multi-word name (no sub)
  Vinton     : "0001 BROWN TOWNSHIP"    → code + multi-word name (no sub)

Sub-field rule: last token is a sub iff it matches ^[A-Z]$ or ^\\d+-[A-Z]$
Everything else after the leading code is treated as part of the name.

Output: ./source/precinct_keys/{county}_precincts.csv
Columns: county | precinct_code | precinct_label | name | sub

Usage:
    python scrape_vtrapp_precincts.py              # interactive menu
    python scrape_vtrapp_precincts.py montgomery   # one county (test/retry)
    python scrape_vtrapp_precincts.py montgomery greene vinton

Requires: curl_cffi, beautifulsoup4
    pip install curl_cffi beautifulsoup4
"""

import csv
import random
import re
import sys
import time
import logging
from pathlib import Path

from curl_cffi import requests
from curl_cffi.requests.exceptions import HTTPError, RequestException, Timeout
from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
OUT_DIR  = BASE_DIR / "source" / "precinct_keys"
LOG_DIR  = BASE_DIR / "working"
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

# ── County lists ──────────────────────────────────────────────────────────────
# Confirmed as of 2026-05-09.  72 counties return the cmb_precfrom dropdown;
# 16 return "does not subscribe to Enhanced Website Features" (or time out to
# the same page).  72 + 16 = 88.
#
# Sources:
#   • Original TRIAD run 2026-05-09 (73 TRIAD counties, 9 non-subscribers found)
#   • Non-TRIAD probe 2026-05-09 (15 counties; 8 subscribe, 7 do not)

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
]  # 72 counties

# Counties confirmed to return "does not subscribe" instead of the dropdown.
# Kept here for documentation and the re-check menu option.
# Re-run option 2 periodically to detect contract changes.
NON_SUBSCRIBER_COUNTIES = [
    "butler",    "clermont",  "crawford",  "cuyahoga",  "franklin",
    "hamilton",  "hancock",   "henry",     "mercer",    "morrow",
    "ottawa",    "sandusky",  "stark",     "trumbull",  "wood",
    "wyandot",
]  # 16 counties

# Distinct sentinel returned by fetch_county when a county explicitly reports
# non-subscription (200 OK + message), as opposed to None (network / parse
# error).  Lets the summary distinguish "known skip" from "genuine failure".
_NOT_SUBSCRIBED = object()

BASE_URL = "https://lookup.boe.ohio.gov/vtrapp/{county}/vtrreport.aspx"

# Full Chrome 147 / Windows 10 header set matching the user's actual browser.
# Sec-Fetch-Site is "none" because each URL is navigated directly, not followed
# from a same-origin link.  Flips to "same-origin" after first successful hit.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;"
        "q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br, zstd",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
    "Sec-Fetch-User":            "?1",
    "sec-ch-ua":                 '"Chromium";v="147", "Google Chrome";v="147", "Not/A)Brand";v="24"',
    "sec-ch-ua-mobile":          "?0",
    "sec-ch-ua-platform":        '"Windows"',
    "DNT":                       "1",
    "Connection":                "keep-alive",
}

# Timing — Gaussian jitter around a 2.5s mean, clipped to [1.2, 5.0].
DELAY_MEAN  = 2.5
DELAY_SIGMA = 0.8
DELAY_MIN   = 1.2
DELAY_MAX   = 5.0

MAX_RETRIES = 3   # attempts per county before giving up

# Sub-field pattern: single uppercase letter OR digit(s)-dash-uppercase-letter.
# Matches: A  B  Z  1-A  2-B  10-C
# Rejects: TWP  CITY  TOWNSHIP  NORTH  SOUTH  EAST  WEST
_SUB_RE = re.compile(r"^(?:[A-Z]|\d+-[A-Z])$")


class BlockedError(Exception):
    """Raised on HTTP 403 — server has flagged the session. Abort immediately."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def human_delay(mean: float = DELAY_MEAN) -> None:
    """Sleep for a Gaussian-jittered duration around `mean` seconds."""
    delay = random.gauss(mean, DELAY_SIGMA)
    delay = max(DELAY_MIN, min(DELAY_MAX, delay))
    time.sleep(delay)


def backoff_delay(attempt: int) -> None:
    """Exponential backoff with uniform jitter: base * 2^attempt + U(0, 2)."""
    base  = 4 * (2 ** attempt) + random.uniform(0.0, 2.0)
    delay = min(base, 60.0)
    log.info("  backoff %.1fs before retry %d", delay, attempt + 1)
    time.sleep(delay)


def parse_label(text: str) -> tuple[str, str, str]:
    """
    Split a dropdown label into (code, name, sub).

    "0010 BROOKVILLE A"   → ("0010",  "BROOKVILLE",     "A")
    "0050 BUTLER TWP A"   → ("0050",  "BUTLER TWP",     "A")
    "0150 CLAYTON 1-A"    → ("0150",  "CLAYTON",        "1-A")
    "275 BATH TWP"        → ("275",   "BATH TWP",       "")
    "0001 BROWN TOWNSHIP" → ("0001",  "BROWN TOWNSHIP", "")
    """
    parts = text.strip().split()
    if not parts:
        return "", "", ""
    code = parts[0]
    if len(parts) == 1:
        return code, "", ""
    if len(parts) >= 3 and _SUB_RE.match(parts[-1]):
        return code, " ".join(parts[1:-1]), parts[-1]
    return code, " ".join(parts[1:]), ""


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_county(session: requests.Session, county: str) -> list[dict] | None:
    url = BASE_URL.format(county=county)

    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            # First successful contact establishes a session on this origin.
            # Real Chrome flips Sec-Fetch-Site to "same-origin" for all
            # subsequent navigations within the same host; mirror that here.
            if HEADERS.get("Sec-Fetch-Site") == "none":
                HEADERS["Sec-Fetch-Site"] = "same-origin"
            break
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 403:
                log.error("  403 Forbidden — session flagged. Aborting run.")
                raise BlockedError(county) from exc
            log.warning("  HTTP %s for %s — skipping.", status, county)
            return None
        except (RequestException, Timeout) as exc:
            log.warning("  attempt %d/%d failed: %s", attempt + 1, MAX_RETRIES, exc)
            if attempt + 1 < MAX_RETRIES:
                backoff_delay(attempt)
            else:
                log.error("  %s — all retries exhausted, skipped.", county)
                return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Detect counties that return 200 but display a "not subscribed" notice.
    # Return the _NOT_SUBSCRIBED sentinel (not None) so the caller can
    # distinguish this known state from a genuine network or parse failure.
    page_text = soup.get_text(" ", strip=True)
    if "does not subscribe" in page_text.lower():
        log.info("  %s — not subscribed to Enhanced Website Features. Skipping.", county)
        return _NOT_SUBSCRIBED

    select = (
        soup.find("select", {"id":   "cmb_precfrom"}) or
        soup.find("select", {"name": "cmb_precfrom"})
    )
    if select is None:
        log.error(
            "  %s — cmb_precfrom dropdown not found. "
            "Page may use a different structure. Check: %s", county, url
        )
        return None

    rows = []
    for opt in select.find_all("option"):
        code_val = opt.get("value", "").strip()
        if not code_val:
            continue
        label        = opt.get_text(strip=True)
        _, name, sub = parse_label(label)
        rows.append({
            "county":         county,
            "precinct_code":  code_val,
            "precinct_label": label,
            "name":           name,
            "sub":            sub,
        })

    log.info("  %d precincts", len(rows))
    return rows


# ── Output ────────────────────────────────────────────────────────────────────

FIELDNAMES = ["county", "precinct_code", "precinct_label", "name", "sub"]

def write_csv(county: str, rows: list[dict]) -> Path:
    path = OUT_DIR / f"{county}_precincts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


# ── Menu ─────────────────────────────────────────────────────────────────────

def show_menu() -> tuple[str, list[str], bool]:
    """
    Interactive mode selector shown when the script is run with no arguments.
    Returns (mode_label, targets, skip_existing).
    """
    done = sum(1 for c in SUBSCRIBER_COUNTIES if (OUT_DIR / f"{c}_precincts.csv").exists())

    print()
    print("  Ohio vtrapp Precinct Scraper")
    print("  " + "─" * 46)
    print(f"  1. Known vtrapp subscribers   ({done}/{len(SUBSCRIBER_COUNTIES)} done — resumes where you left off)")
    print(f"  2. Known non-subscribers      ({len(NON_SUBSCRIBER_COUNTIES)} counties — re-check status)")
    print()

    while True:
        choice = input("  Select [1-2]: ").strip()
        if choice == "1":
            # Skip-existing is always on for the normal scrape so the
            # script acts as a resume rather than a full re-scrape.
            return "Known subscribers", list(SUBSCRIBER_COUNTIES), True
        if choice == "2":
            # Re-probe known non-subscribers in case contract status changed.
            # Summary will flag any that now return the dropdown.
            return "Known non-subscribers", list(NON_SUBSCRIBER_COUNTIES), False
        print("  Please enter 1 or 2.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    flags       = {a for a in sys.argv[1:] if a.startswith("--")}
    county_args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not sys.argv[1:]:
        # ── Interactive menu ──────────────────────────────────────────────────
        mode_label, targets, skip_existing = show_menu()

    elif county_args:
        # ── Direct county list (CLI) ──────────────────────────────────────────
        mode_label    = "Direct"
        skip_existing = "--skip-existing" in flags
        targets       = [a.lower().replace(" ", "").replace("-", "") for a in county_args]
        all_known     = set(SUBSCRIBER_COUNTIES) | set(NON_SUBSCRIBER_COUNTIES)
        unknown       = set(targets) - all_known
        if unknown:
            log.warning("Not in any known county list (proceeding anyway): %s",
                        ", ".join(sorted(unknown)))

    else:
        # ── Flags only (e.g. --skip-existing with no county names) ───────────
        mode_label    = "Known subscribers"
        skip_existing = True
        targets       = list(SUBSCRIBER_COUNTIES)

    # ── Skip-existing filter ──────────────────────────────────────────────────
    if skip_existing:
        before  = len(targets)
        targets = [c for c in targets if not (OUT_DIR / f"{c}_precincts.csv").exists()]
        skipped = before - len(targets)
        if skipped:
            log.info("skip-existing: %d already done, %d remaining.", skipped, len(targets))
        if not targets:
            log.info("All targeted counties already scraped. Nothing to do.")
            return

    if not targets:
        log.info("No counties to scrape.")
        return

    log.info("Mode: %s | Counties: %d", mode_label, len(targets))
    random.shuffle(targets)
    log.info("Order randomised. First: %s", targets[0])

    session = requests.Session(impersonate="chrome131")
    success, failed, newly_unsubscribed = [], [], []

    try:
        for i, county in enumerate(targets, 1):
            log.info("[%d/%d] %s", i, len(targets), county)
            rows = fetch_county(session, county)
            if rows is _NOT_SUBSCRIBED:
                newly_unsubscribed.append(county)
            elif rows is not None:
                path = write_csv(county, rows)
                log.info("  → %s", path.name)
                success.append(county)
            else:
                failed.append(county)
            if i < len(targets):
                human_delay()
                if random.random() < 0.25:
                    extra = random.uniform(5.0, 7.0)
                    log.info("  (extra pause %.1fs)", extra)
                    time.sleep(extra)
    except BlockedError as exc:
        log.error("Run aborted after 403 on '%s'. Completed so far: %s",
                  exc, ", ".join(success) or "none")
        failed.extend(c for c in targets[targets.index(str(exc)):] if c not in success)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*52}")
    print(f"  Mode   : {mode_label}")
    print(f"  Done.  {len(success)} succeeded  |  {len(failed)} failed  |  {len(newly_unsubscribed)} unsubscribed")
    if failed:
        print(f"  Failed : {', '.join(failed)}")
        print(f"  Retry  : python scrape_vtrapp_precincts.py {' '.join(failed)}")
    if newly_unsubscribed:
        if mode_label == "Known non-subscribers":
            print(f"  Still no sub : {', '.join(newly_unsubscribed)}")
        else:
            # Unexpected — flag for addition to NON_SUBSCRIBER_COUNTIES.
            print(f"  Newly unsubscribed : {', '.join(newly_unsubscribed)}")
            print("  Move these to NON_SUBSCRIBER_COUNTIES in the script.")
    if success and mode_label == "Known non-subscribers":
        print(f"  Now subscribed! Move to SUBSCRIBER_COUNTIES: {', '.join(success)}")
    print(f"  Output : {OUT_DIR}")
    print(f"  Log    : {LOG_DIR / 'vtrapp_scrape.log'}")


if __name__ == "__main__":
    main()
