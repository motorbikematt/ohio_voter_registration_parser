"""
precinct_party_export.py
════════════════════════
Export a multi-tab Excel workbook of voter names + addresses + all source
columns, split by partisan cohort, for a chosen county or a single precinct.

Tab layout (8-tab partisan spectrum — colours match dashboard doughnut):
  Pure_R          #ef4444   registered R, zero D primary ballots ever
  R_Crossover     #f87171   registered R, has voted both primaries (scored)
  UNC_Lifetime_R  #fca5a5   unaffiliated, all primaries were R ballots
  UNC_Mixed       #a78bfa   unaffiliated, mixed primary history (scored)
  UNC_No_History  #9ca3af   unaffiliated, no primary participation ever
  UNC_Lifetime_D  #93c5fd   unaffiliated, all primaries were D ballots
  D_Crossover     #60a5fa   registered D, has voted both primaries (scored)
  Pure_D          #3b82f6   registered D, zero R primary ballots ever
  Summary         #1e293b   row counts per tab

Cohort assignment uses classify_all_voters_primary_history() (voter_data_cleaner_v2).
Crossover and UNC_Mixed tabs include scoring columns: lean_score, confidence,
crossover_class, last_three_party, years_since_last_partisan, switch_count.
Pure and Lifetime tabs omit scoring columns (all null for those cohorts).

Output:  UNC_Exports/Workbooks/{County}_{Precinct}_voters.xlsx
                             or {County}_all_voters.xlsx

Usage:
    python precinct_party_export.py

Security: UNC_Exports/ is in .gitignore — no PII leaves that directory.
"""

import logging
import sys
import time
from pathlib import Path

import polars as pl

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
PARQUET_DIR = BASE_DIR / "source" / "parquet"
OUT_DIR     = BASE_DIR / "UNC_Exports" / "Workbooks"

# ── Import shared helpers ─────────────────────────────────────────────────────
sys.path.insert(0, str(BASE_DIR))
import voter_data_cleaner_v2 as v2

OHIO_COUNTIES  = v2.OHIO_COUNTIES
identify_cols  = v2.identify_election_cols
classify_unc   = v2.classify_unc_primary_history
classify_all   = v2.classify_all_voters_primary_history

# ── Tab definitions ───────────────────────────────────────────────────────────
# 8-tab partisan-spectrum layout based on cohort_family (universal classifier).
TABS = [
    # (tab_name,         tab_colour,  filter_col,      cohort_family value)
    ("Pure_R",         "#ef4444",   "cohort_family", "PURE_R"),
    ("R_Crossover",    "#f87171",   "cohort_family", "CROSSOVER_R"),
    ("UNC_Lifetime_R", "#fca5a5",   "cohort_family", "UNC_LIFETIME_R"),
    ("UNC_Mixed",      "#a78bfa",   "cohort_family", "UNC_MIXED"),
    ("UNC_No_History", "#9ca3af",   "cohort_family", "UNC_NO_HISTORY"),
    ("UNC_Lifetime_D", "#93c5fd",   "cohort_family", "UNC_LIFETIME_D"),
    ("D_Crossover",    "#60a5fa",   "cohort_family", "CROSSOVER_D"),
    ("Pure_D",         "#3b82f6",   "cohort_family", "PURE_D"),
]

# ── Logging ───────────────────────────────────────────────────────────────────
def _build_logger() -> logging.Logger:
    log = logging.getLogger("precinct_party_export")
    log.setLevel(logging.DEBUG)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s",
                                         datefmt="%H:%M:%S"))
        log.addHandler(h)
    return log

# ── Data loading ──────────────────────────────────────────────────────────────
def _load_county(county_num: str, logger) -> pl.DataFrame:
    """Load one county from Parquet cache."""
    part = PARQUET_DIR / f"COUNTY_NUMBER={county_num}"
    if not part.exists():
        logger.error("Parquet partition not found: %s", part)
        sys.exit(1)
    logger.info("Loading parquet partition: %s", part)
    df = pl.read_parquet(part)
    logger.info("  %s rows × %s columns loaded", f"{len(df):,}", len(df.columns))
    return df

