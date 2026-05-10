# Handoff: Stacked Bar Chart Cohort Consistency

## What you are doing and why

The Ohio voter registration dashboard (`voter_data_cleaner_v2.py`, ~3,600 lines) exports 6 chart types per geography. The **party doughnut** was already updated to use an 8-cohort COHORT_SLICES taxonomy (Pure R, R-Crossover, UNC-Lifetime-R, UNC-Mixed, UNC-No-History, UNC-Lifetime-D, D-Crossover, Pure D). The **Party × Decade** and **Party × Generation** stacked bar charts were not — they still pivot on `PARTY_LABEL` ("REP"/"DEM"), so their series labels are inconsistent with the doughnut. The requirement is that every geography (precinct, county, ward, district) renders identical labels and colors across all 6 chart types.

## File editing protocol — mandatory

`voter_data_cleaner_v2.py` is ~3,600 lines. **Never use the Edit tool on it.** Always use a Python patch script:

```python
with open('path/to/file.py', encoding='utf-8') as f:
    src = f.read()

old = "exact unique block < 10 lines"
new = "replacement"

assert src.count(old) == 1, f"Expected 1 match, found {src.count(old)}"
src = src.replace(old, new)

with open('path/to/file.py', 'w', encoding='utf-8') as f:
    f.write(src)
```

After every patch: `python3 -c "import ast; ast.parse(open('voter_data_cleaner_v2.py').read())"` — must return clean.

**Bash heredocs also truncate silently at ~50 lines.** Use `Path.write_text()` or the patch script pattern.

## Canonical color/label spec

These are defined at module level in `voter_data_cleaner_v2.py` and must not be changed:

```python
COHORT_SLICES = [
    ('PURE_R',         'Pure R',           '#ef4444'),
    ('CROSSOVER_R',    'R – Crossover',    '#f87171'),
    ('UNC_LIFETIME_R', 'UNC – Lifetime R', '#fca5a5'),
    ('UNC_MIXED',      'UNC – Mixed',      '#a78bfa'),
    ('UNC_NO_HISTORY', 'UNC – No History', '#9ca3af'),
    ('UNC_LIFETIME_D', 'UNC – Lifetime D', '#93c5fd'),
    ('CROSSOVER_D',    'D – Crossover',    '#60a5fa'),
    ('PURE_D',         'Pure D',           '#3b82f6'),
]
```

UNC shadow bar colors come from `UNC_SHADOW_COLORS` (already correct, do not change).

## What to change

There are **four** chart-building blocks that need rewriting, all in `voter_data_cleaner_v2.py`. Two are in the county-level `export_json()` function and two are in the precinct-level `export_precinct_charts()` function.

### 1. County — Party × Decade (inside `export_json`)

**Find by searching for:** `'Party Affiliation by Birth Decade'` (the `_dump_json` title string for the county chart, geography='county').

**Current logic** (approximately lines 2098–2165): pivots `df` on `PARTY_LABEL`, iterates `[('REP', 'rep'), ('DEM', 'dem'), ('Other', 'other')]` for the main bars, then appends UNC shadow datasets from `unc_classified`.

**Replace with**: pivot on `cohort_family` when present, producing one dataset per COHORT_SLICES entry. Each affiliated cohort (PURE_R, CROSSOVER_R, PURE_D, CROSSOVER_D) gets its own stack id matching its side (e.g. stack='r_pure', stack='r_cross', stack='d_cross', stack='d_pure'). The four UNC cohorts share stack='unc'. This eliminates the need for the separate `unc_classified` join in this chart because `cohort_family` already encodes UNC subclass. Fall back to the current PARTY_LABEL logic only if `cohort_family` is not in `df.columns`.

