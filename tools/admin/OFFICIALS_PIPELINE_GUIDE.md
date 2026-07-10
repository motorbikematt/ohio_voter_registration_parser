# Officials Pipeline — Plain-Language Run Guide

This guide explains the officials / captains / candidates pipeline in simple words,
shows what each script makes, and gives you the exact steps for a clean run. If you
follow the steps in order, you will end up with up-to-date files in `serve/` and a
green checkmark from the validator.

> **Read the box at the bottom first** ("Schema rules and known limits"). It lists the
> few places where the rules in `CLAUDE.md §4` could bite you. Nothing here breaks a
> rule, but two things need your eyes on the first run.

> **Note (2026-07):** `dump_schema.py` (Stage 8) was renamed to `validate_schema.py`
> to match the `validate_*` naming of the other gates. Same script, same flags —
> just a new filename. Commands below already reflect the new name.

---

## 1. What this pipeline does (the big picture)

Think of three lists being built at the same time, then joined together:

1. **Officials** — who holds each office right now.
2. **Captains** — who filed to run for precinct central committee.
3. **Candidates** — who filed to run in the November 2026 general election.

After those three lists are built, a fourth step looks up **each person in the voter
file** and writes down their voting history and party lean. A fifth step checks that
everything is well-formed.

```
Officials   (Stage 1)            ->  serve/officials.json
Captains    (Stages 2, 3, 5)     ->  serve/precinct_captains.json
Candidates  (Stages 4, 6)        ->  serve/candidates.json
Match       (Stage 7)            ->  serve/partisan_profiles.json   <-- this session built it
Validate    (Stage 8)            ->  pass/fail report (no file)     <-- this session built it
```

The three list-building chains are **independent** — you can run them in any order.
But Stage 7 (Match) must run **after** all three lists exist, because it reads them.

---

## 2. What each script makes

All scripts live in `tools/admin/` (except the wrapper, in `pipeline/`).

| Step | Script | What it makes |
|------|--------|---------------|
| 1 | `ingest_elected_officials.py --write` | fills the jurisdiction parts of `serve/officials.json` from the county CSV |
| 2 | `precinct_key_manager.py` | the precinct key list `local/source/precinct_keys/montgomery_precincts.csv` (one-time; already exists) |
| 3 | `parse_central_committee.py --county montgomery --all-parties` | `local/working/captain_filings_montgomery_{D,L,R}.json` |
| 4 | `pdf_to_markdown.py --all` then `parse_candidate_petitions.py --county montgomery` | `local/working/candidate_filings_montgomery.json` |
| 5 | `build_precinct_captains.py --county montgomery` | `serve/precinct_captains.json` |
| 6 | `build_candidates.py --county montgomery` | `serve/candidates.json` |
| **7** | **`match_to_voters.py --county montgomery`** | **`serve/partisan_profiles.json`** |
| **8** | **`validate_schema.py`** then **`validate_officials.py --county montgomery`** | refreshes `schema/` and prints a pass/fail report |

**Stage 7 output — `serve/partisan_profiles.json`.** For every filer it could match, it
records that person's `sos_voterid`, voting history counts, lean score, and a plain
label like `Pure D`, `Lapsed R`, or `Crossover (Mixed)`. People it could **not** match
are listed under `_meta.unmatched` so nothing is hidden.

**Stage 8 — the check.** It makes sure precinct keys are real, status words are valid,
the DEM "gaps" are truly empty precincts, every person has a name, every match has a
voter id, and the `schema/` docs still match the live files. If anything is off, it
prints `[FAIL]` lines and exits with an error so a build can stop.

---

## 3. Before you start (one-time setup)

You need these in place:

1. **The voter file** at `local/source/parquet_enriched/enriched_voters.parquet`.
   Stage 7 and Stage 8 read it. (It is large and lives only on your machine.)
2. **The two Python helpers** `duckdb` and `rapidfuzz`. Install them with:
   ```
   uv add rapidfuzz duckdb
   ```
   (Stage 7 uses `rapidfuzz` for near-miss name matching.)
3. **Run from the project root** `D:\vibe\election-data`. Every script finds its own
   files, so you do not need to `cd` anywhere special, but run them from there.

---

## 4. The clean-run steps (do these in order)

You can run everything with one command, or step by step. Both are below.

### Option A — one command (easiest)

```
python pipeline/officials_pipeline_wrapper.py --stage all --county montgomery
```

