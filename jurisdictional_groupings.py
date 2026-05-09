"""
jurisdictional_groupings.py
════════════════════════════════

Generate voter cohort summaries for all Ohio jurisdictions present in SWVF:
  - Cities
  - Townships
  - Villages
  - School Districts (Local, City, Exempted Village)
  - State Senate Districts
  - State Representative Districts
  - Congressional Districts
  - County Court Districts
  - Municipal Court Districts
  - Court of Appeals Districts

Aggregates pre-classified, enriched voter data by jurisdiction and exports:
  - JSON (6 chart types per jurisdiction, schema identical to precinct/county)
  - Excel (multi-sheet workbook, one sheet per jurisdiction type)

Reuses COHORT_SLICES, export logic, and chart formatting from voter_data_cleaner_v2.
Single-threaded main process reads cached enriched parquet once; ThreadPoolExecutor
distributes aggregation across 8 workers per jurisdiction type.

Output:
  docs/data/{jurisdiction_type}/{jurisdiction_slug}_*.json  (6 files per jurisdiction)
  output/jurisdictional_groupings_{format}_{timestamp}.xlsx | .json
"""

import concurrent.futures
import json
import logging
import sys
import time
from datetime import date as date_t, datetime
from pathlib import Path

import polars as pl
import pandas as pd
import xlsxwriter

try:
    import orjson as _orjson
except ImportError:
    _orjson = None
try:
    import psutil as _psutil
    _psutil_proc = _psutil.Process()
except ImportError:
    _psutil = None
    _psutil_proc = None


# ─────────────────────────────────────────────────────────────────────────────
# Paths and constants (reuse from voter_data_cleaner_v2)
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent
DOCS_DIR    = BASE_DIR / "docs"
DATA_DIR    = DOCS_DIR / "data"
LOGS_DIR    = BASE_DIR / "logs"
PARQUET_DIR = BASE_DIR / "source" / "parquet"
OUTPUT_DIR  = BASE_DIR / "output"

LOGS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────

