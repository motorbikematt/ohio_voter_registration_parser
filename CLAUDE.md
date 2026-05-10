# CLAUDE.md – Ohio Voter Registration Parser

## File editing protocol — read first

| File length | Method |
|---|---|
| ≤ 150 lines | Edit tool permitted |
| > 150 lines | **Python patch script. No exceptions.** |

The Edit tool and bash heredocs both truncate silently — observed at 951 lines and at ~50-line heredoc payloads. A failed write looks identical to a successful one until parsing fails downstream.

Patch script template:

```python
from pathlib import Path
p = Path('path/to/file.py')
src = p.read_text(encoding='utf-8')
old = "exact unique block, < 10 lines"
new = "replacement"
assert src.count(old) == 1, f"Expected 1, found {src.count(old)}"
p.write_text(src.replace(old, new), encoding='utf-8')
```

For payloads > ~50 lines, use `Path.write_text(content)` from inside a Python invocation — never `cat << 'EOF' >> file`.

After every patch, validate before proceeding:
- Python: `python3 -c "import ast; ast.parse(open('path').read())"`
- JavaScript: `node --check path/to/file.js`

---

## Project overview

Bottom-up geospatial pipeline converting raw Ohio SWVF data into precinct → ward → city → district → county aggregates, then diff analytics between subregions and parents. Phase 3+ integrates external datasets (census, property, USPS) for unregistered-resident matching and GIS visualization.

## Processing principles

- **Polars or DuckDB**, not Pandas — out-of-core, vectorized, all 88 counties.
- **Parquet** (partitioned by county) for all intermediate layers; **GeoParquet** for spatial.
- **Excel** only for final aggregated stakeholder outputs via `xlsxwriter`/`openpyxl`. Never load raw files into Excel.
- **Provenance** preserved: BoE timestamps, original headers, source URLs.
- **Zero-trust security**: never commit raw PII. `.gitignore` covers `./working/` and `./source/`.

## Delivery

**Web**: SPA on GitHub Pages (`/docs`); WebGL via Deck.gl/MapLibre planned. Lazy-load county data. Charts must be screenshot- and print-ready; dark/light mode.

**Stakeholder Excel**: Aggregated only. Frozen rows, bold headers, auto-width, filters, conditional formatting on anomalies. Print-ready, zero manual cleanup.

## Phases

- **P1 — Atomic Ingestion** ✓ Parse SWVF to precinct.
- **P2 — Roll-Up** Aggregate into wards, cities, school districts, legislative districts, counties.
- **P3 — Diffs + GIS** Demographic/registration deltas; choropleth drill-down.
- **P4 — Dark Data** Property + census + USPS NCOA → unregistered-resident matrix for GOTV.
- **P5 — Temporal/Anomaly** Shift detection, momentum, turnout variance; SaaS subscriber alerts.

## File locations

