"""Speed experiment B4b: QBZ has no bulk route (page size capped at 100, no sitemap, no all-versions endpoint), so
measure the same 698-request crawl through host_get from a thread pool, and check the archives for API captures.
    python -X utf8 speedb_albania_parallel.py <cache_dir>
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(sys.argv[1])
API = 'https://qbz.gov.al/api/v1'
out: dict = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}

# archives: any captures of the JSON API?
crawls = wayback.cc_crawls(CACHE)[:4]
assert wayback.cc_ok()
t = time.time()
cc = wayback.cc_captures('qbz.gov.al/api/', crawls=crawls, match='prefix', cache=CACHE)
out['common_crawl_api'] = {'crawls': crawls, 'seconds': round(time.time() - t, 1), 'captures': len(cc)}
t = time.time()
pt = wayback.pt_captures('qbz.gov.al/api/', match='prefix', cache=CACHE)
out['arquivo_pt_api'] = {'seconds': round(time.time() - t, 1), 'captures': len(pt)}

# 1. the 40 listing pages, 8 threads
t = time.time()
with ThreadPoolExecutor(8) as ex:
    pages = list(ex.map(lambda n: wayback.host_get(f'{API}/acts?type=Ligj&size=100&page={n}', CACHE), range(40)))
items = [i for p in pages if p for i in json.loads(p)['items']]
out['listing'] = {'requests': 40, 'seconds': round(time.time() - t, 1), 'acts': len(items),
                  'with_versions': sum(1 for i in items if i.get('versions'))}

# 2. versions + relations for every act with versions, 12 threads
ids = [i['id'] for i in items if i.get('versions')]
urls = [f'{API}/acts/{i}/{k}' for i in ids for k in ('versions', 'relations')]
t = time.time()
with ThreadPoolExecutor(12) as ex:
    got = list(ex.map(lambda u: wayback.host_get(u, CACHE), urls))
dt = time.time() - t
out['versions_relations'] = {'requests': len(urls), 'ok': sum(1 for g in got if g), 'seconds': round(dt, 1),
                             'per_second': round(len(urls) / dt, 2), 'threads': 12,
                             'host_state': wayback.host_status('qbz.gov.al')}
out['total'] = {'requests': 40 + len(urls), 'seconds': round(out['listing']['seconds'] + dt, 1),
                'at_old_fixed_3_per_second': round((40 + len(urls)) / 3, 1)}
Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
print(json.dumps(out, indent=1, ensure_ascii=False))
