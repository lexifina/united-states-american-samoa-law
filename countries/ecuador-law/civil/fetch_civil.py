"""Fetch (or reuse from the cache) every source the Código Civil part needs, listed in civil/sources_civil.json.

Uses the country's fetch.py: curl --compressed, sha256-named cache, at most 1 request per second per host, every
request logged to .cache/requests.jsonl.

    python -X utf8 civil/fetch_civil.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402


def main() -> int:
    src = json.loads((HERE / "sources_civil.json").read_text(encoding="utf-8"))
    bad = 0
    for item in src.values():
        for u in item["urls"]:
            p = fetch.get(u, timeout=900)
            print("ok " if p else "FAILED", u)
            bad += p is None
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
