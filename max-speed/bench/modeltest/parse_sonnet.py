import json, re, sys, os, hashlib
import xml.etree.ElementTree as ET
D = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(D, '..', 'boe_const.xml')
URL = 'https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1978-31229/texto'
raw = open(SRC, 'rb').read()
root = ET.fromstring(raw)

def norm(s):
    s = ''.join(s.itertext()) if not isinstance(s, str) else s
    s = s.replace('\xa0', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s.replace('“', '"').replace('”', '"').replace('«', '"').replace('»', '"').replace('‘', "'").replace('’', "'")

def iso(d): return f'{d[:4]}-{d[4:6]}-{d[6:]}'
def key(i):
    k = re.sub(r'[^a-z0-9]+', '-', i.lower()).strip('-')
    return re.sub(r'\d+', lambda m: m.group().zfill(3), k)

blocks = []
dates = set()
for b in root.iter('bloque'):
    vs = []
    for v in b.findall('version'):
        d = iso(v.get('fecha_vigencia'))
        lines = [norm(p) for p in v.findall('p') if not p.get('class', '').startswith('nota_pie')]
        lines = [l for l in lines if l]
        vs.append((d, lines))
        dates.add(d)
    vs.sort(key=lambda x: x[0])
    blocks.append((b.get('id'), b.get('tipo'), b.get('titulo') or b.get('id'), vs))
dates = sorted(dates)

def units_at(date):
    out = {}
    for bid, tipo, tit, vs in blocks:
        cur = None
        for d, lines in vs:
            if d <= date: cur = lines
        if cur is None or not cur: continue
        kind = {'precepto': 'art', 'encabezado': 'heading', 'preambulo': 'preamble'}.get(tipo, 'other')
        out[key(bid)] = {'label': norm(tit) if tit else bid, 'kind': kind, 'text': '\n'.join(cur) + '\n'}
    return out

laws, versions, prev = {}, [], None
sha = hashlib.sha256(raw).hexdigest()
for d in dates:
    u = units_at(d)
    v = {'from': d, 'source_url': URL, 'sha256': sha}
    if prev is None:
        v['units'] = u
        v['credits'] = {}
    else:
        lk = 'reforma-' + d
        laws[lk] = {'label': 'Reforma constitucional ' + d, 'title': 'Reforma constitucional con efectos desde ' + d,
                    'kind': 'law', 'enacted': d, 'published': d, 'url': URL, 'temporary_until': None, 'restores': None, 'note': None}
        ch = {k: x for k, x in u.items() if prev.get(k) != x}
        for k in prev:
            if k not in u: ch[k] = None
        v['changes'] = ch
        v['credits'] = {k: [lk] for k in ch}
    versions.append(v)
    prev = u

corpus = {
 'country': {'code': 'ES', 'name': 'Spain', 'slug': 'spain', 'lang': 'es', 'tz': 'Europe/Madrid', 'future_branch': 'futuro',
   'publisher': {'name': 'Agencia Estatal Boletín Oficial del Estado', 'email': 'boe@boe.invalid'},
   'default_in_force_rule': {'text': 'Each version starts on the fecha_vigencia the BOE consolidated text records for it.', 'source': URL},
   'licence_note': 'Source: Agencia Estatal Boletín Oficial del Estado, datos abiertos (reutilización con mención de la fuente).'},
 'sources': [{'name': 'BOE legislación consolidada API', 'url': URL, 'retrieved': '2026-10-29', 'requests': 1,
   'licence': 'BOE open data reuse', 'notes': 'Consolidated text BOE-A-1978-31229.'}],
 'laws': laws,
 'acts': [{'slug': 'constitucion', 'short': 'CE', 'title': 'Constitución Española', 'url': URL,
   'first_law': None, 'earlier_laws': [], 'versions': versions}],
 'applies': [],
 'decisions': ['Each distinct fecha_vigencia is one version; each bloque takes its latest version dated on or before it.',
   'Footnote paragraphs (nota_pie) are dropped; the first-version bloque ids become unit keys with numbers zero-padded.',
   'Versions after the first are credited to a law key named reforma-<date>, because the source does not name the amending laws.'],
 'ai_use': ['none'],
}
with open(os.path.join(D, 'corpus.json'), 'w', encoding='utf-8', newline='\n') as f:
    json.dump(corpus, f, ensure_ascii=False, indent=1)
print(len(versions), len(units_at(dates[-1])))
