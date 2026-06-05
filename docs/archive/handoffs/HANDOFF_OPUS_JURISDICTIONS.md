# Handoff: Jurisdictional Groupings — Design & Correctness

**Date**: 2026-05-10  
**Status**: Data pipeline running. Design decisions needed before dashboard integration.  
**Repo**: https://github.com/motorbikematt/ohio_voter_registration_parser  
**Dashboard**: https://motorbikematt.github.io/ohio_voter_registration_parser/  
**Data dir**: `D:\vibe\election-data`

---

## Your first job

Do not start writing code. Read this document, then ask the user the design questions in the **Decision Points** section before touching anything. The user wants to be prompted.

---

## What works today

The dashboard renders counties and precincts with a 6-chart format:

- Party Affiliation (doughnut, 7-cohort COHORT_SLICES)
- Age by Decade (bar)
- Age by Generation (bar)
- Party × Decade (stacked bar)
- Party × Generation (stacked bar)
- UNC Shadow (stacked bar)

Deep links work: `?county=Montgomery&geo=precinct-detail&precinct=DAYTON+8-B#decade-distribution`

The Parquet cache is complete: 88 Hive-partitioned files, 7,892,613 rows × 135 columns at
`source\parquet\COUNTY_NUMBER=XX\part-0.parquet`.

The enriched frame has 155 columns after `clean_voter_data()` adds cohort classification
(`cohort_family`, `Decade`, `Generation`, 15 cohort columns).

---

## What just ran

`jurisdictional_groupings.py` completed a full aggregation pass (all 12 jurisdiction types)
as part of a pipeline option 1 run on 2026-05-09/10. Files were written to:

```
docs/data/city/        ← subdirectory created by jurisdictional_groupings.py
docs/data/township/
docs/data/village/
docs/data/local_school_district/
... (one subdirectory per jurisdiction type)
```

---

## Problem 1: Output path mismatch (must fix before dashboard integration)

The existing county and precinct JSON files are **flat** in `docs/data/`:
```
docs/data/montgomery_party_affiliation.json
docs/data/montgomery_precinct_dayton_8_b_party.json
```

`jurisdictional_groupings.py` writes to **subdirectories**:
```
docs/data/city/columbus_party_affiliation.json
docs/data/township/washington_township_party_affiliation.json
```

The manifest (`docs/manifest.json`) and dashboard (`docs/charts.js`) currently reference
flat paths. The subdirectory output is invisible to the dashboard as-is.

**Options**:
A. Flatten — change `jurisdictional_groupings.py` to write to `docs/data/` using
   type-infixed filenames: `columbus_city_party_affiliation.json` (matches the pattern
   the handoff doc from the previous session anticipated).
B. Subdirectory — keep subdirectories and update manifest + charts.js to reference
   `data/city/columbus_party_affiliation.json`.
C. Hybrid — subdirectories for new types, keep counties flat (easiest backward compat).

---

## Problem 2: Township and village name collisions (data correctness)

Ohio has 810 unique township names in SWVF, but 152 of them appear in more than one county.
"Washington Township" appears in 23 counties. These are 23 legally distinct entities.

The current aggregation groups by township name alone — so all 23 Washington Townships were
merged into one JSON file. The voter counts and cohort distributions in that file are
meaningless: they represent a phantom statewide entity that does not exist.

**Affected types**: `townships`, `villages` (same problem by identical mechanism).  
**Not affected**: cities (Columbus spanning 3 counties is one city), school districts,
legislative/judicial districts (all statewide by design).

**The fix** requires county-scoping the aggregation key for townships and villages:
- Filter by `(COUNTY_NUMBER, TOWNSHIP)` instead of `TOWNSHIP` alone
- Slug becomes `{county_slug}_{township_slug}` e.g. `montgomery_washington_township`
- The jurisdiction display name becomes "Washington Township (Montgomery Co.)"

The collision counts from the test run:
- Cities: 26/212 span multiple counties — all correct (multi-county cities)
- Townships: 152/810 collide — all incorrect (distinct entities, same name)
- Villages: similar collision rate (not yet quantified precisely)

The test script lives at `D:\vibe\election-data\test_jurisdiction_collisions.py`.

---

## Problem 3: Deep-link URL design for county-scoped townships

