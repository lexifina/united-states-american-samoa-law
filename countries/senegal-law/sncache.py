"""Senegal: one cached fetch for every source.

- archive.org (Wayback `id_` captures, CDX) goes through scripts/gitlaw_common/wayback.py, which keeps one adaptive
  rate for the whole machine (coordinator, FANOUT.md "FAST ARCHIVE ACCESS").
- Common Crawl (wayback.cc_captures / cc_get) is used first where it holds the page.
- Government and court sites are read directly with peachjam.Cache at 1 request per second.
Every response is cached in .cache/ under sha256(url) and logged to .cache/requests.jsonl.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
sys.path.insert(0, str(HERE.parent / "africa-law"))
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import peachjam  # noqa: E402  (read-only shared adapter: its curl cache)
import wayback  # noqa: E402  (read-only shared archive client)

WAYBACK = "https://web.archive.org"


def _direct(offline: bool) -> peachjam.Cache:
    return peachjam.Cache(HERE, offline=offline)


def path(url: str) -> Path:
    return _direct(True).path(url)


def raw(ts: str, orig: str) -> str:
    """The Wayback raw (`id_`) form of a capture."""
    return f"{WAYBACK}/web/{ts}id_/{orig}"


def get(url: str, offline: bool = False) -> bytes:
    p = path(url)
    if p.exists():
        return p.read_bytes()
    if offline:
        raise FileNotFoundError(f"not in cache (run fetch.py): {url}")
    if url.startswith(WAYBACK):
        b = wayback.fetch(url, CACHE)
        if b is None:
            raise RuntimeError(f"archive.org has no such capture: {url}")
        return b
    host = url.split("/")[2]
    peachjam.CRAWL_DELAY.setdefault(host, 1.0)  # government/court hosts: 1 request per second
    return _direct(False).get(url)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for u in sys.argv[1:]:
        b = get(u)
        print(u, len(b), path(u))
