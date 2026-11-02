"""Provincia de Formosa (gitlaw-scraper-dell, 2026-10-30): the Gobierno de la Provincia de Formosa's portal
(www.formosa.gob.ar; robots.txt "User-agent: * / Allow: /", no AI rules; footer "Todos los Derechos Reservados", no
reuse terms). The Legislatura's site (www.legislaturaformosa.gob.ar) carries news only, no law texts.

- Constitution: /modulos/miprovincia/templates/files/constitucion2025.pdf (text layer): the Constitución de la
  Provincia de Formosa sanctioned and promulgated by the Convención Constituyente on 5 September 2025, "Publicada en
  el Boletín Oficial N° 12782 el día ocho de septiembre del año dos mil veinticinco"; cláusula transitoria 1ª: "La
  presente Constitución entrará en vigencia a partir de su publicación".
- Laws: no official per-law text source found (gazette issues only): not built.
"""
from __future__ import annotations

import sys

import ar_provinces as E
from ar_provinces import get, letters, source_letters_pdf
from ar_adapters._ar_pdf import pdf_paragraphs_ordered, source_letters_pdf_raw

CONST = 'https://www.formosa.gob.ar/modulos/miprovincia/templates/files/constitucion2025.pdf'
PAGE = 'https://www.formosa.gob.ar/miprovincia/simbolosprovinciales/constitucion'

_VIGENCIA = [
    ('2025-09-08', 'La presente Constitución entrará en vigencia a partir de su publicación', '2025-09-08',
     'its own clause (cláusula transitoria 1ª): "La presente Constitución entrará en vigencia a partir de su '
     'publicación" (Boletín Oficial N° 12782, 8 September 2025)'),
]


def _patch_in_force():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'in_force', None)
        if orig is None or getattr(orig, '_fo_vigencia', False):
            continue

        def wrapped(paras, pub, promul, _o=orig):
            for opub, phrase, day, basis in _VIGENCIA:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._fo_vigencia = True
        mod.in_force = wrapped


_patch_in_force()


class Adapter:
    host = 'www.formosa.gob.ar'
    source = {
        'name': 'Gobierno de la Provincia de Formosa (www.formosa.gob.ar)',
        'url': 'https://www.formosa.gob.ar/miprovincia/simbolosprovinciales/constitucion',
        'publisher': 'Gobierno de la Provincia de Formosa (www.formosa.gob.ar)',
        'gazette': 'Boletín Oficial de la Provincia de Formosa',
        'notes': "The constitution: the provincial government's PDF of the Constitución de la Provincia de Formosa "
                 'sanctioned on 5 September 2025 and published in Boletín Oficial N° 12782 of 8 September 2025.',
        'dates_note': 'The constitution of 2025 is shown as enacted, dated 8 September 2025, the day of its '
                      'publication, from which its cláusula transitoria 1ª puts it in force.',
    }
    decisions = [
        "Constitution: the provincial government's PDF of the Constitución de la Provincia de Formosa (sanctioned and "
        'promulgated by the Convención Constituyente on 5 September 2025; published in Boletín Oficial N° 12782 of 8 '
        'September 2025; cláusula transitoria 1ª: "La presente Constitución entrará en vigencia a partir de su '
        'publicación"), shown as enacted, dated 8 September 2025. The constitution of 1991/2003 it replaced is not shown.',
        'Laws are not built: no official source of per-law texts was found (the Legislatura site has news only).',
        'Units: the heading (encabezado: the preamble and everything before Art. 1) and one file per article, holding '
        'the article and everything printed after it up to the next article (section headings, the transitional '
        'clauses and the final provision after the last article). Nothing is dropped. One paragraph per line, spacing '
        'normalised.',
    ]
    source_letters = staticmethod(source_letters_pdf_raw)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PAGE}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': PAGE, 'kind': 'constitucion', 'number': '', 'year': '2025',
                'title': 'Constitución de la Provincia de Formosa', 'pub': '2025-09-08', 'promul': '2025-09-05',
                'updated': None, 'related_later': [], 'text_url': CONST, 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or b[:4] != b'%PDF':
            return None
        paras = pdf_paragraphs_ordered(b, stream=True)
        if not paras or letters(''.join(paras)) != source_letters_pdf_raw(b):
            E.say(f'formosa: left out {d["text_url"]} (the two PDF readers disagree)')
            return None
        return paras, b