# ── Precinct listing ──────────────────────────────────────────────────────────
def _list_precincts(df: pl.DataFrame) -> list[str]:
    return sorted(df["PRECINCT_NAME"].drop_nulls().unique().to_list())

# ── Excel writer ──────────────────────────────────────────────────────────────
def _write_workbook(
    df:           pl.DataFrame,
    primary_cols: list[str],
    out_path:     Path,
    logger,
) -> None:
    import xlsxwriter  # imported here so the rest of the script works without it

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Classifying voters with universal cohort classifier ...")
    classified = classify_all(df, primary_cols, logger)

    # Join cohort scoring columns back onto the full DataFrame.  cohort_family
    # is the primary segmentation key; lean_score / confidence / etc. are
    # appended on the right of crossover/mixed tabs only.
    score_cols = [
        "cohort", "cohort_family", "crossover_class",
        "lean_score", "confidence", "recent_5yr_lean",
        "last_three_party", "years_since_last_partisan",
        "switch_count",
        "d_primaries", "r_primaries", "x_primaries",
        "total_primaries", "partisan_primaries",
        "is_new_registrant",
    ]
    score_cols = [c for c in score_cols if c in classified.columns]
    df_enriched = df.join(
        classified.select(["SOS_VOTERID"] + score_cols),
        on="SOS_VOTERID",
        how="left",
    )

    # ── Segment frames by cohort_family ───────────────────────────────────────
    frames: dict[str, pl.DataFrame] = {}
    for tab_name, _, filter_col, cohort_value in TABS:
        frames[tab_name] = df_enriched.filter(pl.col(filter_col) == cohort_value)
        logger.info("  %-20s %s rows", tab_name, f"{len(frames[tab_name]):,}")

    # ── Open workbook ─────────────────────────────────────────────────────────
    logger.info("Writing workbook → %s", out_path)
    wb = xlsxwriter.Workbook(str(out_path), {"constant_memory": True})

    header_fmt = wb.add_format({
        "bold": True, "bg_color": "#1e293b", "font_color": "#e2e8f0",
        "border": 1, "border_color": "#334155",
        "text_wrap": False,
    })
    cell_fmt = wb.add_format({"border": 0, "text_wrap": False})
    int_fmt  = wb.add_format({"border": 0, "num_format": "#,##0"})

    def _is_numeric_col(series: pl.Series) -> bool:
        return series.dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                                 pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                                 pl.Float32, pl.Float64)

    # ── Write data tabs ───────────────────────────────────────────────────────
    # Cohorts with meaningful crossover scoring keep all scoring columns;
    # Pure_* and UNC_Lifetime_* tabs drop them (they'd be nearly all null).
    SCORING_COLS_KEEP = {"R_Crossover", "D_Crossover", "UNC_Mixed"}
    for tab_name, tab_colour, _, _ in TABS:
        frame = frames[tab_name]

        if tab_name not in SCORING_COLS_KEEP:
            drop_candidates = [
                "lean_score", "confidence", "recent_5yr_lean",
                "crossover_class", "last_three_party",
                "years_since_last_partisan", "switch_count",
            ]
            drop = [c for c in drop_candidates if c in frame.columns]
            if drop:
                frame = frame.drop(drop)

        ws = wb.add_worksheet(tab_name)
        ws.set_tab_color(tab_colour)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, 0, len(frame.columns) - 1)

        cols = frame.columns
        col_series = {c: frame[c] for c in cols}

        # Header row
        for ci, col in enumerate(cols):
            ws.write(0, ci, col, header_fmt)
            # Auto-width estimate: max of header length and first 200 values
            sample = col_series[col].head(200).cast(pl.Utf8).drop_nulls().to_list()
            max_w  = max([len(col)] + [len(str(v)) for v in sample])
            ws.set_column(ci, ci, min(max_w + 2, 40))

        # Data rows
        numeric_flags = {c: _is_numeric_col(col_series[c]) for c in cols}
        for ri, row_tuple in enumerate(frame.iter_rows(), start=1):
            for ci, (col, val) in enumerate(zip(cols, row_tuple)):
                if val is None:
                    ws.write_blank(ri, ci, None, cell_fmt)
                elif numeric_flags[col]:
                    ws.write_number(ri, ci, val, int_fmt)
                else:
                    ws.write_string(ri, ci, str(val), cell_fmt)

        logger.info("    wrote %s data rows to tab '%s'", f"{len(frame):,}", tab_name)

    # ── Summary tab ───────────────────────────────────────────────────────────
    ws_sum = wb.add_worksheet("Summary")
    ws_sum.set_tab_color("#1e293b")
    ws_sum.freeze_panes(1, 0)

    sum_hdr = wb.add_format({"bold": True, "bg_color": "#1e293b",
                              "font_color": "#e2e8f0", "border": 1})
    sum_num = wb.add_format({"num_format": "#,##0", "border": 0})

    ws_sum.write(0, 0, "Tab",         sum_hdr)
    ws_sum.write(0, 1, "Voter Count", sum_hdr)
    ws_sum.set_column(0, 0, 22)
    ws_sum.set_column(1, 1, 14)

    for ri, (tab_name, _, _, _) in enumerate(TABS, start=1):
        ws_sum.write_string(ri, 0, tab_name)
        ws_sum.write_number(ri, 1, len(frames[tab_name]), sum_num)

    total_row = len(TABS) + 1
    ws_sum.write_string(total_row, 0, "TOTAL")
    ws_sum.write_number(total_row, 1,
                         sum(len(frames[t]) for t, *_ in TABS), sum_num)

    wb.close()
    logger.info("Workbook saved → %s  (%.1f MB)",
                out_path, out_path.stat().st_size / 1_048_576)

