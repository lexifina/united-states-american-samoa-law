"""Argentine provinces and the Autonomous City of Buenos Aires for git-for-law (gitlaw-scraper-dell, coverage wave
2026-10-30): one public repo per unit, lexifina/argentina-<province>-law, built by scripts/gitlaw_common/build.py from
corpus.d parts (constitution first, then codes, then laws in parts of about 50).

Each province is read from its own official legislation portal (an adapter per host below). SAIJ is not used: its
Reglamento de uso (Res. MJyDH 1427/2011) restricts downloads to personal use and bars reproduction (HOLD, see
FETCH-PERMISSION-EMAILS.md). One process; one request at a time per host, at least 3.2 s apart (more when robots.txt
sets a Crawl-delay); stops a host on any challenge, 403 or 429.

    python -X utf8 scripts/world-law/ar_provinces.py run <slug> [--max-parts=N]   # claim, scaffold, fetch, verify, publish
    python -X utf8 scripts/world-law/ar_provinces.py letters <slug> <part>
    python -X utf8 scripts/world-law/ar_provinces.py publish <slug> <part> <docs-date>

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import html as htmlmod
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # scripts/
DOCS = ROOT.parent.parent                           # ~/Documents
HERE = Path(__file__).resolve().parent
CACHE = HERE / '.ar-cache'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
PART_SIZE = 50
SESSION = 'gitlaw-scraper-dell'
CLAIMS = HERE / 'claims'
MIN_PAUSE = 3.2

# slug: (English name, official name, ISO 3166-2, tz)
PROVINCES = {
    'buenos-aires': ('Buenos Aires', 'Provincia de Buenos Aires', 'AR-B', 'America/Argentina/Buenos_Aires'),
    'cordoba': ('Córdoba', 'Provincia de Córdoba', 'AR-X', 'America/Argentina/Cordoba'),
    'santa-fe': ('Santa Fe', 'Provincia de Santa Fe', 'AR-S', 'America/Argentina/Cordoba'),
    'buenos-aires-city': ('Buenos Aires City', 'Ciudad Autónoma de Buenos Aires', 'AR-C', 'America/Argentina/Buenos_Aires'),
    'mendoza': ('Mendoza', 'Provincia de Mendoza', 'AR-M', 'America/Argentina/Mendoza'),
    'tucuman': ('Tucumán', 'Provincia de Tucumán', 'AR-T', 'America/Argentina/Tucuman'),
    'entre-rios': ('Entre Ríos', 'Provincia de Entre Ríos', 'AR-E', 'America/Argentina/Cordoba'),
    'salta': ('Salta', 'Provincia de Salta', 'AR-A', 'America/Argentina/Salta'),
    'misiones': ('Misiones', 'Provincia de Misiones', 'AR-N', 'America/Argentina/Cordoba'),
    'chaco': ('Chaco', 'Provincia del Chaco', 'AR-H', 'America/Argentina/Cordoba'),
    'corrientes': ('Corrientes', 'Provincia de Corrientes', 'AR-W', 'America/Argentina/Cordoba'),
    'santiago-del-estero': ('Santiago del Estero', 'Provincia de Santiago del Estero', 'AR-G', 'America/Argentina/Cordoba'),
    'san-juan': ('San Juan', 'Provincia de San Juan', 'AR-J', 'America/Argentina/San_Juan'),
    'jujuy': ('Jujuy', 'Provincia de Jujuy', 'AR-Y', 'America/Argentina/Jujuy'),
    'rio-negro': ('Río Negro', 'Provincia de Río Negro', 'AR-R', 'America/Argentina/Salta'),
    'neuquen': ('Neuquén', 'Provincia del Neuquén', 'AR-Q', 'America/Argentina/Salta'),
    'formosa': ('Formosa', 'Provincia de Formosa', 'AR-P', 'America/Argentina/Cordoba'),
    'chubut': ('Chubut', 'Provincia del Chubut', 'AR-U', 'America/Argentina/Catamarca'),
    'san-luis': ('San Luis', 'Provincia de San Luis', 'AR-D', 'America/Argentina/San_Luis'),
    'catamarca': ('Catamarca', 'Provincia de Catamarca', 'AR-K', 'America/Argentina/Catamarca'),
    'la-rioja': ('La Rioja', 'Provincia de La Rioja', 'AR-F', 'America/Argentina/La_Rioja'),
    'la-pampa': ('La Pampa', 'Provincia de La Pampa', 'AR-L', 'America/Argentina/Salta'),
    'santa-cruz': ('Santa Cruz', 'Provincia de Santa Cruz', 'AR-Z', 'America/Argentina/Rio_Gallegos'),
    'tierra-del-fuego': ('Tierra del Fuego', 'Provincia de Tierra del Fuego, Antártida e Islas del Atlántico Sur', 'AR-V',
                         'America/Argentina/Ushuaia'),
}


def repo_name(slug: str) -> str:
    return f'argentina-{slug}-law'


def folder(slug: str) -> Path:
    return ROOT / repo_name(slug)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---------------------------------------------------------------- fetching (one process; one request at a time per host)

class Stop(Exception):
    pass


class Net:
    def __init__(self):
        import requests
        self.requests = requests
        self.s = requests.Session()
        self.s.headers['User-Agent'] = UA
        self.s.headers['Accept-Encoding'] = 'gzip'
        self.last: dict[str, float] = {}
        self.pause: dict[str, float] = {}
        self.stopped: dict[str, str] = {}
        self.count: Counter = Counter()
        self.lock = threading.Lock()
        self.log = HERE / 'logs' / 'ar-provinces-requests.jsonl'
        self.log.parent.mkdir(exist_ok=True)

    def get(self, url: str) -> 'requests.Response':
        host = url.split('/')[2]
        if host in self.stopped:
            raise Stop(f'{host} stopped: {self.stopped[host]}')
        with self.lock:
            for attempt in range(3):
                wait = self.last.get(host, 0) + self.pause.get(host, MIN_PAUSE) - time.time()
                if wait > 0:
                    time.sleep(wait)
                self.last[host] = time.time()
                self.count[host] += 1
                t0 = time.time()
                try:
                    r = self.s.get(url, timeout=120)
                except self.requests.RequestException as e:
                    self._note(url, 0, 0, t0, str(e)[:120])
                    if attempt == 2:
                        raise
                    time.sleep(20 * (attempt + 1))
                    continue
                self._note(url, r.status_code, len(r.content), t0)
                head = r.content[:6000].lower()
                if (b'just a moment' in head and b'cloudflare' in head) or b'cf-chl' in head or \
                        b'incapsula incident' in head or b'request unsuccessful' in head or b'captcha' in head:
                    self.stopped[host] = 'bot challenge'
                    raise Stop(f'bot challenge at {url}: host stopped (never get round one)')
                if r.status_code in (403, 429):
                    self.stopped[host] = f'HTTP {r.status_code}'
                    raise Stop(f'HTTP {r.status_code} at {url}: host stopped')
                if r.status_code >= 500 and attempt < 2:
                    time.sleep(30 * (attempt + 1))
                    continue
                return r
            return r

    def _note(self, url, status, size, t0, err=''):
        with open(self.log, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': now(), 'status': status, 'bytes': size, 'secs': round(time.time() - t0, 2),
                                'url': url[:300], **({'err': err} if err else {})}) + '\n')


NET: Net | None = None


def net() -> Net:
    global NET
    if NET is None:
        NET = Net()
    return NET


def cpath(url: str) -> Path:
    host = url.split('/')[2]
    return CACHE / host / (hashlib.sha256(url.encode()).hexdigest()[:40] + '.gz')


def cached(url: str) -> bytes | None:
    p = cpath(url)
    if p.exists():
        return gzip.decompress(p.read_bytes()) or None
    return None


def get(url: str, refresh: bool = False) -> bytes | None:
    """GET once; the body (b'' for an error answer) is cached gzipped. None for an error answer."""
    p = cpath(url)
    if p.exists() and not refresh:
        return gzip.decompress(p.read_bytes()) or None
    r = net().get(url)
    b = r.content if r.status_code == 200 else b''
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(b, 6, mtime=0))
    os.replace(tmp, p)
    return b or None


# ---------------------------------------------------------------- text

def fold(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()


def ascii_slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', fold(s).lower()).strip('-')


def decode(b: bytes) -> str:
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('cp1252', 'replace')


BLOCK = re.compile(r'<\s*(?:p|div|br|h[1-6]|tr|li|td|th|table|blockquote|pre|center)\b[^>]*>|<\s*/\s*(?:p|div|h[1-6]|tr|li|td|th|table|blockquote|pre|center)\s*>', re.I)
SPACE = re.compile(r'[ \t\r\n    ​﻿]+')


def clean(s: str) -> str:
    return SPACE.sub(' ', unicodedata.normalize('NFC', s).replace('­', '')).strip()


def html_paragraphs(b: bytes) -> list[str]:
    """Body of an HTML document -> its paragraphs (block elements and <br>), whitespace collapsed."""
    s = decode(b)
    i = s.lower().find('<body')
    s = s[i:] if i >= 0 else s
    s = re.sub(r'(?s)<!--.*?-->', '', s)
    s = re.sub(r'(?is)<(script|style|xml|head|title)\b.*?</\1\s*>', '', s)
    s = re.sub(r'[\r\n]+', ' ', s)
    s = BLOCK.sub('\x00', s)
    s = htmlmod.unescape(re.sub(r'<[^>]+>', '', s))
    return [c for c in (clean(x) for x in s.split('\x00')) if c]


def source_letters_html(b: bytes) -> str:
    """Independent reader for the letters check (lxml, not the regex reader above): the body's text content."""
    import lxml.html
    doc = lxml.html.document_fromstring(decode(b))
    for bad in doc.xpath('//script|//style|//head'):
        bad.drop_tree()
    body = doc.find('body')
    return letters((body if body is not None else doc).text_content())


