"""
tools/narrative/officeholders.py
─────────────────────────────────
Adapter: Ohio Roster scraper output -> the `officeholders` dict shape
build_narrative() already expects (see templates.py:
LEVEL_CONFIGS['county']['officeholder_offices']).

DATA SOURCE (read this before re-running anything)
───────────────────────────────────────────────────
This module does NOT scrape, does NOT call any API, and does NOT compute
who currently holds office. It only READS two CSVs per county, already on
disk, written by a separate script:

    local/source/County Data Files/<NN>_<CountyName>/
        <NN>_<CountyName>_roster_facts.csv      <- county-level facts
        <NN>_<CountyName>_roster_officers.csv   <- per-officer rows (THIS is
                                                    what this module reads)

    Written by:  local/source/County Data Files/scrape_ohio_roster.PY
    Sourced from: https://ohioroster.ohiosos.gov (Ohio SoS "Official Roster")

If officeholder data here looks stale, wrong, or missing for a county:
  -> The fix is to RE-RUN scrape_ohio_roster.PY (it resumes; it will not
     re-fetch ranges it already has, and appends any new biennium range
     the SoS site has published). Do NOT edit this module to "correct" an
     officeholder -- there is no local override mechanism, and there
     should not be one; the roster CSVs are the single source of truth.
  -> This module will pick up whatever is newest in the CSVs automatically
     on its next call. It has no cache of its own and no state of its own.

Deterministic only. No LLM calls, no network calls of any kind happen in
this module -- it is a pure CSV-to-dict reshape, safe to call as often as
needed at zero marginal cost.

Update-safe across future scrapes (no code change needed after a rescrape)
────────────────────────────────────────────────────────────────────────────
"Current" is derived per county from the CSVs at call time, never hardcoded:
  1. facts range   = max(range) present in that county's *_roster_facts.csv
  2. officer range = max(range) present in that county's *_roster_officers.csv
     that actually HAS >=1 officer row (falls back below the facts range
     when the newest edition's officer table is still empty -- true as of
     the 2025-2026 edition statewide: facts populated, officer table empty
     for all 88 counties, confirmed 2026-07-13 by direct inspection of the
     scraped CSVs).
When scrape_ohio_roster.PY is next re-run -- after a future election, or
whenever the SoS backfills a previously-empty officer table -- these two
maxima change automatically the next time this module is called. No edit
to this file, templates.py, or generate_narratives.py is required for that
data update to take effect; only the source CSVs need to change.

Office coverage (only 3 of templates.py's county-level slots are sourced)
────────────────────────────────────────────────────────────────────────────
    Commissioner          -> county_commissioner  (list; 3 seats)
    Sheriff                -> sheriff               (single)
    Prosecuting Attorney   -> prosecutor             (single)
templates.py's other county-level slots (us_senator, us_representative,
state_senator, state_representative) have NO roster-site source -- the
Ohio Roster site does not publish those offices -- and will continue
rendering the existing "data not yet available" placeholder regardless of
how often scrape_ohio_roster.PY is re-run. Sourcing those would require a
different upstream dataset, not more scrapes of this site.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
COUNTY_DATA_DIR = ROOT / 'local' / 'source' / 'County Data Files'
COUNTY_MAP_CSV = COUNTY_DATA_DIR / 'Ohio_##_CountyName.csv'

# roster `position` string -> templates.py office_key
POSITION_TO_OFFICE_KEY = {
    'Commissioner': 'county_commissioner',
    'Sheriff': 'sheriff',
    'Prosecuting Attorney': 'prosecutor',
}


def _normalize_name(raw: str) -> str:
    """Collapse repeated internal whitespace (roster site emits e.g.
    'James   Carmichael' with irregular spacing)."""
    return ' '.join((raw or '').split())


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_county_folder_map() -> dict[str, str]:
    """
    Return {county_slug: folder_name}, e.g. {'van_wert': '81_Van Wert'}.
    county_slug matches generate_narratives.county_slug()'s convention
    ('Van Wert' -> 'van_wert') so callers can key off the same slug used
    for party_json/gen_json lookups.
    """
    if not COUNTY_MAP_CSV.exists():
        return {}
    mapping = {}
    for row in _read_csv_rows(COUNTY_MAP_CSV):
        num = row['County Number'].strip()
        name = row['County Name'].strip()
        slug = name.lower().replace(' ', '_').replace("'", '')
        mapping[slug] = f'{num}_{name}'
    return mapping


def _current_officer_range(officer_rows: list[dict]) -> str | None:
    """
    Pick the "current" biennium range from a county's own
    *_roster_officers.csv rows (source: scrape_ohio_roster.PY -> see
    module docstring). Always the max range that HAS >=1 officer row --
    NOT necessarily the newest range in *_roster_facts.csv, since the
    roster site can (and as of 2026-07-13, does for all 88 counties)
    publish a new biennium's facts page before its officer table is
    populated. Re-running the scraper is what advances this value;
    nothing here needs to change when that happens.
    """
    ranges_with_officers = {r['range'] for r in officer_rows if r.get('range')}
    if not ranges_with_officers:
        return None
    return max(ranges_with_officers)


def build_officeholders_for_county(folder_name: str) -> dict:
    """
    Read one county's *_roster_officers.csv (source: scrape_ohio_roster.PY,
    see module docstring -- NOT fetched or computed here) and return the
    officeholders dict for build_narrative(), e.g.:
        {
          'county_commissioner': [{'name': ..., 'party': ...}, ...],
          'sheriff': {'name': ..., 'party': ...},
          'prosecutor': {'name': ..., 'party': ...},
        }
    Offices with no current-range data are simply absent from the dict --
    _build_officeholder_block() already renders "data not yet available"
    for any missing key, so no placeholder logic is needed here.

    folder_name is the roster scraper's own folder naming convention
    (e.g. '85_Wayne', '81_Van Wert' -- NOT a county_slug). Use
    load_county_folder_map() or build_officeholders_by_slug() if you only
    have a county_slug on hand.
    """
    out_dir = COUNTY_DATA_DIR / folder_name
    officers_path = out_dir / f'{folder_name}_roster_officers.csv'
    officer_rows = _read_csv_rows(officers_path)

    current_range = _current_officer_range(officer_rows)
    if current_range is None:
        return {}

    current_rows = [r for r in officer_rows if r['range'] == current_range]

    by_office: dict[str, list[dict]] = {}
    for row in current_rows:
        office_key = POSITION_TO_OFFICE_KEY.get(row['position'])
        if office_key is None:
            continue
        entry = {'name': _normalize_name(row['name_of_officer'])}
        party = (row.get('politics') or '').strip()
        if party and party != 'Unknown':
            entry['party'] = party
        by_office.setdefault(office_key, []).append(entry)

    officeholders: dict = {}
    for office_key, holders in by_office.items():
        # Single-seat offices (Sheriff, Prosecutor) render as one dict;
        # multi-seat offices (Commissioner) stay a list -- matches the
        # isinstance(holders, list) branch in _build_officeholder_block().
        officeholders[office_key] = holders[0] if len(holders) == 1 else holders

    return officeholders


def build_officeholders_by_slug() -> dict[str, dict]:
    """
    Return {county_slug: officeholders_dict} for all 88 counties in one pass.
    Intended for a single bulk load at the start of a generate_narratives.py
    run, mirroring how manifest.json / party_json are loaded once and reused
    -- avoids re-reading 88 CSV pairs per-jurisdiction.
    """
    folder_map = load_county_folder_map()
    result = {}
    for slug, folder_name in folder_map.items():
        officeholders = build_officeholders_for_county(folder_name)
        if officeholders:
            result[slug] = officeholders
    return result
