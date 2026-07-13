#!/usr/bin/env python3
"""seed_quorum_registry.py -- Task B of the Montgomery-first plan
(captain_domain_and_vision.md "NEXT STEPS 2026-07-02"; schema:
local/context/scope/captain_schema_v2.md).

Seeds the seat/holder_term registry for one county's precinct captains:

  1. Locate + classify captain rows via a per-county CountyAdapter (S3) --
     Montgomery is adapter #1, every other county is an explicit
     NotImplementedError stub. "Revisit later" = add an adapter, never
     refactor the core.
  2. CT3 validation gate -- HALT (loud, never silent) if the extracted count
     doesn't match the adapter's expected count, a required field is missing,
     or a precinct has more than one captain.
  3. Match each captain to their voter record via match_to_voters.py's single
     resolver (CLAUDE.md S5, single-resolver hygiene) -- this script does not
     duplicate the fuzzy-match logic.
  4. Write seat + holder_term rows into captain_db.py's SQLite tier (so
     roster_api.py's /activate can find them by v_id) AND emit the quorum
     Captain[] JSON to local/working/quorum_registry_{date}.json (gitignored;
     copy to quorum/src/mockRegistry.json before an event -- never commit).

Both writes are idempotent / re-runnable: upsert_seat + seed_holder_term only
rotate a holder when the matched person actually changed (captain_db.py
docstrings), so re-running this script after a routine re-download of
electedofficials.csv does not spuriously churn holder_term history.

Usage:
    .venv/Scripts/python.exe tools/admin/seed_quorum_registry.py
    .venv/Scripts/python.exe tools/admin/seed_quorum_registry.py --no-db --verbose
"""
from __future__ import annotations

import csv
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/admin/ as import root
from officials_common import (  # noqa: E402
    COUNTY_SLUG,
    ROOT,
    atomic_write_json,
    load_precinct_crosswalk,
    name_from_parts,
    normalize_name,
)

sys.path.insert(0, str(ROOT / "serve"))
import captain_db  # noqa: E402

OUTPUT_DIR = ROOT / "local" / "working"


# ──────────────────────────────────────────────────────────────────────────
# Canonical captain schema (CT6) -- what every adapter maps into
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class CanonicalCaptain:
    county_number: str
    dist_name: str          # BoE ballot code, e.g. "0010" -- lands on the SEAT
    party: str               # 'D' for v1 -- lands on the SEAT
    display_name: str        # crosswalked precinct name, e.g. "KETTERING 1-A"
    first_name: str
    middle_name: str
    last_name: str
    person_key: str          # "<DISTNAME>|<PARTY>|<LASTN>,<FIRSTN>,<MIDDLEN>" -- suffix
                              # deliberately excluded (see to_canonical's comment)
    raw_party: str            # the source PARTY cell, for audit (may be '' or miscoded)
    party_miscoded: bool
    suffix_name: str = ""     # SUFFIXN, e.g. "Jr" -- display only, never in person_key
    origin: str = "elected"

    @property
    def person_display_name(self) -> str:
        # Reuse captain_match_report.py's exact helper (CLAUDE.md S5,
        # single-resolver hygiene) instead of a second hand-rolled join --
        # this is what fixes the dropped-SUFFIXN bug (e.g. DISTNAME 1310
        # "William Louis Smith" instead of "...Smith Jr").
        return name_from_parts(self.first_name, self.middle_name, self.last_name, self.suffix_name)


# ──────────────────────────────────────────────────────────────────────────
# Per-county adapter seam (captain_schema_v2.md S3)
# ──────────────────────────────────────────────────────────────────────────

class CountyAdapter(ABC):
    county_number: str

    @abstractmethod
    def expected_captain_count(self) -> int:
        """CT3 reconciliation target."""

    @abstractmethod
    def locate_captain_rows(self, source_dir: Path) -> list[dict]:
        """CT1/CT2: find + classify captain rows across the county's files.
        Handles known variation across counties: MULTIPLE files, filename !=
        contents, PDF sources -- this county's implementation only has to
        handle ITS OWN shape; do not generalize speculatively."""

    @abstractmethod
    def is_captain(self, row: dict) -> bool:
        """County-specific captain-ID rule (OFCDESC pattern / DISTTYPE+party).
        NEVER filter on the raw PARTY column -- see Montgomery's docstring."""

    @abstractmethod
    def resolve_precinct(self, row: dict) -> str:
        """DISTNAME + crosswalk -> exact parquet PRECINCT_NAME. NEVER the
        OFCDESC suffix (the OFCDESC bug, SESSION_FINDINGS S9)."""

    @abstractmethod
    def to_canonical(self, row: dict) -> CanonicalCaptain:
        """Column map -> the CT6 canonical schema."""


