# Ohio Voter Dashboard — Project Journal

This file is a running narrative of decisions made, problems solved, and direction changes across the life of this project. It is written for the project owner (motorbikematt) and collaborators (Antigravity) to understand not just *what* was built but *why*.

Git commit messages capture what changed. This captures the thinking behind it.

---

## 2026-04-30 — Project Start

**Session context:** *[JSONL placeholder — session transcript not yet reviewed]*

The project started as a voter data cleaner script. The initial commit established the repo and the basic concept: parse Ohio's Statewide Voter File (SWVF), a pipe-delimited flat file with ~46 static columns and 89 dynamic election history columns covering elections from 2000–2026.

**Key early decision:** Use Polars instead of Pandas. The SWVF is large (88 counties, millions of rows), and Pandas would require loading everything into memory. Polars operates out-of-core and is vectorized — the right tool for this scale from day one.

---

## 2026-05-01 — First Pipeline + GitHub Pages Dashboard

**Session context:** *[JSONL placeholder]*

First end-to-end run: Montgomery County voter data processed and exported as JSON. A GitHub Pages dashboard was stood up in `docs/` so outputs could be viewed in a browser immediately — this proved to be a good decision because it made the data tangible and testable from very early on.

The pipeline architecture established here (Python scripts in root, output to `docs/data/`, dashboard in `docs/`) persisted throughout the project.

---

## 2026-05-02 to 2026-05-04 — Statewide Expansion + UNC Shadow

**Session context:** *[JSONL placeholder]*

Scaled from single-county (Montgomery) to all 88 Ohio counties. Several bug fixes were required as edge cases appeared at scale — county numbering, city extraction, manifest writer issues.

**Key concept introduced: UNC Shadow.** Unaffiliated voters (UNC) who have a behavioral partisan history aren't truly unaffiliated — they've just lapsed. The "shadow" metric estimates how many UNC voters have a lifetime Democratic or Republican lean based on their full election history, even if they haven't voted in a primary recently. This became a core analytical concept distinguishing this project from raw registration counts.

Stacked bar charts and adjacency doughnut charts were added to visualize the shadow data.

---

## 2026-05-06 — Phase 1 Complete: Full Ohio Statewide Dashboard

**Commit:** `10f57b707c` — "Phase 1 complete — full Ohio statewide dashboard build (88 counties)"

This was the first major milestone. The dashboard was functionally complete for the county level with:
- All 88 counties processed
- Party affiliation, decade/generation distribution, party-by-decade, UNC shadow charts
- County → Precinct drill-down
- Scope tabs (County / Precinct / City) as tier-1 navigation
- Pipeline menu with targeted county runs, precinct chart opt-in

**Why this mattered:** Phase 1 proved the core pipeline and visualization concept. Everything after this was enrichment — more jurisdiction types, better narratives, LLM integration.

---

## 2026-05-07 to 2026-05-08 — Cohort Taxonomy Refactor ("Mel's Bug")

**Session context:** *[JSONL placeholder]*

A significant refactor of the cohort classification system triggered by what was internally called "Mel's bug" — a miscategorization in how Mixed and UNC voters were being classified.

**The seven cohorts were locked in:**
- Pure D, Pure R (consistent single-party primary voters, currently affiliated)
- Mixed-Active (crossed over, currently affiliated)
- UNC-Lapsed D, UNC-Lapsed R (behavioral partisans, currently unaffiliated)
- Mixed-Lapsed (crossed over, currently unaffiliated)
- UNC-No Primary (never voted in any primary on record)

This taxonomy became the analytical backbone of the entire project. The distinction between "affiliated" (voted in a primary in the current + preceding 2 calendar years) and "unaffiliated" is grounded in Ohio Revised Code R.C. 3513.19 — party affiliation in Ohio is entirely behavior-derived, not a registration choice.

**Legend and tooltip work** also happened in this window — making the chart visualizations readable and printable.

---

## 2026-05-09 — Jurisdictional Groupings: Beyond Counties

**Commit:** `216e023056` — "add jurisdictional groupings generation and export functionality"

Extended the pipeline from county/precinct to 12+ jurisdiction types: townships, villages, cities, congressional districts, state senate districts, state house districts, school districts, court districts, etc.

**Key architectural decision:** County-scoped jurisdiction types (townships, villages, municipal courts) collide on name across counties — there are 23 "Washington Townships" in Ohio. The fix was a composite key `(COUNTY_NUMBER, name)` for these types, producing slugs like `montgomery_washington_township` and display names like "Washington Township (Montgomery Co.)". This is encoded in `jurisdictional_groupings.py` as `county_scoped: True`.

Scripts were reorganized into `tools/` and `tools/scoring/` subdirectories, establishing the final project layout.

---

## 2026-05-09 — Rebuild County & Precinct Stats

**Commit:** `a9c4811bed`

Full statewide rebuild after the cohort taxonomy refactor. This was a validation run — confirming the new 7-cohort classification produced correct numbers across all 88 counties.

---

## 2026-05-12 — Jurisdictions Tab + Enriched Parquet Cache

**Commit:** `6480a442a9`

Major dashboard update adding the Jurisdictions tab with type/county/name cascade selectors. 12 jurisdiction types routed via URL parameters. 1,272 townships, 683 villages, and other types all indexed.

