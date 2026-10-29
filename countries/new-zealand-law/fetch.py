"""New Zealand: find and cache every archived official consolidation ("as at" version) of each act.

legislation.govt.nz (Parliamentary Counsel Office) answers this machine with an AWS WAF bot challenge (HTTP 202,
x-amzn-waf-action: challenge), and its API needs a key, so nothing is fetched from it directly. Common Crawl does not
hold the site (its CDX blocks jump from lawcom.govt.nz to linz.govt.nz). The Internet Archive does: this reads its
`id_` raw captures through the shared machine-wide client scripts/gitlaw_common/wayback.py.

Pages used, per act (year Y, number N):
- old site (to early 2026): /act/public/Y/NNNN/latest/whole.html and /act/public/Y/NNNN/<k>.0/whole.html
- new site (from 2026):     /act/public/Y/N/en/latest/ and /act/public/Y/N/en/<as-at date>/
Each page is one official consolidation and states its date ("as at 4 September 2026").

`latest` captures move forward in time, so the distinct "as at" dates among them are found by bisection: fetch both
ends of a run of captures; if they state the same date, nothing in between differs; otherwise split. Numbered and
dated pages are fetched directly. The result is captures.json (one row per fetched capture with its stated date and
the sha256 of the bytes); parse.py reads only that file and the cache.

    python -X utf8 fetch.py [act-slug ...] [--cached-only]   # --cached-only: record what the cache holds, no network
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
OUT = HERE / 'captures.json'

ACTS = {
    'constitution-act': (1986, 114),
    'bill-of-rights-act': (1990, 109),
    'privacy-act': (2020, 31),
    'crimes-act': (1961, 43),
}
MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}


def as_at(body: bytes) -> str | None:
    t = body.decode('utf-8', 'replace')
    m = re.search(r'<title>[^<]*?\(as at (\d{1,2}) ([A-Za-z]+) (\d{4})\)', t) or \
        re.search(r'[Aa]s at (\d{1,2}) ([A-Za-z]+) (\d{4})', t)
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'


def page_kind(url: str, y: int, n: int) -> str | None:
    p = re.sub(r'^https?://[^/]+', '', url).split('?')[0].split('#')[0]
    if re.fullmatch(rf'/act/public/{y}/{n:04d}/(latest|\d+\.0)/whole\.html', p):
        return 'old-latest' if '/latest/' in p else 'old-numbered'
    m = re.fullmatch(rf'/act/public/{y}/{n}/en/(latest|\d{{4}}-\d\d-\d\d)/?', p)
    if m:
        return 'new-latest' if m.group(1) == 'latest' else 'new-dated'
    return None


def listing(y: int, n: int) -> list[dict]:
    rows = []
    for pre in (f'legislation.govt.nz/act/public/{y}/{n:04d}/', f'legislation.govt.nz/act/public/{y}/{n}/'):
        for c in wayback.captures(pre, match='prefix', cache=CACHE, collapse=None):
            k = page_kind(c['original'], y, n)
            if k and c['statuscode'] == '200' and c['mimetype'].startswith('text/html'):
                rows.append({**c, 'kind': k})
    rows.sort(key=lambda c: c['timestamp'])
    return rows


CACHED_ONLY = '--cached-only' in sys.argv


def get(c: dict) -> dict:
    url = f'https://web.archive.org/web/{c["timestamp"]}id_/{c["original"]}'
    if CACHED_ONLY:
        hit = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
        b = hit.read_bytes() if hit.exists() else None
    else:
        b = wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)
    d = as_at(b) if b else None
    return {'timestamp': c['timestamp'], 'url': c['original'], 'kind': c['kind'], 'as_at': d,
            'bytes': len(b) if b else 0, 'sha256': hashlib.sha256(b).hexdigest() if b else None}


def run(slug: str, done: dict) -> list[dict]:
    y, n = ACTS[slug]
    rows = listing(y, n)
    got: dict[str, dict] = {r['timestamp'] + r['url']: r for r in done.get(slug, [])}

    def fetch(cs):
        todo = [c for c in cs if c['timestamp'] + c['original'] not in got or not got[c['timestamp'] + c['original']]['sha256']]
        with ThreadPoolExecutor(4) as ex:
            for r in ex.map(get, todo):
                got[r['timestamp'] + r['url']] = r
        return [got[c['timestamp'] + c['original']] for c in cs]

    # numbered/dated pages: each is one version
    fetch([c for c in rows if c['kind'] in ('old-numbered', 'new-dated')])
    # latest pages: bisect (skipping captures that fail or state no date)
    latest = [c for c in rows if c['kind'] in ('old-latest', 'new-latest')]
    # one capture per distinct digest is enough
    seen, uniq = set(), []
    for c in latest:
        if c['digest'] not in seen:
            seen.add(c['digest'])
            uniq.append(c)
    latest = uniq

    def date_at(i):
        r = fetch([latest[i]])[0]
        return r['as_at']

    def bisect(lo, hi, dlo, dhi):
        while dlo is None and lo < hi:
            lo += 1
            dlo = date_at(lo)
        while dhi is None and hi > lo:
            hi -= 1
            dhi = date_at(hi)
        if hi - lo <= 1 or dlo == dhi:
            return
        mid = (lo + hi) // 2
        dm = date_at(mid)
        bisect(lo, mid, dlo, dm)
        bisect(mid, hi, dm, dhi)

    if latest:
        bisect(0, len(latest) - 1, date_at(0), date_at(len(latest) - 1))
    out = sorted(got.values(), key=lambda r: r['timestamp'])
    print(slug, len(rows), 'pages listed,', len(out), 'fetched; as-at dates:',
          sorted({r['as_at'] for r in out if r['as_at']}), flush=True)
    return out


def main():
    done = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    for slug in [a for a in sys.argv[1:] if not a.startswith('--')] or list(ACTS):
        done[slug] = run(slug, done)
        tmp = OUT.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(done, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
        tmp.replace(OUT)


if __name__ == '__main__':
    main()