class MontgomeryAdapter(CountyAdapter):
    """Adapter #1. Montgomery's captains live in the single base
    electedofficials.csv -- filename DOES match contents here, unlike
    Ashland's browser-duplicate-filtered downloads (CT1 finding). Future
    adapters must not assume that generalizes.
    """

    county_number = "57"
    _OFCDESC_PREFIX = "DEMOCRATIC CENTRAL COMMITTEE"

    def __init__(self) -> None:
        self._crosswalk = None  # lazy: needs the enriched parquet to validate

    def _xwalk(self):
        if self._crosswalk is None:
            self._crosswalk = load_precinct_crosswalk(COUNTY_SLUG[self.county_number])
        return self._crosswalk

    def expected_captain_count(self) -> int:
        return 209

    def locate_captain_rows(self, source_dir: Path) -> list[dict]:
        path = source_dir / "electedofficials.csv"
        if not path.exists():
            raise FileNotFoundError(f"Montgomery source not found: {path}")
        return list(csv.DictReader(path.open(encoding="utf-8")))

    def is_captain(self, row: dict) -> bool:
        # OFCDESC prefix + DISTTYPE, NOT the raw PARTY column: 33 captain rows
        # have a blank PARTY cell and 1 is miscoded 'R' (verified 2026-07-02,
        # 209 total either way) -- filtering on PARTY=='D' would silently drop
        # 34 real captains (handoff S1 / captain_schema_v2.md S4).
        return (
            row.get("DISTTYPE") == "PRECINCT"
            and (row.get("OFCDESC") or "").startswith(self._OFCDESC_PREFIX)
        )

    def resolve_precinct(self, row: dict) -> str:
        dist_name = (row.get("DISTNAME") or "").strip()
        name = self._xwalk().resolve(dist_name)
        if name is None:
            raise ValueError(
                f"DISTNAME {dist_name!r} did not resolve via the Montgomery precinct crosswalk"
            )
        return name

    def to_canonical(self, row: dict) -> CanonicalCaptain:
        dist_name = (row.get("DISTNAME") or "").strip()
        raw_party = (row.get("PARTY") or "").strip()
        last = (row.get("LASTN") or "").strip()
        first = (row.get("FIRSTN") or "").strip()
        middle = (row.get("MIDDLEN") or "").strip()
        suffix = (row.get("SUFFIXN") or "").strip()
        return CanonicalCaptain(
            county_number=self.county_number,
            dist_name=dist_name,
            # OFCDESC-filtered rows are Dem seats regardless of the raw PARTY
            # cell (handoff S1) -- 'D' is the seat's party, not row['PARTY'].
            party="D",
            display_name=self.resolve_precinct(row),
            first_name=first,
            middle_name=middle,
            last_name=last,
            # Suffix deliberately excluded from person_key: including it would
            # make every already-seeded suffixed captain look like a "different
            # person" on the next run purely from this format change, forcing a
            # spurious two-write rotation (matches captain_match_report.py's own
            # electedofficials_key, which excludes suffix for the same reason).
            person_key=f"{dist_name}|D|{last},{first},{middle}",
            raw_party=raw_party,
            party_miscoded=raw_party not in ("D", ""),
            suffix_name=suffix,
            origin="elected",
        )


ADAPTERS: dict[str, CountyAdapter] = {"57": MontgomeryAdapter()}


def get_adapter(county_number: str) -> CountyAdapter:
    if county_number not in ADAPTERS:
        raise NotImplementedError(f"county {county_number} not yet adapted")
    return ADAPTERS[county_number]


# ──────────────────────────────────────────────────────────────────────────
# CT3 validation gate -- HALT on mismatch, never silent
# ──────────────────────────────────────────────────────────────────────────

