# Ohio Voter Registration Analysis

Download, clean, and analyse Ohio Secretary of State statewide voter files.
Outputs a formatted Excel workbook and a live web dashboard backed by JSON.

## What's in this repo

| File | Purpose |
|---|---|
| `ohio_voter_pipeline.py` | Checks the Ohio SOS site for updated voter files, downloads and decompresses them, then prompts for analysis |
| `voter_data_cleaner_v2.py` | Analysis engine — loads SWVF files with Polars, cleans data, computes participation metrics, exports Excel + JSON |
| `voter_analysis.ipynb` | Jupyter notebook for interactive step-by-step analysis in VSCode |
| `docs/` | Web dashboard (HTML + Chart.js) — reads JSON files from `docs/data/` |

## Requirements

- Python 3.11+
- Dependencies: `pip install -r requirements.txt`

## Quick start

### 1. Set up the environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate (PowerShell)
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Download voter files

```powershell
python ohio_voter_pipeline.py
```

This checks the [Ohio SOS voter file page](https://www6.ohiosos.gov/ords/f?p=VOTERFTP:STWD)
for updated files, downloads the four SWVF `.gz` archives, and decompresses them
into `source/State Voter Files/`.

### 3. Run the analysis

**Option A — Jupyter notebook (recommended for exploration):**
Open `voter_analysis.ipynb` in VSCode and run cells top to bottom.

**Option B — Script directly:**
```powershell
python voter_data_cleaner_v2.py
```

### 4. View the dashboard

Open `docs/index.html` in a browser after running the analysis.
The JSON files in `docs/data/` are updated automatically — no manual steps needed.

## Output

- **Excel workbook** — `county_NN_analysis_YYYY-MM-DD.xlsx` or `ohio_analysis_YYYY-MM-DD.xlsx`
  - County-scale: includes raw Voter Data sheet + Decade Summary, Participation, District Breakdown, Party Cross-tabs
  - Ohio-wide: County Summary replaces raw data (7.9M rows exceeds Excel's row limit)
- **Web dashboard** — `docs/index.html` with interactive Chart.js charts per county
- **Logs** — `logs/voter_analysis_YYYYMMDD_HHMMSS.log` (timestamped per run)

## Data source

Ohio Secretary of State — [Statewide Voter File](https://www6.ohiosos.gov/ords/f?p=VOTERFTP:STWD)

Files are updated monthly and split into four archives covering county ranges 1–22, 23–44, 45–66, and 67–88.
The pipeline script handles download, decompression, and change detection automatically.

## What stays out of git

`source/`, `*.xlsx`, `*.csv`, `*.txt`, and `logs/` are all excluded via `.gitignore`.
The `.txt` exclusion is intentionally broad — an extra conservative guard against
accidentally uploading large government data files. Documentation in this repo uses `.md`.

## Scaling

This prototype covers Montgomery County (county 57, ~300K voters).
The analysis engine is built on [Polars](https://pola.rs/) and handles the full
Ohio statewide file (~7.9M rows across 4 files) without modification.
The next planned stage is matching against Census/USPS address data to identify
unregistered adult residents, followed by GIS visualisation using Census TIGER shapefiles.

## License

MIT — Matthew F Reyes, 2026
