"""Provincia de Santa Cruz (gitlaw-scraper-dell, lane 3, 2026-10-30): the Dirección General Boletín Oficial e Imprenta
(boletinoficial.santacruz.gob.ar; robots.txt "User-agent: *" disallows only the Joomla system folders; no challenge;
footer "© 2022 Dirección General Boletín Oficial - Gobierno de la Provincia de Santa Cruz", no terms for the texts).

Laws: the Boletín's "Legislación / Leyes" section (Joomla K2, category 178) has one item per law as published in the
Boletín Oficial: its header gives the publication day and the Boletín number ("publicado el 08 Octubre 2026 / BO
6164"), and its full text is the law as sanctioned followed by the promulgation decree (with any partial veto), as
published. Items are found through the section's month archive (/legislacion/leyes/date/YYYY/M?catid=178), newest
month first. Each law is shown as published (as enacted) and dated by the in-force rule.

Constitution: the government portal (www.santacruz.gob.ar/constitucion-provincial) carries the 1998 text (sanctioned
1957, reformed 1994 and 1998; Disposición transitoria primera: "La presente Constitución entrará en vigencia a partir
de la fecha de su publicación"), but its publication day (late 1998) is not available: the Boletín's online archive
starts in 1999 and no official record of the day was found. Not built until that day can be stated.
"""
from __future__ import annotations

import datetime as _dt
import re

from ar_provinces import clean, decode, get, letters, BLOCK
import html as htmlmod

BASE = 'https://boletinoficial.santacruz.gob.ar'
MONTH = BASE + '/legislacion/leyes/date/{y}/{m}?catid=178'
MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
         'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
START = '<div class="itemFullText">'
END = '<!-- Adjuntos -->'


def _body(s: str) -> str | None:
    i = s.find(START)
    j = s.find(END, i)
    if i < 0 or j < 0:
        return None
    return s[i + len(START):j]


class Adapter:
    host = 'boletinoficial.santacruz.gob.ar'
    original_only = True
    source = {
        'name': 'Boletín Oficial de la Provincia de Santa Cruz (Dirección General Boletín Oficial e Imprenta, '
                'boletinoficial.santacruz.gob.ar)',
        'url': BASE + '/legislacion/leyes',
        'publisher': 'Dirección General Boletín Oficial e Imprenta de la Provincia de Santa Cruz',
        'gazette': 'Boletín Oficial de la Provincia de Santa Cruz',
        'notes': 'The Boletín Oficial publishes each law as an item of its "Legislación / Leyes" section, with the day '
                 'and number of the Boletín it appeared in, the text as sanctioned and the promulgation decree. The '
                 'site states no terms of use for the texts.',
    }
    decisions = [
        'Laws are the Boletín Oficial\'s own items, each the text of the law as published (as enacted) followed by its '
        'promulgation decree as printed (including any partial veto). Each is dated the day it took effect: its own '
        'vigencia clause, else the ninth day after its publication in the Boletín Oficial. Later amendments are not '
        'shown (the Boletín publishes each amending law as its own item).',
        'Units: the heading (encabezado: the law\'s number, enacting formula and title) and one file per article, holding '
        'the article and everything printed after it up to the next article; after the law\'s last article, the '
        'promulgation decree follows, whose own articles are files "Artículo N (2)". Nothing is dropped. One paragraph '
        'per block element, spacing normalised.',
        'No constitution yet: the 1998 text is on the government portal, but the day of its publication in the '
        'Boletín Oficial (its in-force day under its Disposición transitoria primera) is not available from an '
        'official source.',
    ]
    dates_note = ('Each law is shown as published in the Boletín Oficial (as enacted), dated the day it took effect.')

    def catalogue(self, n_laws: int) -> dict:
        laws, seen = [], set()
        today = _dt.date.today()
        y, m = today.year, today.month
        recent = (today - _dt.timedelta(days=12)).isoformat()
        empty = 0
        while len(laws) < n_laws and empty < 24 and y >= 1999:
            b = get(MONTH.format(y=y, m=m))
            s = decode(b) if b else ''
            ids = re.findall(r'href="/legislacion/leyes/(\d+)"', s)
            if not ids:
                empty += 1
            else:
                empty = 0
            for i in sorted(set(ids), key=int, reverse=True):
                if i in seen:
                    continue
                seen.add(i)
                laws.append({'page': f'{BASE}/legislacion/leyes/{i}', 'id': i, 'recent': recent})
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        return {'constitucion': [], 'codigo': [], 'ley': laws[:n_laws + 40]}

    def detail(self, item: dict) -> dict | None:
        b = get(item['page'])
        if not b:
            return None
        s = decode(b)
        if _body(s) is None:
            return None
        head = re.search(r'<div class="itemHeader">(.*?)</div>', s, re.S)
        ht = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', head.group(1)))) if head else ''
        mm = re.search(r'publicado el\s+(\d{1,2})\s+(\w+)\s+(\d{4})', ht, re.I)
        if not mm or mm.group(2).lower() not in MESES:
            return None
        pub = f'{int(mm.group(3)):04d}-{MESES[mm.group(2).lower()]:02d}-{int(mm.group(1)):02d}'
        if pub > item.get('recent', '9999'):
            return None                                   # not yet in force (pub + 9 after today)
        bo = (re.search(r'BO\s+(\d+)', ht) or [None, ''])[1]
        t = re.search(r'<h2 class="itemTitle">(.*?)</h2>', s, re.S)
        tt = clean(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', t.group(1)))) if t else ''
        num = re.search(r'LEY\s+N\S*\s*([\d.]+)', tt, re.I)
        if not num:
            return None
        intro = re.search(r'<div class="itemIntroText">(.*?)</div>', s, re.S)
        title = clean(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', intro.group(1)))) if intro else ''
        return {'page': item['page'], 'kind': 'ley', 'number': num.group(1).replace('.', ''), 'title': title[:400],
                'pub': pub, 'promul': None, 'updated': None, 'related_later': [], 'text_url': item['page'],
                'note': f'As published in the Boletín Oficial N.º {bo} of {pub}.'}

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b:
            return None
        body = _body(decode(b))
        if body is None:
            return None
        return body_paragraphs(body), b

    @staticmethod
    def source_letters(b: bytes) -> str:
        import lxml.html
        doc = lxml.html.document_fromstring(decode(b))
        el = doc.xpath('//div[@class="itemFullText"]')[0]
        for bad in el.xpath('.//script|.//style'):
            bad.drop_tree()
        return letters(el.text_content())


def body_paragraphs(s: str) -> list[str]:
    s = re.sub(r'(?s)<!--.*?-->', '', s)
    s = re.sub(r'(?is)<(script|style)\b.*?</\1\s*>', '', s)
    s = re.sub(r'[\r\n]+', ' ', s)
    s = BLOCK.sub('\x00', s)
    s = htmlmod.unescape(re.sub(r'<[^>]+>', '', s))
    return [c for c in (clean(x) for x in s.split('\x00')) if c]
