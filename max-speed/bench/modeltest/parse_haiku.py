"""Parse the BOE consolidated Constitution (BOE-A-1978-31229) into corpus.json.

Reads only the local XML cache file; no network. Deterministic.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'boe_const.xml'
OUT = HERE / 'corpus.json'
SOURCE_URL = 'https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1978-31229/texto'
NORM_URL = 'https://www.boe.es/buscar/act.php?id=BOE-A-1978-31229'


def iso(d: str) -> str:
    return f'{d[:4]}-{d[4:6]}-{d[6:8]}'


def norm(s: str) -> str:
    s = s.replace('\u00a0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def para_text(p) -> str | None:
    cls = p.get('class') or ''
    if cls.startswith('nota'):  # editorial amendment notes, not constitutional text
        return None
    t = norm(''.join(p.itertext()))
    return t or None


def version_text(v) -> str:
    lines = [t for t in (para_text(p) for p in v.findall('p')) if t]
    return '\n'.join(lines) + '\n'


root = ET.parse(SRC).getroot()
raw = SRC.read_bytes()

blocks = []  # (order, id, label, [(fecha_vigencia, text, id_norma, fecha_publicacion)])
for order, b in enumerate(root.iter('bloque'), start=1):
    bid = b.get('id')
    if b.get('tipo') == 'preambulo':
        label = 'Preámbulo'
    elif b.get('tipo') == 'firma':
        label = 'Firma'
    else:
        label = norm(b.get('titulo') or bid)
    versions = []
    for v in b.findall('version'):
        versions.append((v.get('fecha_vigencia'), version_text(v), v.get('id_norma'), v.get('fecha_publicacion')))
    blocks.append((order, bid, label, versions))

dates = sorted({fv for _, _, _, vs in blocks for fv, *_ in vs})
key_of = {bid: f'{order:03d}-{bid}' for order, bid, _, _ in blocks}
for k in key_of.values():
    assert re.fullmatch(r'[a-z0-9-]+', k), k


def text_on(versions, day):
    """Text of the latest version in force on day (fecha_vigencia <= day)."""
    best = None
    for fv, text, *_ in versions:
        if fv <= day and (best is None or fv > best[0]):
            best = (fv, text)
    return best[1] if best else None


# Law per reform date (every in-force date after the first one)
law_for_date = {}
laws = {}
for fv in dates[1:]:
    ids = sorted({idn for _, _, _, vs in blocks for f, _, idn, _ in vs if f == fv})
    pub = sorted({p for _, _, _, vs in blocks for f, _, _, p in vs if f == fv})
    key = f'reforma-{iso(fv)}'
    law_for_date[fv] = key
    laws[key] = {
        'label': f'Reforma constitucional {iso(fv)}',
        'title': 'Reforma constitucional',
        'kind': 'law',
        'enacted': None,
        'published': iso(pub[0]) if pub else None,
        'url': f'https://www.boe.es/buscar/act.php?id={ids[0]}' if ids else NORM_URL,
        'temporary_until': None,
        'restores': None,
        'note': None,
    }

versions_out = []
prev_units = None
for i, fv in enumerate(dates):
    units = {}
    for order, bid, label, vs in blocks:
        t = text_on(vs, fv)
        if t is None:
            continue
        units[key_of[bid]] = {
            'label': label,
            'kind': 'art' if bid.startswith('a') and bid[1:2].isdigit() else 'part',
            'text': t,
        }
    credits = {}
    if prev_units is not None:
        for k in sorted(set(units) | set(prev_units)):
            if units.get(k, {}).get('text') != prev_units.get(k, {}).get('text'):
                credits[k] = [law_for_date[fv]]
    v = {'from': iso(fv), 'source_url': SOURCE_URL,
         'sha256': hashlib.sha256(raw).hexdigest(), 'units': units}
    if i > 0:
        v['credits'] = credits
    versions_out.append(v)
    prev_units = units

corpus = {
    'country': {
        'code': 'ES', 'name': 'Spain', 'slug': 'spain', 'lang': 'es',
        'tz': 'Europe/Madrid', 'future_branch': 'futuro',
        'publisher': {'name': 'Agencia Estatal Boletín Oficial del Estado', 'email': 'boe@boe.invalid'},
        'default_in_force_rule': {
            'text': 'Each consolidated version carries its own fecha_vigencia in the BOE open data; that date is the in-force day.',
            'source': SOURCE_URL},
        'licence_note': 'Texto consolidado: Agencia Estatal Boletín Oficial del Estado (BOE), datos abiertos.',
    },
    'sources': [{
        'name': 'BOE open data API, consolidated legislation', 'url': SOURCE_URL,
        'retrieved': '2026-10-29', 'requests': 1,
        'licence': 'BOE open data; reuse under the BOE legal notice',
        'notes': 'One XML document with every bloque and its versions.',
    }],
    'laws': laws,
    'acts': [{
        'slug': 'constitucion', 'short': 'CE',
        'title': 'Constitución Española', 'url': NORM_URL,
        'first_law': None, 'earlier_laws': [],
        'versions': versions_out,
    }],
    'applies': [],
    'decisions': [
        'In-force dates are the fecha_vigencia values of the BOE versions, used as given.',
        'Each reform date after 1978 gets the law key reforma-<date>, credited to every unit whose text changed on that day.',
        'The 1978 text has first_law null, so it is credited to the publisher as the oldest version available.',
        'Enacted dates are left null because the XML gives only publication dates.',
        'Footnote paragraphs (class nota*, BOE amendment annotations) are dropped; they are not constitutional text.',
        'Unit keys are document order plus the BOE bloque id, so they sort naturally.',
    ],
    'ai_use': ['Parser code written with an AI model; no model output is used as text or as credits.'],
}

OUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('versions', len(versions_out), 'units', len(blocks), 'laws', len(laws))
