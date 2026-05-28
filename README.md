# Ohio Voter Registration Analysis

Download, clean, and analyse the Ohio Secretary of State statewide voter file (SWVF).
Outputs interactive web dashboard JSON for all 88 counties and optional Excel workbooks.

## What's in this repo

**Root engine**

| File | Purpose |
|---|---|
| `ohio_voter_pipeline.py` | Main entry point — interactive menu for statewide or targeted county analysis |
| `voter_data_cleaner_v2.py` | Core engine — Polars ingestion, cohort classifier, participation metrics, JSON + Excel export |
| `ohio_voter_pipeline_wrapper.py` | Programmatic wrapper around the pipeline for scripted runs |
| `jurisdictional_groupings.py` | Aggregates all 12 jurisdiction types; handles county-scoped slug logic |

**Utilities (`tools/`)**

| File | Purpose |
|---|---|
| `precinct_unc_export.py` | Standalone export: partisan cohort counts per precinct, all 88 counties |
| `precinct_party_export.py` | Interactive export: 8-tab partisan-spectrum Excel workbook by county or precinct |
| `export_unc_targets.py` | Export cohort-segmented voter targeting CSVs (Pure R/D, Crossover, UNC subclasses) |
| `voter_lookup.py` | Parquet-backed individual voter lookup |
| `raw_voter_lookup.py` | Raw text file voter lookup (pre-Parquet) |
| `generate_narratives.py` | Render templated narrative cards for dashboard jurisdictions |
| `archive_state.py` | Timestamped snapshot of CLAUDE.md / MEMORY.md before overwrite |

**Scoring (`tools/scoring/`)**

| File | Purpose |
|---|---|
| `mixed_lean_predictor.py` | Decay-weighted lean predictor for UNC MIXED cohort |
| `run_lean_predictor_all_cohorts.py` | Batch runner — lean predictor across all cohorts |
| `run_mixed_lean_predictor_all_counties.py` | Batch runner — lean predictor across all 88 counties |
| `unc_lifetime_d_predictor.py` | Lifetime Democratic lean predictor for UNC voters |

**Dashboard**

| Path | Purpose |
|---|---|
| `docs/` | Web dashboard (HTML + Chart.js) with county, city, and precinct drill-down |
| `docs/data/` | ~65k pre-generated JSON payloads, one per geography |
| `docs/manifest.json` | Dashboard index — geography list, cohort metadata, routing |

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management

Key libraries: Polars (vectorized out-of-core processing), PyArrow (Parquet), xlsxwriter/openpyxl (Excel), DuckDB, requests/beautifulsoup4 (optional SOS scrape).

## Quick start

### 1. Set up the environment

```powershell
uv sync
```

### 2. Obtain the source files

