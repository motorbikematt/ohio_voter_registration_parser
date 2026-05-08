"""
voter_lookup.py
═══════════════
Interactive voter name lookup across all four Ohio SWVF flat files.

Searches FIRST_NAME and/or LAST_NAME (case-insensitive, partial match supported).
Reports: county, full name, address, party affiliation, voter status.

Usage
─────
    python voter_lookup.py
    python voter_lookup.py --first "Jane"
    python voter_lookup.py --last "Smith"
    python voter_lookup.py --first "Jane" --last "Smith"
    python voter_lookup.py --first "Jane" --last "Smith" --exact

Options
───────
    --first     First name to search (partial match by default)
    --last      Last name to search (partial match by default)
    --exact     Require exact matches (case-insensitive) instead of contains
    --source    Path to the folder containing SWVF_*.txt files
                Defaults to: D:/vibe/election-data (1)/source/State Voter Files
    --limit     Max results to display (default: 50)

If no CLI args are given, the script prompts interactively.
"""

import argparse
import sys
from pathlib import Path

import polars as pl

# ─────────────────────────────────────────────────────────────────────────────
# County number → name map (Ohio, 1–88)
# ─────────────────────────────────────────────────────────────────────────────

COUNTY_NAMES: dict[str, str] = {
    '01': 'Adams',        '02': 'Allen',        '03': 'Ashland',
    '04': 'Ashtabula',    '05': 'Athens',       '06': 'Auglaize',
    '07': 'Belmont',      '08': 'Brown',        '09': 'Butler',
    '10': 'Carroll',      '11': 'Champaign',    '12': 'Clark',
    '13': 'Clermont',     '14': 'Clinton',      '15': 'Columbiana',
    '16': 'Coshocton',    '17': 'Crawford',     '18': 'Cuyahoga',
    '19': 'Darke',        '20': 'Defiance',     '21': 'Delaware',
    '22': 'Erie',         '23': 'Fairfield',    '24': 'Fayette',
    '25': 'Franklin',     '26': 'Fulton',       '27': 'Gallia',
    '28': 'Geauga',       '29': 'Greene',       '30': 'Guernsey',
    '31': 'Hamilton',     '32': 'Hancock',      '33': 'Hardin',
    '34': 'Harrison',     '35': 'Henry',        '36': 'Highland',
    '37': 'Hocking',      '38': 'Holmes',       '39': 'Huron',
    '40': 'Jackson',      '41': 'Jefferson',    '42': 'Knox',
    '43': 'Lake',         '44': 'Lawrence',     '45': 'Licking',
    '46': 'Logan',        '47': 'Lorain',       '48': 'Lucas',
    '49': 'Madison',      '50': 'Mahoning',     '51': 'Marion',
    '52': 'Medina',       '53': 'Meigs',        '54': 'Mercer',
    '55': 'Miami',        '56': 'Monroe',       '57': 'Montgomery',
    '58': 'Morgan',       '59': 'Morrow',       '60': 'Muskingum',
    '61': 'Noble',        '62': 'Ottawa',       '63': 'Paulding',
    '64': 'Perry',        '65': 'Pickaway',     '66': 'Pike',
    '67': 'Portage',      '68': 'Preble',       '69': 'Putnam',
    '70': 'Richland',     '71': 'Ross',         '72': 'Sandusky',
    '73': 'Scioto',       '74': 'Seneca',       '75': 'Shelby',
    '76': 'Stark',        '77': 'Summit',       '78': 'Trumbull',
    '79': 'Tuscarawas',   '80': 'Union',        '81': 'Van Wert',
    '82': 'Vinton',       '83': 'Warren',       '84': 'Washington',
    '85': 'Wayne',        '86': 'Williams',     '87': 'Wood',
    '88': 'Wyandot',
}

PARTY_LABELS: dict[str, str] = {
    'R': 'Republican',
    'D': 'Democrat',
    '':  'Unaffiliated',
}

DEFAULT_SOURCE = Path('D:/vibe/election-data (1)/source/State Voter Files')

SWVF_FILES = [
    'SWVF_1_22.txt',
    'SWVF_23_44.txt',
    'SWVF_45_66.txt',
    'SWVF_67_88.txt',
]

OUTPUT_COLS = [
    'SOS_VOTERID',
    'COUNTY_NUMBER',
    'LAST_NAME',
    'FIRST_NAME',
    'MIDDLE_NAME',
    'SUFFIX',
    'DATE_OF_BIRTH',
    'REGISTRATION_DATE',
    'VOTER_STATUS',
    'PARTY_AFFILIATION',
    'RESIDENTIAL_ADDRESS1',
    'RESIDENTIAL_SECONDARY_ADDR',
    'RESIDENTIAL_CITY',
    'RESIDENTIAL_STATE',
    'RESIDENTIAL_ZIP',
    'PRECINCT_NAME',
]


# ─────────────────────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────────────────────

def build_filter(first: str, last: str, exact: bool) -> pl.Expr:
    """Construct a Polars filter expression for first/last name search."""
    exprs: list[pl.Expr] = []

    if first:
        f = first.upper()
        if exact:
            exprs.append(pl.col('FIRST_NAME').str.strip_chars().str.to_uppercase() == f)
        else:
            exprs.append(pl.col('FIRST_NAME').str.strip_chars().str.to_uppercase().str.contains(f))

    if last:
        l = last.upper()
        if exact:
            exprs.append(pl.col('LAST_NAME').str.strip_chars().str.to_uppercase() == l)
        else:
            exprs.append(pl.col('LAST_NAME').str.strip_chars().str.to_uppercase().str.contains(l))

    if not exprs:
        raise ValueError('At least one of --first or --last must be provided.')

    # All conditions must match (AND logic)
    result = exprs[0]
    for e in exprs[1:]:
        result = result & e
    return result


