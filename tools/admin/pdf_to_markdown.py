"""pdf_to_markdown.py — batch-convert BoE PDFs to LLM-ready markdown.

Converts one or more PDF files to .md using pymupdf4llm and writes the
result alongside the source file.  Intended for preprocessing BoE filing
reports so future agent sessions can Read the .md directly (no PDF lib
needed in-context, no token overhead from raw PDF parsing).

Usage:
    python tools/admin/pdf_to_markdown.py path/to/file.pdf [file2.pdf ...]
    python tools/admin/pdf_to_markdown.py --all          # all PDFs under local/source/
    python tools/admin/pdf_to_markdown.py --all --force  # overwrite existing .md files

Output: <same directory>/<basename>.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root: tools/admin/ -> tools/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_SOURCE = ROOT / "local" / "source"


def convert(pdf_path: Path, force: bool = False) -> tuple[bool, int, int]:
    """Convert a single PDF to markdown.  Returns (skipped, pdf_bytes, md_bytes)."""
    md_path = pdf_path.with_suffix(".md")
    if md_path.exists() and not force:
        print(f"  SKIP  {pdf_path.name}  (already exists, use --force to overwrite)")
        return True, 0, 0

    try:
        import pymupdf4llm  # noqa: PLC0415
    except ImportError:
        print("ERROR: pymupdf4llm not installed.  Run: pip install pymupdf4llm", file=sys.stderr)
        sys.exit(1)

    md_text = pymupdf4llm.to_markdown(str(pdf_path))
    md_path.write_text(md_text, encoding="utf-8")

    pdf_bytes = pdf_path.stat().st_size
    md_bytes  = md_path.stat().st_size
    return False, pdf_bytes, md_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert BoE PDFs to markdown for offline/LLM use.")
    parser.add_argument("files", nargs="*", type=Path, help="PDF file(s) to convert")
    parser.add_argument("--all",   action="store_true", help="Convert all PDFs under local/source/")
    parser.add_argument("--force", action="store_true", help="Overwrite existing .md files")
    args = parser.parse_args()

    if args.all:
        targets = sorted(LOCAL_SOURCE.rglob("*.pdf"))
        if not targets:
            print(f"No PDFs found under {LOCAL_SOURCE}")
            return
    elif args.files:
        targets = [Path(f).resolve() for f in args.files]
        missing = [t for t in targets if not t.exists()]
        if missing:
            for m in missing:
                print(f"ERROR: not found: {m}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)

    total_pdf = total_md = 0
    converted = skipped = 0

    for pdf in targets:
        print(f"  {'CONV' if not (pdf.with_suffix('.md').exists() and not args.force) else 'SKIP'}  {pdf.name}")
        was_skipped, pb, mb = convert(pdf, force=args.force)
        if was_skipped:
            skipped += 1
        else:
            converted += 1
            total_pdf += pb
            total_md  += mb
            ratio = (mb / pb * 100) if pb else 0
            print(f"        {pb:,} bytes -> {mb:,} bytes ({ratio:.0f}% of original)")

    print(f"\nDone: {converted} converted, {skipped} skipped.")
    if converted:
        print(f"Total: {total_pdf:,} PDF bytes -> {total_md:,} MD bytes")


if __name__ == "__main__":
    main()
