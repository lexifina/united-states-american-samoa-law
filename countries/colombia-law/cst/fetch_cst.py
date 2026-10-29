"""Fetch the pages that date the acts which amended the Código Sustantivo del Trabajo (CST).

Same cache as ../fetch.py (../.cache, sha256(url) names, ../.cache/requests.jsonl), same User-Agent, curl with
--compressed. At least 2.1 s between requests to one host from this process, so that with the other Colombia fetchers
running the total to secretariasenado.gov.co stays near 1 request per second. A URL already logged as failed (404) is
not asked again.

Usage:  python -X utf8 cst/fetch_cst.py laws     # for every act the CST notes name that has no in-force day yet:
                                                 # its basedoc page (base + last page), else the Colpensiones copy
        python -X utf8 cst/fetch_cst.py url <url>...
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, COUNTRY)
import fetch as F  # noqa: E402

COLPENSIONES = "https://normativa.colpensiones.gov.co/colpens/docs/"
_orig_get = F.get
_last: dict[str, float] = {}


def failed_before() -> set[str]:
    out = set()
    try:
        with open(F.LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if str(r.get("status")) in ("404", "410"):
                    out.add(r["url"])
    except OSError:
        pass
    return out


FAILED = failed_before()


def get(url: str):
    if os.path.exists(F.cache_path(url)):
        return F.cached(url)
    if url in FAILED:
        return None
    host = urlparse(url).netloc
    wait = 2.1 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    b = _orig_get(url)
    if b is None:
        FAILED.add(url)
    return b


def page_name(key: str) -> str:
    kind, n, y = key.split("-")
    return f"{'decreto' if kind == 'dec' else 'ley'}_{int(n):04d}_{y}"


def last_page(name: str) -> bool:
    raw = get(F.BASE + name + ".html")
    if raw is None:
        return False
    t = raw.decode("latin-1")
    nums = sorted(set(re.findall(r'value="_pr(\d{3})', t)) | set(re.findall(re.escape(name) + r"_pr(\d{3})\.html", t)))
    if nums:
        get(F.BASE + f"{name}_pr{nums[-1]}.html")
    return True


def undated() -> list[str]:
    sys.path.insert(0, HERE)
    import parse_cst as P
    P.build_cst()
    E = P.E
    return sorted(k for k in E.LAWS if k not in E.IN_FORCE and re.fullmatch(r"(ley|dec)-\d+-\d{4}", k)
                  or (k in E.LAWS and re.fullmatch(r"(ley|dec)-\d+-\d{4}", k) and k not in E.LAW_PAGE))


# Keys that are typing slips in the CST's notes (fixed in parse_cst.py), not acts to fetch.
TYPOS = {"dec-2351-1995", "ley-2737-1989"}


def main(argv):
    if argv[:1] == ["laws"]:
        for k in undated():
            if k in TYPOS:
                continue
            n = page_name(k)
            ok = last_page(n)
            b = None if ok else get(COLPENSIONES + n + ".htm")
            print(k, "basedoc" if ok else ("colpensiones" if b else "none"), flush=True)
    elif argv[:1] == ["url"]:
        for u in argv[1:]:
            b = get(u)
            print(u, None if b is None else len(b))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
