---
name: Dashboard live state and routing conventions
description: GitHub Pages SPA URL, deep-link query format, jurisdictions tab routing, and the JSON regeneration TODO
type: project
originSessionId: c95e6f9c-7797-4aab-a040-ee856f0bf138
---
Live dashboard: https://motorbikematt.github.io/ohio_voter_registration_parser/ — GitHub Pages SPA in `/docs`, manifest-driven, Chart.js. Build via GitHub Actions, ~40s.

**Deep-link query format.** `?county=Montgomery&geo=precinct-detail&precinct=DAYTON+8-B#decade-distribution` selects a precinct view and scrolls to a chart anchor. Jurisdictions tab routes via `?geo=jurisdiction&jurType=X&jurCounty=Y&jurName=Z`; the county component is only present for `county_scoped` jurisdiction types.

**Current UI state (post Pass C, 2026-05-13).** Scope tabs: County / Precinct / Jurisdictions (with Cities aliased to Jurisdictions > Cities). Sub-filters: dead buttons (City Precincts, Congress) removed; "County" sub-filter renamed to "Analysis." Main county-select hidden in Jurisdictions scope. Cities dropdown carries a separate `<optgroup>` for 19 SWVF-blank counties (see `project_data_gaps.md`); selecting one shows an amber unavailability panel with voter count and source explanation.

**Outstanding regeneration TODO.** Townships, villages, and municipal_court_districts dirs under `docs/data/` need re-running after deleting the old phantom-merged directories — `python jurisdictional_groupings.py --jurisdictions townships,villages,municipal_court_districts` — because the county-scoped slug format changed in Pass A (2026-05-10). Check `docs/data/township/`, `docs/data/village/`, and `docs/data/municipal_court_district/` for stale single-county-named slugs before doing aggregation work on those types.

**Why:** Routing conventions and the regeneration TODO are not derivable from `git log` or the manifest alone; the slug-format break is silent.
**How to apply:** When asked to deep-link a view or add a new jurisdiction type, follow the existing query-param schema. Before claiming a jurisdiction type's JSON is current, check the directory's mtime against `jurisdictional_groupings.py`.
