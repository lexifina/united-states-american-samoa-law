"""Fetch archived Justel consolidated texts (French) from the Internet Archive.

Justel's robots.txt disallows /cgi_loi/, /eli/ and /mopdf/ for every crawler, so Justel is never fetched
directly: only Internet Archive `id_` captures, through the shared machine-wide client (wayback.get). Common
Crawl honours robots.txt and holds no Justel pages.

The capture lists are the archive.org CDX listings already cached (one request each, 2026-10-28):
  www.ejustice.just.fgov.be/cgi_loi/article.pl, /cgi_loi/loi_a1.pl, /eli/constitution/, /eli/loi/ (prefix).
For each Justel text number (cn) we take the French current-text captures (not `arch=` archived-version pages),
one per distinct CDX digest, and keep only those whose compressed size shows a full text.

    python -X utf8 scripts/belgium-law/fetch_justel.py [cn ...]
Writes .cache/justel/captures.json (cn -> [{ts, url, wb}]) and caches every page body.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

CDX = [
    'https://web.archive.org/cdx/search/cdx?url=www.ejustice.just.fgov.be/cgi_loi/article.pl&output=json&matchType=prefix&fl=timestamp,original,mimetype,statuscode,digest,length&filter=statuscode:200&collapse=digest',
    'https://web.archive.org/cdx/search/cdx?url=www.ejustice.just.fgov.be/cgi_loi/loi_a1.pl&output=json&matchType=prefix&fl=timestamp,original,mimetype,statuscode,digest,length&filter=statuscode:200&collapse=digest',
]
# Justel text numbers: Constitution, Code penal 1867, old Code civil (Justel splits it in parts)
TEXTS = {
    '1994021730': 'Constitution coordonnee',
    '1867060801': 'Code penal (1867)',
    '1804032130': 'Code civil, part 30', '1804032131': 'Code civil, part 31', '1804032132': 'Code civil, part 32',
    '1804032133': 'Code civil, part 33', '1804032134': 'Code civil, part 34', '1804032135': 'Code civil, part 35',
    '1804032136': 'Code civil, part 36',
}
MIN_LEN = 15000   # compressed WARC bytes; error and search pages are smaller
ELI_CDX = ('https://web.archive.org/cdx/search/cdx?url=www.ejustice.just.fgov.be/eli/loi/&output=json&matchType=prefix'
           '&fl=timestamp,original,mimetype,statuscode,digest,length&filter=statuscode:200&collapse=digest')
# ELI pages are named by NUMAC; Justel's text number (cn) differs
# the new Code civil (2019-): Justel's consolidated books, by NUMAC
BOOKS = {'2022A32057': 'livre 1', '2022A30600': 'livre 2, titre 3', '2020A20347': 'livre 3',
         '2022B30600': 'livre 4', '2022A32058': 'livre 5', '2024A01600': 'livre 6', '2019A12168': 'livre 8',
         '2025A05089': 'livre 9, titre 1'}
ELI_NUMAC = {'1867060850': '1867060801', '1804032150': '1804032130', '1804032151': '1804032131',
             '1804032152': '1804032132', '1804032153': '1804032133', '1804032154': '1804032134',
             '1804032155': '1804032135'}


def french(url: str) -> bool:
    u = url.lower().replace('%2f', '/')
    if re.search(r'[?&](arch=|la=[nd]\b|language=(nl|de)\b|lg_txt=[nd]\b|table_name=wet\b)', u) or '/n&' in u \
            or u.endswith('/n'):
        return False
    return bool(re.search(r'[?&](la=f\b|lg_txt=fr?\b|language=fr\b)', u) or re.search(r'detail=\d{10}/f', u))


def listing() -> dict[str, list[dict]]:
    by: dict[str, dict] = {}
    for u in CDX:
        p = CACHE / hashlib.sha256(u.encode()).hexdigest()
        rows = json.loads(p.read_text(encoding='utf-8'))[1:]
        for ts, orig, mt, sc, dg, ln in rows:
            m = re.search(r'cn(?:_search)?=(\d{10})', orig) or re.search(r'DETAIL=(\d{10})', orig)
            if not m or m.group(1) not in TEXTS or not french(orig) or int(ln) < MIN_LEN:
                continue
            d = by.setdefault(m.group(1), {})
            d.setdefault(dg, {'ts': ts, 'url': orig, 'digest': dg})
    p = CACHE / hashlib.sha256(ELI_CDX.encode()).hexdigest()
    for ts, orig, mt, sc, dg, ln in json.loads(p.read_text(encoding='utf-8'))[1:]:
        m = re.search(r'/eli/loi/\d{4}/\d\d/\d\d/([0-9A-Z]{10})/justel$', orig)
        if not m or not ln.isdigit():
            continue
        if m.group(1) in ELI_NUMAC and int(ln) >= MIN_LEN:
            by.setdefault(ELI_NUMAC[m.group(1)], {}).setdefault(dg, {'ts': ts, 'url': orig, 'digest': dg})
        elif m.group(1) in BOOKS and int(ln) >= 4000:   # the new Code civil's books are short pages
            by.setdefault(m.group(1), {}).setdefault(dg, {'ts': ts, 'url': orig, 'digest': dg})
    return {cn: sorted(d.values(), key=lambda r: r['ts']) for cn, d in by.items()}


def wb_url(r: dict) -> str:
    return f'https://web.archive.org/web/{r["ts"]}id_/{r["url"]}'


def sample(rows: list[dict], per_half_year: int = 1, newest: int = 3) -> list[dict]:
    """The last capture of each half-year, plus the newest few: enough to see every wording that lasted months
    (archive.org serves this machine about one capture per 2-3 seconds, shared by every agent)."""
    by: dict[str, dict] = {}
    for r in rows:
        half = r['ts'][:4] + ('a' if r['ts'][4:6] <= '06' else 'b')
        by[half] = r
    keep = {r['ts'] for r in by.values()} | {r['ts'] for r in rows[-newest:]}
    return [r for r in rows if r['ts'] in keep]


def main() -> None:
    args = sys.argv[1:]
    full = '--all' in args
    want = [a for a in args if not a.startswith('--')] or list(TEXTS)
    caps = listing()
    out = CACHE / 'justel'
    out.mkdir(exist_ok=True)
    allc = {cn: [dict(r, wb=wb_url(r)) for r in caps.get(cn, [])] for cn in [*TEXTS, *BOOKS]}
    (out / 'captures.json').write_text(json.dumps(allc, indent=1), encoding='utf-8')
    todo = [r for cn in want for r in (allc.get(cn, []) if full else sample(allc.get(cn, [])))]
    todo = [r for r in todo if not (CACHE / hashlib.sha256(r['wb'].encode()).hexdigest()).exists()]
    print(len(todo), 'captures to fetch')

    def one(r):
        body = wayback.fetch(r['wb'], cache=CACHE)
        return r['wb'], len(body or b'')

    with ThreadPoolExecutor(8) as pool:
        for i, (u, n) in enumerate(pool.map(one, todo)):
            if not n:
                print('missing', u)
            if i % 50 == 0:
                print(i, flush=True)


if __name__ == '__main__':
    main()
