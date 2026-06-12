# Scoring Directory

This directory contains the logic and runners for the "Lean Prediction" engine. These scripts analyze voter primary ballot history to estimate partisan lean for unaffiliated (UNC) and crossover voters.

## 🧠 Core Logic

### `mixed_lean_predictor.py`
*   **Purpose:** The primary logic engine for recency-weighted partisan scoring.
*   **Method:** Applies an exponential decay function to primary ballot history. Recent ballots are weighted significantly higher than older ones.
*   **Classification:** Buckets voters into `LEAN_D`, `LEAN_R`, or `TRUE_MIXED` based on score thresholds.

## 🏃 Runners & Drivers

### `run_lean_predictor_all_cohorts.py`
*   **Purpose:** The primary driver for the scoring engine. 
*   **Function:** Automatically discovers all target CSVs in the `local/exports/` subdirectories and runs the `mixed_lean_predictor` against them in parallel using a `ProcessPoolExecutor`.

### `run_mixed_lean_predictor_all_counties.py`
*   **Purpose:** A specialized runner focused specifically on the "Mixed" cohort across all 88 counties.
*   **Output:** Aggregates a statewide summary of lean distribution.

### `unc_lifetime_d_predictor.py`
*   **Purpose:** A specific prediction model used for the Lifetime-D cohort analysis.
