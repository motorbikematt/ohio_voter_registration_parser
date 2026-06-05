# Handoff: Pass B — Cache + Dashboard Integration

**Date**: 2026-05-10
**Status**: Pass A complete (county-scoped slugs for townships, villages, municipal courts). Ready for cache + dashboard work.
**Repo**: https://github.com/motorbikematt/ohio_voter_registration_parser
**Dashboard**: https://motorbikematt.github.io/ohio_voter_registration_parser/
**Data dir**: `D:\vibe\election-data (1)`

---

## Your first job

Read this document. Run **Step 0 (cache patch + validation gate)** before touching any dashboard code. The cache is small and standalone; if it breaks, it must break ALONE before dashboard work entangles things. Do not chain into Step 1 if Step 0 validation fails.

Read `CLAUDE.md` for the file-editing protocol. Pay attention to the >150-line patch-script rule and the "loud failures preferred — no try/except" feedback rule. Both are non-negotiable.

---

## What works today (after Pass A — 2026-05-10)

- `jurisdictional_groupings.py` (747 lines) county-scopes townships, villages, and municipal court districts via composite `(COUNTY_NUMBER, name)` keys. Slugs are `{county}_{name}` (e.g. `montgomery_washington_township`).
- `aggregate_jurisdiction()` signature accepts optional `county_name`; non-scoped types (cities, school districts, legislative/judicial) pass `None` and behave as before.
- All 12 active jurisdiction types produce 6-chart-per-jurisdiction JSON in their respective subdirectories under `docs/data/{type}/`. CAREER_CENTER dropped from scope (administrative, no elected officials).
- Pass A patch script preserved at `outputs/patch_pass_a_county_scoping.py` as audit trail.
- Collision report: `collision_report.md`.

## What is broken or missing

1. **Dashboard renders no jurisdiction-level chart pages.** Existing `geography:"city"` sections in `docs/manifest.json` point to legacy table-format `data/{county}_city_summary.json`, NOT the new 6-chart bundle in `docs/data/city/`.
2. **`charts.js` has no scope routing for new jurisdiction types** — only `county`, `precinct`, and the legacy `city` table scopes exist.
3. **Every option 4 invocation pays ~80s of redundant enrichment** because the enriched 155-column frame is not cached across runs.

---

## Step 0: Cache patch (DO THIS FIRST)

### Spec

Persistent enriched parquet cache at `source/parquet_enriched/enriched_voters.parquet`. On enrichment-needing entry points (`clean_voter_data()` callers in `voter_data_cleaner_v2.py` main flow, `jurisdictional_groupings.py` `main()`):

1. Compute `freshness_max_mtime = max(latest raw partition mtime, voter_data_cleaner_v2.py mtime)`. Including the classifier source mtime catches cohort taxonomy refactors — the 2026-05-08 change would have served stale data otherwise. **The freshness check must include classifier source mtime, not just raw parquet mtime.** This is the most important detail in this spec.
2. If `cache_path.exists()` AND `cache_path.stat().st_mtime > freshness_max_mtime`: load cache via `pl.read_parquet(cache_path)`, skip enrichment.
3. Otherwise: load raw parquet, enrich via `clean_voter_data()`, write to cache.

### Required quality gates

- **Atomic write**: write to `cache_path.with_suffix('.parquet.tmp')` then `Path.replace(cache_path)`. A crashed mid-write must NOT leave a corrupt cache.
- **Patch via Python script** with `assert src.count(old) == 1` for every replacement. Both files (`voter_data_cleaner_v2.py` ~3650 lines, `jurisdictional_groupings.py` 747 lines) exceed the 150-line threshold per CLAUDE.md.
- **Validate post-patch**: `python3 -c "import ast; ast.parse(open('jurisdictional_groupings.py').read()); ast.parse(open('voter_data_cleaner_v2.py').read())"` returns clean.
- **No try/except** added. Loud failures preferred.
- **Constant placement**: `PARQUET_ENRICHED_DIR = BASE_DIR / "source" / "parquet_enriched"` defined at top of both files alongside existing path constants. `mkdir(parents=True, exist_ok=True)` once at module init.

