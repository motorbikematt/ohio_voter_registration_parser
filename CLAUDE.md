# CLAUDE.md – Ohio Voter Registration Parser

## ⚠ FILE EDITING PROTOCOL — READ BEFORE TOUCHING ANY FILE

**Check line count first. Always.**

| File length | Required method |
|---|---|
| ≤ 300 lines | Edit tool is permitted |
| > 300 lines | **STOP. Write a Python patch script. No exceptions.** |

### Python patch script template (for files > 300 lines)

```python
with open('path/to/file.py', encoding='utf-8') as f:
    src = f.read()

old = """<exact block, < 10 lines, unique in file>"""
new = """<replacement>"""

assert src.count(old) == 1, f"Expected 1 match, found {src.count(old)}"
src = src.replace(old, new)

with open('path/to/file.py', 'w', encoding='utf-8') as f:
    f.write(src)

# Confirm: print only the affected line numbers
for i, line in enumerate(src.splitlines(), 1):
    if any(l in line for l in new.splitlines() if l.strip()):
        print(f"  line {i}: {line[:80]}")
```

**Why this rule exists:** The Edit tool silently truncates large files mid-edit, corrupting everything after the insertion point. Each truncation costs multiple repair cycles and wasted tokens. The Python script approach is immune to this failure mode.

**No diffs. No exceptions. This rule overrides default behavior.**

---

## Project Overview

Data processing pipeline converting raw Ohio voter registration data into actionable intelligence for a Civic Tech startup. Core architecture: bottom-up geospatial aggregation — ingest the complete Statewide Voter File (SWVF) for all 88 counties, parse to the atomic precinct level, roll up into parent jurisdictions (wards, cities, school districts, congressional districts). Primary output: comparative "diff" analytics between subregions and parent geographies. Phase 3+ integrates external datasets (census, property records, USPS) for unregistered resident matching and GIS visualization.

## Data Processing Philosophy

- **Memory-Safe Scale**: Bypass Pandas. Use **Polars** or **DuckDB** for out-of-core, vectorized processing across all 88 counties.
- **Hierarchical Storage**: No flat CSVs. Use **Parquet** (partitioned by county/region) or **GeoParquet** for all intermediate and final layers.
- **Stakeholder Delivery**: Final aggregated outputs go to `.xlsx` via `xlsxwriter` or `openpyxl`. Never load raw files into Excel.
- **Preserve Traceability**: All data retains provenance back to Ohio BoE publication timestamps, original column headers, and source URLs.
- **Zero-Trust Security**: Never commit raw PII or unaggregated voter files to GitHub. Maintain `.gitignore` for `./working/` and `./source/`.

## Delivery Architecture

**Web**: React (Vite) SPA on GitHub Pages. WebGL mapping via Deck.gl or MapLibre for precinct-polygon rendering. Lazy-load county data on demand. Full-screen map + side-panel anomaly feed. Dark/light mode; charts must be screenshot- and print-ready.

**Stakeholder (Excel)**: Final aggregated outputs only — never raw files. Use `xlsxwriter` or `openpyxl`. Freeze top rows, bold headers, auto-width columns, apply filters, conditional formatting on anomalies. Output must be print-ready with zero manual formatting.

## Phases & Deliverables

- **Phase 1 — Atomic Ingestion** → Parquet: Parse SWVF to precinct level. Core schemas: Party Affiliation, Age/Generation, Registration Status.
- **Phase 2 — Roll-Up** → Parquet: Aggregate into Wards, Cities, School Districts, Legislative Districts, Counties.
- **Phase 3 — Diffs** → Diff Engine + GIS: Demographic/registration deltas between any subregion and its parent. Choropleths and heatmaps, statewide → precinct drill-down.
- **Phase 4 — Dark Data** → Unregistered Resident Matrix: Integrate property records, census blocks, USPS NCOA for probabilistic unregistered-resident matching (GOTV).
- **Phase 5 — Temporal Tracking** → Anomaly Alert System: Demographic shifts, registration momentum, turnout variation over time. Algorithmic flagging of underperforming demographics, unaffiliated concentrations, confirmation spikes, and bright spots. SaaS delivery to subscribers.

## File Locations

