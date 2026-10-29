"""Benchmark 3: how far each approach reaches across countries.

(a) Official sources in register.json that offer an API / point-in-time versions / amendment data, split by whether
    the country already has law on a lexifina main branch (from scripts/*-law/BUILD_STATUS.json).
(b) Common Crawl coverage: captures of each official law host in the 3 newest crawls, via the byte-range index
    (works while index.commoncrawl.org is down), for every country NOT yet on main. Time per lookup.
(c) Shared platforms: hosts and formats that several countries publish through (one parser could cover them).
Writes bench_coverage.json.
"""
import collections, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent; SCRIPTS = HERE.parents[1]
sys.path.insert(0, str(SCRIPTS / 'gitlaw_common'))
import wayback as w
sys.stdout.reconfigure(encoding='utf-8')
reg = json.loads((HERE.parent / 'register.json').read_text(encoding='utf-8'))
countries = json.loads((HERE.parent / 'countries.json').read_text(encoding='utf-8'))
def slugify(n): return re.sub(r'[^a-z0-9]+', '-', n.lower().replace("'", '')).strip('-')
on_main = set()
for f in SCRIPTS.glob('*-law/BUILD_STATUS.json'):
    try:
        m = str(json.loads(f.read_text(encoding='utf-8')).get('main', ''))
        if re.search(r'\bpushed\b', m) and 'preview' not in m.split('(')[0]: on_main.add(f.parent.name[:-4])
    except Exception: pass
off = [s for s in reg['sources'] if s.get('k') == 'official']
out = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'official_sources': len(off), 'countries_on_main': len(on_main)}
flags = collections.Counter()
for s in off:
    done = slugify(s.get('c', '')) in on_main
    for k in ('api', 'pit', 'amend'):
        if s.get(k) == 'y': flags[(k, 'on_main' if done else 'not_on_main')] += 1
out['register_flags'] = {f'{k}|{d}': n for (k, d), n in flags.items()}
todo = [s for s in off if slugify(s.get('c', '')) not in on_main and s.get('u', '').startswith('http')]
hosts = {}
for s in todo:
    h = s['u'].split('://', 1)[1].split('/', 1)[0].lower().removeprefix('www.')
    hosts.setdefault(h, s.get('c'))
crawls = w.cc_crawls(None)[:3]
def look(item):
    h, c = item; t = time.time()
    try: n = len(w.cc_captures(h + '/', match='prefix', crawls=crawls) or [])
    except Exception as e: n = -1
    return {'country': c, 'host': h, 'captures_3_crawls': n, 'seconds': round(time.time() - t, 1)}
t = time.time()
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(look, sorted(hosts.items())))
out['cc_lookup_total_s'] = round(time.time() - t, 1)
out['cc_coverage'] = rows
n = [r['captures_3_crawls'] for r in rows if r['captures_3_crawls'] >= 0]
out['cc_summary'] = {'hosts': len(rows), 'with_any': sum(1 for x in n if x > 0), 'with_100_plus': sum(1 for x in n if x >= 100),
                     'with_1000_plus': sum(1 for x in n if x >= 1000), 'errors': sum(1 for r in rows if r['captures_3_crawls'] < 0),
                     'median_lookup_s': sorted(r['seconds'] for r in rows)[len(rows) // 2] if rows else None}
plat = collections.Counter()
for s in reg['sources']:
    txt = (s.get('u', '') + ' ' + s.get('n', '') + ' ' + s.get('f', '') + ' ' + s.get('note', '')).lower()
    for p in ('akoma ntoso', 'laws.africa', 'peachjam', 'lii', 'paclii', 'eli', 'sparql', 'clml', 'xml', 'json', 'api'):
        if p in txt: plat[p] += 1
out['platform_mentions'] = dict(plat.most_common())
(HERE / 'bench_coverage.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in out.items() if k != 'cc_coverage'}, indent=1, ensure_ascii=False))
