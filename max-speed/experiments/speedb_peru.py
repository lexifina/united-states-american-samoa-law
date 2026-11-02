"""Speed experiment B3 (2026-10-29): El Peruano from archives, sitemap and open data instead of live day listings.

peru-law found its laws by paging busquedas.elperuano.pe's search one day at a time (2,088 of its 4,158 requests).
Measures, for each archive, how many El Peruano norm pages and PDFs it holds and how many of the 2026 laws and
legislative decrees (from peru-law's own day cards, read-only) it covers:
  - the site's own sitemap (busquedas.elperuano.pe/sitemap.xml, allowed by robots.txt);
  - Common Crawl (cluster.idx, newest crawls), Arquivo.pt (pt_captures), archive.org CDX (collapse=urlkey);
  - a raw fetch of a few archived norm pages: do they carry the PDF link and the text?
    python -X utf8 speedb_peru.py <cache_dir>
"""
from __future__ import annotations

import collections
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(sys.argv[1])
PE = Path(r'C:/Users/alany/Documents/lexifina/scripts/peru-law')
out: dict = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
OP = re.compile(r'(\d{6,8}-\d+)')
PREFIXES = ['busquedas.elperuano.pe/dispositivo/', 'busquedas.elperuano.pe/normaslegales/',
            'busquedas.elperuano.pe/api/archivo/file/', 'diariooficial.elperuano.pe/pdf/']

# the laws peru-law needed in 2026 (its day cards hold every norm published from 2026-01-01)
cards = [json.loads(l) for l in (PE / 'penal/.tmp/daycards_2026.jsonl').read_text(encoding='utf-8').splitlines() if l]
want = {c['op'] for c in cards if c['tipo'] in ('LEY', 'DECRETO LEGISLATIVO', 'DECRETO DE URGENCIA')}
allops = {c['op'] for c in cards}
out['cards_2026'] = {'norms': len(allops), 'laws_dlegs_dus': len(want),
                     'days': len({c['day'] for c in cards}), 'first': min(c['day'] for c in cards),
                     'last': max(c['day'] for c in cards)}


def cover(ops: set[str]) -> dict:
    return {'laws_dlegs_dus_covered': len(want & ops), 'all_2026_norms_covered': len(allops & ops)}


# 1. sitemap
t = time.time()
sm = wayback.sitemap_urls('https://busquedas.elperuano.pe/sitemap.xml', CACHE, with_lastmod=True)
urls = [u if isinstance(u, str) else u[0] for u in sm]
out['sitemap'] = {'seconds': round(time.time() - t, 1), 'urls': len(urls),
                  'lastmods': sorted({(u[1] or '')[:10] for u in sm if not isinstance(u, str)})[:5],
                  'kinds': dict(collections.Counter(re.sub(r'\d.*', '', u.split('elperuano.pe/')[-1]) for u in urls))}

# 2. Common Crawl, newest 8 crawls
crawls = wayback.cc_crawls(CACHE)[:8]
assert wayback.cc_ok(), 'Common Crawl blocking this machine; rerun later'
out['common_crawl'] = {'crawls': crawls}
cc_ops: set[str] = set()
cc_recs = {}
for p in PREFIXES:
    t = time.time()
    recs = wayback.cc_captures(p, crawls=crawls, match='prefix', cache=CACHE)
    ok = [r for r in recs if str(r.get('status')) == '200']
    ops = {m.group(1) for r in ok if (m := OP.search(r['url']))}
    cc_ops |= ops
    cc_recs[p] = ok
    out['common_crawl'][p] = {'seconds': round(time.time() - t, 1), 'captures': len(recs), 'ok': len(ok),
                              'distinct_urls': len({r['url'] for r in ok}), 'distinct_ops': len(ops),
                              'per_crawl': dict(collections.Counter(r['crawl'] for r in ok))}
    print('cc', p, out['common_crawl'][p]['ok'], flush=True)
out['common_crawl']['coverage'] = cover(cc_ops)

# 3. Arquivo.pt
pt_ops: set[str] = set()
out['arquivo_pt'] = {}
for p in PREFIXES:
    t = time.time()
    recs = wayback.pt_captures(p, match='prefix', cache=CACHE)
    ops = {m.group(1) for r in recs if (m := OP.search(r['url']))}
    pt_ops |= ops
    out['arquivo_pt'][p] = {'seconds': round(time.time() - t, 1), 'captures': len(recs),
                            'distinct_urls': len({r['url'] for r in recs}), 'distinct_ops': len(ops),
                            'years': dict(sorted(collections.Counter(r['timestamp'][:4] for r in recs).items()))}
    print('pt', p, len(recs), flush=True)
out['arquivo_pt']['coverage'] = cover(pt_ops)

# 4. archive.org: one CDX request per prefix, one row per distinct URL
ia_ops: set[str] = set()
out['archive_org'] = {}
for p in PREFIXES[:2]:
    t = time.time()
    recs = wayback.captures(p, match='prefix', cache=CACHE, collapse='urlkey')
    ops = {m.group(1) for r in recs if (m := OP.search(r['original']))}
    ia_ops |= ops
    out['archive_org'][p] = {'seconds': round(time.time() - t, 1), 'distinct_urls': len(recs), 'distinct_ops': len(ops),
                             'years': dict(sorted(collections.Counter(r['timestamp'][:4] for r in recs).items()))}
    print('ia', p, len(recs), flush=True)
out['archive_org']['coverage'] = cover(ia_ops)
out['union_coverage'] = cover(cc_ops | pt_ops | ia_ops)

# 5. what an archived norm page holds: 24 Common Crawl captures of /dispositivo/ pages (16 threads)
sample = cc_recs['busquedas.elperuano.pe/dispositivo/'][:24]
t = time.time()
with ThreadPoolExecutor(16) as ex:
    bodies = list(ex.map(lambda r: wayback.cc_get(r, CACHE), sample))
dt = time.time() - t
out['cc_page_fetch'] = {'requests': len(sample), 'seconds': round(dt, 1), 'ok': sum(1 for b in bodies if b),
                        'with_pdf_link': sum(1 for b in bodies if b and b'api/archivo/file' in b),
                        'median_bytes': sorted(len(b or b'') for b in bodies)[len(bodies) // 2] if bodies else 0}

Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])