This runs Stages 1 through 8 in the right order. It will skip Stage 2 because the
precinct key file already exists. If a stage fails, it stops and tells you which one.

### Option B — step by step (more control)

Run these one at a time. Check the output of each before moving on.

```
python tools/admin/ingest_elected_officials.py --write
python tools/admin/parse_central_committee.py --county montgomery --all-parties
python tools/admin/build_precinct_captains.py --county montgomery
python tools/admin/pdf_to_markdown.py --all
python tools/admin/parse_candidate_petitions.py --county montgomery
python tools/admin/build_candidates.py --county montgomery
python tools/admin/match_to_voters.py --county montgomery --verbose
python tools/admin/validate_schema.py
python tools/admin/validate_officials.py --county montgomery
```

After Stage 7 you should see a small table like:

```
  incumbent          matched   84  unmatched   12
  captain_candidate  matched  140  unmatched   27
  general_candidate  matched   38  unmatched    9
```

Some "unmatched" is normal — district-level officials (like a U.S. Representative)
have no home address in the county CSV, so they can only be matched by name. Use
`--verbose` to see every hit and miss.

After Stage 8 you should see:

```
VALIDATION PASSED: N/N checks
```

If you see `VALIDATION FAILED`, read the `[FAIL]` lines — each says exactly what is
wrong and which file to fix.

---

## 5. How to tell a run went well

- `serve/partisan_profiles.json` exists and is a few hundred KB, not empty.
- The Stage 7 table shows mostly matched, with a short unmatched list you recognize.
- `python tools/admin/validate_officials.py --county montgomery` prints
  **VALIDATION PASSED**.
- `git diff schema/` shows changes **only between** the
  `<!-- BEGIN GENERATED INVENTORY -->` and `<!-- END GENERATED INVENTORY -->` markers.
  The hand-written notes above those markers should be untouched. If hand-written text
  changed, stop — something edited the wrong part.

### Quick way to prove the safety net works
Open any `serve/*.json`, change a status word to something fake (like `vacantX`), save,
and run Stage 8. It should **FAIL** loudly. Undo your change and it should pass again.
That confirms the validator is really guarding the data.

---

## 6. When to re-run

- **New SOS officials CSV** → re-run Stage 1, then Stage 7 and 8.
- **New weekly candidate petition PDF** → re-run Stage 4, Stage 6, then Stage 7 and 8.
- **New voter file drop** → re-run Stage 7 and 8 (the lean scores can change).
- **Any change to a producer** → always finish with Stage 8.

---

## 7. Saving your work (git)

These files are meant to be committed (per `CLAUDE.md §10`, you push from your own
terminal — not through the MCP):

```
git add serve/partisan_profiles.json serve/officials.json serve/precinct_captains.json serve/candidates.json
git add tools/admin/match_to_voters.py tools/admin/validate_schema.py tools/admin/validate_officials.py
git add pipeline/officials_pipeline_wrapper.py
git add schema/enriched/enriched_voters.md schema/serve/partisan_profiles.md
git add schema/serve/officials.md schema/serve/precinct_captains.md schema/serve/candidates.md
git commit -m "Add officials pipeline consumer, validator, schema machinery, and wrapper"
git push
```

Do **not** push `docs/data/` through the MCP (it is huge — `CLAUDE.md §9`).

---

## ⚠️ Schema rules and known limits (read before the first run)

These are the `CLAUDE.md §4` SWVF rules that matter here, and the few spots that need
your attention. **The code follows every rule below** — these notes tell you *how* it
follows them and where to double-check.

1. **"Lapsed" means an empty party, not an old date.** The code decides a voter is
   "lapsed" when `PARTY_AFFILIATION` is blank (`""`). It never uses a number-of-years
   cutoff for the label. We **checked the voter file on 2026-06-25**: blanks are stored
   as empty strings (`""`), with **zero** nulls, so the `== ""` test is correct. The
   code also treats a null as blank, just in case a future file stores it differently.
   ✅ Rule followed. *If a future voter file starts storing blanks as null instead of
   `""`, this still works — but it is worth re-checking with a quick count.*

2. **Postal city/zip is never used as a jurisdiction.** Stage 7 uses zip codes **only**
   to tell two same-name voters apart, never to decide what city or ward someone is in.
   ✅ Rule followed.

3. **Home zip, not office zip.** For officials, the code reads `HZIPCODE` (home) from
   the CSV and never `OZIPCODE` (office). ✅ Rule followed.

