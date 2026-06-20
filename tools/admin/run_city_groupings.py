#!/usr/bin/env python
"""Direct runner for city groupings — bypasses pipeline menu."""
import sys
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(_ROOT)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline import jurisdictional_groupings as jg

logger, log_file = jg.setup_logger()
logger.info("=" * 70)
logger.info("RUNNING: Generate city-level chart JSON files")
logger.info("=" * 70)

try:
    jg.main(jurisdictions_to_process=['cities'], output_format='json', logger=logger)
    logger.info("=" * 70)
    logger.info("✓ SUCCESS: City groupings generated in docs/data/")
    logger.info("=" * 70)
except Exception as e:
    logger.error(f"✗ FAILED: {e}", exc_info=True)
    sys.exit(1)
