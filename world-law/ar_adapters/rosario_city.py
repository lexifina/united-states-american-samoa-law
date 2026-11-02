"""Municipalidad de Rosario (gitlaw-scraper-dell, 2026-10-31): the consolidated texts the municipality publishes in its
"Normativa" site (www.rosario.gob.ar/mr/normativa, a Plone site; robots.txt disallows only /serviciosti/, /lihat/,
/form/). Terms (rosario.gob.ar Términos y condiciones, Decreto 2098/2021 Anexo II): published content may be used,
reproduced and modified with reference to the Creative Commons 4.0 licence.

Each code is one page whose text block (#parent-fieldname-text) is the consolidated text (texto actualizado), with
notes such as "(Inciso modificado por el Art. 1° de la Ordenanza N° 9808/17)" linking each amending norm's record in
the municipality's norm register (www.rosario.gob.ar/normativa/ver/visualExterna.do?accion=verNormativa&idNormativa=N,
which gives the Boletín Oficial number and "Publicado el" date). Earlier consolidated versions are not published. Each
text is shown as its current consolidated text only, the oldest version available, dated the in-force day (ninth day
after publication, Código Civil y Comercial arts. 5 and 6) of the latest amending norm its notes link, read from that
norm's own record.
"""
from __future__ import annotations

import re

import ar_provinces as E

B = 'https://www.rosario.gob.ar/mr/normativa/'
REC = 'https://www.rosario.gob.ar/normativa/ver/visualExterna.do?accion=verNormativa&idNormativa='
TEXT = re.compile(r'(?s)<div class="" id="parent-fieldname-text">(.*?)</div>\s*<div class="relatedItems">')
PAGES = [
    ('autonomia-municipal/ordenanza-nb0-10850-2025', 'ordenanza', '10850', '2025', 'Autonomía municipal'),
    ('codigo-de-convivencia-ciudadana/ordenanza-no-10267-2021', 'ordenanza', '10267', '2021', 'Código de Convivencia Ciudadana'),
    ('codigo-de-transito/ordenanza-no-6543-1998', 'ordenanza', '6543', '1998', 'Código de Tránsito'),
    ('codigo-tributario/decreto-ordenanza-9476-1978', 'decreto-ordenanza', '9476', '1978', 'Código Tributario Municipal'),
    ('estatuto-y-escalafon-del-personal-municipal/ordenanza-no-3574-1984-1', 'ordenanza', '3574', '1984',
     'Estatuto y Escalafón del Personal Municipal'),
    ('ordenanza-de-contabilidad/decreto-ordenanza-no-19975-1957', 'decreto-ordenanza', '19975', '1957', 'Ordenanza de Contabilidad'),
    ('ordenanza-impositiva/ordenanza-4064-1986', 'ordenanza', '4064', '1986', 'Ordenanza General Impositiva'),
    ('reglamento-de-compras/decreto-no-438-1998', 'decreto', '438', '1998', 'Reglamento de Compras'),
]


def _year(y: str) -> int:
    y = int(y)
    return y + 2000 if y < 30 else (y + 1900 if y < 100 else y)


