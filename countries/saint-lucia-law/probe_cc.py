"""List archived captures of the Phase 1 acts' pages (Common Crawl across all crawls, then archive.org CDX).

Writes .cache/captures.json: {prefix: [records]}. Read-only probe; parse.py never needs it.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
PREFIXES = [
    'attorneygeneralchambers.com/laws-of-saint-lucia/constitution-of-saint-lucia',
    'attorneygeneralchambers.com/laws-of-saint-lucia/criminal-code',
    'attorneygeneralchambers.com/laws-of-saint-lucia/data-protection-act',
]


def main() -> None:
    crawls = wayback.cc_crawls(CACHE)
    out: dict[str, list] = {}
    for p in PREFIXES:
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda c: wayback.cc_captures(p, crawls=[c], match='prefix', cache=CACHE), crawls))
        recs = [r for rs in res for r in rs]
        out['cc:' + p] = recs
        print(p, 'CC', len(recs), sorted({r['timestamp'][:6] for r in recs}), flush=True)
    for p in ['attorneygeneralchambers.com/laws-of-saint-lucia/', 'attorneygeneralchambers.com/']:
        try:
            caps = wayback.captures(p, match='prefix', cache=CACHE)
        except Exception as e:  # noqa: BLE001
            caps = []
            print('wayback fail', p, e)
        out['ia:' + p] = caps
        print(p, 'IA', len(caps), flush=True)
    (CACHE / 'captures.json').write_text(json.dumps(out), encoding='utf-8')


if __name__ == '__main__':
    main()
