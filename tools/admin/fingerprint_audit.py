#!/usr/bin/env python
"""Voter record fingerprint audit (Handoff 10).

Traces per-voter SOS_VOTERID continuity across raw SWVF snapshots to
distinguish lawful roll-off from lost ballot history, with a partisan-skew
cross-check. Works directly against the raw gzipped snapshot files in
local/source/snapshots/ -- it never touches the pipeline, its caches, or
docs/. Read-only against sources; all output lands under
local/working/fingerprint_audit/.

Subcommands
-----------
extract      One compact parquet extract per snapshot (id, county, DOB,
             status, names, all election-history columns, plus a
             window-independent ballot-history party derivation).
noise-floor  Handoff 8B section 4's 04-25 -> 04-30 join on SOS_VOTERID.
             NOTE: 2026-04-30/voterfile.csv is a county-format BoE export,
             not a SWVF extract, so the join is county-scoped (the tool
             identifies the county by ID overlap and says so in the result).
compare      Pairwise fingerprint comparison of two snapshot extracts:
             classification counts (clean / mark lost / mark gained /
             value changed / DOB mismatch / present-in-one-only), per-column
             loss and gain counts, dual residual reporting (VOTER_STATUS =
             CONFIRMATION trusted vs. not), ballot-history party cross-tab,
             county concentration. Writes a JSON result per pair and a
             parquet of anomalous rows.
timeline     For the union of anomalous voter IDs across all pair results,
             dump each voter's value in the affected election columns across
             every extracted snapshot (classifies transient vs. persistent).
rewrite-guard
             Roll up every pair_*.json + anomalies_*.parquet result on disk
             into a (county, election column) allow/deny table: any
             combination showing a value-changed volume that cannot be
             explained by ordinary per-voter correction (Handoff 10 section
             5b's Cuyahoga finding -- history columns are county-mutable
             post-certification) is flagged UNDER_REWRITE. Written for 8B:
             any Axis B trend built on ballot-history columns must consult
             this table first and exclude or flag rows in a flagged
             (county, column) pair, or a BoE remediation batch reads as
             voter behavior. Consumes existing results only -- it does not
             re-run extract/compare.

Identity-key semantics: see local/context/scope/sos_voterid_identity_semantics.md
(Rules 1-3). SOS_VOTERID is a best-effort point-in-time identifier, not an
immutable key; this tool exists to measure how far that assumption bends.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from pipeline.voter_data_cleaner import ELEC_RE, parse_election_meta  # noqa: E402

SNAP_DIR = _ROOT / 'local' / 'source' / 'snapshots'
OUT_DIR = _ROOT / 'local' / 'working' / 'fingerprint_audit'
EXTRACT_DIR = OUT_DIR / 'extracts'
RESULT_DIR = OUT_DIR / 'results'

SPLIT_FILES = ('SWVF_1_22.txt.gz', 'SWVF_23_44.txt.gz',
               'SWVF_45_66.txt.gz', 'SWVF_67_88.txt.gz')
STATIC_KEEP = ('SOS_VOTERID', 'COUNTY_NUMBER', 'DATE_OF_BIRTH',
               'VOTER_STATUS', 'LAST_NAME', 'FIRST_NAME')

# The six snapshots with the PRIMARY-05/05/2026 column allocated (Handoff 10
# section 5) plus 04-25, which the noise-floor join needs.
DEFAULT_SNAPSHOTS = ('2026-04-25', '2026-05-09', '2026-06-20', '2026-06-27',
                     '2026-07-04', '2026-07-11', '2026-07-18')
FINGERPRINT_SNAPSHOTS = DEFAULT_SNAPSHOTS[1:]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _atomic_parquet(df: pl.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    df.write_parquet(tmp)
    tmp.replace(path)


def _atomic_json(obj, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8')
    tmp.replace(path)


def _read_header(path: Path, gzipped: bool) -> list[str]:
    opener = gzip.open if gzipped else open
    with opener(path, 'rt', encoding='utf-8', errors='strict') as fh:
        line = fh.readline()
    return [c.strip().strip('"') for c in line.rstrip('\r\n').split(',')]


def _election_cols(cols: list[str]) -> list[str]:
    ecols = [c for c in cols if ELEC_RE.match(c)]
    ecols.sort(key=lambda c: parse_election_meta(c)[0])
    return ecols


def _filled(col: str) -> pl.Expr:
    """Blank cells arrive as '' or null depending on quoting (CLAUDE.md sec 4);
    extracts normalize '' -> null, so filled == not-null."""
    return pl.col(col).is_not_null()


# --------------------------------------------------------------------------
# extract
# --------------------------------------------------------------------------

def extract_snapshot(snap: str, force: bool = False) -> Path:
    out_path = EXTRACT_DIR / f'{snap}.parquet'
    sidecar = EXTRACT_DIR / f'{snap}.json'
    if out_path.exists() and sidecar.exists() and not force:
        print(f'[extract] {snap}: extract exists, skipping (use --force to redo)')
        return out_path

    snap_dir = SNAP_DIR / snap
    if not snap_dir.is_dir():
        raise FileNotFoundError(f'snapshot dir missing: {snap_dir}')

    header = _read_header(snap_dir / SPLIT_FILES[0], gzipped=True)
    ecols = _election_cols(header)
    if not ecols:
        raise ValueError(f'{snap}: no election columns matched ELEC_RE')
    keep = [c for c in STATIC_KEEP if c in header] + ecols
    missing_static = [c for c in STATIC_KEEP if c not in header]
    if missing_static:
        raise ValueError(f'{snap}: missing static columns {missing_static}')

    frames = []
    per_file = {}
    src_meta = {}
    for fn in SPLIT_FILES:
        p = snap_dir / fn
        if not p.exists():
            raise FileNotFoundError(f'{snap}: missing split file {fn}')
        raw = gzip.decompress(p.read_bytes())
        # utf8-lossy: county rows with non-UTF-8 bytes exist (encoding census,
        # DATA_QUALITY.md); replacement chars can only land in name fields,
        # which are corroboration-only in this audit.
        df = pl.read_csv(io.BytesIO(raw), infer_schema_length=0, columns=keep,
                         encoding='utf8-lossy')
        if set(df.columns) != set(keep):
            raise ValueError(f'{snap}/{fn}: column mismatch vs first split file')
        df = df.select(keep)  # read_csv returns file order; normalize
        per_file[fn] = df.height
        src_meta[fn] = {'bytes': p.stat().st_size,
                        'mtime': datetime.fromtimestamp(p.stat().st_mtime).isoformat()}
        frames.append(df)
    df = pl.concat(frames)
    del frames

    # Normalize '' -> null in election cells so filled == not-null everywhere.
    df = df.with_columns([
        pl.when(pl.col(c) == '').then(None).otherwise(pl.col(c)).alias(c)
        for c in ecols
    ])

    n = df.height
    bad_ids = df.filter(pl.col('SOS_VOTERID').is_null() |
                        (pl.col('SOS_VOTERID') == '')).height
    if bad_ids:
        raise ValueError(f'{snap}: {bad_ids} rows with null/empty SOS_VOTERID')
    dup_ids = n - df.get_column('SOS_VOTERID').n_unique()

    # Window-independent party from actual partisan primary ballots across ALL
    # PRIMARY-* columns (Handoff 10 section 7). Deliberately NOT the enriched
    # cache's PARTY_LABEL and NOT PARTY_AFFILIATION -- both are exposed to the
    # R.C. 3513.19 calendar window (8B section 5). Codes other than D/R
    # (X non-partisan, L and other minor-party codes -- DATA_QUALITY.md row
    # X-PRIMARIES-MINORPARTY-CONFLATION) do not count toward either party.
    prim_cols = [c for c in ecols if c.startswith('PRIMARY-')]
    df = df.with_columns([
        pl.sum_horizontal([(pl.col(c) == 'D').fill_null(False).cast(pl.UInt32)
                           for c in prim_cols]).alias('d_primaries'),
        pl.sum_horizontal([(pl.col(c) == 'R').fill_null(False).cast(pl.UInt32)
                           for c in prim_cols]).alias('r_primaries'),
    ])
    df = df.with_columns(
        pl.when((pl.col('d_primaries') > 0) & (pl.col('r_primaries') == 0))
          .then(pl.lit('D'))
          .when((pl.col('r_primaries') > 0) & (pl.col('d_primaries') == 0))
          .then(pl.lit('R'))
          .when((pl.col('d_primaries') > 0) & (pl.col('r_primaries') > 0))
          .then(pl.lit('MIXED'))
          .otherwise(pl.lit('NONE'))
          .alias('ballot_party')
    )

    filled_counts = dict(zip(
        ecols,
        df.select([_filled(c).sum().alias(c) for c in ecols]).row(0),
    ))
    county_party = (
        df.group_by(['COUNTY_NUMBER', 'ballot_party']).len()
          .sort(['COUNTY_NUMBER', 'ballot_party'])
          .to_dicts()
    )
    status_counts = dict(
        df.group_by('VOTER_STATUS').len().iter_rows()
    )

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(df, out_path)
    _atomic_json({
        'snapshot': snap,
        'generated_utc': _utc_now(),
        'rows': n,
        'rows_per_file': per_file,
        'source_files': src_meta,
        'duplicate_sos_voterid_rows': dup_ids,
        'election_cols': ecols,
        'filled_counts': filled_counts,
        'status_counts': status_counts,
        'county_party_baseline': county_party,
    }, sidecar)
    print(f'[extract] {snap}: {n} rows, {len(ecols)} election cols, '
          f'{dup_ids} duplicate-ID rows -> {out_path.name}')
    return out_path


# --------------------------------------------------------------------------
# noise-floor (8B section 4): 2026-04-25 vs 2026-04-30
# --------------------------------------------------------------------------

def cmd_noise_floor() -> None:
    """Join 04-25 (SWVF) to 04-30 (county-format voterfile.csv) on SOS_VOTERID.

    The 04-30 file is NOT a statewide SWVF export: it is a single county's BoE
    export (SOSIDNUM / CNTYIDNUM / BIRTHYEAR, county-style election columns).
    The statewide join 8B section 4 scoped is therefore impossible; this runs
    the closest defensible substitute: identify the county by ID overlap, then
    join that county's 04-25 rows against the file. Labeled 'identifier-drift
    floor, freeze conditions, county-scoped' in the result.
    """
    a_path = EXTRACT_DIR / '2026-04-25.parquet'
    if not a_path.exists():
        raise FileNotFoundError('run: fingerprint_audit.py extract 2026-04-25 first')
    csv_path = SNAP_DIR / '2026-04-30' / 'voterfile.csv'
    if not csv_path.exists():
        raise FileNotFoundError(f'missing {csv_path}')

    a = pl.read_parquet(a_path, columns=['SOS_VOTERID', 'COUNTY_NUMBER',
                                         'DATE_OF_BIRTH', 'VOTER_STATUS'])
    b = pl.read_csv(csv_path, infer_schema_length=0,
                    columns=['SOSIDNUM', 'CNTYIDNUM', 'BIRTHYEAR', 'VOTERSTAT'])
    b_rows = b.height
    b_bad = b.filter(pl.col('SOSIDNUM').is_null() | (pl.col('SOSIDNUM') == '')).height
    b_dup = b_rows - b.get_column('SOSIDNUM').n_unique()

    matched_all = a.join(b, left_on='SOS_VOTERID', right_on='SOSIDNUM', how='inner')
    county_dist = (matched_all.group_by('COUNTY_NUMBER').len()
                   .sort('len', descending=True))
    top_county, top_n = county_dist.row(0)[0], county_dist.row(0)[1]
    county_share = top_n / matched_all.height if matched_all.height else 0.0

    a_county = a.filter(pl.col('COUNTY_NUMBER') == top_county)
    j = a_county.join(b, left_on='SOS_VOTERID', right_on='SOSIDNUM', how='full',
                      coalesce=True)
    in_a = pl.col('COUNTY_NUMBER').is_not_null()
    in_b = pl.col('CNTYIDNUM').is_not_null()
    matched = j.filter(in_a & in_b).height
    left_only = j.filter(in_a & ~in_b)
    right_only = j.filter(~in_a & in_b).height

    # Birth-year corroboration on matched rows (04-30 carries only BIRTHYEAR).
    by = (a_county.join(b, left_on='SOS_VOTERID', right_on='SOSIDNUM', how='inner')
          .with_columns(pl.col('DATE_OF_BIRTH').str.slice(0, 4).alias('_yr'))
          .filter(pl.col('BIRTHYEAR').is_not_null() & (pl.col('BIRTHYEAR') != '')))
    by_mismatch = by.filter(pl.col('_yr') != pl.col('BIRTHYEAR')).height

    left_status = dict(left_only.group_by('VOTER_STATUS').len().iter_rows())
    b_status = dict(b.group_by('VOTERSTAT').len().iter_rows())

    result = {
        'label': 'identifier-drift floor, freeze conditions, county-scoped',
        'generated_utc': _utc_now(),
        'caveat': ('2026-04-30/voterfile.csv is a county-format BoE export '
                   '(300k rows, SOSIDNUM/CNTYIDNUM/BIRTHYEAR schema), not a '
                   'statewide SWVF file. The statewide join 8B sec 4 scoped '
                   'cannot be run from this snapshot; this is the county-scoped '
                   'substitute. Do not generalize beyond this county or outside '
                   'the 90-day freeze (52 U.S.C.A. 20507(c)(2)(A)).'),
        'county_number': top_county,
        'matched_id_share_in_top_county': round(county_share, 6),
        'rows_04_25_statewide': a.height,
        'rows_04_25_county': a_county.height,
        'rows_04_30_file': b_rows,
        'rows_04_30_bad_id': b_bad,
        'rows_04_30_duplicate_id': b_dup,
        'matched': matched,
        'left_only_in_04_25_county_not_in_04_30': left_only.height,
        'right_only_in_04_30_not_in_04_25_county': right_only,
        'left_only_by_voter_status': left_status,
        'birthyear_checked': by.height,
        'birthyear_mismatch_on_matched': by_mismatch,
        'voterstat_values_04_30': b_status,
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_json(result, RESULT_DIR / 'noise_floor_04-25_04-30.json')
    print(json.dumps(result, indent=2, sort_keys=True))


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------

def _load_extract(snap: str) -> tuple[pl.DataFrame, dict]:
    p = EXTRACT_DIR / f'{snap}.parquet'
    s = EXTRACT_DIR / f'{snap}.json'
    if not p.exists() or not s.exists():
        raise FileNotFoundError(f'extract missing for {snap}; run extract first')
    return pl.read_parquet(p), json.loads(s.read_text(encoding='utf-8'))


def _party_dist(df: pl.DataFrame, col: str = 'ballot_party') -> dict:
    return dict(df.group_by(col).len().iter_rows())


def cmd_compare(snap_a: str, snap_b: str) -> None:
    if snap_a >= snap_b:
        raise ValueError('pass snapshots chronologically: earlier later')
    da, ma = _load_extract(snap_a)
    db, mb = _load_extract(snap_b)
    ecols_a, ecols_b = ma['election_cols'], mb['election_cols']
    shared = [c for c in ecols_a if c in set(ecols_b)]
    only_a = [c for c in ecols_a if c not in set(ecols_b)]
    only_b = [c for c in ecols_b if c not in set(ecols_a)]

    # Duplicate-ID rows (county-move duplicates, 8B sec 4 / Directive 2026-19
    # VI.B) would multiply under a join -- bucket them out and count them.
    dup_a = da.filter(pl.col('SOS_VOTERID').is_duplicated())
    dup_b = db.filter(pl.col('SOS_VOTERID').is_duplicated())
    da_u = da.filter(~pl.col('SOS_VOTERID').is_duplicated())
    db_u = db.filter(~pl.col('SOS_VOTERID').is_duplicated())

    keep_a = ['SOS_VOTERID', 'COUNTY_NUMBER', 'DATE_OF_BIRTH', 'VOTER_STATUS',
              'ballot_party', 'd_primaries', 'r_primaries'] + shared
    keep_b = ['SOS_VOTERID', 'COUNTY_NUMBER', 'DATE_OF_BIRTH', 'VOTER_STATUS',
              'ballot_party'] + shared
    j = (da_u.select(keep_a)
         .with_columns(pl.lit(True).alias('_in_a'))
         .join(db_u.select(keep_b).with_columns(pl.lit(True).alias('_in_b')),
               on='SOS_VOTERID', how='full', suffix='_b', coalesce=True)
         .with_columns([pl.col('_in_a').fill_null(False),
                        pl.col('_in_b').fill_null(False)]))

    left_only = j.filter(pl.col('_in_a') & ~pl.col('_in_b'))
    right_only = j.filter(~pl.col('_in_a') & pl.col('_in_b'))
    m = j.filter(pl.col('_in_a') & pl.col('_in_b'))
    del j

    # Per-column loss/gain/change over matched rows. Every shared column's
    # election closed before snap_a (columns are allocated only after their
    # election), so under Handoff 10 sec 5 trust rank 1 a lost mark is never a
    # life event. Gains on recently closed elections are the late history
    # upload (8B sec 6, two statutory clocks) -- reported per column so the
    # reader can see exactly which columns the gains sit in.
    lost_e = {c: (_filled(c) & pl.col(f'{c}_b').is_null()) for c in shared}
    gain_e = {c: (pl.col(c).is_null() & pl.col(f'{c}_b').is_not_null())
              for c in shared}
    chg_e = {c: (_filled(c) & pl.col(f'{c}_b').is_not_null() &
                 (pl.col(c) != pl.col(f'{c}_b'))) for c in shared}

    per_col = m.select(
        [lost_e[c].sum().alias(f'L|{c}') for c in shared] +
        [gain_e[c].sum().alias(f'G|{c}') for c in shared] +
        [chg_e[c].sum().alias(f'C|{c}') for c in shared]
    ).row(0)
    ncol = len(shared)
    col_stats = {
        c: {'lost': per_col[i], 'gained': per_col[ncol + i],
            'changed': per_col[2 * ncol + i]}
        for i, c in enumerate(shared)
        if per_col[i] or per_col[ncol + i] or per_col[2 * ncol + i]
    }

    m = m.with_columns([
        pl.any_horizontal(list(lost_e.values())).alias('any_lost'),
        pl.any_horizontal(list(gain_e.values())).alias('any_gained'),
        pl.any_horizontal(list(chg_e.values())).alias('any_changed'),
        (pl.col('DATE_OF_BIRTH') != pl.col('DATE_OF_BIRTH_b')).alias('dob_mismatch'),
    ])

    counts = {
        'matched': m.height,
        'clean': m.filter(~pl.col('any_lost') & ~pl.col('any_gained') &
                          ~pl.col('any_changed') & ~pl.col('dob_mismatch')).height,
        'mark_lost': m.filter(pl.col('any_lost')).height,
        'mark_gained': m.filter(pl.col('any_gained')).height,
        'value_changed': m.filter(pl.col('any_changed')).height,
        'dob_mismatch': m.filter(pl.col('dob_mismatch')).height,
        'left_only': left_only.height,
        'right_only': right_only.height,
        'dup_id_rows_a': dup_a.height,
        'dup_id_rows_b': dup_b.height,
    }

    # Anomalies: mark lost, value changed, or DOB mismatch (mark gained alone
    # is dominated by the lawful late-history upload; it stays in col_stats).
    anom = m.filter(pl.col('any_lost') | pl.col('any_changed') |
                    pl.col('dob_mismatch'))
    anom_cols = ['SOS_VOTERID', 'COUNTY_NUMBER', 'COUNTY_NUMBER_b',
                 'DATE_OF_BIRTH', 'DATE_OF_BIRTH_b', 'VOTER_STATUS',
                 'VOTER_STATUS_b', 'ballot_party', 'd_primaries', 'r_primaries',
                 'any_lost', 'any_gained', 'any_changed', 'dob_mismatch']
    anom_out = anom.select(anom_cols)
    if anom.height and anom.height <= 200_000:
        detail = []
        for c in shared:
            sub = anom.filter(lost_e[c] | chg_e[c]).select('SOS_VOTERID')
            if sub.height:
                detail.append(sub.with_columns(pl.lit(c).alias('col'),
                                               pl.lit('lost_or_changed').alias('kind')))
        if detail:
            det = pl.concat(detail).group_by('SOS_VOTERID').agg(
                pl.col('col').sort().str.join(';').alias('affected_cols'))
            anom_out = anom_out.join(det, on='SOS_VOTERID', how='left')

    # Dual residual reporting (Handoff 10 sec 6): CONFIRMATION trusted vs not.
    lost = m.filter(pl.col('any_lost'))
    lost_conf = lost.filter(pl.col('VOTER_STATUS_b') == 'CONFIRMATION')
    residual = {
        'mark_lost_total': lost.height,
        'mark_lost_status_b_confirmation': lost_conf.height,
        'residual_confirmation_trusted': lost.height - lost_conf.height,
        'residual_confirmation_not_trusted': lost.height,
        'gap': lost_conf.height,
    }

    # Party cross-tabs (ballot-history party, window-independent by
    # construction). Rates, not raw counts, per Handoff 10 sec 7.
    xtab = {
        'baseline_statewide': _party_dist(da_u),
        'mark_lost': _party_dist(lost),
        'mark_lost_confirmation_trusted':
            _party_dist(lost.filter(pl.col('VOTER_STATUS_b') != 'CONFIRMATION')),
        'left_only': _party_dist(left_only),
        'left_only_by_status_a':
            dict(left_only.group_by('VOTER_STATUS').len().iter_rows()),
        'dob_mismatch': _party_dist(m.filter(pl.col('dob_mismatch'))),
    }
    county_conc = {
        'mark_lost_by_county':
            dict(lost.group_by('COUNTY_NUMBER').len().iter_rows()),
        'left_only_by_county':
            dict(left_only.group_by('COUNTY_NUMBER').len().iter_rows()),
    }

    pair = f'{snap_a}_{snap_b}'
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(anom_out, RESULT_DIR / f'anomalies_{pair}.parquet')
    result = {
        'pair': [snap_a, snap_b],
        'generated_utc': _utc_now(),
        'rows_a': da.height, 'rows_b': db.height,
        'shared_election_cols': len(shared),
        'cols_only_in_a': only_a, 'cols_only_in_b': only_b,
        'counts': counts,
        'residual_dual_report': residual,
        'per_column_stats_nonzero': col_stats,
        'party_crosstab': xtab,
        'county_concentration': county_conc,
        'anomalies_parquet': f'anomalies_{pair}.parquet',
    }
    _atomic_json(result, RESULT_DIR / f'pair_{pair}.json')
    print(f'[compare] {pair}: matched={counts["matched"]} '
          f'lost={counts["mark_lost"]} gained={counts["mark_gained"]} '
          f'changed={counts["value_changed"]} dob={counts["dob_mismatch"]} '
          f'left_only={counts["left_only"]} right_only={counts["right_only"]}')


# --------------------------------------------------------------------------
# timeline
# --------------------------------------------------------------------------

def cmd_timeline(snapshots: list[str]) -> None:
    """Trace anomalous voters across all snapshots: transient vs persistent."""
    ids = set()
    affected_cols = set()
    for p in sorted(RESULT_DIR.glob('anomalies_*.parquet')):
        d = pl.read_parquet(p)
        d = d.filter(pl.col('any_lost') | pl.col('any_changed') |
                     pl.col('dob_mismatch'))
        ids.update(d.get_column('SOS_VOTERID').to_list())
        if 'affected_cols' in d.columns:
            for s in d.get_column('affected_cols').drop_nulls().to_list():
                affected_cols.update(s.split(';'))
    if not ids:
        print('[timeline] no anomalous IDs found in results')
        return
    cols = sorted(affected_cols, key=lambda c: parse_election_meta(c)[0])
    id_list = sorted(ids)
    frames = []
    for snap in snapshots:
        df, meta = _load_extract(snap)
        have = [c for c in cols if c in df.columns]
        sub = (df.filter(pl.col('SOS_VOTERID').is_in(id_list))
               .select(['SOS_VOTERID', 'COUNTY_NUMBER', 'VOTER_STATUS',
                        'DATE_OF_BIRTH', 'ballot_party'] + have)
               .with_columns(pl.lit(snap).alias('snapshot')))
        frames.append(sub)
    tl = pl.concat(frames, how='diagonal').sort(['SOS_VOTERID', 'snapshot'])
    _atomic_parquet(tl, RESULT_DIR / 'anomaly_timelines.parquet')
    print(f'[timeline] {len(id_list)} anomalous voters x {len(snapshots)} '
          f'snapshots, {len(cols)} affected cols -> anomaly_timelines.parquet')


# --------------------------------------------------------------------------
# rewrite-guard
# --------------------------------------------------------------------------

# Ordinary per-voter correction runs at DOB-mismatch scale (Handoff 10 sec 4:
# 228 unique voters statewide across all 15 pairs, no county >= 40, diffuse).
# A (county, column) combination whose value-changed count clears this bar in
# a single pair is not routine data-entry correction at that scale -- it is
# either a batched county-side rewrite (the Cuyahoga case) or worth a human
# look before any Axis B trend touches that column for that county.
REWRITE_FLAG_THRESHOLD = 40


def cmd_rewrite_guard() -> None:
    """Build the (county, column) under-rewrite table from existing results.

    Reads every anomalies_*.parquet already on disk (produced by `compare`)
    and aggregates value-changed counts by (COUNTY_NUMBER, affected column).
    Does not re-run extract or compare -- if no results exist yet, run
    `compare` for the pairs you need first.
    """
    paths = sorted(RESULT_DIR.glob('anomalies_*.parquet'))
    if not paths:
        print('[rewrite-guard] no anomalies_*.parquet found; run `compare` first')
        return

    rows = []
    for p in paths:
        pair = p.stem.removeprefix('anomalies_')
        d = pl.read_parquet(p)
        if 'affected_cols' not in d.columns:
            # No lost/changed rows in this pair at all (compare only adds this
            # column when such rows exist) -- nothing to roll up, not an error.
            continue
        d = d.filter(pl.col('any_changed') & pl.col('affected_cols').is_not_null())
        if not d.height:
            continue
        exploded = (
            d.select(['SOS_VOTERID', 'COUNTY_NUMBER', 'affected_cols'])
             .with_columns(pl.col('affected_cols').str.split(';').alias('col'))
             .explode('col')
        )
        agg = (exploded.group_by(['COUNTY_NUMBER', 'col']).len()
               .rename({'len': 'changed_count'})
               .with_columns(pl.lit(pair).alias('pair')))
        rows.append(agg)

    if not rows:
        print('[rewrite-guard] no value-changed anomalies in any result on disk')
        return

    all_rows = pl.concat(rows)
    # Roll up to (county, column): worst single-pair count is the flag basis
    # -- a rewrite in flight shows up at full magnitude in whichever pair
    # spans its batch, diluted in pairs spanning more weeks either side.
    rollup = (all_rows.group_by(['COUNTY_NUMBER', 'col'])
              .agg(pl.col('changed_count').max().alias('max_pair_changed_count'),
                   pl.col('changed_count').sum().alias('sum_across_pairs'),
                   pl.col('pair').sort().alias('pairs_observed_in'))
              .sort('max_pair_changed_count', descending=True))
    rollup = rollup.with_columns(
        (pl.col('max_pair_changed_count') >= REWRITE_FLAG_THRESHOLD)
        .alias('under_rewrite')
    )

    flagged = rollup.filter(pl.col('under_rewrite'))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(rollup, OUT_DIR / 'rewrite_guard_table.parquet')
    summary = {
        'generated_utc': _utc_now(),
        'threshold': REWRITE_FLAG_THRESHOLD,
        'threshold_basis': ('Handoff 10 sec 4 DOB-mismatch scale: 228 unique '
                             'voters statewide across 15 pairs, no county >= 40, '
                             'diffuse -- used as the ordinary-correction ceiling'),
        'flagged_county_column_pairs': flagged.height,
        'flagged': flagged.select(
            ['COUNTY_NUMBER', 'col', 'max_pair_changed_count', 'sum_across_pairs']
        ).to_dicts(),
    }
    _atomic_json(summary, OUT_DIR / 'rewrite_guard_summary.json')
    print(f'[rewrite-guard] {rollup.height} (county, column) pairs with any '
          f'value-changed activity; {flagged.height} flagged UNDER_REWRITE '
          f'(threshold={REWRITE_FLAG_THRESHOLD}) -> rewrite_guard_table.parquet')
    for r in flagged.select(['COUNTY_NUMBER', 'col', 'max_pair_changed_count']).iter_rows():
        print(f'  UNDER_REWRITE county={r[0]} col={r[1]} max_changed={r[2]}')


def check_column_clean(county_number: str, column: str) -> bool:
    """Import-time helper for any future Axis B code: True if (county, column)
    is NOT flagged as under active rewrite in the last rewrite-guard run.
    Raises if the guard table hasn't been built yet -- fail loud, not silent,
    per CLAUDE.md's no-try/except-as-control-flow rule for pipeline code."""
    table = OUT_DIR / 'rewrite_guard_table.parquet'
    if not table.exists():
        raise FileNotFoundError(
            'rewrite_guard_table.parquet missing -- run '
            '`fingerprint_audit.py rewrite-guard` first')
    df = pl.read_parquet(table)
    hit = df.filter((pl.col('COUNTY_NUMBER') == county_number) &
                    (pl.col('col') == column) & pl.col('under_rewrite'))
    return hit.height == 0


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_ex = sub.add_parser('extract', help='build per-snapshot compact extracts')
    p_ex.add_argument('snapshots', nargs='*', default=[],
                      help='snapshot dir names; default: all seven usable')
    p_ex.add_argument('--force', action='store_true')

    sub.add_parser('noise-floor', help='8B sec 4 join, 04-25 vs 04-30')

    p_cp = sub.add_parser('compare', help='pairwise fingerprint comparison')
    p_cp.add_argument('snap_a')
    p_cp.add_argument('snap_b')

    p_tl = sub.add_parser('timeline', help='trace anomalous voters across snapshots')
    p_tl.add_argument('snapshots', nargs='*', default=[])

    sub.add_parser('rewrite-guard',
                    help='build (county, column) under-rewrite table from existing results')

    args = ap.parse_args()
    if args.cmd == 'extract':
        snaps = args.snapshots or list(DEFAULT_SNAPSHOTS)
        for s in snaps:
            extract_snapshot(s, force=args.force)
    elif args.cmd == 'noise-floor':
        cmd_noise_floor()
    elif args.cmd == 'compare':
        cmd_compare(args.snap_a, args.snap_b)
    elif args.cmd == 'timeline':
        cmd_timeline(args.snapshots or list(FINGERPRINT_SNAPSHOTS))
    elif args.cmd == 'rewrite-guard':
        cmd_rewrite_guard()


if __name__ == '__main__':
    main()
