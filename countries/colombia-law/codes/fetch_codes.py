"""Fetch the pages the Código Civil / Ley 1581 parser needs beyond what ../fetch.py already cached.

Same cache as ../fetch.py (../.cache, sha256(url) names, ../.cache/requests.jsonl log), same User-Agent,
curl with --compressed. Polite: at least 2.1 s between requests to one host from this process (the
country's own fetch.py may run at the same time, so the two together stay under 1 request per second).

The amending laws' pages are read only for their own vigencia clause (the in-force day of each change).

Usage:  python -X utf8 fetch_codes.py laws        # base page + last page of every amending law
        python -X utf8 fetch_codes.py old         # Colpensiones copies of acts the basedoc lacks
        python -X utf8 fetch_codes.py url <url>...
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fetch as F  # noqa: E402  (../fetch.py: cache, log, curl)

F._last = {}
_orig_get = F.get


def get(url: str):
    import time
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if not os.path.exists(F.cache_path(url)):
        wait = 2.1 - (time.time() - F._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
    return _orig_get(url)


# basedoc page names of the acts that amended the Código Civil (from its notes), plus the codes the notes
# cite by name only (C.P.C. = Decreto 1400 de 1970; C.S. del T. = Decreto 2663 de 1950) and Ley 4 de 1913
# (the default in-force rule).
LAW_PAGES = """
ley_0057_1887 ley_0153_1887 ley_0095_1890 ley_0057_1915 ley_0008_1922 ley_0045_1930 ley_0067_1930 ley_0036_1931
ley_0028_1932 ley_0034_1936 ley_0045_1936 ley_0050_1936 ley_0092_1938 ley_0165_1941 ley_0140_1960 ley_0075_1968
decreto_0960_1970 decreto_1250_1970 decreto_1260_1970 decreto_1400_1970 decreto_2820_1974 ley_0005_1975 decreto_0772_1975
ley_0001_1976 ley_0027_1977 ley_0095_1980 ley_0029_1982 ley_0011_1984 ley_0084_1989 decreto_1712_1989 decreto_2737_1989
ley_0025_1992 ley_0222_1995 decreto_2150_1995 ley_0791_2002 ley_0820_2003 ley_1060_2006 ley_1098_2006 ley_1116_2006
ley_1306_2009 ley_1453_2011 ley_1564_2012 ley_1676_2013 ley_1774_2016 ley_1893_2018 ley_1934_2018 ley_1996_2019
ley_2089_2021 ley_2229_2022 ley_2388_2024 ley_2442_2024 ley_2447_2025 ley_2473_2025 decreto_2663_1950 ley_0004_1913
decreto_3743_1950 ley_0084_1873
""".split()


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


# Acts the basedoc does not hold (most acts before 1992): the same Avance Jurídico compilation as published by
# Colpensiones (a state company), one page per act, read only for the act's heading and vigencia clause.
COLPENSIONES = "https://normativa.colpensiones.gov.co/colpens/docs/"


def old_laws() -> None:
    for n in LAW_PAGES:
        if F.cached(F.BASE + n + ".html") is None:
            b = get(COLPENSIONES + n + ".htm")
            print(n, None if b is None else len(b), flush=True)


def main(argv):
    if argv[:1] == ["old"]:
        old_laws()
    elif argv[:1] == ["laws"]:
        for n in LAW_PAGES:
            print(n, len(last_page(n)), flush=True)
    elif argv[:1] == ["url"]:
        for u in argv[1:]:
            b = get(u)
            print(u, None if b is None else len(b))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
