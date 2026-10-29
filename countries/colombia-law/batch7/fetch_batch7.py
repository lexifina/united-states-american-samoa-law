"""Fetch batch 7 (national laws: Leyes 1150 de 2007, 1474 de 2011, 1712 de 2014, 1755 de 2015, 789 de 2002, 1429 de
2010, 1523 de 2012, 99 de 1993, 388 de 1997 and Decreto Ley 2811 de 1974) from the Senado basedoc, and the base + last
page of every act their notes link to.

Same cache as ../fetch.py (../.cache, sha256(url) file names, ../.cache/requests.jsonl). Requests go through the shared
client `scripts/gitlaw_common/wayback.py` `host_get` (curl --compressed, the machine-wide adaptive rate per host that
the coordinator's SPEED RULE 2 sets), from a thread pool.

Usage:  python -X utf8 batch7/fetch_batch7.py docs | laws | url <url>...
"""
from __future__ import annotations

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, COUNTRY)
sys.path.insert(0, os.path.join(COUNTRY, "phase2"))
sys.path.insert(0, os.path.join(os.path.dirname(COUNTRY), "gitlaw_common"))
import fetch as F  # noqa: E402
import fetch_phase2 as P2  # noqa: E402
import wayback  # noqa: E402

DOCS = ["ley_1150_2007", "ley_1474_2011", "ley_1712_2014", "ley_1755_2015", "ley_0789_2002", "ley_1429_2010",
        "ley_1523_2012", "ley_0099_1993", "ley_0388_1997", "decreto_2811_1974"]
P2.DOCS = DOCS
THREADS = 12


def get(url: str) -> bytes | None:
    return wayback.host_get(url, cache=F.CACHE)


def pool(fn, items):
    with ThreadPoolExecutor(THREADS) as ex:
        return list(ex.map(fn, items))


def pages(name: str) -> list[str]:
    raw = F.cached(F.BASE + name + ".html")
    if raw is None:
        return []
    t = raw.decode("latin-1")
    nums = sorted(set(re.findall(r'value="_pr(\d{3})', t)) | set(re.findall(re.escape(name) + r"_pr(\d{3})\.html", t)))
    return [name] + [f"{name}_pr{n}" for n in nums]


def docs() -> None:
    pool(get, [F.BASE + d + ".html" for d in DOCS])
    pg = [p for d in DOCS for p in pages(d)]
    pool(get, [F.BASE + p + ".html" for p in pg])
    js = [F.BASE + "js/" + p + ".js" for p in pg if b"js/" + p.encode() + b".js" in (F.cached(F.BASE + p + ".html") or b"")]
    pool(get, js)
    for d in DOCS:
        print(d, len(pages(d)), "pages", flush=True)


def laws() -> None:
    names = P2.amending_pages()
    pool(get, [F.BASE + n + ".html" for n in names])
    last = []
    for n in names:
        ps = pages(n)
        if len(ps) > 1:
            last.append(F.BASE + ps[-1] + ".html")
    pool(get, last)
    print(len(names), "acts,", len(last), "last pages", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["docs"]:
        docs()
    elif cmd == ["laws"]:
        laws()
    elif cmd == ["url"]:
        for u, b in zip(sys.argv[2:], pool(get, sys.argv[2:])):
            print(u, None if b is None else len(b))
    else:
        print(__doc__)
