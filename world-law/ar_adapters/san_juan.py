"""Provincia de San Juan (gitlaw-scraper-dell, 2026-10-30): the Digesto Jurídico Provincial of the Cámara de Diputados
de San Juan (digestosanjuan.gob.ar; robots.txt answers with the app page, i.e. no rules; footer "Copyright © Cámara de
Diputados de San Juan", no reuse terms).

- Constitution: /fundamentales/constitucion_provincial.pdf (text layer): the Constitución de 1986 (sanctioned 23 April
  1986; art. 281: "regirá a partir del 1 de Mayo de 1.986"), with art. 175 as amended by Ley 8199 (enmienda under
  art. 277, approved by the consulta popular of 8 May 2011 and incorporated by the Tribunal Electoral on 12 May 2011).
- Laws: the digest's search API (/buscador/legislativo/sancionadas/<base64 JSON>, Elasticsearch hits) gives each
  law's number (digest numbering, e.g. 2840-O), sanción and publication dates and its text as sanctioned
  (texto_original, a .docx on minio.legsanjuan.gob.ar). Only laws with a publication date and a .docx text are built.
"""
from __future__ import annotations

import base64
import html as htmlmod
import io
import json
import re
import sys
import zipfile

import ar_provinces as E
from ar_provinces import clean, decode, get, letters, source_letters_pdf
from ar_adapters._ar_pdf import pdf_paragraphs_ordered

BASE = 'https://digestosanjuan.gob.ar'
CONST = BASE + '/fundamentales/constitucion_provincial.pdf'

_VIGENCIA = [
    ('1986-04-23', 'regirá a partir del 1 de Mayo de 1.986', '1986-05-01',
     'its own clause (art. 281): "Esta Constitución reemplaza a la sancionada en el año 1.927, y regirá a partir del '
     '1 de Mayo de 1.986"'),
]


def _patch_in_force():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'in_force', None)
        if orig is None or getattr(orig, '_sj_vigencia', False):
            continue

        def wrapped(paras, pub, promul, _o=orig):
            for opub, phrase, day, basis in _VIGENCIA:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._sj_vigencia = True
        mod.in_force = wrapped


_patch_in_force()

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def docx_paragraphs(b: bytes) -> list[str]:
    """lxml over word/document.xml: every <w:p> of the body in document order (table cells and text boxes included),
    its text the <w:t> runs whose nearest paragraph is that one (smart tags, hyperlinks and fields included), tabs
    and breaks as spaces. One paragraph per line."""
    from lxml import etree
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        root = etree.fromstring(z.read('word/document.xml'))
    out = []
    for para in root.iter(W + 'p'):
        parts = []
        for el in para.iter(W + 't', W + 'tab', W + 'br'):
            anc = el.getparent()
            while anc is not None and anc.tag != W + 'p':
                anc = anc.getparent()
            if anc is not para:
                continue
            parts.append(el.text or '' if el.tag == W + 't' else ' ')
        out.append(''.join(parts))
    return [c for c in (clean(x) for x in out) if c]


