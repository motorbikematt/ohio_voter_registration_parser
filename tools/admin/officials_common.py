"""officials_common.py -- shared helpers for the officials/captains/candidates pipeline.

Single home for the load-bearing logic the three producer chains share, so the
precinct join-key resolver and name normalizer exist exactly once (CLAUDE.md
section 5, single-resolver hygiene -- a duplicated copy is how the postal-city
bug survived weeks).

Exposes:
  * COUNTY_NUMBER / COUNTY_SLUG    -- county code <-> slug lookup
  * load_precinct_crosswalk(slug)  -- ballot number -> exact parquet PRECINCT_NAME
  * normalize_name(raw)            -- "HUGH M. QUILL, JR" -> "Hugh M. Quill, Jr"
  * name_from_parts(...)           -- assemble a display name from SOS CSV columns
  * atomic_write_json(path, obj)   -- .tmp -> replace, never a partial file

The crosswalk is grounded in the enriched parquet: every normalized PRECINCT_NAME
is validated against the distinct PRECINCT_NAME values the pipeline actually
emits for that county, and a label that fails to resolve is a loud failure, not
a silent skip (CLAUDE.md section 5).
"""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# tools/admin/ -> tools/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
PRECINCT_KEYS_DIR = ROOT / "local" / "source" / "precinct_keys"
ENRICHED_PARQUET = ROOT / "local" / "source" / "parquet_enriched" / "enriched_voters.parquet"

# County slug <-> SWVF COUNTY_NUMBER (string, as stored in the parquet).
COUNTY_NUMBER: dict[str, str] = {
    "montgomery": "57",
}
COUNTY_SLUG: dict[str, str] = {v: k for k, v in COUNTY_NUMBER.items()}


# -- precinct crosswalk --------------------------------------------------------

@dataclass
class PrecinctCrosswalk:
    """Resolves a 4-digit BoE ballot number to an exact parquet PRECINCT_NAME."""

    county_slug: str
    ballot_to_name: dict[str, str]                 # "0010" -> "BROOKVILLE-A"
    names: set[str] = field(default_factory=set)   # all valid PRECINCT_NAME values

    def resolve(self, ballot_number: str) -> str | None:
        """Return the PRECINCT_NAME for a ballot number, or None if unknown."""
        return self.ballot_to_name.get(_pad_ballot(ballot_number))

    @property
    def all_ballots(self) -> list[str]:
        return sorted(self.ballot_to_name)


def _pad_ballot(ballot: str) -> str:
    """BoE ballot numbers are 4-digit, zero-padded ('0010', '0650')."""
    return ballot.strip().zfill(4)


def _label_variants(label: str) -> list[str]:
    """Candidate PRECINCT_NAME spellings for a montgomery_precincts label.

    A label is '0010 BROOKVILLE A' / '0560 DAYTON 3-E'. The parquet sometimes
    dash-joins the sub token ('BROOKVILLE-A', 'ENGLEWOOD-I') and sometimes keeps
    a space ('BUTLER TWP A', 'DAYTON 3-E', 'MIAMISBURG 2-B'); the split is not a
    clean rule, so we generate the plausible spellings and let the parquet name
    set decide which is real (validated 381/381 for Montgomery).
    """
    body = re.sub(r"^\d+\s+", "", label).strip()
    body = re.sub(r"\s+", " ", body)
    dash_last = re.sub(r"\s+(\S+)$", r"-\1", body)   # join only the final token
    dash_all = body.replace(" ", "-")
    # ordered, de-duplicated
    out: list[str] = []
    for v in (body, dash_last, dash_all):
        if v not in out:
            out.append(v)
    return out


def load_parquet_precinct_names(county_slug: str) -> set[str]:
    """Distinct PRECINCT_NAME values the pipeline emits for a county (authority)."""
    import polars as pl  # local import: only the crosswalk needs polars

    number = COUNTY_NUMBER[county_slug]
    df = (
        pl.scan_parquet(ENRICHED_PARQUET)
        .filter(pl.col("COUNTY_NUMBER") == number)
        .select("PRECINCT_NAME")
        .unique()
        .collect()
    )
    return set(df["PRECINCT_NAME"].to_list())


