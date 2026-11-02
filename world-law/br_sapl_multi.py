"""Private. One process for several Câmaras' SAPL hosts (gitlaw-scraper-dell, municipal tier, 2026-10-31).

    python -X utf8 scripts/world-law/br_sapl_multi.py <host>=<city folder> ...

Round-robin over the hosts; each host gets one request at a time, >= 61 s apart (Interlegis SAPL robots:
Crawl-delay: 60). Per host: the norma types, the Lei Orgânica records, each record's norma page and every
/ta/<id>/text/vigencia/ view it links (or its texto_integral file). Cache: <folder>/.cache/sapl (br_city_get layout).
Writes <folder>/.cache/sapl/probe.json and prints progress lines.
"""
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Host, Stop  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1]


def work(host, folder):
    cache = SCRIPTS / folder / '.cache' / 'sapl'
    H = Host(cache, host, delay=61)
    H.last = time.time()
    base = f'https://{host}'
    out = {'host': host, 'lom': []}

    seen = [H.last]

    def get(url):
        b = H.get(url)
        return b

    def fresh():  # True when the last get went to the network (a cached answer needs no wait)
        f = H.last != seen[0]
        seen[0] = H.last
        return f

    def save():
        (cache / 'probe.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    yield H
    b = get(f'{base}/api/norma/tiponormajuridica/?page_size=100')
    if fresh():
        yield H
    tipos = json.loads(b)['results']
    out['tipos'] = [(t['id'], t.get('sigla'), t.get('descricao')) for t in tipos]
    lom = [t['id'] for t in tipos if (t.get('sigla') or '').upper() == 'LOM' or (
        'orgânica' in (t.get('descricao') or '').lower() and 'emenda' not in (t.get('descricao') or '').lower())]
    print(host, 'tipos', out['tipos'], 'lom', lom, flush=True)
    save()
    for t in lom:
        b = get(f'{base}/api/norma/normajuridica/?tipo={t}&page_size=100')
        if fresh():
            yield H
        for r in json.loads(b)['results']:
            if 'emenda' in (r.get('__str__') or '').lower():
                continue  # an amending act filed under the Lei Orgânica type
            page = get(base + (r.get('link_detail_backend') or f"/norma/{r['id']}")).decode('utf-8', 'replace')
            if fresh():
                yield H
            tas = sorted(set(re.findall(r'href="(/ta/\d+/text/vigencia/[^"]+)"', page)))
            rec = {'id': r['id'], 'str': r['__str__'], 'data': r['data'], 'data_publicacao': r.get('data_publicacao'),
                   'texto_integral': r['texto_integral'], 'url': r.get('link_detail_backend') or f"/norma/{r['id']}", 'vigencias': tas,
                   'ta': sorted(set(re.findall(r'href="(/ta/\d+/text)"', page)))}
            out['lom'].append(rec)
            save()
            print(host, rec['str'], 'texto_integral', bool(r['texto_integral']), 'vigencias', len(tas), flush=True)
            for l in tas:
                get(base + l)
                if fresh():
                    yield H
            if not tas and rec['ta']:
                get(base + rec['ta'][0])
                if fresh():
                    yield H
            if r['texto_integral']:
                get(r['texto_integral'] if r['texto_integral'].startswith('http') else base + r['texto_integral'])
                if fresh():
                    yield H
    print(host, 'done', flush=True)


def main():
    jobs = []
    for a in sys.argv[1:]:
        host, folder = a.split('=')
        g = work(host, folder)
        jobs.append([host, g, next(g)])
    while jobs:
        jobs.sort(key=lambda j: j[2].last + j[2].delay)
        j = jobs[0]
        wait = j[2].last + j[2].delay - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            next(j[1])
        except StopIteration:
            jobs.remove(j)
        except (Stop, Exception) as e:
            print(j[0], 'STOP', str(e)[:200], flush=True)
            jobs.remove(j)


if __name__ == '__main__':
    main()
