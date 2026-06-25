# `schema/` — Data Layer Reference

Authoritative, committed reference for every data layer this project emits. One place a contributor (human or agent, CLI or Cowork) can read the shape **and** the meaning of each column and JSON key. Tracked in git — never in `docs/` (public web root) or `local/` (gitignored), so it is shared and reviewable.

## Governing principle: code is the source of truth

A hand-maintained schema doc drifts from what the pipeline actually emits, and a drifted schema doc is the postal-city bug in documentation form (CLAUDE.md §5, single-resolver). So each schema file has two parts with different owners:

1. **Structural inventory — generated, never hand-typed.** Column names, dtypes, JSON key shapes. Produced by `tools/admin/dump_schema.py`, which introspects the live artifacts (`enriched_voters.parquet` schema, each `serve/*.json`). Regenerate; do not edit by hand.
2. **Semantic annotations — hand-written, human-ratified.** The load-bearing "why" that code cannot express: blank-string-not-null, `HZIPCODE`-not-`OZIPCODE`, the `lean_score` sign convention, the `Generation` values that silently return 0 rows if mislabeled. An LLM may *draft* stubs for new columns from their values + call sites, but a human ratifies — a confidently wrong annotation is worse than a blank one.

## Layout — one file per artifact, split by layer

```
schema/
  README.md                    <- this file
  source/                      <- provider-emitted, verbatim (ALL_CAPS / UPPER_SNAKE)
    swvf.md                    <- SWVF static + dynamic election cols; points to local/source/Voter_File_Layout.md
    electedofficials.md        <- SOS elected-officials CSV (O*/H* columns, DISTTYPE, etc.)
  enriched/                    <- derived parquet columns (snake_case)
    enriched_voters.md         <- scoring cols: lean_score, cohort, d_primaries, ...
  serve/                       <- serve-layer JSON shapes (section keys ALL_CAPS, sub-keys snake_case)
    officials.md
    precinct_captains.md
    candidates.md              <- (created by the officials pipeline build)
```

Naming tiers follow CLAUDE.md §6; this directory documents names, never values.

## Drift enforcement — loud, not aspirational

A schema doc is only as good as the rule that keeps it current. The validation gate (`tools/admin/validate_jurisdiction_fields.py` / officials-pipeline Stage 8) regenerates the structural inventory and **fails loudly** if it does not match the committed file (CLAUDE.md §5, loud failures over silent degradation). "Update the doc" becomes "the build breaks if you didn't." New columns appear in the diff with an empty annotation slot, prompting a human to fill the semantics.

## Relationship to the other knowledge stores

- **CLAUDE.md §4** holds only the *irreducible* semantics auto-loaded into every session; it **points here** for the full catalog and is not bloated with it (auto-load = standing token cost).
- **Memory** holds decisions and state ("why the 7-cohort taxonomy"); it **references** these files, never contains the catalog (memory is environment-specific and unshared).
- This directory is the single full catalog. No layer duplicates another's column definitions.

## Host note

`dump_schema.py` must run on **Windows / Claude Code CLI**. The Cowork sandbox mount serves byte-capped reads (~13400 B) and cannot reliably read the parquet or larger serve files (e.g. `precinct_captains.json`), so generation and drift-checks run there, not in Cowork (CLAUDE.md §9).
