# CLAUDE.md — Ohio Voter Registration Parser

## 1. Project Overview
Ohio Statewide Voter File (SWVF) parser and precinct-captain dashboard. Ingests raw county data to generate deterministic, cohort-segmented voter rosters and jurisdictional narratives. Project state, phase status, and dashboard history live in the agent memory systems (auto-loaded via `MEMORY.md`), not here and not in the repo. Those stores are external and environment-specific: Claude Code CLI reads `~/.claude/projects/D--vibe-election-data/memory/`; Cowork reads its own space memory. This file holds only universally applicable rules and irreducible domain semantics.

## 2. Tech Stack
* Core data engine: Polars, DuckDB, `orjson`.
* Export: `xlsxwriter`, `openpyxl` — final aggregated stakeholder outputs only; never load raw files into Excel.
* Frontend: vanilla JavaScript, HTML, Chart.js.
* Prefer Polars/DuckDB over Pandas for all pipeline code (out-of-core, vectorized, all 88 counties). Pandas is **not** banned outright: it is still a required dependency in `pipeline/jurisdictional_groupings.py`, `pipeline/ohio_voter_pipeline_wrapper.py`, and `tools/scoring/unc_lifetime_d_predictor.py`. Do not remove it without migrating those files first — dropping it breaks the runtime.

## 3. Architecture (repo layout)
* `docs/` — public web root (GitHub Pages): `index.htm`, `assets/`, `charts.js`, `data/` (compiled JSON), `captain/`, `manifest.json`, `CNAME`. Frontend/UI conventions: see §11 (kept out of `docs/` so they are never published).
* `pipeline/` — core cleaning/generation: `voter_data_cleaner.py`, `ohio_voter_pipeline.py`, `jurisdictional_groupings.py`, `ohio_voter_pipeline_wrapper.py`.
* `tools/` — segmented by function: `export/`, `lookup/`, `admin/`, `narrative/`, `scoring/`, `tests/`.
* `serve/` — local PII backend (`roster_api.py`, `captain_db.py`); the *code* is committable and PII-free, reading PII only at runtime from `local/`.
* `local/` — local-only workspace, **entirely gitignored**: `source/`, `working/`, `exports/`, `patches/`, `logs/`, `*.db`, and `local/context/` (AI `archive/`, `research/`, `journal/`, `handoffs/`, `scope/`, `business/`).

## 4. SWVF Schema & Domain Semantics
The irreducible knowledge this file exists to hold — most of the project's worst bugs were schema misunderstandings, not code defects.

**Source files.** 4 split flat files (`SWVF_1_22.txt`, `SWVF_23_44.txt`, `SWVF_45_66.txt`, `SWVF_67_88.txt`). Comma-delimited **CSV**, double-quoted fields, UTF-8 — despite the `.txt` extension. NOT pipe-delimited. 46 static cols + 89 dynamic election cols. Official layout: local/source/Voter_File_Layout.md

**Join keys.** `SOS_VOTERID` is the statewide key. `COUNTY_ID` is county-scoped — never join on it across counties.

