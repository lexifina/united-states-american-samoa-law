"""Index of the archived Journal officiel website (jo.gouv.sn, SPIP, about 2005-2018), read from Wayback only.

jo.gouv.sn no longer answers (connection refused, 2026-10-28). Its pages survive as Internet Archive captures:
- spip.php?rubriqueN: one Journal officiel issue ("7123 du samedi 15 septembre 2018") with the titles of its texts
  and links to spip.php?articleN;
- spip.php?articleN: the full text of one published text, as HTML.

    python -X utf8 scripts/senegal-law/jo_index.py          # fetch every captured rubrique page, write jo_index.json

The CDX listing (one request) gives the capture of each rubrique; each is fetched once through
gitlaw_common/wayback.py (shared machine-wide rate) and cached in .cache/.
"""
from __future__ import annotations

import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sncache  # noqa: E402

CDX = ('https://web.archive.org/cdx/search/cdx?url=jo.gouv.sn&matchType=domain&output=json'
       '&fl=timestamp,original,mimetype,statuscode,length&filter=statuscode:200&filter=mimetype:text/html'
       '&collapse=urlkey&limit=20000&showResumeKey=true')


def cdx_rows(offline: bool = False) -> list[list[str]]:
    from urllib.parse import quote
    rows, key = [], None
    while True:
        data = json.loads(sncache.get(CDX + (f'&resumeKey={quote(key, safe="")}' if key else ''), offline))
        key = None
        if data and data[-1] and len(data[-1]) == 1:
            key = data[-1][0]
            data = data[:-2]
        rows += [r for r in data[1:] if len(r) == 5]
        if not key:
            return rows


def decode(b: bytes) -> str:
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('cp1252', 'replace')


def text_of(fragment: str) -> str:
    t = html.unescape(re.sub(r'<[^>]+>', ' ', fragment))
    return re.sub(r'\s+', ' ', t).strip()


def rubrique_info(b: bytes) -> dict:
    s = decode(b)
    i = s.find('PRECEDENT')
    body = s[i:] if i >= 0 else s
    j = body.find('Copyrights')
    body = body[:j] if j >= 0 else body
    head = text_of(body.split('<a', 2)[1] if body.count('<a') > 1 else body)
    issue = re.search(r'PRECEDENT\s*</a>(.*?)<', body, re.S)
    arts = []
    for m in re.finditer(r'<a[^>]+href="[^"]*?article(\d+)[^"]*"[^>]*>(.*?)</a>', body, re.S):
        arts.append({'id': int(m.group(1)), 'title': text_of(m.group(2))})
    return {'issue': text_of(issue.group(1)) if issue else head[:120], 'articles': arts}


def main(offline: bool = False) -> None:
    rows = cdx_rows(offline)
    rub = {}
    for ts, orig, *_ in rows:
        m = re.search(r'\?rubrique(\d+)$', orig)
        if m and 'spip.php' in orig:
            rub.setdefault(int(m.group(1)), (ts, orig))

    def one(item):
        rid, (ts, orig) = item
        try:
            return rid, ts, orig, rubrique_info(sncache.get(sncache.raw(ts, orig), offline))
        except Exception as e:  # a missing capture is listed, never fatal
            return rid, ts, orig, {'error': str(e)[:200]}

    with ThreadPoolExecutor(8) as ex:
        out = list(ex.map(one, sorted(rub.items())))
    index = [{'rubrique': rid, 'ts': ts, 'url': orig, **info} for rid, ts, orig, info in out]
    (HERE / 'jo_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=0) + '\n', encoding='utf-8',
                                        newline='\n')
    print(len(index), 'rubriques;', sum(len(x.get('articles', [])) for x in index), 'article links;',
          sum(1 for x in index if 'error' in x), 'errors')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main('--offline' in sys.argv)
