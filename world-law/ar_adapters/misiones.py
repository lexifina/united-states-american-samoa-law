"""Provincia de Misiones (gitlaw-scraper-dell, 2026-10-30): the Cámara de Representantes de la Provincia de Misiones
(www.diputadosmisiones.gov.ar; robots.txt 404; no challenge).

Constitution: its Documentos page (/nuevo/documentos, js/documentos.js) shows /nuevo/archivos/"2- CONSTITUCION
PROVINCIAL.pdf", a PDF with a text layer (Word, created 11 March 2022) of the Constitución de la Provincia de Misiones
sanctioned by the Convención Constituyente on 21 April 1958, with the later amendments in place and footnotes giving
the replaced wording (Ley 254, Ley 2604, Ley 3651, Ley IV - Nº 60). Current text only, dated by that edition
(11 March 2022). Its own cláusula transitoria art. 11: "La presente Constitución regirá a partir del día de la fecha"
(21 April 1958); the source prints no Boletín Oficial date, so the record's publication date is that day.

Laws: the Cámara's Digesto Jurídico (POST modulos/ramas_ajax.php) gives sanción dates and PDFs but no publication dates
(fecha_publi empty), so laws are not built for now.
"""
from __future__ import annotations

from urllib.parse import quote

from ar_provinces import get
from ar_adapters._dell import patch_article_dot, patch_in_force, pdf_paragraphs_layout, source_letters_pdf_raw

PDF = 'https://www.diputadosmisiones.gov.ar/nuevo/archivos/' + quote('2- CONSTITUCION  PROVINCIAL.pdf')
PAGE = 'https://www.diputadosmisiones.gov.ar/nuevo/documentos'

patch_in_force([
    ('1958-04-21', 'Artículo 11.- La presente Constitución regirá a partir del día de la fecha', '1958-04-21',
     'its own clause (cláusulas transitorias, art. 11): "La presente Constitución regirá a partir del día de la '
     'fecha" (21 April 1958)'),
])
patch_article_dot()


class Adapter:
    host = 'www.diputadosmisiones.gov.ar'
    source = {
        'name': 'Cámara de Representantes de la Provincia de Misiones (www.diputadosmisiones.gov.ar)',
        'url': PAGE,
        'publisher': 'Cámara de Representantes de la Provincia de Misiones',
        'gazette': 'Boletín Oficial de la Provincia de Misiones',
        'notes': 'The Cámara publishes the Constitución de la Provincia de Misiones (1958) with its later amendments in '
                 'place, and footnotes giving the replaced wording, as a PDF with a text layer (edition of 11 March '
                 '2022). The site states no terms of use for it.',
    }
    decisions = [
        'The constitution is the text the Cámara publishes: the 1958 Constitución with its amendments in place (Ley '
        '254, Ley 2604, Ley 3651, Ley IV - Nº 60; the source\'s footnotes give each replaced wording). Earlier '
        'consolidated wordings are not published as texts, so it is shown as its current text only (the oldest '
        'version available), dated by the Cámara\'s edition, 11 March 2022 (the PDF\'s creation date). The norm\'s '
        'record dates the constitution 21 April 1958, the day of its sanción, from which its own transitional art. 11 '
        'makes it rule; the source gives no Boletín Oficial date.',
        'Units: the heading (encabezado: the edition\'s title pages, the list of the Convención\'s members, the '
        'enacting formula and the headings before Artículo 1) and one file per article, holding the article and '
        'everything printed after it up to the next article (section headings, the source\'s footnotes with the '
        'replaced wording, the running heads and page numbers). The Cláusulas transitorias are numbered from Artículo 1 '
        'again and are filed as art-001-dup2 and so on; the Reglamento of 1810 inserted by the Convención follows the '
        'last of them. "Artículo. 50.-" (so printed) is filed as article 50. Nothing is dropped. One paragraph per line, '
        'spacing normalised.',
        'The PDF is read in its content order (PyMuPDF), and its letters and digits are checked against poppler\'s '
        'pdftotext -raw, which reads the same order.',
    ]
    dates_note = ('The constitution is the text as the Cámara publishes it, with its amendments in place (current text '
                  'only, the oldest version available), dated by the Cámara\'s edition of 11 March 2022; its earlier '
                  'wording is given only in the source\'s footnotes.')
    source_letters = staticmethod(source_letters_pdf_raw)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PAGE, 'title': 'Constitución de la Provincia de Misiones',
                                  'constitution': True}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': PAGE, 'kind': 'constitucion', 'number': '', 'year': '1958',
                'title': 'Constitución de la Provincia de Misiones', 'pub': '1958-04-21', 'promul': None,
                'updated': '2022-03-11', 'related_later': ['Ley 254', 'Ley 2604', 'Ley 3651', 'Ley IV - Nº 60'],
                'text_url': PDF}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b
