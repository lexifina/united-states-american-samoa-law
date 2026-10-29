"""Discovery only: fetch a clean Wayback capture of each Editora Peru NLA document (idNorma) and print its title.

Captures from September 2026 on are corrupt (El Peruano now replaces every byte >= 0x80 with U+FFFD), so this
takes the latest capture before 2026-09.

    python -X utf8 more/nla_titles.py ID [ID ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(__file__).resolve().parent.parent / '.cache'
NLA = 'diariooficial.elperuano.pe/Normas/obtenerDocumento?idNorma={n}'
CORRUPT_FROM = '20260901'
fitz.TOOLS.mupdf_display_errors(False)


def clean_captures(n: str) -> list[dict]:
    return [c for c in wayback.captures(NLA.format(n=n), cache=CACHE)
            if c['mimetype'] == 'application/pdf' and c['timestamp'] < CORRUPT_FROM]


def main(ids):
    for n in ids:
        caps = clean_captures(n)
        if not caps:
            print(n, 'no clean capture', flush=True)
            continue
        ts = caps[-1]['timestamp']
        body = wayback.get('https://' + NLA.format(n=n), ts=ts, cache=CACHE)
        if not body:
            print(n, ts, 'fetch failed', flush=True)
            continue
        try:
            d = fitz.open(stream=body, filetype='pdf')
            t = ' '.join(' '.join(d[i].get_text() for i in range(min(3, d.page_count))).split())[:200]
            print(n, ts, [c['timestamp'] for c in caps], d.page_count, 'pp |', t, flush=True)
        except Exception as e:
            print(n, ts, 'bad pdf', e, flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
