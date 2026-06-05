# Memory Index

- [Voter Analysis Project Scope](project_voter_analysis.md) — Montgomery County prototype → Ohio → US scale; unregistered resident matching; GIS visualization planned
- [Phase status and roadmap](project_phase_roadmap.md) — P1 complete (~7.9M rows, 88 partitions); P2-P5 intent ladder
- [Repo layout and active-script reasoning](project_repo_layout.md) — root engine / tools utilities / scoring isolation; non-obvious script behaviors; county_scoped flag
- [Cohort taxonomy (current)](project_cohort_taxonomy.md) — 7-cohort_family public surface; CROSSOVER_R/D held internally; `classify_all_voters_primary_history()` is the entry point
- [Six-chart consistency contract](project_chart_contract.md) — identical chart set across all geographies; `COHORT_SLICES`/`COHORT_STACK_MAP` are the single source of truth
- [Dashboard live state and routing](project_dashboard.md) — Pages URL, deep-link query schema, Jurisdictions tab routing, JSON regeneration TODO
- [SWVF data gaps](project_data_gaps.md) — CITY blank in 19 counties; columns SWVF doesn't carry (Last Activity Type, ballot method, CONFIRMATION subtype)
- [Pipeline safety — no try/except](feedback_pipeline_safety.md) — sole operator; loud failures preferred over silent degradation
- [Verify plan against repo state](feedback_verify_plan_against_repo_state.md) — read touched files before patching a confirmed plan; surface scope gaps before they balloon
- [GitHub push workflow — use MCP, not shell git](feedback_github_push_workflow.md) — 65k tracked files + FUSE mount = shell git always times out; load and use push_files MCP at session start
- [Archive state files before overwriting](feedback_state_archive_rule.md) — run `python tools/archive_state.py <path>` before any Write/Edit to CLAUDE.md or memory files; mirrors prior version into docs/archive/ with ISO timestamp
- [Prefer Read/Write/Edit over bash for known-file operations](feedback_tool_routing_read_write_edit_first.md) — bash only for execute, enumerate, or delete