# ── Interactive menu ──────────────────────────────────────────────────────────
def _pick_county(logger) -> tuple[str, str]:
    """Return (county_num_zero_padded, county_name)."""
    print("\n  Ohio counties (enter number 1-88):")
    for num, name in sorted(OHIO_COUNTIES.items(), key=lambda x: int(x[0])):
        print(f"    {int(num):>3}  {name}")
    while True:
        raw = input("\n  County number: ").strip()
        padded = raw.zfill(2)
        if padded in OHIO_COUNTIES:
            return padded, OHIO_COUNTIES[padded]
        print(f"  ✗ '{raw}' not recognised — try again.")

def main() -> None:
    logger = _build_logger()
    print("\n╔══════════════════════════════════════════╗")
    print("║   Ohio Voter Party Export — Excel        ║")
    print("╚══════════════════════════════════════════╝")
    print("\n  Export mode:")
    print("    1  Single precinct  →  one workbook")
    print("    2  Whole county     →  one workbook")

    while True:
        mode = input("\n  Choice [1/2]: ").strip()
        if mode in ("1", "2"):
            break
        print("  Enter 1 or 2.")

    county_num, county_name = _pick_county(logger)
    t0 = time.perf_counter()

    logger.info("Loading county %s (%s) …", county_num, county_name)
    df = _load_county(county_num, logger)
    primary_cols = [c for c in identify_cols(df) if c.startswith("PRIMARY-")]

    if mode == "1":
        precincts = _list_precincts(df)
        print(f"\n  Precincts in {county_name} ({len(precincts)} total):")
        for i, p in enumerate(precincts, 1):
            print(f"    {i:>4}  {p}")
        while True:
            raw = input("\n  Precinct number from list above: ").strip()
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(precincts):
                    precinct = precincts[idx]
                    break
            except ValueError:
                pass
            print("  Enter the number shown on the left.")

        df = df.filter(pl.col("PRECINCT_NAME") == precinct)
        logger.info("Filtered to precinct '%s': %s rows", precinct, f"{len(df):,}")

        safe_precinct = precinct.replace(" ", "_").replace("/", "-")
        out_path = OUT_DIR / f"{county_name}_{safe_precinct}_voters.xlsx"
    else:
        out_path = OUT_DIR / f"{county_name}_all_voters.xlsx"

    _write_workbook(df, primary_cols, out_path, logger)
    logger.info("Done in %.1f s", time.perf_counter() - t0)
    print(f"\n  ✓ Workbook written to:\n    {out_path}\n")

if __name__ == "__main__":
    main()