def ct3_validate(canon: list[CanonicalCaptain], expected: int) -> None:
    if len(canon) != expected:
        print(
            f"CT3 HALT: expected {expected} captain rows, found {len(canon)}. "
            "Refusing to seed a partial/over-matched roster.",
            file=sys.stderr,
        )
        sys.exit(1)
    seen_dist: set[str] = set()
    for c in canon:
        if not c.dist_name or not c.person_display_name.strip():
            print(f"CT3 HALT: missing required field on {c!r}", file=sys.stderr)
            sys.exit(1)
        if c.dist_name in seen_dist:
            print(
                f"CT3 HALT: duplicate captain for precinct {c.dist_name!r} "
                "(0-or-1 captain per precinct invariant violated)",
                file=sys.stderr,
            )
            sys.exit(1)
        seen_dist.add(c.dist_name)


# ──────────────────────────────────────────────────────────────────────────
# precinctAbbr -- short QR-payload label (HANDOFF S2: "document the rule and
# keep it deterministic"; approximate by design, display only, never identity)
# ──────────────────────────────────────────────────────────────────────────

_TOWNSHIP_WORDS = {"TWP", "TOWNSHIP", "TS"}


def derive_precinct_abbr(precinct_name: str) -> str:
    """'KETTERING 1-A' -> 'KET-1A' (the example in quorum/src/lib/registryUtils.ts);
    'BUTLER TWP A' -> 'BUT-A'; 'BROOKVILLE-A' -> 'BRO-A'."""
    name = precinct_name.strip().upper()
    if " " not in name and "-" in name:
        name = name.replace("-", " ", 1)
    words = [w for w in name.split() if w not in _TOWNSHIP_WORDS]
    if not words:
        return name[:6]
    head, rest = words[0], words[1:]
    abbr_head = head[:3]
    if not rest:
        return abbr_head
    return f"{abbr_head}-{''.join(rest).replace('-', '')}"


# ──────────────────────────────────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────────────────────────────────

