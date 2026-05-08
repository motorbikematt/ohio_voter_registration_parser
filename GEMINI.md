# Project Instructions: Ohio Voter Registration Parser

## 🚨 CRITICAL: File Editing Protocol
**DO NOT use standard `replace` or `write_file` for files exceeding 150 lines.**
The tools silently truncate large payloads. You MUST use a Python patch script for these files.

### Patch Script Template
```python
from pathlib import Path
p = Path('path/to/file.py')
src = p.read_text(encoding='utf-8')
old = "EXACT_UNIQUE_BLOCK_OF_EXISTING_CODE"
new = "REPLACEMENT_CODE"
assert src.count(old) == 1, f"Expected 1, found {src.count(old)}"
p.write_text(src.replace(old, new), encoding='utf-8')
```

### Validation
After every change, you must validate syntax before reporting success:
- **Python:** `python -c "import ast; ast.parse(open('path/to/file.py').read())"`
- **JavaScript:** `node --check path/to/file.js`

---

## Technical Mandates

### 1. Processing & Performance
- **Vectorized Only:** Use **Polars** or **DuckDB**. NEVER use Pandas for core pipeline operations (memory/speed issues).
- **Storage:** Use **Parquet** for intermediate data (partitioned by county). **Excel** is strictly for final stakeholder delivery.
- **Concurrency:** Limit `ThreadPoolExecutor` to `max_workers=8` to prevent system resource exhaustion.
- **Memory:** Be aware that full 88-county Excel passes can peak at **45GB RSS**.

### 2. Security & Data Integrity
- **Zero-PII:** NEVER commit raw voter PII (addresses, full birth dates, etc.).
- **Git Safety:** Ensure `./working/` and `./source/` are excluded by `.gitignore`.
- **Provenance:** Always preserve BoE timestamps and original source headers.

### 3. Schema & Logic
- **Primary Keys:** Use `SOS_VOTERID` for statewide joins. `COUNTY_ID` is local to each county file.
- **Party Affiliation:** Behavior-derived per Ohio EOM Ch.15 (primary ballot history in past 2 calendar years).
- **Election Columns:** Follow the format `[TYPE]-[MM/DD/YYYY]`.

---

## Directory Structure
- **Raw Data:** `D:\vibe\election-data (1)\source\`
- **Web Dashboard:** `D:\vibe\election-data (1)\docs\` (GitHub Pages `/docs` on `main`)
- **Core Engine:** `voter_data_cleaner_v2.py` (~3,650 lines - ALWAYS use patch script)

---

## Active Phase: Phase 2 (Roll-Up)
Currently aggregating precinct data into wards, cities, and counties. The GitHub Pages dashboard is driven by `manifest.json` and `docs/data/*.json`.

*Last updated from CLAUDE.md: 2026-05-08*
