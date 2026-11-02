"""Provincia de Salta (gitlaw-scraper-dell, 2026-10-30): the Cámara de Diputados de la Provincia de Salta
(www.diputadosalta.gob.ar; robots.txt has only comments, no rules; no challenge).

Constitution: /CONSTITUCION_PROVINCIAL_4_11_2022.pdf (linked from the site's "Constitución Provincial"), a PDF with a
text layer of the consolidated Constitución de la Provincia de Salta: sanctioned 2 June 1986, partly reformed by the
Convención Constituyente on 7 April 1998, Enmienda by Ley 7246 (B.O. 29/8/2003), reformed 30 August 2003 and 22
December 2021 (its own closing note), with "*Modificado por la Convención Constituyente de fecha 16/12/2021" notes.
It is the current text only, shown from the date of the Cámara's edition (4 November 2022, the file's name), the
engine's rule for a consolidated text (dated by the record's last update).

The record of the norm: published in the Boletín Oficial on 21 December 2021 (the 2021 reform, as the Consejo
Profesional de Ciencias Económicas de Salta's copy records it; the hcdn.gob.ar collection gives "Última reforma: 22 de
Diciembre de 2021"), in force the day after (its cláusula transitoria PRIMERA: "La presente Constitución entra en
vigencia al día siguiente de su publicación").

Codes and laws: the Cámara's Digesto Jurídico (Ley 7530, /web/digesto): /web/seccion_dig?id=1 (Códigos) and id=4
(Leyes vigentes) list each norm with its sanción, promulgation and publication dates and Boletín Oficial number, and a
born-digital PDF (/digesto_leyes/<n>/download_file, Word) of its text as the Digesto keeps it, with notes such as
"(Modificado por el Art. 1º de la Ley Nº 7998/2017)". A text with such notes is its current text only, dated by the PDF's
creation date (the Digesto's edition of it); a text without them is shown as enacted.
"""
from __future__ import annotations

import re
from datetime import date

from ar_provinces import clean, decode, dmy, get, htmlmod
from ar_adapters._dell import patch_in_force, pdf_paragraphs_layout, source_letters_pdf_raw

PDF = 'https://www.diputadosalta.gob.ar/CONSTITUCION_PROVINCIAL_4_11_2022.pdf'
PAGE = 'https://www.diputadosalta.gob.ar/web/digesto'
BASE = 'https://www.diputadosalta.gob.ar'


def _rows(section: int) -> list[dict]:
    b = get(f'{BASE}/web/seccion_dig?id={section}')
    if not b:
        return []
    out = []
    for r in re.findall(r'<tr>\s*(.*?)</tr>', decode(b), re.S):
        cells = [clean(htmlmod.unescape(re.sub(r'<[^>]+>', '', c))) for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)]
        link = re.search(r'href="(/digesto_leyes/\d+/download_file)"', r)
        if len(cells) < 9 or not link or not re.fullmatch(r'\d+', cells[1]):
            continue
        out.append({'page': BASE + link.group(1), 'tipo': cells[0], 'number': cells[1], 'sancion': dmy(cells[2]),
                    'promul': dmy(cells[3]), 'pub': dmy(cells[4]), 'materia': cells[5], 'bo': cells[6],
                    'title': cells[7]})
    return out


def _pdf_date(b: bytes) -> str | None:
    import pymupdf
    with pymupdf.open(stream=b, filetype='pdf') as doc:
        m = re.match(r'D:(\d{4})(\d{2})(\d{2})', doc.metadata.get('creationDate') or '')
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None

patch_in_force([
    ('2021-12-21', 'PRIMERA: La presente Constitución entra en vigencia al día siguiente de su publicación', '2021-12-22',
     'its own clause (cláusula transitoria primera): "La presente Constitución entra en vigencia al día siguiente de su '
     'publicación"; the 2021 reform published in the Boletín Oficial on 21 December 2021'),
])


