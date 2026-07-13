#!/usr/bin/env python3
"""
captain_db.py — SQLite write tier for the captain registry, notes & walk-list state.

v2 schema (captain_schema_v2.md, 2026-07-02): the fused v1 `captain` row is split
into three entities with three different lifetimes:

  * ``seat``        — durable representation unit (a precinct's central-committee
                       position). The vote/credential/turf entity. Its ``v_id``
                       is an opaque hash of (county, precinct, party) — NEVER a
                       person-derived value — so the QR/account/credential
                       survive a holder rotation (domain doc Q4/Q5).
  * ``holder_term``  — the person occupying a seat for a period: SOS_VOTERID,
                       contact, login. Rotates; a rotation is a two-write
                       operation (end the old term, insert a new one), never an
                       in-place edit, so per-holder field-work performance stays
                       cleanly delineated across a rotation (Q5).
  * ``voter_touch`` / ``walk_list`` — records. Attach to the SEAT (turf follows
                       the seat across rotations) and carry the HOLDER_TERM that
                       produced them (performance attribution).

Treat the SQLite file as sensitive: it lives under ``local/captain.db``
(gitignored) and never goes near ``docs/``.

Public functions (the only surface roster_api.py / seed_quorum_registry.py
should import):

  Connection
    * ``connect()``                       — return the per-process connection

  Seat
    * ``derive_seat_key(...)``            — the (county, dist_name, party) natural key
    * ``derive_v_id(seat_key)``           — opaque public id derived from the seat key
    * ``upsert_seat(...)``                — idempotent create/update, keyed on seat_key
    * ``get_seat(seat_id)`` / ``get_seat_by_v_id(v_id)``
    * ``set_seat_status(seat_id, status)``

  Holder term
    * ``get_active_holder(seat_id)``      — the current (term_end IS NULL) holder, or None
    * ``start_holder_term(...)``          — the raw two-write rotation primitive
    * ``seed_holder_term(...)``           — idempotent wrapper for a re-runnable seeder:
                                             same person -> refresh in place; different
                                             person (or none yet) -> real rotation
    * ``attach_login(...)``               — set password_hash on an existing active
                                             holder_term (self-service /activate or
                                             staff-assisted /activate/override)
    * ``get_captain_view(seat_id)``       — seat + active holder merged into the wire
                                             shape roster_api.py / captain-mode.js expect
    * ``get_current_captain()``           — device-demo mode: the one ACTIVATED
                                             (password_hash set) captain on this device

  Walk lists / touches (seat_id = turf owner, holder_term_id = who did the work)
    * ``find_or_create_walk_list(...)``
    * ``set_walk_status(...)``
    * ``walk_list_progress(walk_list_id)``
    * ``walk_list_statuses(walk_list_id)``
    * ``log_touch(...)``
    * ``list_touches(sos_voterid)``
    * ``list_touches_for_walk_list(walk_list_id)``

Everything else is private helpers.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
# Config-driven DB location: ROSTER_DB_PATH overrides the localhost default so
# a hosted deploy can point at a mounted volume / managed disk with zero code
# change. Default keeps the existing local demo working with zero config.
DB_PATH = Path(os.environ.get("ROSTER_DB_PATH", str(BASE_DIR / "local" / "captain.db")))

# Touch kinds — the set of things that can happen at a door / phone / inbox.
TOUCH_KINDS = {
    "visit", "literature", "phone", "text",
    "no_answer", "refused", "moved", "wrong_address",
}
# Outcomes — deliberately limited to yes/maybe/no per scope discussion. A
# campaign manager can derive any finer scoring downstream; canvasser-facing
# tooling should not require them to slot a stranger into 5 buckets at the door.
TOUCH_OUTCOMES = {"yes", "maybe", "no"}
WALK_STATUSES = {"queued", "done", "skip"}
FILTER_KINDS = {"cohort", "generation", "cohort_generation"}
SEAT_STATUSES = {"filled", "vacant"}
HOLDER_ORIGINS = {"elected", "appointed"}

# Single sqlite3.Connection per process. Reads are concurrent under WAL mode;
# writes serialize via a re-entrant lock so the few captain.db writes don't
# fight each other when the API handles multiple GETs at the same time.
_conn: sqlite3.Connection | None = None
_lock = threading.RLock()


# ──────────────────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS seat (
    seat_id          INTEGER PRIMARY KEY,
    v_id             TEXT UNIQUE NOT NULL,   -- opaque_hash(seat_key); public account/QR bridge
    seat_key         TEXT UNIQUE NOT NULL,   -- "<COUNTY_NUMBER>|<DISTNAME>|<PARTY>" (traceable, no name)
    county_number    TEXT NOT NULL,
    dist_name        TEXT NOT NULL,          -- reliable precinct code (DISTNAME), NOT OFCDESC
    party            TEXT NOT NULL,
    unit_type        TEXT NOT NULL DEFAULT 'precinct'
                       CHECK (unit_type IN ('precinct','ward','political_subdivision')),
    display_name     TEXT NOT NULL,          -- crosswalked, e.g. "KETTERING 1-A" — DISPLAY ONLY
    status           TEXT NOT NULL DEFAULT 'vacant'
                       CHECK (status IN ('filled','vacant')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS holder_term (
    holder_term_id   INTEGER PRIMARY KEY,
    seat_id          INTEGER NOT NULL REFERENCES seat(seat_id),
    sos_voterid      TEXT,                   -- NULLABLE = "pending" match
    person_key       TEXT,                   -- "<DISTNAME>|<PARTY>|<LASTN>,<FIRSTN>,<MIDDLEN>"
    binding_hash     TEXT,                   -- match_to_voters.py fingerprint; SOS change detect
    display_name     TEXT NOT NULL,
    -- login + personal contact — RETIRE with the person (PII, local-only, never committed):
    email            TEXT,
    phone            TEXT,
    phone_digits     TEXT,
    password_hash    TEXT,
    -- NULL until a human claims this holder_term on some device: either via
    -- /activate (password set) or the no-password manual POST /captain form.
    -- Deliberately NOT the same signal as password_hash/email: those can get
    -- backfilled by a future PII-spreadsheet seed pass without that backfill
    -- being mistaken for "someone is using this device" (get_current_captain).
    claimed_at       TEXT,
    origin           TEXT NOT NULL DEFAULT 'elected'
                       CHECK (origin IN ('elected','appointed')),
    term_start       TEXT NOT NULL DEFAULT (datetime('now')),
    term_end         TEXT,                   -- NULL = current active holder
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
-- INVARIANT (Q11): a seat has exactly 0 or 1 ACTIVE holder-term.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_holder
    ON holder_term(seat_id) WHERE term_end IS NULL;
CREATE INDEX IF NOT EXISTS holder_by_seat ON holder_term(seat_id);

CREATE TABLE IF NOT EXISTS voter_touch (
    id              INTEGER PRIMARY KEY,
    sos_voterid     TEXT NOT NULL,
    seat_id         INTEGER NOT NULL REFERENCES seat(seat_id),
    holder_term_id  INTEGER NOT NULL REFERENCES holder_term(holder_term_id),
    precinct_county TEXT NOT NULL,
    precinct_name   TEXT NOT NULL,
    touched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    kind            TEXT NOT NULL,
    -- yes/maybe/no/null. Stored as TEXT so a future scoring system can add
    -- values without a destructive migration; CHECK keeps current vocab tight.
    outcome         TEXT,
    notes           TEXT,
    CHECK (kind IN ('visit','literature','phone','text','no_answer','refused','moved','wrong_address')),
    CHECK (outcome IS NULL OR outcome IN ('yes','maybe','no'))
);
CREATE INDEX IF NOT EXISTS touch_voter ON voter_touch(sos_voterid);
CREATE INDEX IF NOT EXISTS touch_precinct_time ON voter_touch(precinct_county, precinct_name, touched_at);

-- A walk list = a named work session, scoped to the chart-click filter that
-- defined it. find_or_create_walk_list() makes the lookup idempotent:
-- re-clicking the same filter resumes the same list. It belongs to the SEAT
-- (turf continuity across a holder rotation); created_by_holder_term just
-- records who built it.
CREATE TABLE IF NOT EXISTS walk_list (
    id                      INTEGER PRIMARY KEY,
    seat_id                 INTEGER NOT NULL REFERENCES seat(seat_id),
    created_by_holder_term  INTEGER REFERENCES holder_term(holder_term_id),
    precinct_county TEXT NOT NULL,
    precinct_name   TEXT NOT NULL,
    filter_kind     TEXT NOT NULL,   -- 'cohort'|'generation'|'cohort_generation'
    filter_value    TEXT NOT NULL,   -- e.g. 'PURE_D' or 'PURE_D|Millennials'
    filter_label    TEXT NOT NULL,   -- human: 'Pure D Millennials'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (seat_id, filter_kind, filter_value)
);

CREATE TABLE IF NOT EXISTS walk_list_voter (
    walk_list_id    INTEGER NOT NULL REFERENCES walk_list(id),
    sos_voterid     TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('queued','done','skip')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (walk_list_id, sos_voterid)
);
CREATE INDEX IF NOT EXISTS wlv_walklist ON walk_list_voter(walk_list_id);
"""


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────

