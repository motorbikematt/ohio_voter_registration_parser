"""
mixed_lean_predictor.py
=======================
Prototype lean predictor for the MIXED unaffiliated cohort.

Reads montgomery_MIXED_targets.csv and computes, per voter, a recency-weighted
partisan lean score using only fields available in the SWVF. Outputs a scored
CSV plus a summary that buckets voters into LEAN_D, LEAN_R, or TRUE_MIXED.

Tunables are grouped under CONFIG. Everything else is vectorized in Polars.

Method:
  1. Parse PRIMARY-* column headers into dates.
  2. Per-election weight: exp(-DECAY_LAMBDA * years_since_election),
     optionally boosted in presidential primary years.
  3. Ballot codes -> signed values: D -> +1, R -> -1, X / minor / blank -> 0.
  4. lean_score = sum(weight_i * value_i) / sum(weight_i over participated_i)
  5. Auxiliary features: last_three_party, switch_count,
     years_since_last_partisan, recent_5yr_lean, partisan_primary_count.
  6. Classify with thresholds. LOCKED_* override fires when last three
     partisan ballots agree AND most recent partisan ballot is fresh.
"""

from __future__ import annotations

import math
import os
import re
from datetime import date
from pathlib import Path

import polars as pl

# --- CONFIG ---------------------------------------------------------------
INPUT_CSV = Path(os.environ.get(
    "MIXED_INPUT_CSV",
    r"D:\vibe\election-data (1)\UNC_Exports\Mixed\montgomery_MIXED_targets.csv",
))
OUTPUT_CSV = Path(os.environ.get(
    "MIXED_OUTPUT_CSV",
    r"D:\vibe\election-data (1)\UNC_Exports\Mixed\montgomery_MIXED_scored.csv",
))
SUMMARY_CSV = Path(os.environ.get(
    "MIXED_SUMMARY_CSV",
    r"D:\vibe\election-data (1)\UNC_Exports\Mixed\montgomery_MIXED_summary.csv",
))

AS_OF_DATE: date = date(2026, 5, 5)

# Higher = recent ballots dominate harder.
#   0.10 -> half-life ~6.9y
#   0.15 -> half-life ~4.6y  (default)
#   0.25 -> half-life ~2.8y
#   0.40 -> half-life ~1.7y
DECAY_LAMBDA: float = 0.15

# Multiplier on the weight of March-cycle presidential-primary years.
PRESIDENTIAL_PRIMARY_BOOST: float = 1.25

# Thresholds on lean_score in [-1, +1].
LEAN_THRESHOLD: float = 0.20
LOCKED_THRESHOLD: float = 0.40
RECENCY_LOCK_YEARS: float = 6.0

# --- COLUMN PARSING -------------------------------------------------------
PRIMARY_COL_RE = re.compile(r"^PRIMARY-(\d{2})/(\d{2})/(\d{4})$")


def parse_primary_date(col_name):
    m = PRIMARY_COL_RE.match(col_name)
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


def is_presidential_primary(d):
    return d.month == 3 and d.year % 4 == 0


# --- LEAN COMPUTATION -----------------------------------------------------
def _classify_last_three(values):
    if not values:
        return "NONE"
    vs = list(values)
    if all(v == 1 for v in vs):
        return "DDD" if len(vs) >= 3 else ("DD" if len(vs) == 2 else "D")
    if all(v == -1 for v in vs):
        return "RRR" if len(vs) >= 3 else ("RR" if len(vs) == 2 else "R")
    return "MIX"


