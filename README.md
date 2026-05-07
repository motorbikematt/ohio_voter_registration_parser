# Ohio Voter Registration Analysis

Download, clean, and analyse the Ohio Secretary of State statewide voter file (SWVF).
Outputs interactive web dashboard JSON for all 88 counties and optional Excel workbooks.

## What's in this repo

| File | Purpose |
|---|---|
| `ohio_voter_pipeline.py` | Main entry point — interactive menu to run statewide or targeted county analysis |
| `voter_data_cleaner_v2.py` | Core analysis engine — Polars-based ingestion, cleaning, participation metrics, JSON + Excel export |
| `precinct_unc_export.py` | Standalone export: D + UNC Lifetime-D voter counts per precinct, all 88 counties |
| `voter_lookup.py` | Individual voter lookup utility |
| `export_unc_targets.py` | Export unaffiliated voter targeting data |
| `mixed_lean_predictor.py` | UNC voter lean prediction model |
| `run_lean_predictor_all_cohorts.py` | Batch runner — lean predictor across all cohorts |
| `run_mixed_lean_predictor_all_counties.py` | Batch runner — lean predictor across all 88 counties |
| `docs/` | Web dashboard (HTML + Chart.js) with county, city, and precinct drill-down scope tabs |

## Requirements

- Python 3.11+
- Dependencies: `pip install -r requirements.txt`

Key libraries: Polars (vectorized out-of-core processing), PyArrow (Parquet), xlsxwriter/openpyxl (Excel), requests/beautifulsoup4 (optional SOS scrape).

## Quick start

### 1. Set up the environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
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

### 4. View the dashboard

Open `docs/index.html` locally, or view the live dashboard on GitHub Pages:
[https://github.com/motorbikematt/ohio_voter_registration_parser](https://github.com/motorbikematt/ohio_voter_registration_parser)

The dashboard supports three scope tiers: **County** (default), **City**, and **Precinct**.
Precinct drill-down shows per-precinct party composition and UNC shadow charts for every
precinct in the selected county.

## Output

- **Web dashboard** — `docs/index.html` with Chart.js charts; data in `docs/data/` and `docs/manifest.json`
- **Excel workbook** — `ohio_analysis_YYYY-MM-DD.xlsx` (county summary) or `county_NN_analysis_YYYY-MM-DD.xlsx`
  - Sheets: Decade Summary, Participation, District Breakdown, Party Cross-tabs
  - Ohio-wide builds use a County Summary sheet (raw 7.9M rows exceeds Excel's row limit)
- **Parquet cache** — `source/parquet/COUNTY_NUMBER=NN/` — fast reload for subsequent runs
- **Error log** — `working/errors/invalid_birthyear_<run>.csv` — rows dropped for unparseable birth dates
- **Run logs** — `logs/voter_analysis_YYYYMMDD_HHMMSS.log`

## Data source

Ohio Secretary of State — [Statewide Voter File](https://www6.ohiosos.gov/ords/f?p=VOTERFTP:STWD)

Four pipe-delimited archives covering county ranges 1–22, 23–44, 45–66, and 67–88.
Updated monthly. 46 static columns + 89 dynamic election history columns per row (~7.9M rows statewide).
Join key: `SOS_VOTERID` (statewide unique). County numbering follows the official SOS administrative
index: 01–88, strictly alphabetical by county name.

## Analysis methodology

**Party affiliation** is behavior-derived, not self-declared. Per Ohio EOM Ch. 15, affiliation
reflects which party primary a voter participated in within the past two calendar years.
Election history columns are used as ground truth for trajectory analysis.

**Voter status** in the SWVF is either `ACTIVE` or `CONFIRMATION`. `CONFIRMATION` collapses
multiple internal substatus codes (NCOA movers, BMV/SSA mismatches, supplemental list maintenance).
High CONFIRMATION density combined with sparse recent election history is a concrete anomaly signal.

**UNC Lifetime-D** classifies unaffiliated (no party) voters whose entire primary history
consists exclusively of Democratic ballots — a targeting signal for GOTV outreach.

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

`source/`, `working/`, `*.xlsx`, `*.csv`, `*.txt`, and `logs/` are excluded via `.gitignore`.
Raw SWVF files contain PII and must never be committed. Aggregated dashboard JSON in `docs/data/`
contains no individual voter records and is safe to publish.

## Roadmap

- **Phase 2** — Roll-up aggregation: Wards, School Districts, Legislative Districts
- **Phase 3** — Diff engine + GIS: demographic deltas between subregions and parent geographies; precinct choropleth maps via Census TIGER shapefiles
- **Phase 4** — Dark data: unregistered resident matching via property records, Census blocks, USPS NCOA
- **Phase 5** — Temporal tracking: registration momentum, turnout anomaly detection, SaaS delivery

## License

MIT — Matthew F Reyes, 2026