def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


ORD = {'PRIMERO': 1, 'SEGUNDO': 2, 'TERCERO': 3, 'CUARTO': 4, 'QUINTO': 5, 'SEXTO': 6, 'SEPTIMO': 7, 'SETIMO': 7,
       'OCTAVO': 8, 'NOVENO': 9, 'DECIMO': 10, 'UNICO': 1}
LATIN = r'BIS|TER|QUATER|QUINQUIES|SEXIES|SEPTIES|OCTIES|NONIES|NOVIES|DECIES'
ARTICLE = re.compile(r'^\s*(?:ART[IÍ]CULO|ART\.?|ARTS\.?)\s*(?:N[°º]\s*)?(?P<n>\d{1,4})\s*(?:[°ºª]|\.[°º]|O\b)?\s*'
                     r'(?P<latin>(?:' + LATIN + r')\b)?\s*(?:[-–—]\s*(?P<sub>\d{1,3}|[A-Z])\b)?\s*'
                     r'(?:[.:\-–—)]|\s*$|\s+(?=[A-ZÁÉÍÓÚÑ¿"“«(]))', re.I)
ARTICLE_WORD = re.compile(r'^\s*ART[IÍ]CULO\s+(?P<w>' + '|'.join(ORD) + r'|ÚNICO)\b\s*[°º]?\s*[.:\-–—]', re.I)