def build_score_expressions(primary_cols):
    weighted_terms = []
    weight_terms = []
    recent_weighted_terms = []
    recent_weight_terms = []
    partisan_count_terms = []
    partisan_marker_cols = []

    chrono = sorted(primary_cols, key=lambda x: x[1])

    for col, d in chrono:
        years_since = (AS_OF_DATE - d).days / 365.25
        if years_since < 0:
            continue
        base_weight = math.exp(-DECAY_LAMBDA * years_since)
        if is_presidential_primary(d):
            base_weight *= PRESIDENTIAL_PRIMARY_BOOST

        val = (
            pl.when(pl.col(col) == "D").then(1)
              .when(pl.col(col) == "R").then(-1)
              .otherwise(0)
        )
        partisan = (
            pl.when((pl.col(col) == "D") | (pl.col(col) == "R")).then(1)
              .otherwise(0)
        )

        weighted_terms.append(val * base_weight)
        weight_terms.append(partisan * base_weight)
        partisan_count_terms.append(partisan)

        if years_since <= 5.0:
            recent_weighted_terms.append(val * base_weight)
            recent_weight_terms.append(partisan * base_weight)

        partisan_marker_cols.append((val, d))

    weighted_sum = pl.sum_horizontal(weighted_terms) if weighted_terms else pl.lit(0.0)
    weight_sum = pl.sum_horizontal(weight_terms) if weight_terms else pl.lit(0.0)
    lean_score = (
        pl.when(weight_sum > 0).then(weighted_sum / weight_sum).otherwise(0.0)
    )

    rw_sum = pl.sum_horizontal(recent_weighted_terms) if recent_weighted_terms else pl.lit(0.0)
    rwt_sum = pl.sum_horizontal(recent_weight_terms) if recent_weight_terms else pl.lit(0.0)
    recent_5yr_lean = (
        pl.when(rwt_sum > 0).then(rw_sum / rwt_sum).otherwise(0.0)
    )

    partisan_primary_count = (
        pl.sum_horizontal(partisan_count_terms) if partisan_count_terms else pl.lit(0)
    )

    switch_terms = []
    for i in range(1, len(partisan_marker_cols)):
        prev_val, _ = partisan_marker_cols[i - 1]
        curr_val, _ = partisan_marker_cols[i]
        switch_terms.append(
            pl.when((prev_val != 0) & (curr_val != 0) & (prev_val != curr_val))
              .then(1).otherwise(0)
        )
    switch_count = pl.sum_horizontal(switch_terms) if switch_terms else pl.lit(0)

    if partisan_marker_cols:
        newest_first = list(reversed(partisan_marker_cols))
        partisan_list = pl.concat_list([v for v, _ in newest_first])
        # Take last-three partisan ballots (newest first), filter out zeros,
        # then derive classification via pure-Polars set operations.
        l3 = (
            partisan_list
              .list.eval(pl.element().filter(pl.element() != 0))
              .list.head(3)
        )
        l3_len = l3.list.len()
        l3_max = l3.list.max()
        l3_min = l3.list.min()
        # All +1 -> all D; all -1 -> all R; mixed signs -> MIX.
        last_three_party = (
            pl.when(l3_len == 0).then(pl.lit("NONE"))
            .when((l3_max == 1) & (l3_min == 1) & (l3_len >= 3)).then(pl.lit("DDD"))
            .when((l3_max == 1) & (l3_min == 1) & (l3_len == 2)).then(pl.lit("DD"))
            .when((l3_max == 1) & (l3_min == 1) & (l3_len == 1)).then(pl.lit("D"))
            .when((l3_max == -1) & (l3_min == -1) & (l3_len >= 3)).then(pl.lit("RRR"))
            .when((l3_max == -1) & (l3_min == -1) & (l3_len == 2)).then(pl.lit("RR"))
            .when((l3_max == -1) & (l3_min == -1) & (l3_len == 1)).then(pl.lit("R"))
            .otherwise(pl.lit("MIX"))
        )
        ysl_expr = pl.lit(None, dtype=pl.Float64)
        for val, d in partisan_marker_cols:  # oldest -> newest; later overrides
            years_since = (AS_OF_DATE - d).days / 365.25
            ysl_expr = (
                pl.when(val != 0).then(pl.lit(years_since)).otherwise(ysl_expr)
            )
        years_since_last_partisan = ysl_expr
    else:
        last_three_party = pl.lit("NONE")
        years_since_last_partisan = pl.lit(None, dtype=pl.Float64)

    return {
        "lean_score": lean_score.alias("lean_score"),
        "recent_5yr_lean": recent_5yr_lean.alias("recent_5yr_lean"),
        "partisan_primary_count": partisan_primary_count.cast(pl.Int32).alias("partisan_primary_count"),
        "switch_count": switch_count.cast(pl.Int32).alias("switch_count"),
        "last_three_party": last_three_party.alias("last_three_party"),
        "years_since_last_partisan": years_since_last_partisan.alias("years_since_last_partisan"),
    }


