"""Provincia de Tucumán (gitlaw-scraper-dell, 2026-10-30).

Constitution: the Honorable Legislatura de Tucumán (www.legislaturadetucuman.gob.ar, a single-page app; robots.txt
answers the app page, so no rules; no challenge) links /PDFs/constTucuman.pdf, the Constitución de la Provincia de
Tucumán sanctioned by the Convención Constituyente on 6 June 2006 (PDF with a born-digital text layer). Its own art. 170:
"La presente Constitución tiene vigencia, sin necesidad de requisito adicional alguno, a partir del primer día contado
desde su aprobación y sanción por parte de esta Convención" (sanción 6 June 2006). The day is counted under Código Civil
art. 24 (the initial day excluded), so the first day counted is 7 June 2006, which is also the day of its publication in
the Boletín Oficial (7 June 2006, as the Cámara de Diputados de la Nación's collection of provincial constitutions,
www2.hcdn.gob.ar ConsTucuman.pdf, records it; the PDF here prints no publication line).

Laws: the government's Registro Oficial de Leyes y Decretos (leyesydecretostucuman.gob.ar, Secretaría General de la
Gobernación; robots `*` Disallow: empty) lists every law with sanción, promulgation and Boletín Oficial dates and a
"Texto Original" PDF, but the PDFs seen are scans whose text layer is OCR (e.g. "Artículo 10.-" for "Artículo 1°.-"),
so laws are not built from them.
"""
from __future__ import annotations

from ar_provinces import get, source_letters_pdf
from ar_adapters._dell import patch_in_force, pdf_paragraphs_layout

PDF = 'https://www.legislaturadetucuman.gob.ar/PDFs/constTucuman.pdf'
PAGE = 'https://www.legislaturadetucuman.gob.ar/constitucionProvincial'

patch_in_force([
    ('2006-06-07', 'Art. 170.- La presente Constitución tiene vigencia, sin necesidad de requisito adicional alguno, a partir del '
           'primer día contado desde su aprobación y sanción por parte de esta Convención', '2006-06-07',
     'its own clause (art. 170): in force "a partir del primer día contado desde su aprobación y sanción por parte de '
     'esta Convención" (sanción 6 June 2006; the first day counted is 7 June 2006, Código Civil art. 24; Boletín Oficial 7 June 2006)'),
])


class Adapter:
    host = 'www.legislaturadetucuman.gob.ar'
    source = {
        'name': 'Honorable Legislatura de Tucumán (www.legislaturadetucuman.gob.ar)',
        'url': PAGE,
        'publisher': 'Honorable Legislatura de Tucumán',
        'gazette': 'Boletín Oficial de la Provincia de Tucumán',
        'notes': 'The legislature publishes the Constitución de la Provincia de Tucumán sanctioned by the Convención '
                 'Constituyente on 6 June 2006 as a PDF with a text layer (www.legislaturadetucuman.gob.ar/PDFs/'
                 'constTucuman.pdf). The site states no terms of use for it.',
    }
    decisions = [
        'The constitution is the 2006 text the legislature publishes, shown as enacted and dated the day its own art. '
        '170 puts it in force: "a partir del primer día contado desde su aprobación y sanción por parte de esta '
        'Convención" (sanción 6 June 2006), counted with the initial day excluded (Código Civil art. 24), so 7 June '
        '2006, the day it was published in the Boletín Oficial. The 1990 text it replaced is not shown.',
        'Units: the heading (encabezado: the title, the Preámbulo and the headings before Artículo 1) and one file per '
        'article, holding the article and everything printed after it up to the next article (section headings, the '
        'page numbers printed in the PDF and, after art. 170, the closing formula and signatures). Nothing is dropped. '
        'One paragraph per line, spacing normalised.',
    ]
    dates_note = ('The constitution is the 2006 text as the legislature publishes it, shown as enacted on the day it '
                  'took effect (7 June 2006, its art. 170).')
    source_letters = staticmethod(source_letters_pdf)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PAGE, 'title': 'Constitución de la Provincia de Tucumán',
                                  'constitution': True}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': PAGE, 'kind': 'constitucion', 'number': '', 'year': '2006',
                'title': 'Constitución de la Provincia de Tucumán', 'pub': '2006-06-07', 'promul': None, 'updated': None,
                'related_later': [], 'text_url': PDF, 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b
