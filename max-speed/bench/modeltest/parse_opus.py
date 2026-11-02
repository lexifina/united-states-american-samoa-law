"""Parse the BOE consolidated Constitution XML into corpus.json for gitlaw_common."""
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / 'boe_const.xml'
URL = 'https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1978-31229/texto'
ELI = 'https://www.boe.es/buscar/act.php?id='
MONTHS = {m: i + 1 for i, m in enumerate(
    'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split())}


def iso(d: str) -> str:
    return f'{d[:4]}-{d[4:6]}-{d[6:8]}'


def clean(s: str) -> str:
    s = s.replace('\xa0', ' ').replace('−', '-')
    s = s.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    return re.sub(r'\s+', ' ', s).strip()


def slugify(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def unit_key(i: int, b) -> tuple[str, str, str]:
    bid, tipo, titulo = b.get('id'), b.get('tipo'), b.get('titulo') or ''
    m = re.fullmatch(r'Artículo (\d+)', titulo)
    if m:
        return f'{i:03d}-art-{int(m.group(1)):03d}', titulo, 'art'
    if tipo == 'preambulo':
        return f'{i:03d}-preambulo', 'Preámbulo', 'preamble'
    if tipo == 'firma':
        return f'{i:03d}-firma', 'Firma', 'signature'
    if tipo == 'encabezado':
        return f'{i:03d}-{slugify(titulo) or slugify(bid)}', titulo, 'heading'
    kind = 'transitional' if 'transitoria' in titulo.lower() else 'provision'
    return f'{i:03d}-{slugify(titulo) or slugify(bid)}', titulo or bid, kind


def version_text(v) -> str:
    lines = []
    for c in v:
        if c.tag != 'p':  # blockquote = BOE editorial notes, not legal text
            continue
        t = clean(''.join(c.itertext()))
        if t:
            lines.append(t)
    return '\n'.join(lines) + '\n'


def main() -> None:
    raw = SRC.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    root = ET.fromstring(raw)
    bloques = root.findall('.//bloque')
    blocks = []
    dates = set()
    law_meta = {}
    for i, b in enumerate(bloques):
        key, label, kind = unit_key(i, b)
        vs = []
        for v in b.findall('version'):
            d = iso(v.get('fecha_vigencia'))
            dates.add(d)
            vs.append((d, version_text(v)))
            if v.get('id_norma') != 'BOE-A-1978-31229':
                note = ' '.join(''.join(p.itertext()) for p in v.iter('p') if p.get('class') == 'nota_pie')
                law_meta.setdefault(d, {'id': v.get('id_norma'), 'published': iso(v.get('fecha_publicacion')),
                                        'note': clean(note)})
        vs.sort()
        blocks.append((key, label, kind, vs))
    dates = sorted(dates)

    laws = {}
    for d in dates[1:]:
        m = law_meta.get(d, {})
        enacted = None
        em = re.search(r'Reforma de (\d+) de (\w+) de (\d{4})', m.get('note', ''))
        if em and em.group(2) in MONTHS:
            enacted = f'{em.group(3)}-{MONTHS[em.group(2)]:02d}-{int(em.group(1)):02d}'
        laws[f'reforma-{d}'] = {
            'label': f'Reforma constitucional {d}',
            'title': f'Reforma de la Constitución Española ({m.get("id", "")})',
            'kind': 'law', 'enacted': enacted, 'published': m.get('published'),
            'url': ELI + m['id'] if m.get('id') else None,
            'temporary_until': None, 'restores': None, 'note': None,
        }

    versions = []
    prev = None
    for d in dates:
        units = {}
        for key, label, kind, vs in blocks:
            cur = [t for vd, t in vs if vd <= d]
            if cur:
                text = cur[-1]
                if text.startswith(label + '\n'):
                    text = '# ' + text
                units[key] = {'label': label, 'kind': kind, 'text': text}
        ver = {'from': d, 'source_url': URL, 'sha256': sha}
        if prev is None:
            ver['units'] = units
        else:
            changes = {k: u for k, u in units.items() if prev.get(k) != u}
            changes.update({k: None for k in prev if k not in units})
            ver['changes'] = changes
            ver['credits'] = {k: [f'reforma-{d}'] for k in sorted(changes)}
        versions.append(ver)
        prev = units

    corpus = {
        'country': {
            'code': 'ES', 'name': 'Spain', 'slug': 'spain', 'lang': 'es', 'tz': 'Europe/Madrid',
            'future_branch': 'futuro',
            'publisher': {'name': 'Agencia Estatal Boletín Oficial del Estado', 'email': 'boe@boe.invalid'},
            'default_in_force_rule': {
                'text': 'Código Civil art. 2.1: laws enter into force twenty days after their complete publication '
                        'in the BOE unless they provide otherwise; each in-force day here is the BOE consolidated '
                        'text\'s fecha_vigencia.',
                'source': 'https://www.boe.es/buscar/act.php?id=BOE-A-1889-4763'},
            'licence_note': 'Fuente: Agencia Estatal Boletín Oficial del Estado (https://www.boe.es).',
        },
        'sources': [{'name': 'BOE datos abiertos: legislación consolidada', 'url': URL, 'retrieved': '2026-10-29',
                     'requests': 1, 'licence': 'BOE open data reuse terms (attribution)',
                     'notes': 'Consolidated text of BOE-A-1978-31229 with every bloque version and its fecha_vigencia.'}],
        'laws': laws,
        'acts': [{
            'slug': 'constitucion', 'short': 'CE', 'title': 'Constitución Española',
            'url': ELI + 'BOE-A-1978-31229', 'first_law': None, 'earlier_laws': [],
            'versions': versions,
        }],
        'applies': [],
        'decisions': [
            'Each version takes effect on the BOE fecha_vigencia of its bloque versions; one version per distinct date.',
            'Unit keys are prefixed with the bloque position so files sort in document order.',
            'BOE editorial notes (blockquote nota_pie) are dropped from unit text.',
            'Each reform is keyed by its in-force date (reforma-YYYY-MM-DD) and credited to every bloque that changed that day.',
            'The 1978 text has first_law null and is credited to the publisher as the oldest version available.',
        ],
        'ai_use': ['none'],
    }
    out = HERE / 'corpus.json'
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(versions)} versions, {len(versions[0]["units"])} units, laws: {list(laws)}')


if __name__ == '__main__':
    main()
