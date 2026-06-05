# Handoff: Narrative Build (Workstream 1)

Target session model: **Sonnet**. This brief contains everything needed to execute the build without re-asking design questions. The design is locked; do not re-litigate.

## Context in two paragraphs

The dashboard at `docs/v2.html` already renders a templated narrative card beneath the hero on the single-county view. Five counties (Hamilton, Franklin, Cuyahoga, Montgomery, Summit) have `{slug}_narrative.json` files written by `tools/generate_narratives.py` running in `--fake` mode, which is a deterministic template — not an LLM — and the `generated_by` field on those JSONs currently reads `fake-template-v1`. The plan adopted in the prior session renames `fake` → `templated` throughout, splits the inline template into a level-aware registry, inlines narrative generation as a final phase of `ohio_voter_pipeline.py`, adds a metrics-hash cache key, and extends dashboard fetch to precinct and district views. Officeholder weaving (Workstream 2) is a separate workstream and is **out of scope here**; the registry leaves slots for it and renders "data not yet available" placeholders.

The per-level template registry has already been drafted at `tools/narrative/templates.py` and verified across nine sample jurisdictions covering county / precinct / state senate district / congressional district / city / village / township / school district / municipal court. It exports `LEVELS`, `LEVEL_CONFIGS`, `TEMPLATE_VERSION`, `build_metrics_for_level()`, `build_narrative()`, and `metrics_hash()`. Use that module — do not rewrite it.

## Locked decisions (do not re-ask)