def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """One-time clean rebuild from the fused v1 `captain` table to the v2
    seat/holder_term split (captain_schema_v2.md S5).

    Data-state checked 2026-07-02 (default local/captain.db): 1 demo captain
    row, 1 demo touch, 8 demo walk lists — throwaway. The REAL roster is never
    stored here; it is re-derived from source by seed_quorum_registry.py on
    every run. So this drops the v1 tables rather than migrating rows into the
    new shape. Idempotent: only fires when a v1 `captain` table exists and the
    v2 `seat` table does not.
    """
    has_v1 = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='captain'"
    ).fetchone()
    has_v2 = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='seat'"
    ).fetchone()
    if has_v1 and not has_v2:
        conn.executescript(
            "DROP TABLE IF EXISTS walk_list_voter;"
            "DROP TABLE IF EXISTS walk_list;"
            "DROP TABLE IF EXISTS voter_touch;"
            "DROP TABLE IF EXISTS captain;"
        )


def connect() -> sqlite3.Connection:
    """Open (or return cached) connection. Auto-creates parent dir + schema."""
    global _conn
    with _lock:
        if _conn is not None:
            return _conn
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        # WAL = concurrent reads while a writer holds the file. Required because
        # the ThreadingHTTPServer in roster_api.py may have a GET reading while
        # a POST is writing.
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.execute("PRAGMA foreign_keys = ON")
        _migrate_v1_to_v2(_conn)
        _conn.executescript(SCHEMA)
        return _conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


