"""Polite, resumable, cached fetcher for the Belize law sources (gitlaw-BZ).

Every request goes through curl (Python TLS fails on this machine) with --compressed and the
lexifina-watch User-Agent, at most 3 requests a second per host (coordinator SPEED RULE).
Responses are cached under .cache/ by sha256 of the request key and every network request is
logged to .cache/requests.jsonl. A cached request is never made again.

The request key is the URL for GET requests and "POST <url> <body>" for the AGM portal's
listing API (agm.gov.bz/api-laws/, which the portal's own DataTables page calls).

    python -X utf8 fetch.py URL [URL ...]          fetch these URLs
    python -X utf8 fetch.py --listings             every R.E. 2020 volume and every annual Acts list
    python -X utf8 fetch.py --plan                 every document parse.py needs (sources.PLAN)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
API = "https://agm.gov.bz/api-laws/"
MIN_GAP = 0.34          # seconds between requests to one host (3 a second)
_last: dict[str, float] = {}
_lock = threading.Lock()


def key(req: str) -> str:
    return hashlib.sha256(req.encode("utf-8")).hexdigest()


def path_for(req: str) -> Path:
    return CACHE / key(req)


def cached(req: str) -> bytes | None:
    p = path_for(req)
    return p.read_bytes() if p.exists() else None


def post_key(url: str, body: str) -> str:
    return f"POST {url} {body}"


def _slot(host: str) -> None:
    with _lock:
        now = time.time()
        start = max(now, _last.get(host, 0) + MIN_GAP)
        _last[host] = start
    if start > now:
        time.sleep(start - now)


def get(url: str, *, body: str | None = None, retries: int = 3) -> bytes:
    """GET url (or POST body to url) through curl, cached."""
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n")
    req = post_key(url, body) if body is not None else url
    p = path_for(req)
    if p.exists():
        return p.read_bytes()
    host = urlparse(url).netloc
    code = "000"
    for attempt in range(retries):
        _slot(host)
        tmp = p.with_suffix(".part")
        t0 = time.time()
        cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", "300", "-A", UA, "-o", str(tmp),
               "-w", "%{http_code} %{content_type}"]
        if body is not None:
            cmd += ["-H", "X-Requested-With: XMLHttpRequest", "--data", body]
        cmd.append(url.replace(" ", "%20"))
        r = subprocess.run(cmd, capture_output=True, text=True)
        code, _, ctype = (r.stdout or "000 ").partition(" ")
        size = tmp.stat().st_size if tmp.exists() else 0
        with _lock, open(CACHE / "requests.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "req": req,
                                "status": code, "type": ctype, "bytes": size,
                                "err": r.stderr.strip()[:200]}) + "\n")
        if code == "200" and size > 0:
            tmp.replace(p)
            (CACHE / (p.name + ".meta")).write_text(json.dumps({"req": req, "type": ctype,
                                                                "retrieved": time.strftime("%Y-%m-%d", time.gmtime(t0))}))
            return p.read_bytes()
        if tmp.exists():
            tmp.unlink()
        if code in ("404", "403", "410"):
            break
        if code in ("429", "503"):
            time.sleep(60)
        else:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed {code} {req}")


def listing(action: str, volume: str) -> dict:
    return json.loads(get(API, body=f"action={action}&volume={volume}"))


def listings() -> None:
    for v in range(1, 19):
        d = listing("1000", str(v))
        print("RE2020 volume", v, len(d.get("data") or []))
    for y in range(1981, 2027):
        try:
            d = listing("1001", f"{y}_act")
            print("acts", y, d.get("rc"), len(d.get("data") or []))
        except Exception as e:  # noqa: BLE001
            print("acts", y, "FAIL", e)


def main(argv: list[str]) -> None:
    if argv and argv[0] == "--listings":
        listings()
        return
    if argv and argv[0] == "--plan":
        from sources import PLAN
        urls = PLAN
    else:
        urls = argv
    from concurrent.futures import ThreadPoolExecutor

    def one(u):
        try:
            return f"{len(get(u))} {u}"
        except RuntimeError as e:
            return f"FAIL {e}"
    with ThreadPoolExecutor(3) as ex:
        for line in ex.map(one, urls):
            print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
