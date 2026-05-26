# Handoff: Build-Time LLM Narrative Generation — Quick Demo

## Mission

Add grounded, hallucination-proof prose narratives to the precincts.info V2 dashboard.
During the data pipeline run, call the Claude API with structured voter-file metrics and
save the result as `{slug}_narrative.json` alongside the existing chart JSON files.
The V2 dashboard (`docs/v2.html`) then loads and renders this as a prose block beneath
the hero section.

**Scope for this demo:** County level only (88 counties). Do not touch precincts or
districts yet. Get one working end-to-end loop: Python script → JSON → rendered in
browser.

---

## Repo layout (what matters)

```
D:\vibe\election-data\
  docs/
    v2.html                  ← the dashboard (parallel to live index.html)
    assets/
      v2.js                  ← 1446-line app; loadJurisdiction() fetches data files
      v2.css                 ← layout/component styles
      v2-tokens.css          ← design token system
    data/
      {slug}_party_affiliation.json     ← primary data file per county
      {slug}_decade_distribution.json
      {slug}_generation_distribution.json
      {slug}_party_by_decade.json
      {slug}_unc_shadow.json
      {slug}_city_summary.json
      {slug}_narrative.json             ← TARGET: create this file
    manifest.json            ← lists all 88 county names
  tools/
    generate_narratives.py   ← CREATE THIS (standalone script)
  voter_data_cleaner_v2.py   ← main pipeline engine (do not touch for demo)
  ohio_voter_pipeline.py     ← pipeline entry point (do not touch for demo)
```

Slugs are lowercase county names with spaces replaced by underscores, e.g.
`Hamilton` → `hamilton`, `Van Wert` → `van_wert`.

---

## Step 1 — Create `tools/generate_narratives.py`

This is a standalone script. It reads existing JSON files from `docs/data/`,
calls the Claude API, and writes `{slug}_narrative.json` back to `docs/data/`.
It does NOT run the voter pipeline — it consumes already-generated chart JSON.

### How to install the SDK

```powershell
# In the project root (D:\vibe\election-data)
.venv\Scripts\pip install anthropic --break-system-packages
# OR if using uv:
uv add anthropic
```

### Script structure

