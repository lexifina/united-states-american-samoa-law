"""Provincia del Chubut (gitlaw-scraper-dell, lane 3, 2026-10-30): the Honorable Legislatura de la Provincia del
Chubut (legislaturadelchubut.gob.ar; robots.txt Yoast "User-agent: * / Disallow:" (nothing disallowed); no challenge;
footer "© 2021-2024. Todos los derechos reservados", no terms for the legal texts). The old host www.legischubut.gov.ar
presents a certificate for another name (hostname mismatch): not used (TLS verification is never disabled).

Constitution: the Legislatura's "Normativas vigentes" page links /wp-content/uploads/2026/04/CONSTITUCION-PROVINCIAL.pdf
(text layer; WordPress media record dated 2026-04-29), the Constitution of 11 October 1994 with the 2025 enmienda of
arts. 247 and 248 (Ley V N.º 201, referéndum convoked by Decreto 718/2025, promulgated and incorporated by Decreto
1389/2025) incorporated, with the source's notes. Earlier editions on the same site: 2022-05-16 and 2025-08-08
("ajuste 2025"). Current text only, dated by this edition (2026-04-29).

Laws: the Legislatura's Digesto Jurídico (digesto.legislaturadelchubut.gob.ar, JSON API /api/public/...; robots
disallows only account/management paths) holds the Digesto's consolidated texts (texto definitivo, renumbered by
rama, with antecedents and equivalence tables) plus sanción/promulgación/publicación dates.
"""
from __future__ import annotations

import html as htmlmod
import json
import re

from ar_provinces import AMEND_NOTE, BLOCK, clean, get, letters
from ar_adapters._dell import pdf_paragraphs_layout, source_letters_pdf_raw

API = 'https://digesto.legislaturadelchubut.gob.ar/api/public'
LIST = API + '/documentos?page={p}&size=50&sort=publicacionFecha,desc'
# a text consolidated by the Digesto Jurídico (texto definitivo, renumbered, with antecedents/equivalence tables) or
# carrying amendment notes is not shown: the Digesto gives no date for its current wording
CONSOLIDATED = re.compile(r'\(\s*Antes\s+Ley|TABLA\s+DE\s+(ANTECEDENTES|EQUIVALENCIAS)|Texto\s+definitivo|'
                          r'\b(modificad[oa]|sustituid[oa]|incorporad[oa]|derogad[oa])\s+por\s+(el\s+)?(art|ley)', re.I)


PDF = 'https://legislaturadelchubut.gob.ar/wp-content/uploads/2026/04/CONSTITUCION-PROVINCIAL.pdf'
PAGE = 'https://legislaturadelchubut.gob.ar/institucional/normativas-vigentes/'