_DIGITS_RE = re.compile(r"\D+")


def _normalize_phone(raw: str) -> str:
    return _DIGITS_RE.sub("", raw or "")


# ──────────────────────────────────────────────────────────────────────────
# Seat
# ──────────────────────────────────────────────────────────────────────────

def derive_seat_key(county_number: str, dist_name: str, party: str) -> str:
    """The seat's natural key — county|distname|party, NO person name. This is
    the identity anchor (captain_schema_v2.md S1): because nothing here is
    holder-derived, the QR code, activation link, and credential all survive a
    holder rotation. Single resolver — seed_quorum_registry.py must call this,
    never recompute the format itself.
    """
    return f"{county_number}|{dist_name}|{party}"


def derive_v_id(seat_key: str) -> str:
    """Public opaque id for the QR / activation link (`precincts.info/activate?v_id=`).
    sha256-truncated, matching the binding_hash convention already used in
    match_to_voters.py."""
    return hashlib.sha256(seat_key.encode("utf-8")).hexdigest()[:16]


def upsert_seat(
    *, county_number: str, dist_name: str, party: str, display_name: str,
    unit_type: str = "precinct", status: str | None = None,
) -> dict:
    """Create or update a seat, keyed on (county_number, dist_name, party).
    v_id/seat_key are derived here — not passed in — so every caller (the
    seeder, manual captain entry) computes them identically.

    ``status`` is a new-seat default only (falls back to 'vacant' when the
    seat doesn't exist yet). On an EXISTING seat, passing None (the default)
    leaves status untouched — only a caller that explicitly passes status=...
    can change an existing seat's status. This is the fix for the footgun
    where a future caller's default status='vacant' would silently vacate an
    already-filled seat on every re-run (D1 finding, runbook Sec7 item 9).
    """
    if unit_type not in ("precinct", "ward", "political_subdivision"):
        raise ValueError(f"unknown unit_type '{unit_type}'")
    if status is not None and status not in SEAT_STATUSES:
        raise ValueError(f"unknown seat status '{status}'")
    insert_status = status or "vacant"
    seat_key = derive_seat_key(county_number, dist_name, party)
    v_id = derive_v_id(seat_key)
    with _lock:
        c = connect()
        c.execute(
            """
            INSERT INTO seat (v_id, seat_key, county_number, dist_name, party,
                               unit_type, display_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(seat_key) DO UPDATE SET
                display_name = excluded.display_name,
                unit_type    = excluded.unit_type,
                status       = CASE WHEN ? IS NOT NULL THEN excluded.status ELSE seat.status END
            """,
            (v_id, seat_key, county_number, dist_name, party, unit_type, display_name,
             insert_status, status),
        )
        return _row_to_dict(c.execute(
            "SELECT * FROM seat WHERE seat_key = ?", (seat_key,)
        ).fetchone())  # type: ignore[return-value]


