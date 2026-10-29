"""Polite, cached, resumable fetcher for the Bulgaria law corpus.

Every download goes through curl (Python TLS fails on this machine), is cached
under .cache/ by the sha256 of the URL, and is logged to .cache/requests.jsonl.
At most three requests a second per host (SPEED RULE). Standard library only.

    python -X utf8 fetch.py URL [URL ...]      fetch (or reuse) URLs, print cache paths
    python -X utf8 fetch.py --plan             fetch everything listed in sources.json
    python -X utf8 fetch.py --retry N URL ...  as above, retrying failures N times with backoff
    python -X utf8 fetch.py --wayback URL      resolve the newest Wayback capture and fetch its id_ raw form
    python -X utf8 fetch.py --history          survey the archived parliament.bg/bg/const captures (wayback_survey.json)
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


CDX_LISTING = ("https://web.archive.org/cdx/search/cdx?url=parliament.bg/bg/const&output=json&matchType=prefix"
               "&fl=timestamp,original,mimetype,statuscode,digest,length&filter=statuscode:200&collapse=digest")
API_CAPTURES = [("20210629185623", "https://www.parliament.bg/api/v1/nav/bg/const"),
                ("20250820045413", "https://www.parliament.bg/api/v1/nav/bg/const")]


def history() -> None:
    """Survey the Internet Archive captures of parliament.bg/bg/const and find one complete copy per distinct text.

    The old server-rendered page (2010 to May 2021) holds the whole text; later captures are the JavaScript shell
    only. Reads the first capture of every quarter, then bisects between any two neighbours whose parsed text
    differs, so the first capture of every text in the sampled run is found. Each capture is parsed with parse.py
    (the same code as today's text), so markup changes are not counted as changes. Writes wayback_survey.json.
    All archive.org requests go through gitlaw_common/wayback.py (the shared machine-wide rate).
    """
    import re
    sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
    import wayback  # noqa: E402
    import parse  # noqa: E402
    wb = CACHE / "wb"
    rows = json.loads(wayback.fetch(CDX_LISTING, wb).decode("utf-8"))[1:]
    caps = sorted((r[0], r[1]) for r in rows if re.search(r"/bg/const/?$", r[1]) and r[2] == "text/html"
                  and r[0] < "20210601")
    seen: dict[str, dict] = {}

    def read(i: int) -> str | None:
        ts, url = caps[i]
        if ts not in seen:
            raw = wayback.get(url, ts=ts, cache=wb)
            rec = {"timestamp": ts, "url": url, "bytes": len(raw or b""), "complete": False, "text": None}
            if raw:
                rec["sha256"] = hashlib.sha256(raw).hexdigest()
                try:
                    header, units = parse.split_units(parse.page_lines(raw))
                    rec["complete"] = parse.complete(units)
                    rec["text"] = parse.text_hash({"header": header, "units": units})[:16]
                except (ValueError, StopIteration, IndexError, UnicodeDecodeError):
                    pass
            seen[ts] = rec
            print(ts, rec["bytes"], rec["complete"], rec["text"], flush=True)
        return seen[ts]["text"] if seen[ts]["complete"] else None

    def usable(i: int, step: int, stop: int) -> int | None:
        while True:
            if read(i):
                return i
            if i == stop:
                return None
            i += step

    quarters, last_q = [], None
    for i, (ts, _) in enumerate(caps):
        q = (ts[:4], (int(ts[4:6]) - 1) // 3)
        if q != last_q:
            quarters.append(i)
            last_q = q
    quarters.append(len(caps) - 1)
    good = [j for j in (usable(i, 1, min(i + 5, len(caps) - 1)) for i in quarters) if j is not None]
    good = sorted(set(good))

    def bisect(a: int, b: int) -> None:
        if b - a <= 1 or read(a) == read(b):
            return
        m = (a + b) // 2
        j = usable(m, 1, b - 1) or usable(m, -1, a + 1)
        if j is None or j in (a, b):
            return
        bisect(a, j)
        bisect(j, b)

    for a, b in zip(good, good[1:]):
        bisect(a, b)
    for ts, url in API_CAPTURES:
        raw = wayback.get(url, ts=ts, cache=wb)
        rec = {"timestamp": ts, "url": url, "bytes": len(raw or b""), "complete": False, "text": None, "api": True}
        if raw:
            rec["sha256"] = hashlib.sha256(raw).hexdigest()
            header, units = parse.split_units(parse.api_lines(raw))
            rec["complete"] = parse.complete(units)
            rec["text"] = parse.text_hash({"header": header, "units": units})[:16]
        seen[ts] = rec
        print(ts, rec["bytes"], rec["complete"], rec["text"], "(API)", flush=True)
    out = sorted(seen.values(), key=lambda r: r["timestamp"])
    picks, last = [], None
    for r in out:
        if r["complete"] and not r.get("api") and r["text"] != last:
            picks.append([r["timestamp"], r["url"]])
            last = r["text"]
    survey = {"listing": CDX_LISTING, "html_captures": len(caps), "read": len(out), "captures": out,
              "picks": picks}
    tmp = HERE / "wayback_survey.json.tmp"
    tmp.write_text(json.dumps(survey, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(HERE / "wayback_survey.json")
    print("picks:", picks)


def plan() -> None:
    spec = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    for item in spec["files"]:
        p = get(item["url"])
        print(("ok  " if p else "FAIL"), item["url"], flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--plan"]:
        plan()
    elif args[:1] == ["--history"]:
        history()
    elif args[:1] == ["--wayback"]:
        for u in args[1:]:
            raw = wayback(u)
            print(raw, get(raw) if raw else None)
    elif args[:1] == ["--retry"]:
        # --retry N URL...: retry each failed URL up to N times with backoff (intermittent hosts)
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
