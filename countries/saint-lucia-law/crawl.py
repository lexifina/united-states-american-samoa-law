"""Fetch every page of the Phase 1 acts from the Revised Laws of Saint Lucia (2023) site, in table-of-contents order.

    python -X utf8 crawl.py constitution-of-saint-lucia data-protection-act criminal-code

Pages are cached by fetch.py (sha256 of the URL); a rerun fetches only what is missing.
Subsidiary legislation pages (statutory instruments listed under an act) are skipped: Phase 1 builds the acts.
"""
from __future__ import annotations

import re
import sys

import fetch

BASE = 'https://attorneygeneralchambers.com/laws-of-saint-lucia/'


def toc(act: str) -> list[str]:
    t = fetch.get(BASE + act).decode('utf-8')
    hs = list(dict.fromkeys(re.findall(r'href="/laws-of-saint-lucia/' + re.escape(act) + r'/([^"#?]*)"', t)))
    return hs


def is_sub(h: str) -> bool:
    return 'statutory-instrument' in h or h.startswith('proclamation') or h == 'subsidiary-legislation'


def main(acts: list[str]) -> None:
    for act in acts:
        hs = [h for h in toc(act) if not is_sub(h)]
        print(act, len(hs), 'pages', flush=True)
        for n, h in enumerate(hs):
            try:
                fetch.get(BASE + act + '/' + h)
            except RuntimeError as e:
                print('FAIL', e, flush=True)
            if n % 100 == 0:
                print(' ', n, h, flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