class Adapter:
    host = 'legislaturadelchubut.gob.ar'
    source = {
        'name': 'Honorable Legislatura de la Provincia del Chubut (legislaturadelchubut.gob.ar)',
        'url': PAGE,
        'publisher': 'Honorable Legislatura de la Provincia del Chubut',
        'gazette': 'Boletín Oficial de la Provincia del Chubut',
        'notes': 'The Legislatura publishes the Constitución de la Provincia del Chubut (sanctioned by the Convención '
                 'Constituyente on 11 October 1994, in force 15 October 1994) as a PDF with a text layer, with the 2025 '
                 'enmienda of articles 247 and 248 (Ley V N.º 201; Decreto 1389/2025) incorporated and noted; this '
                 'edition was uploaded on 29 April 2026. The site footer reads "Todos los derechos reservados"; it '
                 'states no terms for the legal texts themselves.',
    }
    decisions = [
        'The constitution is the consolidated text the Legislatura publishes (the 1994 Constitution with the 2025 '
        'enmienda of arts. 247 and 248 incorporated, each marked by the source\'s note). The source gives no dated '
        'earlier wording in this file, so it is shown as its current text only (the oldest version available), dated '
        'by the edition\'s upload, 29 April 2026. Its own Disposición final primera puts the 1994 text in force on 15 '
        'October 1994 ("Esta Constitución rige a partir del día 15 de octubre de 1994").',
        'Units: the heading (encabezado: the title, the Preámbulo and the headings before Artículo 1) and one file per '
        'article, holding the article and everything printed after it up to the next article (the marginal headings '
        'of the next article, the source\'s "(Artículo modificado por enmienda ...)" notes and, after the last '
        'article, the Disposiciones complementarias, transitorias and finales and the signatures). Nothing is dropped. '
        'One paragraph per line, spacing normalised; a word broken at a line end by a soft hyphen is joined.',
        'The PDF is read in its content order (PyMuPDF), and its letters and digits are checked against poppler\'s '
        'pdftotext -raw, which reads the same order.',
    ]
    dates_note = ('The constitution is the consolidated text as the Legislatura publishes it (current text only, the '
                  'oldest version available), dated by the edition of 29 April 2026; its earlier wording is not shown.')

    def _page(self, p: int) -> list:
        b = get(LIST.format(p=p))
        return json.loads(b.decode('utf-8')) if b else []

    def catalogue(self, n_laws: int) -> dict:
        # newest first by publication date; the API sorts documents without a date first: find the first page with one
        lo, hi = 0, 400
        while lo < hi:
            mid = (lo + hi) // 2
            pg = self._page(mid)
            if pg and not pg[-1].get('publicacionFecha'):
                lo = mid + 1
            else:
                hi = mid
        import datetime as _dt
        recent = (_dt.date.today() - _dt.timedelta(days=12)).isoformat()   # in force (pub + 9) before today
        laws, p = [], max(lo, 0)
        while len(laws) < n_laws:
            pg = self._page(p)
            if not pg:
                break
            for x in pg:
                if (x.get('tipo') != 'LEY_PROVINCIAL' or not x.get('publicacionFecha') or x.get('borrador')
                        or (x.get('estadoConsolidacion') or '').upper() != 'VIGENTE' or not x.get('rama')
                        or not (x.get('textoFormateado') or '').strip() or x['publicacionFecha'] > recent):
                    continue
                if CONSOLIDATED.search(_plain(x['textoFormateado'])) or AMEND_NOTE.search(_plain(x['textoFormateado'])):
                    continue
                laws.append({'page': f"{API}/rama/{x['rama']['id']}/documento/{x['numero']}",
                             'number': x['numero'], 'rama': x['rama']['numero']})
                if len(laws) >= n_laws:
                    break
            p += 1
        return {'constitucion': [{'page': PDF, 'title': 'Constitución de la Provincia del Chubut',
                                  'constitution': True}], 'codigo': [], 'ley': laws}

    def detail(self, item: dict) -> dict | None:
        if not item.get('constitution'):
            b = get(item['page'])
            if not b:
                return None
            x = json.loads(b.decode('utf-8'))
            t = _plain(x.get('textoFormateado') or '')
            if not x.get('publicacionFecha') or CONSOLIDATED.search(t) or AMEND_NOTE.search(t):
                return None
            return {'page': item['page'], 'kind': 'ley', 'number': f"{x['rama']['numero']}-{x['numero']}",
                    'title': clean(x.get('resumen') or '')[:400], 'pub': x['publicacionFecha'],
                    'promul': x.get('promulgacionFecha'), 'updated': None, 'related_later': [],
                    'text_url': item['page'], 'as_enacted': True, 'json': True,
                    'note': f"As enacted: the Digesto Jurídico's text of Ley {x['rama']['numero']} N.º {x['numero']} "
                            f"(sanción {x.get('sancionFecha')}, promulgación {x.get('promulgacionFecha')} by Decreto "
                            f"{x.get('promulgacionDecreto')}, Boletín Oficial N.º {x.get('publicacionBo')} of "
                            f"{x['publicacionFecha']}), which carries no consolidation or amendment note."}
        return {'page': PDF, 'kind': 'constitucion', 'number': '', 'year': '1994',
                'title': 'Constitución de la Provincia del Chubut', 'pub': '1994-10-14', 'promul': None,
                'updated': '2026-04-29',
                'related_later': ['Ley V N.º 201 (enmienda de los arts. 247 y 248; Decreto 1389/2025)'],
                'in_force': ('1994-10-15', 'its own clause (Disposición final primera): "Esta Constitución rige a '
                                           'partir del día 15 de octubre de 1994"'),
                'text_url': PDF}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b:
            return None
        if d.get('json'):
            return json_paragraphs(b), b
        if not b.startswith(b'%PDF'):
            return None
        return pdf_paragraphs_layout(b), b

    @staticmethod
    def source_letters(b: bytes) -> str:
        if b.startswith(b'%PDF'):
            return source_letters_pdf_raw(b)
        import lxml.html
        h = json.loads(b.decode('utf-8'))['textoFormateado']
        return letters(lxml.html.fragment_fromstring(h, create_parent='div').text_content())


def _plain(h: str) -> str:
    return re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', h)))


def json_paragraphs(b: bytes) -> list[str]:
    """The record's textoFormateado (HTML) -> paragraphs (block elements and <br>), whitespace collapsed."""
    s = json.loads(b.decode('utf-8'))['textoFormateado']
    s = re.sub(r'(?s)<!--.*?-->', '', s)
    s = re.sub(r'(?is)<(script|style)\b.*?</\1\s*>', '', s)
    s = re.sub(r'[\r\n]+', ' ', s)
    s = BLOCK.sub('\x00', s)
    s = htmlmod.unescape(re.sub(r'<[^>]+>', '', s))
    return [c for c in (clean(x) for x in s.split('\x00')) if c]
