# `serve/precinct_captains.json` — precinct central-committee captains

Per-precinct central-committee filings for Montgomery County, keyed by exact
`PRECINCT_NAME`, read by the captain UI (`docs/captain/`) and the roster API.

**Producer:** `tools/admin/build_precinct_captains.py` (Stage 5) from the three
Stage-3 intermediates `local/working/captain_filings_montgomery_{D,L,R}.json`.
Do not hand-edit — regenerate. See [README.md](../README.md) for the
generated-inventory / hand-written-annotation split.

## Structural inventory

Top level: `_meta` plus **one key per precinct** (381 for Montgomery), each an
exact `PRECINCT_NAME` value from `enriched_voters.parquet` (e.g. `BROOKVILLE-A`,
`BUTLER TWP A`, `DAYTON 3-E`). Keys are ordered by BoE ballot number.

```
<PRECINCT_NAME>:
  D: { status, candidates[] }      # Democratic central committee
  L: { status, candidates[] }      # Libertarian central committee
  R: { status, candidates[] }      # Republican central committee
```

Each party object:

| key | type | notes |
|-----|------|-------|
| `status` | str | `uncontested` \| `contested` \| `vacant` \| `data_pending` |
| `candidates` | list | candidate objects (empty for `vacant` / `data_pending`) |

Each candidate object:

| key | type | notes |
|-----|------|-------|
| `name` | str | normalized display name (Title Case), e.g. `Gregory A. Brush` |
| `party` | str \| null | `D`/`L`/`R`, or **null** when the BoE filing carried no party suffix |
| `write_in` | bool | true for write-in filers |

`_meta` keys: `generated`, `county`, `county_number`, `primary_date`,
`keyed_by`, `parties` (per-party provenance: `source`, `source_file`,
`retrieved_date`, `coverage`, `filings`, `gaps`, `status_counts`), `sources`,
`status_semantics`, `notes`.

## Semantic annotations (load-bearing)

- **Keys are exact `PRECINCT_NAME`, never slugs.** The producer validates every
  key against the distinct parquet `PRECINCT_NAME` set for county 57 (loud
  failure on mismatch). Join on the key directly; do not un-slug or normalize it.
- **`status` is computed from filing count + source coverage**, not stored in the
  source:
  - `uncontested` — exactly one filer (elected unopposed in the primary).
  - `contested` — two or more filers; the **certified** primary result is needed
    to pick the winner (Session 2). The list here is the *filer* list, frozen.
  - `vacant` — no one filed, **and** the source enumerates every precinct
    (`coverage: complete`). Applies to D (full report) and L (minor-party report).
  - `data_pending` — filings for this party are not yet loaded
    (`coverage: partial`). All R precincts except the one CSV incumbent are
    `data_pending`, **not** `vacant` — absence here means "unknown", not "empty".
    This distinction is the reason `coverage` is a first-class field upstream.
- **`party: null` is meaningful, not missing.** A central-committee filer with no
  `(D)`/`(L)`/`(R)` suffix in the BoE report is a crossfiler or unaffiliated
  registrant running in that party's primary. Null ≠ unknown party.
- **Source provenance differs by party.** D and L come from 2026 **primary
  central-committee filing reports** (pre-certification snapshots). R comes from
  the **elected-officials CSV** (current officeholder, `DISTTYPE == PRECINCT`
  rows) until the Republican central-committee PDF arrives. `_meta.parties[*]`
  records each source file and retrieval date.
- **`_meta.parties.D.gaps`** lists ballot numbers the DEM report skipped
  (`0650` DAYTON 4-B, `1430` ENGLEWOOD-I) — present in the precinct universe but
  absent from the report; treated as `vacant`. Provenance/QA only.
- **Names are normalized (Title Case), values not schema.** `name` is display-
  cased from the raw all-caps BoE text; the normalizer preserves initials
  (`E.`), joined initials (`S.H.`), and suffixes (`Jr`, `II`). The raw text is
  retained in the Stage-3 intermediate (`name_raw`), not here.

## Known pending data (freezes data, not schema — Session 2 may start)

- 47 contested DEM precinct races await the May-5-2026 certified results to pick
  winners; the filer lists are final, the winners are not.
- The Republican central-committee PDF has not been received; R precincts are
  `data_pending` stubs except `DAYTON 3-E` (Nick Brusky, from the CSV).
