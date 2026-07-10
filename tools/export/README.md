# tools/export/

Scripts that turn the enriched voter data into deliverables for humans — Excel workbooks,
target-list CSVs, and cloud uploads. Unlike `tools/admin/`, these read PII (names, addresses)
and write into `local/exports/` / `UNC_Exports/`, which are gitignored — never GitHub Pages data.

### `precinct_party_export.py`
- **Function:** Interactive tool that exports a multi-tab Excel workbook of voter names,
  addresses, and all source columns, split into the 7-tab partisan-spectrum cohort taxonomy
  (Pure_R, UNC_Lapsed_R, Mixed_Active, Mixed_Lapsed, UNC_No_Primary, UNC_Lapsed_D, Pure_D) that
  mirrors the public dashboard's doughnut chart colors. Precinct-mode workbooks also get 5 embedded
  charts (party doughnut, age-by-decade, age-by-generation, party×decade, party×generation) built
  from COUNTIFS formulas over the data tabs.
- **Inputs:** `local/source/parquet/COUNTY_NUMBER={n}/` (interactive county + precinct-or-whole-county
  choice), classified via `voter_data_cleaner_v2.classify_all_voters_primary_history()`.
- **Outputs:** `local/exports/Workbooks/{County}_{Precinct}_voters.xlsx` or
  `{County}_all_voters.xlsx`.
- **Usage:** `python precinct_party_export.py` (interactive menu; run from repo root so the
  `voter_data_cleaner_v2` import resolves).
- **Security:** output directory is gitignored — no PII leaves it.

### `export_unc_targets.py`
- **Function:** Standalone prototype that reads raw `SWVF_*.txt` files, filters to one county, and
  emits CSV target lists across two taxonomies: (1) legacy UNC-only classes (LIFETIME_D, LIFETIME_R,
  MIXED, NO_HISTORY) plus CURRENT_D/CURRENT_R, and (2) the full universal cohort taxonomy
  (ALL_AFFILIATED_D/R, PURE_D/R, D/R_CROSSOVER sorted by lean_score) via the pipeline's shared
  classifier. All outputs preserve source columns verbatim with computed columns appended.
- **Inputs:** one or more `local/source/State Voter Files/SWVF_*.txt` files (`--input`, repeatable),
  a county number and slug.
- **Outputs:** `local/exports/{Lifetime_D,Lifetime_R,Mixed,No_History,Current_D,Current_R,
  All_Affiliated_D,All_Affiliated_R,Pure_D,Pure_R,D_Crossover,R_Crossover}/{county}_{CLASS}_targets.csv`.
- **Usage:**
  `python export_unc_targets.py --county 57 --county-name montgomery --input "local/source/State Voter Files/SWVF_45_66.txt" [--output-dir DIR]`
- **Security:** output directory must be gitignored before running; PII never leaves it.

### `precinct_unc_export.py`
- **Function:** For every precinct across all 88 Ohio counties (or one county via `--county`),
  computes registration totals and cohort breakdowns (pure D/R, D/R crossover, UNC-lifetime-D/R,
  new registrants) and derives the combined "D + UNC Lifetime-D" count and percentage per precinct —
  the core targeting metric.
- **Inputs:** `local/source/State Voter Files/SWVF_*.txt` (builds/reads the Parquet cache by default;
  `--no-parquet` forces raw CSV ingestion).
- **Outputs:** one CSV per county —
  `local/exports/Precinct_Summary/{county_name}_precinct_d_unc.csv` — plus a statewide rollup
  `ohio_precinct_d_unc.csv` (skipped when `--county` is passed).
- **Usage:** `python precinct_unc_export.py [--no-parquet] [--county 57]`

### `upload_to_gdrive.py`
- **Function:** One-off utility that uploads `docs/cohort_definitions.md` to Google Drive as a
  native Google Doc, using OAuth2 (prompts a local browser consent flow on first run, caches the
  token afterward). Not part of the voter pipeline — a documentation-publishing convenience script.
- **Inputs:** `docs/cohort_definitions.md`; `credentials.json` (OAuth client secret, project root,
  gitignored) and `token.json` (cached credentials, created on first run).
- **Outputs:** a new Google Doc in the authenticated user's Drive; prints the file ID and view link.
- **Usage:** `python tools/export/upload_to_gdrive.py`
- **Requires:** `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`.

## Empty / stub

### `__init__.py`
Empty — makes `tools/export/` importable as a package.
