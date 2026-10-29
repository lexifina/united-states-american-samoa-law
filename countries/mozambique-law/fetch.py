"""Mozambique (gitlaw-MZ): curl cache for official gazette / parliament PDFs and archive.org captures.

Reuses the shared Cache from scripts/africa-law/peachjam.py (read-only import): sha256(url) file names, curl with
--compressed, requests.jsonl log, archive.org spaced at 3 s across every process on the machine. Government hosts are
read at 1 request per second (FANOUT.md). archive.org goes through gitlaw_common/wayback.py.

    python -X utf8 scripts/mozambique-law/fetch.py URL [URL ...]   # fetch and print sha256 + size
    python -X utf8 scripts/mozambique-law/fetch.py --all          # everything in sources.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
import peachjam  # noqa: E402  (shared adapter, read-only)
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import wayback  # noqa: E402  (shared archive.org / Common Crawl client, coordinator 2026-10-28)

GOV_DELAY = 1.0


class Cache(peachjam.Cache):
    """Government hosts at 1 request/s; archive.org goes through wayback.fetch (one adaptive machine-wide rate)."""

    def _wait(self, host: str, delay: float) -> None:
        super()._wait(host, GOV_DELAY)

    def get(self, url: str, retries: int = 6) -> bytes:
        if url.startswith("https://web.archive.org/"):
            p = self.path(url)
            if p.exists():
                return p.read_bytes()
            if self.offline:
                raise FileNotFoundError(f"not in cache (run fetch.py): {url}")
            b = wayback.fetch(url, self.dir)
            if b is None:
                raise RuntimeError(f"fetch failed {url}")
            return b
        return super().get(url, retries)


def cache(offline: bool = False) -> Cache:
    return Cache(HERE, offline=offline)


def main(argv: list[str]) -> None:
    c = cache()
    urls = argv
    if argv == ["--all"]:
        src = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
        urls = [d["url"] for d in src["documents"]]
    for u in urls:
        try:
            b = c.get(u)
            print(c.sha256(u), len(b), u)
        except Exception as e:  # keep going; the log has the status
            print("FAIL", e, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
