#!/usr/bin/env python3
"""
roster_api.py — gated PII-roster backend (PROTOTYPE).

Serves named-voter rosters (first/last/address/city/precinct + last-voted
dates) filtered by jurisdiction and cohort. This is the *gated* counterpart to
the public aggregate dashboard: it reads PII straight from the enriched parquet
and is intended to run ONLY on localhost behind a token. Nothing it returns may
ever be written into docs/ or committed.

Design decisions (see CLAUDE.md + the prototyping discussion):

  * Reads ``local/source/parquet_enriched/enriched_voters.parquet`` — the same
    cache the weekly pipeline rebuilds. We never re-run cleaning here.
  * Weekly-refresh aware: the loaded frame is cached in-process, but its source
    mtime is checked on every request. When the pipeline rewrites the parquet
    (atomic .replace), the next request transparently reloads it. No restart.
  * "Last voted primary/general" are DERIVED at load time from the 89 election
    columns (``PRIMARY-MM/DD/YYYY`` / ``GENERAL-MM/DD/YYYY``). Those columns are
    not chronologically ordered and are sparse (a value exists only if the voter
    cast that ballot), so we parse the date out of each column NAME and keep the
    max non-empty one per voter. Done once per load, not per query.
  * Auth: a single bearer token from ROSTER_TOKEN. Prototype-grade — replace
    with real session auth before this is exposed beyond localhost.
  * Stdlib http.server only — zero new deps. Swap for FastAPI/uvicorn when the
    gated web app is built for real.

Run:
    ROSTER_TOKEN=dev-secret .venv/Scripts/python.exe serve/roster_api.py
    # then:  GET http://127.0.0.1:8000/roster?level=county&id=01&cohort=PURE_R
    #        Authorization: Bearer dev-secret
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import date
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import polars as pl

BASE_DIR = Path(__file__).resolve().parent.parent
ENRICHED_CACHE = BASE_DIR / "local" / "source" / "parquet_enriched" / "enriched_voters.parquet"
# Captain prototype pages, served same-origin so their fetch()/downloads work.
PREVIEW_PAGE = BASE_DIR / "local" / "roster_preview" / "preview.html"   # mobile
PC_PAGE      = BASE_DIR / "local" / "roster_preview" / "pc.html"        # desktop

HOST = os.environ.get("ROSTER_HOST", "127.0.0.1")
PORT = int(os.environ.get("ROSTER_PORT", "8000"))
TOKEN = os.environ.get("ROSTER_TOKEN", "")

# The 7 cohort_family values that back the 7 chart slices. A roster request
# carries the cohort the user clicked; we validate against this set so a typo'd
# cohort yields an empty roster, not an unfiltered name dump.
VALID_COHORTS = {
    "PURE_R", "UNC_LAPSED_R", "MIXED_ACTIVE", "MIXED_LAPSED",
    "UNC_NO_PRIMARY", "UNC_LAPSED_D", "PURE_D",
}

# Ordered cohort spec: (slug, human label, chart color). Order is the
# partisan-spectrum left-to-right used by the dashboard charts. The human label
# is what a precinct captain reads; the slug never surfaces to them. Colors match
# COHORT_SLICES in pipeline/voter_data_cleaner.py so the bar a captain taps is the
# same color as the roster header they get back.
COHORT_SPEC = [
    ("PURE_R",         "Solid Republican",       "#ef4444"),
    ("UNC_LAPSED_R",   "Lapsed Republican",      "#fca5a5"),
    ("MIXED_ACTIVE",   "Mixed – Active",    "#f59e0b"),
    ("MIXED_LAPSED",   "Mixed – Lapsed",    "#a78bfa"),
    ("UNC_NO_PRIMARY", "No Primary History",     "#9ca3af"),
    ("UNC_LAPSED_D",   "Lapsed Democrat",        "#93c5fd"),
    ("PURE_D",         "Solid Democrat",         "#3b82f6"),
]
COHORT_LABELS = {slug: label for slug, label, _ in COHORT_SPEC}

# Jurisdiction levels the field needs. Each maps the request's ``level`` to the
# parquet column it filters on. ``county`` filters on COUNTY_NUMBER (zero-padded
# 2-digit). ``precinct`` additionally needs a county to disambiguate (precinct
# names collide across counties — see CLAUDE.md county-scoped note).
LEVEL_COLUMN = {
    "county": "COUNTY_NUMBER",
    "precinct": "PRECINCT_NAME",
    "congressional_district": "CONGRESSIONAL_DISTRICT",
    "state_senate_district": "STATE_SENATE_DISTRICT",
    "state_representative_district": "STATE_REPRESENTATIVE_DISTRICT",
    "township": "TOWNSHIP",
    "village": "VILLAGE",
    "city": "CITY",
}

# Jurisdiction columns surfaced on every roster row so a canvasser in the field
# sees all the districts a voter sits in, not just the one they filtered by.
JURISDICTION_COLS = [
    "PRECINCT_NAME", "TOWNSHIP", "VILLAGE", "WARD",
    "CONGRESSIONAL_DISTRICT", "STATE_SENATE_DISTRICT",
    "STATE_REPRESENTATIVE_DISTRICT", "LOCAL_SCHOOL_DISTRICT",
]

_ELEC_RE = re.compile(r"^(PRIMARY|GENERAL)-(\d{2})/(\d{2})/(\d{4})$")

_lock = threading.Lock()
_loaded: dict[str, object] = {"mtime": None, "df": None}


def _derive_last_voted(lf: pl.LazyFrame, cols: list[str], kind: str) -> pl.Expr:
    """Build an expr giving the most-recent date (ISO str) the voter cast a
    ``kind`` ('PRIMARY'|'GENERAL') ballot. A cell is "voted" when non-empty.

    The date lives in the column NAME, so we fold across the relevant columns
    keeping the max name-date wherever the cell is populated. Voters with no such
    ballot get null.
    """
    dated = []
    for c in cols:
        m = _ELEC_RE.match(c)
        if not m or m.group(1) != kind:
            continue
        _, mm, dd, yyyy = m.groups()
        iso = f"{yyyy}-{mm}-{dd}"
        # when this ballot was cast (cell non-empty/non-null), contribute its date
        dated.append(
            pl.when(pl.col(c).cast(pl.Utf8).str.strip_chars().str.len_chars() > 0)
              .then(pl.lit(iso))
              .otherwise(None)
        )
    if not dated:
        return pl.lit(None, dtype=pl.Utf8).alias(f"last_{kind.lower()}")
    return pl.max_horizontal(dated).alias(f"last_{kind.lower()}")


def _load(path: Path) -> pl.DataFrame:
    """Load the enriched parquet, projecting only roster-relevant columns and
    attaching derived last-voted dates. Heavy; called once per cache mtime."""
    schema_names = list(pl.scan_parquet(path).collect_schema().names())
    elec_cols = [c for c in schema_names if _ELEC_RE.match(c)]

    base_cols = [
        "SOS_VOTERID", "FIRST_NAME", "LAST_NAME",
        "RESIDENTIAL_ADDRESS1", "CITY", "RESIDENTIAL_CITY", "RESIDENTIAL_ZIP",
        "COUNTY_NUMBER", "cohort_family",
        "PRECINCT_CODE", "PARTY_AFFILIATION",
    ]
    keep = [c for c in dict.fromkeys(base_cols + JURISDICTION_COLS) if c in schema_names]

    lf = pl.scan_parquet(path)
    df = (
        lf.select(keep + elec_cols)
          .with_columns([
              _derive_last_voted(lf, elec_cols, "PRIMARY"),
              _derive_last_voted(lf, elec_cols, "GENERAL"),
              # CITY is blank in ~19 counties; fall back to residential city.
              # Both arrive as empty strings (not null), so normalize "" → null
              # before coalescing, or the empty CITY would shadow RESIDENTIAL_CITY.
              pl.coalesce([
                  pl.col("CITY").cast(pl.Utf8).str.strip_chars()
                    .replace("", None),
                  pl.col("RESIDENTIAL_CITY").cast(pl.Utf8).str.strip_chars()
                    .replace("", None),
              ]).alias("_city"),
          ])
          .drop(elec_cols)
          .collect()
    )
    return df


def get_df() -> pl.DataFrame:
    """Return the roster frame, reloading transparently if the weekly pipeline
    has rewritten the parquet since we last loaded it."""
    if not ENRICHED_CACHE.exists():
        raise FileNotFoundError(
            f"enriched cache missing: {ENRICHED_CACHE} — run the pipeline first"
        )
    mtime = ENRICHED_CACHE.stat().st_mtime
    with _lock:
        if _loaded["mtime"] != mtime:
            _loaded["df"] = _load(ENRICHED_CACHE)
            _loaded["mtime"] = mtime
        return _loaded["df"]  # type: ignore[return-value]


def _roster_frame(level: str, jid: str, cohort: str, county: str | None) -> pl.DataFrame:
    """Apply the jurisdiction+cohort filter and return the matched frame, sorted
    by name. Shared by the JSON roster and the file exports so both see exactly
    the same set of voters."""
    df = get_df()
    col = LEVEL_COLUMN[level]
    flt = pl.col("cohort_family") == cohort
    if level == "county":
        flt = flt & (pl.col("COUNTY_NUMBER").cast(pl.Utf8).str.zfill(2) == jid.zfill(2))
    else:
        flt = flt & (pl.col(col).cast(pl.Utf8) == jid)
        # precinct/township/village names collide across counties — scope by county
        if county is not None and "COUNTY_NUMBER" in df.columns:
            flt = flt & (pl.col("COUNTY_NUMBER").cast(pl.Utf8).str.zfill(2) == county.zfill(2))
    return df.filter(flt).sort(["LAST_NAME", "FIRST_NAME"])


# Columns exported to CSV/XLSX, in order: (frame column, header label).
EXPORT_COLUMNS = [
    ("LAST_NAME", "Last Name"),
    ("FIRST_NAME", "First Name"),
    ("RESIDENTIAL_ADDRESS1", "Address"),
    ("_city", "City"),
    ("RESIDENTIAL_ZIP", "ZIP"),
    ("last_primary", "Last Primary"),
    ("last_general", "Last General"),
    ("PRECINCT_NAME", "Precinct"),
    ("WARD", "Ward"),
    ("CONGRESSIONAL_DISTRICT", "U.S. Congress"),
    ("STATE_SENATE_DISTRICT", "State Senate"),
    ("STATE_REPRESENTATIVE_DISTRICT", "State House"),
]


def query_roster(level: str, jid: str, cohort: str, county: str | None,
                 limit: int, offset: int) -> dict:
    """Filter the roster frame by jurisdiction + cohort and shape rows for the UI."""
    if level not in LEVEL_COLUMN:
        return {"error": f"unknown level '{level}'", "valid": sorted(LEVEL_COLUMN)}
    if cohort not in VALID_COHORTS:
        return {"error": f"unknown cohort '{cohort}'", "valid": sorted(VALID_COHORTS)}

    matched = _roster_frame(level, jid, cohort, county)
    total = matched.height

    page = matched.slice(offset, limit)

    rows = []
    for r in page.iter_rows(named=True):
        rows.append({
            "first": r.get("FIRST_NAME"),
            "last": r.get("LAST_NAME"),
            "address": r.get("RESIDENTIAL_ADDRESS1"),
            "city": r.get("_city"),
            "zip": r.get("RESIDENTIAL_ZIP"),
            "last_primary": r.get("last_primary"),
            "last_general": r.get("last_general"),
            "cohort": r.get("cohort_family"),
            "jurisdictions": {
                k.lower(): r.get(k) for k in JURISDICTION_COLS if k in page.columns
            },
        })

    return {
        "level": level, "id": jid, "cohort": cohort, "county": county,
        "total": total, "offset": offset, "limit": limit,
        "returned": len(rows), "rows": rows,
        "generated": date.today().isoformat(),
    }


def precinct_summary(precinct: str, county: str) -> dict:
    """Per-cohort counts for one precinct, in chart order with labels + colors.

    This is the data behind the bar chart the captain taps. Returning the full
    COHORT_SPEC (even zero-count cohorts) keeps the chart shape stable across
    precincts so the captain always sees the same 7 bars in the same order.
    """
    df = get_df()
    flt = (pl.col("PRECINCT_NAME").cast(pl.Utf8) == precinct)
    if "COUNTY_NUMBER" in df.columns:
        flt = flt & (pl.col("COUNTY_NUMBER").cast(pl.Utf8).str.zfill(2) == county.zfill(2))
    p = df.filter(flt)
    counts = dict(
        p.group_by("cohort_family").agg(pl.len().alias("n"))
         .iter_rows()
    )
    bars = [
        {"cohort": slug, "label": label, "color": color, "count": int(counts.get(slug, 0))}
        for slug, label, color in COHORT_SPEC
    ]
    return {
        "precinct": precinct, "county": county,
        "total": p.height, "bars": bars,
        "generated": date.today().isoformat(),
    }


def _export_frame(level: str, jid: str, cohort: str, county: str | None) -> pl.DataFrame:
    """The exact rows an export contains: the full matched cohort projected to
    EXPORT_COLUMNS with human headers. No pagination — exports are complete."""
    matched = _roster_frame(level, jid, cohort, county)
    src_cols = [c for c, _ in EXPORT_COLUMNS if c in matched.columns]
    rename = {c: lbl for c, lbl in EXPORT_COLUMNS if c in matched.columns}
    return matched.select(src_cols).rename(rename)


def export_csv(level: str, jid: str, cohort: str, county: str | None) -> bytes:
    return _export_frame(level, jid, cohort, county).write_csv().encode("utf-8")


def export_xlsx(level: str, jid: str, cohort: str, county: str | None) -> bytes:
    """Build a printable .xlsx via xlsxwriter (per CLAUDE.md, the mandated path
    for stakeholder spreadsheet output). Frozen header row, auto-width, and the
    cohort label in the sheet name so a printed walk-list is self-identifying."""
    import io
    import xlsxwriter  # local import: only needed when an xlsx is actually requested

    frame = _export_frame(level, jid, cohort, county)
    label = COHORT_LABELS.get(cohort, cohort)
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    # Sheet name: Excel caps at 31 chars and forbids []:*?/\
    ws = wb.add_worksheet(label[:31].replace("/", "-") or "Roster")
    hdr = wb.add_format({"bold": True, "bg_color": "#366092", "font_color": "#FFFFFF", "border": 1})
    cell = wb.add_format({"border": 1})

    headers = frame.columns
    for c, h in enumerate(headers):
        ws.write(0, c, h, hdr)
    for r, row in enumerate(frame.iter_rows(), start=1):
        for c, val in enumerate(row):
            ws.write(r, c, "" if val is None else str(val), cell)

    # Auto-width: header vs. longest value, capped so the address column stays sane.
    for c, h in enumerate(headers):
        col_vals = frame[h].cast(pl.Utf8).fill_null("")
        width = min(max(len(h), int(col_vals.str.len_chars().max() or 0)) + 2, 40)
        ws.set_column(c, c, width)
    ws.freeze_panes(1, 0)
    wb.close()
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Localhost dashboard origin; tighten before any non-local deploy.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        if not TOKEN:
            return True  # no token configured → open (localhost prototype only)
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {TOKEN}"

    def do_OPTIONS(self):
        self._send(204, {})

    def _send_html(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, body: bytes, content_type: str, filename: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._send(200, {"ok": True, "cache_exists": ENRICHED_CACHE.exists()})
        # Serve the captain prototype page from the API itself so the page and
        # its fetch() calls share one origin (no CORS / sandbox / mixed-content).
        if parsed.path in ("/", "/index.html"):
            if PREVIEW_PAGE.exists():
                return self._send_html(200, PREVIEW_PAGE.read_text(encoding="utf-8"))
            return self._send_html(404, "<h1>preview page not found</h1>")
        if parsed.path == "/pc":
            if PC_PAGE.exists():
                return self._send_html(200, PC_PAGE.read_text(encoding="utf-8"))
            return self._send_html(404, "<h1>pc page not found</h1>")
        if parsed.path not in ("/roster", "/precinct-summary", "/export"):
            return self._send(404, {"error": "not found"})
        if not self._authed():
            return self._send(401, {"error": "unauthorized"})

        q = parse_qs(parsed.query)

        if parsed.path == "/export":
            level = q.get("level", ["county"])[0]
            jid = q.get("id", [""])[0]
            cohort = q.get("cohort", [""])[0]
            county = q.get("county", [None])[0]
            fmt = q.get("format", ["csv"])[0].lower()
            if level not in LEVEL_COLUMN:
                return self._send(400, {"error": f"unknown level '{level}'"})
            if cohort not in VALID_COHORTS:
                return self._send(400, {"error": f"unknown cohort '{cohort}'"})
            stem = f"{jid}_{cohort}_{date.today().isoformat()}".replace(" ", "_").replace("/", "-")
            if fmt == "xlsx":
                body = export_xlsx(level, jid, cohort, county)
                return self._send_file(
                    body,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    f"{stem}.xlsx",
                )
            body = export_csv(level, jid, cohort, county)
            return self._send_file(body, "text/csv; charset=utf-8", f"{stem}.csv")

        if parsed.path == "/precinct-summary":
            precinct = q.get("precinct", [""])[0]
            county = q.get("county", [""])[0]
            if not precinct or not county:
                return self._send(400, {"error": "precinct and county required"})
            return self._send(200, precinct_summary(precinct, county))

        level = (q.get("level", ["county"])[0])
        jid = q.get("id", [""])[0]
        cohort = q.get("cohort", [""])[0]
        county = q.get("county", [None])[0]
        try:
            limit = min(int(q.get("limit", ["100"])[0]), 1000)
            offset = max(int(q.get("offset", ["0"])[0]), 0)
        except ValueError:
            return self._send(400, {"error": "limit/offset must be integers"})

        result = query_roster(level, jid, cohort, county, limit, offset)
        code = 400 if "error" in result else 200
        self._send(code, result)

    def log_message(self, fmt, *args):  # quieter console
        pass


def main():
    if not TOKEN:
        print("WARNING: ROSTER_TOKEN unset - API is OPEN. Localhost-only use.")
    print(f"roster_api -> http://{HOST}:{PORT}  (cache: {ENRICHED_CACHE})")
    print("  GET /health")
    print("  GET /roster?level=county&id=01&cohort=PURE_R&limit=50")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