**Enriched parquet cache introduced:** Rather than re-cleaning and re-classifying voter data on every pipeline run, the cleaned+enriched data is cached at `source/parquet_enriched/enriched_voters.parquet`. Freshness is checked by comparing cache mtime against the latest raw partition mtime and classifier source mtime. Atomic write via `.parquet.tmp` → `.replace()` prevents partial writes from corrupting the cache.

This was a significant performance improvement — the pre-classification step (assigning cohort_family to every voter) runs once in the main process, and workers receive enriched slices rather than re-deriving cohorts per county.

---

## 2026-05-13 — Path Refactor + UI Navigation Refactor

**Commits:** `592b6091fb`, `45f1040b33`

Replaced hardcoded absolute paths with `Path(__file__).resolve().parent` throughout the codebase. This made the project portable — runnable from any machine without editing paths.

Geo-navigation and jurisdictional analysis framework refactored in the dashboard.

---

## 2026-05-14 — Environment Setup & MCP Integration

**Session context:** `46b6f0b8-ec9d-45c9-8bfc-2d0761d40f8f.jsonl`, `94c87c71-2b83-4181-bdac-1a3fa1fabb72.jsonl`

Maintenance session focused on setting up Claude CLI configurations, listing active MCP servers, verifying tool connections, and transitioning to Sonnet 4.6 as the default model.

---

## 2026-05-18 — CNAME / GitHub Pages Domain

Brief DNS/CNAME setup for the GitHub Pages deployment. (Created and deleted same day — likely a domain configuration test.)

---

## 2026-05-20 — Chore Updates & Git Environment Debugging

**Session context:** `d4b7cae8-5d35-4684-a1ba-903212c34be3.jsonl`, `e81972c1-06c4-47b5-bcd7-5d6af9024085.jsonl`

Troubleshot Windows/VSCode environment issues:
- **Git permissions collision:** Resolved a "permission denied" error on `C:\Users\motorbikematt\.config\git\ignore` that prevented `git status` and Git synchronization from running in VSCode. Used `takeown` commands to re-establish ownership.
- **GitHub Pages Routing:** Located the main HTML entry point that GitHub Pages renders (`docs/index.html`) to clarify how frontend dashboard routing functions.

---

## 2026-05-25 — MCP Connector Verification

**Session context:** `2edddc0f-a55b-43ef-9664-b4eb6140f65f.jsonl`

Brief verification session to test the integration of the WordPress.com MCP server connector within the agent sandbox environment.

---

## 2026-05-26 — V2 Dashboard Redesign + Narrative Pipeline (Day 1)

**Commits:** `037dc2e0ae`, `56362cecbe`, `fd517e165c`, `b41018a9a4`

Two major workstreams landed on the same day.

### V2 Dashboard
A three-pane dashboard redesign was integrated. This was a significant visual overhaul — new layout, new assets, new HTML structure. The V2 design reflects a more mature understanding of how precinct captains and campaign volunteers actually use the data.

**Terminology change:** "registered" voters → "affiliated" voters throughout the codebase. This was a correctness fix — in Ohio, all registered voters are in the file, but "affiliation" is the legally meaningful term (R.C. 3513.19). Using "registered" was technically imprecise.

### Narrative Pipeline (Workstream 1: Templates)
A new `tools/narrative/` package was built with:
- `templates.py`: Per-level deterministic narrative generation. 14 jurisdiction levels, each with its own configuration (which metrics to render, which officeholder slots to show, whether to embed parent county, etc.)
- `generate_narratives.py`: CLI and programmatic entry point. Cache-skip via `metrics_hash` so unchanged jurisdictions aren't rewritten.
- `TEMPLATE_VERSION = 'v2'`, `PER_LEVEL_CONFIG_VERSION = 'v1'`

**Why deterministic templates first, LLM second:** The template layer guarantees accuracy — it can only say what the data says. The LLM layer (Workstream 2) enriches the prose but always has the templated version as a fallback. This ordering prevents hallucination from affecting the data layer.

**archive_state.py improvements:** Memory directory matching was improved so the archive script correctly handles the `~/.claude/` path structure.

---

## 2026-05-27 — LLM Enricher + Full Integration (Day 2)

**Commits:** `3c248e8061`, `69bcf535f3`, `b5d551354a`, `fe975b4922`, `d8feae4f98`

### The core problem being solved
Template narratives are statistically accurate but clinical. A precinct captain reading "62.2% unaffiliated or lacking primary history" before knocking on a door doesn't know what to do with that. The goal: transform the same aggregate data into plain-English neighbor briefings — the kind of note you'd read on your phone and immediately understand.

### LLM Enricher (`tools/narrative/llm_enricher.py`)
**Model choice:** `claude-haiku-4-5`. Rationale: input is ~200 tokens (structured metrics), output is ~80-120 tokens (2-3 sentences). The task is prose rewriting, not reasoning. Ohio has ~10,000+ precincts — Haiku is ~5× cheaper than Opus for this volume.

