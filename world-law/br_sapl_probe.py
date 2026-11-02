"""Private. Probe a Câmara's SAPL for its Lei Orgânica (gitlaw-scraper-dell, municipal tier, 2026-10-31).

    python -X utf8 scripts/world-law/br_sapl_probe.py <host> <cache_dir> [--vigencias]

One request at a time, >= 61 s apart (Interlegis SAPL robots: Crawl-delay: 60). Fetches the norma types, the Lei
Orgânica records, each record's norma page, and with --vigencias every /ta/<id>/text/vigencia/ view the pages link.
Writes <cache_dir>/probe.json.
"""
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Host  # noqa: E402

host, cache = sys.argv[1], Path(sys.argv[2])
H = Host(cache, host, delay=61)
H.last = time.time()
base = f'https://{host}'
out = {'host': host}
tipos = json.loads(H.get(f'{base}/api/norma/tiponormajuridica/?page_size=100'))['results']
out['tipos'] = [(t['id'], t.get('sigla'), t.get('descricao')) for t in tipos]
lom = [t['id'] for t in tipos if (t.get('sigla') or '').upper() == 'LOM' or 'orgânica' in (t.get('descricao') or '').lower()
       and 'emenda' not in (t.get('descricao') or '').lower()]
print(out['tipos'], lom, flush=True)
out['lom'] = []
for t in lom:
    d = json.loads(H.get(f'{base}/api/norma/normajuridica/?tipo={t}&page_size=100'))
    for r in d['results']:
        page = H.get(base + r['link_detail_backend']).decode('utf-8', 'replace')
        tas = sorted(set(re.findall(r'href="(/ta/\d+/text/vigencia/[^"]+)"', page)))
        out['lom'].append({'id': r['id'], 'str': r['__str__'], 'data': r['data'], 'texto_integral': r['texto_integral'],
                           'url': r['link_detail_backend'], 'vigencias': tas,
                           'ta': sorted(set(re.findall(r'href="(/ta/\d+/text)"', page)))})
        print(out['lom'][-1]['str'], r['texto_integral'], len(tas), flush=True)
        (cache / 'probe.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        if '--vigencias' in sys.argv:
            for l in tas:
                H.get(base + l)
                print(l, flush=True)
(cache / 'probe.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print('done', flush=True)