def article_id(line: str) -> str | None:
    m = ARTICLE.match(line)
    if m:
        rest = line[m.end():m.end() + 40]
        # "Artículo 5 de la ley ..." / "Art. 3, inc. b" are references, not headings
        if re.match(r'\s*(de|del|y|inc|incs|inciso|párrafo|ley|,)\b', rest, re.I) and not re.search(r'[.:\-–—]', line[m.start():m.end()]):
            return None
        parts = [str(int(m.group('n')))]
        if m.group('latin'):
            parts.append(m.group('latin').lower())
        if m.group('sub'):
            parts.append(m.group('sub').lower())
        return '-'.join(parts)
    m = ARTICLE_WORD.match(line)
    if m:
        return str(ORD.get(fold(m.group('w')), 1))
    return None


def split_units(paras: list[str], width: int | None = None) -> dict[str, dict]:
    """Paragraphs -> units: 'encabezado' (everything before the first article), one unit per article (headings just
    above an article stay with the article before; nothing is dropped)."""
    order: list[tuple[str, str, list[str]]] = []
    seen: Counter = Counter()
    cur = ('front', 'encabezado', [])
    order.append(cur)
    for p in paras:
        aid = article_id(p)
        if aid:
            seen[aid] += 1
            rid = aid if seen[aid] == 1 else f'{aid}~{seen[aid]}'
            cur = ('art', rid, [])
            order.append(cur)
        cur[2].append(p)
    if width is None:
        width = 4 if any(k == 'art' and int(re.match(r'\d+', r).group()) >= 1000 for k, r, _ in order) else 3
    units = {}
    for kind, rid, lines in order:
        if not lines:
            continue
        if kind == 'front':
            units['encabezado'] = {'label': 'Encabezado', 'kind': 'preamble', 'text': '\n'.join(lines) + '\n'}
            continue
        base, _, dup = rid.partition('~')
        key = 'art-' + re.sub(r'^\d+', lambda m: m.group().zfill(width), base) + (f'-dup{dup}' if dup else '')
        label = 'Artículo ' + base.replace('-', ' ') + (f' ({dup})' if dup else '')
        units[key] = {'label': label, 'kind': 'art', 'text': '\n'.join(lines) + '\n'}
    return units


# ---------------------------------------------------------------- in force

MONTHS = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
          'SEPTIEMBRE': 9, 'SETIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}
DEFAULT_DAYS = 9
DEFAULT_RULE = ('Código Civil y Comercial de la Nación, art. 5: "Las leyes rigen después del octavo día de su '
                'publicación oficial, o desde el día que ellas determinen", counted under art. 6 (the day of '
                'publication is excluded), so a law without its own vigencia clause is in force from the ninth day '
                'after its publication in the provincial Boletín Oficial (before 1 August 2015, Código Civil art. 2 '
                'as replaced by Ley 16.504, to the same effect). A law\'s own vigencia clause overrides the rule.')


def _add(d: str, n: int) -> str:
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()


def in_force(paras: list[str], pub: str | None, promul: str | None) -> tuple[str | None, str]:
    """The law's own vigencia clause (a sentence with VIGENCIA / VIGOR / REGIR in its last articles), else pub + 9."""
    if not pub:
        return None, 'no publication date'
    tail = fold(" ".join(paras[-25:]))
    for s in re.split(r'(?<=\.)\s+', tail):
        # only a clause about this norm itself: "La presente ley entrará en vigencia ...", "Esta reforma entra en
        # vigencia el día ...", "Esta ley rige desde ..."
        if not re.search(r'(ESTA|LA\s+PRESENTE|PRESENTE)\s+(LEY|REFORMA|CONSTITUCION|NORMA|CODIGO)\b[^.]{0,60}?'
                         r'(ENTRA|ENTRARA|REGIRA|RIGE|REGIR|TENDRA\s+VIGENCIA|COMENZARA|SERA\s+OBLIGATORIA)', s):
            continue
        if re.search(r'\bANTES\s+DEL?\b', s):
            continue
        if re.search(r'DIA\s+SIGUIENTE\s+(AL|DE|A)\s+(DE\s+)?(LA\s+FECHA\s+DE\s+)?SU\s+PUBLICACION', s):
            return _add(pub, 1), 'its own clause: the day after publication'
        if re.search(r'(DESDE|A\s+PARTIR\s+DE(L\s+DIA\s+DE)?|EL\s+DIA\s+DE)\s+(LA\s+FECHA\s+DE\s+)?SU\s+PUBLICACION', s):
            return pub, 'its own clause: from publication'
        if re.search(r'(DESDE|A\s+PARTIR\s+DE)\s+(LA\s+FECHA\s+DE\s+)?SU\s+(SANCION|PROMULGACION)', s):
            return pub, 'its own clause: from sanción/promulgación (dated at publication, when it became known)'
        m = re.search(r'(\d{1,2})\s*(?:[°º]\s*)?DE\s+(' + '|'.join(MONTHS) + r')\s+(?:DE|DEL)\s+(?:ANO\s+)?(\d{4})', s)
        if m and re.search(r'ENTRA|REGIR|VIGENCIA\s+(EL|A\s+PARTIR)|VIGENCIA\s+DESDE', s):
            try:
                d = date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
            except ValueError:
                d = None
            if d and d >= (promul or pub)[:4] + '-01-01':
                return d, 'its own clause: the date it names'
    return _add(pub, DEFAULT_DAYS), 'default rule: the ninth day after publication'