1. Replacement label: `templated-v1` in the JSON `generated_by` field; CLI flag `--fake` → `--templated`; function name `fake_narrative` → `templated_narrative` (or use the registry's `build_narrative()` directly and drop the standalone function).
2. Per-level customization depth: per-level templates with metric emphasis per level. The registry already implements this — county uses generations + decade trend; precinct uses party only; districts surface multi-county geography; municipalities embed parent county.
3. Pipeline integration: inline as final phase of `ohio_voter_pipeline.py`. Insert calls at the end of each branch of `_dispatch()` scoped to the levels just regenerated. Do not modify `voter_data_cleaner_v2.py` or `jurisdictional_groupings.py` internals; the narrative stage only reads their JSON output.
4. Officeholder scope: full roster (federal, state, county, municipal, judicial, precinct captain) is the eventual target, but **Workstream 2** — out of scope for this build. Render placeholders only.
5. Sequencing: ship narrative + rename + per-level templates first; officeholders later.
6. Missing-data UX: render a placeholder line per office, e.g. "State Senator: data not yet available." The registry already produces this.

## File-by-file checklist

### `tools/generate_narratives.py` (refactor)

Rewrite this script to use the registry. Specifically:
- Drop the inline `fake_narrative()` function and `build_metrics()` function; import from `tools.narrative.templates` instead.
- Rename `--fake` CLI flag to `--templated`; remove the "fall back to fake when no API key" auto-degradation and instead make `--templated` explicit. Keep `--dry-run` and `--overwrite` semantics.
- The `generated_by` field value becomes `templated-v1` when the registry produced the prose, or the model string (e.g. `claude-haiku-4-5-20251001`) when the API produced it.
- Add a `--level` argument that accepts one of the `LEVELS` values from the registry, plus `--all-levels` to iterate. Default to `county` to preserve existing behavior.
- Add per-level file enumeration: county uses `manifest.json` `processedCounties`; precinct walks `{county_slug}_precinct_index.json` for each county; districts/cities/townships/etc. walk `docs/data/{level}/*_party_affiliation.json`.
- Implement cache-skip via `metrics_hash`: if the existing output JSON has the same `metrics_hash` and `template_version`, skip regeneration even without `--overwrite`. Output JSON gets a new field `metrics_hash` from `templates.metrics_hash(metrics)`.
- Geography county lookup for districts is the gap — for now, leave `geography_counties=None` and ship; the registry handles missing geography gracefully. A follow-up issue can wire in a `district → counties` map (likely from `jurisdictional_groupings.py` or a precomputed sidecar).

### `tools/narrative/templates.py` (already drafted — do not rewrite)

Drafted in prior session. Use as-is. Bump `TEMPLATE_VERSION` only if you change template output shape; if you do, all narratives auto-invalidate on next run via the cache key.

### Backfill loop for existing five JSONs

One-shot: load each of `{hamilton,franklin,cuyahoga,montgomery,summit}_narrative.json`, regenerate via the new `--templated` path, overwrite. After this, `generated_by: fake-template-v1` is gone from disk. Or simpler: delete the five files and let the next pipeline run recreate them through the new path.

### `ohio_voter_pipeline.py` (file is 505 lines — use the patch-script template, do NOT use the Edit tool)

Add narrative invocation at the end of each branch in `_dispatch()`:
- Branches `1`, `2`, `3`, `5` rebuild county (and optionally precinct) JSON → invoke narrative for `county` (and `precinct` when `include_precincts`).
- Branches `1`, `2`, `4` rebuild jurisdictional grouping JSON → invoke narrative for all 12 non-precinct, non-county levels in `LEVELS`.
- Wrap each call in the project's existing `_timer` + psutil RSS pattern for observability.
- Failures must be loud (per `feedback_pipeline_safety.md`), but transient HTTP retries with bounded attempts are acceptable for the API path.

### `docs/assets/v2.js` (file is 1465 lines — use the patch-script template, do NOT use the Edit tool)

Currently only the `level === 'county'` branch in `loadJurisdiction()` adds the narrative fetch. Add the same line in the precinct branch and district branch:

- Precinct branch (~line 191): `add('narrative', \`data/${cs}_precinct_${ps}_narrative.json\`);`
- District branch (~line 200): `add('narrative', \`data/${t}/${id}_narrative.json\`);`

`renderNarrative()` already gracefully hides on missing data, so partial rollouts are safe.

### `docs/assets/v2.css`

No further changes — the narrative card styles shipped in the prior session.

## Critical operational rules

1. **Edit tool truncates silently on files > 150 lines.** This already bit twice in the prior session (v2.js lost 22 lines off the tail; templates.py lost the cache-key tail). For `ohio_voter_pipeline.py`, `v2.js`, and `voter_data_cleaner_v2.py` use the patch-script template in CLAUDE.md or `Path.write_text(content)` from inside a Python invocation. After every patch validate with `python3 -m py_compile` (Python) or `node --check` (JS).

2. **Do not push `docs/data/` via the GitHub MCP.** 65k tracked files broke the token budget before. Code changes via MCP `push_files`; narrative JSON files via manual `git push` from PowerShell.

3. **No try/except as control flow.** Loud failures preferred over silent degradation, per `feedback_pipeline_safety.md`. The narrative stage may use `try/except` around the API call for retry/backoff, but exhaustion must raise, not silently return None.

4. **Archive state files before overwriting.** `python tools/archive_state.py <path>` before any Write/Edit to `CLAUDE.md` or any `memory/*.md` file.

## Cache-key contract

```python
metrics_hash(metrics, officeholders) = sha256(json({
    'metrics':       metrics,
    'officeholders': officeholders or {},
    'template_v':    TEMPLATE_VERSION,
    'config_v':      PER_LEVEL_CONFIG_VERSION,
}))[:16]
```

Output JSON gains `metrics_hash` field. On regen, compare hashes; skip if identical. Bumping `TEMPLATE_VERSION` or `PER_LEVEL_CONFIG_VERSION` in `templates.py` invalidates all narratives automatically on next run — no `--overwrite` needed.

## Output JSON schema (target)

```json
{
  "geography": "county",
  "level":     "county",
  "jurisdiction_name": "Hamilton",
  "updated":   "2026-05-09",
  "generated_by":    "templated-v1",
  "template_version": "v2",
  "config_version":   "v1",
  "metrics_hash":     "d3fdcd54da43a662",
  "narrative":  "Hamilton County has 602,004 registered voters, with 59.4%..."
}
```

The dashboard's `renderNarrative` reads only `narrative`, `updated`, `generated_by` — the new schema fields are forward-compatible and ignored client-side. No dashboard changes needed for the rename beyond the precinct/district fetch lines noted above.

## Verification checklist (before claiming done)

1. `python3 -m py_compile tools/generate_narratives.py tools/narrative/templates.py tools/narrative/__init__.py ohio_voter_pipeline.py`
2. `node --check docs/assets/v2.js`
3. `python tools/generate_narratives.py Hamilton --templated --overwrite` → confirm output JSON has `generated_by: templated-v1`, `metrics_hash` present, narrative reads cleanly.
4. `python tools/generate_narratives.py --level precinct Hamilton --templated` → narrative JSON appears for each precinct in `hamilton_precinct_index.json`.
5. `python tools/generate_narratives.py --level state_senate_district --templated` → narrative JSON appears in `docs/data/state_senate_district/`.
6. Cache test: re-run step 3 without `--overwrite` — should report skipped, not regenerated.
7. Cache invalidation test: bump `TEMPLATE_VERSION` in `templates.py` to `v3`, re-run step 3 — should regenerate.
8. Open `docs/v2.html` locally, navigate to Hamilton County → narrative card renders with new label. Navigate to a Hamilton precinct (e.g. Addyston A) → narrative card renders.
9. Sample five precincts and five districts; confirm prose reads sensibly.

## Git commit guidance

Per project rule, batch all code changes in one MCP `push_files` call. Suggested commit message:

```
feat(narrative): per-level templated narratives + pipeline integration

- tools/narrative/templates.py: level-keyed registry (14 jurisdiction types)
  with statistical floors, per-level metric emphasis, officeholder
  placeholders, metrics-hash cache key
- tools/generate_narratives.py: refactored to use registry; renamed
  --fake → --templated; added --level and --all-levels; metrics-hash
  skip logic replaces --overwrite for unchanged metrics
- ohio_voter_pipeline.py: inline narrative phase after each chart-JSON
  export branch; wrapped in _timer + RSS logging
- docs/assets/v2.js: extend narrative fetch to precinct and district
  branches (county branch already wired)
- output JSON schema gains level, template_version, config_version,
  metrics_hash; generated_by becomes 'templated-v1' for non-API output
```

Narrative JSON files (`docs/data/*_narrative.json` and `docs/data/{level}/*_narrative.json`) must be pushed manually via PowerShell, not through MCP:

```powershell
cd D:\vibe\election-data
git add docs/data/*_narrative.json docs/data/*/*_narrative.json
git commit -m "feat(narrative): regenerate templated narratives across all levels"
git push
```

## Things explicitly out of scope (Workstream 2)

- Officeholder sourcing pipeline (Bioguide, ProPublica, OpenStates, OH SoS, BoE scraping, party rosters)
- `jurisdictional_offices.json` schema and population
- LLM-path implementation (API key handling, rate-limit retry, model selection)
- District → counties geography map for `lead_with_geography: True` levels (placeholder for now)

## Things worth flagging when you finish

- Total narrative JSON count after a statewide run. Should be on the order of: 88 county + ~9k precinct + 15 congressional + 33 state senate + 99 state rep + 250 city + ~1,300 township + ~700 village + 600 school district + ~120 court = ~12k files. If meaningfully off, investigate enumeration logic.
- Any per-level prose that reads obviously wrong on the sampled cases; we'll iterate.
- Total wall-clock for the statewide templated run. Should be seconds to single-digit minutes; if it's longer, there's an I/O issue worth flagging.
