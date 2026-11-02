"""Provincia de Jujuy (gitlaw-scraper-dell, 2026-10-30): the Legislatura de Jujuy (www.legislaturajujuy.gov.ar;
robots.txt 404, i.e. no rules; Angular site, no reuse terms seen).

- Constitution: /docs/constitucion_provincial.pdf (text layer): the Constitución de la Provincia de Jujuy sanctioned
  by the Convención Constituyente on 20 June 2023, "Publicada en el B.O. Nº 68 21 de Junio de 2023"; cláusula
  transitoria primera: "Esta Constitución entrará en vigencia a partir del día de su publicación".
- Laws: the site's REST list (/rest/index.php/labor/legislativa/acceso/a/leyes/lista, detalle/<id>) gives each law's
  sanción, promulgation and publication dates, but the texts are on sileju.legislaturajujuy.gov.ar, which refuses
  connections from this machine (ports 80 and 443, 2026-10-30): laws are not built for now.
"""
from __future__ import annotations

import sys

import ar_provinces as E
from ar_provinces import get, letters, source_letters_pdf
from ar_adapters._ar_pdf import pdf_paragraphs_ordered

BASE = 'https://www.legislaturajujuy.gov.ar'
CONST = BASE + '/docs/constitucion_provincial.pdf'

_VIGENCIA = [
    ('2023-06-21', 'Esta Constitución entrará en vigencia a partir del día de su publicación', '2023-06-21',
     'its own clause (cláusula transitoria primera): "Esta Constitución entrará en vigencia a partir del día de su '
     'publicación" (Boletín Oficial Nº 68, 21 June 2023)'),
]


def _patch_in_force():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'in_force', None)
        if orig is None or getattr(orig, '_jy_vigencia', False):
            continue

        def wrapped(paras, pub, promul, _o=orig):
            for opub, phrase, day, basis in _VIGENCIA:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._jy_vigencia = True
        mod.in_force = wrapped


_patch_in_force()


class Adapter:
    host = 'www.legislaturajujuy.gov.ar'
    source = {
        'name': 'Legislatura de la Provincia de Jujuy (www.legislaturajujuy.gov.ar)',
        'url': 'https://www.legislaturajujuy.gov.ar/',
        'publisher': 'Legislatura de Jujuy (www.legislaturajujuy.gov.ar)',
        'gazette': 'Boletín Oficial de la Provincia de Jujuy',
        'notes': 'The constitution: the Legislatura\'s PDF of the Constitución de la Provincia de Jujuy sanctioned on '
                 '20 June 2023 and published in Boletín Oficial Nº 68 of 21 June 2023. Laws are listed by the '
                 'Legislatura with their dates; their texts (on sileju.legislaturajujuy.gov.ar) were not reachable '
                 'when this was built.',
        'dates_note': 'The constitution of 2023 is shown as enacted, dated 21 June 2023, the day of its publication, '
                      'from which its cláusula transitoria primera puts it in force. It has not been amended since.',
    }
    decisions = [
        'Constitution: the Legislatura\'s PDF of the Constitución de la Provincia de Jujuy (sanctioned 20 June 2023; '
        'published in Boletín Oficial Nº 68 of 21 June 2023; cláusula transitoria primera: "Esta Constitución entrará '
        'en vigencia a partir del día de su publicación"), shown as enacted, dated 21 June 2023. The constitution of '
        '1986 it replaced is not shown.',
        'Laws are not built yet: the Legislatura\'s law texts are served from sileju.legislaturajujuy.gov.ar, which did '
        'not answer from this machine on 30 October 2026.',
        'Units: the heading (encabezado: everything before Artículo 1, the preamble included) and one file per article, '
        'holding the article and everything printed after it up to the next article (section headings, the '
        'transitional clauses after the last article, signatures, page numbers). Nothing is dropped. One paragraph per '
        'line, spacing normalised.',
    ]
    source_letters = staticmethod(source_letters_pdf)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': CONST}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': CONST, 'kind': 'constitucion', 'number': '', 'year': '2023',
                'title': 'Constitución de la Provincia de Jujuy', 'pub': '2023-06-21', 'promul': None,
                'updated': None, 'related_later': [], 'text_url': CONST, 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or b[:4] != b'%PDF':
            return None
        paras = pdf_paragraphs_ordered(b)
        if not paras or letters(''.join(paras)) != source_letters_pdf(b):
            E.say(f'jujuy: left out {d["text_url"]} (the two PDF readers disagree)')
            return None
        return paras, b