def dmy(s: str) -> str | None:
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s or '')
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- adapters
# Each adapter gives:
#   source: dict (name, url, licence, notes, publisher name)
#   catalogue(): {'constitucion': [item], 'codigo': [item], 'ley': [item]}   (items: dict with 'page' url, 'title')
#   detail(item) -> dict: number, kind ('ley'|'decreto-ley'|'constitucion'|...), title, pub, promul, updated, text_url,
#                         amended (bool), reason; or None when there is no text
#   text(detail) -> (paragraphs, source bytes, letters of the source by the independent reader)


class GBA:
    """Provincia de Buenos Aires: Sistema de Información Normativa y Documental "Malvinas Argentinas"
    (normas.gba.gob.ar), Subsecretaría Legal y Técnica, Secretaría General."""
    host = 'normas.gba.gob.ar'
    base = 'https://normas.gba.gob.ar'
    source = {
        'name': 'Sistema de Información Normativa y Documental "Malvinas Argentinas" (normas.gba.gob.ar), '
                'Subsecretaría Legal y Técnica, Secretaría General, Provincia de Buenos Aires',
        'url': 'https://normas.gba.gob.ar/',
        'publisher': 'Normas GBA (normas.gba.gob.ar)',
        'gazette': 'Boletín Oficial de la Provincia de Buenos Aires',
        'notes': 'For each norm: its record (number, promulgation and publication dates, Boletín Oficial number, '
                 'related norms) and its texto actualizado (HTML). The texto actualizado is the current consolidated '
                 'text; earlier consolidated versions are not published.',
    }

    def page(self, path: str) -> str:
        b = get(self.base + path)
        return decode(b) if b else ''

    def catalogue(self, n_laws: int) -> dict:
        out = {'constitucion': [{'page': '/constitucion-de-la-provincia-de-buenos-aires', 'title':
                                 'Constitución de la Provincia de Buenos Aires', 'constitution': True}]}
        s = self.page('/codigos-de-la-provincia-de-buenos-aires')
        codes = []
        for m in re.finditer(r'href="(/ar-b/[^"]+)"', s):
            if m.group(1) not in [c['page'] for c in codes]:
                codes.append({'page': m.group(1), 'title': ''})
        out['codigo'] = codes
        laws, pg = [], 1
        code_pages = {c['page'] for c in codes}
        seen = set()

        def take(found):
            new = 0
            for f in found:
                if f not in code_pages and f not in seen:
                    seen.add(f)
                    laws.append({'page': f, 'title': ''})
                    new += 1
            return new
        # the newest 200 (the site serves at most 20 result pages per search), then year by year
        while len(laws) < n_laws and pg <= 20:
            s = self.page(f'/resultados?page={pg}&q%5Bsort%5D=by_publication_date_desc&q%5Bterms%5D%5Braw_type%5D=Law')
            if not take(re.findall(r'href="(/ar-b/ley/[^"]+)"', s)):
                break
            pg += 1
        year = 2026
        while len(laws) < n_laws and year >= 1854:
            for pg in range(1, 21):
                if len(laws) >= n_laws:
                    break
                s = self.page(f'/resultados?page={pg}&q%5Bsort%5D=by_publication_date_desc&q%5Bterms%5D%5Braw_type%5D=Law'
                              f'&q%5Bterms%5D%5Byear%5D={year}')
                if not take(re.findall(r'href="(/ar-b/ley/[^"]+)"', s)):
                    break
            year -= 1
        out['ley'] = laws[:n_laws]
        return out

    def detail(self, item: dict) -> dict | None:
        s = self.page(item['page'])
        if not s:
            return None
        t = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<(script|style)\b.*?</\1>', '', s))))
        d = {'page': self.base + item['page']}
        if item.get('constitution'):
            d.update(kind='constitucion', number='', title='Constitución de la Provincia de Buenos Aires')
            m = re.search(r'href="(/constitucion-de-la-provincia-de-buenos-aires-1994)"', s)
            d['text_url'] = self.base + m.group(1) if m else None
        else:
            m = re.match(r'/ar-b/([a-z-]+)/(\d{4})/([^/]+)/(\d+)', item['page'])
            d['kind'], d['year'], d['number'] = m.group(1), m.group(2), m.group(3)
            m = re.search(r'title="Ver texto actualizado"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*title="Ver texto actualizado"', s)
            d['text_url'] = self.base + (m.group(1) or m.group(2)) if m else None
            r = re.search(r'Resumen (.*?) Observaciones', t)
            d['title'] = r.group(1).strip() if r else ''
        d['promul'] = dmy((re.search(r'Fecha de promulgaci[oó]n: (\S+)', t) or [None, ''])[1])
        d['pub'] = dmy((re.search(r'Fecha de publicaci[oó]n: (\S+)', t) or [None, ''])[1])
        d['bo'] = (re.search(r'N[uú]mero de Bolet[ií]n Oficial: (\S+)', t) or [None, ''])[1]
        d['updated'] = dmy((re.search(r'[ÚU]ltima actualizacion: (\S+)', t) or [None, ''])[1])
        # related norms: a later norm (a different one, same year or after) may have changed the text
        rel = re.findall(r'href="/ar-b/([a-z-]+)/(\d{4})/([^/"]+)/\d+"', s.split('Normas relacionadas')[-1]) \
            if 'Normas relacionadas' in s else []
        later = [r for r in rel if not d.get('year') or (int(r[1]) >= int(d['year']) and not (r[0] == d['kind'] and r[2] == d['number']))]
        d['related_later'] = [f'{k} {n}/{y}' for k, y, n in later]
        return d if d.get('text_url') else None

    def text(self, d: dict) -> tuple[list[str], bytes] | None:
        b = get(d['text_url'])
        if not b:
            return None
        return html_paragraphs(b), b


ADAPTERS = {'buenos-aires': GBA}


