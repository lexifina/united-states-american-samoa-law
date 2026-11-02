"""Benchmark 1: fetch methods on the same set of official pages (e-seimas.lrs.lt legal acts; robots.txt: no crawl-delay).

    python -X utf8 scripts/world-law/bench/bench_fetch.py

Measures pages/s, success rate and MB/s for: Common Crawl byte-range (1, 8, 16 threads), live host_get (1, 4, 12
threads), archive.org via the shared limiter (1 and 8 threads), and the index lookups themselves. No cache, so
every request is real. Small samples, under each source's shared adaptive rate. Writes bench_fetch.json.
"""
import json, random, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'gitlaw_common'))
import wayback as w
sys.stdout.reconfigure(encoding='utf-8')
random.seed(7)
out = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'runs': []}

def run(name, fn, items, threads):
    t = time.time()
    with ThreadPoolExecutor(threads) as ex:
        res = list(ex.map(fn, items))
    dt = time.time() - t
    ok = [r for r in res if r]
    row = {'method': name, 'threads': threads, 'n': len(items), 'ok': len(ok), 'seconds': round(dt, 2),
           'pages_per_s': round(len(ok) / dt, 2), 'MB_per_s': round(sum(map(len, ok)) / dt / 1e6, 3),
           'avg_kB': round(sum(map(len, ok)) / max(1, len(ok)) / 1e3, 1)}
    out['runs'].append(row); print(json.dumps(row), flush=True)

# index lookups
t = time.time(); crawls = w.cc_crawls(None); out['cc_crawls_s'] = round(time.time() - t, 2)
t = time.time(); recs = w.cc_captures('e-seimas.lrs.lt/portal/legalAct/lt/TAD/', match='prefix', crawls=crawls[:3]) or []
out['cc_index'] = {'prefix': 'e-seimas.lrs.lt/portal/legalAct/lt/TAD/', 'crawls': 3, 'captures': len(recs),
                   'seconds': round(time.time() - t, 2)}
print(out['cc_index'], flush=True)
recs = [r for r in recs if str(r.get('status', '200')) == '200']
by_url = {}
for r in recs:
    by_url.setdefault(r['url'], r)
sample = random.sample(list(by_url.values()), min(150, len(by_url)))
urls = [r['url'] for r in sample]

for th, n in ((1, 20), (8, 60), (16, 60)):
    run('common-crawl cc_get', lambda r: w.cc_get(r, None), random.sample(sample, n), th)
for th, n in ((1, 15), (4, 30), (12, 40)):
    d = Path(tempfile.mkdtemp(prefix='bench-host-'))
    run('live host_get', lambda u: w.host_get(u, d), random.sample(urls, n), th)
t = time.time(); caps = w.captures('e-seimas.lrs.lt/portal/legalAct/lt/TAD/', match='prefix') or []
out['ia_cdx'] = {'captures': len(caps), 'seconds': round(time.time() - t, 2)}; print(out['ia_cdx'], flush=True)
ia_urls = [c['original'] if isinstance(c, dict) and 'original' in c else (c[2] if isinstance(c, (list, tuple)) else None) for c in caps]
ia_urls = [u for u in ia_urls if u][:200] or urls
for th, n in ((1, 10), (8, 20)):
    run('archive.org wayback.get', lambda u: w.get(u, ts='2026', cache=None), random.sample(ia_urls, min(n, len(ia_urls))), th)
out['archive_rate_state'] = w.status()
(HERE / 'bench_fetch.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
print('saved')
