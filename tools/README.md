# Tools Directory

This directory contains standalone utilities, maintenance scripts, and specialized data exporters for the Ohio Voter Registration project. These tools are separate from the core pipeline logic but provide essential functionality for data acquisition, verification, and stakeholder delivery.

## 🛠 Unified Management

### `precinct_key_manager.py`
*   **Purpose:** The central utility for sourcing and aggregating Ohio precinct keys.
*   **Function:** Combines scraping and aggregation into a single interface. 
    *   **Scrape Mode:** Extracts "Beginning Precinct" dropdowns from BoE `vtrapp` portals using `curl_cffi` and `BeautifulSoup`.
    *   **Aggregate Mode:** Compiles all county CSVs into a master Excel workbook with formatted headers and frozen panes.
*   **Menu Options:** 1. Export CSVs only, 2. Workbook only, 3. Both.
*   **Output:** CSVs in `local/source/precinct_keys/` and `precinct_keys_master.xlsx` in the root.

## 🧹 Maintenance & Cleaning

### `clean_precinct_keys.py`
*   **Purpose:** A surgical utility to clean redundant columns from the scraped precinct CSVs.
*   **Function:** Removes the `name` and `sub` columns and preserves the `precinct_label` as the source of truth across all 88 counties.

## 📊 Specialized Exporters

### `precinct_party_export.py`
*   **Purpose:** Generates a 7-tab Excel workbook for a specific county or precinct, segmented by partisan cohort.
*   **Output:** `local/exports/Workbooks/{County}_all_voters.xlsx`.

### `precinct_unc_export.py`
*   **Purpose:** Computes and exports D + UNC Lifetime-D voter counts per precinct for all 88 counties.
*   **Output:** `local/exports/Precinct_Summary/`.

### `export_unc_targets.py`
*   **Purpose:** A prototype script for emitting filtered target lists for specific partisan cohorts from raw SWVF files.

## 🔍 Verification & Discovery

### `voter_analysis.ipynb`
*   **Purpose:** Active Jupyter notebook for exploratory data analysis (EDA) and prototyping.
*   **Function:** Used for testing new classification logic and generating ad-hoc visualizations.

### `voter_lookup.py`
*   **Purpose:** An interactive CLI utility to search for individual voters by name across the statewide data.
*   **Usage:** `python tools/voter_lookup.py --first "Jane" --last "Smith"`

### `test_jurisdiction_collisions.py`
*   **Purpose:** Scans all county data to detect jurisdiction names (e.g., "Washington Township") that exist in multiple counties.
*   **Output:** Generates `collision_report.md`.

### `admin/validate_jurisdiction_fields.py`
*   **Purpose:** Data-validation gate for the municipality fields in a new SWVF drop. Confirms the per-county field coverage that the pipeline's city resolver (`_dominant_city_per_precinct`) depends on, and flags precincts a postal-city fallback would mislabel.
*   **Why it exists:** The Ohio SWVF ([official layout](https://www6.ohiosos.gov/ords/f?p=111:2)) carries two unrelated location families — authoritative jurisdiction (`CITY`/`VILLAGE`/`WARD`/`TOWNSHIP`) and postal address (`RESIDENTIAL_CITY`). Backfilling a blank `CITY` from the postal column mislabels township precincts with their post-office city (e.g. `WASHINGTON TWP F` → `KETTERING`). The resolver instead walks a hierarchy: `CITY → VILLAGE → WARD-prefix → TOWNSHIP (= not a city) → RESIDENTIAL_CITY` (last resort).
*   **Reports:** (1) per-county CITY coverage; (2) hierarchy-coverage table for blank-CITY counties showing which fallback column covers them, and the *true* postal-last-resort set (counties with no authoritative column — currently only Wyandot); (3) township/village precincts a postal fallback would mislabel.
*   **Usage:** `python tools/admin/validate_jurisdiction_fields.py [--strict] [--show N]`. `--strict` exits non-zero on HIGH-severity mislabels so it can gate a pipeline run in CI.

### `run_city_groupings.py`
*   **Purpose:** A simple wrapper to trigger the generation of city-level chart JSON files for the web dashboard.