def adapter_cls(slug: str):
    """The adapter for a province: built in (above) or scripts/world-law/ar_adapters/<slug with _>.py, class Adapter."""
    if slug in ADAPTERS:
        return ADAPTERS[slug]
    import importlib
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    ADAPTERS[slug] = importlib.import_module('ar_adapters.' + slug.replace('-', '_')).Adapter
    return ADAPTERS[slug]


def pdf_paragraphs(b: bytes) -> list[str]:
    """A PDF with a text layer -> its paragraphs (PyMuPDF text blocks, lines joined with a space). No OCR."""
    import pymupdf
    out = []
    with pymupdf.open(stream=b, filetype='pdf') as doc:
        for page in doc:
            for blk in page.get_text('blocks', sort=False):
                if blk[6] != 0:
                    continue
                c = clean(blk[4])
                if not c:
                    continue
                # a block that continues a sentence (the previous one does not end a sentence or heading, and this one
                # starts in lower case or is not an article heading) is the same paragraph wrapped by the layout
                if out and not re.search(r'[.:;!?)]$', out[-1]) and not article_id(c) and                         (c[:1].islower() or not out[-1].isupper()) and not out[-1].isupper():
                    out[-1] = out[-1] + ' ' + c
                else:
                    out.append(c)
    return out