**Two code paths:**
- `enrich_one()`: Synchronous, one API call per jurisdiction. Good for on-demand enrichment, dashboard endpoints, single-county runs.
- `enrich_batch()`: Anthropic Batch API. Submits all jurisdictions in one call at 50% of real-time pricing. Full Ohio run costs ~$3.

**Prompt caching:** The system prompt is marked `cache_control: ephemeral`. After the first call in a pipeline run, all subsequent calls within the 5-minute TTL pay ~0.1× for the cached system portion. At pipeline scale this pays back quickly.

**Cache key:** `captain_metrics_hash` = SHA-256(metrics + ENRICHER_VERSION + model)[:16]. Separate from the template `metrics_hash`. If data changes or the prompt version bumps, the hash mismatches and the jurisdiction gets re-enriched on the next run.

**PII guarantee:** Only aggregate statistics are sent to the API. No individual voter records, SOS voter IDs, or addresses ever leave the local pipeline.

**Graceful degradation:** If `ANTHROPIC_API_KEY` is absent or the `anthropic` package isn't installed, all functions return `None` silently. The pipeline always has the templated narrative as fallback.

### Cohort definitions clarification (`docs/cohort_definitions.md`)
Two language fixes:
- "inactive voters" → "low-frequency primary voters" for Pure D/R (more accurate — they vote, just infrequently)
- Party affiliation window: clarified it's triggered by the *most recent partisan primary ballot requested*, not just any participation during the window. This distinction matters for edge cases where a voter requested a ballot but didn't mark it.

### Google Drive upload script
A script was added to upload cohort definitions to Google Drive for sharing with Antigravity and other collaborators. Handles authentication flow.

### Full CLI integration (`tools/generate_narratives.py`)
Three new flags wired in:
- `--llm`: Sync enrichment, one call per jurisdiction inline during template loop
- `--llm-batch`: Batch API submission after all templates written (recommended for full-state runs)
- `--llm-force`: Re-enrich even if `captain_metrics_hash` is current (use after prompt changes)

`run_for_levels()` gained matching `llm`, `llm_batch`, `llm_force` kwargs for programmatic use by `ohio_voter_pipeline.py`.

### .gitignore fix
`.claude/settings.local.json` added to `.gitignore` and removed from tracking. This file holds machine-local Claude Code permissions and shouldn't be shared.

### Memory system initialized
First session to establish the `~/.claude/projects/D--vibe-election-data/memory/` directory. Prior sessions had been archiving `CLAUDE.md` as a proxy for project state — a reasonable workaround but not the right tool. The memory system is now properly initialized with user profile, feedback patterns, project state, and key file references.

**Journal established:** This file (`docs/journal/project_journal.md`) created to serve as the human-readable project evolution record — distinct from Claude's memory files (AI-facing) and git commit messages (what changed). This is the *why*.

---

## 2026-05-27 — Repo Organization Audit & Cleanup

**Session context:** Cowork (claude-sonnet-4-6)

### Why this happened

By late May the repository had accumulated enough clutter to hurt legibility: one-shot migration scripts that had never been removed from root, a parallel `SiteDesign/` directory out of sync with `docs/assets/`, handoff files scattered across three locations, a `tests/` directory that was gitignored despite containing real tests, and a `.gitignore` that had accumulated dead rules (including one that ignored itself). None of this broke the pipeline, but it created real cognitive overhead when navigating the GitHub view and a recurring pattern of manually deleting files that should never have been committed.

A full audit was commissioned (`docs/research/repo_organization_audit_2026-05-27.md`) covering every tracked file in the repo, organized by severity from GitHub-visible clutter to local-only PII hygiene.

### Key decisions and their rationale

**Agent instruction files: keep both filenames.** The audit proposed merging `CLAUDE.md` and `GEMINI.md` into a single `AGENTS.md`. This was rejected: Claude auto-discovers `CLAUDE.md` by filename convention, and the Antigravity CLI expects `GEMINI.md`. Renaming either silently breaks the tool that reads it. The correct fix was to strip `GEMINI.md` of content it duplicated from `CLAUDE.md` and have it point to `CLAUDE.md` for shared policy, keeping only Antigravity-specific context (phase status, memory stability notes, enriched-cache invalidation rules) in `GEMINI.md` itself.

**`docs/archive/` made private.** Ten files were tracked inside `docs/archive/` despite `docs/archive/` being listed in `.gitignore` — an incoherent state. The resolution was to untrack the existing files (`git rm --cached`) and enforce the gitignore rule consistently. The archive is now local-only: the `tools/archive_state.py` script still writes timestamped snapshots there, but they are not pushed to GitHub. This is the correct behavior since the archive contains CLAUDE.md and MEMORY.md snapshots that have no value to external readers.

**Handoff files consolidated into `docs/archive/handoffs/`.** Seven HANDOFF_*.md and DESIGN_*.md files were spread across `docs/research/`, `SiteDesign/`, and the repo root. These have historical value as a journal of the AI-to-AI session handoffs that built significant portions of the pipeline, but they are not reference material — they are process artifacts. They now live in `docs/archive/handoffs/` (gitignored, local-only), distinct from the CLAUDE.md state snapshots in `docs/archive/` root.

**`docs/research/` returned to its intended purpose.** The research folder was designed to hold web research, examples, and template source material the owner found while building the project. Three HANDOFF files had drifted in. After removing them, the folder now contains only genuinely external reference material.

