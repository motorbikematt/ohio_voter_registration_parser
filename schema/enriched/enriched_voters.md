# `enriched_voters.parquet` — derived scoring columns

The enriched voter layer at `local/source/parquet_enriched/enriched_voters.parquet`:
the SWVF static + dynamic election columns (verbatim, ALL_CAPS) plus the pipeline's
derived per-voter scoring columns (snake_case, CLAUDE.md §6). Stage 7
(`tools/admin/match_to_voters.py`) reads these to build each filer's
`partisan_profile`. This file documents the **scoring columns** and the
`partisan_profile` shape; the full column list is in the generated inventory below.

> Source columns (`SOS_VOTERID`, `PARTY_AFFILIATION`, `RESIDENTIAL_ZIP`, the SWVF
> election-history columns, …) are documented in `schema/source/` and not repeated
> here. This file covers only what the pipeline *derives*.

## Semantic annotations (load-bearing — CLAUDE.md §4)

- **`lean_score` sign: `D → +1`, `R → -1`, range `[-1.0, +1.0]`.** A positive score
  is Democratic-leaning. This sign convention is load-bearing; flipping it inverts
  every downstream label. (Confirmed from `tools/scoring/mixed_lean_predictor.py`.)
- **Lapse is NOT a year threshold — it is `PARTY_AFFILIATION == ""`.** The SOS already
  applied Ohio's 2-calendar-year supplemental-list window when it blanked
  `PARTY_AFFILIATION`. `years_since_last_partisan` is for **display only** and must
  **never** be the decision gate for a partisan label (the Stage 7
  `derive_profile_label` gates on `PARTY_AFFILIATION` + primary counts, not on years).
- **Blanks are empty strings, not null.** Verified 2026-06-25 for county 57:
  `PARTY_AFFILIATION` has 261,625 `""` values and **0 nulls**. Code that tests the
  lapse signal must compare `== ""` (and may fold a defensive `null → ""`), never
  rely on `pl.col(...).is_null()` — null-aware ops would skip every real blank.
- **`confidence` vs `lean_confidence`.** The parquet column is `confidence`. Stage 7
  renames it to `lean_confidence` in the `partisan_profile` output to disambiguate it
  from a match score. The underlying value is unchanged.
- **Cohort vs crossover_class.** `cohort` / `cohort_family` carry values like
  `PURE_D`, `CROSSOVER_D`, `CROSSOVER_R`; `crossover_class` separately holds
  `LEAN_*` / `LOCKED_*` D|R and `TRUE_MIXED`. `derive_profile_label` reads `cohort`
  (not `crossover_class`) for crossover *direction*.

### Scoring columns Stage 7 reads

| column | type | meaning |
|--------|------|---------|
| `lean_score` | float | partisan lean, `D → +1` / `R → -1`, `[-1,+1]` |
| `confidence` | float | model confidence in `lean_score` (→ `lean_confidence`) |
| `cohort` | str | e.g. `PURE_D`, `CROSSOVER_R` — crossover direction source |
| `cohort_family` | str | coarser cohort grouping |
| `crossover_class` | str \| null | `LEAN_*` / `LOCKED_*` / `TRUE_MIXED` |
| `d_primaries` | int | count of Democratic primary ballots pulled |
| `r_primaries` | int | count of Republican primary ballots pulled |
| `x_primaries` | int | count of non-partisan (`X`) primary ballots |
| `total_primaries` | int | total primaries voted |
| `partisan_primaries` | int | `d_primaries + r_primaries` |
| `recent_5yr_lean` | float | lean restricted to the last 5 years |
| `last_three_party` | str | last three primary ballots, e.g. `DDD`, `RXD` |
| `years_since_last_partisan` | float | **display only** — never gates the label |
| `switch_count` | int | times the voter switched primary party |

## `partisan_profile` shape (Stage 7 output)

Each matched filer in `serve/partisan_profiles.json` carries a `partisan_profile`
record. Source columns stay ALL_CAPS, derived columns snake_case, the label Title
Case (CLAUDE.md §6):

```
{
  "entity_type": "incumbent" | "captain_candidate" | "general_candidate",
  "match_method": "exact_prefix" | "exact_prefix+zip" | "exact_prefix+precinct" | "fuzzy",
  "match_score": int | null,            # 100 for exact, rapidfuzz score for fuzzy
  "sos_voterid": str,                   # statewide join key (SWVF source col)
  "voter_status": "ACTIVE" | "CONFIRMATION",
  "registration_date": str | null,      # first-registration proxy (§4)
  "residential_zip": str,
  "PARTY_AFFILIATION": "D" | "R" | "",  # "" = lapsed (§4); behavior-derived
  "lean_score": float,                  # D → +1, R → -1
  "lean_confidence": float,             # parquet `confidence`, renamed
  "cohort": str, "cohort_family": str, "crossover_class": str | null,
  "d_primaries": int, "r_primaries": int, "x_primaries": int, "total_primaries": int,
  "recent_5yr_lean": float, "last_three_party": str,
  "years_since_last_partisan": float,   # display only
  "switch_count": int,
  "partisan_profile_label": "Pure D" | "Lapsed D" | "Pure R" | "Lapsed R" |
                            "Crossover (D-leaning)" | "Crossover (R-leaning)" |
                            "Crossover (Mixed)" | "Non-Partisan Voter" |
                            "No Primary History",
  // identity keys (vary by entity_type) + the three party facts:
  //   name, office/section/key | precinct_name + party_letter,
  //   filing_party,       // party the person FILED under (may be "I"/another party)
  //   nonpartisan_office  // true when the SEAT itself is nonpartisan
}
```

