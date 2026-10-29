"""Read a Diputados reform list (ref/cpeum_crono.htm, ref/<code>.htm) into decree rows. Reads only the cache."""
from __future__ import annotations

import html
import re
from datetime import date

ROW = re.compile(r'(?is)<tr[^>]*>(.*?)</tr>')
CELL = re.compile(r'(?is)<td[^>]*>(.*?)</td>')
HREF = re.compile(r'(?i)href="([^"]+)"')
DMY = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')


def clean(s: str) -> str:
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = html.unescape(s).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def decode(raw: bytes) -> str:
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp1252', 'replace')


def rows(raw: bytes) -> list[dict]:
    """Every table row that carries a DOF date (dd/mm/yyyy) and a decree title. Order as printed."""
    t = decode(raw)
    out = []
    for r in ROW.findall(t):
        cells = CELL.findall(r)
        if len(cells) < 2:
            continue
        texts = [clean(c) for c in cells]
        when = None
        for x in texts:
            m = DMY.fullmatch(x.strip())
            if m:
                when = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if not when:
            continue
        ti = max(range(len(texts)), key=lambda i: len(texts[i]))
        title = texts[ti]
        # Decree 73 (DOF 14-02-1972) is printed as "REFORMAS y Adiciones a los artículos ...", so "reforma" counts too.
        if not re.search(r'(?i)decreto|fe de erratas|aclaraci|sentencia|declaratoria|acuerdo|ley|reforma', title):
            continue
        # The cell's first paragraph is the decree's own title; the rest is the publisher's summary.
        paras = [clean(p) for p in re.findall(r'(?is)<p[^>]*>(.*?)(?=<p[^>]*>|</td>)', cells[ti])]
        paras = [p for p in paras if p]
        name = paras[0] if paras else title
        num = None
        for x in texts:
            if re.fullmatch(r'\d{1,4}', x):
                num = int(x)
        links = [h for c in cells for h in HREF.findall(c)]
        out.append({'num': num, 'title': title, 'name': name, 'dof': when.isoformat(), 'links': links})
    return out
