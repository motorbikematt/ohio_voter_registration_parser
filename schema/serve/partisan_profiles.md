# `serve/partisan_profiles.json` — filer ↔ voter cross-reference (Stage 7)

The convergence output of the officials pipeline. For every filer in the three
producer serve files, Stage 7 (`tools/admin/match_to_voters.py`) finds that person's
own voter-registration record in `enriched_voters.parquet` and attaches a
`partisan_profile`. The dashboard reads this to show each candidate's / officeholder's
own partisan history.

**Producer:** `tools/admin/match_to_voters.py` (Stage 7). Do not hand-edit —
regenerate. See [README.md](../README.md) and the `partisan_profile` shape in
[../enriched/enriched_voters.md](../enriched/enriched_voters.md).

## Structural inventory

Top level: `_meta` plus three entity-type sections, each a list of matched profiles:

```
_meta: { generated, county, county_number, source_files, match_summary, unmatched, notes }
incumbent:          [ { ...partisan_profile, name, section, key, office, role } ]
captain_candidate:  [ { ...partisan_profile, name, precinct_name, party_letter, status } ]
general_candidate:  [ { ...partisan_profile, name, section, key, office, party } ]
```

The `partisan_profile` fields themselves are documented once in
[../enriched/enriched_voters.md](../enriched/enriched_voters.md) — this file does not
duplicate them.

## Semantic annotations (load-bearing)

- **A filer with no `partisan_profile` entry was NOT matched, not "no data".** Misses
  are listed in `_meta.unmatched` by entity type — gaps are surfaced, not silently
  dropped (CLAUDE.md §5). District-level incumbents (congressional / state house) have
  no home-zip row in `electedofficials.csv`, so they are name-only matches and more
  likely to miss or mis-match; treat them with care.
- **`captain_candidate` matches are name + `PRECINCT_NAME` only.** No captain address
  exists anywhere in the source (the DEM report carries no address, the LIB address is
  discarded, the R CSV `H*` fields are blank), so the precinct key is the only location
  constraint. These are inherently lower-confidence than zip-disambiguated matches.
  Write-in captain filers are intentionally skipped (not locatable registrants).
- **`match_method` records how the match was made.** `exact_prefix+zip` /
  `exact_prefix+precinct` are the strongest (location-confirmed); `exact_prefix` is a
  unique name with no location tiebreaker; `fuzzy` is a rapidfuzz near-match
  (`token_sort_ratio ≥ 80`) and should be spot-checked before being treated as truth.
- **`PARTY_AFFILIATION == ""` is lapsed, not unknown** (CLAUDE.md §4). The
  `partisan_profile_label` already encodes this (`Lapsed D` / `Lapsed R`).
- **Three party facts never collapse (Q1).** `nonpartisan_office` (is the seat
  nonpartisan), `filing_party` (what the person ran as -- may be Independent or a
  different party than their voting history), and the voter-derived
  `partisan_profile_label` are independent fields. `filing_party: "I"` +
  `partisan_profile_label: "Pure D"` is a valid, expected combination.
- **Precinct captains ARE elected officials (Q2).** They appear here as
  `captain_candidate` only because their data currently comes from filing PDFs, not
  the canonical `electedofficials.csv`. A *sitting* captain like Nick Brusky is a
  `DISTTYPE == PRECINCT` row in that CSV (an officeholder) -- distinct from a 2026
  *filer* running for the seat. When the complete CSV lands, PRECINCT officeholders
  should be ingested as officials like any other; the current separation is a
  sourcing workaround, not a claim that captains are not officials.
- **Single county today.** County 57 (Montgomery) only. A multi-county Stage 7 must
  disambiguate on the composite `(COUNTY_NUMBER, name)` — name collisions across
  counties are real (CLAUDE.md §4) and this file does not yet guard against them.

<!-- BEGIN GENERATED INVENTORY -- dump_schema.py; do not edit by hand -->

Structure of `serve/partisan_profiles.json`:

