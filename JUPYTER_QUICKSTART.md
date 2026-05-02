# Jupyter Notebook Quick Start — Ohio Voter Analysis
## VSCode Setup Guide

---

## Why Jupyter fits this workflow

Each stage of the pipeline — load, clean, enrich, summarise, export — maps
naturally to a notebook cell. You can run cells individually, inspect the
Polars DataFrame after each step, tweak a parameter, and re-run only the
affected cell without reloading 7.9M rows from disk. Polars DataFrames also
render as formatted HTML tables inline in the notebook output, which makes
exploratory analysis much faster than running a script and opening Excel.

---

## 1. Prerequisites

- **VSCode** — [code.visualstudio.com](https://code.visualstudio.com)
- **Python 3.11+** — verify with `python --version` in a terminal
- **Git** — already configured if you pushed the repo

---

## 2. Install VSCode Extensions

Open the Extensions panel (`Ctrl+Shift+X`) and install:

| Extension | Publisher | Purpose |
|---|---|---|
| Python | Microsoft | Language support, IntelliSense |
| Jupyter | Microsoft | Notebook UI, kernel management |
| Pylance | Microsoft | Type checking, autocomplete |

---

## 3. Create and Activate a Virtual Environment

Open a terminal inside VSCode (`Ctrl+`` `) pointed at the project folder:

```bash
# Create the virtual environment (one time only)
python -m venv .venv

# Activate it — Windows PowerShell
.venv\Scripts\Activate.ps1

# Activate it — Windows CMD
.venv\Scripts\activate.bat
```

VSCode will detect the new `.venv` and prompt you to select it as the
workspace interpreter. Click **Yes**. If it doesn't prompt, open the Command
Palette (`Ctrl+Shift+P`) → **Python: Select Interpreter** → choose
`.venv\Scripts\python.exe`.

---

## 4. Install Dependencies

With the virtual environment active:

```bash
pip install -r requirements.txt
```

This installs Polars, pandas, xlsxwriter, requests, beautifulsoup4, and
Jupyter itself (pulled in as a dependency of the Jupyter extension's kernel).
If Jupyter's kernel doesn't appear, install it explicitly:

```bash
pip install notebook ipykernel
python -m ipykernel install --user --name=voter-analysis
```

---

## 5. Create the Notebook

In the Explorer panel, right-click the project folder → **New File** →
name it `voter_analysis.ipynb`.

VSCode opens it in the notebook editor. In the top-right kernel picker,
select **voter-analysis** (or your `.venv` Python).

---

## 6. Notebook Cell Structure

Copy the cell blocks below in order. Each one is self-contained — if a
later step fails, re-run only that cell after fixing the issue rather than
restarting from scratch.

---

### Cell 1 — Imports and logging setup

```python
# Cell 1: Imports
# Run once per session. Sets up all libraries and the logger.
# The logger writes to logs/ and to the notebook output simultaneously.

import logging, sys
from pathlib import Path
from datetime import date

import polars as pl
import pandas as pd

# Import all functions from the analysis module so we don't duplicate code.
# voter_data_cleaner_v2.py must be in the same folder as this notebook.
from voter_data_cleaner_v2 import (
    setup_logging,
    load_voter_files,
    clean_voter_data,
    identify_election_cols,
    add_voter_participation,
    build_decade_summary,
    build_election_participation,
    build_district_breakdown,
    build_party_crosstabs,
    export_json,
    OHIO_COUNTIES,
)

log = setup_logging('notebook')
log.info('Environment ready.')
```

---

### Cell 2 — Configuration

```python
# Cell 2: Configuration
# Change COUNTY_NUMBER to analyse a different county, or set to None for all of Ohio.
# County numbers are zero-padded strings: '57' = Montgomery, '25' = Franklin, etc.

BASE_DIR      = Path().resolve()   # resolves to the folder the notebook is opened from
TXT_DIR       = BASE_DIR / "source" / "State Voter Files"
TXT_FILES     = sorted(TXT_DIR.glob("SWVF_*.txt"))

COUNTY_NUMBER = '57'    # Set to None to load all 88 counties (Ohio-wide)
COUNTY_NAME   = OHIO_COUNTIES.get(COUNTY_NUMBER, f'County {COUNTY_NUMBER}')

log.info('Files found: %d', len(TXT_FILES))
for f in TXT_FILES:
    log.info('  %s  (%.2f GB)', f.name, f.stat().st_size / 1e9)
```

---

### Cell 3 — Load

```python
# Cell 3: Load voter files
# Polars scans the files lazily and collects only the rows matching COUNTY_NUMBER.
# For a county this is fast (~10–30 s). For all of Ohio expect 2–4 minutes.

df = load_voter_files(TXT_FILES, county_number=COUNTY_NUMBER, logger=log)

# Inspect the raw schema before any cleaning
print(f"Rows: {len(df):,}   Columns: {len(df.columns)}")
df.head(3)   # renders as a formatted table in the notebook
```

---

### Cell 4 — Clean

```python
# Cell 4: Clean and enrich
# Parses dates, derives birth decade, normalises party labels.
# Rows with invalid birth years are dropped and logged.

df = clean_voter_data(df, log)

# Spot-check: party distribution after normalisation
df.group_by('PARTY_LABEL').len().sort('len', descending=True)
```

---

### Cell 5 — Participation metrics

```python
# Cell 5: Compute per-voter participation metrics
# Uses Polars sum_horizontal — fast single pass across all 89 election columns.

election_cols = identify_election_cols(df)
log.info('%d election columns: %s → %s', len(election_cols), election_cols[0], election_cols[-1])

df = add_voter_participation(df, election_cols, log)

# Quick sanity check: frequency distribution
df.group_by('Voter_Frequency').len().sort('len', descending=True)
```

---

### Cell 6 — Explore (repeat as needed)

```python
# Cell 6: Ad-hoc exploration
# This cell is your scratch space. Re-run it as many times as you like
# without affecting the cleaned DataFrame in memory.

# Example: top precincts by total voters
(
    df.group_by('PRECINCT_NAME')
      .agg(pl.len().alias('Total'), pl.col('PARTY_LABEL').eq('REP').sum().alias('REP'))
      .sort('Total', descending=True)
      .head(20)
)
```

---

### Cell 7 — Export JSON (web dashboard)

```python
# Cell 7: Write JSON files to docs/data/
# This replaces the sample data in the web dashboard with real analysis results.
# After running this cell, open docs/index.html in a browser to see live charts.

export_json(COUNTY_NAME, df, election_cols, log)
log.info('Open docs/index.html to view the updated dashboard.')
```

---

### Cell 8 — Export Excel

```python
# Cell 8: Write Excel workbook
# include_raw=True includes the full Voter Data sheet (safe at county scale).
# Switch to include_raw=False for Ohio-wide runs to stay under Excel's row limit.

from voter_data_cleaner_v2 import build_workbook

if COUNTY_NUMBER:
    output_path = BASE_DIR / f"county_{COUNTY_NUMBER}_analysis_{date.today()}.xlsx"
else:
    output_path = BASE_DIR / f"ohio_analysis_{date.today()}.xlsx"

build_workbook(
    df            = df,
    election_cols = election_cols,
    output_path   = output_path,
    county_name   = COUNTY_NAME,
    include_raw   = True,
    logger        = log,
)

print(f"Saved: {output_path}")
```

---

## 7. Kernel tips

| Situation | Action |
|---|---|
| Changed a function in `voter_data_cleaner_v2.py` | **Restart kernel** → Run All (the import in Cell 1 won't pick up changes otherwise) |
| Cell 3 already ran and you want to re-clean | Re-run Cell 4 only — no need to reload from disk |
| Memory pressure on Ohio-wide load | Set `COUNTY_NUMBER` to a specific county, or close other applications |
| Log file location | `logs/voter_analysis_YYYYMMDD_HHMMSS_notebook.log` |

---

## 8. Running the download pipeline

The notebook handles analysis only. To check for updated voter files and
download them first, run the pipeline script from the VSCode terminal:

```bash
python ohio_voter_pipeline.py
```

After it decompresses the new files into `source/State Voter Files/`, return
to the notebook and re-run from Cell 3.
