"""pdf_to_markdown.py — batch-convert BoE PDFs to LLM-ready markdown.

Converts one or more PDF files to .md using pymupdf4llm and writes the
result alongside the source file.  Intended for preprocessing BoE filing
reports so future agent sessions can Read the .md directly (no PDF lib
needed in-context, no token overhead from raw PDF parsing).

Usage:
    python tools/admin/pdf_to_markdown.py path/to/file.pdf [file2.pdf ...]
    python tools/admin/pdf_to_markdown.py --all          # all PDFs under local/source/County Data Files/
    python tools/admin/pdf_to_markdown.py --all --force  # overwrite existing .md files

Output: <same directory>/<basename>.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root: tools/admin/ -> tools/ -> repo root
ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_SOURCE = ROOT / "local" / "source" / "County Data Files"


def convert(pdf_path: Path, force: bool = False) -> tuple[bool, int, int]:
    """Convert a single PDF to markdown.  Returns (skipped, pdf_bytes, md_bytes)."""
    md_path = pdf_path.with_suffix(".md")
    if md_path.exists() and not force:
        if md_path.stat().st_mtime >= pdf_path.stat().st_mtime:
            print(f"  SKIP  {pdf_path.name}  (already exists and is up-to-date, use --force to overwrite)")
            return True, 0, 0

    try:
        import fitz
        import pymupdf4llm  # noqa: PLC0415
    except ImportError:
        print("ERROR: pymupdf or pymupdf4llm not installed.  Run: uv add pymupdf", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(pdf_path)
    
    # Fast-Pass Vector Scanning
    for page in doc:
        drawings = page.get_drawings()
        
        # 1. Density Fast-Pass: skip if overwhelmingly dense (maps, graphics)
        if len(drawings) > 1000:
            continue
            
        # 2. Geometric Strictness & O(N) Geometry Fast-Pass
        checkboxes = []
        for d in drawings:
            rects = [item for item in d.get("items", []) if item[0] == "re"]
            if len(rects) == 1 and d.get("type") == "s":
                rect = rects[0][1]
                # Checkboxes must be perfect squares (abs width-height < 2) 5-20px wide
                if 5 < rect.width < 20 and 5 < rect.height < 20 and abs(rect.width - rect.height) < 2:
                    checkboxes.append(rect)
                    
        # Bypass thorough scan if zero shapes meet criteria
        if not checkboxes:
            continue
            
        # Extract checkmarks
        checkmarks = [d["rect"] for d in drawings if d.get("type") == "s" and len([item for item in d.get("items", []) if item[0] == "l"]) == 2]

        # 3. Optimized Thorough Scan (Y-Coordinate Bounding)
        for box in checkboxes:
            # Only test intersections against checkmarks on the same Y-band
            is_checked = False
            for cm in checkmarks:
                if abs(cm.y0 - box.y0) < 10 or abs(cm.y1 - box.y1) < 10:
                    if box.intersects(cm):
                        is_checked = True
                        break
                        
            text = "[x]" if is_checked else "[ ]"
            page.insert_text((box.x0, box.y1), text, fontsize=10, fontname="helv", color=(0,0,0))

    md_text = pymupdf4llm.to_markdown(doc)
    doc.close()
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