Pseudocode for the new 8-cohort path:
```python
if 'cohort_family' in df.columns and 'Decade' in df.columns:
    cross = (
        df.filter(pl.col('Decade').is_not_null())
          .group_by(['Decade', 'cohort_family'])
          .agg(pl.len().alias('n'))
          .pivot(on='cohort_family', index='Decade', values='n', aggregate_function='sum')
          .sort('Decade')
    )
    decade_labels = [f'{d}s' for d in cross['Decade'].to_list()]
    decade_vals   = cross['Decade'].to_list()
    stack_map = {
        'PURE_R':         'r_pure',
        'CROSSOVER_R':    'r_cross',
        'UNC_LIFETIME_R': 'unc',
        'UNC_MIXED':      'unc',
        'UNC_NO_HISTORY': 'unc',
        'UNC_LIFETIME_D': 'unc',
        'CROSSOVER_D':    'd_cross',
        'PURE_D':         'd_pure',
    }
    datasets = []
    for fam, lbl, color in COHORT_SLICES:
        vals = ([int(v or 0) for v in cross[fam].to_list()]
                if fam in cross.columns else [0] * len(decade_vals))
        datasets.append({
            'label':           lbl,
            'data':            vals,
            'backgroundColor': color,
            'borderRadius':    3,
            'stack':           stack_map[fam],
        })
else:
    # existing PARTY_LABEL fallback — keep as-is
    ...
```

### 2. County — Party × Generation (inside `export_json`)

**Find by searching for:** `'Party Affiliation by Generation'` (geography='county').

Same transformation as above but grouped by `Generation` instead of `Decade`. Use `_GEN_ORDER` for sort order (already defined in the file). Stack map is identical.

### 3. Precinct — Party × Decade (inside `export_precinct_charts`)

**Find by searching for:** `'Party Affiliation by Birth Decade — {precinct_name}'` (the f-string title).

Same 8-cohort pivot logic, but applied to `pdf` (the per-precinct slice) instead of `df`. The `pdf` frame already has `cohort_family` attached because the enriched county df is passed through. No need to reference `unc_classified` for this chart once `cohort_family` is the source.

### 4. Precinct — Party × Generation (inside `export_precinct_charts`)

**Find by searching for:** `'Party Affiliation by Generation — {precinct_name}'`.

Same as #3, grouped by `Generation`.

## What NOT to change

- `COHORT_SLICES` definition — it's already correct.
- The UNC Shadow chart (`_unc` files) — it uses `unc_classified` and `UNC_SHADOW_COLORS`, which are already consistent.
- The party doughnut in `export_precinct_charts()` — it was already patched this session to use COHORT_SLICES.
- The party doughnut in `export_json()` — already uses COHORT_SLICES (lines ~2003–2013).
- The decade bar (no party) and generation bar (no party) — they're already correct single-series bars.
- `charts.js` — no changes needed; it already reads whatever label/color arrays are in the JSON.

## Verification

After patching, run a spot-check export of a single county (Montgomery = county_num '57') to confirm:
1. `montgomery_party_by_decade.json` has 8 datasets with labels matching COHORT_SLICES.
2. `montgomery_party_by_generation.json` has 8 datasets.
3. `montgomery_precinct_dayton_8_b_party_by_decade.json` has 8 datasets.
4. `montgomery_precinct_dayton_8_b_party_by_generation.json` has 8 datasets.
5. All label strings match exactly: "Pure R", "R – Crossover", "UNC – Lifetime R", "UNC – Mixed", "UNC – No History", "UNC – Lifetime D", "D – Crossover", "Pure D".

The spot check can be done without running the full pipeline by calling `export_precinct_charts()` and the relevant section of `export_json()` directly against the Montgomery Parquet partition.

## After the code change

Once patched and validated, the user needs to run a full statewide JSON build (pipeline option 1 or 2) to regenerate all `docs/data/` files, then `git add docs/data/ && git commit && git push` to redeploy to GitHub Pages.

## Environment

- Python `.venv` at `D:\vibe\election-data (1)\.venv`
- Main script: `D:\vibe\election-data (1)\voter_data_cleaner_v2.py`
- Dashboard JSON output: `D:\vibe\election-data (1)\docs\data\`
- Parquet cache: `D:\vibe\election-data (1)\` (partitioned by county)
- Polars, orjson, psutil are installed in the venv
