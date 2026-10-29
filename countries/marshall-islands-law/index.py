"""Index of the Marshall Islands Revised Code (MIRC) on rmiparliament.org (Nitijela, Office of the Legislative Counsel).

METADATA ONLY. This reads the listing pages (titles, legislation numbers, PDF links, version history, commencement
dates) and never downloads an act's PDF. The texts may not be reused commercially without the permission of the
Marshall Islands Attorney General's Chambers (the site's rights statement), so no legal text is fetched or stored
in this folder until that permission arrives. See PERMISSION_REQUEST.md and PROGRESS.md.

Output goes to .cache/ (never pushed):
  .cache/index.json   one record per principal act: title, number, MIRC title, versions, amending acts.

Run: python -X utf8 scripts/marshall-islands-law/index.py [--titles 31 1 ...]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
BASE = 'https://rmiparliament.org'
BY_TITLE = BASE + '/cms/legislation/acts-of-nitijela/by-title.html'
UA = 'Mozilla/5.0 (compatible; LexifinaResearch/1.0)'
_last = [0.0]


def fetch(url: str, data: str | None = None) -> str:
    key = hashlib.sha256((url + (' POST ' + data if data else '')).encode()).hexdigest()[:24]
    p = CACHE / 'pages' / (key + '.html')
    if p.exists():
        return p.read_text(encoding='utf-8', errors='replace')
    wait = 0.34 - (time.time() - _last[0])  # <= 3 requests a second (SPEED RULE)
    if wait > 0:
        time.sleep(wait)
    args = ['curl', '-sL', '-m', '120', '-A', UA, url]
    if data:
        args[1:1] = ['--data', data]
    body = subprocess.run(args, capture_output=True, check=True).stdout
    _last[0] = time.time()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    with (CACHE / 'requests.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'data': data, 'size': len(body), 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
    return body.decode('utf-8', errors='replace')


def _text(s: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).replace('\xa0', ' ').strip()


def parse(page: str) -> list[dict]:
    """Principal acts with their history modal and their 'amended by...' child rows."""
    modals = {}
    for m in re.finditer(r'id="myHistoryModal(\d+)".*?<h5 id="myModalLabel">(.*?)</h5>(.*?)class="modal-footer"', page, re.S):
        versions = []
        for b in m.group(3).split('<div class="rowHistory">')[1:]:
            href = re.search(r'href="([^"]+\.pdf)"', b)
            num = re.search(r'Version:</b>\s*(\d+)', b)
            fields = {k: _text(v) for k, v in re.findall(r'<b>(Date Commenced|Details|Date Changed):</b>(.*?)</div>', b, re.S)}
            versions.append({'version': int(num.group(1)) if num else None, 'pdf': BASE + href.group(1) if href else None,
                             'commenced': fields.get('Date Commenced'), 'details': fields.get('Details'),
                             'changed': fields.get('Date Changed')})
        modals[m.group(1)] = {'title': _text(m.group(2)), 'versions': versions}
    acts, cur = [], None
    for row in re.finditer(r'<tr class="(row[01]|collapse act-collapse(\d+))">(.*?)</tr>', page, re.S):
        body = row.group(3)
        link = re.search(r'href="(/cms/images/LEGISLATION/[^"]+\.pdf)"[^>]*>(.*?)(?:<div|&nbsp;<i)', body, re.S)
        num = re.search(r'Legislation Number: ([0-9A-Z-]+)', body)
        com = re.search(r'title="Date Commenced" data-bs-content="([^"]*)"', body)
        if row.group(1).startswith('row'):
            mid = re.search(r'href="#myHistoryModal(\d+)"', body)
            cur = {'title': _text(link.group(2)) if link else None, 'number': num.group(1) if num else None,
                   'current_pdf': BASE + link.group(1) if link else None,
                   'current_version': int(v.group(1)) if (v := re.search(r'&nbsp;\[(\d+)\]', body)) else None,
                   'commenced': com.group(1) if com else None,
                   'versions': modals.get(mid.group(1), {}).get('versions', []) if mid else [],
                   'amended_by': []}
            acts.append(cur)
        elif cur is not None and link:
            cur['amended_by'].append({'title': re.sub(r'^amended by\.\.\.\s*', '', _text(link.group(2))),
                                      'number': num.group(1) if num else None, 'pdf': BASE + link.group(1),
                                      'commenced': com.group(1) if com else None})
    return acts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--titles', nargs='*', type=int, default=list(range(1, 53)), help='MIRC title numbers (catid)')
    a = ap.parse_args()
    out = {'source': BY_TITLE, 'all': parse(fetch(BY_TITLE)), 'by_title': {}}
    for t in a.titles:
        out['by_title'][t] = [x['number'] for x in parse(fetch(BY_TITLE, f'catid={t}'))]
    tmp = CACHE / 'index.json.tmp'
    tmp.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    tmp.replace(CACHE / 'index.json')
    print(len(out['all']), 'principal acts;', {t: len(v) for t, v in out['by_title'].items()})


if __name__ == '__main__':
    main()
