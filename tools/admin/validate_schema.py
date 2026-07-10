"""validate_schema.py -- generate the structural inventory the schema/ docs own.

Renamed 2026-07 from dump_schema.py to validate_schema.py so its name carries the
same validate_* verb as validate_officials.py and validate_jurisdiction_fields.py
(the other two integrity gates in this folder) -- "dump" undersold that --check
mode is a real drift gate, not just a generator. All function/CLI-flag names are
unchanged (generate_blocks(), check_drift(), --check). If anything still imports
this module by its old filename/path (validate_officials.py did, see below --
already updated), update the reference.

schema/README.md splits every schema doc into two parts with different owners:
  1. Structural inventory  -- GENERATED here, never hand-typed (column names/dtypes,
     JSON key shapes). Regenerate; do not edit by hand.
  2. Semantic annotations  -- hand-written, human-ratified ("why"). NEVER touched here.

This script introspects the live artifacts (enriched_voters.parquet schema, each
serve/*.json) and writes the inventory into a clearly-separated, marker-delimited
block inside the target doc. Everything outside the markers -- the hand-written
annotations -- is preserved byte-for-byte. validate_officials.py imports
`generate_blocks()` to regenerate-and-compare without writing (the drift gate).

The JSON summarizer collapses a dynamic-keyed map (precinct names, district ids) to
a single `<key>` representative so that adding a precinct is a *data* change, not a
*schema* change -- only real shape changes trip the drift gate.

HOST: run on Windows / Claude Code CLI. The Cowork sandbox serves byte-capped reads
and cannot reliably read the parquet (schema/README.md host note).

Usage:
    python tools/admin/validate_schema.py            # write/refresh the generated blocks
    python tools/admin/validate_schema.py --check    # exit 1 if any block is out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from officials_common import ENRICHED_PARQUET, ROOT  # noqa: E402

SCHEMA_DIR = ROOT / "schema"
SERVE_DIR = ROOT / "serve"

MARK_BEGIN = "<!-- BEGIN GENERATED INVENTORY -- dump_schema.py; do not edit by hand -->"
MARK_END = "<!-- END GENERATED INVENTORY -->"


# -- JSON shape summarizer ----------------------------------------------------

def _scalar(obj) -> tuple:
    if obj is None:
        return ("scalar", "null")
    if isinstance(obj, bool):
        return ("scalar", "bool")
    if isinstance(obj, int):
        return ("scalar", "int")
    if isinstance(obj, float):
        return ("scalar", "float")
    return ("scalar", "str")


def _kind_label(shape: tuple) -> str:
    return {"obj": "object", "map": "map", "list": "list"}.get(shape[0], shape[1])


def merge(a: tuple, b: tuple) -> tuple:
    """Union two shapes into one (used to merge a map's many values)."""
    if a == b:
        return a
    ka, kb = a[0], b[0]
    if ka == "scalar" and kb == "scalar":
        types = sorted(set(a[1].split("|")) | set(b[1].split("|")))
        return ("scalar", "|".join(types))
    if ka == "list" and kb == "list":
        if a[1] is None:
            return b
        if b[1] is None:
            return a
        return ("list", merge(a[1], b[1]))
    if ka == "map" and kb == "map":
        return ("map", merge(a[1], b[1]))
    if ka == "obj" and kb == "obj":
        da = {k: (o, s) for k, o, s in a[1]}
        db = {k: (o, s) for k, o, s in b[1]}
        fields = []
        for k in sorted(set(da) | set(db)):
            if k in da and k in db:
                oa, sa = da[k]
                ob, sb = db[k]
                fields.append((k, oa or ob, merge(sa, sb)))
            elif k in da:
                fields.append((k, True, da[k][1]))
            else:
                fields.append((k, True, db[k][1]))
        return ("obj", fields)
    return ("scalar", "|".join(sorted({_kind_label(a), _kind_label(b)})))


def _merge_values_as_obj(dicts: list[dict], depth: int) -> tuple:
    """Merge a map's dict-values into one obj shape, marking optional keys."""
    n = len(dicts)
    counts: dict[str, int] = {}
    shapes: dict[str, tuple] = {}
    for d in dicts:
        for k, v in d.items():
            counts[k] = counts.get(k, 0) + 1
            s = shape(v, depth)
            shapes[k] = s if k not in shapes else merge(shapes[k], s)
    return ("obj", [(k, counts[k] < n, shapes[k]) for k in sorted(counts)])


def shape(obj, depth: int = 0) -> tuple:
    """Canonical structural shape of a JSON value (data-independent)."""
    if isinstance(obj, list):
        if not obj:
            return ("list", None)
        merged = None
        for el in obj:
            s = shape(el, depth + 1)
            merged = s if merged is None else merge(merged, s)
        return ("list", merged)
    if isinstance(obj, dict):
        vals = list(obj.values())
        # A dict is a dynamic MAP (collapse keys) when its values are homogeneous
        # records: all dicts and either identical key-sets, or simply many of them.
        # depth 0 (the root) is always a fixed contract -- never collapse sections.
        is_map = (
            depth > 0 and len(vals) >= 2 and all(isinstance(v, dict) for v in vals)
            and (len({frozenset(v) for v in vals}) == 1 or len(vals) >= 8)
        )
        if is_map:
            return ("map", _merge_values_as_obj(vals, depth + 1))
        return ("obj", [(k, False, shape(obj[k], depth + 1)) for k in sorted(obj)])
    return _scalar(obj)


def _emit(lines: list[str], name: str, sh: tuple, indent: int, optional: bool) -> None:
    pad = "    " * indent
    opt = "?" if optional else ""
    kind = sh[0]
    if kind == "scalar":
        lines.append(f"{pad}- {name}{opt}: {sh[1]}")
    elif kind == "obj":
        lines.append(f"{pad}- {name}{opt}: {{object}}")
        for k, o, cs in sh[1]:
            _emit(lines, k, cs, indent + 1, o)
    elif kind == "map":
        lines.append(f"{pad}- {name}{opt}: {{map of dynamic keys}}")
        _emit(lines, "<key>", sh[1], indent + 1, False)
    elif kind == "list":
        if sh[1] is None:
            lines.append(f"{pad}- {name}{opt}: [empty list]")
        else:
            lines.append(f"{pad}- {name}{opt}: [list]")
            _emit(lines, "<item>", sh[1], indent + 1, False)


def json_inventory(path: Path) -> str:
    obj = json.loads(path.read_text(encoding="utf-8"))
    root = shape(obj, 0)  # forced contract at depth 0
    lines: list[str] = [f"Structure of `{path.relative_to(ROOT).as_posix()}`:", "", "```"]
    if root[0] == "obj":
        for k, o, cs in root[1]:
            _emit(lines, k, cs, 0, o)
    else:
        _emit(lines, "<root>", root, 0, False)
    lines.append("```")
    return "\n".join(lines)


# -- parquet inventory --------------------------------------------------------

def parquet_inventory() -> str:
    import polars as pl  # local import; only this path needs polars

    schema = pl.scan_parquet(ENRICHED_PARQUET).collect_schema()
    lines = [
        f"Columns of `{ENRICHED_PARQUET.relative_to(ROOT).as_posix()}` "
        f"({len(schema.names())} total):", "",
        "| column | dtype |", "|--------|-------|",
    ]
    for name in schema.names():  # parquet column order, deterministic
        lines.append(f"| `{name}` | {schema[name]} |")
    return "\n".join(lines)


# -- target docs --------------------------------------------------------------

def _targets() -> list[tuple[Path, str, callable]]:
    """(doc_path, source_artifact_label, block_builder). Skipped if source missing."""
    return [
        (SCHEMA_DIR / "enriched" / "enriched_voters.md", str(ENRICHED_PARQUET),
         parquet_inventory),
        (SCHEMA_DIR / "serve" / "officials.md", str(SERVE_DIR / "officials.json"),
         lambda: json_inventory(SERVE_DIR / "officials.json")),
        (SCHEMA_DIR / "serve" / "precinct_captains.md",
         str(SERVE_DIR / "precinct_captains.json"),
         lambda: json_inventory(SERVE_DIR / "precinct_captains.json")),
        (SCHEMA_DIR / "serve" / "candidates.md", str(SERVE_DIR / "candidates.json"),
         lambda: json_inventory(SERVE_DIR / "candidates.json")),
        (SCHEMA_DIR / "serve" / "partisan_profiles.md",
         str(SERVE_DIR / "partisan_profiles.json"),
         lambda: json_inventory(SERVE_DIR / "partisan_profiles.json")),
    ]


def _wrap(block_body: str) -> str:
    return f"{MARK_BEGIN}\n\n{block_body}\n\n{MARK_END}"


def _extract_block(text: str) -> str | None:
    """Return the current generated block (markers included), or None if absent."""
    if MARK_BEGIN not in text or MARK_END not in text:
        return None
    start = text.index(MARK_BEGIN)
    end = text.index(MARK_END) + len(MARK_END)
    return text[start:end]


def generate_blocks() -> dict[Path, str]:
    """Build the up-to-date generated block (markers included) per existing target."""
    blocks: dict[Path, str] = {}
    for doc_path, source, builder in _targets():
        if not Path(source).exists():
            continue  # source artifact not produced yet (e.g. partisan_profiles.json)
        blocks[doc_path] = _wrap(builder())
    return blocks


def write_blocks() -> int:
    written = 0
    for doc_path, fresh in generate_blocks().items():
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        if doc_path.exists():
            text = doc_path.read_text(encoding="utf-8")
            current = _extract_block(text)
            if current is not None:
                new_text = text.replace(current, fresh)
            else:
                sep = "" if text.endswith("\n") else "\n"
                new_text = f"{text}{sep}\n## Generated structural inventory\n\n{fresh}\n"
        else:
            new_text = (f"# `{doc_path.stem}` -- generated inventory\n\n"
                        f"{fresh}\n")
        doc_path.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"[ok] {doc_path.relative_to(ROOT).as_posix()}")
        written += 1
    return written


def check_drift() -> list[str]:
    """Return human-readable problems; empty list means in sync."""
    problems: list[str] = []
    for doc_path, fresh in generate_blocks().items():
        rel = doc_path.relative_to(ROOT).as_posix()
        if not doc_path.exists():
            problems.append(f"{rel}: missing (run dump_schema.py)")
            continue
        current = _extract_block(doc_path.read_text(encoding="utf-8"))
        if current is None:
            problems.append(f"{rel}: no generated block (run dump_schema.py)")
        elif current.replace("\r\n", "\n").strip() != fresh.strip():
            problems.append(f"{rel}: generated inventory is STALE (run dump_schema.py)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate/verify schema structural inventory.")
    ap.add_argument("--check", action="store_true",
                    help="verify blocks are current; exit 1 if stale (no writes)")
    args = ap.parse_args()

    if args.check:
        problems = check_drift()
        if problems:
            print("SCHEMA DRIFT:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("[ok] schema inventory in sync")
        return 0

    n = write_blocks()
    print(f"[done] refreshed {n} generated inventory block(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
