"""ingest_elected_officials.py — populate serve/officials.json from electedofficials.csv.

Reads the Ohio SOS elected officials CSV (standard BoE format) and merges
TOWNSHIP, VILLAGE, LOCAL_SCHOOL_DISTRICT, CITY_SCHOOL_DISTRICT, and WARD
data into officials.json.
Existing district-level entries (CONGRESSIONAL_DISTRICT, STATE_SENATE_DISTRICT,
STATE_REPRESENTATIVE_DISTRICT) are preserved unchanged.

OFCDESC parsing extracts seat type:
  "CLAYTON CITY COUNCIL WARD 1"      -> ward=1, parquet key "CLAYTON WARD 1"
  "KETTERING CITY COUNCIL DISTRICT 2"-> ward=2, parquet key "KETTERING WARD 2"
  "HUBER HEIGHTS CITY COUNCIL AT LARGE" -> at_large
  "BUTLER TOWNSHIP TRUSTEE"          -> trustee (at-large)
  "BROOKVILLE CITY MAYOR"            -> mayor

Ward-keyed entries (keys match parquet WARD column) go into the WARD section.
At-large and mayor entries go into WARD under an "AT_LARGE" sub-key using the
pattern "{CITY} AT LARGE" and "{CITY} MAYOR" — these don't exist as parquet
WARD values but are needed so the frontend can display city-wide officeholders
alongside ward-specific reps.

Usage:
    python tools/admin/ingest_elected_officials.py                  # dry run
    python tools/admin/ingest_elected_officials.py --write          # apply changes
    python tools/admin/ingest_elected_officials.py --county 57      # filter by county in CSV
    python tools/admin/ingest_elected_officials.py --csv path/to/other.csv --write
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT           = Path(__file__).resolve().parent.parent.parent
DEFAULT_CSV    = ROOT / "local" / "source" / "electedofficials.csv"
OFFICIALS_JSON = ROOT / "serve" / "officials.json"

# ── DISTNAME normalization maps ───────────────────────────────────────────────

# CSV "CITY OF X" -> parquet WARD key prefix
# Parquet uses abbreviated forms in some cases.
CITY_PREFIX: dict[str, str] = {
    "CITY OF BROOKVILLE":   "BROOKVILLE",
    "CITY OF CENTERVILLE":  "CENTERVILLE",
    "CITY OF CLAYTON":      "CLAYTON",
    "CITY OF DAYTON":       "DAYTON",
    "CITY OF ENGLEWOOD":    "ENGLEWOOD",
    "CITY OF GERMANTOWN":   "GERMANTOWN",
    "CITY OF HUB HEIGHTS":  "HUBER HTS",      # parquet abbreviation
    "CITY OF KETTERING":    "KETTERING",
    "CITY OF MIAMISBURG":   "MIAMISBURG",
    "CITY OF MORAINE":      "MORAINE",
    "CITY OF OAKWOOD":      "OAKWOOD",
    "CITY OF RIVERSIDE":    "RIVERSIDE",
    "CITY OF SPRINGBORO":   "SPRINGBORO",
    "CITY OF TROTWOOD":     "TROTWOOD",
    "CITY OF UNION":        "UNION",
    "CITY OF VANDALIA":     "VANDALIA",
    "CITY OF W CARROLLTON": "W CARROLLTON",
}

# Township: CSV DISTNAME -> parquet TOWNSHIP value (exact match for Montgomery Co.)
TOWNSHIP_MAP: dict[str, str] = {
    "BUTLER TOWNSHIP":    "BUTLER TOWNSHIP",
    "CLAY TOWNSHIP":      "CLAY TOWNSHIP",
    "CLEARCREEK TOWNSHIP":"CLEARCREEK TOWNSHIP",
    "GERMAN TOWNSHIP":    "GERMAN TOWNSHIP",
    "HARRISON TOWNSHIP":  "HARRISON TOWNSHIP",
    "JACKSON TOWNSHIP":   "JACKSON TOWNSHIP",
    "JEFFERSON TOWNSHIP": "JEFFERSON TOWNSHIP",
    "MIAMI TOWNSHIP":     "MIAMI TOWNSHIP",
    "PERRY TOWNSHIP":     "PERRY TOWNSHIP",
    "WASHINGTON TOWNSHIP":"WASHINGTON TOWNSHIP",
}

# Village: CSV DISTNAME -> parquet VILLAGE value
VILLAGE_MAP: dict[str, str] = {
    "VILL OF FARMERSVILLE":  "FARMERSVILLE VILLAGE",
    "VILL 0F NEW LEBANON":   "NEW LEBANON VILLAGE",   # CSV has typo "0F"
    "VILL OF NEW LEBANON":   "NEW LEBANON VILLAGE",
    "VILL OF PHILLIPSBURG":  "PHILLIPSBURG VILLAGE",
    "VILLAGE OF VERONA":     "VERONA VILLAGE",
    "VILL OF CARLISLE":      "CARLISLE VILLAGE",       # not in parquet county 57; included for completeness
}

# School districts split into two mutually-exclusive parquet columns (handoff
# §3a). LOCAL_SCHOOL_DISTRICT and CITY_SCHOOL_DISTRICT are separate columns in
# enriched_voters.parquet; a voter is in at most one. Without the split, CSD
# board members land in LOCAL_SCHOOL_DISTRICT and the frontend join misses them.

# CSV DISTNAME -> parquet LOCAL_SCHOOL_DISTRICT value (rural/township "local" SDs)
LSD_MAP: dict[str, str] = {
    "BROOKVILLE LSD":      "BROOKVILLE LOCAL SD (MONTG)",
    "CARLISLE LSD":        "CARLISLE LOCAL SD (WARREN)",
    "JEFFERSON TWP LSD":   "JEFFERSON TOWNSHIP LOCAL SD (MONTG)",
    "MAD RIVER LSD":       "MAD RIVER LOCAL SD (MONTG)",
    "NEW LEBANON LSD":     "NEW LEBANON LOCAL SD (MONTG)",
    "NORTHRIDGE LSD":      "NORTHRIDGE LOCAL SD (MONTG)",
    "PREBLE-SHAWNEE LSD":  "PREBLE SHAWNEE LOCAL SD (PREBLE)",
    "TRI-COUNTY NORTH LSD":"TRI-COUNTY NORTH LSD (PREBLE)",
    "VALLEY VIEW LSD":     "VALLEY VIEW LOCAL SD (MONTG)",
}

# CSV DISTNAME -> parquet CITY_SCHOOL_DISTRICT value (municipal "city" SDs)
CSD_MAP: dict[str, str] = {
    "CENTERVILLE CSD":     "CENTERVILLE CITY SD",
    "DAYTON CSD":          "DAYTON CITY SD",
    "HUBER HEIGHTS CSD":   "HUBER HEIGHTS CITY SD",
    "KETTERING CSD":       "KETTERING CITY SD",
    "MIAMISBURG CSD":      "MIAMISBURG CITY SD",
    "NORTHMONT CSD":       "NORTHMONT CITY SD",
    "OAKWOOD CSD":         "OAKWOOD CITY SD",
    "SPRINGBORO CCSD":     "SPRINGBORO COMMUNITY CITY SD",
    "TROTWOOD-MADISON CSD":"TROTWOOD-MADISON CITY SD",
    "VANDALIA-BUTLER CSD": "VANDALIA-BUTLER CITY SD",
    "WEST CARROLLTON CSD": "WEST CARROLLTON CITY SD",
}
# BEAVERCREEK LSD and FAIRBORN CSD removed: they are Greene County (29), not
# Montgomery (57). Restore with county gating if expanding multi-county (§3a).

# Parquet WARD values that actually exist (ward-specific seats only, no at-large)
PARQUET_WARD_PREFIXES = {
    "CLAYTON", "DAYTON", "HUBER HTS", "KETTERING",
    "MIAMISBURG", "MORAINE", "TROTWOOD",
}

# ── OFCDESC seat parsing ──────────────────────────────────────────────────────

_WARD_RE   = re.compile(r'\bWARD\s+(\d+)\b',     re.IGNORECASE)
_DIST_RE   = re.compile(r'\bDISTRICT\s+(\d+)\b', re.IGNORECASE)
_ATLRG_RE  = re.compile(r'\bAT[\s-]+LARGE\b',    re.IGNORECASE)
_MAYOR_RE  = re.compile(r'\bMAYOR\b',             re.IGNORECASE)
_COMMIS_RE = re.compile(r'\bCOMMISSION\b',        re.IGNORECASE)


def parse_seat(ofcdesc: str, city_prefix: str) -> tuple[str, str]:
    """Return (parquet_key, seat_label) for a CITY row.

    parquet_key: exact match to parquet WARD column if ward-specific,
                 or "{prefix} AT LARGE" / "{prefix} MAYOR" for city-wide seats.
    seat_label:  human-readable office description.
    """
    m = _WARD_RE.search(ofcdesc)
    if m:
        n = m.group(1)
        return f"{city_prefix} WARD {n}", f"Ward {n}"

    m = _DIST_RE.search(ofcdesc)
    if m:
        n = m.group(1)
        # Normalize DISTRICT -> WARD to match parquet
        return f"{city_prefix} WARD {n}", f"District {n} (Ward {n})"

    if _ATLRG_RE.search(ofcdesc) or _COMMIS_RE.search(ofcdesc):
        return f"{city_prefix} AT LARGE", "At Large"

    if _MAYOR_RE.search(ofcdesc):
        return f"{city_prefix} MAYOR", "Mayor"

    # Generic council entry with no ward designation -> treat as at-large
    return f"{city_prefix} AT LARGE", "At Large"


def make_incumbent(row: dict) -> dict:
    name_parts = [row["FIRSTN"].strip(), row["MIDDLEN"].strip(), row["LASTN"].strip()]
    if row.get("SUFFIXN", "").strip():
        name_parts.append(row["SUFFIXN"].strip())
    name = " ".join(p for p in name_parts if p)
    party = row.get("PARTY", "").strip() or None
    entry = {"name": name, "party": party}
    if party is None:
        # PARTY == "" in the SOS CSV means the office is nonpartisan by charter
        # (school board, municipal court judge) -- NOT merely "party unknown".
        # Flag it so the serve layer can tell charter-nonpartisan from missing data.
        entry["nonpartisan"] = True
    return entry


# ── Merge logic ───────────────────────────────────────────────────────────────

def build_sections(rows: list[dict]) -> dict:
    """Build WARD, TOWNSHIP, VILLAGE, LOCAL_SCHOOL_DISTRICT dicts from CSV rows."""
    ward: dict        = {}
    township: dict    = {}
    village: dict     = {}
    school: dict      = {}
    city_school: dict = {}
    unmapped: list    = []

    for row in rows:
        dtype    = row["DISTTYPE"]
        distname = row["DISTNAME"].strip()
        ofcdesc  = row["OFCDESC"].strip()

        if dtype == "TOWN":
            parquet_key = TOWNSHIP_MAP.get(distname)
            if not parquet_key:
                unmapped.append(f"TOWN/{distname}")
                continue
            office = ofcdesc  # e.g. "BUTLER TOWNSHIP TRUSTEE"
            # Multiple trustees per township -> collect into list
            if parquet_key not in township:
                township[parquet_key] = {
                    "office":    "Township Trustee",
                    "term_exp":  row.get("TERMEXP", "").strip() or None,
                    "incumbents": [],
                    "challengers": [],
                }
            township[parquet_key]["incumbents"].append(make_incumbent(row))

        elif dtype == "VILL":
            parquet_key = VILLAGE_MAP.get(distname)
            if not parquet_key:
                unmapped.append(f"VILL/{distname}")
                continue
            # Villages can have mayor + multiple council members
            if parquet_key not in village:
                village[parquet_key] = {"offices": [], "challengers": []}
            village[parquet_key]["offices"].append({
                "office":    ofcdesc,
                "term_exp":  row.get("TERMEXP", "").strip() or None,
                "incumbent": make_incumbent(row),
            })

        elif dtype == "SCHOOL":
            # Route to the correct mutually-exclusive parquet column (§3a):
            # local "LSD" districts vs. municipal "CSD" districts.
            lsd_key = LSD_MAP.get(distname)
            csd_key = CSD_MAP.get(distname)
            if lsd_key:
                target, parquet_key = school, lsd_key
            elif csd_key:
                target, parquet_key = city_school, csd_key
            else:
                unmapped.append(f"SCHOOL/{distname}")
                continue
            if parquet_key not in target:
                target[parquet_key] = {
                    "office":    "Board of Education Member",
                    "incumbents": [],
                    "challengers": [],
                }
            target[parquet_key]["incumbents"].append({
                **make_incumbent(row),
                "term_exp": row.get("TERMEXP", "").strip() or None,
            })

        elif dtype == "CITY":
            city_prefix = CITY_PREFIX.get(distname)
            if not city_prefix:
                unmapped.append(f"CITY/{distname}")
                continue
            parquet_key, seat_label = parse_seat(ofcdesc, city_prefix)
            if parquet_key not in ward:
                ward[parquet_key] = {
                    "office":      ofcdesc,
                    "seat":        seat_label,
                    "parquet_match": city_prefix in PARQUET_WARD_PREFIXES and "AT LARGE" not in parquet_key and "MAYOR" not in parquet_key,
                    "incumbents":  [],
                    "challengers": [],
                }
            ward[parquet_key]["incumbents"].append(make_incumbent(row))

    if unmapped:
        print(f"  WARN: {len(unmapped)} unmapped DISTNAME values: {unmapped[:10]}")

    return {
        "WARD": ward,
        "TOWNSHIP": township,
        "VILLAGE": village,
        "LOCAL_SCHOOL_DISTRICT": school,
        "CITY_SCHOOL_DISTRICT": city_school,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Populate officials.json from electedofficials.csv.")
    parser.add_argument("--csv",   type=Path, default=DEFAULT_CSV, help="Path to electedofficials.csv")
    parser.add_argument("--write", action="store_true", help="Write changes (default: dry run)")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    rows = list(csv.DictReader(args.csv.open(encoding="utf-8")))
    relevant_types = {"CITY", "TOWN", "VILL", "SCHOOL"}
    relevant_rows  = [r for r in rows if r["DISTTYPE"] in relevant_types]
    print(f"CSV: {len(rows)} rows, {len(relevant_rows)} relevant (CITY/TOWN/VILL/SCHOOL)")

    new_sections = build_sections(relevant_rows)

    # Report counts
    for sec, data in new_sections.items():
        parquet_matched = sum(1 for v in data.values() if isinstance(v, dict) and v.get("parquet_match", True) and not str(list(data.keys())[0] if data else "").startswith("_"))
        print(f"  {sec}: {len(data)} entries")

    if not args.write:
        print("\nDry run. Pass --write to apply. Sample output:")
        for sec, data in new_sections.items():
            sample_key = next(iter(data), None)
            if sample_key:
                print(f"  {sec}/{sample_key!r}: {json.dumps(data[sample_key], indent=4)[:200]}")
        return

    # Load existing officials.json and merge
    existing = json.loads(OFFICIALS_JSON.read_text(encoding="utf-8"))

    for section, data in new_sections.items():
        if isinstance(existing.get(section), dict) and "_note" in existing[section]:
            # Replace stub
            existing[section] = data
        else:
            # Merge: new entries win, keep existing district-level data
            existing.setdefault(section, {}).update(data)

    OFFICIALS_JSON.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote {OFFICIALS_JSON} ({OFFICIALS_JSON.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
