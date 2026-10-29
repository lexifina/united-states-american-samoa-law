"""Polite, cached, resumable fetcher for the Russia law corpus.

Source: the Official Internet Portal of Legal Information (pravo.gov.ru), IPS
"Законодательство России" as served by actual.pravo.gov.ru (the JSON API behind
the portal's own web viewer, http://actual.pravo.gov.ru:8000/api/ebpi/).
pravo.gov.ru itself does not answer from this machine; actual.pravo.gov.ru does.

Endpoints used (the same calls the portal's viewer makes, js/common.js and js/list.js):
  attrsearch/?bpa=ebpi&q=<json>             search by signing date, kind, number
  redactions/?bpa=ebpi&t={"hash":H,"ttl":3} every edition (редакция) of an act, with dates
  redtext?bpa=ebpi&t=<redid>&ttl=3          the full text of one edition, as HTML in JSON

Every download goes through curl (Python TLS fails on this machine), is cached under
.cache/ by the sha256 of the URL, and is logged to .cache/requests.jsonl.
At most 3 requests a second (SPEED RULE). Standard library only.

    python -X utf8 fetch.py acts           fetch the edition lists and every edition of the acts in ACTS
    python -X utf8 fetch.py search YYYYMMDD
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
LOG = CACHE / "requests.jsonl"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
API = "http://actual.pravo.gov.ru:8000/api/ebpi/"
_lock = threading.Lock()
_last = [0.0]
MIN_GAP = 0.34  # about 3 requests a second

# slug -> document hash on the portal (found with `search` on the signing date)
ACTS = {
    "konstitutsiya": "c9693d70b5bc11c97f515e288930b34815497eab8f08a7ad32eaab319b6d262a",
    "gk-1": "ba747b7c430f",   # completed by resolve() from the search on 19941130
    "uk": "f29a592d348b",     # completed by resolve() from the search on 19960613
}
SIGNED = {"konstitutsiya": "19931212", "gk-1": "19941130", "uk": "19960613"}


def key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def path_for(url: str) -> Path:
    return CACHE / key(url)


def get(url: str, *, force: bool = False, timeout: int = 240) -> bytes | None:
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    out = path_for(url)
    if out.exists() and not force:
        return out.read_bytes()
    for attempt in range(4):
        with _lock:
            wait = MIN_GAP - (time.time() - _last[0])
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        tmp = out.with_suffix(f".part{threading.get_ident()}")
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        r = subprocess.run(["curl", "-sS", "--compressed", "--max-time", str(timeout), "-A", UA, "-o", str(tmp),
                            "-w", "%{http_code}\t%{content_type}", url], capture_output=True, text=True)
        parts = (r.stdout or "").split("\t")
        status = int(parts[0]) if parts and parts[0].isdigit() else 0
        body = tmp.read_bytes() if tmp.exists() else b""
        ok = status == 200 and body[:1] == b"{"
        if ok:
            try:
                d = json.loads(body)
                if d.get("error") not in ("", None, "None"):
                    ok = False
            except ValueError:
                ok = False
        rec = {"url": url, "status": status, "type": parts[1] if len(parts) > 1 else "", "bytes": len(body),
               "sha256": hashlib.sha256(body).hexdigest(), "at": started, "ok": ok, "attempt": attempt}
        with _lock:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if ok:
            tmp.replace(out)
            return body
        tmp.unlink(missing_ok=True)
        if status in (429, 503):
            time.sleep(60)
        else:
            time.sleep(3 * (attempt + 1))
    return None


def search_url(date: str) -> str:
    q = [{"AttrId": 5, "AttrMode": 0, "DateFrom": date, "DateTo": date},
         {"AttrId": 999, "AttrMode": 1, "Words": [100, "date", "", 0, 0]}]
    return API + "attrsearch/?bpa=ebpi&q=" + quote(json.dumps(q, ensure_ascii=False, separators=(",", ":")))


def redactions_url(h: str) -> str:
    return API + "redactions/?bpa=ebpi&t=" + quote(json.dumps({"hash": h, "ttl": 3}, separators=(",", ":")))


def redtext_url(redid: int) -> str:
    return API + f"redtext?bpa=ebpi&t={redid}&ttl=3"


def card_url(docid: int) -> str:
    return API + "card/?bpa=ebpi&t=" + quote(json.dumps({"docid": docid}, separators=(",", ":")))


def resolve(slug: str) -> str:
    h = ACTS[slug]
    if len(h) == 64:
        return h
    d = json.loads(get(search_url(SIGNED[slug])))
    for x in d["docs"]:
        if x["dochash"].startswith(h):
            return x["dochash"]
    raise SystemExit(f"{slug}: hash {h} not found")


def fetch_act(slug: str) -> list[dict]:
    h = resolve(slug)
    d = json.loads(get(redactions_url(h)))
    reds = d["redactions"]
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda r: get(redtext_url(r["redid"])) is not None, reds))
        list(ex.map(lambda i: get(card_url(i)), sorted({r["reddocrefid"] for r in reds if r["reddocrefid"]})))
    print(f"{slug}: {len(reds)} editions, {sum(res)} texts cached, cards fetched")
    return reds


if __name__ == "__main__":
    if sys.argv[1] == "search":
        d = json.loads(get(search_url(sys.argv[2])))
        for x in d["docs"]:
            print(x["docpassing"], "|", x["docnames"][:100], "|", x["dochash"])
    elif sys.argv[1] == "acts":
        for s in (sys.argv[2:] or ACTS):
            fetch_act(s)
