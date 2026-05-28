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


## Pending / Next Steps (as of 2026-05-27)

- **Officeholder data:** All 14 jurisdiction levels currently render "data not yet available" for elected officials. Sourcing this data is the next major workstream.
- **`ohio_voter_pipeline.py` integration:** Pass `llm_batch=True` to `run_for_levels()` in the narrative phase so the full pipeline automatically enriches narratives on a complete run.
- **First live LLM enrichment run:** The enricher is built and wired — it hasn't been run against real data yet. A test run against Hamilton County precincts would validate the system prompt and output quality before a full-state batch.
- **JSONL session review:** Prior session transcripts (`~/.claude/projects/D--vibe-election-data/*.jsonl`) have not yet been reviewed to fill in the journal placeholders for sessions before 2026-05-26.

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
