# Running the Analysis Locally in VSCode

## Prerequisites

- Python 3.11+
- VSCode with the **Python** and **Jupyter** extensions installed

## One-time setup

```powershell
# 1. Create and activate the virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install all dependencies (includes Polars, pandas, Jupyter kernel, etc.)
pip install -r requirements.txt
```

**Tip:** If PowerShell says `pip` is not recognised, the venv isn't activated yet.
Run `.venv\Scripts\Activate.ps1` first — you should see `(.venv)` in your prompt.

## Download voter files

Before analysing, run the pipeline script to fetch the latest Ohio SOS files:

```powershell
python ohio_voter_pipeline.py
```

This checks for updated files, downloads the four `.gz` archives, and decompresses
them into `source/State Voter Files/`. Re-running it when files haven't changed is
safe and fast — it exits immediately after confirming everything is current.

## Option A: Jupyter notebook (recommended)

1. Open `voter_analysis.ipynb` in VSCode
2. Select the `.venv` kernel when prompted (top-right kernel picker)
3. Run cells top to bottom — Cell 2 is the only one you need to edit (county number)

## Option B: Script directly

```powershell
python voter_data_cleaner_v2.py
```

This prompts interactively for county or Ohio-wide mode and writes output to the project folder.

## Output locations

| Output | Path |
|---|---|
| Excel workbook | `county_57_analysis_2026-05-01.xlsx` (county) or `ohio_analysis_2026-05-01.xlsx` |
| Web dashboard data | `docs/data/` — open `docs/index.html` to view |
| Logs | `logs/voter_analysis_YYYYMMDD_HHMMSS.log` |

## Troubleshooting

| Problem | Solution |
|---|---|
| `pip` not recognised | Activate the venv first: `.venv\Scripts\Activate.ps1` |
| `ModuleNotFoundError: No module named 'polars'` | Run `pip install -r requirements.txt` with the venv active |
| `No SWVF_*.txt files found` | Run `ohio_voter_pipeline.py` first to download and decompress voter files |
| Kernel not visible in VSCode | Run `python -m ipykernel install --user --name=voter-analysis` then reload VSCode |
| `ComputeError: invalid utf-8 sequence` | This is handled automatically — the loader uses `latin-1` encoding for Ohio SOS files |
