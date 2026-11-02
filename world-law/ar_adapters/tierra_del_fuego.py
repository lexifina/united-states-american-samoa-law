"""Provincia de Tierra del Fuego, Antártida e Islas del Atlántico Sur (gitlaw-scraper-dell, lane 3, 2026-10-30): the
provincial government's site (www.tierradelfuego.gob.ar; robots.txt "User-agent: *" disallows only /wp-admin/,
Crawl-delay 10, obeyed; no challenge; no terms of use for the texts seen). The Legislatura's www.legistdf.gob.ar is not
used: its robots.txt disallows ClaudeBot on /lp/ (the law archive).

Constitution: the site's CONSTITUCIONES page links /wp-content/uploads/2025/06/const_tdf.pdf (text layer), the
Constitución de la Provincia sanctioned by the Convención Constituyente on 17 May 1991, as enacted (its transitional
clauses for the first elections included; no amendment notes). Its own Cláusula transitoria PRIMERA: "Esta
Constitución entrará en vigencia a partir del día siguiente al de su publicación". Published in the Boletín Oficial on
28 May 1991 (the Boletín itself is not online for 1991; the date is the one the national collections record, e.g. the
Ministerio de Salud's Legisalud copy "Publicado en: Boletín Oficial 28/05/1991", and the press: "entrando en vigencia
con su publicación en el Boletín Oficial el 28 de mayo"), so in force 29 May 1991.

The PDF prints the digit zero as a capital letter O in many article numbers ("Artículo 1O°", "Artículo 2OO°"). The
text is kept exactly as printed; only the unit's id reads such a number with O as 0 (patched in this process, below),
so "Artículo 1O°" is its own unit art-010 instead of running into article 9.

Laws: none built (the government site has no law collection; the Legislatura's archive is disallowed to ClaudeBot).
"""
from __future__ import annotations

import re
import sys

import ar_provinces as E
from ar_provinces import get, net
from ar_adapters._dell import patch_in_force, pdf_paragraphs_layout, source_letters_pdf_raw

HOST = 'www.tierradelfuego.gob.ar'
PDF = 'https://www.tierradelfuego.gob.ar/wp-content/uploads/2025/06/const_tdf.pdf'
PAGE = 'https://www.tierradelfuego.gob.ar/constituciones/'
O_NUM = re.compile(r'^(\s*Art[íi]culo\s+)([0-9O]*O[0-9O]*)(?=\s*°)')

patch_in_force([
    ('1991-05-28', 'Esta Constitución entrará en vigencia a partir del día siguiente al de su publicación', '1991-05-29',
     'its own clause (cláusula transitoria primera): "Esta Constitución entrará en vigencia a partir del día siguiente '
     'al de su publicación"; Boletín Oficial of 28 May 1991'),
])


def _patch_article_id():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'article_id', None)
        if orig is None or getattr(orig, '_tdf', False):
            continue

        def wrapped(line, _o=orig):
            m = O_NUM.match(line)
            if m and m.group(2)[0] != 'O':
                line = m.group(1) + m.group(2).replace('O', '0') + line[m.end():]   # for the id only
            return _o(line)
        wrapped._tdf = True
        mod.article_id = wrapped


_patch_article_id()


class Adapter:
    host = HOST
    source = {
        'name': 'Gobierno de la Provincia de Tierra del Fuego, Antártida e Islas del Atlántico Sur (www.tierradelfuego.gob.ar)',
        'url': PAGE,
        'publisher': 'Gobierno de la Provincia de Tierra del Fuego, Antártida e Islas del Atlántico Sur',
        'gazette': 'Boletín Oficial de la Provincia de Tierra del Fuego',
        'notes': 'The provincial government publishes the Constitución de la Provincia de Tierra del Fuego, Antártida e '
                 'Islas del Atlántico Sur (sanctioned by the Convención Constituyente on 17 May 1991) as a PDF with a '
                 'text layer on its CONSTITUCIONES page. The site states no terms of use for it.',
    }
    decisions = [
        'The constitution is the 1991 text as the government publishes it, shown as enacted and dated the day its own '
        'cláusula transitoria primera puts it in force, the day after its publication in the Boletín Oficial (28 May '
        '1991): 29 May 1991. The 1991 Boletín is not online; the publication day is the one the national collections '
        'record. The source shows no later amendment.',
        'The PDF prints the digit zero as the letter O in many article numbers ("Artículo 1O°", "Artículo 2OO°"). The '
        'text keeps them as printed; only the unit file name reads such a number as digits (art-010, art-200), so each '
        'article is its own unit.',
        'Units: the heading (encabezado: the title and the headings before Artículo 1) and one file per article, '
        'holding the article and everything printed after it up to the next article (the marginal heading of the next '
        'article where the PDF prints it on its own line, section headings and, after the last article, the cláusulas '
        'transitorias, the closing formula and the date). Nothing is dropped. One paragraph per line, spacing '
        'normalised; a word broken at a line end by a soft hyphen is joined.',
        'The PDF is read in its content order (PyMuPDF), and its letters and digits are checked against poppler\'s '
        'pdftotext -raw, which reads the same order.',
    ]
    dates_note = ('The constitution is the 1991 text as the government publishes it, shown as enacted on the day it '
                  'took effect (29 May 1991, the day after its publication in the Boletín Oficial).')
    source_letters = staticmethod(source_letters_pdf_raw)

    def __init__(self):
        net().pause[HOST] = max(net().pause.get(HOST, 0), 10.5)    # robots.txt Crawl-delay: 10

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PAGE, 'title': 'Constitución de la Provincia de Tierra del Fuego',
                                  'constitution': True}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': PAGE, 'kind': 'constitucion', 'number': '', 'year': '1991',
                'title': 'Constitución de la Provincia de Tierra del Fuego, Antártida e Islas del Atlántico Sur',
                'pub': '1991-05-28', 'promul': '1991-05-17', 'updated': None, 'related_later': [], 'text_url': PDF,
                'as_enacted': True,
                'in_force': ('1991-05-29', 'its own clause (cláusula transitoria primera): "Esta Constitución entrará '
                                           'en vigencia a partir del día siguiente al de su publicación"; Boletín '
                                           'Oficial of 28 May 1991'),
                'note': 'As enacted: the Constitution sanctioned by the Convención Constituyente on 17 May 1991.'}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b