**Jurisdiction columns vs. postal address.** `CITY`, `VILLAGE`, `WARD`, `TOWNSHIP` are authoritative jurisdiction fields. `RESIDENTIAL_CITY` is the USPS mail-delivery city — postal, **not** a jurisdiction. Never assign municipal jurisdiction from `RESIDENTIAL_CITY`, and never treat `PRECINCT_NAME` as a jurisdictional proxy (precincts are named for physical boundaries, not the voter's municipality). City-resolution hierarchy: `CITY` → `VILLAGE` → `WARD` prefix → `TOWNSHIP` (means "not a city" → emit `None`) → `RESIDENTIAL_CITY` (true last resort, ~1 county). A `PRECINCT_NAME` township token (`TWP`/`TOWNSHIP`/trailing `" TS"`) outranks a minority village value. Conflating postal with jurisdiction mislabeled 56% of precinct pairs and went undetected for weeks.

**County-scoped jurisdiction types.** `TOWNSHIP`, `VILLAGE`, `MUNICIPAL_COURT_DISTRICT` collide on name across counties (Washington Township in 23 counties; BELLEVUE municipal court in 3). Aggregate on the composite key `(COUNTY_NUMBER, name)`; `county_scoped: True` in `jurisdictional_groupings.py` triggers the slug/display convention. Wards are globally unique (the city name is baked in, e.g. `"CLEVELAND WARD 8"`) and must **not** be county-scoped.

**Status / affiliation semantics (Ohio EOM Ch.15).** `REGISTRATION_DATE` is never reassigned on name/address change — it resets only on cancellation + reactivation, so it is a reliable first-registration proxy. `VOTER_STATUS` is `ACTIVE` or `CONFIRMATION` only (collapses 6+ internal substatus codes; subtype needs county files). `PARTY_AFFILIATION` (`R`/`D`/empty) is behavior-derived (which party's primary in the past 2 calendar years) — use the election-history columns as ground truth.

**Election history (89 dynamic cols).** Header format `[TYPE]-[MM/DD/YYYY]`, TYPE ∈ {`PRIMARY`, `GENERAL`, `SPECIAL`}, range 03/07/2000 → 02/03/2026. The date lives in the column **name**; the cell holds `R`/`D` (party primary ballot), `X` (non-partisan), or empty (didn't vote). 2 calendar years of blanks → supplemental list maintenance → `CONFIRMATION`.

**Blank cells are empty strings, not null.** SWVF arrives with `""`, not `null`; null-aware ops (e.g. `pl.coalesce`) skip nothing. `.replace("", None)` before coalescing or filtering on nullity.

**Derived columns.** PascalCase temporal: `Generation`, `Decade`, `BIRTHYEAR` (not `birth_year`). Canonical `Generation` values are exactly `Silent/Greatest`, `Baby Boomers`, `Gen X`, `Millennials`, `Gen Z` — not Pew shorthand; wrong labels silently return 0 rows.

**Not in SWVF.** Last Activity Type, ballot method (`_TYPE` absentee/Eday/provisional cols), CONFIRMATION subtype — county files only. Precinct canvass (P3+): https://www.ohiosos.gov/elections/election-results-and-data/

## 5. Data Processing Principles
* **Single-resolver logic.** Never duplicate extraction/derivation (e.g. the jurisdiction hierarchy). Define one Python resolver and reuse it across indexers, summaries, and JS-fed outputs — divergent copies are how the postal-city bug survived.
* **Parquet, partitioned by county**, for intermediate layers; GeoParquet for spatial. `COUNTY_NUMBER` is a *partition key*, not a column inside the parquet files — re-add it as a literal when reading partitions (the most common KeyError for new contributors).
* **Atomic writes:** `.parquet.tmp` → `.replace()`; never leave a partial cache. Enriched cache at `local/source/parquet_enriched/enriched_voters.parquet`; freshness = cache mtime vs `max(latest_raw_partition_mtime, classifier_src_mtime)`.
* **Parallelism:** `ThreadPoolExecutor(max_workers=8)`, not multiprocessing (shared address space, avoids WinError 1450). Any cross-county step (e.g. the city→county map) must run single-threaded *after* all 88 counties are written.
* **Provenance preserved** in parquet metadata or sidecar JSON: BoE timestamps, original headers, source URLs.
* **Loud failures over silent degradation.** No `try/except` as control flow (sole operator). Optional layers (LLM enrichment) may degrade gracefully; the core pipeline must not.

## 6. Coding Conventions
* **Path resolution.** Do not rely on CWD. Resolve the project root from the file: `Path(__file__).resolve().parent` at repo root, `Path(__file__).resolve().parent.parent` for scripts under `pipeline/` or `tools/<sub>/`.
* **Encoding.** Keep all printed/console strings ASCII (the Windows console default is cp1252; a Unicode arrow crashes the process). Handle CRLF vs LF explicitly in patch scripts — `pipeline/voter_data_cleaner.py` and `jurisdictional_groupings.py` are CRLF; `ohio_voter_pipeline.py` and `docs/assets/v2.js` are LF.

## 7. Testing and Quality Bar
* **Bounded data checks** before asserting state or data origin: `SELECT COUNT(*)`, `LIMIT 3`, parquet `value_counts()` / `.select([cols])`, file mtime. Each result must fit in a few hundred tokens. Never guess where data came from.
* Verify a column **reaches** the function, not merely that it exists in the source — a targeted reader loading a column subset can pass a schema check and still raise downstream.
* **Error policy.** Log malformed rows to `local/working/errors/[county].log` and continue. Never halt on a parse error.
* `tools/admin/validate_jurisdiction_fields.py` is the data-validation gate; run it on every new SWVF drop.

## 8. File Placement Rules
* **`docs/` is the public web root.** Everything under `docs/` is served by GitHub Pages and is publicly fetchable. Never put internal artifacts there — AI context, memory, journals, handoffs, dev notes, and business docs go to `local/context/` (gitignored); agent rule files go to `.claude/rules/`. The public tree carries only the dashboard and its compiled `data/`.
* One-shot patch scripts go **exclusively** in `local/patches/` (gitignored). At the start of each session, delete any whose target patch has already been applied.
* Large data payloads for ad-hoc scripts (session entries, diffs, JSON blobs) go to a separate temp file in `local/patches/`; the script reads that file rather than receiving content through the command string.
* File appends on large files: never read-modify-write (`p.write_text(p.read_text() + entry)`) — it loads the file into RAM twice. Use `open('a')` and `p.stat().st_size` for size checks.

## 9. Safe-Change Rules
* **File editing.** Use the Edit tool only for files ≤150 lines. The Edit tool and bash heredocs both truncate **silently** — a failed write looks identical to a success until parsing fails downstream. For larger files, write a Python patch script to `local/patches/` (`p.read_text()` / `p.write_text()`), then validate (`python -c "import ast; ast.parse(...)"` or `node --check`). Use `python` / `.venv\Scripts\python.exe` in Git Bash; `python3` exists only in the Cowork Linux sandbox. For payloads >50 lines write via `Path.write_text(content)`; never `cat << 'EOF' >> file`.
* **Zero-trust security.** Never commit email or phone numbers (PII). Name, DOB, and address are public record. `local/` stays entirely in `.gitignore`.
* **Verify input sources.** When a user reports a broken URL/command/output, first ask whether they typed it, pasted it, or something generated it — before proposing a fix. Do not break a working contract to accommodate a muscle-memory typo.
* **MCP push ban.** NEVER push `docs/data/` (~78k generated JSON files) via the GitHub MCP — `push_files` sends content as tokens and a prior attempt exhausted the account budget. Batch changed *code* files into a single `push_files` call; the user pushes regenerated `docs/data/` and binaries manually (see §10).
* **Claude Code CLI host-scanner avoidance** (the `\n#` multi-line `-c` flag, `cd`+redirection) is CLI-host behavior and lives in the global `~/.claude/CLAUDE.md` under `## Command Execution`. It does not fire in the Cowork sandbox (verified), so it is intentionally not duplicated here. Utilities such as `awk`, `sed`, `xargs`, and `stat` are whitelisted in `.claude/settings.local.json` and do not require avoidance.

## 10. Specific Commands
Manual git-push handoff (the sandbox cannot push — Windows Credential Manager prompts are unsupported, and FUSE mounts block git index writes):
```powershell
cd "D:\vibe\election-data"
git add <files>
git commit -m "<message>"
git push
```
* **Safe git search** (repo has ~78k generated files): `git log -S "term" --no-renames | head -n 20`; scope `grep` / `git grep` to a subdirectory, never repo root. One-time: `git config diff.renameLimit 10000`.
* **Stuck `.git/index.lock`** from a failed sandbox op: `Remove-Item ".git\index.lock" -Force`, then commit from PowerShell / VS Code.

## 11. Frontend (docs/)
The GitHub Pages dashboard (`index.htm`, `assets/`, `charts.js`, `captain/`, `data/`). These conventions live here, not in `docs/`, so they are never published (see §8).
* **Breakpoints.** Conform to existing breakpoints — the 880px mobile-drawer breakpoint in `assets/v2.css` is the canonical switch; the captain layer's CSS matches it. Don't introduce a competing breakpoint.
* **XSS boundary.** Route every server-supplied string through `esc()` before it reaches `innerHTML`; `esc()` is the single trust boundary. Re-render paths build markup via `buildTouchesHtml()` + `DOMParser`, not `insertAdjacentHTML`.
* **Captain layer.** `captain/captain-mode.js` decorates the public page; it boots only when `127.0.0.1:8000/health` responds, else exits silently. The public deploy is structurally inert — no backend URL, no API key. Never commit a backend URL or token into the frontend.
* **Data loading.** Charts read precomputed `data/` JSON (flat-file pattern). Do not re-aggregate whole precinct files at runtime — that caused the Kettering over-count. City/jurisdiction views point at precomputed `data/city/`-style files. Send the raw URL slug to the roster API; read display names from the hierarchy row's `data-precinct-name`, not by un-slugging (lossy on hyphens).
