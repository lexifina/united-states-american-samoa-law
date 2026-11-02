"""Provincia del Chaco (gitlaw-scraper-dell, 2026-10-30): the Digesto Jurídico of the Poder Legislativo del Chaco
(digesto.legislaturachaco.gob.ar, Dirección de Información Parlamentaria; no robots.txt, no reuse terms on the site).

- Constitution: "Consultas Especiales" lists the Constitución de la Provincia del Chaco 1957-1994 as a PDF with a text
  layer (Editorial Parlamentaria), last amended by Ley 6436 (art. 75) and Ley 7232 (art. 90, inc. 2).
- Laws: the public search grid (JSON, GetDocumentosBusquedaPublica) gives each law's digest number (e.g. 4228-C, the
  numbering of the Digesto Jurídico, Ley 3092-A of 2018), title and the file name of its PDF; each law's record page
  (VistaPublicaLey) gives sanción, promulgación, publicación and the Boletín Oficial number.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import sys
from urllib.parse import quote

import ar_provinces as E
from ar_provinces import decode, dmy, get, letters, source_letters_pdf
from ar_adapters._ar_pdf import pdf_paragraphs_ordered, source_letters_pdf_raw

BASE = 'https://digesto.legislaturachaco.gob.ar'
CONST_FILE = 'CONSTITUCIÓN DE LA PROVINCIA DEL CHACO 1957-1994.pdf'

# (publication date given, phrase that must be in the text, in-force day, basis)
_VIGENCIA = [
    ('1994-10-27', 'regirá a partir del día de la fecha', '1994-10-27',
     'its own clause (cláusula transitoria primera): "La reforma de la Constitución Provincial, sancionada y '
     'promulgada por la Convención Constituyente, regirá a partir del día de la fecha", given 27 October 1994'),
]


def _patch_in_force():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'in_force', None)
        if orig is None or getattr(orig, '_chaco_vigencia', False):
            continue

        def wrapped(paras, pub, promul, _o=orig):
            for opub, phrase, day, basis in _VIGENCIA:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._chaco_vigencia = True
        mod.in_force = wrapped


_patch_in_force()


def _field(s: str, name: str) -> str | None:
    m = re.search(r'id="%s"[^>]*value="([^"]*)"' % name, s)
    return m.group(1) if m else None


class Adapter:
    host = 'digesto.legislaturachaco.gob.ar'
    source = {
        'name': 'Digesto Jurídico del Poder Legislativo de la Provincia del Chaco (digesto.legislaturachaco.gob.ar), '
                'Dirección de Información Parlamentaria, Cámara de Diputados del Chaco',
        'url': 'https://digesto.legislaturachaco.gob.ar/',
        'publisher': 'Digesto Jurídico del Chaco (digesto.legislaturachaco.gob.ar)',
        'gazette': 'Boletín Oficial de la Provincia del Chaco',
        'notes': 'For each law: its record (digest number, sanción, promulgation and publication dates, Boletín Oficial '
                 'number) and its text as a PDF with a text layer ("copia digital" of the Dirección de Información '
                 'Parlamentaria). The constitution is the Editorial Parlamentaria PDF of the Constitución de la '
                 'Provincia del Chaco 1957-1994 with its later enmiendas (Leyes 6436 and 7232) worked in.',
        'dates_note': 'The constitution is the 1994 text with the enmiendas of Ley 6436 (2009, art. 75) and Ley 7232 '
                      '(2013, art. 90 inc. 2) worked in, shown as its current text only, dated the day Ley 7232 took '
                      'effect (21 June 2013: published 12 June 2013, Boletín Oficial 9509, in force on the ninth day). '
                      'Codes are the digest\'s consolidated texts, current text only, dated by the day the digest '
                      'verified their record. '
                      'Laws are their PDF texts from the digest; a law whose record or text notes a later change is its '
                      'current text only, dated by the day the digest verified its record; every other law is as '
                      'enacted, dated the day it took effect.',
    }
    decisions = [
        'Constitution: the Editorial Parlamentaria PDF of the Constitución de la Provincia del Chaco 1957-1994 (sanctioned '
        '27 October 1994; transitional clause one: it "regirá a partir del día de la fecha"), with the enmiendas of Ley '
        '6436 (art. 75) and Ley 7232 (art. 90 inc. 2) worked in, as the PDF\'s own "Última modificación" note says. It '
        'is shown as its current text only, dated 21 June 2013, the ninth day after Ley 7232 was published (12 June '
        '2013, Boletín Oficial 9509). The 1994 wording before the enmiendas is not shown.',
        'Codes (the laws titled Código in the digest) are the digest\'s consolidated texts: each is shown as its current '
        'text only, dated by the day the digest verified its record (Fecha de Verificación); a code without that date '
        'is left out.',
        'Laws: the digest\'s PDF of each law (text layer; no OCR). A law with no later change noted in its record '
        '(Observación) or text is shown as enacted, dated the day it took effect; otherwise as its current text only, '
        'dated by the day the digest verified its record (Fecha de Verificación). Laws without a publication date in '
        'their record (not yet published) are left out until they are.',
        'In-force day: the law\'s own vigencia clause when its last articles state one (from publication, the day after, '
        'or a named date); otherwise the ninth day after publication (Código Civil y Comercial, arts. 5 and 6).',
        'Units: the heading (encabezado: number, enacting formula and anything before Artículo 1) and one file per '
        'article, holding the article and everything printed after it up to the next article (section headings, '
        'signatures, page headers and footers of the PDF, the source\'s notes). Nothing is dropped. One paragraph per '
        'line, spacing normalised.',
        'Laws are added newest first (by the digest\'s record order), in parts of about 50; the constitution comes first.',
    ]
    # The second reader is poppler in the reading the text was taken in: its default physical order for the text
    # read in that order (every law published before 2026-10-31), else its content-stream order (-raw) for the text
    # read in the PDF's drawing order (see text()). Either way the letters and digits must be equal in order.
    @staticmethod
    def source_letters(b: bytes) -> str:
        default = source_letters_pdf(b)
        paras = pdf_paragraphs_ordered(b)
        if paras and letters(''.join(paras)) == default:
            return default
        return source_letters_pdf_raw(b)

    def grid(self, page: int, **kw) -> dict:
        q = '&'.join(f'{k}={quote(str(v))}' for k, v in kw.items())
        b = get(f'{BASE}/Documentos/Documento/GetDocumentosBusquedaPublica?sort=Id-desc&page={page}&pageSize=100&{q}')
        return json.loads(decode(b)) if b else {'Data': [], 'Total': 0}

    def catalogue(self, n_laws: int) -> dict:
        out = {'constitucion': [{'page': f'{BASE}/Common/DocumentoEspecial/GetArchivo?nombreArchivo={quote(CONST_FILE)}',
                                 'constitution': True}]}
        laws, pg = [], 1
        while len(laws) < n_laws:
            g = self.grid(pg, DocumentoTipoId=1, VerNoVigentes='false')
            if not g['Data']:
                break
            for r in g['Data']:
                f = r.get('NombreDocumentoFisico') or ''
                if not f.lower().endswith('.pdf') or r.get('NoVigente'):
                    continue
                m = re.fullmatch(r'L\.(\d+)\.([A-Z])', r.get('Identificador') or '')
                if not m:
                    continue
                laws.append({'page': f'{BASE}/Documentos/Ley/VistaPublicaLey/{r["Id"]}', 'number': f'{m.group(1)}-{m.group(2)}',
                             'title': (r.get('Titulo') or '').strip(), 'file': f, 'obs': r.get('Observacion') or ''})
            pg += 1
        codes = []
        for r in self.grid(1, Titulo='CODIGO', DocumentoTipoId=1, VerNoVigentes='false')['Data']:
            t = (r.get('Titulo') or '').strip()
            m = re.fullmatch(r'L\.(\d+)\.([A-Z])', r.get('Identificador') or '')
            f = r.get('NombreDocumentoFisico') or ''
            if not m or not f.lower().endswith('.pdf') or r.get('NoVigente') or r.get('EstadoDigesto') == 'Fusionado'                     or not re.match(r'C[OÓ]DIGO', t.upper()) or 'MODIFICACIONES' in t.upper():
                continue
            codes.append({'page': f'{BASE}/Documentos/Ley/VistaPublicaLey/{r["Id"]}', 'number': f'{m.group(1)}-{m.group(2)}',
                          'title': t, 'file': f, 'obs': r.get('Observacion') or '', 'code': True})
        out['codigo'] = codes
        out['ley'] = laws[:n_laws]
        return out

    def detail(self, item: dict) -> dict | None:
        if item.get('constitution'):
            return {'page': item['page'], 'kind': 'constitucion', 'number': '', 'year': '1994',
                    'title': 'Constitución de la Provincia del Chaco 1957-1994', 'pub': '1994-10-27',
                    'promul': '1994-10-27', 'updated': '2013-06-21',
                    'related_later': ['Ley 6436 (enmienda art. 75)', 'Ley 7232 (enmienda art. 90 inc. 2)'],
                    'text_url': item['page']}
        b = get(item['page'])
        if not b:
            return None
        s = decode(b)
        pub = dmy(_field(s, 'Publicacion') or '')
        if not pub:
            return None
        obs = item.get('obs') or ''
        later = [re.sub(r'\s+', ' ', obs).strip()[:200]] if re.search(r'MODIFIC|DEROG|SUSTITU|INCORPOR|PRORROG|SUSPEND|'
                                                                      r'REEMPLAZ|TEXTO ORDENADO', obs.upper()) else []
        upd = dmy(_field(s, 'FechaVerificacion') or '')
        if item.get('code'):
            # a code is the digest's consolidated text (Digesto Jurídico, Ley 3092-A and later consolidations):
            # always its current text only, dated by the day the digest verified its record
            if not upd:
                return None
            later = later or ['texto consolidado del Digesto Jurídico']
        return {'page': item['page'], 'kind': 'ley', 'number': item['number'], 'title': htmlmod.unescape(item['title']),
                'pub': pub, 'promul': dmy(_field(s, 'Promulgacion') or ''), 'bo': _field(s, 'Boletin'),
                'updated': upd, 'related_later': later,
                'text_url': f'{BASE}/Documentos/Documento/GetDocumentoFisico?nombreArchivo={quote(item["file"])}'}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        paras = pdf_paragraphs_ordered(b)
        if paras and letters(''.join(paras)) == source_letters_pdf(b):
            return paras, b
        # 2026-10-31: the PDF's drawing order, checked against poppler's content-stream reading (-raw), as for Formosa
        paras = pdf_paragraphs_ordered(b, stream=True)
        if paras and letters(''.join(paras)) == source_letters_pdf_raw(b):
            return paras, b
        # the two PDF readers disagree on the order of the words in both readings: the norm is left out rather than
        # published with letters the check cannot confirm
        E.say(f'chaco: left out {d["page"]} (PDF readers disagree on reading order)')
        return None