def run(*, county_number: str, write_db: bool, verbose: bool) -> dict:
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        print("ERROR: rapidfuzz not installed. Run: uv add rapidfuzz", file=sys.stderr)
        sys.exit(1)
    from match_to_voters import (  # noqa: E402 -- reuse the single resolver, do not duplicate
        binding_hash,
        derive_match_confidence,
        load_ledger,
        load_voter_index,
        match_entity,
        match_key,
        verification_projection,
    )

    adapter = get_adapter(county_number)
    county_slug = COUNTY_SLUG[county_number]
    source_dir = ROOT / "local" / "source" / "County Data Files" / f"{county_number}_{county_slug.capitalize()}"

    rows = adapter.locate_captain_rows(source_dir)
    captain_rows = [r for r in rows if adapter.is_captain(r)]
    canon = [adapter.to_canonical(r) for r in captain_rows]

    expected = adapter.expected_captain_count()
    ct3_validate(canon, expected)
    print(f"CT3 gate passed: {len(canon)}/{expected} captain rows for county {county_number}")

    index = load_voter_index(county_slug)
    n_voters = sum(len(v) for v in index.values())
    print(f"Loaded {n_voters:,} ACTIVE/CONFIRMATION voters for {county_slug}")

    # C7: the durable, human-owned confirmation ledger. `by_id` resolves a
    # ledger `corrected_sos_voterid` back to a voter row (mirrors
    # match_to_voters.py's own construction).
    ledger = load_ledger()
    by_id = {r["SOS_VOTERID"]: r for rows_ in index.values() for r in rows_}

    registry: list[dict] = []
    needs_review: list[dict] = []
    match_stats = {"high": 0, "medium": 0, "low": 0, "unmatched": 0}
    verification_stats = {"unverified": 0, "confirmed": 0, "rejected": 0, "corrected": 0}

    for c in canon:
        row, method, score, location_check = match_entity(
            index, c.last_name, c.first_name, ("precinct", c.display_name), fuzz, process
        )

        # Ledger check runs for EVERY captain, matched or not -- this is what
        # lets a `corrected` entry promote a currently-unmatched captain (the
        # J Hunter Johnson case) rather than only adjusting an already-matched one.
        mk = match_key("captain_candidate", {"name": c.person_display_name,
                                              "precinct_name": c.display_name})
        entry = ledger.get(mk)
        if entry and entry.get("state") == "corrected":
            cid = entry.get("corrected_sos_voterid")
            if cid in by_id:
                row, method, score, location_check = by_id[cid], "human_corrected", 100, "confirmed"
            elif verbose:
                print(f"  NOTE [{c.dist_name}] ledger correction {cid!r} not found in "
                      f"{county_slug} voter index")

        # Recomputed AFTER the possible override so a correction is evaluated
        # as "confirmed" location, which naturally yields "high" (not hardcoded).
        confidence = derive_match_confidence(method, location_check, None)
        verification_stats[entry.get("state", "unverified") if entry else "unverified"] += 1

        sos_voterid = row["SOS_VOTERID"] if row else None
        bhash = binding_hash(row) if row else None
        verification = verification_projection(
            entry, {"sos_voterid": sos_voterid, "binding_hash": bhash})

        # Write-gate (operator decision): trust the match only when confidence
        # is high or the ledger currently confirms it. An explicit human
        # rejection always wins over confidence -- stricter than
        # match_to_voters.py's own posture for incumbent/general_candidate,
        # deliberately scoped to this seeder only (captains get a self-service
        # PIN; those other entity types don't).
        trusted = confidence == "high" or verification["status"] == "current"
        if entry and entry.get("state") == "rejected":
            trusted = False

        zip_code = (row.get("RESIDENTIAL_ZIP") if row else None) or ""
        if not trusted:
            reason = f"ledger:{entry['state']}" if entry else f"confidence:{confidence or 'unmatched'}"
            needs_review.append({
                "dist_name": c.dist_name, "precinct": c.display_name,
                "person_display_name": c.person_display_name, "reason": reason,
            })
            sos_voterid = None
            bhash = None
            zip_code = ""

        match_stats[confidence if row else "unmatched"] += 1
        if verbose:
            tag = f"{method}/{score}" if row else "NO MATCH"
            flag = "" if trusted else f" NEEDS_REVIEW[{verification['status']}]"
            print(f"  [{c.dist_name}] {c.person_display_name} -> {sos_voterid} ({tag}){flag}")

        if write_db:
            seat = captain_db.upsert_seat(
                county_number=c.county_number, dist_name=c.dist_name, party=c.party,
                display_name=c.display_name, status="filled",
            )
            captain_db.seed_holder_term(
                seat_id=seat["seat_id"], display_name=c.person_display_name,
                person_key=c.person_key, sos_voterid=sos_voterid, binding_hash=bhash,
                origin=c.origin,
            )
            v_id = seat["v_id"]
        else:
            seat_key = captain_db.derive_seat_key(c.county_number, c.dist_name, c.party)
            v_id = captain_db.derive_v_id(seat_key)

        registry.append({
            "uuid": v_id,
            "firstName": normalize_name(c.first_name),
            "lastName": normalize_name(c.last_name),
            "precinct": c.display_name,
            "precinctId": c.dist_name,
            "precinctAbbr": derive_precinct_abbr(c.display_name),
            "zip": zip_code,
            "phone": None,     # PII spreadsheet not yet supplied (HANDOFF S3 interim path)
            "phoneLast4": None,
            "email": None,
            "status": "Active",
            "syncStatus": 0,
        })

    return {
        "_meta": {
            "generated": date.today().isoformat(),
            "county_number": county_number,
            "adapter": type(adapter).__name__,
            "expected_captain_count": expected,
            "seeded": len(registry),
            "match_stats": match_stats,
            "verification_stats": verification_stats,
            "needs_review_total": len(needs_review),
            "wrote_db": write_db,
        },
        "captains": registry,
        "needs_review": needs_review,
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Task B: seed the seat/holder_term registry + emit the quorum Captain[] JSON."
    )
    ap.add_argument("--county-number", default="57", help="SWVF COUNTY_NUMBER (default 57, Montgomery)")
    ap.add_argument("--no-db", action="store_true", help="skip writing captain_db.py's SQLite tier")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    result = run(county_number=args.county_number, write_db=not args.no_db, verbose=args.verbose)
    meta = result["_meta"]

    out_path = OUTPUT_DIR / f"quorum_registry_{date.today().isoformat()}.json"
    nbytes = atomic_write_json(out_path, result["captains"])

    print(f"match stats: {meta['match_stats']}")
    print(f"verification stats (ledger): {meta['verification_stats']}")
    print(f"needs_review: {meta['needs_review_total']}")
    for r in result["needs_review"]:
        print(f"  [{r['dist_name']}] {r['person_display_name']} ({r['precinct']}) -- {r['reason']}")
    print(f"Wrote {out_path.relative_to(ROOT)} ({nbytes:,} bytes)")
    if meta["wrote_db"]:
        print(f"Seeded seat/holder_term rows into {captain_db.DB_PATH}")
    else:
        print("--no-db: captain_db.py SQLite tier NOT written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