def source_letters_pdf(b: bytes) -> str:
    """Independent reader for PDFs (poppler's pdftotext, not PyMuPDF)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'x.pdf'
        f.write_bytes(b)
        out = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(f), '-'], capture_output=True)
        return letters(out.stdout.decode('utf-8', 'replace'))

AMEND_NOTE = re.compile(r'\((?:Texto|Art[íi]culo|Inciso|P[áa]rrafo|Ap[áa]rtado)?\s*[^()]{0,40}(?:seg[úu]n|sustituid|modificad|'
                        r'incorporad|derogad|agregad|observad|vetad)', re.I)


# ---------------------------------------------------------------- one norm -> corpus act

def law_key(d: dict) -> str:
    if d['kind'] == 'constitucion':
        return 'constitucion-' + (d.get('pub') or '')[:4]
    return ascii_slug(f'{d["kind"]}-{d["number"]}' + (f'-{d["year"]}' if d['kind'] not in ('ley',) else ''))


def law_label(d: dict) -> str:
    k = {'ley': 'Ley', 'decreto-ley': 'Decreto-Ley', 'decreto': 'Decreto', 'constitucion': 'Constitución'}.get(d['kind'], d['kind'].title())
    if d['kind'] == 'constitucion':
        return f'Constitución ({(d.get("pub") or "")[:4]})'
    num = d['number']
    if d['kind'] == 'ley' and num.isdigit() and len(num) > 3:
        num = f'{int(num):,}'.replace(',', '.')
    return f'{k} {num}' + (f'/{d["year"]}' if d['kind'] not in ('ley',) and d.get('year') else '')


def build_act(slug: str, d: dict, paras: list[str], src: bytes, used: set, docs_date: str) -> tuple[dict, dict, dict]:
    units = split_units(paras)
    key = law_key(d)
    f, basis = in_force(paras, d.get('pub'), d.get('promul'))
    if d.get('in_force'):
        f, basis = d['in_force']      # the adapter read the norm's own clause
    law = {'label': law_label(d), 'title': d.get('title') or law_label(d), 'kind': 'law',
           'enacted': d.get('promul'), 'published': d.get('pub'), 'url': d['page'], 'temporary_until': None,
           'restores': None, 'note': f'In force {f} ({basis}).' if f else None}
    notes = bool(AMEND_NOTE.search(' '.join(paras)))
    amended = bool(d.get('related_later')) or notes
    if getattr(adapter_cls(slug), 'original_only', False) or d.get('as_enacted'):
        # the source gives each norm's text as enacted (or as of a dated official text): dated on its in-force day
        amended = False
    sha = hashlib.sha256(src).hexdigest()
    if amended or not f:
        day = max(x for x in (d.get('updated'), f) if x) if (d.get('updated') or f) else docs_date
        if d.get('updated') and d['updated'] > docs_date:
            day = max(docs_date, f or docs_date)
        v = {'from': day, 'source_url': d['text_url'], 'sha256': sha, 'units': units, 'credits': {},
             'note': ('Oldest version available: the consolidated text (texto actualizado) as the source holds it, '
                      f'dated by its record\'s last update ({d.get("updated")}). '
                      + ('Norms recorded as related to it since: ' + ', '.join(d['related_later'][:12])
                         + (' …' if len(d['related_later']) > 12 else '') + '. ' if d.get('related_later') else '')
                      + ('The text carries amendment notes. ' if notes else '')
                      + 'Earlier versions are not published by the source.')}
        first_law, earlier = None, [key]
        hist = 'current'
    else:
        v = {'from': f, 'source_url': d['text_url'], 'sha256': sha, 'units': units, 'credits': {},
             'note': (d.get('note') or 'As enacted: no later norm is recorded as related to it and the text carries no '
                      'amendment notes.') + f' In force {f} ({basis}).'}
        first_law, earlier = key, []
        hist = 'enacted'
    title = d.get('title') or law_label(d)
    short = law_label(d) if d['kind'] != 'constitucion' else 'Constitución'
    s = 'constitucion' if d['kind'] == 'constitucion' else law_key(d)
    base, k = s, 2
    while s in used:
        s, k = f'{base}-{k}', k + 1
    used.add(s)
    act = {'slug': s, 'short': short, 'title': title if d['kind'] == 'constitucion' else f'{law_label(d)}: {title}'[:300],
           'url': d['page'], 'first_law': first_law, 'earlier_laws': earlier, 'versions': [v]}
    return act, {key: law}, {'units': len(units), 'history': hist, 'from': v['from']}


# ---------------------------------------------------------------- parts

def country_block(slug: str) -> dict:
    en, native, code, tz = PROVINCES[slug]
    src = adapter_cls(slug).source
    return {
        'code': code, 'name': en, 'slug': f'argentina-{slug}', 'lang': 'es', 'tz': tz, 'future_branch': 'futuro',
        'publisher': {'name': src['publisher'], 'email': f'normas@{adapter_cls(slug).host}.invalid'},
        'default_in_force_rule': {'text': DEFAULT_RULE,
                                  'source': 'https://servicios.infoleg.gob.ar/infolegInternet/anexos/235000-239999/235975/texact.htm'},
        'licence_note': f'Fuente: {src["name"]}, {src["url"]}.',
    }


AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which norms to include; it wrote no law text. '
          'Every word of law comes from the provincial source\'s own texts.']


def decisions(slug: str) -> list[str]:
    src = adapter_cls(slug).source
    if hasattr(adapter_cls(slug), 'decisions'):
        return list(adapter_cls(slug).decisions)
    return [
        f'The source ({src["url"]}) publishes, for each norm, only its current consolidated text (texto actualizado), '
        'not the earlier consolidated versions. A norm that no later norm is recorded as related to, and whose text '
        'carries no amendment notes, is shown as enacted, dated the day it took effect. Every other norm is shown as '
        'its current text only ("oldest version available"), dated by the day its record was last updated.',
        'In-force day: the law\'s own vigencia clause when its last articles state one (from publication, the day after, '
        'or a named date); otherwise the ninth day after publication (Código Civil y Comercial, arts. 5 and 6).',
        'Units: the heading (encabezado: number, enacting formula and anything before Artículo 1) and one file per '
        'article, holding the article and everything printed after it up to the next article (section headings, '
        'signatures, the source\'s amendment notes). Nothing is dropped. One paragraph per line, spacing normalised.',
        'Laws are added newest first, in parts of about 50; codes and the constitution come first.',
    ]


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def source_block(slug: str, retrieved: str) -> dict:
    src = adapter_cls(slug).source
    return {'name': src['name'], 'url': src['url'], 'retrieved': retrieved,
            'licence': 'Official legal texts of the province, published by its government for public consultation. '
                       'Argentina\'s copyright law (Ley 11.723) has no express exclusion for them; laws are public acts '
                       'of government, binding on everyone once officially published (Código Civil y Comercial, art. 5). '
                       'The source states no restriction on reuse. Reproduced with attribution, following the official text.',
            'notes': src['notes']}


def parse_part(slug: str, name: str, details: list[tuple[dict, list[str], bytes]], docs_date: str) -> dict:
    out = folder(slug) / 'corpus.d' / f'{name}.json'
    if out.with_suffix('.PUBLISH').exists():
        return {'skipped': 'published'}
    used, laws_seen = set(), {}
    for p in sorted((folder(slug) / 'corpus.d').glob('*.json')):
        if p.stem == name:
            continue
        pj = json.loads(p.read_text(encoding='utf-8'))
        for a in pj.get('acts', []):
            used.add(a['slug'])
        laws_seen.update(pj.get('laws', {}))
    acts, laws, rep = [], {}, {}
    for d, paras, src in details:
        a, l, r = build_act(slug, d, paras, src, used, docs_date)
        if any(v['from'] == docs_date for v in a['versions']):
            # dated today: its noon commit would be in the future until midday; it joins a later part
            used.discard(a['slug'])
            rep[a['slug']] = {'deferred': 'dated on the retrieval day'}
            continue
        for k, v in l.items():
            if k in laws_seen and laws_seen[k]['label'] != v['label']:
                raise SystemExit(f'law key clash {k}')
            laws.setdefault(k, v)
        acts.append(a)
        rep[a['slug']] = r
    has_first = any(p.stem != name and p.stem < name for p in (folder(slug) / 'corpus.d').glob('*.json'))
    part = {'country': country_block(slug), 'laws': dict(sorted(laws.items())), 'acts': acts}
    if not has_first:
        part.update(sources=[source_block(slug, docs_date)], decisions=decisions(slug), ai_use=AI_USE)
    (folder(slug) / 'corpus.d').mkdir(parents=True, exist_ok=True)
    write_part(out, part)
    return rep


# ---------------------------------------------------------------- checks

def letters_check(slug: str, part_name: str) -> list[str]:
    part = json.loads((folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        for v in act['versions']:
            b = cached(v['source_url'])
            if b is None or hashlib.sha256(b).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]} {v["from"]}: source missing or sha256 differs')
                continue
            ad = adapter_cls(slug)
            src = ad.source_letters(b) if hasattr(ad, 'source_letters') else source_letters_html(b)
            mine = ''.join(u['text'] for u in v['units'].values())
            if src != letters(mine) and sorted(src) != sorted(letters(mine)):
                # (equal multisets pass: two PDF readers may order table cells differently; nothing lost or added)
                ca, cb = Counter(src), Counter(letters(mine))
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((ca - cb).most_common(6))} '
                             f'corpus-only {dict((cb - ca).most_common(6))}')
    return probs


# ---------------------------------------------------------------- docs, scaffold, verify, publish

def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][x.month - 1]} {x.year}'


def _verified(slug: str, extra=()) -> list[dict]:
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((folder(slug) / 'corpus.d').glob('*.json'))
            if p.with_suffix('.PUBLISH').exists() or p.stem in extra]


def write_docs(slug: str, docs_date: str, extra=(), out: Path | None = None):
    en, native, code, tz = PROVINCES[slug]
    src = adapter_cls(slug).source
    parts = _verified(slug, extra)
    rows, nacts, nvers, nen = [], 0, 0, 0
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            nen += bool(a.get('first_law'))
            hist = (f'as enacted, in force {_long(vs[0]["from"])}' if a.get('first_law')
                    else f'current text only, as of {_long(vs[0]["from"])}')
            t = a['title'].replace('|', '/')
            rows.append(f'| `{a["slug"]}/` | {t[:160]}{"…" if len(t) > 160 else ""} | {hist} |')
    is_city = slug == 'buenos-aires-city'
    unit = 'the Autonomous City of Buenos Aires' if is_city else f'the Province of {en}'
    repo = out or (folder(slug) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en}: law history in git

The law of {unit} ({native}, Argentina) as a git history: one file per article, one commit per norm on the day it took effect. `git log` lists the changes to an article; checking out a date gives the text the record holds for that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{code.lower()}/`. Argentina's national law is in [lexifina/argentina-law](https://github.com/lexifina/argentina-law).

The text is in Spanish, exactly as the source prints it.

## What this repository holds

{nacts} norm{"s" if nacts != 1 else ""} so far: the constitution first, then the codes, then laws, newest first, added in parts. {nen} of them are shown as enacted; the rest are their current consolidated text only (see Dates).

| Folder | Norm | History |
| --- | --- | --- |
{chr(10).join(rows)}

## Source

{src['name']}, <{src['url']}>. {src['notes']}

## Dates

- Each commit is dated at **noon, {tz}, on the day the norm took effect**: the day its own vigencia clause names, or otherwise the ninth day after its publication in the {src['gazette']} (Código Civil y Comercial de la Nación, arts. 5 and 6).
- {src.get('dates_note') or "The source publishes only today's consolidated text of each norm. A norm that no later norm is recorded as related to, and whose text carries no amendment notes, is shown as enacted. Every other norm is its current text only, the **oldest version available**, dated by the day the source last updated its record; its earlier wording is not shown."}
- Versions that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.

## Files

`<norm>/art-005.md` is Artículo 5, `art-005-bis.md` Artículo 5 bis; `encabezado.md` holds the number, the enacting formula and anything printed before Artículo 1. Section headings, signatures and the source's amendment notes stay in the file of the article they follow. One paragraph per line.

## How it is checked

- Every version of every norm is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the source document it was read from (read again with an independent HTML reader), so no word is lost or added.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## Limits

This is not an official publication. The binding text is the one published in the {src['gazette']}. Only the norms listed above are included, and most show only their current text.
"""
    lic = f"""The law texts in this repository are official texts of {unit} ({native}, Argentina), taken from
{src['name']}, {src['url']} (consulted {docs_date}).

They are legal norms (constitution, codes and laws) published by the provincial government for public consultation.
Argentina's copyright law, Ley 11.723, contains no express exclusion for official texts; laws are public acts of
government that bind everyone once officially published (Código Civil y Comercial de la Nación, art. 5: "Las leyes
rigen después del octavo día de su publicación oficial, o desde el día que ellas determinen"). The source states no
restriction on reuse. They are reproduced here with this attribution, following the official text.

Changes made by Lexifina: each text was split into one Markdown file per article, one paragraph per line, with spacing
normalised; the wording was not changed. The provincial government does not endorse this repository. This repository
is not an official publication; the binding text is the one published in the {src['gazette']}.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': code.lower(), 'code': code, 'name': en, 'level': 'province' if not is_city else 'autonomous city',
             'parent': 'ar', 'repo': f'https://github.com/lexifina/{repo_name(slug)}',
             'build': f'built: constitution, codes and laws ({nacts} norms, {nvers} versions) from {src["url"]}',
             'language': 'es', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


def run(*a, cwd=None, check=True):
    p = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError(f'{a[:3]} failed: {p.stderr[:400]}')
    return p


def scaffold(slug: str) -> str:
    import tempfile
    en, native, code, tz = PROVINCES[slug]
    repo = repo_name(slug)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    if run('gh', 'api', f'repos/lexifina/{repo}', check=False).returncode != 0:
        run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
            '-f', f'description={en} (Argentina) law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    run('git', 'init', '-q', '-b', 'main', cwd=d)
    run('git', 'config', 'core.autocrlf', 'false', cwd=d)
    src = adapter_cls(slug).source
    (d / 'README.md').write_text(f"""# {en}: law as git history

