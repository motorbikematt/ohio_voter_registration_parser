# Handoff — Ohio Voter Analysis: Pending Fixes

This document is a prompt for a new session. Read the files listed under "Codebase
orientation" before touching any code.

---

## Project summary

Ohio Secretary of State voter registration analysis pipeline. Prototype covers
Montgomery County (~358K voters). Architecture:

- `ohio_voter_pipeline.py` — download orchestrator (scrapes SOS site, streams
  gz archives, decompresses to `source/State Voter Files/`)
- `voter_data_cleaner_v2.py` — analysis engine (Polars, xlsxwriter, JSON export)
- `voter_analysis.ipynb` — Jupyter notebook for step-by-step interactive analysis
- `docs/index.html` + `docs/data/*.json` — Chart.js web dashboard

The engine uses Polars `scan_csv()` with `infer_schema=False` and
`encoding='utf8-lossy'` (Ohio SOS files are Windows-1252). All 135 columns load
as strings; typed columns are cast explicitly in `clean_voter_data()`.

---

## Three pending fixes — implement all three

### Fix 1 — Log dropped rows instead of silently discarding them

**Where:** `clean_voter_data()` in `voter_data_cleaner_v2.py`, around the
birth-year filter block.

**Current behavior:** Rows with birth years outside 1900–current year are
dropped with a single WARNING log line showing only the count.

**Required behavior:** Before dropping, emit one WARNING log line per dropped
row containing at minimum: `SOS_VOTERID`, `DATE_OF_BIRTH`, and the raw parsed
`BIRTHYEAR` value. This lets the analyst cross-reference against the Ohio SOS
source file to determine whether the record is a data-entry error in the state
file or a parser bug on our side. Ohio's voter files have a known history of
subtle undocumented field changes between monthly releases.

Keep the existing summary WARNING (count of dropped rows) after the per-row
logging so the aggregate is still visible in the log.

---

### Fix 2 — Include source-file timestamp in Excel output filenames

**Where:** Cell 8 of `voter_analysis.ipynb` and the equivalent path-construction
logic in `voter_data_cleaner_v2.py` (`build_workbook()` call sites).

**Current behavior:** Filenames use `date.today()` (the date the analysis was
run), e.g. `county_57_analysis_2026-05-01.xlsx`.

**Required behavior:** Filenames should reflect the effective date of the source
voter file — not the run date. The download pipeline already captures
`Last-Modified` HTTP headers from the Ohio SOS server and stores them in
`download_manifest.json`. Use that timestamp as the source date.

Preferred filename format: `county_57_analysis_src20260425.xlsx` (or similar
unambiguous format that distinguishes source date from run date). If
`download_manifest.json` is absent or unparseable, fall back to `date.today()`
and log a WARNING explaining the fallback.

Update the output path logic in both the notebook Cell 8 and anywhere
`build_workbook()` constructs or receives `output_path`.

---

### Fix 3 — Redefine Voter_Frequency to use generals-only denominator

**Where:** `add_voter_participation()` in `voter_data_cleaner_v2.py`.

**Root cause:** `Voter_Frequency` is currently `Elections_Voted / Elections_Eligible`
where `Elections_Eligible` counts all 89 elections (primaries, generals, and
specials) since 2000. The ≥75% "Frequent" threshold is unreachable in practice —
a voter who participates in every general election since 2000 has only ~25/89 ≈
28% turnout by this metric. As a result the "Frequent" bucket is always empty
for any county and will remain empty statewide.

**Required behavior:** Split participation metrics into two parallel sets:

1. **All-elections metrics** (keep existing column names for backward compatibility
   with the Excel workbook and JSON schema):
   - `Elections_Eligible` — all election types, as today
   - `Elections_Voted` — all election types, as today
   - `Turnout_Rate` — all-elections rate

2. **Generals-only metrics** (new columns):
   - `General_Eligible` — count of general elections held on/after registration date
   - `General_Voted` — generals in which the voter participated
   - `General_Turnout_Rate` — `General_Voted / General_Eligible`

Base `Voter_Frequency` on `General_Turnout_Rate` instead of `Turnout_Rate`.
Keep the existing thresholds (`FREQ_HIGH = 0.75`, `FREQ_LOW = 0.25`) — they are
appropriate when the denominator is generals only.

A general election column is identified by `col.startswith('GENERAL-')`. The
existing `identify_election_cols()` function already returns all election columns;
filter within `add_voter_participation()` to produce the generals-only subset.

Update the web dashboard JSON schema and Excel workbook sheets that display
`Voter_Frequency` distributions — the labels ('Frequent (≥75%)', etc.) can stay
the same since they are now meaningful. Add the `General_Eligible` and
`General_Voted` columns to the raw Voter Data Excel sheet and optionally to the
precinct/district summary tables if useful.

---

## Codebase orientation — read these files first

1. `voter_data_cleaner_v2.py` — full engine; read completely before editing
2. `voter_analysis.ipynb` — notebook; check Cell 8 for filename logic
3. `download_manifest.json` — present after `ohio_voter_pipeline.py` has run;
   contains per-file `last_modified` strings from the Ohio SOS HTTP headers
4. `docs/data/montgomery_*.json` — live JSON output schema; Fix 3 must not
   break the keys that `index.html` / `charts.js` consume

Do not change the `OHIO_COUNTIES` dict, the column-rename logic in
`load_voter_files()`, or the `DISTRICT_FIELDS` list — those are stable.