**`patches/` convention established.** A recurring problem: one-shot Python patch scripts were written to repo root, applied, and then forgotten. The owner had to manually delete them at least twice. The fix: a `patches/` directory at root, gitignored, with the convention documented in `CLAUDE.md` and indexed in session memory. Every session should check whether `patches/` contains scripts whose targets have already been applied and delete them. The key insight is that the problem is behavioral (scripts landing at root) not just organizational — the gitignored directory forces scripts to be local-only and signals they have a fixed lifecycle.

**Pandas annotated, not dropped.** `CLAUDE.md` mandates Polars/DuckDB for all core pipeline operations. The audit surfaced that `pandas` is listed in `pyproject.toml` as a dependency. The actual usage is: `jurisdictional_groupings.py` (module-level import), `ohio_voter_pipeline_wrapper.py` (conditional import), and `tools/scoring/unc_lifetime_d_predictor.py`. These files predate the polars mandate and have not yet been migrated. The dependency was annotated in `pyproject.toml` noting exactly where it's used — dropping it without migrating those files would break the runtime.

**`precincts.info` CNAME confirmed live.** The audit flagged the CNAME file as potentially dead because the README pointed to the github.io subpath. Confirmed: `precincts.info` is the live custom domain. The CNAME was kept; the README URL was corrected.

### What changed on disk

- `SiteDesign/assets/` and its web files deleted (stale duplicates of `docs/assets/`)
- `apply_cache_and_mem_fix.py`, `apply_groupings_fix.py`, `main.py`, `command_history.log`, `docs/requirements.bak` removed
- Broken `.antigravitycli/` symlink removed
- `docs/archive/handoffs/` created with 7 handoff files
- `docs/research/` stripped of HANDOFF files; retains only web research
- `tools/test_jurisdiction_collisions.py` → `tests/` (now tracked alongside the three previously-untracked `test_pass_b_*.py` files)
- `patches/` directory created (gitignored)
- `.gitignore` pruned: removed self-ignore, dead per-file rules, `tests/` rule; added `.antigravitycli/`, `patches/`, `command_history.log`
- `README.md` script table rewritten to reflect `tools/` and `tools/scoring/` layout; install instructions updated to `uv sync`; dashboard URL corrected to `https://precincts.info`
- `pyproject.toml` description updated from placeholder; pandas dependency annotated
- `GEMINI.md` de-duplicated (reduced from 70 lines to ~30)
- Memory system updated with `patches/` convention note

### Execution note

The git staging and commits were handed off to a PowerShell script (sandbox FUSE mount blocks git index writes). All file edits were applied directly. The three-commit sequence — cleanup, restructure, hygiene — was the planned order; the PowerShell handoff collapsed them into one operator action.



## 2026-05-28 — City Column Fix: The PRECINCT_NAME Antipattern Exposed

**Session context:** Cowork (claude-sonnet-4-6)

### The problem that broke everything silently

`build_city_summary()` had been working correctly for Montgomery County from the start. That was the problem. Montgomery County's precinct naming convention happens to use the city name as a prefix — "KETTERING 1-A", "DAYTON 18-B". So `_extract_city(PRECINCT_NAME)`, which strips the alphanumeric-plus-whitespace suffix, returned the right answer in Montgomery. This made the function appear correct in development and pass every sanity check that used Montgomery as the test case.

The bug only manifests in a different county. In Greene County, Ohio — which shares the city of Kettering with Montgomery County — the precincts containing Kettering voters are named "BEAVERCREEK 090" and "SUGARCREEK 151". The precinct names reflect the physical precinct boundary township, not the voter's municipal address. `_extract_city` returned "BEAVERCREEK" and "SUGARCREEK". Those are valid county geographies. There is no error. The function just quietly assigned 537 Kettering voters to two cities that don't exist in any stakeholder-facing output.

The fix is straightforward once the bug is understood: use the `CITY` column, which carries the voter's registered address municipality. This is what `CITY` is for. The precinct name was never the right source.

**Scope of misclassification confirmed by Polars scan:** 2,067,475 voters across 135 cities and 144 county-city pairs — roughly 26% of all Ohio registered voters. Kettering was the visible case because it was the motivation for the drill-down feature. Every city that spans county lines had some version of this problem.

### Three-part fix

The repair touched three layers simultaneously.

**Python (`voter_data_cleaner_v2.py`):** `build_city_summary()` now uses `pl.col('CITY')` as the primary grouping key, with a fallback to `_extract_city(PRECINCT_NAME)` only when CITY is null or blank. This fallback covers the ~19 counties where the Ohio SOS does not populate the CITY field in the SWVF. A suffix normalization step was added to handle the " CITY" suffix that SWVF carries on city values ("KETTERING CITY" → "KETTERING"). The docstring was rewritten to document the architectural rationale so the next person reading the function understands that PRECINCT_NAME is not and was never a jurisdictional proxy.

