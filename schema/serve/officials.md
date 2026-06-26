# `serve/officials.json` — current officeholders

Sitting officeholders and their 2026 challengers for Montgomery County, grouped
by office-type section. Read by the dashboard alongside
[candidates.json](candidates.md) (who is running) to show current vs. prospective
holders of each office.

**Producers:** district sections are hand-curated from the BoE petition report;
jurisdiction sections (`WARD`, `TOWNSHIP`, `VILLAGE`, `LOCAL_SCHOOL_DISTRICT`,
`CITY_SCHOOL_DISTRICT`) are populated by
`tools/admin/ingest_elected_officials.py` from `local/source/electedofficials.csv`
(the SOS elected-officials CSV). See [README.md](../README.md).

## Structural inventory

Top level: `_meta` plus office-type sections (ALL_CAPS, mirroring parquet
jurisdiction columns).

**District sections** — `CONGRESSIONAL_DISTRICT`, `STATE_SENATE_DISTRICT`,
`STATE_REPRESENTATIVE_DISTRICT` — keyed by zero-padded district id:

```
<id>: { office, incumbent: {name, party} | null, challengers: [{name, party}], note? }
```

**`WARD`** — keyed by exact parquet WARD value or a city-wide pseudo-key
(`{CITY} AT LARGE`, `{CITY} MAYOR`):

```
<ward key>: { office, seat, parquet_match: bool, incumbents: [...], challengers: [...] }
```
`parquet_match` is true only for ward-specific keys that exist as real parquet
WARD values (at-large / mayor pseudo-keys are false).

**`TOWNSHIP`** — keyed by exact parquet TOWNSHIP value:

```
<township>: { office: "Township Trustee", term_exp, incumbents: [...], challengers: [...] }
```

**`VILLAGE`** — keyed by exact parquet VILLAGE value (a village holds several
distinct offices: mayor, council seats):

```
<village>: { offices: [ {office, term_exp, incumbent: {...}} ], challengers: [...] }
```

**`LOCAL_SCHOOL_DISTRICT` / `CITY_SCHOOL_DISTRICT`** — keyed by exact parquet
value:

```
<district>: { office: "Board of Education Member", incumbents: [...], challengers: [...] }
```

**`_deferred`** — `COUNTY_COMMISSIONER`, `COUNTY_AUDITOR`, parked post-beta.

Person object (`incumbent` / `incumbents[]` / `challengers[]`):

| key | type | notes |
|-----|------|-------|
| `name` | str | full name |
| `party` | str \| null | `R`/`D`/`L`/`I`, or null for nonpartisan offices |
| `nonpartisan` | bool | present and true only when `party` is null |
| `term_exp` | str | term-expiration date (jurisdiction sections), `MM/DD/YYYY` |

## Semantic annotations (load-bearing)

- **`party: null` + `nonpartisan: true` is a charter fact.** An empty `PARTY`
  cell in the SOS CSV means the office is nonpartisan by charter (school board,
  municipal court, most township/village seats) — not "party unknown". Treat it
  as a known nonpartisan office.
- **Keys are exact parquet jurisdiction values, never slugs** (CLAUDE.md section
  4). `LOCAL_SCHOOL_DISTRICT` and `CITY_SCHOOL_DISTRICT` are **separate**
  mutually-exclusive parquet columns; a voter is in at most one. Routing a CSD
  board into LOCAL_SCHOOL_DISTRICT would make the frontend join miss it (the §3a
  bug this split fixed).
- **`RESIDENTIAL_CITY` / postal city is never a jurisdiction key here** — the
  ward/township/village keys are authoritative jurisdiction fields.
- **Greene-county districts are intentionally excluded.** `BEAVERCREEK LSD` and
  `FAIRBORN CSD` rows in the CSV are Greene County (29), not Montgomery (57), and
  are dropped by the ingester (restore with county gating for multi-county).
- **Known inconsistency (pending):** district-section names are Title Case
  (hand-curated), while jurisdiction-section names are raw ALL-CAPS as the SOS CSV
  emits them. Normalizing the latter through
  `tools/admin/officials_common.normalize_name` is a pending cleanup; values are
  load-bearing display strings, not schema, so this does not affect joins.

## Generated structural inventory

<!-- BEGIN GENERATED INVENTORY -- dump_schema.py; do not edit by hand -->

Structure of `serve/officials.json`:

```
- CITY_SCHOOL_DISTRICT: {map of dynamic keys}
    - <key>: {object}
        - challengers: [empty list]
        - incumbents: [list]
            - <item>: {object}
                - name: str
                - nonpartisan: bool
                - party: null
                - term_exp: str
        - office: str
- CONGRESSIONAL_DISTRICT: {object}
    - 10: {object}
        - challengers: [list]
            - <item>: {object}
                - name: str
                - party: str
        - incumbent: {object}
            - legal_name: str
            - name: str
            - party: str
        - incumbent_of_this_race: {object}
            - name: str
            - party: str
        - incumbent_source: str
        - office: str
        - reconciled: bool
- LOCAL_SCHOOL_DISTRICT: {map of dynamic keys}
    - <key>: {object}
        - challengers: [empty list]
        - incumbents: [list]
            - <item>: {object}
                - name: str
                - nonpartisan: bool
                - party: null
                - term_exp: str
        - office: str
- STATE_REPRESENTATIVE_DISTRICT: {map of dynamic keys}
    - <key>: {object}
        - challengers: [list]
            - <item>: {object}
                - name: str
                - party: str
        - incumbent: {object}
            - legal_name?: str
            - name: str
            - party: str
        - incumbent_of_this_race: null|object|object
        - incumbent_source: str
        - office: str
        - reconciled: bool
- STATE_SENATE_DISTRICT: {map of dynamic keys}
    - <key>: {object}
        - challengers: [list]
            - <item>: {object}
                - currently_holds?: {object}
                    - key: str
                    - office: str
                    - section: str
                - name: str
                - party: str
        - incumbent: {object}
            - name: str
            - party: str
        - incumbent_of_this_race: null
        - incumbent_source: str
        - office: str
        - reconciled: bool
- TOWNSHIP: {map of dynamic keys}
    - <key>: {object}
        - challengers: [empty list]
        - incumbents: [list]
            - <item>: {object}
                - name: str
                - nonpartisan?: bool
                - party: null|str
        - office: str
        - term_exp: str
- VILLAGE: {map of dynamic keys}
    - <key>: {object}
        - challengers: [empty list]
        - offices: [list]
            - <item>: {object}
                - incumbent: {object}
                    - name: str
                    - nonpartisan: bool
                    - party: null
                - office: str
                - term_exp: str
- WARD: {map of dynamic keys}
    - <key>: {object}
        - challengers: [empty list]
        - incumbents: [list]
            - <item>: {object}
                - name: str
                - nonpartisan?: bool
                - party: null|str
        - office: str
        - parquet_match: bool
        - seat: str
- _deferred: {map of dynamic keys}
    - <key>: {object}
        - challengers: [list]
            - <item>: {object}
                - name: str
                - party: str
        - incumbent: {object}
            - name: str
            - party: str
        - note: str
        - office: str
- _meta: {object}
    - county: str
    - county_number: int
    - generated: str
    - notes: [list]
        - <item>: str
    - sources: [list]
        - <item>: str
    - valid_through: str
```

<!-- END GENERATED INVENTORY -->
