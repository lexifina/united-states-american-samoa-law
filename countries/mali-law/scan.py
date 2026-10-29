"""Searches the cached Journal officiel issues for a pattern (to find a law, or the laws amending an act).

    python -X utf8 scripts/mali-law/scan.py REGEX [FROM] [TO]

Reads only the cache. Text comes from the PDF text layer (PyMuPDF); issues without one are reported as scans.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402
from jo_index import jo_index  # noqa: E402


def jo_text(url: str) -> str:
    d = fitz.open(stream=fetch.fetch(url, offline=True), filetype='pdf')
    return '\n'.join(p.get_text() for p in d)


def main(pat: str, lo: str = '0000', hi: str = '9999') -> None:
    rx = re.compile(pat, re.I)
    for r in sorted(jo_index(), key=lambda r: r['date']):
        if not lo <= r['date'] <= hi or not fetch.cache_path(r['url']).exists():
            continue
        try:
            t = jo_text(r['url'])
        except Exception as e:  # noqa: BLE001
            print(r['date'], r['url'], 'UNREADABLE', type(e).__name__)
            continue
        if len(t.strip()) < 200:
            print(r['date'], r['url'], 'SCAN (no text layer)')
            continue
        flat = ' '.join(t.split())
        for m in rx.finditer(flat):
            print(r['date'], r['url'].rsplit('/', 1)[-1], '|', flat[max(0, m.start() - 80):m.end() + 160])


if __name__ == '__main__':
    main(*sys.argv[1:])
