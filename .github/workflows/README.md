# CI

This explains the automated checks in `ci.yml` — what they do, why they exist, and how to
read the results. This is the first CI this repo has had; previously the only GitHub
Actions workflow was `pages-build-deployment`, which just publishes `docs/` to
precincts.info and doesn't check anything before doing so.

## What "CI" means here, concretely

CI stands for Continuous Integration — in practice it's just: a script that GitHub runs
automatically every time code is pushed or a pull request is opened, so mistakes get caught
by a machine instead of relying on someone noticing by eye. It runs in a temporary GitHub-
hosted container, separate from your machine and separate from this repo's live site — it
can't break anything by running, it only reports pass/fail.

You'll see it as a row of checks (✅ or ❌) at the bottom of any pull request, or under the
repo's **Actions** tab (`github.com/motorbikematt/ohio_voter_registration_parser/actions`).

## When it runs

Defined in `ci.yml`'s `on:` block: every push to `main`, and every pull request (any
branch). Two independent jobs run in parallel — either can fail without affecting the other.

## Job 1: `frontend-syntax` — Frontend JS syntax check

**What it does:** runs `node --check` against every `.js` file under `docs/` (`docs/*.js`,
`docs/assets/*.js`, `docs/captain/*.js`, `docs/activate/*.js`) — currently `charts.js`,
`v2.js`, `v2-hex-map.js`, `captain-mode.js`, `activate.js`.

**What `node --check` actually does:** it parses the file and reports a syntax error if the
JavaScript is malformed — it does *not* run the code or catch logic bugs. Think of it as
"does this file even load without crashing," not "does this file work correctly." It's cheap
(a couple seconds) and catches an entire class of mistake: a typo, an unmatched brace, a
stray character from a bad edit — the kind of thing that would otherwise only surface as a
silent blank page or broken chart on the live site, with no error message anywhere.

**Run it yourself before pushing:**
```bash
node --check docs/assets/v2.js
```

## Job 2: `data-naming` — docs/data/city slug naming check

**What it does:** runs `tools/tests/test_data_slug_naming.py`, a Python test (via `pytest`)
that scans every file in `docs/data/city/` and checks its filename is a "clean slug" — only
lowercase letters, digits, and single underscores, with no double underscores.

**Why this exists:** in July 2026, `pipeline/jurisdictional_groupings.py`'s filename
generator had a bug where a city name with a trailing space or stray punctuation (e.g. a
raw value like `"COLUMBUS CITY "` with a trailing space, or `"WASHINGTON C.H."` with
periods) produced a broken filename like `columbus_city__decade_distribution.json` (double
underscore) or one containing a literal period. The dashboard's frontend
(`docs/assets/v2.js`) builds its own, always-clean version of the same slug when it fetches
chart data — so the mismatch meant the frontend requested a file that didn't exist under
that name, got a 404, and the whole page silently showed "No summary data found" with no
error visible anywhere except the browser's network tab. Nine cities were affected,
including Columbus — Ohio's largest city — before it was caught. This test is a permanent
guard against that specific failure mode recurring after a future pipeline run.

**Run it yourself:**
```bash
pip install pytest
pytest tools/tests/test_data_slug_naming.py -v
```

**If it fails**, the assertion message lists the offending filenames directly (capped at 10
per problem type, with a count of how many more there are) — no need to dig through logs.

**Scope note:** this only checks `docs/data/city/`, not the rest of `docs/data/`. While
building it, a first draft that scanned the entire `docs/data/` tree found ~2,500 files in
`docs/data/local_school_district/` and `docs/data/exempted_village_school_district/` using a
different naming pattern with parentheses (e.g. `ada_ex_vill_sd_(hardin)_...`). That wasn't
confirmed to be a bug — those two jurisdiction types aren't currently linked from the
frontend at all, so nothing 404s today — and folding it in would have made this check fail
immediately for a separate, not-yet-understood reason. Deliberately left out; see the
handoff doc from the session that added this file for the investigation notes.

## What's *not* covered yet

This repo already has a larger test suite under `tools/tests/` (`test_pass_b_index.py`,
`test_pass_b_cache.py`, `test_jurisdiction_collisions.py`, `test_voter_data_cleaner.py`,
`test_pass_b_manifest_frontend.py`) that is **not** wired into CI. Running it locally
currently gives 126 failed / 27 errored out of ~210 tests, unrelated to anything in this
workflow — several tests reference `docs/index.html`, a file that was renamed to
`docs/index.htm` during an earlier frontend rewrite, plus at least one test has an unrelated
path bug. Wiring that suite into CI as-is would make every future PR red from its first run
for old, pre-existing reasons that have nothing to do with the change being reviewed — worse
than having no CI at all, since a check that's always red gets ignored. It needs a separate
triage pass before it can be added here. See the handoff doc for details.

Also not covered: anything that requires the raw SWVF source data (`local/`, gitignored).
That data is real voter PII and must never be uploaded to a GitHub-hosted runner — so the
core pipeline logic that transforms raw data can only ever be tested locally, on your own
machine, against your own copy of the source files. CI here is deliberately limited to
checks that only need already-public, already-committed files.
