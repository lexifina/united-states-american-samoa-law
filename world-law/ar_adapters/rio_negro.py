"""Provincia de Río Negro (gitlaw-scraper-dell, 2026-10-30): the Legislatura de Río Negro (web.legisrn.gov.ar; robots.txt
"User-agent: * / Disallow:" (nothing disallowed); its constitution page offers the PDF "para distribución libre y
gratuita").

- Constitution: webadmin.legisrn.gov.ar/wp-content/uploads/2025/05/CONSTITUCION-RIO-NEGRO-DIGITAL.pdf (text layer;
  "Versión digital 2025"): the Constitución de la Provincia de Río Negro sanctioned on 3 June 1988; Normas
  Complementarias art. 24: "Esta Constitución regirá a partir del día cuatro de junio de mil novecientos ochenta y
  ocho". Not amended since.
- Laws: from the Legislatura's Legislación Provincial database (deepening pass, 2026-10-30; see the end of this file).
"""
from __future__ import annotations

import sys

import ar_provinces as E
from ar_provinces import get, letters, source_letters_pdf
from ar_adapters._ar_pdf import pdf_paragraphs_ordered

CONST = 'https://webadmin.legisrn.gov.ar/wp-content/uploads/2025/05/CONSTITUCION-RIO-NEGRO-DIGITAL.pdf'
PAGE = 'https://web.legisrn.gov.ar/institucional/pagina/constitucion-de-la-provincia-de-rio-negro'

_VIGENCIA = [
    ('1988-06-03', 'Esta Constitución regirá a partir del día cuatro de junio de mil novecientos ochenta y ocho', '1988-06-04',
     'its own clause (Normas Complementarias, art. 24): "Esta Constitución regirá a partir del día cuatro de junio de '
     'mil novecientos ochenta y ocho"'),
]


def _patch_in_force():
    for mod in {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values():
        orig = getattr(mod, 'in_force', None)
        if orig is None or getattr(orig, '_rn_vigencia', False):
            continue

        def wrapped(paras, pub, promul, _o=orig):
            for opub, phrase, day, basis in _VIGENCIA:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._rn_vigencia = True
        mod.in_force = wrapped


_patch_in_force()


class Adapter:
    host = 'webadmin.legisrn.gov.ar'
    source = {
        'name': 'Legislatura de la Provincia de Río Negro (web.legisrn.gov.ar)',
        'url': 'https://web.legisrn.gov.ar/',
        'publisher': 'Legislatura de Río Negro (web.legisrn.gov.ar)',
        'gazette': 'Boletín Oficial de la Provincia de Río Negro',
        'notes': "The constitution: the Legislatura's digital edition (2025, PDF) of the Constitución de la Provincia "
                 'de Río Negro sanctioned on 3 June 1988, offered "para distribución libre y gratuita". It includes the '
                 "Legislatura's preface and index and the Convención's closing note, kept in the text.",
        'dates_note': 'The constitution of 1988 is shown as enacted, dated 4 June 1988, the day its Normas '
                      'Complementarias (art. 24) put it in force. It has not been amended since.',
    }
    decisions = [
        "Constitution: the Legislatura's digital edition of the Constitución de la Provincia de Río Negro (sanctioned in "
        'Viedma on 3 June 1988; Normas Complementarias art. 24: "Esta Constitución regirá a partir del día cuatro de '
        'junio de mil novecientos ochenta y ocho"), shown as enacted, dated 4 June 1988.',
        "Units: the heading (encabezado: the edition's title page, preface and index, the preamble and everything "
        'before Artículo 1) and one file per article. The 26 articles of the Normas Complementarias, numbered again '
        'from 1, are the files art-NNN-dup2. Each file holds the article and everything printed after it up to the next '
        "article (section headings, page numbers, the Convención's closing note). Nothing is dropped. One paragraph "
        'per line, spacing normalised.',
        'Laws are not built in this pass.',
    ]
    source_letters = staticmethod(source_letters_pdf)

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [{'page': PAGE}], 'codigo': [], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': PAGE, 'kind': 'constitucion', 'number': '', 'year': '1988',
                'title': 'Constitución de la Provincia de Río Negro', 'pub': '1988-06-03', 'promul': None,
                'updated': None, 'related_later': [], 'text_url': CONST, 'as_enacted': True}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b or b[:4] != b'%PDF':
            return None
        paras = pdf_paragraphs_ordered(b)
        if not paras or letters(''.join(paras)) != source_letters_pdf(b):
            E.say(f'rio-negro: left out {d["text_url"]} (the two PDF readers disagree)')
            return None
        return paras, b


# ---------------------------------------------------------------- laws (deepening pass, 2026-10-30)
# The Legislatura's "Legislación Provincial" database (web.legisrn.gov.ar/legislativa/legislacion, "producida sobre los
# textos originales sancionados"): a search by sanción date range lists the laws, 100 per page; each record page
# (/legislativa/legislacion/ver?id=N) gives the Estado, sanción, promulgación, publication in the Boletín Oficial,
# "Entrada en vigencia", the norms it affects and "Se encuentra afectada por:" (later norms that changed it); its
# "Texto Promulgado" (/legislativa/legislacion/documento?id=N) is the text as promulgated (PDF, text layer). Only laws
# in force (Normal, Vigente) that no later norm is recorded as affecting are taken, as enacted, dated by the record's
# Entrada en vigencia.