4. **Captains are matched with no zip — flag.** Precinct captains have **no address
   anywhere** in the source data. So the code matches them by **name + precinct** only.
   This is weaker than a zip match. Treat captain matches (and any `fuzzy` match) as
   "likely, please spot-check," not "certain." This is a data limit, not a bug — there
   is no address to use. ⚠️ **Lower confidence by design.**

5. **One county only.** Everything here is Montgomery (county 57). Names repeat across
   Ohio's counties (there is a "Washington Township" in 23 counties), so if this is ever
   extended to more counties, the matching must key on **county + name together**. Today,
   with one county, there is no collision. ⚠️ **Do not run multi-county without adding
   the county key first.**

6. **Voter status is only ACTIVE or CONFIRMATION.** Stage 7 only looks at these two
   statuses, which are the only two the voter file uses. ✅ Rule followed.

If any future change cannot keep one of the ✅ rules above, **stop and flag it loudly**
— these rules are the ones that caused the project's worst past bugs.

## Temporary data sources (workarounds in effect)

Some inputs are stopgaps until the county updates its records. Knowing this keeps you
from mistaking "we do not have it yet" for "it does not exist."

- **Precinct captains (DEM / LIB):** built from one-off central-committee filing PDFs
  (`DEM-CENTRAL-COMMITTEE-5-2-26.pdf`, `LIB-CENTRAL-COMMITTEE.pdf`). These are
  temporary. The captain file marks each party's source and coverage in
  `_meta.parties` so you always know where a row came from.
- **Precinct captains (REP):** mostly **missing**. The Republican central-committee
  report has not arrived, so every R precinct except one (Nick Brusky, DAYTON 3-E,
  from the CSV) is `data_pending` -- meaning "unknown", **not** "vacant". Do not read
  an empty R precinct as "no one is running."
- **Precinct captains are themselves elected officials.** They are in their own file
  today only because their data comes from filing PDFs, not the canonical CSV. A
  *sitting* captain (Nick Brusky) is a `DISTTYPE == PRECINCT` row in
  `electedofficials.csv` -- an officeholder, the same shape as any other official --
  and is a different thing from a 2026 *filer* running for the seat. When the
  complete CSV arrives, those PRECINCT officeholders should be ingested as officials
  like everyone else (a routing choice still to be decided). The current separation
  is a sourcing workaround, not a statement that captains are not officials.
- **The real source is coming.** The county Board of Elections' canonical export,
  `local/source/electedofficials.csv` (from
  https://lookup.boe.ohio.gov/vtrapp/montgomery/cnm.aspx), is supposed to list **all**
  elected officials, including precinct captains. It is not complete yet, and the BoE
  has not given a date.

**Will the pipeline break when the complete CSV arrives? No.** Stage 7 (Match) and
Stage 8 (Validate) read the **serve files**, not the raw sources, so they do not care
which source produced a row. When the full CSV lands, the producer scripts regenerate
the serve files, the R `data_pending` count drops toward zero, and you simply re-run
Stages 7 and 8. No schema change and no code change in this session's files are needed.
One future nicety: when captains finally carry a home zip, the captain matcher could
use it as an extra tiebreaker (today it matches captains by name + precinct only).

## Three facts about party, kept separate

Ohio voters never register a party -- it is inferred only from which primary ballot
they pull. So three different "party" ideas exist, and the code keeps them apart on
purpose:

1. **Is the office nonpartisan?** A charter fact about the *seat* (school board,
   township trustee, most municipal/judicial). The office `party` is blank because a
   nonpartisan race gives no chance to file an affiliation. In a matched record this is
   `nonpartisan_office`.
2. **What party did the person FILE under?** `filing_party` -- what is printed on the
   ballot. For a partisan office, someone who has pulled one party's primaries for years
   may still file as an Independent or another party. That is allowed and expected.
3. **What does their voting behavior say?** `PARTY_AFFILIATION`, `lean_score`, and the
   `partisan_profile_label`, from their own primary ballots.

The mixed case is normal: `filing_party: "I"` next to `partisan_profile_label: "Pure D"`
means "ran as an Independent, but has only ever voted in Democratic primaries." All
three facts are separate fields from separate sources -- none overwrites another.

Also note the label **"Non-Partisan Voter"** means the voter only ever pulled
non-partisan (`X`) ballots -- that is about the *voter's behavior*, and is a different
idea from a *nonpartisan office*. Same word, different meaning.
