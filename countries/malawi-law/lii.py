"""Malawi's fetcher: the shared Peachjam adapter's fetch, but reading Common Crawl first and archive.org for the gaps.

    python -X utf8 scripts/malawi-law/fetch.py          (calls lii.fetch)

Why its own fetch: peachjam.fetch reads only archive.org with a fixed delay, and archive.org throttles this machine
(coordinator, 2026-10-28 21:45 UTC: "FAST ARCHIVE ACCESS" in scripts/africa-law/FANOUT.md). This module finds every
archived copy of each expression page in two archives:
- Common Crawl (index.commoncrawl.org, one prefix query per crawl for malawilii.org/akn/mw/act/, then the page bytes
  by byte range from data.commoncrawl.org), and
- the Internet Archive (one CDX query per work, then the raw `id_` capture), through scripts/gitlaw_common/wayback.py,
  which keeps one adaptive archive.org rate for the whole machine.
It takes the newest copy that is a good expression page (peachjam.good_expression_page) and pins it in sources.json in
exactly the shape peachjam.parse reads: for a Common Crawl copy the cache key is "cc:<warc file>:<offset>:<length>"
(the key wayback.cc_get caches under), for an archive.org copy the raw `id_` URL. No MalawiLII page is ever fetched.

Adapter parts the shared peachjam.py could adopt: the two-archive discovery (`candidates`) and fetch (`fetch`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
sys.path.insert(0, str(HERE))
import peachjam  # noqa: E402
import wayback  # noqa: E402

CACHE = HERE / ".cache"
N_CRAWLS = 16  # CC-MAIN-2026-43 back to about 2023: MalawiLII has run on Peachjam since 2023


def cc_records(cfg: dict) -> list[dict]:
    """Every Common Crawl capture under <host>/akn/<cc>/act/ in the newest N_CRAWLS crawls (cached index pages)."""
    up = subprocess.run(["curl", "-sS", "-o", os.devnull, "-m", "20", "-w", "%{http_code}", f"{wayback.CC_INDEX}/"],
                        capture_output=True, text=True).stdout.strip()
    if up != "200":  # the index server sometimes refuses this machine; archive.org then serves alone
        print(f"Common Crawl index unreachable (HTTP {up or 'none'}): archive.org only this run")
        return []
    crawls = wayback.cc_crawls(CACHE)[:N_CRAWLS]
    if not crawls:
        raise SystemExit("Common Crawl collinfo.json unavailable")
    pre = f"{cfg['lii']['hosts'][0]}/akn/{cfg['lii']['cc']}/act/"
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda c: wayback.cc_captures(pre, crawls=[c], match="prefix", cache=CACHE), crawls))
    return [r for rs in res for r in rs]


def candidates(cfg: dict, work: str, cc: list[dict]) -> dict[str, list[dict]]:
    """{expression date: [copy, ...] newest first}; a copy is {"via": "cc"|"ia", "ts", "original", ...}."""
    rx = re.compile(rf"/akn/{cfg['lii']['cc']}/act/{re.escape(work)}/eng@(\d{{4}}-\d{{2}}-\d{{2}})/?$")
    out: dict[str, list[dict]] = {}
    for r in cc:
        m = rx.search(r["url"].split("?")[0])
        if m and "?" not in r["url"] and str(r.get("status")) == "200" and "html" in (r.get("mime") or ""):
            out.setdefault(m.group(1), []).append({"via": "cc", "ts": r["timestamp"], "original": r["url"],
                                                   "crawl": r["crawl"], "filename": r["filename"],
                                                   "offset": r["offset"], "length": r["length"]})
    for host in cfg["lii"]["hosts"]:
        for r in wayback.captures(f"{host}/akn/{cfg['lii']['cc']}/act/{work}/eng@", match="prefix", cache=CACHE):
            m = rx.search(r["original"].split("?")[0])
            if m and "?" not in r["original"] and "html" in r["mimetype"]:
                out.setdefault(m.group(1), []).append({"via": "ia", "ts": r["timestamp"], "original": r["original"]})
    for d in out:
        out[d].sort(key=lambda c: (c["ts"], c["via"]), reverse=True)
    return dict(sorted(out.items()))


def get(copy: dict) -> tuple[str, bytes | None]:
    """(cache key = the url peachjam.parse reads, bytes)"""
    if copy["via"] == "cc":
        rec = {"filename": copy["filename"], "offset": copy["offset"], "length": copy["length"], "status": 200}
        return f"cc:{copy['filename']}:{copy['offset']}:{copy['length']}", wayback.cc_get(rec, cache=CACHE)
    url = peachjam.raw(copy["ts"], copy["original"])
    return url, wayback.fetch(url, CACHE)


def good_page(b: bytes, expr_uri: str) -> bool:
    """peachjam.good_expression_page, plus the pre-Peachjam MalawiLII layout (2021-2022 captures), which names the
    expression in JSON with escaped slashes ("expression_frbr_uri":"\\/akn\\/mw\\/..."): ISSUES-malawi.md #2."""
    if peachjam.good_expression_page(b, expr_uri):
        return True
    t = b.decode("utf-8", "replace")
    esc = expr_uri.replace("/", "\\/")
    return 'class="akn-akomaNtoso"' in t and f'"expression_frbr_uri":"{esc}"' in t