import datetime as _dt
import html as _html
import re as _re

WEB = 'https://web.legisrn.gov.ar'
LIST = (WEB + '/legislativa/legislacion/index?LeySearch%5Btipo%5D=L&LeySearch%5Bfs_desde%5D=01-01-{y}'
        '&LeySearch%5Bfs_hasta%5D=31-12-{y}&page={p}&per-page=100')

_Const = Adapter


class Adapter(_Const):
    source = dict(_Const.source)
    source['notes'] = (_Const.source['notes'] + ' Laws: the Legislatura\'s Legislación Provincial database, which gives '
                       'for each law its record (Estado, sanción, promulgación, publication in the Boletín Oficial, '
                       'Entrada en vigencia, the norms it affects and the later norms that affect it) and its Texto '
                       'Promulgado, the text as promulgated (PDF with a text layer).')
    source['dates_note'] = (_Const.source['dates_note'] + ' Laws are shown as enacted, each dated by the Entrada en '
                            'vigencia its Legislatura record gives; only laws in force that no later norm is recorded '
                            'as affecting are included.')
    decisions = _Const.decisions[:-1] + [
        'Laws: only laws whose Legislatura record says Normal (Vigente) and lists no later norm under "Se encuentra '
        'afectada por", each as its Texto Promulgado (the text as promulgated), dated by the record\'s Entrada en '
        'vigencia; newest first, in parts of about 50.']

    def catalogue(self, n_laws: int) -> dict:
        laws, year = [], _dt.date.today().year
        cutoff = (_dt.date.today() - _dt.timedelta(days=2)).isoformat()
        while len(laws) < n_laws and year >= 1958:
            ids, p = [], 1
            while True:
                b = get(LIST.format(y=year, p=p))
                s = E.decode(b) if b else ''
                found = _re.findall(r'href="/legislativa/legislacion/ver\?id=(\d+)">Ley N\S* (\d+)<', s)
                ids += found
                m = _re.search(r'Mostrando <b>\d+-(\d+)</b> de <b>(\d+)</b>', s)
                if not found or not m or int(m.group(1)) >= int(m.group(2)):
                    break
                p += 1
            for rid, num in sorted(set(ids), key=lambda x: (-int(x[1]), -int(x[0]))):
                if len(laws) >= n_laws:
                    break
                r = self._record(rid)
                if r and r['eligible'] and r['in_force'] <= cutoff:
                    laws.append({'page': f'{WEB}/legislativa/legislacion/ver?id={rid}', 'id': rid, 'number': num})
            year -= 1
        return {'constitucion': [{'page': PAGE}], 'codigo': [], 'ley': laws}

    def _record(self, rid: str) -> dict | None:
        b = get(f'{WEB}/legislativa/legislacion/ver?id={rid}')
        if not b:
            return None
        s = E.decode(b)
        t = _re.sub(r'\s+', ' ', _html.unescape(_re.sub(r'<[^>]+>', ' ', _re.sub(r'(?is)<(script|style)\b.*?</\1>', '', s))))
        num = _re.search(r'/ Ley N\S* (\d+)', t)
        doc = _re.search(r'href="(/legislativa/legislacion/documento\?id=\d+)"', s)
        est = _re.search(r'Estado\s*: ([^()]*)\(\s*([^)]*?)\s*\)', t)

        def day(label):
            m = _re.search(label + r'\s+(?:el|en el Bolet\S+ Oficial del)\s+(\d{2})-(\d{2})-(\d{4})', t)
            return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None
        title = _re.search(r'Imprimir</button></p>\s*<p>(.*?)</p>', s, _re.S)
        r = {'number': num.group(1) if num else None, 'doc': WEB + _html.unescape(doc.group(1)) if doc else None,
             'estado': f'{est.group(1).strip()} ({est.group(2)})' if est else '', 'sancion': day('Sancionada'),
             'promul': day('Promulgada'), 'pub': day('Publicado'), 'vig': day('Entrada en vigencia'),
             'affected': 'Se encuentra afectada por' in s,
             'title': E.clean(_html.unescape(_re.sub(r'<[^>]+>', ' ', title.group(1)))) if title else ''}
        r['in_force'] = r['vig'] or (E._add(r['pub'], E.DEFAULT_DAYS) if r['pub'] else '9999')
        r['eligible'] = bool(r['number'] and r['doc'] and r['pub'] and not r['affected']
                             and r['estado'] == 'Normal (Vigente)')
        return r

    def detail(self, item: dict) -> dict | None:
        if not item.get('id'):
            return _Const.detail(self, item)
        r = self._record(item['id'])
        if not r or not r['eligible']:
            return None
        d = {'page': item['page'], 'kind': 'ley', 'number': r['number'], 'title': r['title'][:400],
             'pub': r['pub'], 'promul': r['promul'], 'updated': None, 'related_later': [], 'text_url': r['doc'],
             'as_enacted': True,
             'note': f"As enacted: the Texto Promulgado of Ley {r['number']} (sanción {r['sancion']}, promulgación "
                     f"{r['promul']}, Boletín Oficial of {r['pub']}); its Legislatura record says {r['estado']} and "
                     f"lists no later norm affecting it."}
        if r['vig']:
            d['in_force'] = (r['vig'], 'the Legislatura record: Entrada en vigencia')
        return d