class Adapter:
    host = 'www.diputadosalta.gob.ar'
    source = {
        'name': 'Cámara de Diputados de la Provincia de Salta (www.diputadosalta.gob.ar)',
        'url': 'https://www.diputadosalta.gob.ar/',
        'publisher': 'Cámara de Diputados de la Provincia de Salta',
        'gazette': 'Boletín Oficial de la Provincia de Salta',
        'notes': 'The Cámara publishes the consolidated Constitución de la Provincia de Salta (1986, with the reforms of '
                 '1998, 2003 and 2021 and the Enmienda of Ley 7246) as a PDF with a text layer, edition of 4 November '
                 '2022 (www.diputadosalta.gob.ar/CONSTITUCION_PROVINCIAL_4_11_2022.pdf), and its Digesto Jurídico (Ley '
                 '7530): for each code and law in force, its sanción, promulgation and publication dates, Boletín '
                 'Oficial number and a PDF of its text as the Digesto keeps it, with notes on later changes. The site '
                 'states no terms of use for them.',
    }
    decisions = [
        'The constitution is the consolidated text the Cámara publishes (sanctioned 2 June 1986; reformed in 1998, '
        '2003 and 2021; Enmienda by Ley 7246, 2003). Earlier wordings are not published by the source, so it is shown '
        'as its current text only (the oldest version available), dated by the Cámara\'s edition, 4 November 2022. '
        'The norm\'s record gives the 2021 reform\'s publication in the Boletín Oficial (21 December 2021) and its '
        'in-force day under the cláusula transitoria primera (the day after publication, 22 December 2021).',
        'Units: the heading (encabezado: the title, the Preámbulo and the headings before Artículo 1) and one file per '
        'article, holding the article and everything printed after it up to the next article (section headings, the '
        'source\'s "*Modificado ..." notes, page numbers and, after the last article, the Disposiciones transitorias, '
        'signatures, certification, the Convención\'s declarations and the history note). Nothing is dropped. One '
        'paragraph per line, spacing normalised; a word broken at a line end by a soft hyphen is joined, a printed '
        'hyphen is kept.',
        'The PDF is read in its content order (PyMuPDF), and its letters and digits are checked against poppler\'s '
        'pdftotext -raw, which reads the same order.',
    ]
    dates_note = ('The constitution is the consolidated text as the Cámara publishes it (current text only, the oldest '
                  'version available), dated by the Cámara\'s edition of 4 November 2022; its earlier wording is not '
                  'shown.')
    source_letters = staticmethod(source_letters_pdf_raw)

    def catalogue(self, n_laws: int) -> dict:
        codes = _rows(1)
        laws = sorted(_rows(4), key=lambda r: (r['pub'] or '', int(r['number'])), reverse=True)
        code_pages = {c['page'] for c in codes}
        laws = [r for r in laws if r['page'] not in code_pages and r['tipo'] == 'Ley']
        return {'constitucion': [{'page': PDF, 'title': 'Constitución de la Provincia de Salta',
                                  'constitution': True}], 'codigo': codes, 'ley': laws[:n_laws]}

    def detail(self, item: dict) -> dict | None:
        if item.get('constitution'):
            return {'page': PDF, 'kind': 'constitucion', 'number': '', 'year': '2021',
                    'title': 'Constitución de la Provincia de Salta', 'pub': '2021-12-21', 'promul': None,
                    'updated': '2022-11-04',
                    'related_later': ['Convención Constituyente 7/4/1998', 'Ley 7246 (enmienda, B.O. 29/8/2003)',
                                      'Convención Constituyente 30/8/2003', 'Convención Constituyente 16-22/12/2021'],
                    'text_url': PDF}
        if not item.get('pub'):
            return None
        b = get(item['page'])
        if not b or not b.startswith(b'%PDF'):
            return None
        kind = 'decreto-ley' if item['tipo'].lower().startswith('decreto') else 'ley'
        return {'page': item['page'], 'kind': kind, 'number': item['number'],
                'year': (item.get('sancion') or item['pub'])[:4], 'title': item['title'], 'pub': item['pub'],
                'promul': item.get('promul'), 'updated': _pdf_date(b), 'related_later': [],
                'text_url': item['page']}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b
