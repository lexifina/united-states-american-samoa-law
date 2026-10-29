"""Fetch InfoLEG / Boletín Oficial / datos.jus.gob.ar pages into .cache/ (gitlaw-AR).

Every request goes through curl (Python TLS fails on this machine), is cached by
sha256(url), is rate-limited to 1 request per second per host, and is logged to
.cache/requests.jsonl. Re-running is free: cached URLs are never re-fetched.

Usage:
    python -X utf8 fetch.py url URL [URL ...]
    python -X utf8 fetch.py acts            # the Phase 1/2 act pages and their link graphs
    python -X utf8 fetch.py amenders        # every norm listed as modifying a chosen act (norma.htm)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
BASE = "https://servicios.infoleg.gob.ar/infolegInternet"
_last: dict[str, float] = {}


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode("utf-8")).hexdigest()


def anexo_dir(nid: int) -> str:
    lo = nid // 5000 * 5000
    return f"{lo}-{lo + 4999}"


def norma_url(nid: int, page: str = "norma.htm") -> str:
    return f"{BASE}/anexos/{anexo_dir(nid)}/{nid}/{page}"


def vinculos_url(nid: int, modo: int) -> str:
    # modo=1: normas que esta norma modifica; modo=2: normas que la modifican
    return f"{BASE}/verVinculos.do?modo={modo}&id={nid}"


def ficha_url(nid: int) -> str:
    return f"{BASE}/verNorma.do?id={nid}"


def get(url: str, *, retries: int = 3) -> bytes | None:
    p = cache_path(url)
    if p.exists():
        return p.read_bytes()
    CACHE.mkdir(exist_ok=True)
    host = urlparse(url).netloc
    for attempt in range(retries):
        wait = 1.05 - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
        tmp = p.with_suffix(".part")
        r = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--max-time", "120", "-A", UA, "-o", str(tmp),
             "-w", "%{http_code}\t%{content_type}\t%{size_download}", url],
            capture_output=True, text=True)
        code, ctype, size = (r.stdout.split("\t") + ["", "", ""])[:3]
        rec = {"t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "url": url,
               "status": code, "type": ctype, "bytes": size, "sha256_url": p.name}
        with open(CACHE / "requests.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if code == "200" and tmp.exists():
            os.replace(tmp, p)
            return p.read_bytes()
        if tmp.exists():
            tmp.unlink()
        if code in ("404", "410"):
            return None
        time.sleep(3 * (attempt + 1))
    return None


def cached(url: str) -> bytes | None:
    p = cache_path(url)
    return p.read_bytes() if p.exists() else None


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "url":
        for u in rest:
            b = get(u)
            print(len(b) if b else None, u)
    elif cmd in ("acts", "amenders"):
        import acts as A  # local registry of chosen acts
        if cmd == "acts":
            for nid in A.all_ids():
                for u in (norma_url(nid), norma_url(nid, "texact.htm"), vinculos_url(nid, 2),
                          ficha_url(nid)):
                    b = get(u)
                    print(len(b) if b else None, u, flush=True)
        else:
            import parse as P
            ids = set()
            for nid in A.all_ids():
                ids |= {m["id"] for m in P.modifiers(nid)}
            for mid in sorted(ids):
                for u in (norma_url(mid), ficha_url(mid)):
                    b = get(u)
                    print(len(b) if b else None, u, flush=True)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
