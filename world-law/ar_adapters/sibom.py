"""Municipal ordinances of a Buenos Aires province partido from SIBOM (gitlaw-scraper-dell, 2026-10-31).

SIBOM, the Sistema de Boletines Oficiales Municipales (sibom.slyt.gba.gob.ar), is the Province of Buenos Aires'
platform on which each municipality makes its Boletín Oficial Municipal (Ley 14.491, which replaced art. 108 inc. 2 and
added inc. 18 of the Ley Orgánica de las Municipalidades, Decreto-Ley 6769/58), run by the Subsecretaría Legal y
Técnica, Secretaría General. robots.txt has no rules; the site states no terms restricting reuse ("Publicidad de los
actos de gobierno con plena eficacia jurídica", /about).

Catalogue: the city's bulletin list (/cities/<id>?page=N, newest first), then each bulletin's page, whose "Ordenanzas"
panel links every ordinance it published (number and the date line "City, dd/mm/yyyy"). Text: the ordinance's own
page (/bulletins/<b>/contents/<c>), the column holding the published text (HTML). The text is the ordinance as
published in the bulletin, so it is shown as enacted, dated on the day it took effect.
"""
from __future__ import annotations

import re

import ar_provinces as E

BASE = 'https://sibom.slyt.gba.gob.ar'
COL = re.compile(r'(?s)<div class="col-md-9">(.*?)</div><div class="col-md-3">')


def _date(s: str) -> str | None:
    return E.dmy(s)