def load_precinct_crosswalk(county_slug: str, validate: bool = True) -> PrecinctCrosswalk:
    """Build the ballot-number -> PRECINCT_NAME crosswalk for a county.

    Source: local/source/precinct_keys/{slug}_precincts.csv (ballot number in the
    'precinct_code' column, '0010 BROOKVILLE A' in 'precinct_label').
    With validate=True every resolved name is checked against the parquet name
    set and an unresolved label raises -- the crosswalk is load-bearing, so a
    miss must be loud (CLAUDE.md section 5).
    """
    csv_path = PRECINCT_KEYS_DIR / f"{county_slug}_precincts.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"precinct key file not found: {csv_path}")

    valid_names = load_parquet_precinct_names(county_slug) if validate else None

    ballot_to_name: dict[str, str] = {}
    unresolved: list[str] = []
    for row in csv.DictReader(csv_path.open(encoding="utf-8")):
        ballot = _pad_ballot(row["precinct_code"])
        label = row["precinct_label"]
        chosen = None
        for variant in _label_variants(label):
            if valid_names is None or variant in valid_names:
                chosen = variant
                break
        if chosen is None:
            unresolved.append(f"{ballot} {label!r}")
            continue
        ballot_to_name[ballot] = chosen

    if unresolved:
        raise ValueError(
            f"{len(unresolved)} precinct labels did not resolve to a parquet "
            f"PRECINCT_NAME for {county_slug}: {unresolved[:10]}"
        )

    names = set(ballot_to_name.values())
    if validate and valid_names is not None and names != valid_names:
        missing = sorted(valid_names - names)
        extra = sorted(names - valid_names)
        raise ValueError(
            f"crosswalk does not cover the parquet name set for {county_slug}: "
            f"missing={missing[:5]} extra={extra[:5]}"
        )

    return PrecinctCrosswalk(county_slug=county_slug, ballot_to_name=ballot_to_name, names=names)


# -- name normalization --------------------------------------------------------

_ROMAN = {"II", "III", "IV", "V", "VI", "VII"}
_SUFFIX_LOWER = {"JR", "SR"}


def _title_token(tok: str) -> str:
    """Title-case one whitespace token, preserving initials and name suffixes."""
    # Separate a trailing comma (", JR") so it survives re-casing.
    trailing = ""
    if tok.endswith(","):
        tok, trailing = tok[:-1], ","
    if not tok:
        return trailing

    bare = tok.rstrip(".").upper()
    if bare == "AND":                                # joint ticket ("X and Y")
        return "and" + trailing
    if bare in _ROMAN:
        return bare + trailing
    if bare in _SUFFIX_LOWER:
        return bare.capitalize() + ("." if tok.endswith(".") else "") + trailing
    if re.fullmatch(r"(?:[A-Z]\.){2,}", tok.upper()):  # joined initials, e.g. "S.H."
        return tok.upper() + trailing
    if re.fullmatch(r"[A-Z]\.?", tok.upper()):       # single-letter initial
        return tok.upper() + trailing
    if "-" in tok:                                    # hyphenated given/surname
        return "-".join(_title_token(p) for p in tok.split("-")) + trailing

    low = tok.lower()
    if low.startswith("mc") and len(low) > 2:
        return "Mc" + low[2:].capitalize() + trailing
    if low.startswith("o'") and len(low) > 2:
        return "O'" + low[2:].capitalize() + trailing
    return tok.capitalize() + trailing


def normalize_name(raw: str) -> str:
    """Display-case a raw all-caps BoE name.

    'HUGH M. QUILL, JR' -> 'Hugh M. Quill, Jr'; 'WILLIAM N. DAVIS, II' ->
    'William N. Davis, II'. Names in the BoE filing reports are already in
    first-last order, so this only re-cases -- it does NOT invert 'LAST, FIRST'
    (the commas in real data are suffix commas, and inverting would corrupt them).
    """
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return raw
    return " ".join(_title_token(t) for t in raw.split(" ")).strip()


def name_from_parts(first: str, middle: str, last: str, suffix: str = "") -> str:
    """Assemble a normalized display name from discrete SOS CSV columns."""
    parts = [p.strip() for p in (first, middle, last, suffix) if p and p.strip()]
    return normalize_name(" ".join(parts))


# -- io ------------------------------------------------------------------------

def atomic_write_json(path: Path, obj: object) -> int:
    """Write JSON atomically (.tmp -> os.replace); return bytes written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return len(text.encode("utf-8"))
