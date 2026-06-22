"""Validate the jurisdiction-vs-postal city fields in an enriched voter parquet.

Run this whenever a new SWVF drop is ingested. It confirms the per-county field
coverage that the pipeline's municipality resolver
(`_dominant_city_per_precinct` in pipeline/voter_data_cleaner.py) depends on, and
flags any precinct that would be mislabeled by a postal-city fallback.

Background -- Ohio SWVF official file layout:
  https://www6.ohiosos.gov/ords/f?p=111:2  (also mirrored in
  local/source/Voter_File_Layout.md)
The voter file carries TWO unrelated location families:
    * Postal address:  RESIDENTIAL_CITY / RESIDENTIAL_ZIP ... -> USPS mail
      delivery only. NOT a legal jurisdiction.
    * Authoritative jurisdiction: CITY / VILLAGE / WARD / TOWNSHIP / PRECINCT ->
      the Board of Elections' assignment of where a voter legally votes. CITY is
      blank for voters in an unincorporated township (they vote in NO city);
      their TOWNSHIP column names the township.
Conflating them (backfilling a blank CITY from RESIDENTIAL_CITY) mislabels
township precincts with their post-office city -- e.g. Montgomery's
WASHINGTON TWP F (CITY='', TOWNSHIP='WASHINGTON TOWNSHIP') gets tagged KETTERING
because its mail is delivered from the Kettering post office.

The resolver therefore uses a jurisdiction HIERARCHY, not a postal fallback:
  CITY -> VILLAGE -> WARD-prefix -> TOWNSHIP(=not a city) -> RESIDENTIAL_CITY.
Bounded all-county checks established why: 69 counties populate CITY; 16 of the
remaining blank-CITY counties populate TOWNSHIP~100%; Cuyahoga (18) encodes the
municipality in its WARD prefix ('CLEVELAND WARD 7') and PRECINCT_NAME; only
Wyandot (88) has no authoritative column at all, so postal is a true last resort
there -- 1 county, not 19.

What this checks, per county:
  1. CITY coverage        -- % of voters with a non-blank authoritative CITY.
  2. Hierarchy coverage   -- for blank-CITY counties, the % populated of each
     fallback column (VILLAGE / WARD / TOWNSHIP) and whether ANY authoritative
     column covers the county. Counties with none are the true postal-last-resort
     set (expected: just Wyandot).
  3. Name conflicts       -- precincts whose NAME is a township/village but whose
     postal RESIDENTIAL_CITY is a different municipality (the mislabel risk a
     postal fallback would reintroduce).

Read-only. Bounded output. Exit code is non-zero under --strict if any
HIGH-severity mislabel is found, so this can gate a pipeline run in CI.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import polars as pl

DEFAULT_PARQUET = Path('local/source/parquet_enriched/enriched_voters.parquet')

# Ohio's 88 counties are numbered 01-88 in alphabetical order (fixed by statute).
OHIO_COUNTIES = [
    'Adams', 'Allen', 'Ashland', 'Ashtabula', 'Athens', 'Auglaize', 'Belmont',
    'Brown', 'Butler', 'Carroll', 'Champaign', 'Clark', 'Clermont', 'Clinton',
    'Columbiana', 'Coshocton', 'Crawford', 'Cuyahoga', 'Darke', 'Defiance',
    'Delaware', 'Erie', 'Fairfield', 'Fayette', 'Franklin', 'Fulton', 'Gallia',
    'Geauga', 'Greene', 'Guernsey', 'Hamilton', 'Hancock', 'Hardin', 'Harrison',
    'Henry', 'Highland', 'Hocking', 'Holmes', 'Huron', 'Jackson', 'Jefferson',
    'Knox', 'Lake', 'Lawrence', 'Licking', 'Logan', 'Lorain', 'Lucas',
    'Madison', 'Mahoning', 'Marion', 'Medina', 'Meigs', 'Mercer', 'Miami',
    'Monroe', 'Montgomery', 'Morgan', 'Morrow', 'Muskingum', 'Noble', 'Ottawa',
    'Paulding', 'Perry', 'Pickaway', 'Pike', 'Portage', 'Preble', 'Putnam',
    'Richland', 'Ross', 'Sandusky', 'Scioto', 'Seneca', 'Shelby', 'Stark',
    'Summit', 'Trumbull', 'Tuscarawas', 'Union', 'Van Wert', 'Vinton',
    'Warren', 'Washington', 'Wayne', 'Williams', 'Wood', 'Wyandot',
]
COUNTY_NAME = {f'{i + 1:02d}': n for i, n in enumerate(OHIO_COUNTIES)}

# A county is a true "postal last resort" only if NO authoritative jurisdiction
# column (CITY/VILLAGE/WARD/TOWNSHIP) covers it -- i.e. any_auth_cov below this
# threshold. A merely-blank CITY does NOT qualify (TOWNSHIP/WARD usually cover
# it). Tunable. Expected to select exactly Wyandot (88) on the current file.
POSTAL_ONLY_CITY_COVERAGE = 0.10
TWP_VILLAGE_RE = r'\bTWP\b|\bTOWNSHIP\b|\bVILLAGE\b|\bVILL\b'


def _nonblank(col: str) -> pl.Expr:
    return pl.col(col).is_not_null() & (pl.col(col).str.strip_chars() != '')


def coverage_by_county(lf: pl.LazyFrame) -> pl.DataFrame:
    """Per-county non-blank coverage of every jurisdiction-hierarchy column plus
    the postal RESIDENTIAL_CITY. `any_auth_cov` is the fraction of voters covered
    by ANY authoritative column (CITY/VILLAGE/WARD/TOWNSHIP) -- counties near 0
    there are the true postal-last-resort set."""
    cols = lf.collect_schema().names()
    auth = [c for c in ('CITY', 'VILLAGE', 'WARD', 'TOWNSHIP') if c in cols]
    agg = [pl.len().alias('voters')]
    for c in auth + (['RESIDENTIAL_CITY'] if 'RESIDENTIAL_CITY' in cols else []):
        agg.append(_nonblank(c).sum().alias(f'{c.lower()}_nb'))
    # any_auth: voter covered if any authoritative column is non-blank.
    any_expr = pl.lit(False)
    for c in auth:
        any_expr = any_expr | _nonblank(c)
    agg.append(any_expr.sum().alias('any_auth_nb'))

    out = lf.group_by('COUNTY_NUMBER').agg(agg)
    ratios = [(pl.col(f'{c.lower()}_nb') / pl.col('voters')).alias(f'{c.lower()}_cov')
              for c in auth + (['RESIDENTIAL_CITY'] if 'RESIDENTIAL_CITY' in cols else [])]
    ratios.append((pl.col('any_auth_nb') / pl.col('voters')).alias('any_auth_cov'))
    return out.with_columns(ratios).sort('COUNTY_NUMBER').collect()


def township_postal_conflicts(lf: pl.LazyFrame) -> pl.DataFrame:
    """Precincts whose NAME is a township/village, CITY is blank, but the postal
    RESIDENTIAL_CITY carries a municipality -- the mislabel set."""
    twp = lf.filter(
        pl.col('PRECINCT_NAME').str.to_uppercase().str.contains(TWP_VILLAGE_RE)
        & ~_nonblank('CITY')
        & _nonblank('RESIDENTIAL_CITY')
    )
    return (
        twp.group_by(['COUNTY_NUMBER', 'PRECINCT_NAME'])
           .agg(
               pl.len().alias('voters'),
               pl.col('RESIDENTIAL_CITY').mode().first().alias('postal_city'),
               pl.col('TOWNSHIP').mode().first().alias('township'),
           )
           .sort(['COUNTY_NUMBER', 'voters'], descending=[False, True])
           .collect()
    )


def village_in_township_candidates(lf: pl.LazyFrame) -> pl.DataFrame:
    """KNOWN-LIMITATION flag (manual review). Precincts whose name is NOT a
    township token, but whose dominant TOWNSHIP column value is a COMPOSITE of
    two place words (e.g. Wyandot's NEVADA precinct -> TOWNSHIP='NEVADA ANTRIM':
    the incorporated Village of Nevada split across Antrim & Eden townships).

    The resolver maps these to None ('not a city') because the TOWNSHIP column is
    populated -- which UNDER-CLAIMS a real incorporated village. We deliberately
    do NOT auto-correct (the composite-township pattern is rare and hard to
    detect without false positives -- see the 2026-06 decision). Instead we
    surface candidates loudly so a human can confirm whether the village should
    roll up. Heuristic is intentionally tight (composite township starting with
    the precinct's first word, second word NOT a township token) to minimize
    noise; review every row, it is not authoritative."""
    dom = (lf.filter(_nonblank('TOWNSHIP'))
             .group_by(['COUNTY_NUMBER', 'PRECINCT_NAME', 'TOWNSHIP'])
             .agg(pl.len().alias('n'))
             .sort('n', descending=True)
             .group_by(['COUNTY_NUMBER', 'PRECINCT_NAME'])
             .agg(pl.first('TOWNSHIP').alias('township'),
                  pl.sum('n').alias('voters'))
             .collect())
    import re
    rows = []
    for r in dom.iter_rows(named=True):
        pn = (r['PRECINCT_NAME'] or '').strip().upper()
        tw = (r['township'] or '').strip().upper()
        if not pn or not tw:
            continue
        # Skip precincts already correctly handled as townships by name.
        if re.search(TWP_VILLAGE_RE, pn) or re.search(r'\sTS$', pn):
            continue
        toks = tw.split()
        first = pn.split()[0]
        # composite: 'NEVADA ANTRIM' -> starts with precinct's first word, has a
        # distinct second word, and is not spelled as a township.
        if (len(toks) >= 2 and toks[0] == first
                and 'TOWNSHIP' not in tw and 'TWP' not in tw
                and not tw.endswith('TOWNSHP')):  # common misspelling = real twp
            rows.append(r)
    return pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={'COUNTY_NUMBER': pl.Utf8, 'PRECINCT_NAME': pl.Utf8,
                'township': pl.Utf8, 'voters': pl.Int64})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parquet', type=Path, default=DEFAULT_PARQUET)
    ap.add_argument('--show', type=int, default=25,
                    help='max conflict rows to print')
    ap.add_argument('--strict', action='store_true',
                    help='exit non-zero if any name conflict exists')
    args = ap.parse_args()

    if not args.parquet.exists():
        print(f'ERROR: parquet not found: {args.parquet}', file=sys.stderr)
        return 2

    lf = pl.scan_parquet(args.parquet)
    cols = lf.collect_schema().names()
    need = {'COUNTY_NUMBER', 'PRECINCT_NAME', 'CITY', 'RESIDENTIAL_CITY',
            'TOWNSHIP'}
    missing = need - set(cols)
    if missing:
        print(f'ERROR: parquet missing required columns: {sorted(missing)}',
              file=sys.stderr)
        return 2

    def name(n: str) -> str:
        return COUNTY_NAME.get(n, n)

    print('=' * 70)
    print('JURISDICTION FIELD VALIDATION')
    print(f'  source: {args.parquet}')
    print('=' * 70)

    cov = coverage_by_county(lf)
    # The TRUE postal-last-resort set: no authoritative column covers the county.
    # (Not "CITY blank" -- a blank CITY is usually covered by TOWNSHIP/WARD.)
    postal_only = cov.filter(pl.col('any_auth_cov') < POSTAL_ONLY_CITY_COVERAGE)
    print(f'\n[1] CITY coverage: {cov.height} counties present')
    weak = cov.filter(pl.col('city_cov') < 0.50).sort('city_cov')
    print(f'    counties with < 50% authoritative CITY coverage: {weak.height}')
    print('    (low CITY is normal -- these counties encode municipality via '
          'TOWNSHIP/VILLAGE/WARD; see [2])')
    for r in weak.head(40).to_dicts():
        print(f"      {name(r['COUNTY_NUMBER']):<14} "
              f"CITY {r['city_cov']*100:5.1f}%  "
              f"RES {r.get('residential_city_cov', 0)*100:5.1f}%  "
              f"({r['voters']:,} voters)")

    print(f'\n[2] Jurisdiction-hierarchy coverage for blank-CITY counties')
    print('    For each county with < 50% CITY, the fallback columns the '
          'resolver relies on:')
    print(f"      {'county':<14} {'CITY':>6} {'VILL':>6} {'WARD':>6} "
          f"{'TWP':>6} {'ANY-AUTH':>9}")
    for r in weak.sort('any_auth_cov').head(40).to_dicts():
        print(f"      {name(r['COUNTY_NUMBER']):<14} "
              f"{r.get('city_cov', 0)*100:5.1f}% "
              f"{r.get('village_cov', 0)*100:5.1f}% "
              f"{r.get('ward_cov', 0)*100:5.1f}% "
              f"{r.get('township_cov', 0)*100:5.1f}% "
              f"{r.get('any_auth_cov', 0)*100:8.1f}%")
    print(f'\n    -> TRUE postal-last-resort counties (no authoritative column, '
          f'ANY-AUTH < {POSTAL_ONLY_CITY_COVERAGE*100:.0f}%): {postal_only.height}')
    print('       Only these legitimately fall through to RESIDENTIAL_CITY. '
          'Expected: Wyandot (88) only.')
    for r in postal_only.to_dicts():
        print(f"      {name(r['COUNTY_NUMBER']):<14} "
              f"ANY-AUTH {r['any_auth_cov']*100:4.1f}%  "
              f"RES {r.get('residential_city_cov', 0)*100:5.1f}%")

    conflicts = township_postal_conflicts(lf)
    print(f'\n[3] Township/Village precincts mislabeled via postal city: '
          f'{conflicts.height}')
    print('    (NAME is a township/village, CITY blank, postal city populated)')
    for r in conflicts.head(args.show).to_dicts():
        print(f"      {name(r['COUNTY_NUMBER']):<12} "
              f"{r['PRECINCT_NAME']:<26} postal={r['postal_city']:<16} "
              f"({r['voters']:,} voters)")
    if conflicts.height > args.show:
        print(f'      ... +{conflicts.height - args.show} more '
              f'(raise --show to see all)')

    vit = village_in_township_candidates(lf)
    print('\n' + '!' * 70)
    print(f'[4] KNOWN LIMITATION -- village-in-township (MANUAL REVIEW): '
          f'{vit.height}')
    print('!' * 70)
    print('    These precincts resolve to None ("not a city") because their')
    print('    TOWNSHIP column is populated -- but the value is a COMPOSITE place')
    print('    code (e.g. NEVADA -> "NEVADA ANTRIM"), so a real incorporated')
    print('    village may be UNDER-CLAIMED. By decision (2026-06) we do NOT auto-')
    print('    correct this; review each row and assign the village manually if')
    print('    warranted. See memory: city-resolution-village-in-township.')
    for r in vit.sort('COUNTY_NUMBER').to_dicts():
        print(f"      {name(r['COUNTY_NUMBER']):<12} "
              f"{r['PRECINCT_NAME']:<22} township={r['township']!r:<22} "
              f"({r['voters']:,} voters)  -> currently None")

    # Severity: a township/postal name conflict is HIGH unless the county is a
    # true postal-last-resort county (no authoritative column at all). Everywhere
    # else the resolver has TOWNSHIP/WARD/VILLAGE to do the right thing, so a
    # postal label there would be a genuine mislabel.
    postal_set = set(postal_only['COUNTY_NUMBER'].to_list())
    high = conflicts.filter(~pl.col('COUNTY_NUMBER').is_in(postal_set))
    print(f'\n[SUMMARY]')
    print(f'  township/postal name conflicts total:                 '
          f'{conflicts.height}')
    print(f'  HIGH-severity (county HAS authoritative columns):      '
          f'{high.height}')
    print(f'  true postal-last-resort counties (no auth col):        '
          f'{postal_only.height}  (expected: 1 = Wyandot)')
    print('  NOTE: the resolver maps these conflicts to None (= "not a city")')
    print('        via the TOWNSHIP step, so they are NOT mislabeled at runtime.')
    print('        This count tracks the postal-fallback risk surface over time.')

    if high.height and args.strict:
        print('\nFAIL: high-severity jurisdiction mislabels present.',
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
