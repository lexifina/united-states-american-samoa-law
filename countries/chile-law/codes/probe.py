"""Prints, from the cache, what LeyChile says each candidate idNorma is (versions list, refundidos chain)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

for idn in [int(x) for x in sys.argv[1:]]:
    for url in (fetch.versions_url(idn), fetch.chain_url(idn)):
        try:
            raw = fetch.fetch(url, offline=True)
        except FileNotFoundError:
            print(idn, 'not cached', url); continue
        print(idn, url.split('/')[-1][:40], raw[:1500].decode('utf-8', 'replace'))
    try:
        vs = fetch.versions(idn, offline=True)
        print(idn, 'versions', len(vs), vs[0]['@vigenteDesde'], vs[-1]['@vigenteDesde'], vs[-1].get('@vigenteHasta'))
    except Exception as e:
        print(idn, 'err', e)