def best(copies: list[dict], expr_uri: str, tries: int = 6) -> dict | None:
    for c in copies[:tries]:
        key, b = get(c)
        if b and good_page(b, expr_uri):
            pin = {"capture": c["ts"], "original": c["original"], "url": key, "via": c["via"],
                   "sha256": hashlib.sha256(b).hexdigest()}
            if c["via"] == "cc":
                pin.update(crawl=c["crawl"], warc=c["filename"], offset=c["offset"], length=c["length"])
            return pin
    return None


def fetch(folder: Path = HERE) -> dict:
    cfg = peachjam.load_config(folder)
    lii = cfg["lii"]
    cc = cc_records(cfg)
    pins: dict = {"lii": lii["name"], "acts": {}, "laws": {}, "listings": {}}
    law_uris: set[str] = set()
    for act in cfg["acts"]:
        work = act["work"]
        caps = candidates(cfg, work, cc)
        if not caps:
            raise SystemExit(f"{work}: no archived expression pages")
        uri = peachjam.work_uri(cfg, work)
        with ThreadPoolExecutor(8) as ex:
            got = dict(zip(caps, ex.map(lambda d: best(caps[d], f"{uri}/eng@{d}"), caps)))
        exprs = {d: p for d, p in got.items() if p and d not in act.get("skip", [])}
        missing = sorted(d for d, p in got.items() if not p)
        pins["acts"][work] = {"expressions": exprs, "copies_without_text": missing}
        info = peachjam.page_info(peachjam.Cache(folder, offline=True).get(exprs[max(exprs)]["url"]))
        for item in info["timeline"]:
            for ev in item["events"]:
                for href, _ in ev["links"]:
                    if href and "/akn/" in href and "@" not in href:
                        law_uris.add(re.sub(r"^/[a-z]{2}(?=/akn/)", "", href))
        print(f"{work}: {len(exprs)}/{len(caps)} expressions archived with text: {sorted(exprs)}; no text: {missing}")

    def law(uri: str):
        w = re.sub(rf"^/akn/{lii['cc']}/act/", "", uri)
        caps = candidates(cfg, w, cc)
        for day in caps:  # oldest expression first: the law as enacted
            p = best(caps[day], f"{uri}/eng@{day}", tries=3)
            if p:
                return {"expression": day, **p}
        return None

    todo = sorted(u for u in law_uris if re.sub(rf"^/akn/{lii['cc']}/act/", "", u) not in pins["acts"])
    with ThreadPoolExecutor(6) as ex:
        for uri, p in zip(todo, ex.map(law, todo)):
            pins["laws"][uri] = p
            print(f"law {uri}: {'archived ' + p['expression'] + ' via ' + p['via'] if p else 'no archived page'}")
    pins["retrieved"] = cfg["retrieved"]
    tmp = folder / "sources.json.tmp"
    tmp.write_text(json.dumps(pins, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(folder / "sources.json")
    return pins