def source_letters_docx(b: bytes) -> str:
    """Independent reader: every <w:t> run text of word/document.xml, read with a regex over the raw XML."""
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        x = z.read('word/document.xml').decode('utf-8')
    return letters(''.join(htmlmod.unescape(m) for m in re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', x)))


def _source_letters(b: bytes) -> str:
    return source_letters_pdf(b) if b[:4] == b'%PDF' else source_letters_docx(b)


def _iso(s):
    return s[:10] if s and re.match(r'\d{4}-\d\d-\d\d', s) else None


class Adapter:
    host = 'digestosanjuan.gob.ar'
    source = {
        'name': 'Digesto Jurídico Provincial de San Juan (digestosanjuan.gob.ar), Cámara de Diputados de la Provincia de '
                'San Juan',
        'url': 'https://digestosanjuan.gob.ar/',
        'publisher': 'Digesto Jurídico de San Juan (digestosanjuan.gob.ar)',
        'gazette': 'Boletín Oficial de la Provincia de San Juan',
        'notes': 'For each law: its record (digest number, sanción and publication dates, state) and its text as '
                 'sanctioned (texto original, Word document). The constitution is the Cámara de Diputados PDF of the '
                 'Constitución de 1986 with the enmienda of art. 175 (Ley 8199) worked in.',
        'dates_note': 'The constitution is the 1986 text with art. 175 as amended by Ley 8199 (approved in the consulta '
                      'popular of 8 May 2011, incorporated by the Tribunal Electoral on 12 May 2011), shown as its '
                      'current text only, dated 12 May 2011. Laws are their texts as sanctioned (texto original), each '
                      'dated the day it took effect; later amendments are not shown.',
    }
    decisions = [
        'Constitution: the Cámara de Diputados PDF of the Constitución de la Provincia de San Juan (sanctioned 23 April '
        '1986; art. 281: it "regirá a partir del 1 de Mayo de 1.986"), which prints art. 175 as amended by Ley 8199 '
        '("Artículo enmendado por Ley Nº 8199, conforme a lo establecido en el Art. 277"). The enmienda was approved by '
        'the consulta popular of 8 May 2011 and incorporated into the constitution by the Tribunal Electoral on 12 May '
        '2011 (press reports; the digest records Ley 8199 as sanctioned 17 March 2011). It is shown as its current text '
        'only, dated 12 May 2011; the 1986 wording of art. 175 is not shown.',
        'Laws: the digest\'s texto original of each law (the Word document of the text as sanctioned), shown as '
        'enacted, dated the day it took effect. Laws without a publication date in the digest, or whose text is only a '
        'scan or an old .doc file, are left out. A law whose Word document has text the two readers do not both see '
        'is left out.',
        'In-force day: the law\'s own vigencia clause when its last articles state one (from publication, the day after, '
        'or a named date); otherwise the ninth day after publication (Código Civil y Comercial, arts. 5 and 6).',
        'Units: the heading (encabezado: number, enacting formula and anything before Artículo 1) and one file per '
        'article, holding the article and everything printed after it up to the next article (section headings, '
        'signatures, annexes). Nothing is dropped. One paragraph per line, spacing normalised.',
        'Laws are added newest first (by sanción date), in parts of about 50; the constitution comes first.',
    ]
    source_letters = staticmethod(_source_letters)

    def search(self, desde) -> dict:
        q = {'texto': '', 'filtros': [], 'sort': [{'fecha': 'desc'}], 'desde': desde}
        b64 = base64.b64encode(json.dumps(q, separators=(',', ':')).encode()).decode()
        b = get(f'{BASE}/buscador/legislativo/sancionadas/{b64}')
        return json.loads(decode(b)) if b else {'hits': {'hits': []}}

    def catalogue(self, n_laws: int) -> dict:
        out = {'constitucion': [{'page': CONST, 'constitution': True}], 'codigo': []}
        laws, desde, seen = [], None, set()
        for _ in range(450):   # deepening pass: walk past the first 60 result pages (1,500 hits of ~10,450)
            hits = self.search(desde)['hits']['hits']
            if not hits:
                break
            for h in hits:
                s = h.get('_source') or {}
                t = s.get('texto_original') or ''
                tn = s.get('tipo_Norma') or {}
                tn = tn.get('acronimo') if isinstance(tn, dict) else str(tn)
                if 'LP' not in str(tn) or not t.lower().endswith('.docx') or not _iso(s.get('fecha_Publicacion')):
                    continue
                num = f"{s.get('numero', '')}-{str(s.get('asiento') or '').rsplit('-', 1)[-1]}"
                if not re.fullmatch(r'\d+-[A-Z]', num):
                    continue
                if num in seen:
                    continue
                seen.add(num)
                laws.append({'page': f'{BASE}/digesto/detalle_ley/{s["id"]}', 'number': num,
                             'title': (s.get('tema_General') or '').strip(), 'pub': _iso(s['fecha_Publicacion']),
                             'sancion': _iso(s.get('fecha_Sancion')), 'text_url': t})
            if len(laws) >= n_laws:
                break
            desde = hits[-1].get('sort')
        out['ley'] = laws[:n_laws]
        return out

    def detail(self, item: dict) -> dict | None:
        if item.get('constitution'):
            return {'page': CONST, 'kind': 'constitucion', 'number': '', 'year': '1986',
                    'title': 'Constitución de la Provincia de San Juan', 'pub': '1986-04-23', 'promul': None,
                    'updated': '2011-05-12', 'related_later': ['Ley 8199 (enmienda art. 175)'], 'text_url': CONST,
                    'as_enacted': False}
        return {'page': item['page'], 'kind': 'ley', 'number': item['number'], 'title': item['title'],
                'pub': item['pub'], 'promul': None, 'updated': None, 'related_later': [], 'text_url': item['text_url'],
                'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b:
            return None
        if b[:4] == b'%PDF':
            paras = pdf_paragraphs_ordered(b)
        elif b[:2] == b'PK':
            try:
                paras = docx_paragraphs(b)
            except Exception as e:
                E.say(f'san-juan: unreadable {d["text_url"]}: {e}')
                return None
        else:
            return None
        if not paras or letters(''.join(paras)) != _source_letters(b):
            E.say(f'san-juan: left out {d["text_url"]} (the two readers disagree)')
            return None
        return paras, b