def search(source_dir: Path, first: str, last: str,
           exact: bool, limit: int) -> pl.DataFrame:
    """Scan all four SWVF files and return matching rows."""
    filt = build_filter(first, last, exact)
    frames: list[pl.LazyFrame] = []

    for fname in SWVF_FILES:
        path = source_dir / fname
        if not path.exists():
            print(f'  [WARN] Not found, skipping: {path}')
            continue

        lf = pl.scan_csv(
            path,
            separator=',',
            quote_char='"',
            infer_schema=False,
            encoding='utf8-lossy',
            ignore_errors=True,
        ).filter(filt)

        frames.append(lf)

    if not frames:
        print('ERROR: No SWVF source files found. Check --source path.')
        sys.exit(1)

    combined = pl.concat(frames).collect()

    # Select only the display columns that exist in the file
    keep = [c for c in OUTPUT_COLS if c in combined.columns]
    result = combined.select(keep)

    if limit > 0:
        result = result.head(limit)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────────────────────────────────────

def display(df: pl.DataFrame, limit: int) -> None:
    if df.is_empty():
        print('\n  No matching voters found.\n')
        return

    total = len(df)
    shown = min(total, limit) if limit > 0 else total
    print(f'\n  Found {total:,} match(es){f" — showing first {limit}" if limit > 0 and total > limit else ""}.\n')
    print('─' * 72)

    for row in df.iter_rows(named=True):
        county_num  = (row.get('COUNTY_NUMBER') or '').strip().zfill(2)
        county_name = COUNTY_NAMES.get(county_num, f'County {county_num}')

        first  = (row.get('FIRST_NAME')   or '').strip()
        middle = (row.get('MIDDLE_NAME')  or '').strip()
        last   = (row.get('LAST_NAME')    or '').strip()
        suffix = (row.get('SUFFIX')       or '').strip()
        name_parts = [p for p in [first, middle, last, suffix] if p]
        full_name  = ' '.join(name_parts)

        addr1  = (row.get('RESIDENTIAL_ADDRESS1')      or '').strip()
        addr2  = (row.get('RESIDENTIAL_SECONDARY_ADDR') or '').strip()
        city   = (row.get('RESIDENTIAL_CITY')          or '').strip()
        state  = (row.get('RESIDENTIAL_STATE')         or '').strip()
        zip_   = (row.get('RESIDENTIAL_ZIP')           or '').strip()
        addr_line = addr1
        if addr2:
            addr_line += f', {addr2}'
        city_line = ', '.join(p for p in [city, state, zip_] if p)

        party_raw   = (row.get('PARTY_AFFILIATION') or '').strip()
        party_label = PARTY_LABELS.get(party_raw, party_raw or 'Unaffiliated')
        status      = (row.get('VOTER_STATUS') or '').strip()
        precinct    = (row.get('PRECINCT_NAME') or '').strip()
        dob         = (row.get('DATE_OF_BIRTH') or '').strip()
        reg_date    = (row.get('REGISTRATION_DATE') or '').strip()
        sos_id      = (row.get('SOS_VOTERID') or '').strip()

        print(f'  Name       : {full_name}')
        print(f'  County     : {county_name} ({county_num})')
        print(f'  Address    : {addr_line}')
        if city_line:
            print(f'               {city_line}')
        if precinct:
            print(f'  Precinct   : {precinct}')
        print(f'  Party      : {party_label}')
        print(f'  Status     : {status}')
        print(f'  DOB        : {dob}')
        print(f'  Registered : {reg_date}')
        print(f'  SOS ID     : {sos_id}')
        print('─' * 72)

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Search Ohio voter registration records by name.'
    )
    parser.add_argument('--first',  default='', help='First name (partial match by default)')
    parser.add_argument('--last',   default='', help='Last name (partial match by default)')
    parser.add_argument('--exact',  action='store_true', help='Require exact name match')
    parser.add_argument('--source', default=str(DEFAULT_SOURCE),
                        help='Path to folder containing SWVF_*.txt files')
    parser.add_argument('--limit',  type=int, default=50,
                        help='Max results to display (0 = unlimited, default 50)')
    return parser.parse_args()


def prompt_interactive() -> tuple[str, str, bool]:
    print('\n  Ohio Voter Lookup')
    print('  ─────────────────')
    first = input('  First name (leave blank to skip): ').strip()
    last  = input('  Last name  (leave blank to skip): ').strip()
    if not first and not last:
        print('  ERROR: Enter at least a first or last name.')
        sys.exit(1)
    exact_input = input('  Exact match? [y/N]: ').strip().lower()
    exact = exact_input in ('y', 'yes')
    return first, last, exact


def main() -> None:
    args = parse_args()

    # If no name args given, drop into interactive mode
    if not args.first and not args.last:
        first, last, exact = prompt_interactive()
    else:
        first = args.first
        last  = args.last
        exact = args.exact

    source_dir = Path(args.source)
    if not source_dir.exists():
        print(f'ERROR: Source directory not found: {source_dir}')
        sys.exit(1)

    match_type = 'exact' if exact else 'partial'
    terms = ' + '.join(p for p in [f'first="{first}"' if first else '',
                                    f'last="{last}"' if last else ''] if p)
    print(f'\n  Searching ({match_type}): {terms}')
    print(f'  Source: {source_dir}')
    print('  Scanning all 4 SWVF files — this may take 30–60 seconds ...\n')

    results = search(source_dir, first, last, exact, args.limit)
    display(results, args.limit)


if __name__ == '__main__':
    main()