The current deep-link scheme for precincts:
```
?county=Montgomery&geo=precinct-detail&precinct=DAYTON+8-B#decade-distribution
```

For cities (no county-scoping needed):
```
?scope=city&name=Columbus#decade-distribution
```

For townships (county-scoped):
```
?scope=township&county=Montgomery&name=Washington+Township#decade-distribution
```

The user currently shares URLs with `#anchor` pointing directly to a specific chart.
This feature must be preserved for all jurisdiction types.

**Design questions**:
- Does the township URL include `county` as a separate parameter, or is the county
  encoded into the name ("Washington Township — Montgomery Co.")?
- Does the dashboard show a county filter when scope=township is selected, or does it
  show all county-qualified names in one flat dropdown?
- Are non-colliding townships (unique names) treated the same way as colliding ones for
  URL consistency, or do they get simpler URLs?

---

## Decision Points — ask the user these before writing any code

1. **Output path**: flat (type-infixed filenames) or subdirectory structure? This choice
   cascades into manifest format and charts.js routing.

2. **Township/village scope in the UI**: Does the user want townships in the dashboard at
   all right now, or should they be deferred until county-scoping is implemented correctly?
   (Cities and school/legislative districts are correct and could ship independently.)

3. **Township URL design**: county as a separate URL parameter, or encoded into the display
   name? Or a two-step UI (pick county first, then township)?

4. **Collision handling for non-colliding townships**: uniform treatment (always
   county-scoped slug) or only scope the ones that actually collide?

5. **Re-run scope**: after design decisions, does the user want to delete the current
   township/village output and re-run only those types (pipeline option 4 with partial
   jurisdiction list), or is a full rebuild acceptable?

---

## Key files

| File | Purpose |
|---|---|
| `jurisdictional_groupings.py` | ~620 lines. Aggregation + export. Lines 153–201: JURISDICTIONS dict. Lines 209–213: `_slugify()`. Lines 426–454: `export_jurisdiction_json()` — writes to subdirs. Lines 539–582: pre-partition + resume logic (recently patched). |
| `ohio_voter_pipeline.py` | ~510 lines. Menu driver. `_dispatch()` at line 432: option 4 runs all 12 jurisdiction types. |
| `docs/manifest.json` | Manifest driving the dashboard. 533 county sections (correct, 6-chart format). City sections exist but point to old `data/{slug}_city_summary.json` table format — not updated yet. |
| `docs/charts.js` | Manifest-driven renderer. Deep-link logic: `_populatePrecinctDropdown`, `_filterSections`, `_renderVisibleSections`, `_rebuildNav`. |
| `test_jurisdiction_collisions.py` | Collision detector. Run to quantify village collisions. |
| `CLAUDE.md` | Project rules. **Critical**: files >150 lines must be patched via Python patch scripts, not the Edit tool (Edit truncates silently at ~951 lines). |

---

## File editing rule (enforce this throughout)

From `CLAUDE.md`:

> Files >150 lines: Python patch script. No exceptions.

Template:
```python
from pathlib import Path
p = Path('path/to/file.py')
src = p.read_text(encoding='utf-8')
old = "exact unique block, < 10 lines"
new = "replacement"
assert src.count(old) == 1, f"Expected 1, found {src.count(old)}"
p.write_text(src.replace(old, new), encoding='utf-8')
```

After every patch: `python3 -c "import ast; ast.parse(open('path').read())"` for Python,
`node --check path` for JS.

---

## Environment

- OS: Windows 11
- Python venv: `C:\Users\motorbikematt\.venv\Scripts\activate`
- Key packages: polars, xlsxwriter, openpyxl, psutil, orjson
- Bash sandbox has system Python3 — no polars. Run scripts via PowerShell or pipeline menu.
- Git index.lock cleanup if needed: `Remove-Item "D:\vibe\election-data\.git\index.lock" -Force`
- GitHub Pages: `/docs` on `main`, builds in ~40s

---

## What NOT to do

- Do not run the full county pass (option 1 or 3) unless the user asks — it takes 40+ minutes.
- Do not commit township/village JSON to GitHub until the county-scoping problem is resolved.
- Do not use the Edit tool on any file longer than 150 lines.
- Do not load raw SWVF .txt files into memory — always use the Parquet cache.
