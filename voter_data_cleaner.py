import pandas as pd
import xlsxwriter  # noqa: F401 — imported for engine availability check; used via pd.ExcelWriter
import os
import re
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

INPUT_CSV   = r"D:\vibe\election-data (1)\source\2026-04-30\voterfile.csv"
OUTPUT_XLSX = r"D:\vibe\election-data (1)\voter_analysis.xlsx"

# Participation thresholds for Voter_Frequency classification
FREQ_HIGH = 0.75   # ≥ 75% of eligible elections → Frequent
FREQ_LOW  = 0.25   # < 25% of eligible elections → Infrequent (25–74% → Moderate)

# District fields written to the District Breakdown sheet (must match CSV header exactly)
DISTRICT_FIELDS = [
    'U.S. CONGRESS',
    'STATE SENATE',
    'STATE HOUSE',
    'SCHOOL DIST',
    'CO BD OF EDUC',
]

# Party codes shown as explicit columns in cross-tabs; all others collapse to "Other"
TOP_PARTIES = ['DEM', 'REP', 'UNC']

ELECTION_TYPE_LABELS = {
    'G':  'General',
    'P':  'Primary',
    'S':  'Special',
    'PS': 'Primary/Special',
}

# Shared Excel format definitions (applied inside create_excel_workbook)
_DARK_BLUE  = '#366092'   # header bg on Voter Data sheet (original)
_MED_BLUE   = '#4472C4'   # header bg on summary sheets (original)
_TITLE_BG   = '#D9E1F2'   # light blue title-row background for section headers


# ─────────────────────────────────────────────────────────────────────────────
# Election-column helpers
# ─────────────────────────────────────────────────────────────────────────────

def identify_election_cols(df):
    """Return a chronologically sorted list of election participation columns.

    Participation columns follow the pattern YYYYMMDD(G|PS|P|S) with no _TYPE suffix.
    The alternation order (PS before P/S) is intentional to avoid partial matches.
    """
    pattern = re.compile(r'^\d{8}(G|PS|P|S)$')
    cols = [c for c in df.columns if pattern.match(c)]
    cols.sort(key=lambda c: c[:8])
    return cols


def parse_election_meta(col):
    """Parse an election column name into (date, type_code, type_label).

    Example: '20241105G' → (date(2024, 11, 5), 'G', 'General')
    Returns (None, None, None) on any parse failure.
    """
    m = re.match(r'^(\d{8})(G|PS|P|S)$', col)
    if not m:
        return None, None, None
    date_str, type_code = m.groups()
    try:
        elec_date = datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        elec_date = None
    return elec_date, type_code, ELECTION_TYPE_LABELS.get(type_code, type_code)


def voted_mask(series):
    """Return boolean Series: True where a voter participated (non-null, non-blank)."""
    return series.notna() & (series.astype(str).str.strip() != '')


# ─────────────────────────────────────────────────────────────────────────────
# Data cleaning & enrichment
# ─────────────────────────────────────────────────────────────────────────────

