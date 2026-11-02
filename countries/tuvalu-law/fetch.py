"""Polite, resumable, cached fetcher for the Tuvalu law sources (tuvalu-legislation.tv).

Every request goes through curl (Python TLS fails on this machine), at most three
requests per second per host (SPEED RULE), with the lexifina-watch User-Agent. Responses are
cached under .cache/ by sha256(url) and every network request is logged to
.cache/requests.jsonl. A cached URL is never fetched again.

    python -X utf8 fetch.py URL [URL ...]      fetch these URLs
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


def get(url: str, *, retries: int = 3, data: str | None = None) -> bytes:
    """GET url, or POST form `data` to it (cached under sha256 of url, newline, data)."""
    ck = url if data is None else url + "\n" + data
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n")
    p = path_for(ck)
    if p.exists():
        return p.read_bytes()
    host = urlparse(url).netloc
    for attempt in range(retries):
        wait = 0.34 - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        tmp = p.with_suffix(".part")
        t0 = time.time()
        r = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--max-time", "180", "-A", UA, "-o", str(tmp),
             "-w", "%{http_code} %{content_type}"] + (["--data", data] if data is not None else [])
            + [url.replace(" ", "%20")],
            capture_output=True, text=True)
        _last[host] = time.time()
        code, _, ctype = (r.stdout or "000 ").partition(" ")
        size = tmp.stat().st_size if tmp.exists() else 0
        with open(CACHE / "requests.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "url": url, "post": data,
                                "status": code, "type": ctype, "bytes": size,
                                "err": r.stderr.strip()[:200]}) + "\n")
        if code == "200" and size > 0:
            tmp.replace(p)
            (CACHE / (p.name + ".meta")).write_text(json.dumps({"url": url, "post": data, "type": ctype}))
            return p.read_bytes()
        if tmp.exists():
            tmp.unlink()
        if code in ("404", "403", "410"):
            break
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed {code} {url}")


def main(argv: list[str]) -> None:
    urls = argv
    for u in urls:
        try:
            b = get(u)
            print(len(b), u)
        except RuntimeError as e:
            print("FAIL", e)


if __name__ == "__main__":
    main(sys.argv[1:])
