"""Probe helper: fetch one URL through the shared Peachjam cache (rate-limited, logged) and print where it is cached.

    python -X utf8 scripts/ghana-law/probe.py <url> [<url> ...]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
import peachjam  # noqa: E402

cache = peachjam.Cache(HERE)
for url in sys.argv[1:]:
    try:
        b = cache.get(url)
        print(len(b), cache.path(url), url)
    except RuntimeError as e:
        print("FAIL", e)
