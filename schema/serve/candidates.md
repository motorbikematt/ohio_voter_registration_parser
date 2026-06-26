# `serve/candidates.json` — 2026 general-election candidate roster

Candidates on Montgomery County's November 2026 ballot, grouped by office type.
The dashboard reads this alongside [officials.json](officials.md) (current
officeholders) to show "who holds this office now" vs "who is running".

**Producer:** `tools/admin/build_candidates.py` (Stage 6) from the Stage-4
intermediate `local/working/candidate_filings_montgomery.json`, which
`tools/admin/parse_candidate_petitions.py` parses from the BoE Candidate Petition
Report PDF. Do not hand-edit — regenerate. See [README.md](../README.md).

## Structural inventory

Top level: `_meta` plus office-type sections (ALL_CAPS, mirroring the
`enriched_voters.parquet` jurisdiction columns where one exists):

| section | mid-level key | source |
|---------|---------------|--------|
| `CONGRESSIONAL_DISTRICT` | district id (`10`) | parquet column |
| `STATE_SENATE_DISTRICT` | district id (`05`) | parquet column |
| `STATE_REPRESENTATIVE_DISTRICT` | district id (`36`, `37`, …) | parquet column |
| `COUNTY_COMMISSIONER` | `county` | county-wide |
| `COUNTY_AUDITOR` | `county` | county-wide |
| `STATEWIDE` | office slug (`governor-lt-governor`) | no parquet jurisdiction |
| `JUDICIAL` | office slug (`judge-of-the-court-of-common-pleas-term-begins-1-1-2027`) | no parquet jurisdiction |

Each mid-level value:

| key | type | notes |
|-----|------|-------|
| `office` | str | verbatim BoE office label (`State Representative- 36th District (1)`) |
| `candidates` | list | candidate objects |

Each candidate object (snake_case):

| key | type | notes |
|-----|------|-------|
| `name` | str | normalized display name (Title Case) |
| `party` | str \| null | `D`/`R`/`L`/`I`, or **null** for nonpartisan offices |
| `address` | obj \| null | `{ street, city, zip }`; null when no address printed |
| `petition_filed` | str \| null | ISO `YYYY-MM-DD` |
| `petition_certified` | str \| null | ISO `YYYY-MM-DD` |
| `nonpartisan` | bool | present and true only when `party` is null |

`_meta` keys: `generated`, `county`, `county_number`, `election_date`,
`valid_through`, `retrieved_date`, `source`, `source_file`, `total_candidates`,
`offices_per_section`, `notes`.

## Semantic annotations (load-bearing)

- **District section keys match officials.json and the parquet columns.** A
  `STATE_REPRESENTATIVE_DISTRICT` id here (`36`) is the same id used in
  `officials.json` and the parquet `STATE_REPRESENTATIVE_DISTRICT` column —
  join across the three on it. Ids are zero-padded to 2 digits (`05`, not `5`).
- **`STATEWIDE` and `JUDICIAL` have no parquet jurisdiction**, so they key by an
  office slug, not an id. The slug includes the term-begin date for judicial
  seats (`…term-begins-1-1-2027`) because multiple Common Pleas seats share a
  title and differ only by term — dropping it would collide them.
- **`party` is BoE party in single-letter form** (`DEM`→`D`, `REP`→`R`,
  `LIB`→`L`, `IND`→`I`). **Null = nonpartisan office** (most judicial seats),
  flagged with `nonpartisan: true` — null is a charter fact, not missing data,
  exactly as in `officials.json`.
- **`address.zip` is load-bearing for Session-2 voter matching.** It is the
  candidate's *mailing* address from the petition, not a jurisdiction signal —
  do not derive jurisdiction from it (CLAUDE.md section 4, postal ≠ jurisdiction).
  `street: "On File"` with null `city`/`zip` means the BoE withheld the address.
- **This is a weekly snapshot.** `_meta.retrieved_date` records when the petition
  report was downloaded; BoE updates it weekly. Re-running the Stage-4 parser and
  this builder on a fresh PDF refreshes the roster. `valid_through` =
  `election_date` (2026-11-03).
- **Date fields are best-effort for address-less rows.** `petition_filed` /
  `petition_certified` are mapped by column position, reliable for full-address
  district/county/judicial rows; statewide rows (no address columns) may leave
  them null. `date_of_election` lives once in `_meta.election_date`.

## Generated structural inventory

<!-- BEGIN GENERATED INVENTORY -- dump_schema.py; do not edit by hand -->

Structure of `serve/candidates.json`:

```
- CONGRESSIONAL_DISTRICT: {object}
    - 10: {object}
        - candidates: [list]
            - <item>: {object}
                - address: {object}
                    - city: str
                    - street: str
                    - zip: str
                - incumbent_source?: str
                - is_incumbent: bool
                - name: str
                - party: str
                - petition_certified: str
                - petition_filed: str
        - office: str
- COUNTY_AUDITOR: {object}
    - county: {object}
        - candidates: [list]
            - <item>: {object}
                - address: {object}
                    - city: str
                    - street: str
                    - zip: str
                - incumbent_source?: str
                - is_incumbent: bool
                - name: str
                - party: str
                - petition_certified: str
                - petition_filed: str
        - office: str
- COUNTY_COMMISSIONER: {object}
    - county: {object}
        - candidates: [list]
            - <item>: {object}
                - address: {object}
                    - city: str
                    - street: str
                    - zip: str
                - incumbent_source?: str
                - is_incumbent: bool
                - name: str
                - party: str
                - petition_certified: str
                - petition_filed: str
        - office: str
- JUDICIAL: {map of dynamic keys}
    - <key>: {object}
        - candidates: [list]
            - <item>: {object}
                - address: {object}
                    - city: null|str
                    - street: str
                    - zip: null|str
                - incumbent_source?: str
                - is_incumbent: bool
                - name: str
                - nonpartisan?: bool
                - party: null|str
                - petition_certified: null|str
                - petition_filed: null|str
        - office: str
- STATEWIDE: {map of dynamic keys}
    - <key>: {object}
        - candidates: [list]
            - <item>: {object}
                - address: null
                - incumbent_source?: str
                - is_incumbent: bool
                - name: str
                - party: str
                - petition_certified: str
                - petition_filed: str
        - office: str
- STATE_REPRESENTATIVE_DISTRICT: {map of dynamic keys}
    - <key>: {object}
        - candidates: [list]
            - <item>: {object}
                - address: {object}
                    - city: str
                    - street: str
                    - zip: str
                - incumbent_source?: str
                - is_incumbent: bool
                - name: str
                - party: str
                - petition_certified: str
                - petition_filed: str
        - office: str
- STATE_SENATE_DISTRICT: {object}
    - 05: {object}
        - candidates: [list]
            - <item>: {object}
                - address: {object}
                    - city: str
                    - street: str
                    - zip: str
                - is_incumbent: bool
                - name: str
                - party: str
                - petition_certified: str
                - petition_filed: str
        - office: str
- _meta: {object}
    - county: str
    - county_number: int
    - election_date: str
    - generated: str
    - notes: [list]
        - <item>: str
    - offices_per_section: {object}
        - CONGRESSIONAL_DISTRICT: int
        - COUNTY_AUDITOR: int
        - COUNTY_COMMISSIONER: int
        - JUDICIAL: int
        - STATEWIDE: int
        - STATE_REPRESENTATIVE_DISTRICT: int
        - STATE_SENATE_DISTRICT: int
    - retrieved_date: str
    - source: str
    - source_file: str
    - total_candidates: int
    - valid_through: str
```

<!-- END GENERATED INVENTORY -->
