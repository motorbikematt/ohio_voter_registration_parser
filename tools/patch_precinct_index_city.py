#!/usr/bin/env python3
"""
Patch all *_precinct_index.json files to add a 'city' field per precinct.

The city field is derived from the dominant CITY column value in the SWVF
parquet data for each precinct. CITY values are normalized (strip ' CITY',
' VILLAGE', etc. suffixes) to match existing city_summary display names.

Precincts in blank-CITY counties get city: null.

Run from the project root: python tools/patch_precinct_index_city.py
"""
import json
import re
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import voter_data_cleaner_v2 as _v2

ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'docs' / 'data'
PAR_DIR  = ROOT / 'source' / 'parquet'

_SUFFIX_RE = re.compile(r'\s+(?:CITY|VILLAGE|CITY CORP|CORP)$', re.IGNORECASE)

def normalize_city(name: str) -> str:
    return _SUFFIX_RE.sub('', name.strip()).strip() if name else ''

# Build slug → county_number from OHIO_COUNTIES  {'01': 'Adams', ...}
SLUG_TO_NUM = {
    name.lower().replace(' ', '_'): num
    for num, name in _v2.OHIO_COUNTIES.items()
}

def dominant_city_per_precinct(county_num: str) -> dict:
    par_path = PAR_DIR / f'COUNTY_NUMBER={county_num}'
    if not par_path.exists():
        return {}
    df = pl.read_parquet(par_path, columns=['PRECINCT_NAME', 'CITY'])
    populated = df.filter(
        pl.col('CITY').is_not_null() & pl.col('CITY').str.len_chars().gt(0)
    )
    if populated.is_empty():
        return {}
    dominant = (
        populated
        .group_by(['PRECINCT_NAME', 'CITY'])
        .agg(pl.len().alias('n'))
        .sort(['PRECINCT_NAME', 'n'], descending=[False, True])
        .group_by('PRECINCT_NAME')
        .first()
    )
    return {row['PRECINCT_NAME']: normalize_city(row['CITY'])
            for row in dominant.iter_rows(named=True)}

def patch_index(index_path: Path, city_map: dict) -> int:
    data = json.loads(index_path.read_text(encoding='utf-8'))
    patched = 0
    for entry in data.get('precincts', []):
        city = city_map.get(entry.get('name', ''))
        entry['city'] = city or None
        if city:
            patched += 1
    index_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return patched

def main():
    index_files = sorted(DATA_DIR.glob('*_precinct_index.json'))
    print(f'Found {len(index_files)} precinct index files.')
    total_patched = 0
    missing = []
    for idx_path in index_files:
        slug = idx_path.name.replace('_precinct_index.json', '')
        county_num = SLUG_TO_NUM.get(slug)
        if not county_num:
            missing.append(slug)
            continue
        city_map = dominant_city_per_precinct(county_num)
        n = patch_index(idx_path, city_map)
        total_patched += n
        status = f'{n} precincts with city' if city_map else 'blank-CITY county (city: null)'
        print(f'  {slug} (#{county_num}): {status}')
    if missing:
        print(f'\n  [warn] No county number for: {missing}')
    print(f'\nDone. {total_patched} precincts patched.')

if __name__ == '__main__':
    main()
