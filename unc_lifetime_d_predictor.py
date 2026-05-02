import pandas as pd
import xlsxwriter
import os

INPUT_CSV  = r"D:\vibe\election-data (1)\source\2026-04-30\voterfile.csv"
OUTPUT_XLSX = r"D:\vibe\election-data (1)\unc_party_patterns_2026.xlsx"

# ── 1. Load ──────────────────────────────────────────────────────────────────
print("Loading voter file...")
df = pd.read_csv(INPUT_CSV, low_memory=False)
print(f"  {len(df):,} total voters")

# ── 2. Identify primary ballot columns ───────────────────────────────────────
# Columns: YYYYMMDDP or YYYYMMDDPS  (not _TYPE, not G-only, not bare S)
primary_cols = [
    c for c in df.columns
    if c[0].isdigit()
    and not c.endswith('_TYPE')
    and not (c.endswith('G') and not 'P' in c)   # exclude pure generals
    and not (c[-1] == 'S' and 'P' not in c)       # exclude pure specials
    and 'P' in c                                   # must have P somewhere
]
print(f"  Primary ballot columns found: {len(primary_cols)}")
print(f"  Columns: {primary_cols}")

# ── 3. Isolate current UNC voters ────────────────────────────────────────────
unc = df[df['PARTYAFFIL'].str.upper() == 'UNC'].copy()
print(f"\n  UNC voters: {len(unc):,}")

# ── 4. Score each UNC voter's primary history ─────────────────────────────────
def classify(row):
    votes = [str(row[c]).strip().upper() for c in primary_cols if pd.notna(row[c]) and str(row[c]).strip() not in ('', 'NAN')]
    if not votes:
        return 'NO_HISTORY', 0, 0, 0, 0
    d_votes = sum(1 for v in votes if v == 'D')
    r_votes = sum(1 for v in votes if v == 'R')
    x_votes = sum(1 for v in votes if v == 'X')
    o_votes = len(votes) - d_votes - r_votes - x_votes  # G, etc.
    if d_votes > 0 and r_votes == 0 and x_votes == 0 and o_votes == 0:
        label = 'LIFETIME_D'
    elif r_votes > 0 and d_votes == 0 and x_votes == 0 and o_votes == 0:
        label = 'LIFETIME_R'
    elif d_votes > 0 and r_votes > 0:
        label = 'MIXED_D_R'
    elif d_votes > 0 and (x_votes > 0 or o_votes > 0):
        label = 'MIXED_D_OTHER'
    elif r_votes > 0 and (x_votes > 0 or o_votes > 0):
        label = 'MIXED_R_OTHER'
    else:
        label = 'OTHER'   # X-only, G-only, or unrecognized
    return label, d_votes, r_votes, x_votes, o_votes

print("\nClassifying UNC primary histories (this may take ~30s)...")
results = unc[primary_cols + ['PARTYAFFIL']].apply(
    lambda row: pd.Series(classify(row),
                          index=['classification', 'd_votes', 'r_votes', 'x_votes', 'o_votes']),
    axis=1
)
unc = unc.copy()
unc['classification'] = results['classification']
unc['d_votes']        = results['d_votes']
unc['r_votes']        = results['r_votes']
unc['x_votes']        = results['x_votes']
unc['o_votes']        = results['o_votes']
unc['total_primaries']= unc[['d_votes','r_votes','x_votes','o_votes']].sum(axis=1).astype(int)

# ── 5. Summary ────────────────────────────────────────────────────────────────
summary = unc['classification'].value_counts()
print("\nUNC Classification Summary:")
for label, count in summary.items():
    print(f"  {label:<20} {count:>7,}")

# ── 6. Build per-classification voter lists ───────────────────────────────────
id_cols = [
    'LASTN', 'FIRSTN', 'MIDDLEN', 'SUFFIXN',
    'STNUM', 'STDIR', 'STNAME', 'APT', 'CITY', 'ZIP',
    'BIRTHYEAR', 'REGDATE', 'LASTVOTE', 'SOSIDNUM',
    'U.S. CONGRESS', 'STATE SENATE', 'STATE HOUSE',
    'PRECNAME', 'PRSID',
]
stat_cols  = ['classification', 'd_votes', 'r_votes', 'x_votes', 'o_votes', 'total_primaries']
history_cols = primary_cols
export_cols = [c for c in id_cols + stat_cols + history_cols if c in unc.columns]