- Raw: `D:\vibe\election-data (1)\source\`
- Working / final: `D:\vibe\election-data (1)\`

## Schema reference

Source: 4 split flat files (`SWVF_1_22.txt`, `SWVF_23_44.txt`, `SWVF_45_66.txt`, `SWVF_67_88.txt`). Pipe-delimited, quoted, UTF-8. 46 static cols + 89 dynamic election cols.

**Join key**: `SOS_VOTERID` (statewide). `COUNTY_ID` is county-scoped — never use cross-county.

### Identity / demographics
`SOS_VOTERID`, `COUNTY_NUMBER` (1–88), `COUNTY_ID`, `LAST_NAME`, `FIRST_NAME`, `MIDDLE_NAME`, `SUFFIX`, `DATE_OF_BIRTH` (YYYY-MM-DD).

### Registration / status
- `REGISTRATION_DATE` — Never reassigned on name/address change. Reliable first-registration proxy. Resets only on cancellation + reactivation.
- `VOTER_STATUS` — `ACTIVE` or `CONFIRMATION` only in SWVF; collapses 6+ internal substatus codes (FPCA, NCOA, BMV/SSA MATCH, CONF NCOA, CONF LIST MAINT, CONF NO VOTE). CONFIRMATION spikes are ambiguous in SWVF; subtype distinction requires county files.
- `PARTY_AFFILIATION` — `R`, `D`, or empty (unaffiliated). Behavior-derived per Ohio EOM Ch.15: which party primary in past 2 calendar years. Use election-history columns as ground truth.

### PII (never commit)
- Residential: ADDRESS1, SECONDARY_ADDR, CITY, STATE, ZIP, ZIP_PLUS4, COUNTRY, POSTALCODE
- Mailing: ADDRESS1, SECONDARY_ADDRESS, CITY, STATE, ZIP, ZIP_PLUS4, COUNTRY, POSTAL_CODE

### Jurisdictional aggregation keys
`PRECINCT_NAME` (atomic unit, e.g. KETTERING 1-A), `PRECINCT_CODE`, `CONGRESSIONAL_DISTRICT`, `STATE_SENATE_DISTRICT`, `STATE_REPRESENTATIVE_DISTRICT`, `CITY`, `TOWNSHIP`, `VILLAGE`, `WARD`, `LOCAL_SCHOOL_DISTRICT`, `CITY_SCHOOL_DISTRICT`, `EXEMPTED_VILL_SCHOOL_DISTRICT`, `CAREER_CENTER`, `COUNTY_COURT_DISTRICT`, `MUNICIPAL_COURT_DISTRICT`, `COURT_OF_APPEALS`, `STATE_BOARD_OF_EDUCATION`, `EDU_SERVICE_CENTER_DISTRICT`, `LIBRARY`.

### County-scoped types (collide on name across counties — composite key required)
`TOWNSHIP`, `VILLAGE`, `MUNICIPAL_COURT_DISTRICT`. The same name denotes legally distinct entities in different counties (Washington Township in 23 counties, BELLEVUE municipal court in 3, etc.). Aggregation must use `(COUNTY_NUMBER, name)` as the composite key. `JURISDICTIONS[type]['county_scoped'] = True` triggers this in `jurisdictional_groupings.py`. Output slug becomes `{county_slug}_{name_slug}`. Display label becomes `{name} ({County} Co.)`.

### Election history (89 dynamic cols)
Format `[TYPE]-[MM/DD/YYYY]`, TYPE ∈ {PRIMARY, GENERAL, SPECIAL}. Range 03/07/2000 → 02/03/2026. Values: `R`/`D` (party primary ballot), `X` (non-partisan), empty (didn't vote). 2 calendar years of blanks → supplemental list maintenance → CONFIRMATION. High CONFIRMATION + sparse recent history = anomaly signal (Ohio EOM Ch.4). No `_TYPE` suffixes (absentee/Eday) in SWVF — county files only.

### Not in SWVF
- Last Activity Type (VOT/ABR/REG/UPD/BMV/PET/CON) — must infer from election history.
- Ballot method (`_TYPE` cols) — Absentee/Eday/Provisional.
- CONFIRMATION subtype.

### External (P3+)
Precinct canvass: https://www.ohiosos.gov/elections/election-results-and-data/

### Error policy
Log malformed rows to `./working/errors/[county].log` and continue. Never halt on parse error.

## Project state

- **Phase 1 complete**. Parquet cache: 88 partitions, 7,892,613 rows × 135 cols.
- **Directory layout** (2026-05-09 reorganization):
  - Root: core engine + config only. `ohio_voter_pipeline.py` (menu driver), `ohio_voter_pipeline_wrapper.py`, `voter_data_cleaner_v2.py` (core, ~3,650 lines), `jurisdictional_groupings.py` (747 lines, county-scoped aggregator), `state_configs/ohio.py`.
  - `tools/`: utility scripts and exporters. `precinct_unc_export.py`, `precinct_party_export.py`, `export_unc_targets.py`, `precinct_key_manager.py` (merged scrape + aggregate functions), `clean_precinct_keys.py`, `run_city_groupings.py`, `test_jurisdiction_collisions.py`, `voter_lookup.py`, `voter_analysis.ipynb`. Precinct key CSVs are lean 3-col schema: county, precinct_code, precinct_label.
  - `tools/scoring/`: lean-prediction module. `mixed_lean_predictor.py`, `unc_lifetime_d_predictor.py`, `run_lean_predictor_all_cohorts.py`, `run_mixed_lean_predictor_all_counties.py`.
  - `docs/research/`: archived research logs and handoff notes.
- **Active scripts**:
  - `ohio_voter_pipeline.py` — menu driver. Option 4 dispatches `jurisdictional_groupings.main()` with `--jurisdictions` filter.
  - `voter_data_cleaner_v2.py` — core engine. Module-level `COHORT_SLICES`, `COHORT_STACK_MAP`, `OHIO_COUNTIES` (number→name, line 203). `classify_all_voters_primary_history()` universal classifier; `clean_voter_data()` auto-attaches 15 cohort columns; `export_json()` + `export_precinct_charts()` write all 6 chart types.
  - `jurisdictional_groupings.py` — multi-jurisdiction aggregator. `JURISDICTIONS` dict with `column`, `display`, optional `county_scoped` flag. `aggregate_jurisdiction()` accepts optional `county_name` for slug + display qualification. `main()` branches on `county_scoped` for composite-key enumeration, partition, dispatch.
  - `tools/precinct_unc_export.py` — per-precinct cohort counts (pure_d/r, crossover, unc_lifetime, new_registrants).
  - `tools/precinct_party_export.py` — interactive 8-tab partisan-spectrum xlsx by county/precinct.
  - `tools/export_unc_targets.py` — cohort-segmented targeting CSVs.
  - `tools/precinct_key_manager.py` — interactive precinct key manager (merged from scrape_vtrapp_precincts + aggregate_precinct_keys).
- **Dashboard**: GitHub Pages `/docs` — county + precinct scope, manifest-driven, Chart.js. Live: https://motorbikematt.github.io/ohio_voter_registration_parser/
  - Deep-link: `?county=Montgomery&geo=precinct-detail&precinct=DAYTON+8-B#decade-distribution`
  - 2026-05-07: deep-link bug fixed — `_populatePrecinctDropdown` in `docs/charts.js` now calls `_filterSections` + `_renderVisibleSections` + `_rebuildNav` after injecting precinct sections.
  - **Pending Pass B**: dashboard renders no jurisdiction-level chart pages. Existing `geography:"city"` sections in `manifest.json` reference legacy `data/{county}_city_summary.json` table format, NOT the 6-chart bundle in `docs/data/city/`. New scope routing + filter UI in `charts.js` required to expose all 12 jurisdiction types.
