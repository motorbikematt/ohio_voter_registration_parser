"""
tools/generate_narratives.py
────────────────────────────
Reads existing chart JSON from docs/data/ and writes a {slug}_narrative.json
for every jurisdiction at the specified level(s).

Prose is produced by the per-level template registry in
tools/narrative/templates.py -- deterministic, hallucination-proof, and fast.
The LLM API path is Workstream 2 and is not implemented here.

Cache-skip strategy
───────────────────
Each output JSON stores a `metrics_hash` field -- a 16-char SHA-256 prefix of
the input metrics + template version.  On subsequent runs, if the hash matches
the existing file's hash, the file is skipped.  Bumping TEMPLATE_VERSION or
PER_LEVEL_CONFIG_VERSION in templates.py auto-invalidates all cached narratives
on the next run (no --overwrite needed).

Usage (CLI)
───────────
  # All 88 counties (default level)
  python tools/generate_narratives.py --templated

  # Targeted county run
  python tools/generate_narratives.py Hamilton Franklin --templated

  # All Hamilton precincts
  python tools/generate_narratives.py --level precinct Hamilton --templated

  # All cities
  python tools/generate_narratives.py --level city --templated

  # Every level in sequence
  python tools/generate_narratives.py --all-levels --templated

  # Inspect output without writing
  python tools/generate_narratives.py Hamilton --templated --dry-run

  # Force regeneration despite unchanged metrics
  python tools/generate_narratives.py --templated --overwrite

Usage (programmatic -- called by ohio_voter_pipeline.py)
────────────────────────────────────────────────────────
  from tools.generate_narratives import run_for_levels
  ok, skipped, failed = run_for_levels(['county', 'precinct'])
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# ---- Registry import ---------------------------------------------------------
# Insert tools/ onto sys.path so 'from narrative.templates import ...' resolves
# whether this file is run directly ('python tools/generate_narratives.py')
# or imported by ohio_voter_pipeline.py from the project root.
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from narrative.templates import (   # noqa: E402  (import after sys.path mutation)
    LEVELS,
    TEMPLATE_VERSION,
    PER_LEVEL_CONFIG_VERSION,
    build_metrics_for_level,
    build_narrative,
    metrics_hash as _metrics_hash,
)

# ---- Paths -------------------------------------------------------------------
ROOT     = _TOOLS_DIR.parent          # project root  (D:\vibe\election-data)
DATA_DIR = ROOT / 'docs' / 'data'
MANIFEST = ROOT / 'docs' / 'manifest.json'

# ---- Constants ---------------------------------------------------------------
# Label written to generated_by field when the template registry produced the
# prose.  Matches the locked decision from the planning session (2026-05-26).
GENERATED_BY_TEMPLATED = 'templated-v1'

# Jurisdiction levels that are neither county nor precinct.  Used by the
# pipeline to request narrative generation after jurisdictional_groupings.py
# has written its chart JSON.
NON_COUNTY_LEVELS = [l for l in LEVELS if l not in ('county', 'precinct')]

log = logging.getLogger(__name__)


# ---- Utilities ---------------------------------------------------------------

def county_slug(name: str) -> str:
    """
    Produce the filesystem slug for a county name.
    'Van Wert' -> 'van_wert'.  Matches voter_data_cleaner_v2 convention.
    """
    return name.lower().replace(' ', '_').replace("'", '')


def _load_json(path: Path) -> dict | None:
    """Return parsed JSON dict, or None if the file is missing or malformed."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        log.debug('Could not parse %s: %s', path.name, exc)
        return None


# ---- County-list extraction --------------------------------------------------

def load_county_list() -> list[str]:
    """
    Return the 88 Ohio county proper-cased names from manifest.json.

    manifest.json is occasionally written truncated mid-JSON by the pipeline
    (the file contains ~65k chart entries and can exceed write-buffer limits).
    When json.loads() fails, fall back to regex extraction of the allCounties
    array, which always appears near the top of the file and is reliably intact.
    """
    raw = MANIFEST.read_text(encoding='utf-8')
    try:
        d = json.loads(raw)
        counties = (
            d.get('processedCounties')
            or d.get('allCounties')
            or d.get('counties')
            or []
        )
        if counties:
            return counties
    except json.JSONDecodeError:
        pass  # fall through to regex

    m = re.search(r'"allCounties"\s*:\s*(\[.*?\])', raw, re.DOTALL)
    if m:
        log.debug('manifest.json truncated; used regex fallback for county list')
        return json.loads(m.group(1))

    raise RuntimeError(
        'Cannot extract county list from manifest.json -- '
        'file may be completely malformed.'
    )


# ---- Per-level enumeration ---------------------------------------------------

