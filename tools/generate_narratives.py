"""tools/generate_narratives.py — county narrative generator (demo)."""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None

ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'docs' / 'data'
MANIFEST = ROOT / 'docs' / 'manifest.json'

MODEL          = 'claude-haiku-4-5-20251001'
PROMPT_VERSION = 'v1'
MAX_TOKENS     = 220
TEMPERATURE    = 0
RATE_LIMIT_SEC = 0.3


def county_slug(name: str) -> str:
    return name.lower().replace(' ', '_').replace("'", '')


def load_json_safe(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def build_metrics(slug: str):
    pa = load_json_safe(DATA_DIR / f'{slug}_party_affiliation.json')
    if not pa:
        return None

    gen = load_json_safe(DATA_DIR / f'{slug}_generation_distribution.json')
    pbd = load_json_safe(DATA_DIR / f'{slug}_party_by_decade.json')

    labels = pa['chartConfig']['labels']
    data   = pa['chartConfig']['datasets'][0]['data']
    total  = sum(data) or 1

    r_lean = data[0] + data[1]
    d_lean = data[5] + data[6]
    unc    = data[2] + data[3] + data[4]

    metrics = {
        'county':       pa.get('county', slug.replace('_', ' ').title()),
        'data_as_of':   pa.get('updated', ''),
        'total_voters': sum(data),
        'party': {
            'r_lean_pct': round(r_lean / total * 100, 1),
            'd_lean_pct': round(d_lean / total * 100, 1),
            'unc_pct':    round(unc    / total * 100, 1),
            'pure_r_pct': round(data[0] / total * 100, 1),
            'pure_d_pct': round(data[6] / total * 100, 1),
            'net_lean':   round((d_lean - r_lean) / total * 100, 1),
        },
    }

    if gen:
        glabels = gen['chartConfig']['labels']
        gdata   = gen['chartConfig']['datasets'][0]['data']
        gtotal  = sum(gdata) or 1
        metrics['generations'] = {
            glabels[i]: round(gdata[i] / gtotal * 100, 1)
            for i in range(len(glabels))
        }

    if pbd:
        ds = pbd['chartConfig']['datasets']
        ds_map = {d['label']: d['data'] for d in ds}
        def decade_lean(idx):
            r  = (ds_map.get('Pure R', [0]*10)[idx] +
                  ds_map.get('UNC – Lapsed R', [0]*10)[idx])
            d_ = (ds_map.get('Pure D', [0]*10)[idx] +
                  ds_map.get('UNC – Lapsed D', [0]*10)[idx])
            tot = sum(v[idx] for v in ds_map.values()) or 1
            return round((d_ - r) / tot * 100, 1)
        try:
            older_lean   = round((decade_lean(4) + decade_lean(5)) / 2, 1)
            younger_lean = round((decade_lean(8) + decade_lean(9)) / 2, 1)
            metrics['trend'] = {
                'older_cohort_lean_d_minus_r':   older_lean,
                'younger_cohort_lean_d_minus_r': younger_lean,
                'direction': 'bluer' if younger_lean > older_lean else 'redder',
            }
        except IndexError:
            pass

    return metrics


SYSTEM_PROMPT = """You are a civic data analyst writing factual summaries for a
nonpartisan voter registration dashboard. Your summaries must be grounded
strictly in the numbers provided. Do not add context, history, or claims
from your training data about specific people, elections, or events.
Do not name incumbents or candidates. Do not speculate beyond what the
numbers show. Write in plain American English, 2-3 sentences, present tense."""


def build_user_prompt(metrics: dict) -> str:
    county = metrics['county']
    total  = f"{metrics['total_voters']:,}"
    party  = metrics['party']
    net    = party['net_lean']
    lean_str = (f"{abs(net):.1f}% net Democratic-leaning" if net > 0
                else f"{abs(net):.1f}% net Republican-leaning")

    lines = [
        f"Write a 2-3 sentence factual summary of {county}'s voter registration makeup.",
        "",
        "DATA (use only these numbers — do not add outside knowledge):",
        f"  Total registered voters: {total}",
        f"  Republican-leaning: {party['r_lean_pct']}%  (Pure R {party['pure_r_pct']}% + behaviorally-lapsed R)",
        f"  Democratic-leaning: {party['d_lean_pct']}%  (Pure D {party['pure_d_pct']}% + behaviorally-lapsed D)",
        f"  Unaffiliated / no primary history: {party['unc_pct']}%",
        f"  Net lean: {lean_str}",
    ]

    if 'generations' in metrics:
        gen = metrics['generations']
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
        "",
        f"Data as of: {metrics['data_as_of']}",
        "",
        "Write only the 2-3 sentence summary. No headers, no bullet points, no outside context.",
    ]
    return '\n'.join(lines)