# Ordered sheet definitions: (classification label, sheet name, header colour)
SHEET_DEFS = [
    ('LIFETIME_D',     'Lifetime D',      '#1F497D'),
    ('LIFETIME_R',     'Lifetime R',      '#C0392B'),
    ('MIXED_D_R',      'Mixed D-R',       '#7D3C98'),
    ('MIXED_D_OTHER',  'Mixed D-Other',   '#1A6B4A'),
    ('MIXED_R_OTHER',  'Mixed R-Other',   '#873600'),
    ('OTHER',          'Other',           '#555555'),
    ('NO_HISTORY',     'No History',      '#888888'),
]

subsets = {}
for label, sheet_name, _ in SHEET_DEFS:
    sub = unc[unc['classification'] == label][export_cols].copy()
    if label != 'NO_HISTORY':
        sub = sub.sort_values('total_primaries', ascending=False)
    subsets[label] = (sheet_name, sub)
    print(f"  {sheet_name:<22} {len(sub):>7,} voters")

# ── 7. Write XLSX ─────────────────────────────────────────────────────────────
print(f"\nWriting: {OUTPUT_XLSX}")

with pd.ExcelWriter(OUTPUT_XLSX, engine='xlsxwriter') as writer:
    wb = writer.book

    def write_sheet(df, sheet_name, hex_color):
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        hdr_fmt = wb.add_format({
            'bold': True, 'bg_color': hex_color, 'font_color': '#FFFFFF',
            'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial'
        })
        for ci, col in enumerate(df.columns):
            ws.write(0, ci, col, hdr_fmt)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, 0, len(df.columns) - 1)
        ws.set_column(0, len(df.columns) - 1, 14)

    # One sheet per classification
    for label, sheet_name, color in SHEET_DEFS:
        _, sub = subsets[label]
        write_sheet(sub, sheet_name, color)
        print(f"  Wrote '{sheet_name}': {len(sub):,} rows")

    # Summary sheet with chart
    summary_df = summary.reset_index()
    summary_df.columns = ['Classification', 'Count']
    summary_df['% of UNC'] = (summary_df['Count'] / len(unc) * 100).round(1)

    # Attach display label for chart
    label_map = {label: name for label, name, _ in SHEET_DEFS}
    summary_df['Label'] = summary_df['Classification'].map(label_map).fillna(summary_df['Classification'])
    summary_df = summary_df[['Label', 'Classification', 'Count', '% of UNC']]

    summary_df.to_excel(writer, sheet_name='Summary', index=False)
    ws_sum = writer.sheets['Summary']
    sh_fmt = wb.add_format({'bold': True, 'bg_color': '#2C3E50', 'font_color': '#FFFFFF',
                            'align': 'center', 'font_name': 'Arial'})
    for ci, col in enumerate(summary_df.columns):
        ws_sum.write(0, ci, col, sh_fmt)
    ws_sum.set_column(0, 0, 20)
    ws_sum.set_column(1, 1, 18)
    ws_sum.set_column(2, 2, 12)
    ws_sum.set_column(3, 3, 12)

    # Stacked/colour-coded bar chart
    chart = wb.add_chart({'type': 'column'})
    n = len(summary_df)
    chart.add_series({
        'name':       'Voter Count',
        'categories': ['Summary', 1, 0, n, 0],
        'values':     ['Summary', 1, 2, n, 2],
        'fill':       {'color': '#4472C4'},
        'data_labels': {'value': True, 'num_format': '#,##0'},
    })
    chart.set_title({'name': 'UNC Voters by Lifetime Primary Pattern'})
    chart.set_x_axis({'name': 'Pattern'})
    chart.set_y_axis({'name': 'Voter Count', 'num_format': '#,##0'})
    chart.set_size({'width': 560, 'height': 340})
    chart.set_legend({'none': True})
    ws_sum.insert_chart('F2', chart)
    print(f"  Wrote 'Summary' with chart")

print("\n" + "=" * 60)
print("DONE")
print(f"  Output: {OUTPUT_XLSX}")
lifetime_d_count = len(subsets['LIFETIME_D'][1])
print(f"  'Lifetime D' sheet: {lifetime_d_count:,} voters — primary 2026 target list")
print("=" * 60)