def make(city_id: int, city: str, partido: str, search: bool = False):
    class Adapter:
        host = 'sibom.slyt.gba.gob.ar'
        original_only = True
        search_mode = search
        source = {
            'name': f'Sistema de Boletines Oficiales Municipales (SIBOM), Subsecretaría Legal y Técnica, Secretaría '
                    f'General, Provincia de Buenos Aires: Boletín Oficial Municipal de {partido}',
            'url': f'{BASE}/cities/{city_id}',
            'publisher': f'Boletín Oficial Municipal de {partido} (SIBOM)',
            'gazette': f'Boletín Oficial Municipal de {partido}',
            'notes': f'SIBOM is the platform on which each municipality of the Province of Buenos Aires makes its '
                     f'Boletín Oficial Municipal (Ley 14.491). For each bulletin it lists the ordinances it published; '
                     f'each ordinance has its own page with the text as published (HTML). The site states no terms '
                     f'restricting reuse.',
        }

        @staticmethod
        def source_letters(b: bytes) -> str:
            import lxml.html
            doc = lxml.html.document_fromstring(E.decode(b))
            col = doc.xpath('//div[@class="col-md-9"]')
            if len(col) != 1:
                return ''
            for bad in col[0].xpath('.//script|.//style'):
                bad.drop_tree()
            return E.letters(col[0].text_content())

        def catalogue(self, n_laws: int) -> dict:
            if search:
                return self.catalogue_search(n_laws)
            laws, seen, page = [], set(), 1
            while len(laws) < n_laws:
                s = E.decode(E.get(f'{BASE}/cities/{city_id}' + (f'?page={page}' if page > 1 else '')) or b'')
                bl = re.findall(r'<p class="bulletin-title">([^<]*)</p><p class="bulletin-date">Publicado el '
                                r'([0-9/]+)</p></div><div class="col-xs-4"><form class="button_to" method="get" '
                                r'action="/bulletins/(\d+)"', s)
                if not bl or (page >= 12 and not laws):
                    break
                for title, pub, bid in bl:
                    b = E.decode(E.get(f'{BASE}/bulletins/{bid}') or b'')
                    for href, num, line in re.findall(
                            r'<a class="content-link" href="(/bulletins/\d+/contents/\d+)"><div class="white-box '
                            r'ordinance"><p>Ordenanza N[º°o]?\s*([^<]*)</p><p class="city-and-date">([^<]*)</p>', b):
                        if href in seen:
                            continue
                        seen.add(href)
                        laws.append({'page': BASE + href, 'number': E.clean(num).replace('.', ''),
                                     'pub': _date(pub), 'promul': _date(line), 'bulletin': E.clean(title)})
                    if len(laws) >= n_laws:
                        break
                page += 1
            return {'constitucion': [], 'codigo': [], 'ley': laws[:n_laws]}

        def catalogue_search(self, n_laws: int) -> dict:
            # SIBOM's own ordinance search for the city (10 a page, roughly oldest first): read from the last page
            # back until n_laws are found, then newest first by publication date and number
            q = f'q%5Bterms%5D%5Bbulletin.city_id%5D={city_id}&q%5Bterms%5D%5Btype%5D=Ordinance'
            first = E.decode(E.get(f'{BASE}/advanced_search?{q}') or b'')
            pages = [int(x) for x in re.findall(r'advanced_search\?page=(\d+)&', first.replace('&amp;', '&'))]
            last = max(pages or [1])
            laws, seen = [], set()
            for page in range(last, 0, -1):
                s = first if page == 1 else E.decode(E.get(f'{BASE}/advanced_search?page={page}&{q}') or b'')
                for href, num, title, pub in re.findall(
                        r'content-title"><a href="(/bulletins/\d+/contents/\d+)">Ordenanza N[º°o]?\s*([^<\s]*)'
                        r'( en el bolet[íi]n [^<]*)</a></p></div><div class="col-md-1"></div></div><div><span '
                        r'class="text-muted">([0-9/]+)', s):
                    if href in seen:
                        continue
                    seen.add(href)
                    laws.append({'page': BASE + href, 'number': num.replace('.', ''), 'pub': _date(pub),
                                 'promul': None, 'bulletin': E.clean(title)})
                if len(laws) >= n_laws:
                    break
            laws.sort(key=lambda x: (x['pub'] or '', int(re.sub(r'\D', '', x['number']) or 0)), reverse=True)
            return {'constitucion': [], 'codigo': [], 'ley': laws[:n_laws]}

        def detail(self, item: dict) -> dict | None:
            num = re.sub(r'\s+', '', item['number'])
            m = re.match(r'(\d+)(?:/(\d{2,4}))?$', num)
            if not m or not item.get('pub'):
                return None
            year = (item.get('promul') or item['pub'])[:4]
            return {'page': item['page'], 'text_url': item['page'], 'kind': 'ordenanza', 'number': m.group(1),
                    'year': year, 'pub': item['pub'], 'promul': item.get('promul'), 'updated': None,
                    'related_later': [], 'as_enacted': True, 'bulletin': item.get('bulletin'),
                    'title': f'Ordenanza {m.group(1)}'}

        def text(self, d: dict):
            b = E.get(d['text_url'])
            if not b:
                return None
            s = E.decode(b)
            if len(COL.findall(s)) != 1:
                return None
            if re.search(r'<p class="extracted-version-disclaimer">\s*[^<\s]', s):
                return None       # an extract, not the whole text
            if not d.get('promul'):
                m = re.search(r'<p class="city-and-date">([^<]*)</p>', s)
                d['promul'] = _date(m.group(1)) if m else None
            paras = E.html_paragraphs(COL.search(s).group(1).encode('utf-8'))
            if not paras or not any(E.article_id(p) for p in paras):
                return None
            # title: the heading plus the start of the first article
            a1 = next((p for p in paras if E.article_id(p)), '')
            a1 = re.sub(r'^\s*ART[IÍ]CULO\s*\S+\s*[:.\-–]*\s*', '', a1, flags=re.I)
            d['title'] = a1[:220]
            d['in_force'] = in_force(paras, d['pub'], d.get('promul'))
            return paras, b
    return Adapter


def in_force(paras: list[str], pub: str, promul: str | None):
    """The ordinance's own vigencia clause (as the provincial engine reads one, with ORDENANZA for LEY), else the ninth
    day after publication in the Boletín Oficial Municipal (Código Civil y Comercial, arts. 5 and 6)."""
    p2 = [re.sub(r'ORDENANZA', 'LEY', x, flags=re.I) for x in paras]
    f, basis = E.in_force(p2, pub, promul)
    return f, basis.replace('default rule: the ninth day after publication',
                            'default rule: the ninth day after publication in the Boletín Oficial Municipal')
