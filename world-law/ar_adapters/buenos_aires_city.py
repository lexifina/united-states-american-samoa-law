"""Ciudad Autónoma de Buenos Aires: Normativa BA, the legislation database of the Boletín Oficial de la Ciudad
(boletinoficial.buenosaires.gob.ar/normativaba, Secretaría Legal y Técnica). Private (world-law-ops).

Catalogue: the Constitution (norma 26766) and the laws the city's Digesto Jurídico lists as its most relevant norms
(digesto.buenosaires.gob.ar/buscador/normativaRelevante), each found by a number search (POST) in Normativa BA.
Text: the record's "Texto actualizado" PDF when it has one (current text, dated by its "Fecha de actualización"),
otherwise the record's in-page "Texto original" (as enacted).
"""
from __future__ import annotations

import gzip
import html as htmlmod
import json
import re
import time

from ar_provinces import (CACHE, MIN_PAUSE, Stop, clean, cpath, decode, dmy, get, letters, net, pdf_paragraphs,
                          source_letters_pdf, BLOCK)

BASE = 'https://boletinoficial.buenosaires.gob.ar'
MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
          'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
MODIFY = re.compile(r'MODIFICADA POR|SUSTITUIDA POR|DEROGADA|DEROGADO|PARCIALMENTE|INCORPORA|TEXTO ORDENADO|'
                    r'MODIFICADO POR|ABROGADA|PRORROGADA', re.I)


def _panel(s: str, pid: str) -> str:
    i = s.find(f'id="{pid}"')
    if i < 0:
        return ''
    j = s.find('<div class="panel panel-default"', i)
    return s[i:j if j > 0 else None]


def _pdf_bytes(b: bytes) -> bytes:
    """The texto actualizado endpoint prints PHP warnings before the PDF; both readers skip to %PDF."""
    i = b.find(b'%PDF')
    return b[i:] if i >= 0 else b