def clean_voter_data(df):
    """Clean and prepare voter data (unchanged from original, plus REGDATE_DT column)."""
    print("Cleaning voter data...")

    # Birth year validation
    df['BIRTHYEAR'] = pd.to_numeric(df['BIRTHYEAR'], errors='coerce')
    df = df[(df['BIRTHYEAR'] >= 1900) & (df['BIRTHYEAR'] <= 2024)]

    # Create decade grouping column (used by existing Decade Summary sheet)
    df['Decade'] = (df['BIRTHYEAR'] // 10 * 10).astype(int)

    # Clean address fields
    df['full_address'] = (
        df['STNUM'].astype(str) + " " +
        df['STDIR'].fillna('') + " " +
        df['STNAME'].astype(str) + " " +
        df['APT'].fillna('')
    ).str.strip().str.replace(r'\s+', ' ', regex=True)

    # Standardize party affiliation
    df['PARTYAFFIL'] = df['PARTYAFFIL'].fillna('Unknown').str.strip()

    # Parse registration date once; stored as Python date objects for fast comparisons
    df['REGDATE_DT'] = pd.to_datetime(
        df['REGDATE'], format='%m/%d/%Y', errors='coerce'
    ).dt.date

    return df


def add_voter_participation(df, election_cols):
    """Add per-voter participation metrics to df (modifies in place, returns df).

    New columns added:
      Elections_Eligible  — count of elections the voter was registered for
      Elections_Voted     — count of those elections where the voter cast a ballot
      Turnout_Rate        — Elections_Voted / Elections_Eligible (NaN if 0 eligible)
      Voter_Frequency     — 'Frequent (≥75%)' / 'Moderate (25–74%)' /
                            'Infrequent (<25%)' / 'No Eligible Elections'

    A voter is considered eligible for an election if their REGDATE_DT is on or
    before the election date. Empty/null participation columns mean did not vote.
    """
    print("  Computing per-voter participation metrics...")

    reg_dates = df['REGDATE_DT']

    eligible   = pd.Series(0, index=df.index, dtype='int32')
    voted_ct   = pd.Series(0, index=df.index, dtype='int32')

    for col in election_cols:
        elec_date, _, _ = parse_election_meta(col)
        if elec_date is None:
            continue
        elig = reg_dates.notna() & (reg_dates <= elec_date)
        voted = voted_mask(df[col])
        eligible  += elig.astype('int32')
        voted_ct  += (elig & voted).astype('int32')

    df['Elections_Eligible'] = eligible
    df['Elections_Voted']    = voted_ct
    df['Turnout_Rate'] = (
        voted_ct.astype('float32') / eligible.replace(0, float('nan'))
    ).round(4)

    # Vectorised frequency classification (no row-wise apply)
    rate = df['Turnout_Rate'].fillna(0.0)
    freq = pd.Series('Infrequent (<25%)', index=df.index)
    freq = freq.mask(rate >= FREQ_LOW,  'Moderate (25–74%)')
    freq = freq.mask(rate >= FREQ_HIGH, 'Frequent (≥75%)')
    freq = freq.mask(eligible == 0,     'No Eligible Elections')
    df['Voter_Frequency'] = freq

    print(f"  ✓ Participation metrics added: "
          f"{(eligible > 0).sum():,} voters had at least one eligible election")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Summary builders  (each returns DataFrames; no I/O)
# ─────────────────────────────────────────────────────────────────────────────

def build_election_participation(df, election_cols):
    """Build three DataFrames for the Participation sheet.

    Returns:
      election_df  — one row per election with eligible count, votes cast, and rate
      type_df      — aggregation by election type (General / Primary / Special / etc.)
      freq_df      — voter frequency distribution (Frequent / Moderate / Infrequent)
    """
    print("  Building election participation summary...")

    reg_dates = df['REGDATE_DT']
    rows = []
    for col in election_cols:
        elec_date, type_code, type_label = parse_election_meta(col)
        if elec_date is None:
            continue
        elig_mask  = reg_dates.notna() & (reg_dates <= elec_date)
        n_eligible = int(elig_mask.sum())
        n_voted    = int((voted_mask(df[col]) & elig_mask).sum())
        rate       = n_voted / n_eligible if n_eligible > 0 else None
        rows.append({
            'Election':  col,
            'Date':      elec_date.strftime('%Y-%m-%d'),
            'Type':      type_label,
            'Eligible':  n_eligible,
            'Voted':     n_voted,
            '_rate_raw': rate,                       # kept for type_df aggregation only
            'Rate':      f"{rate:.1%}" if rate is not None else 'N/A',
        })

    election_df = pd.DataFrame(rows)

    # Summary by election type (uses raw rate for averaging)
    type_df = (
        election_df.groupby('Type')
        .agg(
            Elections   = ('Election',  'count'),
            Avg_Eligible= ('Eligible',  'mean'),
            Avg_Voted   = ('Voted',     'mean'),
            Avg_Rate    = ('_rate_raw', 'mean'),
        )
        .round({'Avg_Eligible': 0, 'Avg_Voted': 0, 'Avg_Rate': 4})
        .reset_index()
    )
    type_df.columns = ['Type', 'Elections', 'Avg Eligible', 'Avg Voted', 'Avg Rate']
    type_df['Avg Rate'] = type_df['Avg Rate'].map(
        lambda r: f"{r:.1%}" if pd.notna(r) else 'N/A'
    )

    # Drop internal column before returning
    election_df = election_df.drop(columns=['_rate_raw'])

    # Voter frequency distribution
    order = ['Frequent (≥75%)', 'Moderate (25–74%)', 'Infrequent (<25%)', 'No Eligible Elections']
    freq_counts = (
        df['Voter_Frequency']
        .value_counts()
        .reindex(order, fill_value=0)
        .reset_index()
    )
    freq_counts.columns = ['Frequency Class', 'Voter Count']
    freq_counts['Percent'] = (
        freq_counts['Voter Count'] / len(df) * 100
    ).round(2).astype(str) + '%'

    return election_df, type_df, freq_counts


def build_district_breakdown(df, election_cols):
    """Build a per-district-field breakdown DataFrame.

    Returns:
      district_tables  — dict mapping each DISTRICT_FIELDS entry to a DataFrame
                         with columns: [district, Total Voters, Party: DEM/REP/UNC/Other,
                         Status: Active/Inactive/Other, Eligible (col), Voted (col), Rate%]
      most_recent_g    — name of the most recent General election column used for turnout,
                         or None if no General election columns exist
    """
    print("  Building district breakdowns...")

    # Most recent General election for turnout column
    g_cols = [c for c in election_cols if c.endswith('G')]
    most_recent_g = g_cols[-1] if g_cols else None

    # Vectorised party bucket
    party_raw = df['PARTYAFFIL'].astype(str).str.strip().str.upper()
    party_col = party_raw.where(party_raw.isin(TOP_PARTIES), other='Other')

    # Vectorised status bucket — 'ACTIVE VOTER' is active, 'INACTIVE ...' is inactive
    status_raw = df['VOTERSTAT'].fillna('').astype(str).str.strip().str.upper()
    status_col = pd.Series('Other', index=df.index)
    status_col = status_col.mask(status_raw.str.startswith('INACTIVE'), 'Inactive')
    status_col = status_col.mask(status_raw.str.startswith('ACTIVE'),   'Active')

    # Recent General election eligibility and vote flags
    if most_recent_g:
        g_date, _, _ = parse_election_meta(most_recent_g)
        elig_g  = (df['REGDATE_DT'].notna() & (df['REGDATE_DT'] <= g_date)).astype(int)
        voted_g = (voted_mask(df[most_recent_g]) & elig_g.astype(bool)).astype(int)
        g_elig_col  = f'Eligible ({most_recent_g})'
        g_voted_col = f'Voted ({most_recent_g})'
    else:
        elig_g  = pd.Series(0, index=df.index)
        voted_g = pd.Series(0, index=df.index)
        g_elig_col  = 'Eligible (N/A)'
        g_voted_col = 'Voted (N/A)'

    district_tables = {}
    for field in DISTRICT_FIELDS:
        if field not in df.columns:
            print(f"  ⚠ District field not found, skipping: {field}")
            continue

        dist_vals = df[field].fillna('Unknown').astype(str).str.strip()

        # Build a compact working frame to avoid copying all 110 columns
        work = pd.DataFrame({
            'district': dist_vals,
            'party':    party_col,
            'status':   status_col,
            'elig_g':   elig_g,
            'voted_g':  voted_g,
        })

        totals      = work.groupby('district').size().rename('Total Voters')
        party_ct    = work.pivot_table(
            index='district', columns='party', values='elig_g',
            aggfunc='count', fill_value=0
        )
        status_ct   = work.pivot_table(
            index='district', columns='status', values='elig_g',
            aggfunc='count', fill_value=0
        )
        g_agg       = work.groupby('district')[['elig_g', 'voted_g']].sum()

        # Ensure all expected columns exist in pivots
        for p in TOP_PARTIES + ['Other']:
            if p not in party_ct.columns:
                party_ct[p] = 0
        for s in ['Active', 'Inactive', 'Other']:
            if s not in status_ct.columns:
                status_ct[s] = 0

        party_ct  = party_ct[TOP_PARTIES + ['Other']].rename(
            columns={p: f'Party: {p}' for p in TOP_PARTIES + ['Other']}
        )
        status_ct_out = status_ct[['Active', 'Inactive', 'Other']].rename(
            columns={s: f'Status: {s}' for s in ['Active', 'Inactive', 'Other']}
        )
        g_agg = g_agg.rename(columns={'elig_g': g_elig_col, 'voted_g': g_voted_col})
        g_agg['Rate%'] = (
            g_agg[g_voted_col] / g_agg[g_elig_col].replace(0, float('nan'))
        ).round(4).map(lambda r: f"{r:.1%}" if pd.notna(r) else 'N/A')

        out = pd.concat(
            [totals, party_ct, status_ct_out, g_agg], axis=1
        ).reset_index().rename(columns={'district': field})
        out = out.sort_values('Total Voters', ascending=False).reset_index(drop=True)

        district_tables[field] = out

    return district_tables, most_recent_g


def build_party_crosstabs(df):
    """Build three party cross-tabulation DataFrames for the Party Cross-tabs sheet.

    Returns:
      by_congress  — party × U.S. Congressional district
      by_decade    — party × birth decade cohort
      by_status    — party × voter registration status
    """
    print("  Building party cross-tabs...")

    def make_crosstab(index_col, index_label):
        ct = pd.crosstab(
            df[index_col].fillna('Unknown').astype(str).str.strip(),
            df['PARTYAFFIL'].astype(str).str.strip().str.upper(),
            margins=True,
            margins_name='Total',
        )
        ct = ct.reset_index().rename(columns={'PARTYAFFIL': 'Party', index_col: index_label})
        ct.insert(0, index_label, ct.pop(index_label))
        return ct

    by_congress = make_crosstab('U.S. CONGRESS', 'Congressional District')
    by_decade   = make_crosstab('Decade',         'Birth Decade')
    by_status   = make_crosstab('VOTERSTAT',      'Voter Status')

    return by_congress, by_decade, by_status


# ─────────────────────────────────────────────────────────────────────────────
# Excel sheet writers
# ─────────────────────────────────────────────────────────────────────────────

def _write_section(writer, sheet_name, df, start_row, title,
                   hdr_fmt, title_fmt, col_widths=None):
    """Write a titled section (one title row + one DataFrame) to an Excel sheet.

    The sheet is created on the first call; subsequent calls append below.

    Args:
        writer      : active pd.ExcelWriter (xlsxwriter engine)
        sheet_name  : target worksheet name
        df          : DataFrame to write
        start_row   : 0-indexed row to write the title on (data follows at start_row+1)
        title       : section heading string
        hdr_fmt     : xlsxwriter format for the column-header row
        title_fmt   : xlsxwriter format for the section title row
        col_widths  : optional dict {col_index: width} or list of (col_index, width) tuples

    Returns:
        next_start_row (int) — first free row after the section + a 2-row gap
    """
    # Write title row first (writes nothing if title is None)
    if title:
        # If sheet doesn't exist yet, create it via a dummy write so to_excel can target it
        if sheet_name not in writer.sheets:
            df.head(0).to_excel(writer, sheet_name=sheet_name, startrow=start_row + 1,
                                index=False)
        ws = writer.sheets[sheet_name]
        ws.write(start_row, 0, title, title_fmt)

    # Write DataFrame (header=True at start_row, data below)
    df.to_excel(writer, sheet_name=sheet_name, startrow=start_row + 1, index=False)
    ws = writer.sheets[sheet_name]

    # Re-apply header format over pandas' default
    for col_num, col_name in enumerate(df.columns):
        ws.write(start_row + 1, col_num, str(col_name), hdr_fmt)

    # Optional column widths
    if col_widths:
        items = col_widths.items() if isinstance(col_widths, dict) else col_widths
        for col_idx, width in items:
            ws.set_column(col_idx, col_idx, width)

    return start_row + 1 + 1 + len(df) + 2   # title + header + data rows + blank gap


def write_participation_sheet(writer, wb, df, election_cols):
    """Write the 'Participation' sheet: three stacked sections."""
    print("  Writing Participation sheet...")
    sheet = 'Participation'

    hdr_fmt   = wb.add_format({
        'bold': True, 'font_color': '#FFFFFF', 'bg_color': _MED_BLUE,
        'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 11,
    })
    title_fmt = wb.add_format({
        'bold': True, 'font_color': '#1F3864', 'bg_color': _TITLE_BG,
        'font_name': 'Arial', 'font_size': 12,
    })

    election_df, type_df, freq_df = build_election_participation(df, election_cols)

    row = 0
    row = _write_section(writer, sheet, election_df, row,
                         'Election Participation — by Election', hdr_fmt, title_fmt,
                         col_widths={0: 16, 1: 14, 2: 18, 3: 14, 4: 10, 5: 10})

    row = _write_section(writer, sheet, type_df, row,
                         'Participation Summary — by Election Type', hdr_fmt, title_fmt,
                         col_widths={0: 20, 1: 12, 2: 16, 3: 14, 4: 12})

    _write_section(writer, sheet, freq_df, row,
                   'Voter Frequency Distribution', hdr_fmt, title_fmt,
                   col_widths={0: 30, 1: 14, 2: 12})

    writer.sheets[sheet].freeze_panes(2, 0)
    print(f"  ✓ Participation sheet: {len(election_df)} elections, "
          f"{len(type_df)} types, {len(freq_df)} frequency classes")


def write_district_sheet(writer, wb, df, election_cols):
    """Write the 'District Breakdown' sheet: one stacked section per district field."""
    print("  Writing District Breakdown sheet...")
    sheet = 'District Breakdown'

    hdr_fmt   = wb.add_format({
        'bold': True, 'font_color': '#FFFFFF', 'bg_color': _MED_BLUE,
        'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 11,
    })
    title_fmt = wb.add_format({
        'bold': True, 'font_color': '#1F3864', 'bg_color': _TITLE_BG,
        'font_name': 'Arial', 'font_size': 12,
    })

    district_tables, most_recent_g = build_district_breakdown(df, election_cols)

    row = 0
    for field, tbl in district_tables.items():
        title = f'District Breakdown — {field}'
        row = _write_section(writer, sheet, tbl, row, title, hdr_fmt, title_fmt)

    # Auto-width the first column of each section is handled by the dynamic col_widths
    # below; set a sensible default for all columns
    ws = writer.sheets.get(sheet)
    if ws:
        ws.set_column(0, 0, 35)
        ws.set_column(1, 20, 16)

    print(f"  ✓ District Breakdown sheet: {len(district_tables)} district types"
          + (f", most recent General: {most_recent_g}" if most_recent_g else ""))


def write_party_crosstabs_sheet(writer, wb, df):
    """Write the 'Party Cross-tabs' sheet: three stacked pivot tables."""
    print("  Writing Party Cross-tabs sheet...")
    sheet = 'Party Cross-tabs'

    hdr_fmt   = wb.add_format({
        'bold': True, 'font_color': '#FFFFFF', 'bg_color': _MED_BLUE,
        'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 11,
    })
    title_fmt = wb.add_format({
        'bold': True, 'font_color': '#1F3864', 'bg_color': _TITLE_BG,
        'font_name': 'Arial', 'font_size': 12,
    })

    by_congress, by_decade, by_status = build_party_crosstabs(df)

    row = 0
    row = _write_section(writer, sheet, by_congress, row,
                         'Party Affiliation × Congressional District',
                         hdr_fmt, title_fmt, col_widths={0: 35})

    row = _write_section(writer, sheet, by_decade, row,
                         'Party Affiliation × Birth Decade',
                         hdr_fmt, title_fmt, col_widths={0: 16})

    _write_section(writer, sheet, by_status, row,
                   'Party Affiliation × Voter Status',
                   hdr_fmt, title_fmt, col_widths={0: 25})

    ws = writer.sheets.get(sheet)
    if ws:
        ws.set_column(1, 30, 12)   # all party-code columns

    print(f"  ✓ Party Cross-tabs sheet: 3 pivot tables")


# ─────────────────────────────────────────────────────────────────────────────
# Workbook assembly
# ─────────────────────────────────────────────────────────────────────────────

def create_excel_workbook(df, election_cols, output_path):
    """Create XLSX with all sheets using xlsxwriter engine (fast path)."""
    print(f"Creating workbook: {output_path}")

    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        wb = writer.book

        # ── Sheet 1: Voter Data ───────────────────────────────────────────────
        df.to_excel(writer, sheet_name='Voter Data', index=False)
        ws_data = writer.sheets['Voter Data']

        hdr_fmt = wb.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': _DARK_BLUE,
            'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 11,
        })
        for col_num, col_name in enumerate(df.columns):
            ws_data.write(0, col_num, col_name, hdr_fmt)

        ws_data.freeze_panes(1, 0)
        for col_num, col_name in enumerate(df.columns):
            sample_width = min(max(len(str(col_name)), 8), 30)
            ws_data.set_column(col_num, col_num, sample_width)

        # ── Sheet 2: Decade Summary ───────────────────────────────────────────
        decade_summary = (
            df.groupby('Decade')
              .size()
              .reset_index(name='Voter Count')
              .sort_values('Decade')
        )
        decade_summary.to_excel(writer, sheet_name='Decade Summary', index=False)

        ws_sum = writer.sheets['Decade Summary']
        sum_hdr_fmt = wb.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': _MED_BLUE,
            'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 11,
        })
        for col_num, col_name in enumerate(decade_summary.columns):
            ws_sum.write(0, col_num, col_name, sum_hdr_fmt)
        ws_sum.set_column(0, 0, 15)
        ws_sum.set_column(1, 1, 15)

        chart = wb.add_chart({'type': 'column'})
        n = len(decade_summary)
        chart.add_series({
            'name':       'Voter Count',
            'categories': ['Decade Summary', 1, 0, n, 0],
            'values':     ['Decade Summary', 1, 1, n, 1],
            'fill':       {'color': _MED_BLUE},
        })
        chart.set_title({'name': 'Voters by Birth Decade'})
        chart.set_x_axis({'name': 'Birth Decade'})
        chart.set_y_axis({'name': 'Voter Count', 'num_format': '#,##0'})
        chart.set_size({'width': 480, 'height': 300})
        ws_sum.insert_chart('D2', chart)

        # ── Sheet 3: Participation ────────────────────────────────────────────
        write_participation_sheet(writer, wb, df, election_cols)

        # ── Sheet 4: District Breakdown ───────────────────────────────────────
        write_district_sheet(writer, wb, df, election_cols)

        # ── Sheet 5: Party Cross-tabs ─────────────────────────────────────────
        write_party_crosstabs_sheet(writer, wb, df)

    print(f"\n✓ Workbook saved: {output_path}")
    print(f"  Sheet 'Voter Data':        {len(df):,} records, {len(df.columns)} columns")
    print(f"  Sheet 'Decade Summary':    {len(decade_summary)} cohorts + bar chart")
    print(f"  Sheet 'Participation':     election-level rates, type summary, frequency dist")
    print(f"  Sheet 'District Breakdown': {len(DISTRICT_FIELDS)} district types")
    print(f"  Sheet 'Party Cross-tabs':  3 pivot tables (Congress, Decade, Status)")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("VOTER DATA CLEANING & XLSX EXPORT")
    print("=" * 60)

    if not os.path.exists(INPUT_CSV):
        print(f"✗ Error: Input file not found: {INPUT_CSV}")
        return

    print(f"Loading: {INPUT_CSV}")
    try:
        df = pd.read_csv(INPUT_CSV, low_memory=False)
        print(f"✓ Loaded {len(df):,} rows, {len(df.columns)} columns")
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return

    try:
        df = clean_voter_data(df)
        print(f"✓ Cleaned: {len(df):,} valid voter records")
    except Exception as e:
        print(f"✗ Error cleaning data: {e}")
        return

    election_cols = identify_election_cols(df)
    print(f"✓ Detected {len(election_cols)} election participation columns "
          f"({election_cols[0]} → {election_cols[-1]})")

    try:
        df = add_voter_participation(df, election_cols)
    except Exception as e:
        print(f"✗ Error computing participation metrics: {e}")
        return

    try:
        create_excel_workbook(df, election_cols, OUTPUT_XLSX)
        print("\n" + "=" * 60)
        print("SUCCESS")
        print("=" * 60)
    except Exception as e:
        print(f"✗ Error creating workbook: {e}")
        return


if __name__ == "__main__":
    main()
