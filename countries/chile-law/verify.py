"""Checks corpus.json against LeyChile's current consolidated text.

    python -X utf8 scripts/chile-law/verify.py [--corpus PATH] [--date YYYY-MM-DD] [--offline]

For each act, fetches (once, through fetch.py's cache) the text LeyChile serves for the act's norm on --date (the day
the data was retrieved) and compares it, unit by unit, with the corpus version in force on that day. It also checks
that every version carries the sha256 of a cached source file. Prints one JSON line per act and exits 1 on any
difference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import parse  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', default=str(HERE / 'corpus.json'))
    ap.add_argument('--date', default='2026-10-28')
    ap.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    c = json.loads(Path(args.corpus).read_text(encoding='utf-8'))
    cached = {p.name for p in fetch.CACHE.iterdir()}
    sums = set()
    for name in cached:
        if len(name) == 64:
            sums.add(hashlib.sha256((fetch.CACHE / name).read_bytes()).hexdigest())
    bad = 0
    for a in c['acts']:
        meta = parse.ACT_META[a['slug']]
        norm = fetch.ACTS[a['slug']][-1]
        live = [v for v in a['versions'] if v['from'] <= args.date][-1]
        # The version of the norm in force on the date, by LeyChile's own versions list.
        vs = fetch.versions(norm, offline=True)
        day = [v['@vigenteDesde'] for v in vs if v['@vigenteDesde'] <= args.date][-1]
        raw = fetch.fetch(fetch.version_url(norm, day), offline=args.offline)
        width = len(next(k for k in live['units'] if k.startswith('art-')).split('-')[1])
        units = parse.read_version(raw, width, meta.get('part'))['units']
        diff = sorted(k for k in set(units) | set(live['units'])
                      if units.get(k, {}).get('text') != live['units'].get(k, {}).get('text'))
        # The unversioned reader text (what the LeyChile page shows today), when cached or fetchable.
        cur_url = (f'{fetch.SERVICE}/Navegar/get_norma_json?idNorma={norm}&idVersion=&idLey=&tipoVersion=&cve='
                   '&agrupa_partes=1&r=')
        try:
            cur = parse.read_version(fetch.fetch(cur_url, offline=args.offline), width, meta.get('part'))['units']
            cur_diff = sorted(k for k in set(cur) | set(live['units'])
                              if cur.get(k, {}).get('text') != live['units'].get(k, {}).get('text'))
        except FileNotFoundError:
            cur_diff = None
        unsourced = [v['from'] for v in a['versions'] if v['sha256'] not in sums]
        ok = not diff and not cur_diff and not unsourced
        bad += not ok
        print(json.dumps({'act': a['slug'], 'in_force_on': args.date, 'corpus_version': live['from'],
                          'leychile_version': day, 'units': len(live['units']), 'differences': diff[:20],
                          'differences_vs_current_page': cur_diff if cur_diff is None else cur_diff[:20],
                          'versions': len(a['versions']), 'versions_without_cached_source': unsourced}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