def get_seat(seat_id: int) -> dict | None:
    with _lock:
        return _row_to_dict(connect().execute(
            "SELECT * FROM seat WHERE seat_id = ?", (seat_id,)
        ).fetchone())


def get_seat_by_v_id(v_id: str) -> dict | None:
    with _lock:
        return _row_to_dict(connect().execute(
            "SELECT * FROM seat WHERE v_id = ?", (v_id,)
        ).fetchone())


def set_seat_status(seat_id: int, status: str) -> None:
    if status not in SEAT_STATUSES:
        raise ValueError(f"unknown seat status '{status}'")
    with _lock:
        connect().execute("UPDATE seat SET status = ? WHERE seat_id = ?", (status, seat_id))


# ──────────────────────────────────────────────────────────────────────────
# Holder term
# ──────────────────────────────────────────────────────────────────────────

def get_active_holder(seat_id: int) -> dict | None:
    with _lock:
        return _row_to_dict(connect().execute(
            "SELECT * FROM holder_term WHERE seat_id = ? AND term_end IS NULL",
            (seat_id,),
        ).fetchone())


def start_holder_term(
    *, seat_id: int, display_name: str,
    sos_voterid: str | None = None, person_key: str | None = None,
    binding_hash: str | None = None, origin: str = "elected",
    email: str | None = None, phone: str | None = None,
    password_hash: str | None = None, claimed: bool = False,
) -> dict:
    """Rotate the seat to a new holder: end any current active term, then
    insert a fresh one. Two-write, never an in-place edit (captain_schema_v2.md
    S2b) — that is what keeps per-holder performance attribution clean across a
    rotation. The seat row (and its v_id/credential/turf) is untouched.

    Unconditional: calling this for a holder who hasn't actually changed still
    starts a new term. Callers seeding from a re-runnable source should use
    ``seed_holder_term`` instead, which only rotates on a genuine change.

    ``claimed=True`` marks this term as already bound to a device/person (the
    no-password manual POST /captain path); leave False for a seeder pre-populating
    an as-yet-unclaimed officeholder.
    """
    if origin not in HOLDER_ORIGINS:
        raise ValueError(f"unknown origin '{origin}'")
    phone_digits = _normalize_phone(phone) if phone else None
    with _lock:
        c = connect()
        # BEGIN IMMEDIATE around the two-write rotation (D1, runbook Sec7 item
        # 10): end-old + insert-new must commit atomically, or a crash between
        # the two writes could leave a seat with zero active holders.
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute(
                "UPDATE holder_term SET term_end = datetime('now') "
                "WHERE seat_id = ? AND term_end IS NULL",
                (seat_id,),
            )
            cur = c.execute(
                """
                INSERT INTO holder_term (
                    seat_id, sos_voterid, person_key, binding_hash, display_name,
                    email, phone, phone_digits, password_hash, origin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (seat_id, sos_voterid, person_key, binding_hash, display_name,
                 email, phone, phone_digits, password_hash, origin),
            )
            hid = cur.lastrowid
            if claimed:
                c.execute(
                    "UPDATE holder_term SET claimed_at = datetime('now') WHERE holder_term_id = ?",
                    (hid,),
                )
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        return _row_to_dict(c.execute(
            "SELECT * FROM holder_term WHERE holder_term_id = ?", (hid,)
        ).fetchone())  # type: ignore[return-value]


def seed_holder_term(
    *, seat_id: int, display_name: str, person_key: str | None,
    sos_voterid: str | None, binding_hash: str | None, origin: str = "elected",
) -> dict:
    """Idempotent holder attach for a re-runnable seeder (HANDOFF S2: "the
    seeder must be re-runnable and reflect the current file").

    Same person_key as the current active holder -> refresh match data
    (sos_voterid/binding_hash/display_name) IN PLACE — not a rotation, so
    login/contact/password are left untouched. Different person_key (or no
    active holder yet) -> a genuine rotation, routed through the two-write
    ``start_holder_term`` so the outgoing holder's records stay cleanly
    delineated from the incoming one (Q5).
    """
    current = get_active_holder(seat_id)
    if current is not None and person_key is not None and current["person_key"] == person_key:
        with _lock:
            c = connect()
            c.execute(
                "UPDATE holder_term SET sos_voterid = ?, binding_hash = ?, display_name = ? "
                "WHERE holder_term_id = ?",
                (sos_voterid, binding_hash, display_name, current["holder_term_id"]),
            )
            return _row_to_dict(c.execute(
                "SELECT * FROM holder_term WHERE holder_term_id = ?",
                (current["holder_term_id"],),
            ).fetchone())  # type: ignore[return-value]
    return start_holder_term(
        seat_id=seat_id, display_name=display_name, sos_voterid=sos_voterid,
        person_key=person_key, binding_hash=binding_hash, origin=origin,
    )


def attach_login(*, holder_term_id: int, password_hash: str) -> dict:
    """Set login credentials on an existing active holder_term. Does not
    start a new term — the officeholder the seeder already identified IS the
    account being activated. Two call sites: roster_api.py's self-service
    ``/activate`` (PIN-verified) and the staff-assisted ``/activate/override``
    (no PIN, human-verified) — both first-activation-only, since the
    "already activated" guard below fires for either caller."""
    with _lock:
        c = connect()
        row = c.execute(
            "SELECT * FROM holder_term WHERE holder_term_id = ? AND term_end IS NULL",
            (holder_term_id,),
        ).fetchone()
        if row is None:
            raise ValueError("holder_term not found or no longer active")
        if row["password_hash"]:
            raise ValueError("account already activated")
        c.execute(
            "UPDATE holder_term SET password_hash = ?, claimed_at = datetime('now') "
            "WHERE holder_term_id = ?",
            (password_hash, holder_term_id),
        )
        return _row_to_dict(c.execute(
            "SELECT * FROM holder_term WHERE holder_term_id = ?", (holder_term_id,)
        ).fetchone())  # type: ignore[return-value]


def _captain_view(seat_id: int) -> dict | None:
    """Merge a seat + its active holder_term into the wire shape roster_api.py
    (and the legacy docs/captain/captain-mode.js frontend) expect. Single place
    that builds this join so get_current_captain() and the /activate response
    don't each duplicate it (CLAUDE.md S5, single-resolver hygiene).

    `id` aliases `seat_id`: captain-mode.js persists `captain.id` and echoes it
    back as `captain_id` on writes; roster_api.py resolves that back to the
    seat's active holder_term server-side for attribution, so the wire
    contract doesn't need to change even though the identity model underneath
    it did.

    Never leaks `password_hash` (D1, runbook Sec7 item 8) — the raw hash is
    read here (needed nowhere outside this function) and immediately
    collapsed into a boolean `activated` before the dict is returned.
    """
    with _lock:
        row = connect().execute(
            "SELECT s.seat_id, s.v_id, s.seat_key, s.county_number, s.dist_name, "
            "       s.party, s.display_name AS precinct_display_name, s.status, "
            "       h.holder_term_id, h.sos_voterid, h.person_key, h.display_name, "
            "       h.email, h.phone, h.phone_digits, h.password_hash, h.claimed_at, "
            "       h.origin, h.term_start "
            "FROM seat s JOIN holder_term h ON h.seat_id = s.seat_id AND h.term_end IS NULL "
            "WHERE s.seat_id = ?",
            (seat_id,),
        ).fetchone()
        if row is None:
            return None
        d = _row_to_dict(row)
        d["activated"] = d.pop("password_hash") is not None
        d["id"] = d["seat_id"]
        d["precinct_county"] = d["county_number"]
        d["precinct_name"] = d["precinct_display_name"]
        return d


def get_captain_view(seat_id: int) -> dict | None:
    """Public wrapper so roster_api.py can render one specific seat's merged
    identity (e.g. right after /activate) without reaching into private state."""
    return _captain_view(seat_id)


def get_current_captain() -> dict | None:
    """Single-captain-per-device mode: return the lowest-seat_id captain that
    has actually been CLAIMED (claimed_at set) on this device, or None.

    Deliberately excludes pre-seeded-but-unclaimed holders: once the seeder
    pre-populates seats/holder_terms for all 209 Montgomery captains, "lowest
    seat_id" alone would make every fresh browser silently "log in" as
    whichever captain happens to sort first. claimed_at is set by BOTH
    /activate (password path) and the no-password manual POST /captain form —
    it is a distinct signal from password_hash/email so a future PII-sheet
    backfill of contact info can't be mistaken for "someone is using this
    device."

    When the hosted tier ships this becomes a session lookup; call sites in
    roster_api.py shouldn't have to change.
    """
    with _lock:
        row = connect().execute(
            "SELECT s.seat_id FROM seat s JOIN holder_term h "
            "ON h.seat_id = s.seat_id AND h.term_end IS NULL "
            "WHERE h.claimed_at IS NOT NULL "
            "ORDER BY s.seat_id ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return _captain_view(row["seat_id"])


# ──────────────────────────────────────────────────────────────────────────
# Walk lists
# ──────────────────────────────────────────────────────────────────────────

def find_or_create_walk_list(
    *, seat_id: int, precinct_county: str, precinct_name: str,
    filter_kind: str, filter_value: str, filter_label: str,
    seed_voter_ids: list[str], created_by_holder_term: int | None = None,
) -> dict:
    """Look up a walk list by (seat, filter); create it if absent.

    On create, seed walk_list_voter with status='queued' for every voter id in
    seed_voter_ids. On re-find, do NOT re-seed — preserve existing statuses so
    re-clicking the same chart resumes the same walk. Scoped by seat_id (turf),
    not holder_term_id, so a walk in progress survives a holder rotation.
    """
    if filter_kind not in FILTER_KINDS:
        raise ValueError(f"unknown filter_kind '{filter_kind}'")
    with _lock:
        conn = connect()
        row = conn.execute(
            "SELECT * FROM walk_list WHERE seat_id = ? AND filter_kind = ? AND filter_value = ?",
            (seat_id, filter_kind, filter_value),
        ).fetchone()
        if row is not None:
            return _row_to_dict(row)  # type: ignore[return-value]
        cur = conn.execute(
            "INSERT INTO walk_list (seat_id, created_by_holder_term, precinct_county, "
            "precinct_name, filter_kind, filter_value, filter_label) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (seat_id, created_by_holder_term, precinct_county, precinct_name,
             filter_kind, filter_value, filter_label),
        )
        wl_id = cur.lastrowid
        if seed_voter_ids:
            conn.executemany(
                "INSERT OR IGNORE INTO walk_list_voter (walk_list_id, sos_voterid, status) "
                "VALUES (?, ?, 'queued')",
                [(wl_id, vid) for vid in seed_voter_ids if vid],
            )
        return _row_to_dict(conn.execute(
            "SELECT * FROM walk_list WHERE id = ?", (wl_id,)
        ).fetchone())  # type: ignore[return-value]


def set_walk_status(*, walk_list_id: int, sos_voterid: str, status: str) -> None:
    if status not in WALK_STATUSES:
        raise ValueError(f"unknown status '{status}'")
    with _lock:
        connect().execute(
            "INSERT INTO walk_list_voter (walk_list_id, sos_voterid, status, updated_at) "
            "VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(walk_list_id, sos_voterid) DO UPDATE SET "
            "  status = excluded.status, updated_at = excluded.updated_at",
            (walk_list_id, sos_voterid, status),
        )


def walk_list_progress(walk_list_id: int) -> dict:
    """Counts powering the roster panel header widget: total / done / skipped
    / last_touched_at. Cheap; runs once per panel open."""
    with _lock:
        conn = connect()
        row = conn.execute(
            "SELECT "
            "  COUNT(*) AS total, "
            "  SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done, "
            "  SUM(CASE WHEN status = 'skip' THEN 1 ELSE 0 END) AS skip "
            "FROM walk_list_voter WHERE walk_list_id = ?",
            (walk_list_id,),
        ).fetchone()
        # last touch against any voter in this walk list, on the SAME SEAT
        # (turf continuity — a touch logged by the predecessor still counts).
        last = conn.execute(
            "SELECT MAX(t.touched_at) AS last_touched_at "
            "FROM voter_touch t "
            "JOIN walk_list_voter wlv ON wlv.sos_voterid = t.sos_voterid "
            "JOIN walk_list wl ON wl.id = wlv.walk_list_id "
            "WHERE wlv.walk_list_id = ? AND t.seat_id = wl.seat_id",
            (walk_list_id,),
        ).fetchone()
        return {
            "walk_list_id": walk_list_id,
            "total": int(row["total"] or 0),
            "done": int(row["done"] or 0),
            "skip": int(row["skip"] or 0),
            "last_touched_at": last["last_touched_at"] if last else None,
        }


def walk_list_statuses(walk_list_id: int) -> dict[str, str]:
    """Map of sos_voterid -> status for every voter in this list. The UI uses
    this to paint the Done checkbox state when the roster renders."""
    with _lock:
        cur = connect().execute(
            "SELECT sos_voterid, status FROM walk_list_voter WHERE walk_list_id = ?",
            (walk_list_id,),
        )
        return {r["sos_voterid"]: r["status"] for r in cur.fetchall()}


# ──────────────────────────────────────────────────────────────────────────
# Touches
# ──────────────────────────────────────────────────────────────────────────

def log_touch(
    *, sos_voterid: str, seat_id: int, holder_term_id: int,
    precinct_county: str, precinct_name: str,
    kind: str, outcome: str | None, notes: str | None,
) -> dict:
    if kind not in TOUCH_KINDS:
        raise ValueError(f"unknown kind '{kind}'")
    if outcome is not None and outcome not in TOUCH_OUTCOMES:
        raise ValueError(f"unknown outcome '{outcome}'")
    if not sos_voterid:
        raise ValueError("sos_voterid required")
    with _lock:
        cur = connect().execute(
            "INSERT INTO voter_touch (sos_voterid, seat_id, holder_term_id, "
            "precinct_county, precinct_name, kind, outcome, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sos_voterid, seat_id, holder_term_id, precinct_county, precinct_name,
             kind, outcome, notes),
        )
        tid = cur.lastrowid
        return _row_to_dict(connect().execute(
            "SELECT * FROM voter_touch WHERE id = ?", (tid,)
        ).fetchone())  # type: ignore[return-value]


def list_touches(sos_voterid: str, *, holder_term_id: int | None = None) -> list[dict]:
    """Touches for one voter, newest first. holder_term_id filter narrows to a
    specific captain's own touches when needed (e.g. a performance report);
    omitted, it returns every touch on this voter regardless of who logged it."""
    with _lock:
        sql = "SELECT * FROM voter_touch WHERE sos_voterid = ?"
        args: list[Any] = [sos_voterid]
        if holder_term_id is not None:
            sql += " AND holder_term_id = ?"
            args.append(holder_term_id)
        sql += " ORDER BY touched_at DESC"
        cur = connect().execute(sql, args)
        return [dict(r) for r in cur.fetchall()]


def list_touches_for_walk_list(walk_list_id: int) -> dict[str, list[dict]]:
    """Bulk fetch: every touch on every voter in this walk list, grouped by
    sos_voterid. One round-trip beats N round-trips when the roster has 74
    voters and the panel renders them all at once.
    """
    with _lock:
        cur = connect().execute(
            "SELECT t.* FROM voter_touch t "
            "JOIN walk_list_voter wlv ON wlv.sos_voterid = t.sos_voterid "
            "WHERE wlv.walk_list_id = ? "
            "ORDER BY t.sos_voterid, t.touched_at DESC",
            (walk_list_id,),
        )
        out: dict[str, list[dict]] = {}
        for r in cur.fetchall():
            out.setdefault(r["sos_voterid"], []).append(dict(r))
        return out


if __name__ == "__main__":
    # Smoke test — useful when iterating on schema. Run:
    #   .venv\\Scripts\\python.exe serve\\captain_db.py
    connect()
    print(f"DB at {DB_PATH}")
    print(f"Current captain (activated on this device): {get_current_captain()}")
