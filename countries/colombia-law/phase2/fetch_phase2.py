"""Fetch the Phase 2 codes (Código Penal, Código General del Proceso, Código Sustantivo del Trabajo) and the
basedoc pages of the acts that amended them (for their vigencia clauses).

Same cache as ../fetch.py (../.cache, sha256(url) names, ../.cache/requests.jsonl), same User-Agent, curl.
At least 2.1 s between requests to one host from this process, so that with other fetchers of this country
running at the same time the total stays near 1 request per second.

Usage:  python -X utf8 phase2/fetch_phase2.py docs     # the three codes (base, pr pages, js)
        python -X utf8 phase2/fetch_phase2.py laws     # base + last page of every amending act named in their notes
        python -X utf8 phase2/fetch_phase2.py url <url>...
"""
from __future__ import annotations

import os
import re
import sys
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fetch as F  # noqa: E402

DOCS = ["ley_0599_2000", "ley_1564_2012", "codigo_sustantivo_trabajo"]
_orig_get = F.get
_last: dict[str, float] = {}


def get(url: str):
    if not os.path.exists(F.cache_path(url)):
        host = urlparse(url).netloc
        wait = 2.1 - (time.time() - _last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
    return _orig_get(url)


F.get = get  # fetch_doc() in ../fetch.py calls get() through the module


def last_page(name: str) -> list[str]:
    base = F.BASE + name + ".html"
    raw = get(base)
    if raw is None:
        return []
    t = raw.decode("latin-1")
    nums = sorted(set(re.findall(r'value="_pr(\d{3})', t)) | set(re.findall(re.escape(name) + r"_pr(\d{3})\.html", t)))
    out = [base]
    if nums:
        u = F.BASE + f"{name}_pr{nums[-1]}.html"
        if get(u) is not None:
            out.append(u)
    return out


def amending_pages() -> list[str]:
    """basedoc page names of every Ley/Decreto linked from the three codes' note boxes."""
    names = set()
    for d in DOCS:
        base = F.cached(F.BASE + d + ".html")
        if base is None:
            continue
        t = base.decode("latin-1")
        pg = [d] + [f"{d}_pr{n}" for n in sorted(set(re.findall(r'value="_pr(\d{3})', t)))]
        for p in pg:
            for u in (F.BASE + "js/" + p + ".js", F.BASE + p + ".html"):
                b = F.cached(u)
                if b:
                    names |= set(re.findall(r"href=['\"]((?:ley|decreto)_\d{4}_\d{4})(?:_pr\d{3})?\.html", b.decode("latin-1")))
    return sorted(names - set(DOCS))


def main(argv):
    if argv[:1] == ["docs"]:
        for d in DOCS:
            print(d, len(F.fetch_doc(d)), flush=True)
    elif argv[:1] == ["laws"]:
        for n in amending_pages():
            print(n, len(last_page(n)), flush=True)
    elif argv[:1] == ["url"]:
        for u in argv[1:]:
            b = get(u)
            print(u, None if b is None else len(b))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