def record(idn: str) -> dict | None:
    s = E.decode(E.get(REC + idn) or b'')
    if not s:
        return None
    t = re.sub(r'\s+', ' ', E.htmlmod.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<(script|style)\b.*?</\1>', '', s))))
    head = re.search(r'(Ordenanza|Decreto - Ordenanza|Decreto Concejo Municipal|Decreto|Resolución[^N]*)\s*N[º°]\s*([\d.]+)\s*/\s*(\d{4})', t)
    pub = re.search(r'Publicado el (\d{1,2}/\d{1,2}/\d{4})', t)
    return {'id': idn, 'label': f'{head.group(1)} {head.group(2)}/{head.group(3)}' if head else f'norm {idn}',
            'pub': E.dmy(pub.group(1)) if pub else None}


class Adapter:
    host = 'www.rosario.gob.ar'
    source = {
        'name': 'Municipalidad de Rosario, Normativa (www.rosario.gob.ar/mr/normativa) and its register of norms '
                '(www.rosario.gob.ar/normativa)',
        'url': 'https://www.rosario.gob.ar/mr/normativa',
        'publisher': 'Municipalidad de Rosario, Normativa',
        'gazette': 'Boletín Oficial Municipal Electrónico de Rosario (B.O.M.E.)',
        'notes': 'The municipality publishes the consolidated text (texto actualizado) of its main codes and ordinances, '
                 'with notes naming and linking the norm that made each change; its register of norms gives each norm\'s '
                 'Boletín Oficial number and publication date. Earlier consolidated versions are not published.',
    }
    terms = ('The municipality\'s terms of use (Términos y condiciones, Decreto 2098/2021, Anexo II) say its published '
             'content may be used, reproduced and modified with reference to the Creative Commons 4.0 licence.')
    level_note = ('Rosario has no carta orgánica yet (its first is to be drafted by a convention elected under '
                  'Ordenanza 10.850/2025 on municipal autonomy); its organic law is the Province of Santa Fe\'s Ley '
                  'Orgánica de Municipalidades, Ley 2756, which is provincial law and not included here. The autonomy '
                  'ordinance comes first.')
    current_texts = True
    default_rule = ('An ordinance takes effect on the day its own vigencia clause names; otherwise, as for any general norm, '
                    'under Código Civil y Comercial de la Nación, art. 5 ("Las leyes rigen después del octavo día de su '
                    'publicación oficial, o desde el día que ellas determinen"), counted under art. 6 (the day of '
                    'publication excluded): the ninth day after its publication in the Boletín Oficial Municipal.')
    default_rule_source = 'https://servicios.infoleg.gob.ar/infolegInternet/anexos/235000-239999/235975/texact.htm'
    decisions = [
        'Source: the consolidated texts (texto actualizado) the Municipalidad de Rosario publishes at '
        'www.rosario.gob.ar/mr/normativa. Earlier consolidated versions are not published, so each norm is shown as its '
        'current text only, the oldest version available.',
        'Date of each text: its notes link the norms that amended it to their records in the municipality\'s register of '
        'norms. The records of the latest-year norms linked (at most four) are read for their Boletín Oficial publication '
        'date; the text is dated the in-force day of the latest of them, the ninth day after its publication (Código Civil '
        'y Comercial, arts. 5 and 6). Where a note\'s link points to a different record than the norm it names, the '
        'record the link points to is used.',
        'Rosario has no carta orgánica yet; the autonomy ordinance (Ordenanza 10.850/2025) comes first, then the codes. '
        'The provincial Ley Orgánica de Municipalidades (Ley 2756) is provincial law and not included.',
        'Units: the heading (encabezado: everything before the first Artículo) and one file per article, holding the '
        'article and everything printed after it up to the next article (section headings, amendment notes, annexes). '
        'Where an approving ordinance\'s articles and the code\'s own articles share a number, the later ones are kept '
        'as separate files (-dup2). Nothing is dropped. One paragraph per line, spacing normalised.',
    ]
    holds = 'its main codes and ordinances, each as its current consolidated text'
    dates_note = ('The source publishes only today\'s consolidated text of each norm. Each is shown as its current text '
                  'only, the **oldest version available**, dated the day the latest amending norm linked in its notes took '
                  'effect (the ninth day after that norm\'s publication in the Boletín Oficial, as its record gives it); '
                  'its earlier wording is not shown.')

    @staticmethod
    def source_letters(b: bytes) -> str:
        import lxml.html
        doc = lxml.html.document_fromstring(E.decode(b))
        col = doc.xpath('//div[@id="parent-fieldname-text"]')
        if len(col) != 1:
            return ''
        for bad in col[0].xpath('.//script|.//style'):
            bad.drop_tree()
        return E.letters(col[0].text_content())

    def catalogue(self, n_laws: int) -> dict:
        return {'constitucion': [], 'codigo': [{'page': B + p, 'kind': k, 'number': n, 'year': y, 'name': nm}
                                               for p, k, n, y, nm in PAGES], 'ley': []}

    def detail(self, item: dict) -> dict | None:
        return {'page': item['page'], 'text_url': item['page'], 'kind': item['kind'], 'number': item['number'],
                'year': item['year'], 'title': item['name'], 'pub': None, 'promul': None, 'updated': None,
                'related_later': []}

    def text(self, d: dict):
        b = E.get(d['text_url'])
        if not b:
            return None
        s = E.decode(b)
        m = TEXT.findall(s)
        if len(m) != 1:
            return None
        paras = E.html_paragraphs(m[0].encode('utf-8'))
        # the amending norms its notes link, latest cited year first; read their records (at most 4) for the dates
        cited = []
        for idn, txt in re.findall(r'idNormativa=(\d+)"?[^>]*>([^<]{0,200})', m[0]):
            mm = re.search(r'N[°º]\s*([\d.]+)\s*/\s*(\d{2,4})', E.htmlmod.unescape(txt))
            if mm:
                cited.append((_year(mm.group(2)), int(mm.group(1).replace('.', '')), idn))
        if not cited:
            return None
        top = max(c[0] for c in cited)
        ids = []
        for y, n, idn in sorted(cited, reverse=True):
            if y == top and idn not in ids:
                ids.append(idn)
        recs = [r for r in (record(i) for i in ids[:4]) if r and r.get('pub')]
        if not recs:
            return None
        last = max(recs, key=lambda r: r['pub'])
        day = E._add(last['pub'], E.DEFAULT_DAYS)
        d['updated'] = day
        d['related_later'] = [r['label'] for r in recs]
        d['as_of_note'] = (f'Oldest version available: the consolidated text (texto actualizado) as the source holds it. '
                           f'Its notes link amending norms up to {last["label"]} (Boletín Oficial, published '
                           f'{last["pub"]}; in force {day}, the ninth day after publication), so it is dated that day. '
                           f'Earlier consolidated versions are not published by the source.')
        return paras, b
