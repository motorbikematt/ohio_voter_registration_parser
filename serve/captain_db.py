#!/usr/bin/env python3
"""
captain_db.py — SQLite write tier for captain notes & walk-list state.

This is the first *write* surface in the project. Everything before it was
read-only (SWVF is public record; the roster API just queries it). Captain
notes are a different category: they're observations made by a person against
identifiable voters, plus the captain's own contact info. Treat the SQLite
file as sensitive: it lives under ``local/captain.db`` (gitignored) and never
goes near ``docs/``.

Path A in the scope discussion: single SQLite file per captain device. No auth,
no sync, no multi-captain. Schema designed so it lifts to Postgres cleanly when
the hosted tier comes online — see ``project-roster-api`` memory note.

Public functions (the only surface roster_api.py should import):

  * ``connect()``                       — return the per-process connection
  * ``get_captain()``                   — returns dict or None
  * ``create_captain(...)``             — inserts the (single) captain row
  * ``find_or_create_walk_list(...)``   — idempotent: same filter same list
  * ``set_walk_status(...)``            — queued/done/skip per voter per list
  * ``walk_list_progress(walk_list_id)``— counts for the header widget
  * ``log_touch(...)``                  — visit/lit/phone, with yes/maybe/no
  * ``list_touches(sos_voterid)``       — history for one voter

Everything else is private helpers.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "local" / "captain.db"

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

# Single sqlite3.Connection per process. Reads are concurrent under WAL mode;
# writes serialize via a re-entrant lock so the few captain.db writes don't
# fight each other when the API handles multiple GETs at the same time.
_conn: sqlite3.Connection | None = None
_lock = threading.RLock()


# ──────────────────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS captain (
    id              INTEGER PRIMARY KEY,
    display_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT NOT NULL,
    -- digits-only normalized phone, used for de-dup once SaaS hosting lets
    -- multiple captains share a precinct. Captured now so the rewrite later
    -- doesn't have to backfill against unstructured input.
    phone_digits    TEXT NOT NULL,
    precinct_county TEXT NOT NULL,
    precinct_name   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS voter_touch (
    id              INTEGER PRIMARY KEY,
    sos_voterid     TEXT NOT NULL,
    captain_id      INTEGER NOT NULL REFERENCES captain(id),
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
-- defined it. The captain's clicking "Pure D" on Kettering 1-A and clicking
-- "Millennials" later are two distinct lists, with their own progress and
-- their own statuses. find_or_create_walk_list() makes the lookup idempotent:
-- re-clicking the same filter resumes the same list.
CREATE TABLE IF NOT EXISTS walk_list (
    id              INTEGER PRIMARY KEY,
    captain_id      INTEGER NOT NULL REFERENCES captain(id),
    precinct_county TEXT NOT NULL,
    precinct_name   TEXT NOT NULL,
    filter_kind     TEXT NOT NULL,   -- 'cohort'|'generation'|'cohort_generation'
    filter_value    TEXT NOT NULL,   -- e.g. 'PURE_D' or 'PURE_D|Millennials'
    filter_label    TEXT NOT NULL,   -- human: 'Pure D Millennials'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (captain_id, precinct_county, precinct_name, filter_kind, filter_value)
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
        _conn.executescript(SCHEMA)
        return _conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


# ──────────────────────────────────────────────────────────────────────────
# Captain
# ──────────────────────────────────────────────────────────────────────────

_DIGITS_RE = re.compile(r"\D+")


def _normalize_phone(raw: str) -> str:
    return _DIGITS_RE.sub("", raw or "")


def get_captain() -> dict | None:
    """Single-captain-per-device mode: return the (lowest-id) row, or None.

    When the hosted tier ships, this becomes a session lookup; the call sites
    in roster_api.py shouldn't have to care about the change.
    """
    with _lock:
        cur = connect().execute(
            "SELECT * FROM captain ORDER BY id ASC LIMIT 1"
        )
        return _row_to_dict(cur.fetchone())


def create_captain(
    *, display_name: str, email: str, phone: str,
    precinct_county: str, precinct_name: str,
) -> dict:
    """Insert (and return) the captain row. Required fields must be non-empty.

    Localhost prototype: we don't enforce uniqueness. A second call overwrites
    nothing — it just creates another row, and get_captain() picks the first.
    That keeps the UX of "let me re-do the picker" from getting stuck.
    """
    for label, val in [("display_name", display_name), ("email", email),
                       ("phone", phone), ("precinct_county", precinct_county),
                       ("precinct_name", precinct_name)]:
        if not val or not str(val).strip():
            raise ValueError(f"{label} required")
    with _lock:
        cur = connect().execute(
            "INSERT INTO captain (display_name, email, phone, phone_digits, "
            "precinct_county, precinct_name) VALUES (?, ?, ?, ?, ?, ?)",
            (display_name.strip(), email.strip(), phone.strip(),
             _normalize_phone(phone), precinct_county.strip(),
             precinct_name.strip()),
        )
        new_id = cur.lastrowid
        return _row_to_dict(connect().execute(
            "SELECT * FROM captain WHERE id = ?", (new_id,)
        ).fetchone())  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────────
# Walk lists
# ──────────────────────────────────────────────────────────────────────────

def find_or_create_walk_list(
    *, captain_id: int, precinct_county: str, precinct_name: str,
    filter_kind: str, filter_value: str, filter_label: str,
    seed_voter_ids: list[str],
) -> dict:
    """Look up a walk list by (captain, precinct, filter); create it if absent.

    On create, seed walk_list_voter with status='queued' for every voter id in
    seed_voter_ids. On re-find, do NOT re-seed — preserve existing statuses so
    re-clicking the same chart resumes the same walk.

    Why "find or create": the captain's click on the Pure D bar is both
    "filter the roster" AND "this is my walk list" — see scope discussion.
    """
    if filter_kind not in FILTER_KINDS:
        raise ValueError(f"unknown filter_kind '{filter_kind}'")
    with _lock:
        conn = connect()
        row = conn.execute(
            "SELECT * FROM walk_list WHERE captain_id = ? AND precinct_county = ? "
            "AND precinct_name = ? AND filter_kind = ? AND filter_value = ?",
            (captain_id, precinct_county, precinct_name, filter_kind, filter_value),
        ).fetchone()
        if row is not None:
            return _row_to_dict(row)  # type: ignore[return-value]
        cur = conn.execute(
            "INSERT INTO walk_list (captain_id, precinct_county, precinct_name, "
            "filter_kind, filter_value, filter_label) VALUES (?, ?, ?, ?, ?, ?)",
            (captain_id, precinct_county, precinct_name,
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
        # last touch against any voter in this walk list, by THIS captain
        last = conn.execute(
            "SELECT MAX(t.touched_at) AS last_touched_at "
            "FROM voter_touch t "
            "JOIN walk_list_voter wlv ON wlv.sos_voterid = t.sos_voterid "
            "JOIN walk_list wl ON wl.id = wlv.walk_list_id "
            "WHERE wlv.walk_list_id = ? AND t.captain_id = wl.captain_id",
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
    *, sos_voterid: str, captain_id: int,
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
            "INSERT INTO voter_touch (sos_voterid, captain_id, precinct_county, "
            "precinct_name, kind, outcome, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sos_voterid, captain_id, precinct_county, precinct_name,
             kind, outcome, notes),
        )
        tid = cur.lastrowid
        return _row_to_dict(connect().execute(
            "SELECT * FROM voter_touch WHERE id = ?", (tid,)
        ).fetchone())  # type: ignore[return-value]


def list_touches(sos_voterid: str, *, captain_id: int | None = None) -> list[dict]:
    """Touches for one voter, newest first. captain_id filter is reserved for
    the future hosted multi-captain world; today there's only one captain so
    it's effectively a no-op."""
    with _lock:
        sql = "SELECT * FROM voter_touch WHERE sos_voterid = ?"
        args: list[Any] = [sos_voterid]
        if captain_id is not None:
            sql += " AND captain_id = ?"
            args.append(captain_id)
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
    #   .venv\Scripts\python.exe serve\captain_db.py
    connect()
    print(f"DB at {DB_PATH}")
    print(f"Existing captain: {get_captain()}")