- **Raw source data**: `D:\vibe\election-data (1)\source\`
- **Working/intermediate files**: `D:\vibe\election-data (1)\`
- **Final deliverables**: `D:\vibe\election-data (1)\`

## Data Schema Reference

Source: 4 split flat files (`SWVF_1_22.txt`, `SWVF_23_44.txt`, `SWVF_45_66.txt`, `SWVF_67_88.txt`). Pipe-delimited, quoted strings, UTF-8. 46 static columns + 89 dynamic election columns per row.

**Join key**: `SOS_VOTERID` — statewide unique identifier. `COUNTY_ID` is county-scoped only; do not use as a cross-county join key.

### Identity & Demographics
| Column | Type | Notes |
|---|---|---|
| `SOS_VOTERID` | str | Statewide PK |
| `COUNTY_NUMBER` | str | 1-88 |
| `COUNTY_ID` | str | County-scoped, not statewide unique |
| `LAST_NAME` | str | |
| `FIRST_NAME` | str | |
| `MIDDLE_NAME` | str | |
| `SUFFIX` | str | |
| `DATE_OF_BIRTH` | date | YYYY-MM-DD |

### Registration & Status
| Column | Type | Notes |
|---|---|---|
| `REGISTRATION_DATE` | date | YYYY-MM-DD. Never reassigned on name/address change — reliable first-registration proxy for cohort analysis. Reset only on cancellation + reactivation. |
| `VOTER_STATUS` | enum | ACTIVE or CONFIRMATION only in SWVF. Collapses 6+ internal substatus codes (ACTIVE FPCA, ACTIVE NCOA, BMV/SSA MATCH, CONF NCOA, CONF LIST MAINT, CONF NO VOTE). A CONFIRMATION spike is ambiguous — may reflect NCOA movers, BMV/SSA mismatches, or supplemental-process inactives. Distinguishing requires county-level files. |
| `PARTY_AFFILIATION` | enum | R, D, or empty string (unaffiliated). Lagged, behavior-derived — not self-declared. Per Ohio EOM Ch.15, determined by which party primary the voter participated in within the past two calendar years. Use election history columns as ground truth for trajectory analysis. |

### Residential Address (PII — never commit)
RESIDENTIAL_ADDRESS1, RESIDENTIAL_SECONDARY_ADDR, RESIDENTIAL_CITY, RESIDENTIAL_STATE, RESIDENTIAL_ZIP, RESIDENTIAL_ZIP_PLUS4, RESIDENTIAL_COUNTRY, RESIDENTIAL_POSTALCODE

### Mailing Address (PII — never commit)
MAILING_ADDRESS1, MAILING_SECONDARY_ADDRESS, MAILING_CITY, MAILING_STATE, MAILING_ZIP, MAILING_ZIP_PLUS4, MAILING_COUNTRY, MAILING_POSTAL_CODE

### Jurisdictional Assignments (aggregation keys)
| Column | Notes |
|---|---|
| `PRECINCT_NAME` | Human-readable (e.g., KETTERING 1-A) — primary atomic unit |
| `PRECINCT_CODE` | Internal code (e.g., 01AAI) |
| `CONGRESSIONAL_DISTRICT` | Federal House district |
| `STATE_SENATE_DISTRICT` | |
| `STATE_REPRESENTATIVE_DISTRICT` | |
| `CITY` | Municipal jurisdiction |
| `TOWNSHIP` | |
| `VILLAGE` | |
| `WARD` | Municipal ward |
| `LOCAL_SCHOOL_DISTRICT` | |
| `CITY_SCHOOL_DISTRICT` | |
| `CAREER_CENTER` | Vocational district |
| `EXEMPTED_VILL_SCHOOL_DISTRICT` | |
| `COUNTY_COURT_DISTRICT` | |
| `MUNICIPAL_COURT_DISTRICT` | |
| `COURT_OF_APPEALS` | |
| `STATE_BOARD_OF_EDUCATION` | |
| `EDU_SERVICE_CENTER_DISTRICT` | |
| `LIBRARY` | |

### Election History Columns (dynamic, 89 total)
Format: [TYPE]-[MM/DD/YYYY] where TYPE is PRIMARY, GENERAL, or SPECIAL.
Range: PRIMARY-03/07/2000 to SPECIAL-02/03/2026.
Values: R or D (party ballot in primary), X (non-partisan participation), empty string (did not participate).
No _TYPE suffix columns (absentee/Eday) — those exist in county-level files only.
Ground truth for party affiliation trajectory and engagement modeling. Two calendar years of blanks triggers supplemental list-maintenance, placing voters in CONFIRMATION status. High CONFIRMATION density + sparse recent history = concrete anomaly signal (Ohio EOM Ch.4).

### Missing Fields (county files only, not in SWVF)
- Last Activity Type (LAT): VOT, ABR, REG, UPD, BMV, PET, CON — drives list maintenance and CONFIRMATION transitions. Must be inferred from election history columns.
- Ballot method (_TYPE columns): Absentee / Election Day / Provisional.
- CONFIRMATION subtype: NCOA vs. supplemental vs. BMV mismatch.

### External Data Sources (Phase 3+)
Precinct-level official canvass results published by Ohio SoS after each even-year election:
https://www.ohiosos.gov/elections/election-results-and-data/

### Error Policy
On malformed rows: log to ./working/errors/[county].log and continue. Do not halt on parse errors.

## Known Project State

- **Current phase**: Phase 1 complete — pipeline built; Parquet cache operational (88 partitions)
- **Processed**: Parquet cache built from all 4 SWVF source files; 7,892,613 rows × 135 columns
- **Active scripts**: `ohio_voter_pipeline.py` (menu driver), `voter_data_cleaner_v2.py` (core pipeline), `precinct_unc_export.py` (standalone precinct D/UNC export)
- **Dashboard**: GitHub Pages at `docs/` — county + precinct + city scope tabs; manifest-driven; Chart.js
- **Next milestone**: Full statewide JSON build (option 2) to populate dashboard for all 88 counties + precinct drill-down

---

*Last updated: 2026-05-06*