**JSON regeneration (`tools/regen_city_summary.py`):** Rather than re-running the full Option 1 pipeline (which processes all 88 counties from scratch, rebuilds enriched parquet, and regenerates every output type), a targeted script reads only the three columns needed (`PRECINCT_NAME`, `VOTER_STATUS`, `CITY`) from the hive-partitioned parquet, adds `COUNTY_NUMBER` back as a literal (it is a partition key, not a column inside the parquet files), and calls the fixed `build_city_summary()` directly. All 88 `*_city_summary.json` files were regenerated in minutes. Greene > Kettering now appears correctly: 537 voters, 2 precincts.

**Precinct index (`tools/patch_precinct_index_city.py`):** The `*_precinct_index.json` files needed a `city` field so the client-side JavaScript could filter precincts by city without name-prefix guessing. The script imports `OHIO_COUNTIES` from `voter_data_cleaner_v2` to build a slug-to-number map, computes the dominant CITY value per precinct from parquet data using a group-by + sort + first chain, and writes the `city` field to each of the 3,924 precinct records across all 88 index files. Counties in the blank-CITY set get `city: null`.

**JavaScript (`docs/assets/v2.js`, `aggregateCityCharts()`):** The client-side filter was updated from name-prefix substring matching (`prec.name.startsWith(upper + ' ')`) to exact match on `prec.city`, with name-prefix as fallback for blank-CITY counties. This aligns the client behavior with what the Python layer now produces.

### The audit that followed

After fixing the immediate bug, the broader question became: how many other places in the codebase assume `PRECINCT_NAME` is a jurisdictional proxy? A systematic column-by-column audit was run against the full SWVF schema.

The result was illuminating in both directions.

**`RESIDENTIAL_CITY` — the unused obvious answer.** This column is 100% populated in all 19 blank-CITY counties. Confirmed by scanning Cuyahoga (one of the blank-CITY counties): 862,439 voters, 100% `RESIDENTIAL_CITY` populated, 0% `CITY` populated. Every instance of `_extract_city(PRECINCT_NAME)` across all fallback paths could be replaced with `RESIDENTIAL_CITY`, which is semantically correct and requires no regex. The six compiled regex patterns in `_PRECINCT_SUFFIX_PATTERNS` and the `_extract_city()` function itself can be deleted outright. They were solving a problem that the source data solves directly. The fact that they existed for this long is a consequence of validating the pipeline primarily against Montgomery, which has good CITY coverage.

**`WARD` — direct column, not in pipeline.** The SWVF carries a `WARD` column ("KETTERING WARD 1", "DAYTON WARD 18"), 52.6% populated in Montgomery. Wards are a distinct jurisdictional type meaningful to campaign operations — ward-level organizing is common in larger Ohio cities, and precinct captains often report to ward coordinators. `jurisdictional_groupings.py` currently has 12 jurisdiction types. `WARD` should be the 13th.

**`PRECINCT_CODE` — stable identifier, not in index.** The SWVF carries a `PRECINCT_CODE` column (e.g., "57AKT") that is more stable than `PRECINCT_NAME` across SOS file updates. The SOS occasionally renames precincts without changing codes. Adding it to `index_entries.append()` in the precinct indexer is a minor addition with long-term resilience benefits.

**`COUNTY_ID` cross-county misuse.** Confirmed that `COUNTY_ID` is county-scoped (the SOS reuses values across counties) and `SOS_VOTERID` is the correct statewide join key. No code was found actively misusing this, but the schema reference in CLAUDE.md was verified to make the distinction explicit.

### What still doesn't work, and why it's architectural

The cross-county city problem is partially solved. `aggregateCityCharts()` correctly identifies which precincts belong to Kettering using `prec.city` exact matching. But it only queries one county's precinct index — the one selected in the left panel. When a user clicks Montgomery > Kettering, the function fetches Montgomery's 41 Kettering precincts. It does not know to also query Greene's index for BEAVERCREEK 090 and SUGARCREEK 151.

Resolving this requires generating a `city_county_map.json` artifact during the pipeline — a lookup from city name to the list of county slugs that contain voters registered in that city. The client can then query multiple precinct indexes in a `Promise.all` before aggregating charts. This is Group 3 of the planned refactor.

The left-panel hierarchy builder (`populateCountyChildren()`) also still uses name-prefix matching to bucket precincts into city groups in the navigation tree. This means Greene's BEAVERCREEK 090 and SUGARCREEK 151 precincts — even though tagged `city: 'KETTERING'` in the index — won't appear under a "Kettering" city grouping in the Greene county left-panel view. This is a separate fix from the chart aggregation issue and also belongs to Group 3.

The expected visible behavior after all three groups are complete: clicking Montgomery > Kettering will aggregate charts across Montgomery's 41 Kettering precincts AND Greene's 2. Clicking Greene > Kettering will aggregate just the 2 Greene precincts. Both counties will list Kettering as a named city group in their left panels.

### Refactor plan

The next session is organized into three groups with increasing scope and risk.

**Group 1 — Housekeeping (~30 min):** Consolidate the three duplicate `generate_narratives` import blocks in `ohio_voter_pipeline.py` into a single `_load_generate_narratives()` helper at module level. Remove the unused `import os` at line 17. Reword menu option [3] ("skip jurisdictional groupings") to make clear that cities, townships, and districts are jurisdictional groupings — users have reported confusion about whether "skip jurisdictional groupings" also skips city summaries. Groups 1 and 2 are appropriate for Sonnet.

