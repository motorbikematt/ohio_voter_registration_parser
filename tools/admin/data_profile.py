"""Shared per-county data-profiling primitives -- the tooling behind the
"88-county assumption" (CLAUDE.md 5).

The doctrine: a source column's meaning is heterogeneous across the 88 county
Boards of Elections until a bounded per-county profile proves it uniform. This
module is where that profiling lives, so "profile before you assume" is a
one-call habit for ANY stream (SWVF jurisdiction columns today; elected
officials, results, committees next) instead of bespoke SQL re-invented per
caller.

Single-source rule (CLAUDE.md 5): the 88-county roster is NOT re-declared here.
It is imported from its one canonical home, pipeline/voter_data_cleaner.py's
`OHIO_COUNTIES` ({'01': 'Adams', ...}) -- the same dict every other module in
the repo consumes. Re-declaring it (as the validator once did, via a private
list + enumerate) is the exact divergent-copy disease the doctrine forbids.

State seam (future multi-state): everything here is Ohio-concrete but
single-sourced, so adding a second state is a LOCAL change, not a scattered
hunt. The two Ohio-specific facts to revisit when that day comes are both in
`OHIO_COUNTIES`'s canonical definition, not here:
  * counties numbered 01-88 in alphabetical order (fixed by Ohio statute), and
  * `COUNTY_NUMBER` is a 2-char zero-padded string.
This module deliberately does NOT pre-build a `state` parameter or a state
registry: there is no second state on disk to validate that design against, and
guessing its shape is the confident-wrong-guess the doctrine exists to prevent.
Earn the abstraction with evidence when the second state arrives.
"""
from __future__ import annotations
import sys
from pathlib import Path

import polars as pl

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from pipeline import voter_data_cleaner as _v  # noqa: E402

# The single canonical county roster -- imported, never re-declared. Keyed
# '01'->'Adams'. Callers that want the number->name map use this directly.
OHIO_COUNTIES: dict[str, str] = _v.OHIO_COUNTIES


def nonblank(col: str) -> pl.Expr:
    """A voter-file cell is present only if non-null AND not whitespace. SWVF
    blanks arrive as '' (empty string), not null (CLAUDE.md 4), so a plain
    is_not_null() would count every blank as populated."""
    return pl.col(col).is_not_null() & (pl.col(col).str.strip_chars() != '')


def iter_county_frames(lf: pl.LazyFrame, cols: list[str]):
    """Yield (county_num, county_name, slug, df) for every county present in
    `lf`, selecting only `cols` (the caller names the columns its resolver
    needs -- jurisdiction, results, officials, ...). One select/collect pass
    over the parquet, then bounded to <=88 filtered slices. Single-threaded by
    design: any cross-county aggregation must run after all counties are
    materialized (CLAUDE.md 5).

    `cols` is intersected with the frame's schema, so a stream missing an
    optional column degrades to the columns it does have rather than raising --
    the schema-level face of heterogeneity (a column present here, absent
    there)."""
    present = [c for c in cols if c in lf.collect_schema().names()]
    full = lf.select(present).collect()
    for num, cname in sorted(OHIO_COUNTIES.items()):
        sub = full.filter(pl.col('COUNTY_NUMBER') == num)
        if sub.height:
            yield num, cname, cname.lower().replace(' ', '_'), sub


def coverage_by_county(lf: pl.LazyFrame) -> pl.DataFrame:
    """Per-county non-blank coverage of every jurisdiction-hierarchy column plus
    the postal RESIDENTIAL_CITY. `any_auth_cov` is the fraction of voters covered
    by ANY authoritative column (CITY/VILLAGE/WARD/TOWNSHIP) -- counties near 0
    there are the true postal-last-resort set.

    This is the jurisdiction stream's coverage profile; it stays here (not in
    the validator) because it is the reference shape every stream's coverage
    profile should follow."""
    cols = lf.collect_schema().names()
    auth = [c for c in ('CITY', 'VILLAGE', 'WARD', 'TOWNSHIP') if c in cols]
    tail = auth + (['RESIDENTIAL_CITY'] if 'RESIDENTIAL_CITY' in cols else [])
    agg = [pl.len().alias('voters')]
    for c in tail:
        agg.append(nonblank(c).sum().alias(f'{c.lower()}_nb'))
    # any_auth: voter covered if any authoritative column is non-blank.
    any_expr = pl.lit(False)
    for c in auth:
        any_expr = any_expr | nonblank(c)
    agg.append(any_expr.sum().alias('any_auth_nb'))

    out = lf.group_by('COUNTY_NUMBER').agg(agg)
    ratios = [(pl.col(f'{c.lower()}_nb') / pl.col('voters')).alias(f'{c.lower()}_cov')
              for c in tail]
    ratios.append((pl.col('any_auth_nb') / pl.col('voters')).alias('any_auth_cov'))
    return out.with_columns(ratios).sort('COUNTY_NUMBER').collect()


def profile_column(lf: pl.LazyFrame, col: str, top: int = 5) -> pl.DataFrame:
    """The "profile before you assume" one-call habit (CLAUDE.md 5).

    Before any code branches on, aggregates, or resolves a source column, call
    this to see whether the column means the same thing across counties. For
    `col`, per county, returns a BOUNDED frame: total rows, non-blank count and
    rate, distinct non-blank value count, and the top-N most common non-blank
    values with their counts (as a list, so the whole result fits in a few
    hundred tokens even across 88 counties).

    What to look for -- the four divergence levels (CLAUDE.md 5): wildly
    different `distinct` or `top_values` between counties (VALUE divergence);
    `nonblank_rate` near 0 in some counties and near 1 in others (SCHEMA/coverage
    divergence -- the column is effectively absent for those counties). FORMAT
    and PROVENANCE divergence live outside a single tabular column and are not
    visible here; profile the raw artifact for those.

    Read-only, bounded, stream-agnostic: `col` need not be a jurisdiction
    column."""
    if col not in lf.collect_schema().names():
        raise KeyError(
            f"profile_column: {col!r} not in frame; columns present: "
            f"{sorted(lf.collect_schema().names())[:20]}...")

    nb = nonblank(col)
    per_county = (
        lf.group_by('COUNTY_NUMBER')
          .agg(
              pl.len().alias('rows'),
              nb.sum().alias('nonblank'),
              pl.col(col).filter(nb).n_unique().alias('distinct'),
          )
          .with_columns((pl.col('nonblank') / pl.col('rows')).alias('nonblank_rate'))
    )

    # Top-N non-blank values per county, folded into a list column so the
    # result is one row per county regardless of cardinality.
    ranked = (
        lf.filter(nb)
          .group_by(['COUNTY_NUMBER', col])
          .agg(pl.len().alias('_n'))
          .sort(['COUNTY_NUMBER', '_n'], descending=[False, True])
          .group_by('COUNTY_NUMBER', maintain_order=True)
          .agg(
              pl.struct([pl.col(col).alias('value'), pl.col('_n').alias('count')])
                .head(top).alias('top_values'))
    )

    out = (
        per_county.join(ranked, on='COUNTY_NUMBER', how='left')
                  .sort('COUNTY_NUMBER')
                  .collect()
    )
    return out.with_columns(
        pl.col('COUNTY_NUMBER')
          .replace_strict(OHIO_COUNTIES, default='?')
          .alias('county'))
