"""Benchmark 4: how much dated history Common Crawl holds for single law pages, across many crawls."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'gitlaw_common'))
import wayback as w
sys.stdout.reconfigure(encoding='utf-8')
crawls = w.cc_crawls(None)
pages = {'Latvia Satversme (likumi.lv)': 'likumi.lv/ta/id/57980',
         'NZ Constitution Act (legislation.govt.nz)': 'legislation.govt.nz/act/public/1986/0114/latest/whole.html',
         'Spain Constitution (boe.es)': 'boe.es/buscar/act.php?id=BOE-A-1978-31229',
         'Estonia Constitution (riigiteataja.ee)': 'riigiteataja.ee/akt/633949',
         'Austria B-VG (ris.bka.gv.at)': 'ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer=10000138'}
out = {'crawls_available': len(crawls), 'rows': []}
for n_crawls in (24, len(crawls)):
    for label, u in pages.items():
        t = time.time()
        try: caps = w.cc_captures(u, match='exact', crawls=crawls[:n_crawls]) or []
        except Exception as e: caps = []
        ok = [c for c in caps if str(c.get('status', '200')) == '200']
        years = sorted({str(c.get('timestamp', ''))[:4] for c in ok})
        row = {'page': label, 'crawls_searched': n_crawls, 'captures_200': len(ok), 'years': f'{years[0]}–{years[-1]}' if years else '-',
               'distinct_years': len(years), 'seconds': round(time.time() - t, 1)}
        out['rows'].append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
(HERE / 'bench_cc_depth.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
