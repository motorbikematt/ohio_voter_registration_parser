#!/usr/bin/env python3
"""Archive CLAUDE.md or a memory file with an ISO timestamp before overwrite.

Invoke this BEFORE any Write or Edit that overwrites:
  - D:\\vibe\\election-data\\CLAUDE.md
  - any file under the Cowork memory directory (MEMORY.md, project_*.md, feedback_*.md, etc.)

The archive captures the prior version verbatim. Git then provides the diff
chain on top of that for any file already tracked.

Usage:
    python tools/archive_state.py <absolute_or_relative_path>

Destination layout:
    docs/archive/<filename>.<YYYY-MM-DDTHHMM>.md            -- project files (CLAUDE.md, repo-local .md)
    docs/archive/memory/<filename>.<YYYY-MM-DDTHHMM>.md     -- memory files (path contains a 'memory' segment)

Prints the archive path (project-relative) on stdout. Exits 0 on success;
1 on missing source or bad argument. Loud failures preferred -- this script
intentionally has no try/except.
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = PROJECT_ROOT / "docs" / "archive"


def archive(src: Path) -> Path:
    if not src.exists():
        print(f"missing source: {src}", file=sys.stderr)
        sys.exit(1)
    if not src.is_file():
        print(f"not a file: {src}", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now().strftime("%Y-%m-%dT%H%M")
    in_memory = "memory" in {p.lower() for p in src.parts}
    dest_dir = ARCHIVE_ROOT / "memory" if in_memory else ARCHIVE_ROOT
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{src.stem}.{ts}{src.suffix}"
    # Same-minute collisions: append a serial.
    serial = 2
    while dest.exists():
        dest = dest_dir / f"{src.stem}.{ts}-{serial}{src.suffix}"
        serial += 1

    shutil.copy2(src, dest)
    return dest


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: archive_state.py <path>", file=sys.stderr)
        sys.exit(1)
    src = Path(sys.argv[1]).expanduser().resolve()
    dest = archive(src)
    # Print project-relative if inside the project; otherwise absolute.
    try:
        rel = dest.relative_to(PROJECT_ROOT)
        print(rel.as_posix())
    except ValueError:
        print(str(dest))


if __name__ == "__main__":
    main()