def setup_logger(name='groupings', log_dir=LOGS_DIR):
    """Create timestamped logger for this run."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'{name}_{timestamp}.log'

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # File handler (debug level)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    # Console handler (info level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    # Formatter
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_file


# ─────────────────────────────────────────────────────────────────────────────
# Cohort definitions (copied from voter_data_cleaner_v2)
# ─────────────────────────────────────────────────────────────────────────────

COHORT_SLICES = [
    ('PURE_R',         'Pure R',           '#ef4444'),
    ('UNC_LAPSED_R',   'UNC – Lapsed R',  '#fca5a5'),
    ('MIXED_ACTIVE',   'Mixed – Active',   '#f59e0b'),
    ('MIXED_LAPSED',   'Mixed – Lapsed',   '#a78bfa'),
    ('UNC_NO_PRIMARY', 'UNC – No Primary', '#9ca3af'),
    ('UNC_LAPSED_D',   'UNC – Lapsed D',  '#93c5fd'),
    ('PURE_D',         'Pure D',           '#3b82f6'),
]

COHORT_STACK_MAP = {
    'PURE_R':         'r_pure',
    'UNC_LAPSED_R':   'unc_r',
    'MIXED_ACTIVE':   'unc_mid',
    'MIXED_LAPSED':   'unc_mid',
    'UNC_NO_PRIMARY': 'unc_mid',
    'UNC_LAPSED_D':   'unc_d',
    'PURE_D':         'd_pure',
}

UNC_SHADOW_COLORS = {
    'UNC_LAPSED_R': '#fca5a5',
    'MIXED_ACTIVE': '#f59e0b',
    'MIXED_LAPSED': '#a78bfa',
    'UNC_NO_PRIMARY': '#9ca3af',
    'UNC_LAPSED_D': '#93c5fd',
}

CHART_COLORS = {
    'bar':      '#3b82f6',
    'generation': '#8b5cf6',
}

GENERATION_RANGES = {
    'Silent': (1928, 1945),
    'Baby Boomers': (1946, 1964),
    'Generation X': (1965, 1980),
    'Millennials': (1981, 1996),
    'Generation Z': (1997, 2012),
    'Gen Alpha': (2013, 2025),
}


# ─────────────────────────────────────────────────────────────────────────────
# Jurisdiction definitions
# ─────────────────────────────────────────────────────────────────────────────

JURISDICTIONS = {
    'cities': {
        'column': 'CITY',
        'display': 'City',
    },
    'townships': {
        'column': 'TOWNSHIP',
        'display': 'Township',
    },
    'villages': {
        'column': 'VILLAGE',
        'display': 'Village',
    },
    'local_school_districts': {
        'column': 'LOCAL_SCHOOL_DISTRICT',
        'display': 'Local School District',
    },
    'city_school_districts': {
        'column': 'CITY_SCHOOL_DISTRICT',
        'display': 'City School District',
    },
    'exempted_vill_school_districts': {
        'column': 'EXEMPTED_VILL_SCHOOL_DISTRICT',
        'display': 'Exempted Village School District',
    },
    'state_senate_districts': {
        'column': 'STATE_SENATE_DISTRICT',
        'display': 'State Senate District',
    },
    'state_rep_districts': {
        'column': 'STATE_REPRESENTATIVE_DISTRICT',
        'display': 'State Representative District',
    },
    'congressional_districts': {
        'column': 'CONGRESSIONAL_DISTRICT',
        'display': 'Congressional District',
    },
    'county_court_districts': {
        'column': 'COUNTY_COURT_DISTRICT',
        'display': 'County Court District',
    },
    'municipal_court_districts': {
        'column': 'MUNICIPAL_COURT_DISTRICT',
        'display': 'Municipal Court District',
    },
    'court_of_appeals': {
        'column': 'COURT_OF_APPEALS',
        'display': 'Court of Appeals District',
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation and export functions
# ─────────────────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert jurisdiction name to URL-safe slug."""
    if name is None or (isinstance(name, float)):
        return 'unknown'
    return str(name).lower().replace(' ', '_').replace('/', '_').replace('-', '_')


