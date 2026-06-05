# Project Instructions: Ohio Voter Registration Parser

## 🚨 CRITICAL: File Editing Protocol
**DO NOT use standard `replace` or `write_file` for files exceeding 150 lines.**
The tools silently truncate large payloads. You MUST use a Python patch script for these files.

### Patch Script Template
```python
from pathlib import Path
import ast

p = Path('path/to/file.py')
src = p.read_text(encoding='utf-8')
old = "EXACT_UNIQUE_BLOCK_OF_EXISTING_CODE"
new = "REPLACEMENT_CODE"
assert src.count(old) == 1, f"Expected 1, found {src.count(old)}"
p.write_text(src.replace(old, new), encoding='utf-8')

# Mandatory AST check after write
ast.parse(p.read_text(encoding='utf-8'))
```

### Validation & Testing
- **Syntax Validation:** After every change, you must validate syntax before reporting success (`python -c "import ast; ast.parse(open('file.py', encoding='utf-8').read())"`).
- **Unit Testing:** `pytest` is the standard. All unit tests belong in the `tests/` directory (e.g., `tests/test_voter_data_cleaner.py`). Run `pytest tests/` after logic changes to catch regressions in text parsing (e.g., regex stripping) or data manipulation.

---

## Technical Mandates

### 1. Processing & Performance
- **Vectorized Only:** Use **Polars** or **DuckDB**. NEVER use Pandas for core pipeline operations.
- **Storage:** Use **Parquet** for intermediate data. **Excel** is strictly for final stakeholder delivery.
- **Memory Stability:** Be aware of Arrow buffer copies during grouping/partitioning. Prefer sequential processing with explicit `del` for large numbers of partitions over thread pools if memory peaks (e.g., in jurisdictional groupings). Full 88-county Excel passes can peak at **45GB RSS**.
- **Caching (Pending):** A persistent enrichment cache at `source/parquet_enriched/` is planned to skip the ~80s `clean_voter_data()` cost. **Invalidation Rule:** The cache MUST be invalidated if the raw parquet is newer OR if `voter_data_cleaner_v2.py` is newer, to prevent serving stale cohort logic. Writes must be atomic (e.g., write `.tmp` then rename).

### 2. Security & Data Integrity
- **Zero-PII:** NEVER commit raw voter PII (addresses, full birth dates, etc.).
- **Git Safety:** Ensure `./working/` and `./source/` are excluded by `.gitignore`.
- **Provenance:** Always preserve BoE timestamps and original source headers.

### 3. Architecture & Dual-Rollup Logic
- **Primary Keys:** Use `SOS_VOTERID` for statewide joins. `COUNTY_ID` is local to each county file.
- **`jurisdictional_groupings.py`**: Performs strict legal groupings based on jurisdiction columns (e.g., `CITY`, `TOWNSHIP`). This handles true cross-county aggregates (e.g., Columbus spanning Franklin/Delaware/Fairfield).
- **`build_city_summary()` (in v2 core)**: Intentionally performs a precinct-derived rollup to group local geographies within a single county (e.g., stripping suffixes to group precincts visually for a county dashboard), even if it differs from the legal `CITY` column.

---

## Directory Structure
- **Raw Data:** `D:\vibe\election-data (1)\source\`
- **Web Dashboard:** `D:\vibe\election-data (1)\docs\` (GitHub Pages `/docs` on `main`)
- **Core Engine:** `voter_data_cleaner_v2.py`, `ohio_voter_pipeline.py` (menu driver)
- **Aggregators:** `jurisdictional_groupings.py` (all 12 jurisdiction types)
- **Tools:** `tools/` contains utility scripts including `voter_lookup.py` (global Parquet search) and `raw_voter_lookup.py` (global raw text search).
- **Tests:** `tests/` contains all `pytest` unit test definitions.

---

## Active Phase: Phase 2 (Roll-Up) - Pass B Pending
Currently aggregating precinct data into wards, cities, counties, and 12 total jurisdictional types. 
- **Pass A Complete:** Implemented county-scoped slugs for townships, villages, and municipal courts to prevent cross-county collisions of identically named but legally distinct entities.
- **Pass B Pending:** 
  1. Implement the persistent enriched-parquet cache.
  2. Implement dashboard UI plumbing (`manifest.json` and `charts.js`) to expose and render the new jurisdiction-level chart pages.

*Last updated: 2026-05-10*
