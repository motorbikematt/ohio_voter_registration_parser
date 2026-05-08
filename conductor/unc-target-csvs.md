# Implementation Plan: UNC Shadow Partisan CSV Exports

## Objective
Generate actionable target lists (CSVs) containing PII (names, addresses, precincts) for voters identified as "Shadow Partisans" (e.g., UNC voters with a Lifetime D or Lifetime R primary voting history). These lists must be output securely and strictly excluded from version control.

## Key Files & Context
- **`voter_data_cleaner_v2.py`**: The core analysis engine. We will add a new export function here utilizing the existing `classify_unc_primary_history()` output.
- **`ohio_voter_pipeline.py`**: The orchestration script. We will update the interactive prompt to allow users to opt-in to generating these target lists.
- **`.gitignore`**: Must be updated to ignore the new `exports/` directory to prevent PII leakage to GitHub.

## Implementation Steps

### 1. Security First: Update `.gitignore`
Before writing any new data files, update `.gitignore` to explicitly exclude the directory where the CSVs will be saved.
- Add `exports/` to `.gitignore`.

### 2. Core Logic: `voter_data_cleaner_v2.py`
Add a new function `export_unc_target_csvs(county_name, df, primary_cols, logger)`:
- Call the existing `classify_unc_primary_history(df, primary_cols, logger)`.
- If the result is empty, log and return early.
- Perform an `inner_join` between the original `df` and the classified results on `SOS_VOTERID`.
- Select the relevant PII and statistical columns: `SOS_VOTERID`, `FIRST_NAME`, `LAST_NAME`, `RESIDENTIAL_ADDRESS1`, `CITY`, `ZIP`, `PRECINCT_NAME`, `total_primaries`, `d_primaries`, `r_primaries`, `unc_class`.
- Create the `exports/` directory if it doesn't exist.
- Group the joined DataFrame by `unc_class` and iterate.
- For each group (e.g., `LIFETIME_D`), write a CSV to `exports/{county_slug}_{unc_class}_targets.csv`.

### 3. Pipeline Integration: `ohio_voter_pipeline.py`
Update the interactive prompt and dispatch logic to offer the CSV export.
- Modify `prompt_next_step()` to include an option for generating CSV target lists alongside the JSON/Excel options. For example:
  - `[1] Full Ohio → web dashboard JSON only`
  - `[2] Full Ohio → web dashboard JSON + statewide Excel workbook`
  - `[3] Full Ohio → web dashboard JSON + Excel + UNC Target CSVs`
  - `[4] Exit`
- Update `_dispatch()` to handle the new option. If selected, call the new `export_unc_target_csvs` function for each county processed (or the combined dataset, depending on scaling needs).

### 4. Update Notebook (Optional but Recommended)
- Update `voter_analysis.ipynb` to import and demonstrate calling `export_unc_target_csvs` in a new cell, so interactive users can also generate the lists.

## Verification & Testing
1. **Security Check:** Verify `git status` ignores the `exports/` folder after a test run.
2. **Data Integrity Check:** Inspect a generated CSV (e.g., `montgomery_LIFETIME_D_targets.csv`) to ensure:
   - Only UNC voters are present.
   - PII columns are correctly mapped.
   - Primary vote counts align with the classification.
3. **Execution Check:** Run `ohio_voter_pipeline.py` and select the new option to ensure the end-to-end flow executes without errors.