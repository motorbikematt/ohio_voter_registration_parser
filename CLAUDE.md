# CLAUDE.md — Ohio Voter Registration Parser

Project state, phase status, dashboard history, and changelog live in the Cowork memory system (auto-loaded via `MEMORY.md`), not here. This file holds only universally applicable rules and irreducible domain semantics.

## State-file archive rule (read first)

Before any Write or Edit that overwrites `CLAUDE.md`, `MEMORY.md`, or any file under the Cowork memory directory (`memory/project_*.md`, `memory/feedback_*.md`, etc.), first run `python tools/archive_state.py <path>` from the project root. The script copies the current version to `docs/archive/{filename}.{YYYY-MM-DDTHHMM}.md` (or `docs/archive/memory/...` for memory files), giving us a timestamped progression of state evolution that git then tracks. Skipping this step loses the prior version irrecoverably for memory files (which live outside the project's git history).

## File editing protocol

Edit tool for files ≤150 lines; Python patch script for anything longer. The Edit tool and bash heredocs both truncate silently — a failed write looks identical to a successful one until parsing fails downstream.

Patch script template:

```python
from pathlib import Path
p = Path('path/to/file.py')
src = p.read_text(encoding='utf-8')
old = "exact unique block, < 10 lines"
new = "replacement"
assert src.count(old) == 1, f"Expected 1, found {src.count(old)}"
p.write_text(src.replace(old, new), encoding='utf-8')
```

For payloads >50 lines, use `Path.write_text(content)` from inside a Python invocation — never `cat << 'EOF' >> file`. After every patch validate: Python `python3 -c "import ast; ast.parse(open('path').read())"`, JavaScript `node --check path/to/file.js`.

**Patch script location.** One-shot patch scripts go in `patches/` (gitignored), never at repo root. Check `patches/` at the start of each session and delete any script whose target patch has already been applied.

## Processing principles

- **Polars or DuckDB**, not Pandas — out-of-core, vectorized, all 88 counties.
- **Parquet** (partitioned by county) for intermediate layers; **GeoParquet** for spatial.
- **Excel only for final aggregated stakeholder outputs** via `xlsxwriter`/`openpyxl`. Never load raw files into Excel.
- **Provenance preserved** in parquet metadata or sidecar JSON: BoE timestamps, original headers, source URLs.
- **Zero-trust security**: never commit raw PII. `.gitignore` covers `./working/` and `./source/`.
- **Error policy**: log malformed rows to `./working/errors/[county].log` and continue. Never halt on parse error.
- **No try/except as control flow** — sole operator, loud failures preferred over silent degradation.

## File locations

Raw input in `source/`. Working output and dashboard JSON in `./` and `./docs/data/`. Core engine scripts at root; utilities and exporters in `tools/`; scoring module in `tools/scoring/`.

## Schema reference — SWVF source

Source: 4 split flat files (`SWVF_1_22.txt`, `SWVF_23_44.txt`, `SWVF_45_66.txt`, `SWVF_67_88.txt`). Pipe-delimited, quoted, UTF-8. 46 static cols + 89 dynamic election cols.

**Join keys.** `SOS_VOTERID` (statewide). `COUNTY_ID` is county-scoped — never use cross-county.

**Registration/status semantics (per Ohio EOM Ch.15).**
- `REGISTRATION_DATE` never reassigned on name/address change; resets only on cancellation + reactivation. Reliable first-registration proxy.
- `VOTER_STATUS` in SWVF is `ACTIVE` or `CONFIRMATION` only — collapses 6+ internal substatus codes (FPCA, NCOA, BMV/SSA MATCH, CONF NCOA, CONF LIST MAINT, CONF NO VOTE). Subtype distinction requires county files.
- `PARTY_AFFILIATION` (`R`, `D`, empty) is behavior-derived: which party primary in past 2 calendar years. Use election-history columns as ground truth.

**PII columns (never commit).** Residential: `ADDRESS1`, `SECONDARY_ADDR`, `CITY`, `STATE`, `ZIP`, `ZIP_PLUS4`, `COUNTRY`, `POSTALCODE`. Mailing: `ADDRESS1`, `SECONDARY_ADDRESS`, `CITY`, `STATE`, `ZIP`, `ZIP_PLUS4`, `COUNTRY`, `POSTAL_CODE`.

**County-scoped jurisdiction types.** `TOWNSHIP`, `VILLAGE`, `MUNICIPAL_COURT_DISTRICT` collide on name across counties (Washington Township in 23 counties, BELLEVUE municipal court in 3). Aggregation must use `(COUNTY_NUMBER, name)` composite key. `JURISDICTIONS[type]['county_scoped'] = True` in `jurisdictional_groupings.py` triggers slug `{county_slug}_{name_slug}` and display `{name} ({County} Co.)`.

**Election history (89 dynamic cols).** Format `[TYPE]-[MM/DD/YYYY]`, TYPE ∈ {`PRIMARY`, `GENERAL`, `SPECIAL`}. Range 03/07/2000 → 02/03/2026. Values: `R`/`D` (party primary ballot), `X` (non-partisan), empty (didn't vote). 2 calendar years of blanks → supplemental list maintenance → `CONFIRMATION`. High CONFIRMATION + sparse recent history = anomaly signal (Ohio EOM Ch.4). No `_TYPE` suffixes (absentee/Eday) in SWVF — county files only.

**Not in SWVF.** Last Activity Type (VOT/ABR/REG/UPD/BMV/PET/CON) — infer from election history. Ballot method (`_TYPE` cols) — Absentee/Eday/Provisional. CONFIRMATION subtype.

**External P3+ source.** Precinct canvass: https://www.ohiosos.gov/elections/election-results-and-data/

## Pipeline architecture (why the code looks the way it does)

`ThreadPoolExecutor` with `max_workers=8`, not multiprocessing — shared address space, no IPC, no WinError 1450. `orjson` for JSON (GIL-releasing, ~3–5× stdlib; falls back to stdlib if missing). `psutil` RSS logging in every `_timer` exit. Pre-classification (`classify_all_voters_primary_history()`) runs once in main process; workers receive enriched slices with `cohort_family` attached. Enriched-parquet cache at `source/parquet_enriched/enriched_voters.parquet` skips redundant cleaning; freshness check compares cache mtime against `max(latest_raw_partition_mtime, classifier_src_mtime)`. Atomic write via `.parquet.tmp` → `.replace()`. Install: `.venv\Scripts\pip install orjson psutil`.

## Git push rule — MCP vs manual

**CRITICAL: never push `docs/data/` via the GitHub MCP.** That tree contains ~65,000 JSON files; a prior attempt via `push_files` consumed the entire account token budget. Do not repeat under any circumstances.

| Scenario | Method |
|---|---|
| Code changes this session (Python, JS, config, markdown) | MCP `push_files` — content already in context, zero extra token cost |
| Pipeline-regenerated `docs/data/` JSON files | User runs `git push` from PowerShell or VS Code |
| Binary files or files >50 MB | User runs `git push` from PowerShell or VS Code |

Batch all changed code files into a single `push_files` call. Never iterate file-by-file — each call is a separate commit and compounds token cost. For `.git/index.lock` from failed sandbox git ops: `Remove-Item ".git\index.lock" -Force`, then commit from PowerShell or VS Code.

Manual-push handoff command template:

```powershell
cd "D:\vibe\election-data"
git add <specific files or -A>
git commit -m "<message>"
git push
```
