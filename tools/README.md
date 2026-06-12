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

### `run_city_groupings.py`
*   **Purpose:** A simple wrapper to trigger the generation of city-level chart JSON files for the web dashboard.