**Group 2 — Python data layer (~2 hr):** Delete `_extract_city()`, `_PRECINCT_SUFFIX_PATTERNS`, and all six compiled regexes. Replace all fallback calls with `RESIDENTIAL_CITY`. Add `WARD` as the 13th jurisdiction type in `jurisdictional_groupings.py`. Add `PRECINCT_CODE` to `index_entries.append()`. Run `regen_city_summary.py` after to produce clean output from the simplified fallback logic.

**Group 3 — JS architecture (~3 hr, Opus):** Generate `city_county_map.json` as a pipeline artifact. Rewrite `aggregateCityCharts()` for multi-county fetching via `Promise.all`. Fix `populateCountyChildren()` to group precincts by `prec.city` rather than name-prefix extraction. Group 3 involves enough multi-file architectural reasoning — the city_county_map format, the fetch loop structure, the fallback chain when a county's index is missing — that Opus is worth the cost for the design pass.

### README extension

`README.md` was extended with a `voter_data_cleaner_v2.py` reference section covering the smoke test invocation, the table of public entry points and their signatures, key build functions, targeted utilities, the data flow diagram, and the `COUNTY_NUMBER`-as-partition-key constraint (the most common source of KeyError for new contributors). This had been absent since the v2 refactor in April.

## 2026-05-28 — Refactor Groups 1–3 Executed: RESIDENTIAL_CITY, WARD, and Cross-County Aggregation

**Session context:** Claude Code (claude-opus-4-8)

This session executed all three refactor groups that the prior 2026-05-28 entry had laid out as pending. It was done as one Opus session rather than splitting Groups 1–2 to Sonnet, because the work was tightly coupled (the RESIDENTIAL_CITY swap, the regen tool's column list, and the cross-county map all depend on each other's correctness) and because Group 3 carried design decisions worth reasoning through in one continuous thread.

### Groups 1 & 2 — code cleanup and the data-layer correction

**Group 1 (`ohio_voter_pipeline.py`).** Removed the dead `import os` (zero `os.` references; `import sys` stays — it is still used at `sys.exit(1)`). The three duplicated deferred-import blocks for `generate_narratives` were collapsed into a single module-level `_load_generate_narratives()` helper that owns the `sys.path` insertion and returns the module; callers that want the `NON_COUNTY_LEVELS` constant read it as `_load_generate_narratives().NON_COUNTY_LEVELS`. The laziness is preserved deliberately — `tools/` has no `__init__.py`, and the narrative machinery is heavy and optional, so it must not become a top-level import. Menu option [3] was reworded to spell out that the skipped jurisdictional groupings include "cities, townships, wards, districts," closing the reported confusion about whether [3] also skips city summaries.

**Group 2 (`voter_data_cleaner_v2.py`, `jurisdictional_groupings.py`, `tools/regen_city_summary.py`).** The `_extract_city(PRECINCT_NAME)` fallback in `build_city_summary()` was replaced with the `RESIDENTIAL_CITY` column, and `_extract_city()`, `_PRECINCT_SUFFIX_PATTERNS`, and the six compiled regexes were deleted outright (48 lines removed, zero references remaining). This is the resolution the prior session's audit pointed to: `RESIDENTIAL_CITY` is the semantically correct fallback and is 100% populated in the blank-CITY counties, so the regex machinery was solving a problem the source data already solves. `PRECINCT_CODE` was added to `index_entries.append()` (read from the per-precinct frame, guarded for empty precincts). `WARD` was added as the 13th jurisdiction type.

**The WARD design refinement worth recording.** The prior session described WARD as "the 13th jurisdiction type." On inspecting the actual data, WARD values turned out to be *already fully-qualified* — "CLEVELAND WARD 8", "NORTH ROYALTON WARD 1" — with the city name baked in. That changes the design: unlike townships (which collide as bare "Washington Township" across 23 counties and therefore require the `county_scoped` composite key), wards are globally unique strings and must NOT be county-scoped. They were added as a plain non-county-scoped type, identical in shape to cities and school districts. The existing aggregation loop's generic filter (`len(str(j).strip()) > 1`) discards the empty-string WARD rows (rural and unincorporated precincts) automatically, so no loop changes were needed. This mirrors why cities are not county-scoped either: incorporated entities have unique names; geographic subdivisions don't.

**A latent bug caught before it shipped.** `regen_city_summary.py` loaded only `['PRECINCT_NAME', 'VOTER_STATUS', 'CITY']`. With the fallback now referencing `pl.col('RESIDENTIAL_CITY')`, the regen would have raised `ColumnNotFoundError` on every county. Fixed by adding `RESIDENTIAL_CITY` to the column list and updating the now-stale note text ("falls back to precinct-name extraction" → "falls back to RESIDENTIAL_CITY"). This is exactly the failure the "loud failures preferred" rule is meant to surface — and the reason verifying a column *reaches* the function matters more than verifying it merely exists in the parquet. The main-pipeline path was separately confirmed safe: `clean_voter_data()` only adds columns and filters rows (never a restrictive `.select()`), and the enriched cache is written wholesale, so RESIDENTIAL_CITY/WARD/PRECINCT_CODE all survive to `build_city_summary()`'s callsite.

