"""Provincia de Córdoba (gitlaw-scraper-dell, 2026-10-30): the Legislatura de la Provincia de Córdoba's website
(legislaturacba.gob.ar, WordPress; robots.txt disallows only /wp-admin/).

The constitution page carries the full text of the Constitución as reformed on 14 September 2001 (B.O. the same day).
Its own cláusula transitoria decimonovena says "ESTA reforma entra en vigencia el día diez de diciembre de dos mil
uno" (words, which the engine's digit-date reader does not see), so the date is given here (see _VIGENCIA).

Laws: the legislature's Gestión Legislativa Digital (gld.legislaturacba.gob.ar, Textos Aprobados) gives each law as
the text approved (sanción date only, no publication date), and the government digest web2.cba.gov.ar (leyes.nsf)
times out from this machine, so only the constitution is built for now.
"""
from __future__ import annotations

import sys

import ar_provinces as E
from ar_provinces import decode, get, html_paragraphs, letters

# (publication date, phrase that must be in the text, in-force day, basis): a vigencia clause written in words
_VIGENCIA = [
    ('2001-09-14', 'ESTA reforma entra en vigencia el día diez de diciembre de dos mil uno', '2001-12-10',
     'its own clause (cláusula transitoria decimonovena): "ESTA reforma entra en vigencia el día diez de diciembre de '
     'dos mil uno"; arts. 78, 79, 80, 82, 86, 87, 90 and the transitional clauses ruled from publication'),
]


def _patch_in_force():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'in_force', None)
        if orig is None or getattr(orig, '_vigencia_words', False):
            continue

        def wrapped(paras, pub, promul, _o=orig):
            for opub, phrase, day, basis in _VIGENCIA:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._vigencia_words = True
        mod.in_force = wrapped


def _patch_split():
    """The page prints a few articles twice over: a heading line ("Artículo 61: Educación") and then the body starting
    "Articulo 61. ...". Such a body is kept in the same unit as its heading (the next unit straight after a one-line
    unit of the same number), not filed as a duplicate article. Nothing is dropped or reordered."""
    import re
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'split_units', None)
        if orig is None or getattr(orig, '_merge_heads', False):
            continue

        def wrapped(paras, width=None, _o=orig):
            units = _o(paras, width)
            out, prev = {}, None
            for k, u in units.items():
                m = re.fullmatch(r'(art-[0-9a-z-]+?)-dup\d+', k)
                if m and prev == m.group(1) and out[prev]['text'].count('\n') == 1:
                    out[prev] = dict(out[prev], text=out[prev]['text'] + u['text'])
                    continue
                out[k] = u
                prev = k
            return out
        wrapped._merge_heads = True
        mod.split_units = wrapped


_patch_in_force()
_patch_split()

BASE = 'https://legislaturacba.gob.ar'
CONST = BASE + '/constitucion-de-la-provincia-de-cordoba/'


def _article_slice(s: str) -> str:
    i = s.find('<header class="entry-header')
    j = s.find('</article>', i)
    if i < 0 or j < 0:
        raise ValueError('article element not found')
    return s[i:j]


class Adapter:
    host = 'legislaturacba.gob.ar'
    source = {
        'name': 'Legislatura de la Provincia de Córdoba (legislaturacba.gob.ar)',
        'url': 'https://legislaturacba.gob.ar/',
        'publisher': 'Legislatura de la Provincia de Córdoba (legislaturacba.gob.ar)',
        'gazette': 'Boletín Oficial de la Provincia de Córdoba',
        'notes': 'The legislature publishes the full text of the Constitución de la Provincia de Córdoba as reformed '
                 'on 14 September 2001 (B.O. 14 September 2001) as one web page. The site footer reads "Todos los '
                 'derechos reservados"; it states no terms for the legal texts themselves.',
    }
    decisions = [
        'The constitution is the text the legislature publishes (the 2001 reform, with its transitional clauses), '
        'shown as enacted and dated the day its own cláusula transitoria decimonovena puts the reform in force, '
        '10 December 2001 (articles 78, 79, 80, 82, 86, 87, 90 and the transitional clauses ruled from publication on '
        '14 September 2001; the record dates the whole text on 10 December 2001). The 1987 text is not published by the '
        'source and is not shown.',
        'Units: the heading (encabezado: title, date line, B.O. line, Preámbulo and the headings before Artículo 1) and '
        'one file per article, holding the article and everything printed after it up to the next article (section '
        'headings and, after the last article, the Disposición complementaria, the Disposiciones transitorias and the '
        'closing formula). Nothing is dropped. One paragraph per line, spacing normalised.',
        'Only the page\'s article element (title and text) is read; the site navigation and footer are not part of '
        'the law and are left out.',
    ]
    dates_note = ('The constitution is the text as the legislature publishes it, the 2001 reform, shown as enacted on '
                  'the day it took effect (10 December 2001, its cláusula transitoria decimonovena).')

    @staticmethod
    def source_letters(b: bytes) -> str:
        """Independent reader (lxml): the text content of the page's <article> element."""
        import lxml.html
        doc = lxml.html.document_fromstring(decode(b))
        art = doc.xpath('//article')
        if len(art) != 1:
            return ''
        return letters(art[0].text_content())

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': CONST, 'title': 'Constitución de la Provincia de Córdoba',
                                  'constitution': True}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        b = get(item['page'])
        if not b:
            return None
        s = decode(b)
        if 'B.O., 14 de setiembre de 2001' not in s:
            raise SystemExit('Córdoba constitution page changed: B.O. line not found; check the date')
        return {'page': item['page'], 'kind': 'constitucion', 'number': '', 'year': '2001',
                'title': 'Constitución de la Provincia de Córdoba', 'pub': '2001-09-14', 'promul': None,
                'updated': None, 'related_later': [], 'text_url': item['page'], 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b:
            return None
        return html_paragraphs(_article_slice(decode(b)).encode('utf-8')), b