def enumerate_county(filter_names: list[str] | None = None) -> list[dict]:
    """
    Return one entry per county: {'slug': str, 'county': str}.
    filter_names restricts to those county names (proper-cased, as in manifest).
    """
    all_counties = load_county_list()
    if filter_names:
        all_counties = [c for c in all_counties if c in filter_names]
    return [{'slug': county_slug(c), 'county': c} for c in all_counties]


def enumerate_precinct(filter_counties: list[str] | None = None) -> list[dict]:
    """
    Walk each county's {county_slug}_precinct_index.json and yield one entry
    per precinct.

    Precinct index format (written by voter_data_cleaner_v2):
      { 'county': 'Hamilton',
        'precincts': [
          {'name': 'ADDYSTON A', 'safe_name': 'addyston_a', ...}, ...
        ] }

    Returns entries:
      { 'slug':          '{county_slug}_precinct_{safe_name}',
        'county_slug':   str,
        'county':        str (proper-cased),
        'precinct':      str (display name from index),
        'precinct_safe': str (safe_name from index) }
    """
    all_counties = load_county_list()
    if filter_counties:
        all_counties = [c for c in all_counties if c in filter_counties]

    entries = []
    for county_name in all_counties:
        cs  = county_slug(county_name)
        idx = _load_json(DATA_DIR / f'{cs}_precinct_index.json')
        if not idx:
            continue
        for p in idx.get('precincts', []):
            safe = p.get('safe_name', '')
            if not safe:
                continue
            entries.append({
                'slug':          f'{cs}_precinct_{safe}',
                'county_slug':   cs,
                'county':        county_name,
                'precinct':      p.get('name', safe),
                'precinct_safe': safe,
            })
    return entries


def enumerate_level(level: str) -> list[dict]:
    """
    For district/city/township/school/court levels, glob
    docs/data/{level}/*_party_affiliation.json to enumerate all jurisdictions.

    The slug is the filename stem minus '_party_affiliation' (e.g. '01' for
    state senate district 1, 'akron_city' for the city of Akron).

    Returns entries: {'slug': str, 'level': str, 'out_dir': Path}
    """
    level_dir = DATA_DIR / level
    if not level_dir.exists():
        log.debug('No data directory for level %r -- skipping', level)
        return []
    entries = []
    for pa_file in sorted(level_dir.glob('*_party_affiliation.json')):
        slug = pa_file.name.replace('_party_affiliation.json', '')
        entries.append({'slug': slug, 'level': level, 'out_dir': level_dir})
    return entries


# ---- Data loaders ------------------------------------------------------------

def _load_county_jsons(slug: str) -> tuple:
    """
    Load (party, generation, party_decade) chart JSONs for a county slug.
    County level renders both generation distribution and decade trend.
    """
    return (
        _load_json(DATA_DIR / f'{slug}_party_affiliation.json'),
        _load_json(DATA_DIR / f'{slug}_generation_distribution.json'),
        _load_json(DATA_DIR / f'{slug}_party_by_decade.json'),
    )


def _load_precinct_jsons(entry: dict) -> tuple:
    """
    Load (party, None, party_decade) for a precinct entry from enumerate_precinct().
    Generation distribution is not rendered for precincts (small n, noisy signal).
    """
    cs, ps = entry['county_slug'], entry['precinct_safe']
    return (
        _load_json(DATA_DIR / f'{cs}_precinct_{ps}_party.json'),
        None,
        _load_json(DATA_DIR / f'{cs}_precinct_{ps}_party_by_decade.json'),
    )


def _load_level_jsons(level: str, slug: str) -> tuple:
    """
    Load (party, None, party_decade) for any district/city/township/etc. slug.
    Generation distribution files are not produced for these levels by the
    current pipeline; templates.py omits the generation sentence gracefully.
    """
    level_dir = DATA_DIR / level
    return (
        _load_json(level_dir / f'{slug}_party_affiliation.json'),
        None,
        _load_json(level_dir / f'{slug}_party_by_decade.json'),
    )


# ---- Output path resolution --------------------------------------------------

def out_path_for(level: str, slug: str) -> Path:
    """
    Resolve the output narrative JSON path for any level/slug combination.

      county, precinct -> docs/data/{slug}_narrative.json
      (all other)      -> docs/data/{level}/{slug}_narrative.json
    """
    if level in ('county', 'precinct'):
        return DATA_DIR / f'{slug}_narrative.json'
    return DATA_DIR / level / f'{slug}_narrative.json'


# ---- Cache validation --------------------------------------------------------