### Reference (corrected) skeleton

```python
PARQUET_ENRICHED_DIR = BASE_DIR / "source" / "parquet_enriched"
PARQUET_ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
ENRICHED_CACHE = PARQUET_ENRICHED_DIR / "enriched_voters.parquet"
CLASSIFIER_SRC = BASE_DIR / "voter_data_cleaner_v2.py"

def _cache_is_fresh() -> bool:
    if not ENRICHED_CACHE.exists():
        return False
    cache_mt = ENRICHED_CACHE.stat().st_mtime
    raw_partitions = list(PARQUET_DIR.glob("COUNTY_NUMBER=*"))
    if not raw_partitions:
        return False
    latest_raw     = max(p.stat().st_mtime for p in raw_partitions)
    classifier_mt  = CLASSIFIER_SRC.stat().st_mtime
    return cache_mt > max(latest_raw, classifier_mt)

def _write_cache_atomic(df: pl.DataFrame) -> None:
    tmp = ENRICHED_CACHE.with_suffix('.parquet.tmp')
    df.write_parquet(tmp, compression="zstd")
    tmp.replace(ENRICHED_CACHE)
```

Wire into `main()` flow at the existing enrichment site:

```python
if _cache_is_fresh():
    logger.info("Loading enriched voter data from persistent cache...")
    df = pl.read_parquet(ENRICHED_CACHE)
else:
    logger.info("Enriching voter data (will take ~80s)...")
    df = clean_voter_data(df, logger)  # use whatever signature is current
    logger.info("Writing enriched voter data to persistent cache...")
    _write_cache_atomic(df)
```

### Validation gate (do not proceed to Step 1 if any expectation fails)

```powershell
& C:\Users\motorbikematt\.venv\Scripts\activate
cd "D:\vibe\election-data (1)"

# First run populates the cache
$t1 = Measure-Command { python jurisdictional_groupings.py --jurisdictions cities }

# Second run uses the cache
$t2 = Measure-Command { python jurisdictional_groupings.py --jurisdictions cities }

Write-Host "Run 1: $($t1.TotalSeconds)s"
Write-Host "Run 2: $($t2.TotalSeconds)s"
Write-Host "Delta: $($t1.TotalSeconds - $t2.TotalSeconds)s"
```

Expectations:
- `$t2.TotalSeconds` is at least 60s lower than `$t1.TotalSeconds` (the enrichment step skips on second run).
- `source/parquet_enriched/enriched_voters.parquet` exists after first run, ~10 GB on disk.
- A test-only diff between the two runs' output JSON shows zero substantive changes (timestamps may differ; voter counts must not).

If any expectation fails: stop, diagnose. Do NOT proceed to dashboard work on a broken cache.

---

## Step 1: Dashboard plumbing

### Decision points to confirm with user before implementing

A. **Scope tab grouping**: separate scope tabs per jurisdiction type (12 tabs), or one "Jurisdictions" tab with a sub-selector? With 12 types, individual tabs likely overflow on mobile.

B. **Default landing when scope=type but no county**: auto-pick first alphabetical county, render a "select a county" prompt, or render a statewide aggregate?

C. **Statewide aggregations**: should non-scoped types (cities, school districts) get a "statewide" rollup (Columbus combining its 3 counties)? Currently outputs are county-scoped per the existing data.

D. **Legacy city scope handling**: the `geography:"city"` sections in `manifest.json` point to old `data/{county}_city_summary.json` table format. Replace with the new 6-chart bundle, OR keep both as separate scopes (new "city detail" vs legacy "city summary")?

E. **Manifest entry strategy**: enumerate every (type, jurisdiction) section in `manifest.json` (50K+ entries — load-time concern), or use a small `jurisdictionScopes` registry block plus per-type `index.json` files written by `jurisdictional_groupings.py` (recommended)?

### Manifest schema (recommended)

Add a small registry block to `manifest.json` rather than enumerating individual jurisdictions:

