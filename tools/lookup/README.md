# tools/lookup/

Ad hoc, read-only search and cross-reference utilities for finding individual voter records —
by free-text search, or by matching a named official/candidate to their registration. Distinct
from `tools/admin/`'s staged officials pipeline: these are standalone investigative tools, not
pipeline stages, and none of them write to `serve/`.

**Terminology note (2026-07):** these scripts return raw SWVF fields (name, DOB, address, party
affiliation, voting history) — Ohio public record, not PII by itself; anyone can obtain the same
data from a Board of Elections or the SOS lookup portal. The stricter PII/SOC2-Type2 handling
threshold applies only when a voter record is *joined* against non-public personally-identifying
data (a personal phone/email — see `match_officials_to_voters.py` below, and `CLAUDE.md §9`'s
`H*` field policy). Every search output here still stays out of the repo (all write to the
gitignored project root or `local/working/`) — but for reasons independent of PII classification:
it's a generated data artifact, not code or documentation, and it goes stale within weeks of the
source SWVF drop. Delete search-result CSVs once you're done with them; they have no reason to
accumulate.

### `voter_lookup_parquet.py`
*(renamed 2026-07 from `voter_lookup.py`; function names `run_global_parquet_search()` etc.
are unchanged — only the filename changed, to disambiguate from `voter_lookup_source.py`
below. If anything imports this by the old filename/path, update the reference. Same date:
added optional `--last`/`--first` field-scoped filters — `--last` is a prefix match against
`LAST_NAME`, `--first` is a substring match against `FIRST_NAME`, and the two AND together, so
`--last Roberts --first Zach` finds both "Zach" and "Zachary" Roberts without needing to guess
which form the voter file uses; the bare positional `term` search has no wildcard support and
can't do that on its own. Also fixed a pre-existing bug in the same pass: the console summary
crashed with `UnicodeEncodeError` under the Windows cp1252 console default whenever a matched
row held a non-ASCII character — stdout is now reconfigured to UTF-8 on startup.)*
- **Function:** Global substring search across **every column** of the enriched Parquet cache,
  case-insensitive, scanning all county partitions. The general-purpose "find one voter" tool —
  search by name, address fragment, `SOS_VOTERID`, etc. Prints a jurisdictional summary (top
  CITY/TOWNSHIP/VILLAGE/PRECINCT_NAME combinations) and a per-county match breakdown to the console.
- **Inputs:** a search term (positional arg, or prompts interactively if omitted);
  `local/source/parquet/COUNTY_NUMBER=*/` partitions (or `--dir` override); optional `--last`
  (LAST_NAME prefix) / `--first` (FIRST_NAME substring) field filters, usable with or without
  the positional term.
- **Outputs:** `search_{term}_{timestamp}.csv` at the project root — all 135 columns for every
  matching row.
- **Usage:** `python tools/lookup/voter_lookup_parquet.py "SEARCH TERM"` (or run with no argument
  to be prompted), or `python tools/lookup/voter_lookup_parquet.py --last Roberts --first Zach`
  for a name search that's tolerant of nickname-vs-legal-name mismatches.

### `voter_lookup_source.py`
*(renamed 2026-07 from `raw_voter_lookup.py`; function name `run_global_raw_search()` is
unchanged — only the filename changed, to pair with `voter_lookup_parquet.py` above. If
anything imports this by the old filename/path, update the reference.)*
- **Function:** Same global substring search as `voter_lookup_parquet.py`, but scans the **raw**
  `SWVF_*.txt` source files directly instead of the cleaned Parquet cache. Useful when a record is
  suspected to have been dropped or altered somewhere in pipeline processing and you need to check
  the untouched original.
- **Inputs:** a search term (positional arg, or prompts interactively);
  `local/source/State Voter Files/SWVF_*.txt` (or `--dir` override).
- **Outputs:** `search_raw_{term}_{timestamp}.csv` at the project root — all columns for every
  matching row, with a `SOURCE_FILE` column noting which SWVF split file it came from.
- **Usage:** `python tools/lookup/voter_lookup_source.py "SEARCH TERM"` (or run with no argument
  to be prompted).

### `match_officials_to_voters.py`
- **Function:** Links rows in `electedofficials.csv` that have a home zip (`HZIPCODE`) to their
  voter registration record in the enriched Parquet, using DuckDB for the candidate query and a
  two-pass strategy (exact last name + first-name prefix via SQL, then rapidfuzz full-name fuzzy
  matching with zip as a tiebreaker). An earlier, narrower-scoped sibling of
  `tools/admin/match_to_voters.py`'s single resolver — this one is officials-CSV-only and
  standalone, not part of the staged pipeline.
- **Inputs:** `local/source/electedofficials.csv`,
  `local/source/parquet_enriched/enriched_voters.parquet`.
- **Outputs:** `local/working/officials_voter_links.json` (per-official match method, score,
  matched `SOS_VOTERID`, voter status/party, and `address_verified` flag).
- **Usage:**
  `python tools/lookup/match_officials_to_voters.py [--county 57] [--all-counties] [--verbose]`
- **Requires:** `duckdb`, `rapidfuzz`.

## Empty / stub

### `__init__.py`
Empty — makes `tools/lookup/` importable as a package.
