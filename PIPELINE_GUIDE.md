# Ohio Voter Pipeline — Operations Guide

**Script**: `ohio_voter_pipeline.py`  
**Last updated**: 2026-05-09

---

## Prerequisites

1. **Python venv** — activate before every run:
   ```powershell
   cd "D:\vibe\election-data (1)"
   .\.venv\Scripts\activate
   ```

2. **Required packages** — should already be installed; verify once if anything fails:
   ```powershell
   pip install polars orjson psutil xlsxwriter openpyxl requests beautifulsoup4
   ```

3. **Source voter files** — four pipe-delimited `.txt` files in `source\State Voter Files\`:
   ```
   SWVF_1_22.txt
   SWVF_23_44.txt
   SWVF_45_66.txt
   SWVF_67_88.txt
   ```

4. **Parquet cache** — built automatically on the first run. After that, all runs load from
   `source\parquet\` (88 Hive partitions, ~7.9 M rows × 135 cols). Build takes ~4 minutes;
   subsequent loads take under 60 seconds.

---

## Running the pipeline

```powershell
cd "D:\vibe\election-data (1)"
.\.venv\Scripts\activate
python ohio_voter_pipeline.py
```

The script asks two questions before doing any real work:

1. **Check for updated voter files?** — answer `N` unless you have reason to believe Ohio SOS
   has published a new snapshot. The SOS site frequently blocks automated requests with 403 or
   CAPTCHA, so scraping is best-effort.

2. **Which analysis step?** — see the menu below.

---

## Menu options

```
[1]  Full rebuild — counties + precincts + all jurisdictions → JSON  (default)
[2]  Full rebuild → JSON + Excel workbook
[3]  Counties + precincts only → JSON  (skip jurisdictional groupings)
[4]  Jurisdictional groupings only → JSON  (cities, townships, districts, etc.)
[5]  Selected counties only → JSON
[L]  List all 88 counties with official state numbers
[0]  Exit
```

### Option 1 — Full rebuild (use this for new data)

Runs two passes back-to-back:

**Pass A** — `voter_data_cleaner_v2.py` processes all 88 counties from the Parquet cache,
writes 6 chart JSON files per county + per precinct into `docs/data/`, and updates
`manifest.json`. This is the slow pass (~20–40 min depending on hardware).

**Pass B** — `jurisdictional_groupings.py` reads the enriched Parquet (already classified by
Pass A), then aggregates all 12 jurisdictional types: cities, townships, villages, local school
districts, city school districts, exempted village school districts, state senate districts,
state representative districts, congressional districts, county court districts, municipal court
districts, and court of appeals. Progress is printed as a rolling counter:

```
  [  1/212] cities: Columbus                                         
  [  2/212] cities: Cleveland                                        
  ...
```

**Option 2** adds an Excel workbook export after both passes. The workbook peaks at ~45 GB RSS
during generation — only run this if you have sufficient RAM available.

### Option 3 — Counties + precincts only

Same as Pass A above. Use this if you changed the cohort classifier and need to rebuild county
and precinct JSON without re-running jurisdictional groupings.

### Option 4 — Jurisdictional groupings only

Runs only Pass B. Use this if county JSON is already current and you only need to refresh
city/township/district data (e.g., after fixing a bug in `jurisdictional_groupings.py`).

The script reads the enriched Parquet directly — it does not depend on county JSON output.

### Option 5 — Selected counties only

Prompts for one or more county names or numbers (comma-separated). Builds county + precinct
JSON for only those counties. Useful for spot-checking a classifier change without waiting for
all 88 counties to process.

---

## Expected output locations

All JSON output lands in `docs/data/`. After a full rebuild you will see:

```
docs/data/
  adams_party_affiliation.json          ← county-level, one file per chart type
  adams_decade_distribution.json
  adams_party_by_decade.json
  adams_party_by_generation.json
  adams_unc_shadow.json
  adams_cohort_counts.json
  adams_precinct_*.json                 ← precinct-level (if precinct charts enabled)
  ...
  adams_city_party_affiliation.json     ← city-level (from Pass B)
  adams_city_decade_distribution.json
  ...
  adams_township_party_affiliation.json ← township-level
  ...                                   ← similar structure for all 12 jurisdiction types
```

`manifest.json` is updated by each pass and controls what the dashboard renders.

---

## If it looks frozen

The script is not frozen — it is pre-partitioning or aggregating. Each jurisdictional type
prints a rolling counter (`[  N/TOTAL]`) that updates in place. If you see no output for more
than a few seconds during the county pass (Pass A), that is normal — the Parquet load and
classification are single-threaded and quiet.

Typical runtimes on a 16-core / 64 GB machine:
- Parquet load + classify: ~60 s
- County pass (88 counties, no precincts): ~20 min
- County pass (with precincts): ~35 min
- Jurisdictional groupings (all 12 types): ~10–20 min

---

## Log files

Every run writes a timestamped log to `logs\`:

```
logs\voter_analysis_YYYYMMDD_HHMMSS_pipeline.log    ← county pass
logs\groupings_YYYYMMDD_HHMMSS.log                  ← jurisdictional pass
```

If something fails, the log will say where. Common entries to look for:
- `ERROR  Enriched parquet not found` — parquet cache missing; run option 1 or 3 first.
- `WARNING  download_manifest.json not found` — expected on first run; not an error.
- `[N/TOTAL]` success rate line at the end of each jurisdictional type — check for low rates.

---

## Common errors and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Script exits immediately with no output | Missing `if __name__ == '__main__': main()` at end of file | Check last 3 lines of `ohio_voter_pipeline.py` |
| `Enriched parquet not found` | Cache not yet built or path wrong | Run option 1 or 3 first |
| `ModuleNotFoundError: polars` | Running outside venv | `.\.venv\Scripts\activate` |
| `WinError 1450` during Excel pass | Insufficient handles (ThreadPoolExecutor leak) | Restart Python; reduce `max_workers` in v2 |
| `git: cannot lock ref` | Stale index.lock from a failed commit | `Remove-Item "D:\vibe\election-data (1)\.git\index.lock" -Force` |
| A jurisdiction type shows 0/N success | Enriched Parquet missing `cohort_family` column | Ensure `clean_voter_data()` is called before aggregation |

---

## Deploy to GitHub Pages

After a successful run:

```powershell
cd "D:\vibe\election-data (1)"
git add docs/data/ manifest.json
git commit -m "Rebuild dashboard JSON — $(Get-Date -Format 'yyyy-MM-dd')"
git push origin main
```

GitHub Actions rebuilds Pages in ~40 seconds. The dashboard is live at:
https://motorbikematt.github.io/ohio_voter_registration_parser/

---

## Verify the dashboard

1. Open the URL above.
2. Select **County** scope — verify charts render for a sample county (e.g., Montgomery).
3. Select **City** scope — verify cities appear in the Geo filter and 6 charts render.
4. Select **Precinct** scope — verify precincts load and deep-link works
   (`?county=Montgomery&geo=precinct-detail&precinct=DAYTON+8-B`).
5. Check cohort counts on the Cohort Summary table match expected ballpark figures.