```json
"jurisdictionScopes": [
  {
    "key": "townships",
    "scope": "township",
    "displayName": "Township",
    "displayNamePlural": "Townships",
    "dirName": "township",
    "countyScoped": true,
    "charts": ["party_affiliation", "decade_distribution", "party_by_decade", "party_by_generation", "unc_shadow"]
  },
  {
    "key": "cities",
    "scope": "city",
    "displayName": "City",
    "displayNamePlural": "Cities",
    "dirName": "city",
    "countyScoped": false,
    "charts": [...]
  }
]
```

Per-type enumeration comes from `docs/data/{dirName}/index.json` written by `jurisdictional_groupings.py`. See "Required script change" below.

### `charts.js` changes

URL parsing in `_readUrlParams` + `_applyUrlState`:
- Extend `?scope=` to accept `township`, `village`, `municipal_court_district`, `local_school_district`, `city_school_district`, `exempted_vill_school_district`, `state_senate_district`, `state_rep_district`, `congressional_district`, `county_court_district`, `court_of_appeals`, plus `city` (new chart-bundle scope, possibly distinct from legacy).
- For `countyScoped` types: require both `?county=` and `?name=` params.
- For non-scoped types: `?name=` only.

URL writing in `_writeUrlState`: parallel writes for the same params.

Filter UI:
- Non-scoped types: flat dropdown listing all entities of the type, sorted alphabetically.
- Scoped types: county dropdown + sub-jurisdiction dropdown (cascading — second dropdown filters by first).

Rendering: dynamic path resolution. Given `activeScope + activeCounty + activeName`, build data URL:
- Scoped: `data/{dirName}/{county_slug}_{name_slug}_{chart}.json`
- Non-scoped: `data/{dirName}/{name_slug}_{chart}.json`

Preserve `#anchor` deep-link behavior across all new scopes.

Files to edit: `docs/charts.js` (line count unknown — read first, treat as >150 if so), `docs/index.html` (likely needs new scope tab buttons + filter UI elements).

### Required script change before Step 1 can populate filter dropdowns

`jurisdictional_groupings.py` does not currently write a per-type index file. Add:

```python
def export_jurisdiction_index(results, jurisdiction_type, logger):
    """Write {dir}/index.json listing all (county, name, slug) tuples for a type."""
    type_dir = DATA_DIR / jurisdiction_type.lower().replace(' ', '_')
    index = [
        {
            'county':      r.get('county'),  # None for non-scoped
            'name':        r['jurisdiction_name'],
            'slug':        r['slug'],
            'voter_count': r['voter_count'],
        }
        for r in results if r
    ]
    _dump_json(index, type_dir / 'index.json', logger)
```

Call from `main()` after the JSON export loop. Patch via Python script with `assert count == 1`. After patching, re-run option 4 to populate index files. The cache from Step 0 makes this fast.

---

## Decision points the user has already settled (do not re-litigate)

| Decision | Resolved as |
|---|---|
| Output path layout | Subdirectory per type under `docs/data/` |
| Township/village/municipal-court phantom-merge fix | Uniform county-scoped slugs `{county}_{name}` |
| URL pattern for scoped types | `?scope=type&county=X&name=Y` separate params |
| Filter UI for scoped types | County dropdown + sub-jurisdiction dropdown cascade |
| Scope of fix-and-rerun | Townships, villages, municipal_court_districts (career_centers dropped) |
| Cache fix sequencing | Pass B Step 0, before dashboard work |
| Dashboard scope of effort | Pass B (this session) covers all 12 active types in one coherent design |

---

## Key files

