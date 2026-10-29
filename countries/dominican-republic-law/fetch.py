"""Polite, cached, resumable fetcher for the Dominican Republic law corpus.

Every download goes through curl (Python TLS fails on this machine), is cached
under .cache/ by the sha256 of the URL, and is logged to .cache/requests.jsonl.
At most three requests per second per host (coordinator SPEED RULE). Standard library only.

    python -X utf8 fetch.py URL [URL ...]      fetch (or reuse) URLs, print cache paths
    python -X utf8 fetch.py --plan             fetch everything listed in sources.json
    python -X utf8 fetch.py --retry N URL ...  as above, retrying failures N times with backoff
    python -X utf8 fetch.py --wayback URL      resolve the newest Wayback capture and fetch its id_ raw form
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
LOG = CACHE / "requests.jsonl"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
_last: dict[str, float] = {}


def key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def path_for(url: str) -> Path:
    return CACHE / key(url)


def meta_for(url: str) -> Path:
    return CACHE / (key(url) + ".json")


def cached(url: str) -> Path | None:
    p, m = path_for(url), meta_for(url)
    if p.exists() and m.exists():
        if json.loads(m.read_text(encoding="utf-8")).get("status") == 200:
            return p
    return None


def _ensure_cache() -> None:
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")


def get(url: str, *, force: bool = False, extra: list[str] | None = None, timeout: int = 180) -> Path | None:
    """Return the cache path for url, downloading it if needed. None on failure."""
    _ensure_cache()
    if not force:
        hit = cached(url)
        if hit:
            return hit
    host = urlparse(url).netloc
    wait = 0.34 - (time.time() - _last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    out = path_for(url)
    tmp = out.with_suffix(".part")
    cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout), "-A", UA, "-o", str(tmp),
           "-w", "%{http_code}\t%{content_type}\t%{url_effective}"] + (extra or []) + [url]
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    r = subprocess.run(cmd, capture_output=True, text=True)
    parts = (r.stdout or "").split("\t", 2)
    status = int(parts[0]) if parts and parts[0].isdigit() else 0
    ctype = parts[1] if len(parts) > 1 else ""
    final = parts[2] if len(parts) > 2 else url
    size = tmp.stat().st_size if tmp.exists() else 0
    sha = hashlib.sha256(tmp.read_bytes()).hexdigest() if tmp.exists() else ""
    rec = {"url": url, "final": final, "status": status, "type": ctype, "bytes": size, "sha256": sha,
           "at": started, "err": (r.stderr or "").strip()[:300]}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if status == 200 and tmp.exists():
        tmp.replace(out)
        meta_for(url).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    if tmp.exists():
        tmp.unlink()
    meta_for(url).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return None


def wayback(url: str, timestamp: str = "") -> str | None:
    """Return the id_ raw URL of the Wayback capture closest to timestamp (newest if empty)."""
    api = "https://archive.org/wayback/available?url=" + quote(url, safe="")
    if timestamp:
        api += "&timestamp=" + timestamp
    p = get(api, force=True)
    if not p:
        return None
    snap = json.loads(p.read_text(encoding="utf-8")).get("archived_snapshots", {}).get("closest")
    if not snap or not snap.get("available"):
        return None
    ts = snap["timestamp"]
    return f"https://web.archive.org/web/{ts}id_/{url}"


def plan() -> None:
    spec = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    for item in spec["files"]:
        p = get(item["url"])
        print(("ok  " if p else "FAIL"), item["url"], flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--plan"]:
        plan()
    elif args[:1] == ["--wayback"]:
        for u in args[1:]:
            raw = wayback(u)
            print(raw, get(raw) if raw else None)
    elif args[:1] == ["--retry"]:
        # --retry N URL...: retry each failed URL up to N times with backoff (official sites and Wayback are intermittent)
        n = int(args[1])
        for u in args[2:]:
            p = None
            for i in range(n):
                p = get(u)
                if p:
                    break
                time.sleep(min(60, 5 * 2 ** i))
            print(p, u, flush=True)
    else:
        for u in args:
            print(get(u), u)