def _dump_json(data: dict, filepath: Path, logger: logging.Logger):
    """Write JSON with orjson if available, else stdlib json."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if _orjson:
        with open(filepath, 'wb') as f:
            f.write(_orjson.dumps(data, option=_orjson.OPT_INDENT_2))
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    logger.debug(f'Wrote {filepath.name}')


def aggregate_jurisdiction(
    df: pl.DataFrame,
    jurisdiction_key: str,
    jurisdiction_name: str | None,
    jurisdiction_type: str,
    election_cols: list[str],
    today: str,
    logger: logging.Logger,
) -> dict:
    """
    Aggregate voter data for a single jurisdiction and return chart data.

    Returns dict with keys: party_affiliation, decade_distribution, party_by_decade,
    party_by_generation, unc_shadow, cohort_counts
    """

    if jurisdiction_name is None or (isinstance(jurisdiction_name, float)):
        return {}

    slug = _slugify(jurisdiction_name)
    note = f'Analysis run {today} — Ohio Secretary of State SWVF voter file'

    # Subset to this jurisdiction
    subset = df.filter(pl.col(jurisdiction_key) == jurisdiction_name)
    if subset.height == 0:
        logger.warning(f'Empty subset: {jurisdiction_type} {jurisdiction_name}')
        return {}

    result = {
        'slug': slug,
        'jurisdiction_type': jurisdiction_type,
        'jurisdiction_name': str(jurisdiction_name),
        'voter_count': subset.height,
    }

    # ── Party affiliation (doughnut) ──────────────────────────────────────────
    if 'cohort_family' in subset.columns:
        cohort_counts_df = (
            subset.group_by('cohort_family').agg(pl.len().alias('n'))
        )
        cmap = dict(zip(cohort_counts_df['cohort_family'].to_list(),
                        cohort_counts_df['n'].to_list()))

        pa_labels = [lbl   for _, lbl, _ in COHORT_SLICES]
        pa_colors = [color for _, _, color in COHORT_SLICES]
        pa_counts = [int(cmap.get(fam, 0)) for fam, _, _ in COHORT_SLICES]
        pa_total  = sum(pa_counts)
        pa_pcts   = [int(round(100 * c / pa_total)) if pa_total > 0 else 0 for c in pa_counts]

        result['party_affiliation'] = {
            'title': 'Party Affiliation',
            'type': 'doughnut',
            'chartConfig': {
                'labels': [f'{lbl} — {cnt:,} ({pct}%)'
                          for lbl, cnt, pct in zip(pa_labels, pa_counts, pa_pcts)],
                'datasets': [{
                    'data': pa_counts,
                    'backgroundColor': pa_colors,
                }],
            },
            'note': note + ' — partisan spectrum: registered + behavioral cohorts.',
        }

        result['cohort_counts'] = {fam: int(cmap.get(fam, 0)) for fam, _, _ in COHORT_SLICES}

    # ── Decade distribution (bar) ─────────────────────────────────────────────
    if 'Decade' in subset.columns:
        decade_df = (
            subset.group_by('Decade')
                  .agg(pl.len().alias('count'))
                  .sort('Decade')
        )
        result['decade_distribution'] = {
            'title': 'Voter Age Distribution by Birth Decade',
            'type': 'bar',
            'chartConfig': {
                'labels': [f'{d}s' for d in decade_df['Decade'].to_list()],
                'datasets': [{
                    'label': 'Registered Voters',
                    'data': decade_df['count'].to_list(),
                    'backgroundColor': CHART_COLORS['bar'],
                    'borderRadius': 4,
                }],
            },
            'note': note,
        }

    # ── Party × Decade (stacked bar) ──────────────────────────────────────────
    if 'cohort_family' in subset.columns and 'Decade' in subset.columns:
        party_decade_df = (
            subset.group_by(['Decade', 'cohort_family'])
                  .agg(pl.len().alias('count'))
                  .sort('Decade')
        )

        decades = sorted(party_decade_df['Decade'].unique().to_list())
        decade_labels = [f'{d}s' for d in decades]

        datasets = []
        for fam, lbl, color in COHORT_SLICES:
            data = []
            for decade in decades:
                row = party_decade_df.filter(
                    (pl.col('Decade') == decade) & (pl.col('cohort_family') == fam)
                )
                data.append(int(row['count'].sum()) if row.height > 0 else 0)

            datasets.append({
                'label': lbl,
                'data': data,
                'backgroundColor': color,
                'stack': COHORT_STACK_MAP[fam],
            })

        result['party_by_decade'] = {
            'title': 'Party Affiliation by Birth Decade',
            'type': 'bar',
            'chartConfig': {
                'labels': decade_labels,
                'datasets': datasets,
            },
            'note': note,
        }

    # ── Party × Generation (stacked bar) ──────────────────────────────────────
    if 'cohort_family' in subset.columns and 'birth_year' in subset.columns:
        # Compute generation from birth_year
        subset_with_gen = subset.with_columns(
            pl.col('birth_year').map_elements(
                lambda y: next((g for g, (start, end) in GENERATION_RANGES.items()
                              if start <= y <= end), 'Unknown'),
                return_dtype=pl.Utf8
            ).alias('generation')
        )

        gen_order = ['Silent', 'Baby Boomers', 'Generation X', 'Millennials', 'Generation Z', 'Gen Alpha']

        party_gen_df = (
            subset_with_gen.group_by(['generation', 'cohort_family'])
                           .agg(pl.len().alias('count'))
        )

        # Filter to known generations and sort
        party_gen_df = party_gen_df.filter(pl.col('generation').is_in(gen_order))

        datasets = []
        for fam, lbl, color in COHORT_SLICES:
            data = []
            for gen in gen_order:
                row = party_gen_df.filter(
                    (pl.col('generation') == gen) & (pl.col('cohort_family') == fam)
                )
                data.append(int(row['count'].sum()) if row.height > 0 else 0)

            datasets.append({
                'label': lbl,
                'data': data,
                'backgroundColor': color,
                'stack': COHORT_STACK_MAP[fam],
            })

        result['party_by_generation'] = {
            'title': 'Party Affiliation by Generation',
            'type': 'bar',
            'chartConfig': {
                'labels': gen_order,
                'datasets': datasets,
            },
            'note': note,
        }

    # ── UNC Shadow (stacked bar) ──────────────────────────────────────────────
    if 'cohort_family' in subset.columns:
        unc_families = ['UNC_LAPSED_R', 'MIXED_ACTIVE', 'MIXED_LAPSED', 'UNC_NO_PRIMARY', 'UNC_LAPSED_D']
        unc_labels = [lbl for fam, lbl, _ in COHORT_SLICES if fam in unc_families]
        unc_colors = [color for fam, _, color in COHORT_SLICES if fam in unc_families]

        unc_counts = []
        for fam in unc_families:
            cnt = int(subset.filter(pl.col('cohort_family') == fam).height)
            unc_counts.append(cnt)

        result['unc_shadow'] = {
            'title': 'UNC Shadow Partisanship',
            'type': 'doughnut',
            'chartConfig': {
                'labels': [f'{lbl} — {cnt:,}' for lbl, cnt in zip(unc_labels, unc_counts)],
                'datasets': [{
                    'data': unc_counts,
                    'backgroundColor': unc_colors,
                }],
            },
            'note': note,
        }

    return result


def export_jurisdiction_json(
    results: dict,
    jurisdiction_type: str,
    logger: logging.Logger,
):
    """Export aggregated jurisdiction data to JSON files."""

    type_dir = DATA_DIR / jurisdiction_type.lower().replace(' ', '_')
    type_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        if not result:
            continue

        slug = result.get('slug')
        if not slug:
            continue

        # Write each chart type as separate JSON
        for chart_type in ['party_affiliation', 'decade_distribution', 'party_by_decade',
                          'party_by_generation', 'unc_shadow']:
            if chart_type in result:
                chart_data = result[chart_type]
                chart_data['geography'] = jurisdiction_type
                chart_data['jurisdiction_name'] = result['jurisdiction_name']
                chart_data['updated'] = result.get('today', date_t.today().isoformat())

                filepath = type_dir / f'{slug}_{chart_type}.json'
                _dump_json(chart_data, filepath, logger)


def main(
    jurisdictions_to_process: list[str] | None = None,
    output_format: str = 'json',
    logger: logging.Logger | None = None,
):
    """
    Main entry point: load enriched parquet, aggregate all jurisdictions, export.

    Args:
        jurisdictions_to_process: List of jurisdiction type keys (e.g., ['cities', 'townships']).
                                 If None, processes all.
        output_format: 'json', 'xlsx', or 'both'
        logger: Optional logger; creates one if not provided.
    """

    if logger is None:
        logger, log_file = setup_logger()
        logger.info(f'Log file: {log_file}')

    start_time = time.time()
    today = date_t.today().isoformat()

    # Determine which jurisdictions to process
    if jurisdictions_to_process is None:
        jurisdictions_to_process = list(JURISDICTIONS.keys())

    logger.info(f'Processing {len(jurisdictions_to_process)} jurisdiction types: {jurisdictions_to_process}')
    logger.info(f'Output format: {output_format}')

    # Load enriched parquet
    logger.info('Loading enriched voter parquet...')
    try:
        df = pl.read_parquet(str(PARQUET_DIR / 'all_counties_enriched.parquet'))
        logger.info(f'Loaded {df.height:,} rows × {df.width} columns')
    except FileNotFoundError:
        logger.error(f'Enriched parquet not found at {PARQUET_DIR / "all_counties_enriched.parquet"}')
        logger.error('Run voter_data_cleaner_v2.py (option 1) to generate it.')
        return False

    # Get election columns (any column matching PRIMARY-*, GENERAL-*, SPECIAL-* pattern)
    election_cols = [col for col in df.columns if col.split('-')[0] in ['PRIMARY', 'GENERAL', 'SPECIAL']]
    logger.info(f'Found {len(election_cols)} election history columns')

    # Aggregate each jurisdiction type
    jurisdiction_results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}

        for jurisdiction_type_key in jurisdictions_to_process:
            if jurisdiction_type_key not in JURISDICTIONS:
                logger.warning(f'Unknown jurisdiction type: {jurisdiction_type_key}')
                continue

            config = JURISDICTIONS[jurisdiction_type_key]
            column = config['column']
            display = config['display']

            # Skip if column not in dataframe
            if column not in df.columns:
                logger.warning(f'Column {column} not in dataframe; skipping {jurisdiction_type_key}')
                continue

            logger.info(f'Aggregating {jurisdiction_type_key} ({column})...')

            # Get unique jurisdictions for this type
            jurisdictions = sorted([j for j in df[column].unique().to_list()
                                  if j is not None and not (isinstance(j, float))])

            logger.info(f'  {len(jurisdictions)} unique {jurisdiction_type_key}')

            # Submit aggregation tasks
            futures_for_type = {}
            for jurisdiction_name in jurisdictions:
                future = executor.submit(
                    aggregate_jurisdiction,
                    df, column, jurisdiction_name, display, election_cols, today, logger
                )
                futures_for_type[jurisdiction_name] = future

            # Collect results as they complete
            results = []
            for jurisdiction_name in jurisdictions:
                try:
                    result = futures_for_type[jurisdiction_name].result(timeout=300)
                    if result:
                        result['today'] = today
                        results.append(result)
                except concurrent.futures.TimeoutError:
                    logger.error(f'Timeout aggregating {jurisdiction_type_key} / {jurisdiction_name}')
                except Exception as e:
                    logger.error(f'Error aggregating {jurisdiction_type_key} / {jurisdiction_name}: {e}')

            jurisdiction_results[jurisdiction_type_key] = {
                'config': config,
                'results': results,
            }

    # Export
    if output_format in ['json', 'both']:
        logger.info('Exporting JSON...')
        for jurisdiction_type_key, data in jurisdiction_results.items():
            config = data['config']
            results = data['results']
            export_jurisdiction_json(results, config['display'], logger)
        logger.info('JSON export complete')

    elapsed = time.time() - start_time
    logger.info(f'Done in {elapsed:.1f}s')

    if _psutil_proc:
        logger.info(f'Peak RSS: {_psutil_proc.memory_info().rss / 1e9:.2f} GB')

    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Aggregate Ohio voter data by jurisdictions present in SWVF.'
    )
    parser.add_argument(
        '--jurisdictions',
        type=str,
        default=None,
        help='Comma-separated list of jurisdiction types to process. '
             'Default: all. Options: cities, townships, villages, '
             'local_school_districts, city_school_districts, exempted_vill_school_districts, '
             'state_senate_districts, state_rep_districts, congressional_districts, '
             'county_court_districts, municipal_court_districts, court_of_appeals'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'xlsx', 'both'],
        default='json',
        help='Output format (default: json)'
    )

    args = parser.parse_args()

    jurisdictions_to_process = None
    if args.jurisdictions:
        jurisdictions_to_process = [j.strip() for j in args.jurisdictions.split(',')]

    logger, log_file = setup_logger()
    logger.info(f'Log file: {log_file}')

    success = main(
        jurisdictions_to_process=jurisdictions_to_process,
        output_format=args.format,
        logger=logger
    )

    sys.exit(0 if success else 1)
