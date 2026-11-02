"""Speed experiment B4 (2026-10-29): a bulk or sitemap route for Albania's QBZ (qbz.gov.al)?

albania-law used 698 requests: 40 listing pages (/acts?type=Ligj&size=100&page=N), then /versions and /relations
for each of 329 laws. qbz.gov.al has no robots.txt (the path serves the app's HTML), so no Disallow or Crawl-delay.
Probes, each one request through host_get:
  - sitemap.xml and API description files (openapi / api-docs);
  - the largest page size the list accepts, and whether it can sort or filter on the `versions` count;
  - whether one act's record embeds its versions or relations (expand / include parameters);
  - ELI paths (the list gives eliPath and an rdf field) as a bulk route.
    python -X utf8 speedb_albania.py <cache_dir>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(sys.argv[1])
API = 'https://qbz.gov.al/api/v1'
out: dict = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'probes': []}


def probe(url: str, note: str = '') -> bytes | None:
    t = time.time()
    b = wayback.host_get(url, CACHE, tries=2, timeout=120)
    kind = 'none'
    if b:
        s = b[:200].lstrip()
        kind = 'json' if s[:1] in (b'{', b'[') else 'xml' if s.startswith(b'<?xml') or s.startswith(b'<urlset') \
            or s.startswith(b'<sitemapindex') or s.startswith(b'<rdf') else 'html' if b'<html' in b[:2000].lower() else 'other'
    rec = {'url': url, 'note': note, 'seconds': round(time.time() - t, 2), 'bytes': len(b or b''), 'kind': kind}
    if kind == 'json':
        try:
            d = json.loads(b)
            if isinstance(d, dict):
                rec['keys'] = list(d)[:20]
                if 'items' in d:
                    rec['items'] = len(d['items'])
                    rec['total'] = d.get('total')
                    rec['first_versions'] = [i.get('versions') for i in d['items'][:10]]
            elif isinstance(d, list):
                rec['list_len'] = len(d)
        except ValueError:
            rec['kind'] = 'bad-json'
    out['probes'].append(rec)
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return b


for u in ['https://qbz.gov.al/sitemap.xml', 'https://qbz.gov.al/robots.txt', f'{API}/openapi.json', f'{API}/api-docs',
          'https://qbz.gov.al/v3/api-docs', 'https://qbz.gov.al/api/openapi.json', 'https://qbz.gov.al/api/v1/docs']:
    probe(u, 'discovery')

for size in (1000, 5000):
    probe(f'{API}/acts?type=Ligj&size={size}&page=0', f'page size {size}')
probe(f'{API}/acts?type=Ligj&size=100&page=0&sort=versions,desc', 'sort by versions')
probe(f'{API}/acts?type=Ligj&size=100&page=0&hasVersions=true', 'filter hasVersions')
probe(f'{API}/acts?type=Ligj&size=100&page=0&minVersions=1', 'filter minVersions')
probe(f'{API}/acts/7534', 'one act record')
probe(f'{API}/acts/7534?expand=versions,relations', 'expand')
probe(f'{API}/acts/7534?include=versions,relations', 'include')
probe(f'{API}/versions?size=1000&page=0', 'all versions endpoint')
probe(f'{API}/relations?size=1000&page=0', 'all relations endpoint')
probe('https://qbz.gov.al/eli/ligj/2026/10/09/105', 'ELI path')
probe(f'{API}/acts?size=1000&page=0', 'all types, 1000')

Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
