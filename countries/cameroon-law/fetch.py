"""Polite, resumable, cached fetcher for the Cameroon law sources.

Every request goes through curl (Python TLS fails on this machine) with the lexifina-watch User-Agent:
at most 1 request per second per government host; archive.org through gitlaw_common/wayback.py (one shared adaptive rate).
Responses are cached under .cache/ by sha256(url); every network request is logged to .cache/requests.jsonl.
A cached URL is never fetched again.

    python -X utf8 fetch.py URL [URL ...]
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
_last: dict[str, float] = {}


def key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def path_for(url: str) -> Path:
    return CACHE / key(url)


def cached(url: str) -> bytes | None:
    p = path_for(url)
    return p.read_bytes() if p.exists() else None


def _delay(host: str) -> float:
    return 3.0 if host.endswith("archive.org") else 1.0


def get(url: str, *, retries: int = 3) -> bytes:
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n")
    p = path_for(url)
    if p.exists():
        return p.read_bytes()
    host = urlparse(url).netloc
    if host.endswith("archive.org"):
        # archive.org goes through the shared, machine-wide adaptive client (same cache layout and log).
        sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
        import wayback
        b = wayback.fetch(url, cache=CACHE)
        if b is None:
            raise RuntimeError(f"fetch failed 404 {url}")
        return b
    code = "000"
    for attempt in range(retries):
        wait = _delay(host) - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        tmp = p.with_suffix(".part")
        t0 = time.time()
        r = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--max-time", "180", "-A", UA, "-o", str(tmp),
             "-w", "%{http_code} %{content_type}", url.replace(" ", "%20")],
            capture_output=True, text=True)
        _last[host] = time.time()
        code, _, ctype = (r.stdout or "000 ").partition(" ")
        size = tmp.stat().st_size if tmp.exists() else 0
        with open(CACHE / "requests.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "url": url,
                                "status": code, "type": ctype, "bytes": size,
                                "err": r.stderr.strip()[:200]}) + "\n")
        if code == "200" and size > 0:
            tmp.replace(p)
            (CACHE / (p.name + ".meta")).write_text(json.dumps({"url": url, "type": ctype}))
            return p.read_bytes()
        if tmp.exists():
            tmp.unlink()
        if code in ("404", "403", "410"):
            break
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"fetch failed {code} {url}")


def main(argv: list[str]) -> None:
    for u in argv:
        try:
            b = get(u)
            print(len(b), path_for(u).name[:12], u)
        except RuntimeError as e:
            print("FAIL", e)


if __name__ == "__main__":
    main(sys.argv[1:])
