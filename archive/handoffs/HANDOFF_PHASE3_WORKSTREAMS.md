# Phase 3 Workstreams — Narrative Enrichment & Officeholder Data

**Status:** Not started. Phase 2 (per-level templated narratives + pipeline integration) is complete.
**Prerequisite:** Phase 2 merged and statewide `--templated` run completed (~12k narrative JSONs on disk).

---

## What Phase 2 left in place

Every jurisdiction at every level now has a `{slug}_narrative.json` with:

```json
{
  "geography":         "county",
  "level":             "county",
  "jurisdiction_name": "Hamilton",
  "updated":           "2026-05-09",
  "generated_by":      "templated-v1",
  "template_version":  "v2",
  "config_version":    "v1",
  "metrics_hash":      "d3fdcd54da43a662",
  "narrative":         "Hamilton County has 602,004 registered voters..."
}
```

The prose is correct but thin — it surfaces party lean, generation mix, and decade trend, then renders placeholder lines for every elected office:

```
U.S. Senator: data not yet available.
State Senator: data not yet available.
County Commissioner: data not yet available.
```

Phase 3 replaces those placeholders with real names and, optionally, replaces the entire prose paragraph with a richer LLM-authored narrative.

---

## Workstream 2 — Officeholder Sourcing Pipeline

### Goal

Populate a `jurisdictional_offices.json` sidecar (or per-jurisdiction file) that maps every jurisdiction slug to its current officeholders by office key. The template registry reads this at narrative-generation time and substitutes real names for the placeholder lines.

### Office keys defined in `templates.py`

| Office key | Display label | Levels that use it |
|---|---|---|
| `us_senator` | U.S. Senator | county |
| `us_representative` | U.S. Representative | county, congressional_district |
| `state_senator` | State Senator | county, state_senate_district |
| `state_representative` | State Representative | county, state_representative_district |
| `county_commissioner` | County Commissioner | county |
| `sheriff` | Sheriff | county |
| `prosecutor` | Prosecutor | county |
| `mayor` | Mayor | city, village |
| `city_council` | City Council | city |
| `city_attorney` | City Attorney | city |
| `village_council` | Village Council | village |
| `trustee` | Township Trustee | township |
| `fiscal_officer` | Fiscal Officer | township |
| `school_board_member` | School Board | local_school_district, city_school_district, exempted_village_school_district |
| `municipal_court_judge` | Municipal Court Judge | municipal_court_district |
| `county_court_judge` | County Court Judge | county_court_district |
| `appeals_court_judge` | Court of Appeals Judge | court_of_appeals_district |
| `precinct_captain_r` | Republican Precinct Captain | precinct |
| `precinct_captain_d` | Democratic Precinct Captain | precinct |

### Recommended source ladder