```python
"""
tools/generate_narratives.py

Reads existing county chart JSON from docs/data/ and calls the Claude API
to generate a 2-3 sentence grounded narrative for each county.

Usage:
  python tools/generate_narratives.py                  # all 88 counties
  python tools/generate_narratives.py Hamilton Franklin # targeted run
  python tools/generate_narratives.py --dry-run        # print prompts, no API calls
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

import anthropic

ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'docs' / 'data'
MANIFEST = ROOT / 'docs' / 'manifest.json'

MODEL          = 'claude-haiku-4-5-20251001'   # fast + cheap for demo; swap to sonnet for quality
PROMPT_VERSION = 'v1'
MAX_TOKENS     = 220
TEMPERATURE    = 0   # deterministic — factual output only
RATE_LIMIT_SEC = 0.3  # polite pause between calls


def county_slug(name: str) -> str:
    return name.lower().replace(' ', '_').replace("'", '')


def load_json_safe(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def build_metrics(slug: str) -> dict | None:
    """
    Assemble a structured metrics dict from existing chart JSON files.
    Returns None if the primary party_affiliation file is missing.
    """
    pa  = load_json_safe(DATA_DIR / f'{slug}_party_affiliation.json')
    if not pa:
        return None

    gen = load_json_safe(DATA_DIR / f'{slug}_generation_distribution.json')
    pbd = load_json_safe(DATA_DIR / f'{slug}_party_by_decade.json')

    # ── Party affiliation ──────────────────────────────────────────────────
    labels = pa['chartConfig']['labels']   # 7 cohort labels
    data   = pa['chartConfig']['datasets'][0]['data']
    total  = sum(data)

    cohorts = {labels[i]: data[i] for i in range(len(labels))}
    r_lean  = data[0] + data[1]   # Pure R + UNC-Lapsed R
    d_lean  = data[5] + data[6]   # UNC-Lapsed D + Pure D
    unc     = data[2] + data[3] + data[4]

    metrics = {
        'county':        pa.get('county', slug.replace('_', ' ').title()),
        'data_as_of':    pa.get('updated', ''),
        'total_voters':  total,
        'party': {
            'r_lean_pct':  round(r_lean / total * 100, 1),
            'd_lean_pct':  round(d_lean / total * 100, 1),
            'unc_pct':     round(unc    / total * 100, 1),
            'pure_r_pct':  round(data[0] / total * 100, 1),
            'pure_d_pct':  round(data[6] / total * 100, 1),
            'net_lean':    round((d_lean - r_lean) / total * 100, 1),  # + = D, - = R
        },
    }

    # ── Generation distribution ────────────────────────────────────────────
    if gen:
        glabels = gen['chartConfig']['labels']
        gdata   = gen['chartConfig']['datasets'][0]['data']
        gtotal  = sum(gdata) or 1
        metrics['generations'] = {
            glabels[i]: round(gdata[i] / gtotal * 100, 1)
            for i in range(len(glabels))
        }

    # ── Party trend by decade (oldest→youngest) ────────────────────────────
    # Summarise into: are younger cohorts more R, D, or UNC than older ones?
    if pbd:
        ds = pbd['chartConfig']['datasets']
        dec_labels = pbd['chartConfig']['labels']
        # Keep only last 3 decades (most recent voters) vs first 3 (oldest)
        # Simple lean index per decade: (D-cohorts - R-cohorts) / all
        ds_map = {d['label']: d['data'] for d in ds}
        def decade_lean(idx):
            r = (ds_map.get('Pure R', [0]*10)[idx] +
                 ds_map.get('UNC – Lapsed R', [0]*10)[idx])
            d_ = (ds_map.get('Pure D', [0]*10)[idx] +
                  ds_map.get('UNC – Lapsed D', [0]*10)[idx])
            tot = sum(v[idx] for v in ds_map.values()) or 1
            return round((d_ - r) / tot * 100, 1)
        # Use 1950s/60s as "older" baseline, 1990s/2000s as "younger"
        older_lean   = round((decade_lean(4) + decade_lean(5)) / 2, 1)  # 1950s+60s
        younger_lean = round((decade_lean(8) + decade_lean(9)) / 2, 1)  # 1990s+2000s
        metrics['trend'] = {
            'older_cohort_lean_d_minus_r':   older_lean,
            'younger_cohort_lean_d_minus_r': younger_lean,
            'direction': 'bluer' if younger_lean > older_lean else 'redder',
        }

    return metrics


SYSTEM_PROMPT = """You are a civic data analyst writing factual summaries for a
nonpartisan voter registration dashboard. Your summaries must be grounded
strictly in the numbers provided. Do not add context, history, or claims
from your training data about specific people, elections, or events.
Do not name incumbents or candidates. Do not speculate beyond what the
numbers show. Write in plain American English, 2-3 sentences, present tense."""


def build_user_prompt(metrics: dict) -> str:
    county  = metrics['county']
    total   = f"{metrics['total_voters']:,}"
    party   = metrics['party']
    net     = party['net_lean']
    lean_str = (f"{abs(net):.1f}% net Democratic-leaning" if net > 0
                else f"{abs(net):.1f}% net Republican-leaning")

    lines = [
        f"Write a 2-3 sentence factual summary of {county}'s voter registration makeup.",
        f"",
        f"DATA (use only these numbers — do not add outside knowledge):",
        f"  Total registered voters: {total}",
        f"  Republican-leaning: {party['r_lean_pct']}%  (Pure R {party['pure_r_pct']}% + behaviorally-lapsed R)",
        f"  Democratic-leaning: {party['d_lean_pct']}%  (Pure D {party['pure_d_pct']}% + behaviorally-lapsed D)",
        f"  Unaffiliated / no primary history: {party['unc_pct']}%",
        f"  Net lean: {lean_str}",
    ]

    if 'generations' in metrics:
        gen = metrics['generations']
        # Find the largest generation
        top_gen = max(gen, key=gen.get)
        lines.append(f"  Largest generation: {top_gen} at {gen[top_gen]}% of registered voters")

    if 'trend' in metrics:
        t = metrics['trend']
        lines.append(
            f"  Generational trend: voters born in the 1990s-2000s lean "
            f"{t['younger_cohort_lean_d_minus_r']:+.1f}% D-R vs "
            f"{t['older_cohort_lean_d_minus_r']:+.1f}% D-R for 1950s-60s cohorts "
            f"— registration is trending {t['direction']} in younger age groups."
        )

    lines += [
        f"",
        f"Data as of: {metrics['data_as_of']}",
        f"",
        f"Write only the 2-3 sentence summary. No headers, no bullet points, no outside context.",
    ]
    return '\n'.join(lines)


def generate_narrative(client: anthropic.Anthropic, metrics: dict, dry_run: bool) -> str | None:
    prompt = build_user_prompt(metrics)
    if dry_run:
        print(f"\n{'='*60}")
        print(f"PROMPT for {metrics['county']}:")
        print(prompt)
        return None

    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logging.error('API error for %s: %s', metrics['county'], e)
        return None


def write_narrative_json(slug: str, metrics: dict, narrative: str) -> None:
    out = {
        'geography':       'county',
        'jurisdiction_name': metrics['county'],
        'updated':         metrics['data_as_of'],
        'generated_by':    MODEL,
        'prompt_version':  PROMPT_VERSION,
        'narrative':       narrative,
    }
    path = DATA_DIR / f'{slug}_narrative.json'
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    logging.info('Wrote %s', path.name)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('counties', nargs='*', help='County names to process (default: all)')
    parser.add_argument('--dry-run', action='store_true', help='Print prompts without API calls')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing narrative files')
    args = parser.parse_args()

    # Load county list from manifest
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    all_counties = manifest.get('processedCounties') or manifest.get('counties') or []

    if args.counties:
        target = [c for c in all_counties if c in args.counties]
        missing = set(args.counties) - set(target)
        if missing:
            logging.warning('Not found in manifest: %s', missing)
    else:
        target = all_counties

    client = None if args.dry_run else anthropic.Anthropic(
        api_key=os.environ.get('ANTHROPIC_API_KEY')
    )

    ok = skipped = failed = 0
    for county in target:
        slug = county_slug(county)
        out_path = DATA_DIR / f'{slug}_narrative.json'

        if out_path.exists() and not args.overwrite and not args.dry_run:
            logging.info('Skip %s (exists; use --overwrite to regenerate)', slug)
            skipped += 1
            continue

        metrics = build_metrics(slug)
        if not metrics:
            logging.warning('No party data for %s — skipping', slug)
            failed += 1
            continue

        narrative = generate_narrative(client, metrics, args.dry_run)

        if narrative:
            write_narrative_json(slug, metrics, narrative)
            ok += 1
            time.sleep(RATE_LIMIT_SEC)
        elif not args.dry_run:
            failed += 1

    if not args.dry_run:
        logging.info('Done — ok:%d skipped:%d failed:%d', ok, skipped, failed)


if __name__ == '__main__':
    main()
```

