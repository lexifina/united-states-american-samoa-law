"""Index parsers for the cached Guyana source pages (no network: read the cache only)."""
from __future__ import annotations

import html
import re

import fetch

MOLA_INDEX = ['https://www.mola.gov.gy/laws-of-guyana'] + [f'https://www.mola.gov.gy/laws-of-guyana?page={i}' for i in range(2, 53)]
PARL_INDEX = ['https://parliament.gov.gy/publications/acts-of-parliament/'] + [
    f'https://parliament.gov.gy/publications/acts-of-parliament/P{i}' for i in range(10, 1850, 10)]
MONTHS = {m: i for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(), 1)}


def _date(s: str) -> str | None:
    m = re.match(r'\s*(\d{1,2}) ([A-Z][a-z]{2}),\s*(\d{4})', s or '')
    if not m:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}'


def mola_chapters() -> list[dict]:
    rows = []
    for u in MOLA_INDEX:
        b = fetch.cached(u)
        if not b:
            continue
        h = b.decode('utf-8', 'replace')
        for m in re.finditer(r'<a href="(https://www\.mola\.gov\.gy/laws/[^"]+)" target="_blank"><h6 class="card-title" >([^<]+)</h6>', h):
            rows.append({'title': html.unescape(m.group(2)).strip(), 'url': m.group(1)})
    return rows


def parliament_acts() -> list[dict]:
    rows = []
    for u in PARL_INDEX:
        b = fetch.cached(u)
        if not b:
            continue
        h = b.decode('utf-8', 'replace')
        for tr in re.findall(r'<tr class="(?:odd|even)">(.*?)</tr>', h, re.S):
            t = re.search(r'<a href="([^"]+)">\s*([^<]+)</a>', tr)
            passed = re.search(r'Date Passed</h5><span class="common-td">([^<]*)<', tr)
            pub = re.search(r'Published Date</h5><span class="common-td">([^<]*)<', tr)
            pdf = re.search(r'<a href="([^"]+\.pdf)"', tr, re.I)
            rows.append({'title': html.unescape(t.group(2)).strip() if t else '', 'page': t.group(1) if t else '',
                         'passed': _date(passed.group(1)) if passed else None,
                         'published': _date(pub.group(1)) if pub else None,
                         'pdf': pdf.group(1) if pdf else None})
    return rows
