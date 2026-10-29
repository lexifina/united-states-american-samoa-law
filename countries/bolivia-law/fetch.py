"""Polite, cached, resumable fetcher for the Bolivia law corpus.

Every request goes through curl (Python urllib fails TLS on this machine),
is cached under .cache/<sha256(url)>.<ext>, rate-limited to 1 request per
second per host, and logged to .cache/requests.jsonl.

Usage:
    python -X utf8 fetch.py URL [URL ...]      # fetch (or reuse) and print the cache path
    python -X utf8 fetch.py --manifest         # fetch every URL listed in sources.json
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
LOG = CACHE / "requests.jsonl"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
_last: dict[str, float] = {}


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode("utf-8")).hexdigest()


def cached(url: str) -> Path | None:
    p = cache_path(url)
    return p if p.exists() and p.stat().st_size > 0 else None


def fetch(url: str, *, force: bool = False, timeout: int = 120) -> Path:
    CACHE.mkdir(exist_ok=True)
    p = cache_path(url)
    if p.exists() and p.stat().st_size > 0 and not force:
        return p
    host = urlparse(url).netloc
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix(".part")
    hdr = p.with_suffix(".hdr")
    t0 = time.time()
    r = subprocess.run(
        ["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout), "-A", UA,
         "-o", str(tmp), "-D", str(hdr), "-w", "%{http_code}	%{content_type}	%{url_effective}", url],
        capture_output=True, text=True)
    _last[host] = time.time()
    out = (r.stdout or "").strip().split("	", 2)
    status = out[0] if out else ""
    ctype = out[1] if len(out) > 1 else ""
    final = out[2] if len(out) > 2 else ""
    size = tmp.stat().st_size if tmp.exists() else 0
    entry = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "url": url, "status": status,
             "content_type": ctype, "final_url": final, "bytes": size,
             "sha256": hashlib.sha256(tmp.read_bytes()).hexdigest() if size else None,
             "cache": p.name, "error": (r.stderr or "").strip()[:300] or None}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if status.startswith("2") and size:
        tmp.replace(p)
        meta = p.with_suffix(".json")
        meta.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"fetch failed {status} {url} {entry['error']}")
    return p


def wayback(url: str, timestamp: str = "") -> str | None:
    """Return the raw (id_) Wayback URL of the closest capture, or None."""
    q = f"https://archive.org/wayback/available?url={url}" + (f"&timestamp={timestamp}" if timestamp else "")
    p = fetch(q)
    d = json.loads(p.read_text(encoding="utf-8"))
    snap = d.get("archived_snapshots", {}).get("closest")
    if not snap or not snap.get("available"):
        return None
    ts = snap["timestamp"]
    return f"https://web.archive.org/web/{ts}id_/{url}"


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--manifest":
        man = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
        n = 0
        for item in man["fetch"]:
            try:
                fetch(item["url"])
                n += 1
            except RuntimeError as e:
                print(e, file=sys.stderr)
        print(f"{n}/{len(man['fetch'])} cached")
        return 0
    for u in argv:
        try:
            print(fetch(u))
        except RuntimeError as e:
            print(e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