**Verification.** `regen_city_summary.py` ran clean across all 88 counties. Cuyahoga — a 0%-CITY county that previously depended entirely on the now-deleted regex — now produces 59 real municipalities (Cleveland 236,702; Parma 51,036; …) with zero blank/unknown rows.

### Group 3 — cross-county aggregation, and a long design conversation

The headline feature: `aggregateCityCharts()` previously only ever queried the one county whose tree was clicked, so Montgomery > Kettering could never reach Greene's Kettering precincts (SUGARCREEK 151, BEAVERCREEK 090 — precincts whose *names* contain no hint of Kettering, which is why the old name-prefix logic was structurally incapable of finding them). The fix is a new pipeline artifact, `city_county_map.json`, inverting every precinct index's `city` field into `{ "CITY": ["county_slug", ...] }`, so the client can fan out across all counties containing a city.

**Design decisions, and the reasoning the owner pushed on:**

- **Map key = uppercase city name, not a nested structure with precinct refs.** Nested *feels* more flexible but duplicates the source of truth (the precinct→city mapping already lives in each index's `city` field), moves the "what counts as a Kettering precinct" filter rule out of the JS and into a baked artifact that can drift, and saves no fetches because the JS loads the indexes anyway. The flat map stores only what the per-county indexes *cannot* know locally: which *other* counties also contain the city. It is an index over the indexes, holding zero precinct facts of its own. Empirically validated: the 26 cross-county cities are all genuine multi-county municipalities (Columbus, Dublin, Loveland, Kettering, …), no false-name collisions — confirming that cities, being incorporated and uniquely named, are collision-free in a way townships are not.

- **Emit location: inline in the pipeline, not a standalone `tools/` script.** This reversed my initial recommendation, and the reversal is the instructive part. I had argued for a standalone tool on the grounds that a fresh repo-cloner should be able to rebuild the map from committed indexes without a full pipeline run. The owner surfaced the flaw: that argument silently assumed the committed JSONs are a *feature*. They are not — they are an accident. The repo's *intended* design ships code + provenance, and every cloner is meant to fetch the source gzips and reproduce the outputs themselves. In that world there are no committed indexes to scan, the standalone tool's reusability has no consumer, and the cross-county map is simply one more derived step of a from-scratch reproduction — i.e. inline pipeline logic, exactly the owner's original instinct. The one structural constraint that survives any framing: the map can only be computed *after* all 88 counties are written, and the pipeline writes them across 8 parallel workers, none of which can see "Kettering is in both Montgomery and Greene." So the emit lives in a final, single-threaded, post-all-counties step regardless — implemented as `_build_city_county_map()`, called at the end of the precinct-rebuilding branches (choices 1, 2, 3).

- **A larger realization, deferred deliberately.** The owner recognized mid-session that hosting chart content for website visitors and shipping reproducible code for cloners are two different products that have been conflated into one repo. The honest decomposition: this is "one generator, two destinations," not "two sets of tools" — both personas run the identical pipeline; only the last mile differs (the admin *publishes* the output, the cloner *discards* it). The real fork is therefore (1) stop committing `docs/data/`, and (2) add a publish path for the admin — and (2) is unbuildable until the host is decided (the owner flagged possible GitHub permissions/subscription limits and a possible host migration). So the publish-architecture split was deferred to a dedicated future session, and this session built only the persona-agnostic generator, which is correct in either end-state.

**The artifact emitted this session.** Rather than force a full pipeline run, `_build_city_county_map()` was invoked directly against the already-committed precinct indexes (no source files, seconds, low memory) to produce `docs/data/city_county_map.json`: 212 cities, 26 cross-county, 8.7 KB. `KETTERING → ['greene', 'montgomery']`. Both counties' `city_summary.json` already list Kettering (Montgomery 42,366 / 44 precincts; Greene 537 / 2), so the node now appears under both — and clicking it from either entry point aggregates the *same* whole-city chart totals.

**JavaScript (`docs/assets/v2.js`).** Added a cached, null-safe `loadCityCountyMap()` (falls back gracefully so the current live site keeps working before the map is committed). `aggregateCityCharts()` was rewritten to resolve the city's county list from the map, load each county's precinct index, collect matching precincts tagged with their own county slug, and fetch each precinct's six chart files from its *own* county namespace — so Greene precincts are fetched from `greene_precinct_*.json`, not `montgomery_*`. `populateCountyChildren()` now groups precincts by the authoritative `prec.city` field instead of longest-prefix-match on precinct name, with name-prefix retained only as a fallback for indexes lacking a `city` field.

### Performance / hosting note

The corpus is ~78,754 JSON files / ~98 MB, but for runtime that count is a red herring on a static site — what matters is requests-per-view, and the map adds one 8.7 KB fetch. The genuine scaling pressure (unrelated to this change) is that city aggregation is client-side fan-out over per-precinct files: Cleveland is ~256 precincts × 6 charts ≈ 1,500 requests on a cold cache. The eventual fix is pipeline-side pre-aggregated city chart files; the flat map is forward-compatible with that and does not worsen the common case.

### Method and process notes

All edits to files over 150 lines used Python patch scripts in `patches/` (gitignored), per protocol, with byte-level CRLF handling: `voter_data_cleaner_v2.py` and `jurisdictional_groupings.py` are CRLF (read bytes → normalize to `\n` → patch → re-encode to `\r\n`), while `ohio_voter_pipeline.py` and `docs/assets/v2.js` are bare-LF (write `\n`). Every patch was validated (`ast.parse` for Python, `node --check` for JS) and the scripts deleted after application. The stale `patches/fix_city_summary.py` was removed at session start. The Group 2 work was committed and pushed by the owner before Group 3 began.

**A workflow principle was recorded to memory:** when data needs regenerating and the rebuild is a local process with no token cost, prefer telling the owner to rerun the existing pipeline over writing a single-use regen tool — the tool spends the Anthropic bill to save local compute the owner does not care about. (So: to repopulate `precinct_code` into the indexes, the answer is simply to rerun `ohio_voter_pipeline.py` option [1] with precincts included; no bespoke tool.)

---

## Pending / Next Steps (as of 2026-05-28, post-refactor)

- **Precinct-index rebuild for `precinct_code`:** The `precinct_code` field is in code but absent from published `*_precinct_index.json` (still 0 across all indexes). Repopulate by rerunning `ohio_voter_pipeline.py` option [1] with precincts included — this also regenerates `city_county_map.json` in the same pass. Local rerun, no tool needed. Not a prerequisite for cross-county user testing (that path uses `prec.city`, already present).
- **Publish-architecture split (deferred, awaits hosting decision):** Stop committing `docs/data/` (gitignore + `git rm --cached`); add an admin publish path to whatever host is chosen. Blocked on the owner's hosting/permissions/migration decision. "One generator, two destinations."
- **Cross-county map partial-rebuild gap:** `_build_city_county_map()` fires from the full-rebuild branches (1/2/3) but not from targeted option [5], so a single-county rebuild leaves the map stale. Low-impact under the "everyone reproduces from scratch" model; documented, not solved.
- **User testing (ready now):** With v2.js + `city_county_map.json` pushed, testers should open Montgomery > Kettering and Greene > Kettering and confirm both show identical aggregated charts (~42.9k combined). Do not scope `precinct_code` into testing.
- **Officeholder data:** All 14 jurisdiction levels render "data not yet available." Next major content workstream.
- **LLM enrichment first run:** Enricher built, wired, integration-tested. Hamilton County precincts proposed as validation target before a full-state batch run.
- **Git push handoff (this session, owner-run):** Group 3 — `docs/assets/v2.js`, `ohio_voter_pipeline.py`, `docs/data/city_county_map.json`, and `docs/journal/project_journal.md`. Code via the owner's terminal alongside the single data artifact (the map is one small file, not the bulk `docs/data/` tree — the MCP data-push prohibition still applies to the ~78k-file tree).

---

## Appendix: Development Environment & Collaboration Guidelines

The following guidelines and constraints were formalized on **2026-05-27** to capture operational and environmental rules for this codebase:

### 1. Developer Environment & Sandbox Constraints
*   **File Editing Protocol (150-Line Limit):** Standard file editing tools and bash heredocs can silently truncate files longer than 150 lines inside the agent environment. To prevent downstream parse failures, modifications to files exceeding 150 lines must be executed using Python patch scripts.
*   **Sandbox Shell Differences:** The CLI sandbox executes shell commands in a Linux-like Bash environment, although the project host is Windows. PowerShell cmdlets (e.g., `Get-ChildItem`) will fail; use Python or standard Unix commands instead.
*   **Git Authentication Limitation:** Sandbox execution of `git push` fails due to the Windows Credential Manager (`wincredman`) credential-popups not being supported in the sandbox. `git push` commands must be handed off to the user's local terminal.
*   **Git Token Budget Protection:** Never push the generated data directories (such as `docs/data/` containing ~65,000 JSON files) using the agent's push tools, as this will exhaust the account token budget.

### 2. Collaboration & Workflow Guidelines
*   **User Profile & Project Audience:** The tools and captain briefings generated by the pipeline are built specifically for Democratic campaign volunteers and precinct captains doing door-to-door or phone outreach.
*   **Terse Confirmations:** The project owner uses terse approval messages (e.g., `"yes build"`, `"proceed"`, `"2"`, `"build"`). These are binding confirmations and indicate that the agent should execute the plan directly without entering verification or clarification loops.
*   **Codebase Key References:**
    *   Pipeline Entry Point: [ohio_voter_pipeline.py](file:///D:/vibe/election-data/ohio_voter_pipeline.py)
    *   Narrative CLI: [generate_narratives.py](file:///D:/vibe/election-data/tools/generate_narratives.py)
    *   LLM Enricher: [llm_enricher.py](file:///D:/vibe/election-data/tools/narrative/llm_enricher.py) (documentation: [README_llm_enricher.md](file:///D:/vibe/election-data/tools/narrative/README_llm_enricher.md))
    *   Cohort Classifier: [tools/scoring/](file:///D:/vibe/election-data/tools/scoring/)
    *   Jurisdictional Groupings: [jurisdictional_groupings.py](file:///D:/vibe/election-data/tools/jurisdictional_groupings.py)
