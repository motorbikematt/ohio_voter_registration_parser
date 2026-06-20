"""Ensure project root is on sys.path so pipeline package is importable in tests."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