def fake_narrative(metrics: dict) -> str:
    county = metrics['county']
    total  = f"{metrics['total_voters']:,}"
    p = metrics['party']
    net = p['net_lean']
    lean_word = 'Democratic' if net > 0 else 'Republican'
    parts = [
        f"{county} has {total} registered voters, with {p['unc_pct']}% unaffiliated or lacking primary history.",
        f"Republican-leaning voters make up {p['r_lean_pct']}% of registrants and Democratic-leaning voters account for {p['d_lean_pct']}%, giving the county a net {lean_word} lean of {abs(net):.1f} percentage points.",
    ]
    if 'generations' in metrics:
        top = max(metrics['generations'], key=metrics['generations'].get)
        parts.append(f"{top} are the largest generational cohort at {metrics['generations'][top]}% of registrants.")
    return ' '.join(parts)


def generate_narrative(client, metrics: dict, dry_run: bool, fake: bool):
    prompt = build_user_prompt(metrics)
    if dry_run:
        print(f"\n{'='*60}")
        print(f"PROMPT for {metrics['county']}:")
        print(prompt)
        return None
    if fake or client is None:
        return fake_narrative(metrics)

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


def write_narrative_json(slug: str, metrics: dict, narrative: str, model_label: str) -> None:
    out = {
        'geography':         'county',
        'jurisdiction_name': metrics['county'],
        'updated':           metrics['data_as_of'],
        'generated_by':      model_label,
        'prompt_version':    PROMPT_VERSION,
        'narrative':         narrative,
    }
    path = DATA_DIR / f'{slug}_narrative.json'
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    logging.info('Wrote %s', path.name)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('counties', nargs='*', help='County names to process (default: all)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--fake', action='store_true', help='Skip API; emit deterministic templated narrative')
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    all_counties = manifest.get('processedCounties') or manifest.get('counties') or []

    if args.counties:
        target = [c for c in all_counties if c in args.counties]
        missing = set(args.counties) - set(target)
        if missing:
            logging.warning('Not found in manifest: %s', missing)
    else:
        target = all_counties

    client = None
    if not args.dry_run and not args.fake:
        if anthropic is None:
            logging.warning('anthropic SDK not installed — falling back to --fake mode')
            args.fake = True
        else:
            key = os.environ.get('ANTHROPIC_API_KEY')
            if not key:
                logging.warning('ANTHROPIC_API_KEY not set — falling back to --fake mode')
                args.fake = True
            else:
                client = anthropic.Anthropic(api_key=key)

    model_label = MODEL if (client is not None) else 'fake-template-v1'

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

        narrative = generate_narrative(client, metrics, args.dry_run, args.fake)

        if narrative:
            write_narrative_json(slug, metrics, narrative, model_label)
            ok += 1
            if client is not None:
                time.sleep(RATE_LIMIT_SEC)
        elif not args.dry_run:
            failed += 1

    if not args.dry_run:
        logging.info('Done — ok:%d skipped:%d failed:%d', ok, skipped, failed)


if __name__ == '__main__':
    main()