`partisan_profile_label` is derived by `derive_profile_label` — gated on
`PARTY_AFFILIATION` + `d/r/x_primaries` (+ `cohort` for crossover direction),
**never** on `years_since_last_partisan`.

## Three party facts, kept separate (Ohio semantics)

Ohio voters do not register a party; affiliation is inferred only from which primary
ballot they pull (CLAUDE.md section 4). Three different "party" ideas coexist in a
matched record and must never be collapsed:

1. **Is the seat partisan?** -- `nonpartisan_office`. Nonpartisan offices (school board,
   most judicial/township/village) give no chance to file an affiliation, which is why
   the office `party` is blank. Blank is a charter fact, not missing data.
2. **What party did the person FILE under?** -- `filing_party`. For a partisan office a
   filer may run as an Independent or a different party than their primary history
   suggests; `filing_party` records what is printed on the ballot.
3. **What does their voting behavior say?** -- `PARTY_AFFILIATION`, `lean_score`, and
   `partisan_profile_label`, derived from their own primary ballots.

The mixed case is fully representable and intentional: `filing_party: "I"` with
`partisan_profile_label: "Pure D"` means "ran as an Independent, but has only ever
pulled Democratic primary ballots." The three live in separate fields from separate
sources; nothing overwrites anything. `filing_party` + `nonpartisan_office` are carried
uniformly on every entity type (`captain_candidate` also keeps `party_letter` = which
party's central committee the filing was for).

<!-- BEGIN GENERATED INVENTORY -- dump_schema.py; do not edit by hand -->

Columns of `local/source/parquet_enriched/enriched_voters.parquet` (155 total):

| column | dtype |
|--------|-------|
| `SOS_VOTERID` | String |
| `COUNTY_ID` | String |
| `LAST_NAME` | String |
| `FIRST_NAME` | String |
| `MIDDLE_NAME` | String |
| `SUFFIX` | String |
| `DATE_OF_BIRTH` | String |
| `REGISTRATION_DATE` | String |
| `VOTER_STATUS` | String |
| `PARTY_AFFILIATION` | String |
| `RESIDENTIAL_ADDRESS1` | String |
| `RESIDENTIAL_SECONDARY_ADDR` | String |
| `RESIDENTIAL_CITY` | String |
| `RESIDENTIAL_STATE` | String |
| `RESIDENTIAL_ZIP` | String |
| `RESIDENTIAL_ZIP_PLUS4` | String |
| `RESIDENTIAL_COUNTRY` | String |
| `RESIDENTIAL_POSTALCODE` | String |
| `MAILING_ADDRESS1` | String |
| `MAILING_SECONDARY_ADDRESS` | String |
| `MAILING_CITY` | String |
| `MAILING_STATE` | String |
| `MAILING_ZIP` | String |
| `MAILING_ZIP_PLUS4` | String |
| `MAILING_COUNTRY` | String |
| `MAILING_POSTAL_CODE` | String |
| `CAREER_CENTER` | String |
| `CITY` | String |
| `CITY_SCHOOL_DISTRICT` | String |
| `COUNTY_COURT_DISTRICT` | String |
| `CONGRESSIONAL_DISTRICT` | String |
| `COURT_OF_APPEALS` | String |
| `EDU_SERVICE_CENTER_DISTRICT` | String |
| `EXEMPTED_VILL_SCHOOL_DISTRICT` | String |
| `LIBRARY` | String |
| `LOCAL_SCHOOL_DISTRICT` | String |
| `MUNICIPAL_COURT_DISTRICT` | String |
| `PRECINCT_NAME` | String |
| `PRECINCT_CODE` | String |
| `STATE_BOARD_OF_EDUCATION` | String |
| `STATE_REPRESENTATIVE_DISTRICT` | String |
| `STATE_SENATE_DISTRICT` | String |
| `TOWNSHIP` | String |
| `VILLAGE` | String |
| `WARD` | String |
| `PRIMARY-03/07/2000` | String |
| `GENERAL-11/07/2000` | String |
| `SPECIAL-05/08/2001` | String |
| `GENERAL-11/06/2001` | String |
| `PRIMARY-05/07/2002` | String |
| `GENERAL-11/05/2002` | String |
| `SPECIAL-05/06/2003` | String |
| `GENERAL-11/04/2003` | String |
| `PRIMARY-03/02/2004` | String |
| `GENERAL-11/02/2004` | String |
| `SPECIAL-02/08/2005` | String |
| `PRIMARY-05/03/2005` | String |
| `PRIMARY-09/13/2005` | String |
| `GENERAL-11/08/2005` | String |
| `SPECIAL-02/07/2006` | String |
| `PRIMARY-05/02/2006` | String |
| `GENERAL-11/07/2006` | String |
| `PRIMARY-05/08/2007` | String |
| `PRIMARY-09/11/2007` | String |
| `GENERAL-11/06/2007` | String |
| `PRIMARY-11/06/2007` | String |
| `GENERAL-12/11/2007` | String |
| `PRIMARY-03/04/2008` | String |
| `PRIMARY-10/14/2008` | String |
| `GENERAL-11/04/2008` | String |
| `GENERAL-11/18/2008` | String |
| `PRIMARY-05/05/2009` | String |
| `PRIMARY-09/08/2009` | String |
| `PRIMARY-09/15/2009` | String |
| `PRIMARY-09/29/2009` | String |
| `GENERAL-11/03/2009` | String |
| `PRIMARY-05/04/2010` | String |
| `PRIMARY-07/13/2010` | String |
| `PRIMARY-09/07/2010` | String |
| `GENERAL-11/02/2010` | String |
| `PRIMARY-05/03/2011` | String |
| `PRIMARY-09/13/2011` | String |
| `GENERAL-11/08/2011` | String |
| `PRIMARY-03/06/2012` | String |
| `GENERAL-11/06/2012` | String |
| `PRIMARY-05/07/2013` | String |
| `PRIMARY-09/10/2013` | String |
| `PRIMARY-10/01/2013` | String |
| `GENERAL-11/05/2013` | String |
| `PRIMARY-05/06/2014` | String |
| `GENERAL-11/04/2014` | String |
| `PRIMARY-05/05/2015` | String |
| `PRIMARY-09/15/2015` | String |
| `GENERAL-11/03/2015` | String |
| `PRIMARY-03/15/2016` | String |
| `GENERAL-06/07/2016` | String |
| `PRIMARY-09/13/2016` | String |
| `GENERAL-11/08/2016` | String |
| `PRIMARY-05/02/2017` | String |
| `PRIMARY-09/12/2017` | String |
| `GENERAL-11/07/2017` | String |
| `PRIMARY-05/08/2018` | String |
| `GENERAL-08/07/2018` | String |
| `GENERAL-11/06/2018` | String |
| `PRIMARY-05/07/2019` | String |
| `PRIMARY-09/10/2019` | String |
| `GENERAL-11/05/2019` | String |
| `PRIMARY-03/17/2020` | String |
| `GENERAL-11/03/2020` | String |
| `PRIMARY-05/04/2021` | String |
| `PRIMARY-08/03/2021` | String |
| `PRIMARY-09/14/2021` | String |
| `GENERAL-11/02/2021` | String |
| `PRIMARY-05/03/2022` | String |
| `PRIMARY-08/02/2022` | String |
| `GENERAL-11/08/2022` | String |
| `SPECIAL-02/28/2023` | String |
| `PRIMARY-05/02/2023` | String |
| `SPECIAL-08/08/2023` | String |
| `SPECIAL-09/12/2023` | String |
| `PRIMARY-10/03/2023` | String |
| `GENERAL-11/07/2023` | String |
| `SPECIAL-12/05/2023` | String |
| `SPECIAL-02/27/2024` | String |
| `PRIMARY-03/19/2024` | String |
| `GENERAL-06/11/2024` | String |
| `GENERAL-11/05/2024` | String |
| `SPECIAL-01/07/2025` | String |
| `PRIMARY-05/06/2025` | String |
| `SPECIAL-08/05/2025` | String |
| `PRIMARY-09/09/2025` | String |
| `GENERAL-11/04/2025` | String |
| `SPECIAL-01/06/2026` | String |
| `SPECIAL-02/03/2026` | String |
| `COUNTY_NUMBER` | String |
| `BIRTHYEAR` | Int32 |
| `Decade` | Int32 |
| `Generation` | String |
| `REGDATE_DT` | Date |
| `PARTY_LABEL` | String |
| `d_primaries` | Int32 |
| `r_primaries` | Int32 |
| `x_primaries` | Int32 |
| `total_primaries` | Int32 |
| `partisan_primaries` | Int32 |
| `lean_score` | Float64 |
| `confidence` | Float64 |
| `recent_5yr_lean` | Float64 |
| `last_three_party` | String |
| `years_since_last_partisan` | Float64 |
| `switch_count` | Int32 |
| `cohort` | String |
| `cohort_family` | String |
| `crossover_class` | String |
| `is_new_registrant` | Boolean |

<!-- END GENERATED INVENTORY -->
