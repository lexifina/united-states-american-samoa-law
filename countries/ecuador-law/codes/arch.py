"""Read-only index copies through the shared archive client (Common Crawl first, then archive.org).

    python -X utf8 codes/arch.py cc <url>          Common Crawl captures (newest 6 crawls)
    python -X utf8 codes/arch.py cdx <url>         archive.org captures
    python -X utf8 codes/arch.py get <url> [ts]    archive.org id_ bytes -> prints cache path
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / ".cache"
sys.path.insert(0, r"C:/Users/alany/Documents/lexifina/scripts/gitlaw_common")
import wayback  # noqa: E402


def main(argv: list[str]) -> None:
    cmd, url = argv[0], argv[1]
    if cmd == "cc":
        try:
            crawls = wayback.cc_crawls(CACHE)[:6]
            recs = wayback.cc_captures(url, crawls=crawls, cache=CACHE)
            print(json.dumps(recs, indent=1)[:3000])
        except Exception as e:  # noqa: BLE001
            print("Common Crawl failed:", e)
    elif cmd == "cdx":
        for r in wayback.captures(url, cache=CACHE, collapse=None):
            print(r)
    elif cmd == "get":
        ts = argv[2] if len(argv) > 2 else "2"
        b = wayback.get(url, ts=ts, cache=CACHE)
        full = f"https://web.archive.org/web/{ts}id_/{url}"
        print(len(b) if b else None, CACHE / hashlib.sha256(full.encode()).hexdigest())


if __name__ == "__main__":
    main(sys.argv[1:])