### To run the demo (5 counties first)

```powershell
cd D:\vibe\election-data
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # set your key

# Dry run — see prompts without spending API calls
python tools/generate_narratives.py Hamilton Franklin Cuyahoga --dry-run

# Real run — 5 populous counties
python tools/generate_narratives.py Hamilton Franklin Cuyahoga Montgomery Summit

# Full 88-county run
python tools/generate_narratives.py
```

---

## Step 2 — Wire the narrative into `docs/assets/v2.js`

Three small edits. Do not reorganize anything else.

### 2a. Fetch the narrative file in `loadJurisdiction()`

Find the county block (line ~183):
```javascript
if (level === 'county') {
  const s = id;
  add('party',       `data/${s}_party_affiliation.json`);
  add('decade',      `data/${s}_decade_distribution.json`);
  // ... existing lines ...
  add('precinctIndex',`data/${s}_precinct_index.json`);
}
```

Add one line after the last `add()` in the county block:
```javascript
  add('narrative',   `data/${s}_narrative.json`);
```

### 2b. Add a narrative card to `buildCenterPaneSingle()`

Find (line ~934):
```javascript
'<div class="hero" id="hero"></div>' +
'<div class="charts-grid">' +
```

Change to:
```javascript
'<div class="hero" id="hero"></div>' +
'<div class="narrative-card" id="narrative-card" style="display:none"></div>' +
'<div class="charts-grid">' +
```

### 2c. Render the narrative in `refreshView()`

Find the single-jurisdiction branch (around line ~1159):
```javascript
renderBreadcrumb(bag);
renderHero($('hero'), bag);
renderCharts(bag);
renderMapSelection(bag);
```

Add one line after `renderHero`:
```javascript
renderNarrative(bag);
```

Then add the `renderNarrative` function anywhere in the IIFE, e.g. just before `renderBreadcrumb`:

```javascript
function renderNarrative(bag) {
  const el = $('narrative-card');
  if (!el) return;
  if (!bag.narrative || !bag.narrative.narrative) {
    el.style.display = 'none';
    return;
  }
  el.style.display = '';
  el.innerHTML =
    '<div class="eyebrow" style="margin-bottom:6px">Jurisdiction overview</div>' +
    '<p class="narrative-text">' + bag.narrative.narrative + '</p>' +
    '<div class="narrative-meta">Data as of ' + (bag.narrative.updated || '') +
    ' &middot; generated by ' + (bag.narrative.generated_by || 'AI') + '</div>';
}
```

### 2d. Add minimal CSS to `docs/assets/v2.css`

Append to the end of the file:

```css
/* ── Narrative card ─────────────────────────────────────── */
.narrative-card {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r);
  padding: var(--pad-card);
  margin-bottom: var(--gap-stack);
}
.narrative-text {
  font-family: var(--ff-serif);
  font-size: 15px;
  line-height: 1.65;
  color: var(--ink);
  margin: 0 0 8px;
}
.narrative-meta {
  font-family: var(--ff-mono);
  font-size: 10px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
```

