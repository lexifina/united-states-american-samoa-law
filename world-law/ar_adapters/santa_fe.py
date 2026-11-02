"""Provincia de Santa Fe (gitlaw-scraper-dell, 2026-10-30): the Cámara de Diputadas y Diputados de la Provincia de
Santa Fe (diputadossantafe.gov.ar; robots.txt 404, no challenge).

Its constitution page links the "Ejemplar auténtico" PDF (text layer) of the Constitución de la Provincia Invencible de
Santa Fe, Reforma 2025, sanctioned 10 September 2025. Its own cláusula transitoria PRIMERA: "Esta Constitución entrará
en vigencia a partir del día de su publicación" (outside the last paragraphs the engine reads, so it is given here).
Published in the Boletín Oficial on Thursday 11 September 2025 (the government hosts www.santafe.gob.ar / .gov.ar, which
carry the Boletín Oficial, time out from this machine; the date is the one reported the same day, La Capital,
"En vigencia: la nueva Constitución de Santa Fe fue publicada en el Boletín Oficial", 2025-09-11).

Laws: no law database on the Cámara's site; the government and Senate hosts time out. Constitution only for now.
"""
from __future__ import annotations

from ar_provinces import get
from ar_adapters._dell import patch_in_force, pdf_paragraphs_layout, source_letters_pdf_raw

PDF = 'https://diputadossantafe.gov.ar/web/files/upload/la-camara/constitucion_provincial.pdf'
PAGE = 'https://diputadossantafe.gov.ar/web/camara/constitucion-provincial/'

patch_in_force([
    ('2025-09-11', 'PRIMERA: Esta Constitución entrará en vigencia a partir del día de su publicación', '2025-09-11',
     'its own clause (cláusula transitoria primera): "Esta Constitución entrará en vigencia a partir del día de su '
     'publicación"; Boletín Oficial of 11 September 2025'),
])


class Adapter:
    host = 'diputadossantafe.gov.ar'
    source = {
        'name': 'Cámara de Diputadas y Diputados de la Provincia de Santa Fe (diputadossantafe.gov.ar)',
        'url': PAGE,
        'publisher': 'Cámara de Diputadas y Diputados de la Provincia de Santa Fe',
        'gazette': 'Boletín Oficial de la Provincia de Santa Fe',
        'notes': 'The Cámara publishes the "Ejemplar auténtico" of the Constitución de la Provincia Invencible de Santa '
                 'Fe, Reforma 2025 (Edición 0, from the text sanctioned in plenary session on 10 September 2025), as a '
                 'PDF with a text layer. The site footer reads "Todos los derechos reservados"; it states no terms for '
                 'the legal texts themselves.',
    }
    decisions = [
        'The constitution is the 2025 text (Reforma 2025, sanctioned 10 September 2025), shown as enacted and dated the '
        'day its own cláusula transitoria primera puts it in force, the day of its publication: the Boletín Oficial of '
        '11 September 2025. The 1962 text it replaces is not published by the source and is not shown.',
        'Units: the heading (encabezado: the edition\'s title pages, the list of the Convención\'s members and staff, '
        'the Preámbulo and the headings before Artículo 1) and one file per article, holding the article and everything '
        'printed after it up to the next article (section headings, the page numbers printed in the PDF and, after the '
        'last article, the Disposiciones transitorias and the closing formula). Nothing is dropped. One paragraph per '
        'line, spacing normalised; a word broken at a line end by a soft hyphen is joined.',
        'The PDF is read in its content order (PyMuPDF), and its letters and digits are checked against poppler\'s '
        'pdftotext -raw, which reads the same order.',
    ]
    dates_note = ('The constitution is the 2025 text as the Cámara publishes it, shown as enacted on the day it took '
                  'effect (11 September 2025, its publication in the Boletín Oficial; cláusula transitoria primera).')
    source_letters = staticmethod(source_letters_pdf_raw)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PAGE, 'title': 'Constitución de la Provincia de Santa Fe',
                                  'constitution': True}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        b = get(PAGE)
        if not b or b'constitucion_provincial.pdf' not in b:
            return None
        return {'page': PAGE, 'kind': 'constitucion', 'number': '', 'year': '2025',
                'title': 'Constitución de la Provincia Invencible de Santa Fe (Reforma 2025)', 'pub': '2025-09-11',
                'promul': None, 'updated': None, 'related_later': [], 'text_url': PDF, 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b
