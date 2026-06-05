CLAUDE.md review — instruction inventory, efficiency analysis, and a better approach to project-state capture
=================================================================================================================

Generated 2026-05-13 against `D:\vibe\election-data\CLAUDE.md` (~200 lines). Each distinct rule, guideline, fact, or state declaration is enumerated below with an honest pro/con read on whether it earns its slot in a file that ships into every conversation.

The unifying frame is Anthropic's own published guidance: CLAUDE.md is loaded at the start of every session, every line competes for finite instruction-attention bandwidth, and Anthropic explicitly tells the model "this context may or may not be relevant" — meaning Claude is permitted, even encouraged, to ignore CLAUDE.md content it judges off-topic ([Anthropic — Best practices for Claude Code](https://code.claude.com/docs/en/best-practices); [HumanLayer — Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)). The peer-reviewed research HumanLayer cites indicates frontier thinking models follow ~150–200 instructions before quality degrades uniformly across the prompt, and Claude Code's own system prompt already consumes ~50 of those slots ([arXiv 2507.11538](https://arxiv.org/pdf/2507.11538)). Anything in CLAUDE.md that is not universally applicable is a tax on every other rule's adherence.

Instruction inventory
---------------------

1. **File editing protocol table (≤150 lines → Edit; >150 → Python patch script).** Efficient: it encodes a hard-won, project-specific failure mode (silent Edit-tool and heredoc truncation observed at 951 lines / ~50-line payloads) that Claude cannot infer from the codebase. This is the canonical "thing Claude can't guess" content Anthropic's docs say *should* live in CLAUDE.md. Inefficient: the threshold "150 lines" is a heuristic, not a measured cutoff; a single load-bearing patch attempt against a 140-line file could still truncate. The rule would harden if it specified *behavior* ("verify post-write via re-read or AST parse regardless of size") rather than gating on a length proxy.

2. **Patch-script template (read → assert count == 1 → write).** Efficient: includes the failure-mode insurance (`assert src.count(old) == 1`) that turns silent overlapping-match bugs into loud failures. Inline code samples Claude can copy beat prose descriptions for procedural work. Inefficient: an inline ~10-line template eats roughly five instruction slots and will rot if the project moves to Ruby/Go subcomponents. Anthropic's preferred pattern is to put procedural recipes in a Skill under `.claude/skills/` and let the description-based loader pull them in only when relevant ([Anthropic — Best practices](https://code.claude.com/docs/en/best-practices)).

3. **>50-line payloads must use `Path.write_text`, never heredoc.** Efficient: directly addresses an observed shell-tool truncation. Inefficient: redundant with rule 1; the same guardrail could be expressed once ("never trust unverified writes; always validate via re-read or AST parse") instead of branching by mechanism.

4. **Post-patch validation (`ast.parse` for Python, `node --check` for JS).** Efficient and high-value — this is the "give Claude a way to verify its work" pattern that Anthropic calls "the single highest-leverage thing you can do" ([best-practices](https://code.claude.com/docs/en/best-practices)). It would be even more efficient as a `PostToolUse` hook in `.claude/settings.json`, because hooks are deterministic where CLAUDE.md instructions are advisory; Anthropic explicitly recommends hooks for "actions that must happen every time with zero exceptions."

5. **"Bottom-up geospatial pipeline" project overview paragraph.** Efficient: gives Claude the WHAT and WHY HumanLayer emphasizes — anchoring all downstream questions. Inefficient: includes phase descriptions (P3+ integration of census, USPS NCOA, etc.) that bias the model toward not-yet-implemented features. A WHAT/WHY paragraph could be 3 sentences instead of 5.

6. **Processing principles — Polars/DuckDB, not Pandas.** Efficient: a negative rule that prevents a near-certain default ("Pandas is the most common pattern") from being chosen. Anthropic explicitly recommends negative rules in CLAUDE.md. This is exactly the right shape and length.

7. **Parquet partitioned by county; GeoParquet for spatial.** Efficient: an architectural decision Claude cannot derive from inspecting the repo without doing a costly tree scan. Earns its slot.

8. **Excel only for final aggregated stakeholder outputs via xlsxwriter/openpyxl.** Efficient: combines a tool choice with a use-boundary in one line. Note: the phrase "never load raw files into Excel" is the load-bearing half — a reader is more likely to internalize the prohibition than the library name.

9. **Provenance preservation (BoE timestamps, original headers, source URLs).** Efficient as a principle, inefficient as expressed: "preserved" is fuzzy. A more useful version would say *where* provenance is preserved (column suffix? sidecar JSON? parquet metadata?). As written, two consecutive sessions could reasonably interpret it differently.

10. **Zero-trust security; never commit raw PII; .gitignore covers `./working/` and `./source/`.** Efficient and load-bearing. Negative rules around data exfiltration belong in CLAUDE.md verbatim.

11. **Web delivery requirements (SPA on `/docs`, WebGL planned, lazy-load, screenshot/print-ready, dark/light).** Mixed efficiency: the "what's deployed today" half is useful onboarding; the "WebGL via Deck.gl/MapLibre planned" half describes vaporware and competes for attention against rules that govern current work. The planned-feature notes belong in `docs/research/` or an issue tracker, not in the session preamble.

12. **Stakeholder Excel formatting requirements (frozen rows, bold headers, auto-width, filters, conditional formatting, print-ready).** Efficient for the rare session that actually produces a deliverable xlsx. Inefficient as universal context: a session debugging the parser parsing logic gets nothing from it. This is the textbook progressive-disclosure case — should be a Skill (`.claude/skills/stakeholder-xlsx/SKILL.md`) that auto-loads only when the prompt references Excel deliverables.

13. **Phases P1–P5 with status flags.** Mixed: the P1 ✓ marker is useful state; the P2–P5 narratives are roadmap. Roadmap drifts faster than CLAUDE.md is updated and biases the model toward speaking as though Phase 2+ infrastructure exists.

14. **File locations (Raw: `source/`, Working/final: `./`).** Efficient. Two lines, high signal, can't be inferred without listing the tree.

15. **Schema reference block — 4 SWVF files, pipe-delimited, 46 static + 89 dynamic cols.** Efficient: this is genuinely irreplaceable WHAT context. Without it, Claude wastes a session reading the raw header line.

16. **`SOS_VOTERID` is the statewide join key; `COUNTY_ID` is county-scoped, never cross-county.** Efficient and load-bearing — exactly the kind of non-obvious gotcha CLAUDE.md exists for. A misuse here corrupts every downstream aggregate.

17. **Identity / demographics column enumeration.** Inefficient at this length. A Skill or `docs/schema.md` reference would serve better, since these column names are also literally in the parquet schema Claude can scan in <2 seconds. Anthropic's docs explicitly say not to include "anything Claude can figure out by reading code." This block likely earns its slot for the brief annotations (DOB format, etc.), not the bare column names.

18. **Registration / status semantics — REGISTRATION_DATE never reassigned, VOTER_STATUS collapses 6+ substatuses, PARTY_AFFILIATION derived from primary history.** Efficient and high-value. This is irreducibly domain-specific institutional knowledge encoded in Ohio EOM Ch.15 that the parquet itself does not reveal. Cite the Ohio Election Officials Manual reference more precisely (chapter + section) and this becomes near-perfect CLAUDE.md material.

19. **PII column enumeration (residential and mailing addresses).** Efficient. Repeats principle 10 with the specific column list. Worth the redundancy because the consequence of a leak is asymmetric.

20. **Jurisdictional aggregation keys (long enumerated list).** Inefficient at this length. Most sessions touch one or two jurisdiction types. Same Skill case as item 12.

21. **CITY column data gap — 19 counties blank, dated 2026-05-13.** Mixed: critical to know if you're querying city aggregations, irrelevant otherwise. The date stamp at least lets future sessions judge staleness, but the right home is a dated note in `docs/research/data_gaps.md` referenced from CLAUDE.md.

22. **County-scoped types — composite key `(COUNTY_NUMBER, name)` for townships, villages, municipal_court_districts.** Efficient and load-bearing. Like rule 16, getting this wrong silently corrupts aggregates.

23. **Election history format `[TYPE]-[MM/DD/YYYY]`, value semantics (R/D/X/empty), 2-blank-year confirmation rule.** Efficient. Irreplaceable domain knowledge.

24. **"Not in SWVF" gaps — Last Activity Type, ballot method, CONFIRMATION subtype.** Efficient negative space — tells Claude not to hallucinate columns that look like they should exist.

25. **External resource URL for precinct canvass.** Efficient. A reference pointer beats an embedded copy.

26. **Error policy — log malformed rows to `./working/errors/[county].log` and continue.** Efficient, clear, deterministic. Pairs well with the "no try/except" feedback memory in `MEMORY.md`.

27. **Project state — "Phase 1 complete. 88 partitions, 7,892,613 rows × 135 cols."** This is exactly the content the user flagged. *Inefficient as CLAUDE.md content* for three reasons. First, it ages: the row count will drift the next time SWVF updates; the partition count will not, but the file gives no signal of which numbers are stable. Second, it competes for attention against rules that govern current behavior — Anthropic's research shows that more instructions degrade adherence on *all* instructions, not just the irrelevant ones. Third, the state is recoverable: a 2-line shell command (`duckdb -c "select count(*) from 'source/parquet/*/*.parquet'"`) regenerates it on demand. The lower-cost alternative is covered in the dedicated section below.

28. **Directory layout (2026-05-09 reorganization) — tools/ hierarchy, scoring/ module, root engine-only.** Same problem as item 27, in worse shape: this is structural metadata that Claude can derive from `ls -R tools/` in one call. Dated layout notes will silently lie the moment someone moves a file without updating CLAUDE.md.

29. **Active scripts roster with one-line descriptions.** Mixed. The descriptions ("`jurisdictional_groupings.py` — multi-jurisdiction aggregator. JURISDICTIONS dict with column, display, optional county_scoped flag") encode behavior Claude cannot infer cheaply. The roster *list* itself is repeated work. The right shape is a `tools/README.md` that the file system already wants to host, referenced from CLAUDE.md via Anthropic's `@docs/tools-README.md` import syntax (see Anthropic memory docs).

30. **Dashboard URL, deep-link pattern, dated bug fix (2026-05-07).** The URL is reference content (good); the dated bug fix is git-log content (bad — `git log docs/charts.js` is authoritative).

31. **Pass B and Pass C status notes (2026-05-12, 2026-05-13) — Jurisdictions tab added, UI consolidated, etc.** This is changelog content that belongs in `CHANGELOG.md` or git commit messages. Including it in CLAUDE.md trades against every rule that governs *future* work.

32. **Dashboard JSON status / "re-run jurisdictional_groupings.py after deleting old phantom-merged dirs."** Pure stale-state TODO. Belongs in an issue tracker or `TODO.md`. If it has not been done by now (2026-05-13, ~24 hours after Pass C), the rule will mis-fire when someone *has* done it but forgotten to update CLAUDE.md.

33. **Cohort taxonomy notes (2026-05-08) — 7 cohort_family values, no decay scoring, classify_unc_primary_history legacy wrapper.** Mixed. The taxonomy itself is load-bearing (Claude needs to know there are 7 cohorts and what "pure" means). The "pending caller audit before removal" TODO is task-tracking content.

34. **County-scoping Pass A notes (2026-05-10) — slug format, display label format, career_centers dropped.** Mostly redundant with rule 22. The slug-format detail is useful; the "Pass A" framing only matters during the active refactor.

35. **Chart consistency contract — 6-chart table with types and stack IDs.** Efficient *if* chart work is a frequent session theme. Inefficient as universal preamble. Strong Skill candidate (`.claude/skills/chart-contract/SKILL.md`).

36. **Pipeline architecture (ThreadPoolExecutor max_workers=8, orjson, psutil RSS logging, enriched-parquet cache).** Efficient: explains *why* the code looks the way it does, which Claude cannot infer from the code itself. The reasoning ("shared address space, no IPC, no WinError 1450") is the load-bearing part. The peak-RSS figure (45 GB) and 80s cost figure are aging facts that don't change the architecture and could be trimmed.

37. **Install command (`pip install orjson psutil`).** Efficient — one line, can't be guessed. Anthropic-canonical content.

38. **Git `.git/index.lock` recovery command.** Efficient: dispatches a known recurring failure with a copy-paste fix.

39. **GitHub Pages `/docs` on `main`, Actions build ~40s.** First half is structural (efficient); second half is a benchmark that ages.

40. **Pending cleanup list (`git rm --cached` for GEMINI.md, old v1, stray PNGs).** Pure TODO. Belongs in an issue or `TODO.md`.

41. **Git push rule — MCP vs Manual, including the 65k-file warning and decision table.** Efficient and load-bearing — exactly the kind of "we tried this and it nuked our token budget" guardrail CLAUDE.md exists for. The negative framing ("Never push docs/data via MCP") is correctly emphatic. The PowerShell command snippet earns its space because it's the recovery procedure. This block is among the strongest in the file.

42. **"Last updated" footnote and `.bak` filename.** Inefficient as a Claude-facing instruction; useful as a human commit-log artifact, but git tracks both for free.

Summary of where this CLAUDE.md leaks attention
------------------------------------------------

By rough count, ~17 of the 42 distinct items above (40%) are universally applicable rules: file-editing safety (1–4), processing principles (6–10), schema/domain semantics (15–18, 22–24, 26), git push rule (41). Those are the rules that *should* be loaded on every session.

The other ~25 items are some mix of: (a) state that ages, (b) changelog that git already tracks, (c) domain detail relevant to one workflow but not others, (d) roadmap that biases the model toward speaking as if planned work exists. HumanLayer's measurement that their root CLAUDE.md is "less than sixty lines" is not arbitrary — it's the empirical lower bound that keeps instruction-following near the ceiling of the model's bandwidth. This file is ~200 lines, so by HumanLayer's heuristic it's carrying ~140 lines of attention tax.

Two diagnostic symptoms of bloat to watch for in this project: Claude ignoring a rule despite having "IMPORTANT" markers (rule lost in noise — Anthropic flags this as the canonical bloat signal), and Claude asking questions whose answers are in CLAUDE.md (phrasing buried too deep to surface). If either is happening, the file is past its useful density.

A better approach to capturing project state
---------------------------------------------

The user's core question — "an instruction was added to capture project state in that file but I wonder if there is a better, Anthropic or community determined approach" — has a clean answer with strong precedent. The current pattern (embed state directly in CLAUDE.md, manually update the "Project state" block, manually update the "Last updated" footnote) is the lowest-leverage option available. There are three Anthropic- or community-blessed alternatives, each with a tradeoff profile.

**Option A — Progressive Disclosure via a separate state file referenced from CLAUDE.md.** Anthropic's own memory documentation supports `@path/to/file.md` import syntax in CLAUDE.md, which means CLAUDE.md can read `@docs/project_state.md` on session start without inlining its contents. HumanLayer pushes this further: keep `agent_docs/` files (`building_the_project.md`, `pipeline_state.md`, etc.) and reference them by name with one-line descriptions in CLAUDE.md, letting Claude decide which to read. This collapses your "Project state," "Directory layout," "Active scripts," "Pass B/C status," and "Dashboard JSON status" sections — currently ~70 lines of CLAUDE.md — into a single 4-line pointer block, freeing ~35% of your file budget for rules that should be universal. Tradeoff: requires you (or Claude) to maintain `docs/project_state.md` as a discipline. Best fit for slow-changing state.

**Option B — Auto-memory via `MEMORY.md` (the system you already have).** You already operate the Cowork two-tier memory system (CLAUDE.md as working memory, `memory/` directory for the knowledge base, MEMORY.md as the index — visible in this conversation's system prompt and in your own `productivity:memory-management` skill). This is the Anthropic-canonical answer for Cowork specifically. The bargain is: factual project state goes into `memory/project_*.md` files indexed by `MEMORY.md`; CLAUDE.md only holds rules and irreducible schema. Auto-memory loads the first 200 lines / 25KB of `MEMORY.md` per session, then Claude pulls specific memory files on demand. Your existing memory already contains `project_voter_analysis.md`, `project_cohort_taxonomy.md`, and `project_repo_layout.md` — meaning the architecture is in place and CLAUDE.md is partially duplicating it. The cleanest move would be: delete the "Project state," "Directory layout," "Dashboard JSON status," and Pass B/C blocks from CLAUDE.md, and let MEMORY.md carry them. Tradeoff: the memory system is Cowork-specific; if you ever want this project to be portable to vanilla Claude Code, you lose the auto-loading. Best fit for state that changes weekly and that you want decoupled from the team-shared CLAUDE.md.

**Option C — Hooks for deterministic state updates.** Anthropic recommends `PostToolUse` hooks for any state that *must* stay accurate. A 20-line hook script (or a tiny Python tool invoked from `.claude/settings.json`) could regenerate a `STATE.json` after every parquet rebuild: row counts, partition counts, last-mtime per county, file checksums of the active scripts. Claude would read `STATE.json` (small, structured, parseable in one tool call) instead of trusting a hand-edited prose block. Tradeoff: more upfront wiring, and `STATE.json` doesn't carry narrative. Best fit for facts that have a deterministic single source of truth (row counts, file paths, partition mtimes) but a poor fit for institutional decisions ("we collapsed CROSSOVER_R/D into MIXED_ACTIVE").

The pragmatic recommendation, given that you already run the two-tier Cowork memory system, is to commit to Option B for project state, reserve CLAUDE.md for rules and irreducible schema, and adopt Option C only for the row/partition/mtime numbers if you find yourself updating them more than monthly. Option A is the better fit if you ever expose this repo to non-Cowork contributors. The three are not mutually exclusive; HumanLayer's blog and Anthropic's docs both treat CLAUDE.md + skills + hooks + auto-memory as a layered stack rather than a single channel.

One uncertainty worth flagging: Anthropic publishes no quantitative guidance on optimal CLAUDE.md length specifically for the Cowork-on-desktop runtime as opposed to the Claude Code CLI runtime. The "<300 lines, ideally <60" figure comes from HumanLayer's analysis of the CLI harness ([Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)) and Anthropic's CLI docs ([Best practices](https://code.claude.com/docs/en/best-practices)). The Cowork desktop runtime almost certainly inherits the same instruction-attention dynamics — same models, same loading pattern — but I have not found an Anthropic publication that confirms this in print as of this writing.

Sources
-------
- [Anthropic — Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [Anthropic — Store instructions and memories](https://code.claude.com/docs/en/memory)
- [HumanLayer — Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [HumanLayer — 12-factor agents, factor 3: own your context window](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md)
- [arXiv 2507.11538 — instruction-following degradation in LLMs (cited by HumanLayer)](https://arxiv.org/pdf/2507.11538)
- [Anthropic Help Center — Organize your tasks with projects in Claude Cowork](https://support.claude.com/en/articles/14116274-organize-your-tasks-with-projects-in-claude-cowork)