def _cache_hit(out_path: Path, new_hash: str) -> bool:
    """
    Return True if the existing output JSON already has new_hash as its
    metrics_hash field -- meaning neither the input data nor the template
    version changed since the last run.  Bumping TEMPLATE_VERSION or
    PER_LEVEL_CONFIG_VERSION in templates.py produces a new hash that will
    not match any existing file, so the cache auto-invalidates statewide.
    """
    existing = _load_json(out_path)
    if not existing:
        return False
    return existing.get('metrics_hash') == new_hash


# ---- Core per-jurisdiction builder -------------------------------------------

def _process_one(
    *,
    level:         str,
    slug:          str,
    party_json:    dict | None,
    gen_json:      dict | None,
    pd_json:       dict | None,
    parent_county: str | None,
    out_path:      Path,
    overwrite:     bool,
    dry_run:       bool,
) -> str:
    """
    Build and write (or print) the narrative JSON for one jurisdiction.
    Returns 'ok', 'skipped', or 'failed'.

    Steps:
      1. Build a level-aware metrics dict via build_metrics_for_level().
      2. Compute metrics_hash.  Skip if it matches the existing file.
      3. Generate prose via build_narrative() (template registry; deterministic).
      4. Write output JSON (or print to stdout in --dry-run mode).

    Note: the LLM API path is Workstream 2 -- only the template path is active.
    Officeholders are not yet sourced; all office slots render placeholders.
    """
    # 1. Assemble level-aware metrics from raw chart JSON.
    metrics = build_metrics_for_level(
        level=level,
        party_json=party_json,
        decade_json=None,           # decade_trend derived from party_decade_json
        generation_json=gen_json,
        party_decade_json=pd_json,
        parent_county=parent_county,
        geography_counties=None,    # district->counties map is Workstream 2
    )
    if metrics is None:
        log.debug('No usable metrics for %s/%s -- skipping', level, slug)
        return 'failed'

    # 2. Cache check: skip if metrics + template versions are unchanged.
    mhash = _metrics_hash(metrics)
    if not overwrite and not dry_run and _cache_hit(out_path, mhash):
        log.info('Skip %s (metrics_hash unchanged)', out_path.name)
        return 'skipped'

    # 3. Generate prose.  officeholders=None -> all slots render placeholder text.
    narrative = build_narrative(metrics, officeholders=None)

    # 4a. Dry-run: print to stdout without writing.
    if dry_run:
        print(f"\n{'='*60}")
        print(f"[{level}] {slug}")
        print(narrative)
        return 'ok'

    # 4b. Write output JSON with full provenance fields.
    out = {
        'geography':         level,
        'level':             level,
        'jurisdiction_name': metrics['name'],
        'updated':           metrics['data_as_of'],
        'generated_by':      GENERATED_BY_TEMPLATED,
        'template_version':  TEMPLATE_VERSION,
        'config_version':    PER_LEVEL_CONFIG_VERSION,
        'metrics_hash':      mhash,
        'narrative':         narrative,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    log.info('Wrote %s', out_path.name)
    return 'ok'


# ---- Level-specific runners --------------------------------------------------

def _run_county(
    filter_names: list[str] | None,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Generate narrative JSONs for all (or filtered) counties."""
    ok = skipped = failed = 0
    for entry in enumerate_county(filter_names):
        slug = entry['slug']
        party, gen, pd = _load_county_jsons(slug)
        if party is None:
            log.warning('No party data for county %s -- skipping', slug)
            failed += 1
            continue
        result = _process_one(
            level='county', slug=slug,
            party_json=party, gen_json=gen, pd_json=pd,
            parent_county=None,
            out_path=out_path_for('county', slug),
            overwrite=overwrite, dry_run=dry_run,
        )
        ok      += result == 'ok'
        skipped += result == 'skipped'
        failed  += result == 'failed'
    return ok, skipped, failed


def _run_precinct(
    filter_counties: list[str] | None,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    """
    Generate narrative JSONs for all precincts across all (or filtered) counties.
    Missing precinct party files are logged at DEBUG -- they are expected during
    partial pipeline runs -- to avoid noise in the run log.
    """
    ok = skipped = failed = 0
    for entry in enumerate_precinct(filter_counties):
        party, gen, pd = _load_precinct_jsons(entry)
        if party is None:
            log.debug('No party data for precinct %s -- skipping', entry['slug'])
            failed += 1
            continue
        result = _process_one(
            level='precinct', slug=entry['slug'],
            party_json=party, gen_json=gen, pd_json=pd,
            parent_county=entry['county'],
            out_path=out_path_for('precinct', entry['slug']),
            overwrite=overwrite, dry_run=dry_run,
        )
        ok      += result == 'ok'
        skipped += result == 'skipped'
        failed  += result == 'failed'
    return ok, skipped, failed


def _run_level(
    level: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Generate narrative JSONs for all jurisdictions at a district/city/etc. level."""
    ok = skipped = failed = 0
    for entry in enumerate_level(level):
        slug = entry['slug']
        party, gen, pd = _load_level_jsons(level, slug)
        if party is None:
            log.debug('No party data for %s/%s -- skipping', level, slug)
            failed += 1
            continue
        result = _process_one(
            level=level, slug=slug,
            party_json=party, gen_json=gen, pd_json=pd,
            parent_county=None,
            out_path=out_path_for(level, slug),
            overwrite=overwrite, dry_run=dry_run,
        )
        ok      += result == 'ok'
        skipped += result == 'skipped'
        failed  += result == 'failed'
    return ok, skipped, failed


def _dispatch_level(
    level: str,
    filter_names: list[str] | None,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Route a single level string to its runner function."""
    if level == 'county':
        return _run_county(filter_names, overwrite, dry_run)
    if level == 'precinct':
        return _run_precinct(filter_names, overwrite, dry_run)
    return _run_level(level, overwrite, dry_run)


# ---- Public API (for pipeline import) ----------------------------------------

def run_for_levels(
    levels: list[str],
    filter_names: list[str] | None = None,
    overwrite: bool = False,
) -> tuple[int, int, int]:
    """
    Programmatic entry point called by ohio_voter_pipeline.py._narrative_phase().

    Runs the templated narrative generator for each specified level without
    touching sys.argv.  filter_names restricts county/precinct enumeration to
    those county names (proper-cased as they appear in manifest.json).

    Args:
        levels:       List of level strings from LEVELS, e.g. ['county', 'precinct'].
        filter_names: County names to process; None means all 88 counties.
        overwrite:    If True, regenerate even when metrics_hash is unchanged.

    Returns:
        (total_ok, total_skipped, total_failed) summed across all levels.

    Example:
        # At end of pipeline county-export phase:
        from tools.generate_narratives import run_for_levels
        ok, sk, fa = run_for_levels(['county', 'precinct'], filter_names=['Hamilton'])
    """
    total_ok = total_skipped = total_failed = 0
    for level in levels:
        ok, sk, fa = _dispatch_level(level, filter_names, overwrite, dry_run=False)
        log.info(
            '[narrative] %-35s  ok:%-5d  skipped:%-5d  failed:%d',
            level, ok, sk, fa,
        )
        total_ok      += ok
        total_skipped += sk
        total_failed  += fa
    return total_ok, total_skipped, total_failed


# ---- CLI ---------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    parser = argparse.ArgumentParser(
        description=(
            'Generate templated prose narratives for Ohio voter dashboard '
            'jurisdictions at any level (county, precinct, city, district, etc.).'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'names', nargs='*',
        metavar='NAME',
        help=(
            'County names (for --level county or precinct) or jurisdiction '
            'slugs to process.  Default: all jurisdictions for the level.'
        ),
    )
    parser.add_argument(
        '--level', default='county', choices=list(LEVELS),
        help='Jurisdiction level to generate narratives for.  Default: county.',
    )
    parser.add_argument(
        '--all-levels', action='store_true',
        help='Run all %(count)d levels in sequence (overrides --level).' % {'count': len(LEVELS)},
    )
    parser.add_argument(
        '--templated', action='store_true',
        help=(
            'Use the deterministic template registry to generate prose.  '
            'Required for offline / no-API-key runs.  '
            '(LLM API path is Workstream 2 -- not yet implemented.)'
        ),
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print generated narratives to stdout; do not write any files.',
    )
    parser.add_argument(
        '--overwrite', action='store_true',
        help=(
            'Ignore the metrics_hash cache and regenerate all files.  '
            'Normally not needed -- bumping TEMPLATE_VERSION in templates.py '
            'auto-invalidates the cache statewide.'
        ),
    )
    args = parser.parse_args()

    # Guard: --templated is required.  The LLM API path (Workstream 2) is not
    # yet implemented.  This prevents silent no-ops if someone forgets the flag.
    if not args.templated and not args.dry_run:
        parser.error(
            '--templated is required.  '
            'The LLM API path (Workstream 2) is not yet implemented.  '
            'Run with --templated to use the deterministic template registry.'
        )

    levels = list(LEVELS) if args.all_levels else [args.level]
    filter_names = args.names or None

    for level in levels:
        log.info('=== level: %s ===', level)
        ok, skipped, failed = _dispatch_level(
            level, filter_names, args.overwrite, args.dry_run,
        )
        if not args.dry_run:
            log.info(
                '[%s] done -- ok:%d  skipped:%d  failed:%d',
                level, ok, skipped, failed,
            )


if __name__ == '__main__':
    main()