# --- CLASSIFICATION -------------------------------------------------------
def add_prediction(df):
    return df.with_columns([
        pl.when(
            (pl.col("lean_score") >= LOCKED_THRESHOLD)
            & (pl.col("last_three_party") == "DDD")
            & (pl.col("years_since_last_partisan") <= RECENCY_LOCK_YEARS)
        ).then(pl.lit("LOCKED_D"))
        .when(
            (pl.col("lean_score") <= -LOCKED_THRESHOLD)
            & (pl.col("last_three_party") == "RRR")
            & (pl.col("years_since_last_partisan") <= RECENCY_LOCK_YEARS)
        ).then(pl.lit("LOCKED_R"))
        .when(pl.col("lean_score") >= LEAN_THRESHOLD).then(pl.lit("LEAN_D"))
        .when(pl.col("lean_score") <= -LEAN_THRESHOLD).then(pl.lit("LEAN_R"))
        .otherwise(pl.lit("TRUE_MIXED"))
        .alias("prediction"),
        (
            pl.col("lean_score").abs()
            * (pl.col("partisan_primary_count").cast(pl.Float64)
               / (pl.col("partisan_primary_count").cast(pl.Float64) + 2.0))
        ).round(3).alias("confidence"),
    ])


# --- MAIN -----------------------------------------------------------------
def main():
    print(f"[load] {INPUT_CSV}")
    df = pl.read_csv(INPUT_CSV, infer_schema_length=0)
    print(f"[load] {df.height:,} rows, {df.width} cols")

    primary_cols = []
    for col in df.columns:
        d = parse_primary_date(col)
        if d is not None:
            primary_cols.append((col, d))
    print(f"[scan] {len(primary_cols)} PRIMARY-* columns detected")
    print(f"[scan] AS_OF_DATE={AS_OF_DATE}, DECAY_LAMBDA={DECAY_LAMBDA}, "
          f"PRES_BOOST={PRESIDENTIAL_PRIMARY_BOOST}")

    exprs = build_score_expressions(primary_cols)
    df = df.with_columns(list(exprs.values()))
    df = add_prediction(df)

    df = df.with_columns([
        pl.col("lean_score").round(4),
        pl.col("recent_5yr_lean").round(4),
        pl.col("years_since_last_partisan").round(2),
    ])

    computed = [
        "lean_score", "recent_5yr_lean", "partisan_primary_count",
        "switch_count", "last_three_party", "years_since_last_partisan",
        "prediction", "confidence",
    ]
    keep = [c for c in df.columns if c not in computed] + computed
    df = df.select(keep)

    print(f"[write] {OUTPUT_CSV}")
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(OUTPUT_CSV)

    summary = (
        df.group_by("prediction")
          .agg([
              pl.len().alias("n"),
              pl.col("lean_score").mean().round(3).alias("mean_lean"),
              pl.col("confidence").mean().round(3).alias("mean_confidence"),
              pl.col("partisan_primary_count").mean().round(2).alias("mean_partisan_n"),
              pl.col("switch_count").mean().round(2).alias("mean_switches"),
              pl.col("years_since_last_partisan").mean().round(2).alias("mean_years_since"),
          ])
          .sort("n", descending=True)
    )
    print("\n[summary]")
    with pl.Config(tbl_rows=20, tbl_cols=20):
        print(summary)
    summary.write_csv(SUMMARY_CSV)
    print(f"[write] {SUMMARY_CSV}")

    preview_cols = [
        "SOS_VOTERID", "LAST_NAME", "FIRST_NAME", "PRECINCT_NAME",
        "lean_score", "recent_5yr_lean", "last_three_party",
        "switch_count", "partisan_primary_count",
        "years_since_last_partisan", "prediction", "confidence",
    ]
    print("\n[top 10 LEAN_D / LOCKED_D by confidence]")
    with pl.Config(tbl_rows=10, tbl_cols=12, fmt_str_lengths=30):
        d_prev = (
            df.filter(pl.col("prediction").is_in(["LEAN_D", "LOCKED_D"]))
              .sort("confidence", descending=True)
              .select(preview_cols)
              .head(10)
        )
        print(d_prev)
    print("\n[top 10 LEAN_R / LOCKED_R by confidence]")
    with pl.Config(tbl_rows=10, tbl_cols=12, fmt_str_lengths=30):
        r_prev = (
            df.filter(pl.col("prediction").is_in(["LEAN_R", "LOCKED_R"]))
              .sort("confidence", descending=True)
              .select(preview_cols)
              .head(10)
        )
        print(r_prev)


if __name__ == "__main__":
    main()