The Ohio SOS blocks automated downloads with 403/CAPTCHA. Download the four SWVF archives
manually from the [Ohio SOS voter file page](https://www6.ohiosos.gov/ords/f?p=VOTERFTP:STWD)
and place them in `source/State Voter Files/`:

```
SWVF_1_22.txt.gz
SWVF_23_44.txt.gz
SWVF_45_66.txt.gz
SWVF_67_88.txt.gz
```

### 3. Build the Parquet cache and run the analysis

```powershell
python ohio_voter_pipeline.py
```

On first run, select option **[1]** or **[2]**. The pipeline will decompress the source files,
build a Hive-partitioned Parquet cache (`source/parquet/COUNTY_NUMBER=NN/`), then export
dashboard JSON for all 88 counties. Subsequent runs load from the Parquet cache (~4 seconds
for all 7.9M rows) instead of re-parsing the raw text files.

**Menu options:**

| Option | Action |
|---|---|
| `1` | Full Ohio (88 counties) → web dashboard JSON |
| `2` | Full Ohio (88 counties) → web dashboard JSON + Excel workbook |
| `3` | Selected counties only → web dashboard JSON (by number or name) |
| `L` | List all 88 counties with official SOS numbers |
| `0` | Exit |

For targeted runs (option 3), enter county numbers or names — partial name matching and
comma-separated multi-county selection are supported. Example: `57, greene, 76`.

### 4. Export a precinct or county voter workbook

```powershell
python tools/precinct_party_export.py
```

Interactive menu: choose county + precinct (single workbook) or whole county. Output lands in
`UNC_Exports/Workbooks/`. Tabs follow the 8-cohort partisan spectrum (see Cohort Taxonomy below).

### 5. View the dashboard

Open `docs/index.html` locally, or view the live dashboard at:
[https://precincts.info](https://precincts.info)

The dashboard supports three scope tiers: **County** (default), **City**, and **Precinct**.
Precinct drill-down shows per-precinct cohort composition for every precinct in the selected county.

## Output

- **Web dashboard** — `docs/index.html` with Chart.js charts; data in `docs/data/` and `docs/manifest.json`
- **Excel workbook** — `ohio_analysis_YYYY-MM-DD.xlsx` (county summary) or `county_NN_analysis_YYYY-MM-DD.xlsx`
  - Sheets: Decade Summary, Participation, District Breakdown, Party Cross-tabs
  - Ohio-wide builds use a County Summary sheet (raw 7.9M rows exceeds Excel's row limit)
- **Precinct workbook** — `UNC_Exports/Workbooks/{County}_{Precinct}_voters.xlsx` — all voter columns + cohort scoring
- **Target CSVs** — `UNC_Exports/Pure_D/`, `UNC_Exports/D_Crossover/`, etc. — one file per county per cohort
- **Parquet cache** — `source/parquet/COUNTY_NUMBER=NN/` — fast reload for subsequent runs
- **Error log** — `working/errors/invalid_birthyear_<run>.csv` — rows dropped for unparseable birth dates
- **Run logs** — `logs/voter_analysis_YYYYMMDD_HHMMSS.log`

## Cohort taxonomy

`PARTY_AFFILIATION` in the SWVF is behavior-derived and lagged — it reflects only the past two calendar years of primary participation, not lifetime history. The universal classifier (`classify_all_voters_primary_history`) applies the full 26-year election history to every voter and assigns a cohort and cohort_family.

### Affiliated voters (affiliated R or D)

| Cohort family | Definition | Dashboard color |
|---|---|---|
| `PURE_R` | Affiliated R + zero D primary ballots ever | `#ef4444` |
| `CROSSOVER_R` | Affiliated R + has voted both primaries historically | `#f87171` |
| `PURE_D` | Affiliated D + zero R primary ballots ever | `#3b82f6` |
| `CROSSOVER_D` | Affiliated D + has voted both primaries historically | `#60a5fa` |

`R_NEW` / `D_NEW` (registered within ~2 years, no primary history) roll into `PURE_R` / `PURE_D` with `is_new_registrant = True`.

### Unaffiliated voters (UNC)

| Cohort family | Definition | Dashboard color |
|---|---|---|
| `UNC_LIFETIME_R` | All primaries were R ballots | `#fca5a5` |
| `UNC_LIFETIME_D` | All primaries were D ballots | `#93c5fd` |
| `UNC_MIXED` | Has voted both party primaries | `#a78bfa` |
| `UNC_NO_HISTORY` | No primary participation on record | `#9ca3af` |

### Crossover scoring

Voters in `CROSSOVER_R`, `CROSSOVER_D`, and `UNC_MIXED` receive decay-weighted lean scores:

- `lean_score` ∈ [-1, +1]: recency-weighted ratio of D vs R primary ballots (decay λ=0.15, presidential-year 1.25× boost)
- `crossover_class`: `LOCKED_D` / `LEAN_D` / `TRUE_MIXED` / `LEAN_R` / `LOCKED_R`
  - Affiliated crossover thresholds: LOCKED ±0.50, LEAN ±0.30
  - UNC MIXED thresholds: LOCKED ±0.40, LEAN ±0.20
- Auxiliary: `confidence`, `recent_5yr_lean`, `last_three_party`, `switch_count`, `years_since_last_partisan`

## Analysis methodology

**Party affiliation** is behavior-derived, not self-declared. Per Ohio EOM Ch. 15, affiliation
reflects which party primary a voter participated in within the past two calendar years.
Election history columns are used as ground truth for lifetime trajectory analysis.

**Voter status** in the SWVF is either `ACTIVE` or `CONFIRMATION`. `CONFIRMATION` collapses
multiple internal substatus codes (NCOA movers, BMV/SSA mismatches, supplemental list maintenance).
High CONFIRMATION density combined with sparse recent election history is a concrete anomaly signal.

**Generational cohorts** follow [Pew Research Center definitions](https://pewrsr.ch/2HFp9rq):

| Generation | Birth years |
|---|---|
| Silent / Greatest | ≤ 1945 |
| Baby Boomers | 1946–1964 |
| Generation X | 1965–1980 |
| Millennials | 1981–1996 |
| Generation Z | 1997–2012 |
| Gen Alpha | ≥ 2013 |

## What stays out of git

`source/`, `working/`, `UNC_Exports/`, `*.xlsx`, `*.csv`, `*.txt`, and `logs/` are excluded via `.gitignore`.
Raw SWVF files contain PII and must never be committed. Aggregated dashboard JSON in `docs/data/`
contains no individual voter records and is safe to publish.

## Roadmap

- **Phase 2** — Roll-up aggregation: Wards, School Districts, Legislative Districts
- **Phase 3** — Diff engine + GIS: demographic deltas between subregions and parent geographies; precinct choropleth maps via Census TIGER shapefiles
- **Phase 4** — Dark data: unregistered resident matching via property records, Census blocks, USPS NCOA
- **Phase 5** — Temporal tracking: registration momentum, turnout anomaly detection, SaaS delivery

## License

MIT — Matthew F Reyes, 2026
