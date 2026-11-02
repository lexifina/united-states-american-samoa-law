"""Provincia de Entre Ríos (gitlaw-scraper-dell, 2026-10-30): the Honorable Cámara de Senadores de la Provincia de Entre
Ríos (www.senadoer.gob.ar, WordPress; robots.txt disallows only /wp-admin/; no challenge).

Constitution: the site's "Constitución de Entre Ríos" link (/descargas/524) is a PDF with a text layer of the
Constitución sanctioned by the Convención Constituyente on 3 October 2008. Its own art. 296: "La presente Constitución
regirá desde 1º de noviembre de dos mil ocho" (a date half in words, which the engine's reader does not see), so the day
is given here. Published in the Boletín Oficial on 15 October 2008 (as the Ministerio de Salud de la Nación's e-legis
copy records it: "Sanción: 03/10/2008; Boletín Oficial 15/10/2008"; the PDF here prints no publication line).

Laws: each /ley/ley-n-NNNNN/ page gives promulgation and publication dates, but its download is the whole Boletín
Oficial issue the law appeared in (e.g. Ley 11.135: the 102-page issue of 22 December 2023), not the law alone, so laws
are not built from it for now.
"""
from __future__ import annotations

from ar_provinces import get
from ar_adapters._dell import patch_in_force, pdf_paragraphs_layout, source_letters_pdf_raw

PDF = 'https://www.senadoer.gob.ar/descargas/524'
PAGE = 'https://www.senadoer.gob.ar/'

patch_in_force([
    ('2008-10-15', 'La presente Constitución regirá desde 1º de noviembre de dos mil ocho', '2008-11-01',
     'its own clause (art. 296): "La presente Constitución regirá desde 1º de noviembre de dos mil ocho"'),
])


class Adapter:
    host = 'www.senadoer.gob.ar'
    source = {
        'name': 'Honorable Cámara de Senadores de la Provincia de Entre Ríos (www.senadoer.gob.ar)',
        'url': PAGE,
        'publisher': 'Honorable Cámara de Senadores de la Provincia de Entre Ríos',
        'gazette': 'Boletín Oficial de la Provincia de Entre Ríos',
        'notes': 'The Senate publishes the Constitución de la Provincia de Entre Ríos sanctioned by the Convención '
                 'Constituyente on 3 October 2008 as a PDF with a text layer (www.senadoer.gob.ar/descargas/524). The '
                 'site states no terms of use for it.',
    }
    decisions = [
        'The constitution is the 2008 text the Senate publishes, shown as enacted and dated the day its own art. 296 '
        'puts it in force: "La presente Constitución regirá desde 1º de noviembre de dos mil ocho" (sanción 3 October '
        '2008; Boletín Oficial 15 October 2008). The 1933 text it replaced is not shown.',
        'Units: the heading (encabezado: the title and enacting formula before Artículo 1) and one file per article, '
        'holding the article and everything printed after it up to the next article (section headings, the running '
        'head and page numbers printed in the PDF and, after art. 297, the closing formula and signatures). Nothing is '
        'dropped. One paragraph per line, spacing normalised.',
        'The PDF is read in its content order (PyMuPDF), and its letters and digits are checked against poppler\'s '
        'pdftotext -raw, which reads the same order.',
    ]
    dates_note = ('The constitution is the 2008 text as the Senate publishes it, shown as enacted on the day it took '
                  'effect (1 November 2008, its art. 296).')
    source_letters = staticmethod(source_letters_pdf_raw)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PDF, 'title': 'Constitución de la Provincia de Entre Ríos',
                                  'constitution': True}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': PDF, 'kind': 'constitucion', 'number': '', 'year': '2008',
                'title': 'Constitución de la Provincia de Entre Ríos', 'pub': '2008-10-15', 'promul': None,
                'updated': None, 'related_later': [], 'text_url': PDF, 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b