**Federal (US Senators and Representatives)**
- [Bioguide](https://bioguide.congress.gov/) — canonical member IDs, terms, party
- [ProPublica Congress API](https://projects.propublica.org/api-docs/congress-api/) — current members by state/district; free API key
- Ohio has 2 senators (statewide) and 16 congressional districts

**State legislators**
- [OpenStates API](https://docs.openstates.org/api-v3/) — current Ohio Senate (33 seats) and House (99 seats) members by district; free tier
- Maps cleanly to `state_senate_district` and `state_representative_district` slugs (zero-padded `01`–`33` / `01`–`99`)

**County-level offices (commissioner, sheriff, prosecutor)**
- Ohio Secretary of State [elected officials lookup](https://www.ohiosos.gov/elected-officials/) — HTML scrape or downloadable roster
- 88 counties × 3 offices = 264 records; relatively stable (4-year terms)

**Municipal (mayor, council, city attorney)**
- Ohio SoS [municipal officers](https://www.ohiosos.gov/elections/voters/toolkit/municipal-officials/) — annual filing; HTML scrape
- Scope: ~250 cities and ~700 villages is large; prioritize cities with `total_voters > 10,000` first

**Township trustees and fiscal officers**
- Ohio SoS township officer filings — same annual source
- ~1,300 townships; trustee boards have 3 members each; may warrant abbreviated display ("3 trustees on file")

**School board members**
- Ohio Department of Education [district contacts](https://education.ohio.gov/) — per-district board roster
- ~600 districts total; board terms are 4 years, staggered

**Judicial (municipal, county, appeals court judges)**
- Ohio Supreme Court [attorney/judge directory](https://www.supremecourt.ohio.gov/) — active bench roster per court
- Municipal courts: ~120; county courts: ~88; appeals districts: 12

**Precinct captains**
- County Board of Elections annual party precinct organization filings
- Not statewide-available in machine-readable form; may require per-county FOIA or party contact
- Lowest priority — render placeholder if unavailable

### Target schema for `tools/data/jurisdictional_offices.json`

```json
{
  "version": "2026-05",
  "source_urls": { "federal": "propublica", "state": "openstates", ... },
  "offices": {
    "hamilton": {
      "us_senator":         ["Sherrod Brown", "JD Vance"],
      "us_representative":  "Brad Wenstrup",
      "state_senator":      "Louis Blessing III",
      "state_representative": "Adam Bird",
      "county_commissioner": ["Alicia Reece", "Denise Driehaus", "Stephanie Summerow Dumas"],
      "sheriff":            "Charmaine McGuffey",
      "prosecutor":         "Melissa Powers"
    },
    "01": {
      "us_representative": "Brad Wenstrup"
    },
    "state_senate_district/09": {
      "state_senator": "Louis Blessing III"
    }
  }
}
```

Keys are jurisdiction slugs matching the filesystem convention. District-level keys use `{level}/{slug}` to avoid collisions. Values are strings (single officeholder) or arrays (multi-member bodies — commissioners, council, board).

### Integration point in `templates.py`

`build_narrative(metrics, officeholders=None)` already accepts `officeholders` as a dict keyed by office key. When non-`None`, it substitutes the name instead of the placeholder string. The sourcing pipeline passes the relevant slice per jurisdiction:

```python
# In generate_narratives.py _process_one():
offices_slice = _load_offices_for(level, slug)   # new helper
narrative = build_narrative(metrics, officeholders=offices_slice)
```

No changes needed to `templates.py` or the output JSON schema — `officeholders` is already wired in the cache-hash computation, so swapping in real names auto-invalidates the cache for that jurisdiction.

### Suggested build order

1. Federal (2 senators + 16 reps) — highest visibility, simplest sourcing, done in an afternoon
2. State legislators (33 senate + 99 house) — OpenStates API, scriptable in one pass
3. County offices (sheriff, prosecutor, commissioner) — 88 × 3 records, SoS scrape
4. Judicial — Ohio Supreme Court roster
5. Municipal — city/village mayors and councils
6. Township and school board — largest volume, lowest individual reach
7. Precinct captains — FOIA or skip pending data access

---

## Workstream 3 — LLM Narrative Enrichment

### Goal

For jurisdictions where richer prose is warranted (large counties, high-traffic dashboard pages), replace the deterministic template paragraph with a Claude-authored narrative that synthesizes the statistical picture into a more readable, contextually aware summary.

### Design

The `generate_narratives.py` CLI already has a slot for this — `--templated` is a required flag precisely to leave room for an implicit LLM path once the API key handling is wired. The LLM path should:

1. Accept a `--model` flag (default `claude-haiku-4-5-20251001` for cost; `claude-sonnet-4-6` for quality)
2. Build the same `metrics` dict from the registry
3. Construct a prompt from `metrics` + `officeholders` (from Workstream 2)
4. Call the Anthropic API with retry/backoff (max 3 attempts, exponential backoff, raise on exhaustion — per `feedback_pipeline_safety.md`)
5. Write output JSON with `generated_by: claude-haiku-4-5-20251001` (or whatever model string)

The cache-skip mechanism handles coexistence automatically: a jurisdiction with `generated_by: claude-haiku-4-5-20251001` will be skipped by a `--templated` run unless `--overwrite` is passed. A `--model` run will overwrite template narratives but not re-call the API if the metrics hash is unchanged.

### Rate limiting

At ~12k jurisdictions, batch API generation is feasible but needs throttling. Suggested approach:
- `--level county` first (88 calls) to validate prose quality
- Approve prose quality before running `--all-levels`
- Use a per-minute semaphore (Haiku tier is 4,000 RPM / 400k TPM on Tier 1; a narrative prompt is ~500 tokens in, ~200 out → well within limits for a serial statewide run)

### Prompt template (draft)

```
You are writing a concise, factual overview paragraph for a voter registration dashboard.
The jurisdiction is {noun} {name}{parent_clause}.
Registration data as of {data_as_of}.

Key statistics:
- Total registered voters: {total_voters:,}
- Republican-leaning: {r_lean_pct}% | Democratic-leaning: {d_lean_pct}% | Unaffiliated: {unc_pct}%
{generation_clause}
{decade_clause}
{geography_clause}

Current officeholders:
{officeholder_lines}

Write one paragraph (3–5 sentences) that synthesizes the partisan composition and notable
characteristics of this jurisdiction. Do not editorialize or predict electoral outcomes.
Use plain American English. Do not use the word "significant" or "notable."
```

The officeholder lines come from Workstream 2. Without them, the prompt omits that section and the model focuses on the statistical picture.

### Output JSON — no schema changes needed

`generated_by` becomes the model string; all other fields are identical to the templated schema. The dashboard's `renderNarrative()` already displays whatever is in `narrative` — no frontend changes for Phase 3.

---

## Workstream 4 — District Geography Map (Minor)

### Problem

Congressional districts, state senate/house districts, and court of appeals districts have `lead_with_geography: True` in `LEVEL_CONFIGS`, meaning the narrative should open with the counties the district spans ("District 01 covers Hamilton and Clermont counties…"). Currently `geography_counties=None` is passed to `build_metrics_for_level()`, so that opening sentence is suppressed.

### Fix

Build a precomputed sidecar `tools/data/district_county_map.json`:

```json
{
  "congressional_district": {
    "01": ["Hamilton", "Clermont", "Warren"],
    "02": ["Adams", "Brown", ...]
  },
  "state_senate_district": { ... },
  "state_representative_district": { ... },
  "court_of_appeals_district": { ... }
}
```

Source: Ohio SoS precinct-to-district assignment file (available in the canvass data), or a spatial join of census TIGER shapefiles against county boundaries. Either approach is a one-shot script; the output is a ~50KB JSON file that never changes between redistricting cycles.

Integration is a one-line change in `generate_narratives.py _process_one()`:

```python
geography_counties = _district_county_map.get(level, {}).get(slug)
metrics = build_metrics_for_level(..., geography_counties=geography_counties)
```

No changes to `templates.py` needed — the geography sentence is already templated, just gated on `geography_counties` being non-`None`.

---

## Recommended sequencing

| Order | Workstream | Estimated effort | Unlock |
|---|---|---|---|
| 1 | **WS2: Federal + state legislators** | 1–2 hours | County, district, senate, house narratives get real names |
| 2 | **WS4: District geography map** | 2–3 hours | District narratives open with county geography |
| 3 | **WS2: County offices** | 2–3 hours | County narratives complete |
| 4 | **WS3: LLM enrichment (county only)** | 1–2 hours | Validate prose quality on 88 counties before scaling |
| 5 | **WS2: Municipal + township + school** | 4–6 hours | Full roster coverage |
| 6 | **WS3: LLM enrichment (all levels)** | 1 hour (scripted) | ~12k richer narratives |
| 7 | **WS2: Precinct captains** | TBD (data access) | Precinct narrative completeness |

---

## Files to create or modify

| File | Change |
|---|---|
| `tools/sources/federal_offices.py` | New — scrapes ProPublica Congress API for OH senators + reps |
| `tools/sources/state_offices.py` | New — calls OpenStates API for OH senate + house |
| `tools/sources/county_offices.py` | New — scrapes OH SoS elected officials page |
| `tools/sources/municipal_offices.py` | New — scrapes OH SoS municipal officer filings |
| `tools/sources/judicial_offices.py` | New — scrapes OH Supreme Court bench roster |
| `tools/sources/build_offices.py` | New — orchestrator: runs all sources, merges into `jurisdictional_offices.json` |
| `tools/data/jurisdictional_offices.json` | New output — slug-keyed officeholder roster |
| `tools/data/district_county_map.json` | New output — district → county membership (WS4) |
| `tools/generate_narratives.py` | Minor: add `_load_offices_for()` helper + `--model` CLI flag |
| `tools/narrative/templates.py` | No changes expected — officeholder slots already implemented |
| `ohio_voter_pipeline.py` | Minor: pass `--overwrite` to narrative phase when offices rebuilt |

---

## What is explicitly out of scope for Phase 3

- Ballot history per officeholder (voting record, committee assignments)
- Campaign finance data
- Precinct captain contact information (PII)
- Real-time election night results
- Any change to the SWVF ingestion pipeline (`voter_data_cleaner_v2.py`, `jurisdictional_groupings.py`)