Work in progress. This repository will hold the law of {en} ({native}, Argentina) as a git history: one file per
article, one commit per norm on the day it took effect.

Planned first build: the provincial constitution, then the codes and laws, from the province's official legislation
portal.

Source: <{src['url']}>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text(f"""# Sources

- {src['name']}: <{src['url']}>

The terms and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    run('git', 'add', '-A', cwd=d)
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-10-30T12:00:00-0300', GIT_COMMITTER_DATE='2026-10-30T12:00:00-0300')
    subprocess.run(['git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
                    f'Argentina ({en}): sources, before any law'], cwd=d, env=env, check=True)
    run('git', 'remote', 'add', 'origin', remote, cwd=d)
    for attempt in range(4):
        p = run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
        if p.returncode == 0:
            break
        time.sleep(10 * (attempt + 1))
    return 'CREATED ' + run('git', 'ls-remote', remote, check=False).stdout.strip()[:60]


def _low(cmd: list[str], env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                          creationflags=0x4000 if os.name == 'nt' else 0)


def _rm(d: Path):
    import stat

    def onerr(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if d.exists():
        shutil.rmtree(d, onexc=onerr)


def verify_part(slug: str, part: str, docs_date: str) -> tuple[bool, str]:
    probs = letters_check(slug, part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[0]}'
    src = folder(slug)
    tmp = DOCS / f'{repo_name(slug)}-verify'
    build = DOCS / f'{repo_name(slug)}-verifybuild'
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()] + [part]
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(slug, docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-600:]
    c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
              str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, 'check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force'):
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300] + \
            json.dumps(res.get('details', [])[:3], ensure_ascii=False)[:400]
    pj = json.loads((src / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    acts = pj['acts']
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} norm(s), {sum(len(a["versions"]) for a in acts)} versions {days[0]}..{days[-1]} from '
            f'{adapter_cls(slug).host}: letters and digits of every version equal the source document (independent lxml '
            f'reader); scratch build of verified parts + this part: check.py {res.get("versions")} versions, 0 mismatches, '
            f'0 trailer errors, 0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return True, line


def publish(slug: str, part: str, docs_date: str) -> str:
    ok, line = verify_part(slug, part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    pub = folder(slug) / 'corpus.d' / f'{part}.PUBLISH'
    tmp = pub.with_suffix('.ptmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    write_docs(slug, docs_date, extra=[part])
    os.replace(tmp, pub)
    top = folder(slug) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


# ---------------------------------------------------------------- driver

def claim(slug: str, note: str) -> bool:
    p = CLAIMS / f'{repo_name(slug)}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'{SESSION} {now()} ({note})\n')
        return True
    except FileExistsError:
        return p.read_text(encoding='utf-8', errors='replace').startswith(SESSION)


def progress(slug: str, line: str):
    p = folder(slug) / 'PROGRESS.md'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'# {repo_name(slug)} (private progress, gitlaw-scraper-dell)\n\nBuilder: '
                     f'scripts/world-law/ar_provinces.py; source {adapter_cls(slug).source["url"]}.\n\n',
                     encoding='utf-8', newline='\n')
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {now()} {line}\n')


def cpu_ok() -> bool:
    try:
        last = Path(os.environ['LOCALAPPDATA'], 'gitlaw-cpu.log').read_text(encoding='utf-8').strip().splitlines()[-1]
        c5 = int(re.search(r'cpu5=(\d+)', last).group(1))
        ram = int(re.search(r'ram=(\d+)', last).group(1))
        return c5 <= 92 and ram <= 85
    except Exception:
        return True


def plan(cat: dict) -> list[tuple[str, list[dict]]]:
    out = [('10-constitucion', cat['constitucion'][:1])] if cat.get('constitucion') else []
    codes = cat.get('codigo', [])
    for i in range(0, len(codes), PART_SIZE):
        out.append((f'{20 + i // PART_SIZE}-codigos-{i // PART_SIZE + 1}', codes[i:i + PART_SIZE]))
    leyes = cat.get('ley', [])
    for i in range(0, len(leyes), PART_SIZE):
        out.append((f'{30 + i // PART_SIZE}-leyes-{i // PART_SIZE + 1:02d}', leyes[i:i + PART_SIZE]))
    return out


def fetch_part(slug: str, members: list[dict]) -> list[tuple[dict, list[str], bytes]]:
    ad = adapter_cls(slug)()
    out = []
    for m in members:
        d = ad.detail(m)
        if not d:
            continue
        t = ad.text(d)
        if not t or not t[0]:
            continue
        out.append((d, t[0], t[1]))
    return out


def drive(slug: str, docs_date: str, n_laws: int, max_parts: int | None):
    if not claim(slug, 'Argentine provinces'):
        say(f'{slug}: claimed by another session, skipped')
        return
    folder(slug).mkdir(exist_ok=True)
    gi = folder(slug) / '.gitignore'
    if not gi.exists():
        gi.write_text('.tmp/\n', encoding='utf-8', newline='\n')
    say(f'{slug}: scaffold {scaffold(slug)}')
    ad = adapter_cls(slug)()
    cat = ad.catalogue(n_laws)
    parts = plan(cat)
    progress(slug, f'catalogue: {len(cat.get("constitucion", []))} constitution, {len(cat.get("codigo", []))} codes, '
                   f'{len(cat.get("ley", []))} laws; {len(parts)} parts')
    for i, (name, members) in enumerate(parts):
        if max_parts is not None and i >= max_parts:
            break
        if (folder(slug) / 'corpus.d' / f'{name}.PUBLISH').exists():
            continue
        dets = fetch_part(slug, members)
        say(f'{slug} {name}: fetched {len(dets)}/{len(members)} ({sum(net().count.values())} requests)')
        if not dets:
            progress(slug, f'{name}: no text in any member')
            continue
        while not cpu_ok():
            time.sleep(60)
        rep = parse_part(slug, name, dets, docs_date)
        (folder(slug) / '.tmp').mkdir(exist_ok=True)
        (folder(slug) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                                 encoding='utf-8')
        r = _low([sys.executable, '-X', 'utf8', str(Path(__file__)), 'publish', slug, name, docs_date])
        out = (r.stdout.strip().splitlines() or [''])[-1] + (r.stderr.strip()[-300:] if r.returncode else '')
        say(f'{slug} {name}: {out[:300]}')
        progress(slug, f'{name}: {out[:600]}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    cmd = sys.argv[1]
    if cmd == 'run':
        args = sys.argv[2:]
        mp, nl = None, 200
        for a in list(args):
            if a.startswith('--max-parts='):
                mp = int(a.split('=')[1]); args.remove(a)
            if a.startswith('--laws='):
                nl = int(a.split('=')[1]); args.remove(a)
        dd = dt.date.today().isoformat()
        for s_ in args:
            try:
                drive(s_, dd, nl, mp)
            except Stop as e:
                say(f'{s_}: STOPPED {e}')
                progress(s_, f'STOPPED: {e}')
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
    elif cmd == 'scaffold':
        for s_ in sys.argv[2:]:
            print(s_, scaffold(s_))
