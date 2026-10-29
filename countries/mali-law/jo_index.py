"""The Journal officiel index of sgg-mali.ml, read from the cached listing page.

    python -X utf8 scripts/mali-law/jo_index.py [FROM YYYY-MM-DD] [TO YYYY-MM-DD] [--fetch]

Prints (and with --fetch downloads) every JO issue in the date range. jo_index() is used by parse.py and scan.py.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

INDEX = 'https://sgg-mali.ml/fr/journal-officiel/le-journal-officiel.html'
SPECIAL = 'https://sgg-mali.ml/fr/journal-officiel/journaux-speciaux.html'


def jo_index() -> list[dict]:
    t = fetch.fetch(INDEX, offline=True).decode('utf-8', 'replace')
    out = []
    for url, label in re.findall(r"href='([^']+\.pdf)'[^>]*>(.*?)</a>", t, flags=re.S):
        label = ' '.join(html.unescape(re.sub(r'<[^>]+>|subject', ' ', label)).split())
        m = re.search(r'JO n°(\S+)\s*(spécial)?\s*du (\d\d)/(\d\d)/(\d{4})', label)
        if not m:
            continue
        out.append({'url': url, 'label': label, 'num': m.group(1), 'special': bool(m.group(2)),
                    'date': f'{m.group(5)}-{m.group(4)}-{m.group(3)}'})
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    lo = args[0] if args else '0000'
    hi = args[1] if len(args) > 1 else '9999'
    rows = [r for r in jo_index() if lo <= r['date'] <= hi]
    rows.sort(key=lambda r: (r['date'], r['url']))
    for r in rows:
        print(r['date'], r['url'])
    if '--fetch' in sys.argv:
        res = fetch.fetch_many([r['url'] for r in rows], threads=3)
        bad = [u for u, b in res.items() if isinstance(b, Exception)]
        print(len(rows) - len(bad), 'cached;', len(bad), 'failed', bad)
