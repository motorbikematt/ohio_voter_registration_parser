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
- **Active scripts**:
  - `ohio_voter_pipeline.py` — menu driver
  - `voter_data_cleaner_v2.py` — core engine (~3,650 lines). Module-level `COHORT_SLICES` + `COHORT_STACK_MAP`. `classify_all_voters_primary_history()` universal classifier; `clean_voter_data()` auto-attaches 15 cohort columns; `export_json()` + `export_precinct_charts()` write all 6 chart types.
  - `precinct_unc_export.py` — per-precinct cohort counts (pure_d/r, crossover, unc_lifetime, new_registrants).
  - `precinct_party_export.py` — interactive 8-tab partisan-spectrum xlsx by county/precinct.
  - `export_unc_targets.py` — cohort-segmented targeting CSVs.
- **Dashboard**: GitHub Pages `/docs` — county + precinct scope, manifest-driven, Chart.js. Live: https://motorbikematt.github.io/ohio_voter_registration_parser/
  - Deep-link: `?county=Montgomery&geo=precinct-detail&precinct=DAYTON+8-B#decade-distribution`
  - 2026-05-07: deep-link bug fixed — `_populatePrecinctDropdown` in `docs/charts.js` now calls `_filterSections` + `_renderVisibleSections` + `_rebuildNav` after injecting precinct sections.
- **Dashboard JSON status**: Current as of 2026-05-08. Regenerate with pipeline option 1 or 2 after any classifier change, then commit + push.
- **Cohort taxonomy** (2026-05-08): 7 public `cohort_family` values. No decay scoring. Pure means zero opposing-party primary history, lifetime. CROSSOVER_R/D preserved internally in `cohort` column for future proprietary analysis; map to `MIXED_ACTIVE` in `cohort_family`. `classify_unc_primary_history()` is a legacy wrapper delegating to `classify_all_voters_primary_history()` — pending caller audit before removal.

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
- Install: `.venv\Scripts\pip install orjson psutil`

## Git

- `.git/index.lock` from failed sandbox git ops: `Remove-Item "D:\vibe\election-data (1)\.git\index.lock" -Force`, then commit from PowerShell or VS Code.
- GitHub Pages: `/docs` on `main`. Actions build ~40s.
- Pending cleanup: `git rm --cached` for `GEMINI.md`, old `voter_data_cleaner.py` (v1), two stray `.png` files.

---

*Last updated: 2026-05-08 (7-cohort schema, Mixed-Active/Lapsed split)*
