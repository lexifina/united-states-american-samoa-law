"""Fetcher for the Liberia law sources: a thin wrapper around the shared africa-law Cache (read-only import).

curl with --compressed, cache under .cache/ named by sha256(url), every request logged to .cache/requests.jsonl,
archive.org through gitlaw_common/wayback.py (one adaptive rate for the machine), other hosts 5 s.

    python -X utf8 fetch.py URL [URL ...]     fetch (or read from cache) and print sha256 + size
    python -X utf8 fetch.py --plan            fetch every URL parse.py needs (sources.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
from peachjam import Cache  # noqa: E402

CACHE = Cache(HERE)


sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import wayback  # noqa: E402


def get(url: str) -> bytes:
    """archive.org through the shared adaptive client (coordinator, 21:45Z); other hosts through the Cache (5 s)."""
    if url.startswith("https://web.archive.org/"):
        b = wayback.fetch(url, CACHE.dir)
        if b is None:
            raise RuntimeError(f"not archived: {url}")
        return b
    return CACHE.get(url)


def main(argv: list[str]) -> None:
    urls = argv
    if argv and argv[0] == "--plan":
        urls = [s["url"] for s in json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["files"]]
    for u in urls:
        try:
            b = get(u)
            print(CACHE.sha256(u)[:16], len(b), u)
        except Exception as e:  # noqa: BLE001
            print("FAIL", e)


if __name__ == "__main__":
    main(sys.argv[1:])