class Adapter:
    host = 'boletinoficial.buenosaires.gob.ar'
    source = {
        'name': 'Normativa BA, Boletín Oficial de la Ciudad Autónoma de Buenos Aires (Secretaría Legal y Técnica)',
        'url': 'https://boletinoficial.buenosaires.gob.ar/normativaba',
        'publisher': 'Normativa BA (boletinoficial.buenosaires.gob.ar)',
        'gazette': 'Boletín Oficial de la Ciudad Autónoma de Buenos Aires',
        'notes': 'For each norm: its record (number, sanción, promulgation and publication dates, state, relations: '
                 'the norms that modified, regulated or complemented it), the text as enacted ("Texto original", in '
                 'the record) and, for amended norms, the current text ("Texto actualizado", a PDF with its date of '
                 'update). Earlier consolidated versions are not used here.',
        'dates_note': 'A norm with a "Texto actualizado" is its current text only, the **oldest version available**, '
                      'dated by its "Fecha de actualización"; its earlier wording is not shown. A norm without one is its '
                      '"Texto original", shown as enacted and dated the day it took effect; where its record lists later '
                      'modifying norms, the commit message names them and their changes are not shown.',
    }

    def __init__(self):
        self.ids_path = CACHE / self.host / 'law-ids.json'
        self.ids = json.loads(self.ids_path.read_text(encoding='utf-8')) if self.ids_path.exists() else {}
        self.token = None

    # -- the number search (POST), paced like every other request to the host
    def _post(self, data: dict) -> str:
        n = net()
        with n.lock:
            wait = n.last.get(self.host, 0) + max(n.pause.get(self.host, MIN_PAUSE), 5) - time.time()
            if wait > 0:
                time.sleep(wait)
            n.last[self.host] = time.time()
            n.count[self.host] += 1
            t0 = time.time()
            r = n.s.post(BASE + '/normativaba/resultados', data=data, timeout=90)
            n._note(BASE + '/normativaba/resultados POST ' + json.dumps(data)[:80], r.status_code, len(r.content), t0)
        if r.status_code in (403, 429):
            n.stopped[self.host] = f'HTTP {r.status_code}'
            raise Stop(f'HTTP {r.status_code} on search')
        return r.text

    def _token(self) -> str:
        if not self.token:
            n = net()
            with n.lock:
                wait = n.last.get(self.host, 0) + MIN_PAUSE - time.time()
                if wait > 0:
                    time.sleep(wait)
                n.last[self.host] = time.time()
                r = n.s.get(BASE + '/normativaba', timeout=60)
            m = re.search(r'<input[^>]*buscador\[_token\][^>]*>', r.text)
            self.token = re.search(r'value="([^"]+)"', m.group(0)).group(1)
        return self.token

    def law_id(self, num: str) -> str | None:
        if num in self.ids:
            return self.ids[num]
        try:
            s = self._post({'buscador[id_tipo_norma]': '22', 'buscador[numero]': num,
                            'buscador[_token]': self._token(), 'buscador[busca_en_contenido]': '0'})
        except Stop:
            raise
        except Exception:
            return None
        found = sorted(set(re.findall(r'href="/normativaba/norma/(\d+)"', s)))
        self.ids[num] = found[0] if len(found) == 1 else None
        self.ids_path.parent.mkdir(parents=True, exist_ok=True)
        self.ids_path.write_text(json.dumps(self.ids, indent=0), encoding='utf-8')
        return self.ids[num]

    def catalogue(self, n_laws: int) -> dict:
        b = get('https://digesto.buenosaires.gob.ar/buscador/normativaRelevante')
        s = decode(b) if b else ''
        nums = []
        for m in re.finditer(r'detalleNorma/(?:Ley|LEY)%20N%C2%[BA][A0]%20([\d.]+)"', s):
            k = m.group(1).replace('.', '')
            if k not in nums:
                nums.append(k)
        laws = []
        for k in nums:
            if len(laws) >= n_laws:
                break
            i = self.law_id(k)
            if i:
                laws.append({'page': f'/normativaba/norma/{i}', 'number': k})
        return {'constitucion': [{'page': '/normativaba/norma/26766', 'constitution': True}], 'codigo': [],
                'ley': laws}

    def detail(self, item: dict) -> dict | None:
        url = BASE + item['page']
        b = get(url)
        if not b:
            return None
        s = decode(b)
        t = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<(script|style)\b.*?</\1>', '', s))))
        d = {'page': url}
        if item.get('constitution'):
            d.update(kind='constitucion', number='', title='Constitución de la Ciudad Autónoma de Buenos Aires')
            d.update(as_enacted=True,
                     in_force=('1996-10-01', 'its own clause, art. 140: "A partir de la sanción de esta Constitución, '
                                             'quedan derogadas todas las normas que se le opongan"; sancionada 1 October 1996'),
                     note='The Constitution as sanctioned by the Convención Constituyente on 1 October 1996 (published in '
                          'the Boletín Oficial on 10 October 1996), with the corrections of the Fe de Erratas approved by '
                          'Ley 1 (1997) incorporated, as the source prints it. It has not been amended since.')
        else:
            d.update(kind='ley', number=item['number'])
            m = re.search(r'S[ií]ntesis: (.*?) Publicaci[oó]n:', t)
            d['title'] = (m.group(1).strip() if m else '')[:400]
        d['pub'] = dmy((re.search(r'Publicaci[oó]n: (\S+)', t) or [None, ''])[1])
        d['promul'] = dmy((re.search(r'Promulgaci[oó]n: (\S+)', t) or [None, ''])[1]) or \
            dmy((re.search(r'Sanci[oó]n: (\S+)', t) or [None, ''])[1])
        estado = (re.search(r'Estado: (\S+(?: vigente)?)', t) or [None, ''])[1]
        if estado.lower().startswith('no'):
            return None
        rel = _panel(s, 'collapseThree')
        rel_t = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', rel)))
        d['related_later'] = [m.group(0) for m in re.finditer(
            r'(MODIFICADA POR|SUSTITUIDA POR|DEROGADA PARCIALMENTE POR|DEROGADA POR|INCORPORADA POR)\s+\S+(?:\s+\S+){0,3}?\s+\d+\s+\d{4}', rel_t)]
        ta = _panel(s, 'collapseFour')
        m = re.search(r'(?:src|href)="(https://boletinoficialpdf\.buenosaires\.gob\.ar/util/imagen\.php\?idn=\d+&amp;idf=\d+)"', ta)
        if m:
            d['text_url'] = htmlmod.unescape(m.group(1))
            ft = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', ta)))
            mm = re.search(r'Fecha de actualizaci[oó]n: (\d{1,2}) de (\w+) de (\d{4})', ft, re.I)
            if mm and mm.group(2).lower() in MONTHS:
                d['updated'] = f'{int(mm.group(3)):04d}-{MONTHS[mm.group(2).lower()]:02d}-{int(mm.group(1)):02d}'
            d['is_pdf'] = True
            if not d.get('updated'):
                return None          # a current text without its date cannot be dated
            if not d['related_later']:
                d['related_later'] = ['texto actualizado']
        else:
            if not _panel(s, 'collapseFive'):
                return None
            d['text_url'] = url + '#texto-original'
            d['updated'] = None
            if d['related_later'] and d['kind'] != 'constitucion':
                # only the text as enacted is published: shown as enacted, the later changes are not applied
                d['as_enacted'] = True
                d['note'] = ('As enacted (the "Texto original" of its record; the source publishes no updated text for it). '
                             'Later norms recorded as changing it, whose changes are not shown: '
                             + '; '.join(d['related_later'][:10]) + ('; …' if len(d['related_later']) > 10 else '') + '.')
        return d

    def text(self, d: dict):
        b = get(d['text_url'])
        if not b:
            return None
        if d.get('is_pdf'):
            if b'%PDF' not in b[:4000]:
                return None
            return pdf_paragraphs(_pdf_bytes(b)), b
        return original_paragraphs(b), b

    @staticmethod
    def source_letters(b: bytes) -> str:
        if b'%PDF' in b[:4000]:
            return source_letters_pdf(_pdf_bytes(b))
        import lxml.html
        doc = lxml.html.document_fromstring(decode(b))
        el = doc.get_element_by_id('collapseFive')
        for bad in el.xpath('.//script|.//style'):
            bad.drop_tree()
        return letters(el.text_content())


def original_paragraphs(b: bytes) -> list[str]:
    s = _panel(decode(b), 'collapseFive')
    s = s[s.find('>') + 1:]
    s = re.sub(r'(?s)<!--.*?-->', '', s)
    s = re.sub(r'(?is)<(script|style)\b.*?</\1\s*>', '', s)
    s = re.sub(r'[\r\n]+', ' ', s)
    s = BLOCK.sub('\x00', s)
    s = htmlmod.unescape(re.sub(r'<[^>]+>', '', s))
    return [c for c in (clean(x) for x in s.split('\x00')) if c]