---

## Output file format (`{slug}_narrative.json`)

```json
{
  "geography": "county",
  "jurisdiction_name": "Hamilton County",
  "updated": "2026-05-09",
  "generated_by": "claude-haiku-4-5-20251001",
  "prompt_version": "v1",
  "narrative": "Hamilton County has 602,004 registered voters, with 47.5% unaffiliated
    or lacking primary history — the largest segment by far. Republican-leaning voters
    make up 18.5% of registrants, while Democratic-leaning voters account for 22.1%,
    giving the county a modest net Democratic lean of 3.6 percentage points. Millennials
    are the largest generational cohort at 30.9%, and younger birth-decade cohorts lean
    measurably more Democratic than older ones."
}
```

---

## Data shapes consumed by the script

All from `docs/data/{slug}_*.json`. Every file has a `chartConfig` key.

**`_party_affiliation.json`** — the anchor file
- `chartConfig.labels`: 7 strings — `['Pure R', 'UNC – Lapsed R', 'Mixed – Active', 'Mixed – Lapsed', 'UNC – No Primary', 'UNC – Lapsed D', 'Pure D']`
- `chartConfig.datasets[0].data`: 7 integers (voter counts per cohort)
- `meta`: `{ new_registrants_r, new_registrants_d, new_registrants_unc }` (optional)
- `updated`: ISO date string e.g. `"2026-05-09"`

**`_generation_distribution.json`**
- `chartConfig.labels`: `['Silent/Greatest', 'Baby Boomers', 'Gen X', 'Millennials', 'Gen Z']`
- `chartConfig.datasets[0].data`: 5 integers

**`_party_by_decade.json`**
- `chartConfig.labels`: decade strings `['1910s', '1920s', ..., '2000s']`
- `chartConfig.datasets`: 7 datasets (one per cohort), each with `label` and `data` (10 integers)

**`manifest.json`** — county name list
- `processedCounties` or `counties`: array of 88 strings (proper-cased county names)

---

## Grounding rules for prompt design

The system prompt must prevent the LLM from drawing on training knowledge.
Key principles already encoded in the script above:

1. All numbers are explicitly provided — the LLM is told to use only them.
2. No incumbent names, no election references, no historical events.
3. Temperature 0 — no creative variation.
4. Max 220 tokens — forces tight, factual sentences.
5. `prompt_version` field in output JSON lets you invalidate old narratives if prompt changes.

If the output ever contains a claim not derivable from the metrics block, the prompt
needs a tighter constraint. Add: *"Every factual claim must cite a number I provided.
Do not use phrases like 'historically' or 'since [year]'."*

---

## Cost estimate for demo run

Using `claude-haiku-4-5-20251001`:
- Input: ~350 tokens/county × 88 counties = ~30,800 tokens ≈ $0.02
- Output: ~80 tokens/county × 88 counties = ~7,040 tokens ≈ $0.007
- **Total for 88-county run: ~$0.03**

Using `claude-sonnet-4-6` (higher quality):
- ~$0.80 for all 88 counties

---

## Git commit guidance

Per project rules, batch all changes in one commit. Do not push `docs/data/` via
MCP (65k files). Code-only files are safe to push via MCP `push_files`:

```
tools/generate_narratives.py    (new)
docs/assets/v2.js               (3 small edits)
docs/assets/v2.css              (appended narrative styles)
```

The generated `docs/data/*_narrative.json` files must be pushed manually:

```powershell
cd D:\vibe\election-data
git add docs/data/*_narrative.json
git commit -m "feat(narrative): add LLM-generated county summaries (demo, 88 counties)"
git push
```

---

## Known gaps / do not fix in this session

- Precinct and district narratives: out of scope for demo
- Incumbent names: not in SWVF; needs separate Google Civic API integration
- Compare mode: `renderNarrative` only wires to single-jurisdiction view; compare shows two heroes already
- `v2.js` narrative fetch silently 404s for counties not yet generated — this is fine; `renderNarrative` hides the card if missing
- `narrative.json` is not included in `manifest.json` chartConfig; no need to add it there

---

## References

- CLAUDE.md (project root) — file editing protocol, git push rules, PII constraints
- `docs/assets/v2.js` — full app; `loadJurisdiction()` at line ~176, `buildCenterPaneSingle()` at line ~931, `refreshView()` at line ~1130
- `voter_data_cleaner_v2.py` — pipeline engine (reference only; do not touch)
- `jurisdictional_groupings.py` — jurisdiction JSON export (reference only)
