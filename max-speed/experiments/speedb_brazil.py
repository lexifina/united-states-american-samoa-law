"""Speed experiment B2 (2026-10-29): Arquivo.pt and LexML as sources of dated Brazilian federal texts.

Planalto refuses requests from this machine, so brazil-law reads it through archive.org `id_` captures (one shared
~2/s rate for the whole machine). Measures:
  1. Arquivo.pt prefix listings (pt_captures) of Planalto's ccivil_03 tree and of the Chamber's legin original texts
     (archive copies only: www.camara.leg.br's robots.txt has an AI-bot block group): seconds, captures, distinct URLs,
     year span;
  2. dated versions: distinct digests per year of the Constitution's compiled page, and a raw fetch of one capture per
     year plus a sample of law pages (bot/error pages counted);
  3. the same exact-URL listing through archive.org's CDX, for comparison.
LexML was probed by hand (see SPEED-B.md): its SRU API sits under /busca/ (Disallowed) and /urn pages carry
metadata and links only, at a 5 s Crawl-delay.
    python -X utf8 speedb_brazil.py <cache_dir>
"""
from __future__ import annotations

import collections
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(sys.argv[1])
out: dict = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'listings': {}}
CF = 'www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm'
PREFIXES = [
    'www.planalto.gov.br/ccivil_03/leis/',
    'planalto.gov.br/ccivil_03/leis/',
    'www.planalto.gov.br/ccivil_03/constituicao/',
    'www.planalto.gov.br/ccivil_03/emendas/',
    'www.planalto.gov.br/ccivil_03/decreto-lei/',
    'www.planalto.gov.br/ccivil_03/_ato2019-2022/',
    'www.planalto.gov.br/ccivil_03/_ato2023-2026/',
    'www2.camara.leg.br/legin/fed/',
    'www2.camara.gov.br/legin/fed/',
]


def bad(body: bytes | None) -> bool:
    if not body or len(body) < 6000:
        return True
    head = body[:20000].lower()
    return b'acesso negado' in head or b'enable javascript' in head or b'request rejected' in head


recs_by = {}
for p in PREFIXES:
    t = time.time()
    recs = wayback.pt_captures(p, match='prefix', cache=CACHE)
    dt = time.time() - t
    years = collections.Counter(r['timestamp'][:4] for r in recs)
    recs_by[p] = recs
    out['listings'][p] = {'seconds': round(dt, 2), 'captures': len(recs), 'distinct_urls': len({r['url'] for r in recs}),
                          'first': min(years) if years else None, 'last': max(years) if years else None,
                          'per_year': dict(sorted(years.items())), 'capped_at_100k': len(recs) >= 100000}
    print(p, out['listings'][p]['captures'], round(dt, 1), 's', flush=True)

# 2. the Constitution's compiled page: one capture per distinct digest, grouped by year
t = time.time()
cf = wayback.pt_captures(CF, cache=CACHE)
cf_sec = time.time() - t
digests = {}
for r in sorted(cf, key=lambda r: r['timestamp']):
    digests.setdefault(r['digest'], r)
per_year = {}
for r in digests.values():
    per_year.setdefault(r['timestamp'][:4], r)
out['cf_compilado'] = {'seconds': round(cf_sec, 2), 'captures': len(cf), 'distinct_digests': len(digests),
                       'years_with_a_capture': sorted(per_year)}

sample = list(per_year.values())
leis = [r for r in recs_by['www.planalto.gov.br/ccivil_03/leis/'] if r['url'].lower().endswith('.htm')]
random.seed(7)
sample += random.sample(leis, min(40, len(leis)))
t = time.time()
with ThreadPoolExecutor(12) as ex:
    bodies = list(ex.map(lambda r: wayback.pt_get(r, cache=CACHE), sample))
dt = time.time() - t
out['raw_fetch'] = {'requests': len(sample), 'seconds': round(dt, 1), 'per_second': round(len(sample) / dt, 2),
                    'ok_real_pages': sum(1 for b in bodies if not bad(b)), 'bot_or_error_or_empty': sum(1 for b in bodies if bad(b)),
                    'megabytes': round(sum(len(b or b'') for b in bodies) / 1e6, 2), 'threads': 12,
                    'host_state': wayback.host_status('arquivo.pt')}
out['cf_per_year_fetch'] = [{'ts': r['timestamp'], 'bytes': len(b or b''), 'real': not bad(b)}
                            for r, b in zip(sample[:len(per_year)], bodies)]

# 3. archive.org CDX for the same exact URL (shared machine-wide rate)
t = time.time()
ia = wayback.captures(CF, cache=CACHE)
out['archive_org_cf'] = {'seconds': round(time.time() - t, 1), 'captures_collapsed_by_digest': len(ia),
                         'years': sorted({r['timestamp'][:4] for r in ia}) if ia and isinstance(ia[0], dict) else None}

Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
print(json.dumps({k: v for k, v in out.items() if k != 'listings'}, indent=1, ensure_ascii=False))

# 4. (added after the first run) filter by the CDX `length` field: bot/JS-challenge copies are 1.9-3.1 KB compressed,
# real pages 2.9 KB and up (40-capture sample: one overlap each way). Keep captures with length >= 3200.
real = {}
for p, recs in recs_by.items():
    ok = [r for r in recs if int(r.get('length') or 0) >= 3200]
    urls = collections.defaultdict(set)
    for r in ok:
        urls[r['urlkey']].add(r['digest'])
    real[p] = {'captures': len(recs), 'real_by_length': len(ok), 'urls_with_real': len(urls),
               'urls_2plus_versions': sum(1 for v in urls.values() if len(v) > 1),
               'real_per_year': dict(sorted(collections.Counter(r['timestamp'][:4] for r in ok).items()))}
out['length_filter'] = real
Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
