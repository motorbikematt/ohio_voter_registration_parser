---
name: Phase status and roadmap
description: Current pipeline phase plus the P1-P5 intent ladder; what is built vs. planned
type: project
originSessionId: c95e6f9c-7797-4aab-a040-ee856f0bf138
---
Phase 1 (Atomic Ingestion) is complete as of late April 2026. Parquet cache lives under `source/parquet/` with 88 county partitions and ~7.9M voter rows × 135 cols. Row count drifts on each SWVF refresh; verify via `duckdb -c "select count(*) from 'source/parquet/*/*.parquet'"` before quoting a number.

Phase ladder (decisions, not just plans):
- P1 — Atomic Ingestion ✓ — parse SWVF to precinct.
- P2 — Roll-Up — aggregate into wards, cities, school districts, legislative districts, counties.
- P3 — Diffs + GIS — demographic/registration deltas; choropleth drill-down; precinct→municipality joins from Ohio SOS canvass to resolve the CITY data gap.
- P4 — Dark Data — property + census + USPS NCOA → unregistered-resident matrix for GOTV.
- P5 — Temporal/Anomaly — shift detection, momentum, turnout variance; SaaS subscriber alerts.

**Why:** Roadmap is intent the code does not encode. Without it Claude treats the prototype as the goal.
**How to apply:** Anchor architectural suggestions to the next phase the user is actually working in (currently late P2 / early P3), not P4-P5 abstractions. Don't speak as though P3+ infrastructure exists.
