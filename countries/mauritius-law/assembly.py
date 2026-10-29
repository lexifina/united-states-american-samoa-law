"""The National Assembly's "Acts as passed by Parliament and Gazetted" table, as data.

    python -X utf8 scripts/mauritius-law/assembly.py index            # write .tmp/assembly_index.json
    python -X utf8 scripts/mauritius-law/assembly.py fetch 2015 2026  # fetch every Act PDF of those years
    python -X utf8 scripts/mauritius-law/assembly.py grep REGEX        # Acts whose text matches REGEX

Reads only the cached listing page (fetched by fetch.py). Each row gives the Act number, title, and the dates
Introduced, Passed, Assented, Gazetted and "Date in force" ('*' = by Proclamation; footnotes are kept verbatim).
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

LISTING = 'https://mauritiusassembly.govmu.org/mauritiusassembly/index.php/acts-2/'
SKIP = re.compile(r'(?i)appropriation|additional remuneration')


def _clean(s: str) -> str:
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).replace('​', '').strip()


def index(offline: bool = True) -> list[dict]:
    b = fetch.fetch(LISTING, offline).decode('utf-8', 'replace')
    out, year, notes = [], None, []
    for row in re.findall(r'(?s)<tr.*?</tr>', b):
        cells = [_clean(c) for c in re.findall(r'(?s)<t[dh][^>]*>(.*?)</t[dh]>', row)]
        links = [html.unescape(x) for x in re.findall(r'href="([^"]+)"', row)]
        if not cells:
            continue
        m = re.search(r'Acts as passed by Parliament and Gazetted for year (\d{4})', ' '.join(cells))
        if m:
            year = int(m.group(1))
            continue
        pdfs = [x for x in links if x.lower().endswith('.pdf') and '_debates' not in x.lower()
                and '_amendments' not in x.lower()]
        if not cells[0] or not pdfs:
            if year and cells[0].lstrip().startswith('*') and len(cells[0]) > 3:
                out.append({'year': year, 'footnote': cells[0]})
            if year and len(cells) > 1 and cells[1].startswith('The Reprint of Laws') and pdfs:
                pass
            if not pdfs:
                continue
        num = re.sub(r'\s+', '', re.sub(r'(?i)^act\s*no\.?', '', cells[0])).split('of')[0] if cells[0] else ''
        dates = (cells + [''] * 7)[2:7]
        out.append({'year': year, 'no': int(num) if num.isdigit() else None, 'title': cells[1] if len(cells) > 1 else '',
                    'introduced': dates[0], 'passed': dates[1], 'assented': dates[2], 'gazetted': dates[3],
                    'in_force': dates[4], 'pdf': pdfs[0].replace('http://', 'https://')})
    return out


def text(url: str) -> str:
    """The PDF's text layer (pdftotext -layout), empty if it has none."""
    p = fetch.path(url)
    r = subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', str(p), '-'], capture_output=True)
    return r.stdout.decode('utf-8', 'replace')


def main(argv: list[str]) -> None:
    if argv[0] == 'index':
        rows = index(offline=False)
        (HERE / '.tmp').mkdir(exist_ok=True)
        (HERE / '.tmp' / 'assembly_index.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
        print(len(rows))
    elif argv[0] == 'fetch':
        lo, hi = int(argv[1]), int(argv[2])
        for r in index():
            if r.get('pdf') and lo <= (r['year'] or 0) <= hi and not SKIP.search(r['title']):
                try:
                    fetch.fetch(r['pdf'])
                except Exception as e:  # noqa: BLE001
                    print('FAIL', r['pdf'], e, flush=True)
        print('done')
    elif argv[0] == 'grep':
        rx = re.compile(argv[1])
        for r in index():
            if r.get('pdf') and fetch.path(r['pdf']).exists():
                t = text(r['pdf'])
                hits = rx.findall(t)
                if hits:
                    print(r['year'], r['no'], r['title'], r['in_force'], len(hits))


if __name__ == '__main__':
    main(sys.argv[1:])
