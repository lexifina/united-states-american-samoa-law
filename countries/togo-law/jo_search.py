"""List jo.gouv.tg search results (node, title, PDF link) for a nature and a title/body query, all pages.

    python -X utf8 jo_search.py <nature_tid|All> <title> [<body words>]
"""
from __future__ import annotations

import html
import re
import sys
import urllib.parse

import fetch


def search(nature: str = 'All', title: str = '', body: str = '', max_pages: int = 10) -> list[dict]:
    out = []
    for page in range(max_pages):
        q = {'choix': 'on', 'field_nature_tid': nature, 'title': title, 'field_corps_du_texte_value': body}
        if page:
            q['page'] = str(page)
        url = 'https://jo.gouv.tg/recherche?' + urllib.parse.urlencode(q)
        h = (fetch.get(url) or b'').decode('utf-8', 'replace')
        i = h.find('view-content')
        if i < 0:
            break
        j = h.find('/Lois"', i)
        seg = h[i:j if j > 0 else None]
        rows = re.findall(r'<a href="(/node/\d+)"[^>]*>(.*?)</a>(.*?)<a href="(https?://jo\.gouv\.tg/sites/[^"]+)"', seg, re.S)
        for node, t, mid, pdf in rows:
            txt = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', t + ' ' + mid)).strip()
            out.append({'node': node, 'title': txt, 'pdf': pdf})
        if 'pager-next' not in h:
            break
    return out


if __name__ == '__main__':
    a = sys.argv[1:] + ['', '', '']
    for r in search(a[0], a[1], a[2]):
        print(r['node'], '|', r['title'][:160], '|', urllib.parse.unquote(r['pdf']))
