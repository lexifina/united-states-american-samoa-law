"""Speed experiment B1 (2026-10-29): can InfoLEG's open-data bulk files replace page-by-page InfoLEG fetches?

Measures:
  1. the three bulk files on datos.jus.gob.ar (robots: Crawl-Delay 10, /api/ disallowed, so no CKAN API; the dataset
     page lists the download links): requests, seconds, rows;
  2. dates: does the bulk table hold fecha_sancion / fecha_boletin for every norm whose verNorma.do record page the
     argentina-law agent fetched (792 of its 1,622 requests)?
  3. amendment links: does the modificatorias table give the same modifier ids as each verVinculos.do?modo=2 page?
  4. texts: the bulk table carries only text URLs, so texts stay page fetches; measure host_get on norma.htm
     (InfoLEG has no robots.txt and no stated Crawl-delay) against argentina-law's fixed 1 request a second.

Reads the argentina-law cache read-only for the comparison. Writes speedb_argentina.json next to this file.
    python -X utf8 speedb_argentina.py <cache_dir>
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(sys.argv[1])
AR = Path(r'C:/Users/alany/Documents/lexifina/scripts/argentina-law/.cache')
DS = 'https://datos.jus.gob.ar/dataset/d9a963ea-8b1d-4ca3-9dd9-07a4773e8c23/resource/'
FILES = {
    'normas': DS + 'bf0ec116-ad4e-4572-a476-e57167a84403/download/base-infoleg-normativa-nacional.zip',
    'modificatorias': DS + 'dea3c247-5a5d-408f-a224-39ae0f8eb371/download/base-complementaria-infoleg-normas-modificatorias.zip',
    'modificadas': DS + '0c4fdafe-f4e8-4ac2-bc2e-acf50c27066d/download/base-complementaria-infoleg-normas-modificadas.zip',
}
BASE = 'https://servicios.infoleg.gob.ar/infolegInternet'
out: dict = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def rows(blob: bytes) -> list[dict]:
    z = zipfile.ZipFile(io.BytesIO(blob))
    with z.open(z.namelist()[0]) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding='utf-8', errors='replace')))


# 1. bulk download, one request at a time, 10 s apart (stated Crawl-Delay)
bulk, t_all = {}, time.time()
for i, (k, u) in enumerate(FILES.items()):
    if i:
        time.sleep(10)
    t = time.time()
    b = wayback.fetch_direct(u, CACHE)
    bulk[k] = rows(b)
    out[f'bulk_{k}'] = {'bytes': len(b), 'seconds': round(time.time() - t, 1), 'rows': len(bulk[k]),
                        'columns': list(bulk[k][0].keys())}
out['bulk_total'] = {'requests': 3, 'seconds_including_crawl_delay': round(time.time() - t_all, 1)}
N = {int(r['id_norma']): r for r in bulk['normas']}
mods: dict[int, set[int]] = {}
for r in bulk['modificatorias']:
    mods.setdefault(int(r['id_norma_modificada']), set()).add(int(r['id_norma_modificatoria']))
modificadas_by: dict[int, set[int]] = {}
for r in bulk['modificadas']:
    modificadas_by.setdefault(int(r[list(r)[0]]), set()).add(int(r[list(r)[1]]))
out['normas_with_dates'] = {
    'fecha_boletin': sum(1 for r in N.values() if r['fecha_boletin']),
    'fecha_sancion': sum(1 for r in N.values() if r['fecha_sancion']),
    'texto_original_url': sum(1 for r in N.values() if r['texto_original']),
    'texto_actualizado_url': sum(1 for r in N.values() if r['texto_actualizado']),
    'max_fecha_boletin': max(r['fecha_boletin'] for r in N.values() if r['fecha_boletin']),
}

# 2 + 3. compare with what argentina-law fetched page by page
log = [json.loads(l) for l in (AR / 'requests.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
ficha_ids = [int(m.group(1)) for r in log if (m := re.search(r'verNorma\.do\?id=(\d+)', r['url']))]
out['ficha_pages_fetched'] = len(ficha_ids)
out['ficha_ids_in_bulk_with_fecha_boletin'] = sum(1 for i in ficha_ids if i in N and N[i]['fecha_boletin'])
out['ficha_ids_missing_from_bulk'] = [i for i in ficha_ids if i not in N][:20]

vin = []
for r in log:
    m = re.search(r'verVinculos\.do\?modo=2&id=(\d+)', r['url'])
    if not m:
        continue
    nid = int(m.group(1))
    p = AR / hashlib.sha256(r['url'].encode()).hexdigest()
    if not p.exists():
        continue
    s = p.read_bytes().decode('latin-1')
    page = {int(x) for x in re.findall(r'verNorma\.do[^"]*?[?&]id=(\d+)"', s)} - {nid}
    tab = mods.get(nid, set())
    vin.append({'id': nid, 'page': len(page), 'bulk': len(tab), 'both': len(page & tab),
                'only_page': sorted(page - tab)[:10], 'only_bulk': sorted(tab - page)[:10]})
out['vinculos_vs_modificatorias'] = vin
out['vinculos_summary'] = {'pages': len(vin), 'page_links': sum(v['page'] for v in vin),
                           'bulk_links': sum(v['bulk'] for v in vin), 'in_both': sum(v['both'] for v in vin)}

# 4. texts: host_get on norma.htm for 60 amending norms of the Código Penal not cached by argentina-law
cp = sorted(mods.get(16546, set()))
urls = [N[i]['texto_original'].replace('http://', 'https://') for i in cp if i in N and N[i]['texto_original']][:60]
t = time.time()
with ThreadPoolExecutor(12) as ex:
    got = list(ex.map(lambda u: wayback.host_get(u, CACHE), urls))
dt = time.time() - t
out['texts_host_get'] = {'requests': len(urls), 'ok': sum(1 for g in got if g), 'seconds': round(dt, 1),
                         'per_second': round(len(urls) / dt, 2), 'threads': 12,
                         'host_state': wayback.host_status('servicios.infoleg.gob.ar')}
out['texts_fixed_1rps_seconds_same_count'] = len(urls) * 1.05

Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
print(json.dumps({k: v for k, v in out.items() if k != 'vinculos_vs_modificatorias'}, indent=1, ensure_ascii=False))
