"""Probe helper: fetch one URL through the shared Peachjam cache (shared archive.org rate, logged), print a summary.

    python -X utf8 scripts/tanzania-law/probe.py <url> [maxchars]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
import peachjam  # noqa: E402

c = peachjam.Cache(HERE)
b = c.get(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
print(c.path(sys.argv[1]))
print(b[:n].decode("utf-8", "replace"))