- **Dashboard JSON status**: Current as of 2026-05-08 for county/precinct. Townships, villages, municipal_court_districts re-run pending after Pass A patch (2026-05-10). Re-run command: `python jurisdictional_groupings.py --jurisdictions townships,villages,municipal_court_districts`. Delete old phantom-merged dirs first: `docs/data/township`, `docs/data/village`, `docs/data/municipal_court_district`.
- **Cohort taxonomy** (2026-05-08): 7 public `cohort_family` values. No decay scoring. Pure means zero opposing-party primary history, lifetime. CROSSOVER_R/D preserved internally in `cohort` column for future proprietary analysis; map to `MIXED_ACTIVE` in `cohort_family`. `classify_unc_primary_history()` is a legacy wrapper delegating to `classify_all_voters_primary_history()` — pending caller audit before removal.
- **County-scoping (2026-05-10, Pass A)**: Townships, villages, municipal_court_districts in `JURISDICTIONS` carry `county_scoped: True`. Slugs are `{county}_{name}` (e.g. `montgomery_washington_township`). Display labels are `{name} ({County} Co.)`. Resume sentinel files use the new naming. Cities, school districts, legislative/judicial districts remain non-scoped (multi-county multi-county-by-design or county-encoded names). Career_centers dropped from scope — administrative, no elected officials. Collision report at `collision_report.md`.

## Chart consistency contract

All geographies (precinct, county, ward, city, district) render the same 6 charts with identical labels, colors, and ordering:

| Chart | Type | Series |
|---|---|---|
| Party Affiliation | doughnut | 7-cohort `COHORT_SLICES`: Pure R → UNC Lapsed R → Mixed Active → Mixed Lapsed → UNC No Primary → UNC Lapsed D → Pure D. Columns: Republican \| Mixed / Unaffiliated \| Democratic |
| Age by Decade | bar | Decade (1920s–2010s) |
| Age by Generation | bar | Pew boundaries |
| Party × Decade | stacked bar | 7-cohort stacks per decade (stack ids: `r_pure`, `unc_r`, `unc_mid`, `unc_d`, `d_pure`) |
| Party × Generation | stacked bar | 7-cohort stacks per generation (same stack ids) |
| UNC Shadow | stacked bar | UNC_LAPSED_R / UNC_LAPSED_D / MIXED_ACTIVE / MIXED_LAPSED / UNC_NO_PRIMARY |

Doughnut tooltips are disabled and the legend renders `"<Cohort> — <count> (<pct>%)"` with thousands separators for screenshot/print legibility. Bar tooltips remain enabled.

`COHORT_SLICES` and `COHORT_STACK_MAP` are module-level in `voter_data_cleaner_v2.py` near `UNC_SHADOW_COLORS` — single source of truth.

## Pipeline architecture

- `ThreadPoolExecutor` `max_workers=8` — shared address space, no IPC, no WinError 1450.
- `orjson` for JSON (GIL-releasing, ~3–5× stdlib). Falls back to stdlib if missing.
- `psutil` RSS logging in every `_timer` exit. Peak RSS ~45 GB during Excel pass (two 7.9M-row frames).
- Pre-classification: `classify_all_voters_primary_history()` runs once in main process; workers receive enriched slices with `cohort_family` attached. `_unc_classified_from_enriched_df()` fast path skips redundant decay math.
- **Pending Pass B**: persistent enriched-parquet cache at `source/parquet_enriched/` to skip the ~80s `clean_voter_data()` cost on subsequent option 4 runs. Freshness check must compare cache mtime against `max(raw partition mtime, voter_data_cleaner_v2.py mtime)` to catch classifier-code changes; otherwise stale enriched frames silently serve.
- Install: `.venv\Scripts\pip install orjson psutil`

## Git

- `.git/index.lock` from failed sandbox git ops: `Remove-Item "D:\vibe\election-data (1)\.git\index.lock" -Force`, then commit from PowerShell or VS Code.
- GitHub Pages: `/docs` on `main`. Actions build ~40s.
- Pending cleanup: `git rm --cached` for `GEMINI.md`, old `voter_data_cleaner.py` (v1), two stray `.png` files.

---

*Last updated: 2026-05-10 (Pass A: county-scoped slugs for townships/villages/municipal_court_districts in `jurisdictional_groupings.py`. Pass B pending: enriched-parquet cache + dashboard plumbing for all 12 jurisdiction types — see `HANDOFF_OPUS_PASS_B.md`.)*