```
- _meta: {object}
    - county: str
    - county_number: str
    - generated: str
    - match_summary: {map of dynamic keys}
        - <key>: {object}
            - by_confidence: {object}
                - high: int
                - low: int
                - medium: int
            - matched: int
            - needs_review: int
            - unmatched: int
    - needs_review_total: int
    - notes: [list]
        - <item>: str
    - source_files: {object}
        - candidates: str
        - confirmations: str
        - officials: str
        - precinct_captains: str
        - voters: str
    - unmatched: {object}
        - captain_candidate: [empty list]
        - general_candidate: [list]
            - <item>: str
        - incumbent: [list]
            - <item>: str
    - verification_summary: {object}
        - confirmed: int
        - corrected: int
        - rejected: int
        - unverified: int
- captain_candidate: [list]
    - <item>: {object}
        - PARTY_AFFILIATION: str
        - binding_hash: str
        - cohort: str
        - cohort_family: str
        - crossover_class: null
        - d_primaries: int
        - entity_type: str
        - filing_party: str
        - jurisdiction_consistent: null
        - last_three_party: str
        - lean_confidence: float
        - lean_score: float
        - location_check: str
        - match_confidence: str
        - match_key: str
        - match_method: str
        - match_score: int
        - name: str
        - needs_review: bool
        - nonpartisan_office: bool
        - partisan_profile_label: str
        - party_letter: str
        - precinct_name: str
        - r_primaries: int
        - recent_5yr_lean: null
        - registration_date: str
        - residential_zip: str
        - sos_voterid: str
        - status: str
        - switch_count: int
        - total_primaries: int
        - verification: {object}
            - basis: null
            - state: str
            - status: str
            - verified_by: null
            - verified_date: null
        - voter_status: str
        - x_primaries: int
        - years_since_last_partisan: float
- general_candidate: [list]
    - <item>: {object}
        - PARTY_AFFILIATION: str
        - binding_hash: str
        - cohort: str
        - cohort_family: str
        - crossover_class: null|str
        - d_primaries: int
        - entity_type: str
        - filing_party: null|str
        - jurisdiction_consistent: bool|null
        - key: str
        - last_three_party: str
        - lean_confidence: float|null
        - lean_score: float|null
        - location_check: str
        - match_confidence: str
        - match_key: str
        - match_method: str
        - match_score: int
        - name: str
        - needs_review: bool
        - nonpartisan_office: bool
        - office: str
        - partisan_profile_label: str
        - r_primaries: int
        - recent_5yr_lean: float|null
        - registration_date: str
        - residential_zip: str
        - section: str
        - sos_voterid: str
        - switch_count: int
        - total_primaries: int
        - verification: {object}
            - basis: null
            - state: str
            - status: str
            - verified_by: null
            - verified_date: null
        - voter_status: str
        - x_primaries: int
        - years_since_last_partisan: float|null
- incumbent: [list]
    - <item>: {object}
        - PARTY_AFFILIATION: str
        - binding_hash: str
        - cohort: str
        - cohort_family: str
        - crossover_class: null|str
        - d_primaries: int
        - entity_type: str
        - filing_party: null|str
        - jurisdiction_consistent: bool|null
        - key: str
        - last_three_party: str
        - lean_confidence: float|null
        - lean_score: float|null
        - location_check: str
        - match_confidence: str
        - match_key: str
        - match_method: str
        - match_score: int
        - name: str
        - needs_review: bool
        - nonpartisan_office: bool
        - office: str
        - partisan_profile_label: str
        - r_primaries: int
        - recent_5yr_lean: float|null
        - registration_date: str
        - residential_zip: str
        - role: str
        - section: str
        - sos_voterid: str
        - switch_count: int
        - total_primaries: int
        - verification: {object}
            - basis: null
            - state: str
            - status: str
            - verified_by: null
            - verified_date: null
        - voter_status: str
        - x_primaries: int
        - years_since_last_partisan: float|null
```

<!-- END GENERATED INVENTORY -->