| File | Lines | Purpose |
|---|---|---|
| `jurisdictional_groupings.py` | 747 | County-scoped aggregator. `JURISDICTIONS` dict has `county_scoped` flag. Needs `export_jurisdiction_index()` for Step 1. |
| `voter_data_cleaner_v2.py` | ~3,650 | Core engine. `OHIO_COUNTIES` dict at line 203. `clean_voter_data()` is the cache target. |
| `docs/manifest.json` | ~9,000+ | Per-county sections. Needs new `jurisdictionScopes` registry block. |
| `docs/charts.js` | unknown | Scope routing. `_readUrlParams`, `_applyUrlState`, `_setupScopeTabs`, `_filterSections`, `_rebuildNav` need extension. |
| `docs/index.html` | unknown | Scope tab markup. May need new tab buttons + filter `<select>` elements. |
| `docs/data/{type}/` | many | 6-chart JSON output per jurisdiction. Index file to be added. |
| `collision_report.md` | — | Per-type collision counts (reference). |
| `outputs/patch_pass_a_county_scoping.py` | — | Pass A audit trail. |
| `HANDOFF_OPUS_JURISDICTIONS.md` | — | Pre-Pass-A handoff (historical context). |
| `CLAUDE_backup_2026-05-10.md` | — | CLAUDE.md state at the moment Pass B started. |

---

## File editing rule (enforce throughout)

From `CLAUDE.md`:

> Files >150 lines: Python patch script. No exceptions.
> `assert src.count(old) == 1`
> Validate after every patch: `python3 -c "import ast; ast.parse(...)"` for Python; `node --check path` for JS.

The Edit tool has truncated silently at ~951 lines in this codebase before. Do not be tempted by short patches in long files.

---

## Memory pointers (auto-loaded)

- `feedback_pipeline_safety.md` — no try/except; sole operator; loud failures preferred over silent degradation.
- `feedback_verify_plan_against_repo_state.md` — read touched files before patching a confirmed plan; surface scope gaps before they balloon. (This handoff exists because the prior session caught such a gap mid-implementation.)
- `project_cohort_taxonomy.md` — 2026-05-08 refactor. Pure R/D + crossover scoring. Dashboard JSON regeneration needed after any classifier change.
- `project_repo_layout.md` — 2026-05-09. `tools/` hierarchy; root is engine-only.

---

## Environment

- OS: Windows 11
- Python venv: `C:\Users\motorbikematt\.venv\Scripts\activate`
- Key packages: polars, xlsxwriter, openpyxl, psutil, orjson
- Bash sandbox has system Python3 — **no polars**. Run pipeline scripts via PowerShell or the `ohio_voter_pipeline.py` menu, never via the bash sandbox.
- File system limitation: bash sandbox cannot delete files in the workspace mount (`Operation not permitted`). Tell the user to delete via PowerShell when needed.
- Git index lock cleanup: `Remove-Item "D:\vibe\election-data (1)\.git\index.lock" -Force`
- GitHub Pages: `/docs` on `main`, builds in ~40s.

---

## What NOT to do

- Do not start dashboard work until the Step 0 cache validation gate passes cleanly.
- Do not commit broken JSON or stale cache output to GitHub.
- Do not add `try/except` blocks anywhere — loud failures preferred.
- Do not enumerate every jurisdiction in `manifest.json` (50K+ entries kills load time and goes against the registry-block design above).
- Do not run full pipeline option 1 or 3 (40+ minutes) unless user explicitly asks.
- Do not use the Edit tool on any file longer than 150 lines.
- Do not use the bash sandbox to run polars-dependent scripts; it has no polars and will fail.
- Do not delete files via the bash sandbox in the workspace mount; permissions are read+write only, no delete.

---

## Last action in Pass A (2026-05-10)

Pass A patch landed and AST-validated. User instructed to delete `docs/data/township/`, `docs/data/village/`, `docs/data/municipal_court_district/` via PowerShell, then re-run:

```powershell
python jurisdictional_groupings.py --jurisdictions townships,villages,municipal_court_districts
```

Verify post-rerun: spot-check known collisions exist as separate files. Township: `docs/data/township/montgomery_washington_township_*` and `docs/data/township/pickaway_washington_township_*` should both exist with different voter counts. Municipal court: `docs/data/municipal_court_district/erie_bellevue_*`, `huron_bellevue_*`, `sandusky_bellevue_*` all present.

If user has not yet re-run when this Pass B session begins, the township/village/municipal_court output will be missing or stale. Confirm state with `ls docs/data/township | head` before relying on it for Step 1 dashboard integration.
