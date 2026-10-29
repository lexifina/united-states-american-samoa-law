"""Polite, cached, resumable fetcher for the Ecuador law corpus.

Every download goes through curl (Python TLS fails on this machine), is cached
under .cache/ by the sha256 of the URL, and is logged to .cache/requests.jsonl.
At most one request per second per host.

    python -X utf8 fetch.py URL [URL ...]      fetch (or reuse) URLs
    python -X utf8 fetch.py --plan              fetch everything in sources.json
"""
from __future__ import annotations

import hashlib
import json
import os
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


def key(url: str, data: str | None = None) -> str:
    """sha256 of the URL; a POST adds a newline and its form body (the Registro Oficial listings are POSTs)."""
    ident = url if data is None else url + "\n" + data
    return hashlib.sha256(ident.encode("utf-8")).hexdigest()


def path_for(url: str, data: str | None = None) -> Path:
    return CACHE / key(url, data)


def meta_for(url: str, data: str | None = None) -> Path:
    return CACHE / (key(url, data) + ".json")


def cached(url: str, data: str | None = None) -> Path | None:
    p = path_for(url, data)
    m = meta_for(url, data)
    if p.exists() and m.exists():
        info = json.loads(m.read_text(encoding="utf-8"))
        if info.get("status") == 200:
            return p
    return None


def _ensure_cache() -> None:
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")


def get(url: str, *, data: str | None = None, force: bool = False, extra: list[str] | None = None,
        timeout: int = 120) -> Path | None:
    """Return the cache path for url (POSTing the urlencoded `data` if given), downloading it if needed.
    None on failure."""
    _ensure_cache()
    if not force:
        hit = cached(url, data)
        if hit:
            return hit
    host = urlparse(url).netloc
    wait = 1.05 - (time.time() - _last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    out = path_for(url, data)
    tmp = out.with_suffix(".part")
    cmd = [
        "curl", "-sS", "-L", "--compressed", "--max-time", str(timeout), "-A", UA,
        "-o", str(tmp), "-w", "%{http_code} %{content_type} %{url_effective}",
    ] + (["--data", data] if data is not None else []) + (extra or []) + [url]
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    r = subprocess.run(cmd, capture_output=True, text=True)
    parts = (r.stdout or "").split(" ", 2)
    status = int(parts[0]) if parts and parts[0].isdigit() else 0
    ctype = parts[1] if len(parts) > 1 else ""
    final = parts[2] if len(parts) > 2 else url
    size = tmp.stat().st_size if tmp.exists() else 0
    sha = hashlib.sha256(tmp.read_bytes()).hexdigest() if tmp.exists() else ""
    rec = {"t": started, "url": url, **({"post": data} if data is not None else {}), "status": status, "type": ctype, "final": final,
           "bytes": size, "sha256": sha, "err": (r.stderr or "").strip()[:300]}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if status == 200 and size > 0:
        os.replace(tmp, out)
        meta_for(url, data).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    if tmp.exists():
        tmp.unlink()
    meta_for(url, data).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return None


def plan_urls() -> list[str]:
    """Every URL parse.py needs, from sources.json ({"<name>": {"urls": [...]}, ...})."""
    src = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    urls: list[str] = []
    for item in src.values():
        if isinstance(item, dict):
            urls.extend(u for u in item.get("urls", []) if u)
    return urls


def main(argv: list[str]) -> int:
    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]
    urls = plan_urls() if argv[:1] == ["--plan"] else argv
    bad = 0
    for u in urls:
        p = get(u, force=force)
        info = json.loads(meta_for(u).read_text(encoding="utf-8"))
        print(info["status"], info["bytes"], info["type"], u, "->", p.name if p else "FAILED")
        bad += p is None
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
