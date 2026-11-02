"""Spain's 17 comunidades autónomas and the autonomous cities of Ceuta and Melilla for git-for-law (gitlaw-scraper-dell,
coverage wave 2026-10-30): one public repo per unit, lexifina/spain-<unit>-law, built by scripts/gitlaw_common/build.py
from corpus.d parts. The national lexifina/spain-law and scripts/spain-law belong to another session: never touched.

Source: the BOE's consolidated legislation (Agencia Estatal Boletín Oficial del Estado, "Legislación consolidada",
open-data API https://www.boe.es/datosabiertos/api/legislacion-consolidada). Each norm's XML holds every block
(article, disposition, heading) with every version, its fecha_vigencia and the id_norma of the norm that made it. The
Estatuto de Autonomía (an Estatal Ley Orgánica) is each unit's first part; then the unit's Autonómico norms in force,
oldest first, in parts of PART_SIZE. ONE fetch process for the host, shared by every unit, one request at a time.

    python -X utf8 scripts/world-law/es_ccaa.py run [unit ...]        # claim, scaffold, fetch, parse, verify, publish
    python -X utf8 scripts/world-law/es_ccaa.py partpub <unit> <part> <docs-date>
    python -X utf8 scripts/world-law/es_ccaa.py letters <unit> <part>

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # scripts/
DOCS = ROOT.parent.parent                           # ~/Documents
HERE = Path(__file__).resolve().parent
UA = 'lexifina-git-for-law/1.0 (world-law@lexifina.com)'
HOST = 'www.boe.es'
API = f'https://{HOST}/datosabiertos/api/legislacion-consolidada'
PAUSE0, PAUSE1 = 3.0, 2.0                            # seconds between request starts: first 100 answers, then
PART_SIZE = 50
SESSION = 'gitlaw-scraper-dell'
CLAIMS = HERE / 'claims'
CACHE = HERE / '.cache' / 'es-boe'                  # gitignored (**/.cache/)
ROBOTS_IDS = HERE / 'es_boe_robots_ids.txt'         # ids named by a Disallow line of www.boe.es/robots.txt

# unit: (English name, official name, ISO 3166-2, BOE departamento codes, Estatuto id, tz, genitive for docs)
UNITS = {
    'andalusia': ('Andalusia', 'Comunidad Autónoma de Andalucía', 'ES-AN', ['8010'], 'BOE-A-2007-5825', 'Europe/Madrid'),
    'catalonia': ('Catalonia', 'Comunidad Autónoma de Cataluña', 'ES-CT', ['8070'], 'BOE-A-2006-13087', 'Europe/Madrid'),
    'madrid': ('Madrid', 'Comunidad de Madrid', 'ES-MD', ['8131'], 'BOE-A-1983-6317', 'Europe/Madrid'),
    'valencia': ('Valencian Community', 'Comunitat Valenciana', 'ES-VC', ['8161', '8162'], 'BOE-A-1982-17235',
                 'Europe/Madrid'),
    'galicia': ('Galicia', 'Comunidad Autónoma de Galicia', 'ES-GA', ['8090'], 'BOE-A-1981-9564', 'Europe/Madrid'),
    'basque-country': ('Basque Country', 'Comunidad Autónoma del País Vasco', 'ES-PV', ['8140'], 'BOE-A-1979-30177',
                       'Europe/Madrid'),
    'castile-and-leon': ('Castile and León', 'Comunidad de Castilla y León', 'ES-CL', ['9531'], 'BOE-A-2007-20635',
                         'Europe/Madrid'),
    'canary-islands': ('Canary Islands', 'Comunidad Autónoma de Canarias', 'ES-CN', ['8030'], 'BOE-A-2018-15138',
                       'Atlantic/Canary'),
    'castile-la-mancha': ('Castilla-La Mancha', 'Comunidad Autónoma de Castilla-La Mancha', 'ES-CM', ['8060'],
                          'BOE-A-1982-20820', 'Europe/Madrid'),
    'murcia': ('Region of Murcia', 'Comunidad Autónoma de la Región de Murcia', 'ES-MC', ['8100'], 'BOE-A-1982-15031',
               'Europe/Madrid'),
    'aragon': ('Aragon', 'Comunidad Autónoma de Aragón', 'ES-AR', ['8020'], 'BOE-A-2007-8444', 'Europe/Madrid'),
    'balearic-islands': ('Balearic Islands', 'Comunidad Autónoma de las Illes Balears', 'ES-IB', ['8120', '8121'],
                         'BOE-A-2007-4233', 'Europe/Madrid'),
    'extremadura': ('Extremadura', 'Comunidad Autónoma de Extremadura', 'ES-EX', ['8080'], 'BOE-A-2011-1638',
                    'Europe/Madrid'),
    'asturias': ('Asturias', 'Comunidad Autónoma del Principado de Asturias', 'ES-AS', ['8150'], 'BOE-A-1982-634',
                 'Europe/Madrid'),
    'navarre': ('Navarre', 'Comunidad Foral de Navarra', 'ES-NC', ['8170'], 'BOE-A-1982-20824', 'Europe/Madrid'),
    'cantabria': ('Cantabria', 'Comunidad Autónoma de Cantabria', 'ES-CB', ['8040'], 'BOE-A-1982-635', 'Europe/Madrid'),
    'la-rioja': ('La Rioja', 'Comunidad Autónoma de La Rioja', 'ES-RI', ['8110'], 'BOE-A-1982-15030', 'Europe/Madrid'),
    'ceuta': ('Ceuta', 'Ciudad Autónoma de Ceuta', 'ES-CE', [], 'BOE-A-1995-6358', 'Africa/Ceuta'),
    'melilla': ('Melilla', 'Ciudad Autónoma de Melilla', 'ES-ML', [], 'BOE-A-1995-6359', 'Africa/Ceuta'),
}
CITY = {'ceuta', 'melilla'}


def repo_name(u: str) -> str:
    return f'spain-{u}-law'


def folder(u: str) -> Path:
    return ROOT / repo_name(u)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---------------------------------------------------------------- fetching (one process, one request at a time)

class Stop(Exception):
    pass


class Net:
    def __init__(self):
        import requests
        self.requests = requests
        self.s = requests.Session()
        self.s.headers['User-Agent'] = UA
        self.s.headers['Accept-Encoding'] = 'gzip'
        self.lock = threading.Lock()
        self.last = 0.0
        self.count = 0
        self.clean = 0
        self.forbidden = 0
        self.log = HERE / 'logs' / 'es-boe-requests.jsonl'
        self.log.parent.mkdir(exist_ok=True)

    def get(self, url: str, accept: str):
        with self.lock:  # one request at a time, whatever the caller
            for attempt in range(4):
                wait = self.last + (PAUSE0 if self.clean < 100 else PAUSE1) - time.time()
                if wait > 0:
                    time.sleep(wait)
                self.last = time.time()
                self.count += 1
                t0 = time.time()
                try:
                    r = self.s.get(url, headers={'Accept': accept}, timeout=300)
                except self.requests.RequestException:
                    self._note(url, 0, 0, t0)
                    if attempt == 3:
                        raise
                    time.sleep(20 * (attempt + 1))
                    continue
                self._note(url, r.status_code, len(r.content), t0)
                head = r.content[:3000].lower()
                if (b'just a moment' in head or b'captcha' in head or b'incapsula' in head
                        or b'request unsuccessful' in head or b'access denied' in head):
                    raise Stop(f'challenge-like answer at {url}: stopping the host (never get round one)')
                if r.status_code == 429:
                    raise Stop('429 from the host: stopping')
                if r.status_code == 403:
                    self.forbidden += 1
                    if self.forbidden >= 2:
                        raise Stop('403 twice: stopping')
                    time.sleep(120)
                    continue
                if r.status_code >= 500:
                    if attempt < 3:
                        time.sleep(30 * (attempt + 1))
                        continue
                    raise Stop(f'{r.status_code} four times at {url}: stopping')
                if r.status_code == 200:
                    self.clean += 1
                return r
            return r

    def _note(self, url, status, size, t0):
        with open(self.log, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': now(), 'status': status, 'bytes': size, 'secs': round(time.time() - t0, 2),
                                'url': url[:300]}) + '\n')


NET: Net | None = None


def net() -> Net:
    global NET
    if NET is None:
        NET = Net()
    return NET


def _cached(name: str, url: str, accept: str, fetch: bool = True) -> bytes | None:
    p = CACHE / name
    if p.exists():
        b = gzip.decompress(p.read_bytes())
        return b or None
    if not fetch:
        return None
    r = net().get(url, accept)
    b = r.content if r.status_code == 200 else b''
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(b, 6, mtime=0))
    os.replace(tmp, p)
    return b or None


def norm_list(fetch: bool = True) -> list[dict]:
    out = []
    for off in (0, 5000, 10000, 15000):
        b = _cached(f'list/{off}.json.gz', f'{API}?limit=5000&offset={off}', 'application/json', fetch)
        if not b:
            break
        d = json.loads(b)['data']
        out += d
        if len(d) < 5000:
            break
    return out


def norm_path(ident: str) -> Path:
    return CACHE / 'id' / f'{ident}.xml.gz'


def norm_url(ident: str) -> str:
    return f'{API}/id/{ident}'


def fetch_norm(ident: str, fetch: bool = True) -> bytes | None:
    return _cached(f'id/{ident}.xml.gz', norm_url(ident), 'application/xml', fetch)


_LIST = None


def listing() -> dict[str, dict]:
    global _LIST
    if _LIST is None:
        _LIST = {d['identificador']: d for d in norm_list(fetch=False)}
    return _LIST


def robots_ids() -> set[str]:
    return set(ROBOTS_IDS.read_text(encoding='utf-8').split()) if ROBOTS_IDS.exists() else set()


def catalogue(u: str) -> list[dict]:
    """The unit's Autonómico norms in force, oldest first (BOE consolidated list), without robots-named ids."""
    deps = set(UNITS[u][3])
    skip = robots_ids()
    out = [d for d in listing().values() if d['ambito']['codigo'] == '2' and d['departamento']['codigo'] in deps
           and d.get('vigencia_agotada') != 'S' and d['identificador'] not in skip]
    return sorted(out, key=lambda d: (d.get('fecha_disposicion') or '', d.get('fecha_publicacion') or '',
                                      d['identificador']))


def plan(u: str) -> list[tuple[str, list[str]]]:
    out = [('10-estatuto', [UNITS[u][4]])]
    ids = [d['identificador'] for d in catalogue(u)]
    for i in range(0, len(ids), PART_SIZE):
        out.append((f'{30 + i // PART_SIZE}-normas-{i // PART_SIZE + 1:02d}', ids[i:i + PART_SIZE]))
    return out


# ---------------------------------------------------------------- parsing one norm

SPACE = re.compile(r'[\s  -​  　]+')
SOFT = re.compile('[­﻿]')
BOE_ID = re.compile(r'^BOE-[A-Z]-\d{4}-\d+$')


def iso(s: str | None) -> str | None:
    if not s or not re.fullmatch(r'\d{8}', s) or s.startswith('9999'):
        return None
    try:
        d = dt.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None
    return d.isoformat() if d.year >= 1800 else None


def clean(s: str) -> str:
    s = SPACE.sub(' ', SOFT.sub('', unicodedata.normalize('NFC', s))).strip()
    return s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')


def render(v: ET.Element) -> str:
    """One line per paragraph; a table one line per row, cells joined by ' | '."""
    lines = []

    def walk(e):
        tag = e.tag.split('}')[-1]
        if tag == 'table':
            def rows(t):
                for x in t:
                    xt = x.tag.split('}')[-1]
                    if xt == 'tr':
                        cells = [clean(''.join(td.itertext())) for td in x]
                        if any(cells):
                            lines.append(' | '.join(cells))
                    elif xt in ('thead', 'tbody', 'tfoot'):
                        rows(x)
                    else:
                        c = clean(''.join(x.itertext()))
                        if c:
                            lines.append(c)
            rows(e)
            return
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'pre', 'caption'):
            t = clean(''.join(e.itertext()))
            if t:
                lines.append(t)
            return
        kids = list(e)
        if not kids:
            t = clean(''.join(e.itertext()))
            if t:
                lines.append(t)
            return
        if (e.text or '').strip():
            lines.append(clean(e.text))
        for k in kids:
            walk(k)
            if (k.tail or '').strip():
                lines.append(clean(k.tail))

    for child in v:
        walk(child)
        if (child.tail or '').strip():
            lines.append(clean(child.tail))
    return ''.join(x + '\n' for x in lines if x)


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


ORD1 = {'primera': 1, 'primero': 1, 'segunda': 2, 'segundo': 2, 'tercera': 3, 'tercero': 3, 'cuarta': 4, 'cuarto': 4,
        'quinta': 5, 'quinto': 5, 'sexta': 6, 'sexto': 6, 'septima': 7, 'septimo': 7, 'setima': 7, 'octava': 8,
        'octavo': 8, 'novena': 9, 'noveno': 9}
ORD10 = {'decima': 10, 'decimo': 10, 'vigesima': 20, 'vigesimo': 20, 'trigesima': 30, 'trigesimo': 30,
         'cuadragesima': 40, 'cuadragesimo': 40, 'quincuagesima': 50, 'quincuagesimo': 50, 'sexagesima': 60,
         'sexagesimo': 60, 'septuagesima': 70, 'septuagesimo': 70, 'octogesima': 80, 'octogesimo': 80,
         'nonagesima': 90, 'nonagesimo': 90, 'centesima': 100}
SPECIAL = {'undecima': 11, 'undecimo': 11, 'duodecima': 12, 'duodecimo': 12}


def ordinal(words: str) -> int | None:
    w = ascii_slug(words).replace('-', ' ').split()
    if not w:
        return None
    if len(w) == 1:
        x = w[0]
        if x in ORD1:
            return ORD1[x]
        if x in ORD10:
            return ORD10[x]
        if x in SPECIAL:
            return SPECIAL[x]
        for t, tv in ORD10.items():
            if x.startswith(t[:-1]) and x[len(t) - 1:] in ORD1:  # decimotercera, vigesimoprimera
                return tv + ORD1[x[len(t) - 1:]]
        return None
    if len(w) == 2 and w[0] in ORD10 and w[1] in ORD1:
        return ORD10[w[0]] + ORD1[w[1]]
    return None


DISP = {'adicional': 'da', 'adicionales': 'da', 'transitoria': 'dt', 'transitorias': 'dt', 'transitora': 'dt',
        'derogatoria': 'dd', 'derogatorias': 'dd', 'final': 'df', 'finales': 'df'}


def _disp(kind: str, rest: str) -> str:
    if not rest:
        return kind
    if rest.startswith('unica') or rest.startswith('unico'):
        return f'{kind}-unica'
    n = ordinal(rest)
    if n is None:
        mm = re.match(r'^(\d+)(.*)$', rest)
        if mm:
            return f'{kind}-{int(mm.group(1)):02d}{mm.group(2)}'
        return f'{kind}-{rest}'
    return f'{kind}-{n:02d}'


def block_key(tipo: str, bid: str, titulo: str, heading: str = '') -> str:
    t = clean(titulo or '')
    a = ascii_slug(t)
    if tipo == 'preambulo' or bid == 'preambulo':
        return 'preambulo'
    if tipo == 'firma' or bid == 'firma':
        return 'firma'
    if tipo == 'nota_inicial':
        return 'nota-inicial'
    m = re.match(r'^art(?:iculos?|s?\.)?-?(\d+)-a-(\d+)$', a)
    if m:
        return f'art-{int(m.group(1)):03d}-a-{int(m.group(2)):03d}'
    m = re.match(r'^art(?:iculo|\.)?-?(\d+)(?:-(.*))?$', a)
    if m:
        rest = m.group(2) or ''
        return f'art-{int(m.group(1)):03d}' + (f'-{rest}' if rest else '')
    if a in ('articulo-unico', 'art-unico'):
        return 'art-unico'
    m = re.match(r'^disposicion-(adicional|transitoria|transitora|derogatoria|final)(?:-(.+))?$', a)
    if m:
        return _disp(DISP[m.group(1)], m.group(2) or '')
    h = ascii_slug(heading)
    mh = re.match(r'^disposiciones?-(adicionales|transitorias|derogatorias|finales|adicional|transitoria|derogatoria|'
                  r'final)$', h)
    if mh and (ordinal(a) is not None or a.startswith('unic')):
        return _disp(DISP[mh.group(1)], a)
    if a.startswith('anexo') or a.startswith('annex'):
        return a[:60].strip('-') or 'anexo'
    return 'b-' + (ascii_slug(bid) or 'bloque')


def unit_kind(tipo: str, key: str) -> str:
    if key == 'preambulo':
        return 'preamble'
    if key.startswith('art-'):
        return 'art'
    if key.startswith('dt-'):
        return 'transitional'
    if key.startswith(('da-', 'dd-', 'df-')):
        return 'disposition'
    if key.startswith('anexo'):
        return 'annex'
    if key == 'firma':
        return 'signature'
    if key == 'nota-inicial':
        return 'note'
    return 'heading' if tipo == 'encabezado' else 'other'


def law_key(ident: str) -> str:
    return ident.lower()


LABEL = re.compile(r'^(.*?\d+/\d{4},?\s+de\s+\d{1,2}\s+de\s+[a-záéíóú]+(?:\s+de\s+\d{4})?)', re.I)


def short_label(title: str) -> str:
    t = clean(title).rstrip('.')
    m = LABEL.match(t)
    s = m.group(1) if m else t
    return s if len(s) <= 120 else s[:117].rstrip() + '...'


def law_kind_of(label: str) -> str:
    low = label.lower()
    if low.startswith(('sentencia', 'auto ', 'pleno', 'cuestión', 'cuestion', 'recurso')):
        return 'court'
    if low.startswith(('decreto', 'real decreto', 'orden', 'resolución', 'resolucion', 'acuerdo', 'instrumento')) \
            and not low.startswith(('decreto-ley foral', 'decreto foral legislativo')):
        return 'decree'
    return 'law'


POR = re.compile(r'(?:^|,\s*|\s)por\s+(?:el |la |los |las )?((?:(?!,\s*por\s).)+)$')


def analisis_titles(root: ET.Element) -> dict[str, str]:
    out = {}
    for kind in ('posterior', 'anterior'):
        for r in root.iter(kind):
            i = (r.findtext('id_norma') or '').strip()
            t = clean(r.findtext('texto') or '')
            if not i or not t:
                continue
            if kind == 'posterior':
                m = POR.search(t)
                if m:
                    out.setdefault(i, m.group(1).strip())
            else:
                out.setdefault(i, t)
    return out


def law_entry(ident: str, pub: str | None, atitles: dict[str, str]) -> dict:
    d = listing().get(ident)
    if d:
        title = clean(d['titulo'])
        label = short_label(title)
        enacted = iso(d.get('fecha_disposicion'))
        pub = iso(d.get('fecha_publicacion')) or pub
        url = d.get('url_html_consolidada') or f'https://{HOST}/buscar/doc.php?id={ident}'
    elif ident in atitles:
        title = atitles[ident]
        label = short_label(title)
        enacted = None
        url = f'https://{HOST}/buscar/doc.php?id={ident}'
    else:
        title = label = ident
        enacted = None
        url = f'https://{HOST}/buscar/doc.php?id={ident}'
    if label != ident and ident not in label:
        label = f'{label} ({ident})'
    return {'label': label, 'title': title, 'kind': law_kind_of(title), 'enacted': enacted, 'published': pub,
            'url': url, 'temporary_until': None, 'restores': None, 'note': None}


def act_slug(title: str, ident: str, used: set) -> str:
    t = clean(title)
    m = re.match(r'^(.*?)\s+(\d+)/(\d{4})', t)
    if m:
        base = f'{ascii_slug(m.group(1))}-{m.group(3)}-{int(m.group(2)):03d}'
    else:
        base = ascii_slug(ident)
    base = base[:60].strip('-')
    s, n = base, 2
    while s in used or s in ('data', 'tools'):
        s = f'{base}-{n}'
        n += 1
    used.add(s)
    return s


def blocks_of(root: ET.Element) -> list[dict]:
    """Every block with its dated versions, in the BOE's order; versions sorted by (date, BOE order)."""
    out = []
    for b in root.iter('bloque'):
        vs = []
        for i, v in enumerate(b.findall('version')):
            d = iso(v.get('fecha_vigencia'))
            if not d:
                continue
            vs.append({'date': d, 'i': i, 'norma': (v.get('id_norma') or '').strip(),
                       'pub': iso(v.get('fecha_publicacion')), 'text': render(v)})
        vs.sort(key=lambda x: (x['date'], x['i']))
        out.append({'id': b.get('id') or '', 'tipo': b.get('tipo') or '', 'titulo': b.get('titulo') or '', 'vs': vs})
    return out


def groups_of(blocks: list[dict]) -> list[tuple[str, list[int]]]:
    """Units: each heading block (tipo encabezado) goes with the next non-heading block; trailing headings with the
    last unit. Returns [(unit key, [block indexes])] in document order, keys unique."""
    units: list[list] = []
    pending: list[int] = []
    heading = ''
    for i, b in enumerate(blocks):
        if b['tipo'] == 'encabezado':
            pending.append(i)
            heading = b['titulo'] or ''
            continue
        units.append([block_key(b['tipo'], b['id'], b['titulo'], heading), pending + [i], i])
        pending = []
    if pending:
        if units:
            units[-1][1].extend(pending)
        else:
            units.append(['encabezado', pending, pending[0]])
    seen: dict[str, int] = {}
    out = []
    for key, idxs, main in units:
        k = key
        if k in seen:
            seen[k] += 1
            k = f'{key}-{seen[key]}'
        else:
            seen[k] = 1
        out.append((k, idxs, main))
    return out


def parse_norm(ident: str, used: set, laws_seen: dict, statute: bool = False) -> tuple[dict, dict, dict] | None:
    raw = fetch_norm(ident, fetch=False)
    if not raw:
        return None
    root = ET.fromstring(raw)
    meta = root.find('data/metadatos')
    title = clean(meta.findtext('titulo') or ident)
    atitles = analisis_titles(root)
    blocks = blocks_of(root)
    groups = groups_of(blocks)
    dates = sorted({v['date'] for b in blocks for v in b['vs']})
    if not dates:
        return None
    sha = hashlib.sha256(raw).hexdigest()
    laws: dict[str, dict] = {}

    def need(i: str, pub: str | None) -> str | None:
        if not BOE_ID.match(i):
            return None
        k = law_key(i)
        if k in laws_seen:
            laws.setdefault(k, laws_seen[k])
        elif k not in laws:
            laws[k] = law_entry(i, pub, atitles)
        return k

    versions, prev_units, report = [], {}, Counter()
    prev_sel: dict[int, int] = {}
    for d in dates:
        sel = {}
        for bi, b in enumerate(blocks):
            cur = None
            for vi, v in enumerate(b['vs']):
                if v['date'] <= d:
                    cur = vi
            if cur is not None:
                sel[bi] = cur
        units = {}
        credits = {}
        for key, idxs, main in groups:
            present = [bi for bi in idxs if bi in sel]
            if not present:
                continue
            text = ''.join(blocks[bi]['vs'][sel[bi]]['text'] for bi in present)
            if not text:
                continue
            mb = blocks[main]
            units[key] = {'label': clean(mb['titulo']) or ('Preámbulo' if key == 'preambulo' else
                                                           'Firma' if key == 'firma' else
                                                           'Nota inicial' if key == 'nota-inicial' else key),
                          'kind': unit_kind(mb['tipo'], key), 'text': text}
            if prev_units.get(key, {}).get('text') != text:
                ls = []
                for bi in present:
                    if prev_sel.get(bi) != sel[bi]:
                        v = blocks[bi]['vs'][sel[bi]]
                        k = need(v['norma'], v['pub'])
                        if k and k not in ls:
                            ls.append(k)
                if ls:
                    credits[key] = ls
        gone = [k for k in prev_units if k not in units]
        changed = [k for k in units if prev_units.get(k, {}).get('text') != units[k]['text']] + gone
        if versions and not changed:
            prev_sel = sel
            continue
        if not versions:
            v = {'from': d, 'source_url': norm_url(ident), 'sha256': sha, 'units': units}
        else:
            v = {'from': d, 'source_url': norm_url(ident), 'sha256': sha,
                 'changes': {k: (units[k] if k in units else None) for k in changed},
                 'credits': {k: credits[k] for k in changed if k in credits}}
            report['unexplained'] += sum(1 for k in changed if k not in credits)
        versions.append(v)
        prev_units, prev_sel = units, sel
    first_norms = sorted({blocks[bi]['vs'][vi]['norma'] for bi, vi in _sel_at(blocks, dates[0]).items()})
    own = law_key(ident)
    pub0 = iso(meta.findtext('fecha_publicacion'))
    if first_norms == [ident]:
        first_law = need(ident, pub0)
        earlier = []
    else:
        first_law = None
        earlier = [k for k in (need(i, None) for i in first_norms) if k]
    slug = act_slug(title, ident, used) if not statute else ('lorafna' if 'Foral de Navarra' in title
                                                             else 'estatuto-de-autonomia')
    used.add(slug)
    act = {'slug': slug, 'short': short_label(title), 'title': title,
           'url': clean(meta.findtext('url_html_consolidada') or f'https://{HOST}/buscar/act.php?id={ident}'),
           'boe_id': ident, 'boe_updated': (meta.findtext('fecha_actualizacion') or '')[:8],
           'first_law': first_law, 'earlier_laws': earlier, 'versions': versions}
    report['versions'] = len(versions)
    report['blocks'] = len(blocks)
    report['undated_versions'] = sum(1 for b in root.iter('bloque') for v in b.findall('version')
                                     if not iso(v.get('fecha_vigencia')))
    return act, laws, dict(report)


def _sel_at(blocks, d):
    sel = {}
    for bi, b in enumerate(blocks):
        for vi, v in enumerate(b['vs']):
            if v['date'] <= d:
                sel[bi] = vi
    return sel


# ---------------------------------------------------------------- parts

def country_block(u: str) -> dict:
    en, native, code, _, _, tz = UNITS[u]
    return {
        'code': code, 'name': en, 'slug': f'spain-{u}', 'lang': 'es', 'tz': tz, 'future_branch': 'futuro',
        'publisher': {'name': 'Agencia Estatal Boletín Oficial del Estado, legislación consolidada (www.boe.es)',
                      'email': 'legislacion-consolidada@boe.es.invalid'},
        'default_in_force_rule': {
            'text': 'Each version takes effect on the fecha_vigencia that the BOE consolidated text gives the block '
                    'versions it contains.',
            'source': 'https://www.boe.es/datosabiertos/api/legislacion-consolidada'},
        'licence_note': ('Basado en datos de la Agencia Estatal Boletín Oficial del Estado, https://www.boe.es. '
                         'Consolidated texts are for information only (texto consolidado de carácter meramente '
                         'informativo). Laws and regulations are not protected by copyright in Spain (Ley de '
                         'Propiedad Intelectual, art. 13).'),
    }


AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which norms to include; it wrote no law text. '
          'Every word of law comes from the BOE consolidated texts.']


def decisions(u: str) -> list[str]:
    return [
        'Each act is one BOE consolidated text. Its versions are the distinct fecha_vigencia days of its block '
        'versions; each version holds, for every block, the latest block version in force on that day.',
        'Each change is credited to the norm the BOE names on the new block version (id_norma); a block version whose '
        'id_norma is not a BOE identifier is left uncredited (committed by the publisher as unexplained).',
        'Block versions without a real fecha_vigencia (empty or 99999999) cannot be placed in time and are left out. '
        'Where a block has two versions on one day, the last in the BOE\'s order is the text in force that day.',
        'Units: one file per article, disposition, annex, preamble and signature; the heading blocks (book, title, '
        'chapter, section) are kept at the top of the file of the block that follows them.',
        'A day whose block versions change no words is not a version.',
        'Included: the Estatuto de Autonomía (an Estatal Ley Orgánica), then the unit\'s Autonómico norms the BOE '
        'consolidates and marks as not exhausted (vigencia_agotada N), oldest first.',
        'An act\'s first commit is its first publication when every block of its earliest version comes from the act '
        'itself; otherwise it is the oldest version the BOE holds, naming the norms in it.',
    ]


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def source_block(retrieved: str) -> dict:
    return {'name': 'Agencia Estatal Boletín Oficial del Estado: legislación consolidada (open-data API)',
            'url': 'https://www.boe.es/datosabiertos/api/legislacion-consolidada', 'retrieved': retrieved,
            'licence': 'BOE reuse conditions (licencia tipo, Resolución de 27 de junio de 2024): reuse for commercial '
                       'and non-commercial purposes with attribution "Basado en datos de la Agencia Estatal Boletín '
                       'Oficial del Estado" and a link to https://www.boe.es; consolidated texts are informative only. '
                       'Ley de Propiedad Intelectual art. 13: laws and regulations are not protected.',
            'notes': 'The whole XML of each consolidated norm: metadata, analysis and every version of every block.'}


def parse_part(u: str, name: str, ids: list[str], docs_date: str) -> dict | None:
    out = folder(u) / 'corpus.d' / f'{name}.json'
    if out.with_suffix('.PUBLISH').exists():
        return {'skipped': 'published'}
    used, laws_seen = set(), {}
    for p in sorted((folder(u) / 'corpus.d').glob('*.json')) if (folder(u) / 'corpus.d').exists() else []:
        if p.stem == name:
            continue
        pj = json.loads(p.read_text(encoding='utf-8'))
        for a in pj.get('acts', []):
            used.add(a['slug'])
        for k, law in pj.get('laws', {}).items():
            laws_seen.setdefault(k, law)
    acts, laws, rep = [], {}, {}
    for ident in ids:
        if not norm_path(ident).exists():
            return None
        r = parse_norm(ident, used, laws_seen, statute=name == '10-estatuto')
        if r is None:
            rep[ident] = 'no text'
            continue
        a, l, rp = r
        acts.append(a)
        for k, v in l.items():
            laws.setdefault(k, v)
            laws_seen.setdefault(k, v)
        rep[a['slug']] = rp
    if not acts:
        return {'empty': rep}
    part = {'country': country_block(u), 'laws': dict(sorted(laws.items())), 'acts': acts}
    if name == '10-estatuto':
        part.update(sources=[source_block(docs_date)], decisions=decisions(u), ai_use=AI_USE)
    (folder(u) / 'corpus.d').mkdir(parents=True, exist_ok=True)
    write_part(out, part)
    return rep


# ---------------------------------------------------------------- checks (independent reader: lxml)

def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


def source_states(raw: bytes) -> dict[str, str]:
    """Independent of the parser: lxml, the version elements' whole text, the state of every block on every date."""
    from lxml import etree
    root = etree.fromstring(raw)
    blocks = []
    for b in root.iter('bloque'):
        vs = []
        for i, v in enumerate(b.findall('version')):
            f = v.get('fecha_vigencia') or ''
            if not re.fullmatch(r'\d{8}', f) or f.startswith('9999') or f < '18000101':
                continue
            try:
                dt.date(int(f[:4]), int(f[4:6]), int(f[6:]))
            except ValueError:
                continue
            vs.append((f'{f[:4]}-{f[4:6]}-{f[6:]}', i, ''.join(v.itertext())))
        vs.sort()
        blocks.append(vs)
    days = sorted({x[0] for vs in blocks for x in vs})
    out = {}
    for d in days:
        s = []
        for vs in blocks:
            cur = None
            for x in vs:
                if x[0] <= d:
                    cur = x[2]
            if cur is not None:
                s.append(cur)
        out[d] = letters(''.join(s))
    return out


def letters_check(u: str, part_name: str) -> list[str]:
    p = folder(u) / 'corpus.d' / f'{part_name}.json'
    part = json.loads(p.read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        raw = gzip.decompress(norm_path(act['boe_id']).read_bytes())
        if hashlib.sha256(raw).hexdigest() != act['versions'][0]['sha256']:
            probs.append(f'{act["slug"]}: sha256 differs from the cached source')
            continue
        states = source_states(raw)
        units = {}
        for v in act['versions']:
            if 'units' in v:
                units = dict(v['units'])
            else:
                for k, x in v['changes'].items():
                    if x is None:
                        units.pop(k, None)
                    else:
                        units[k] = x
            src = states.get(v['from'])
            if src is None:
                probs.append(f'{act["slug"]} {v["from"]}: no such day in the source')
                continue
            mine = letters(''.join(x['text'] for x in units.values()))
            if sorted(src) != sorted(mine):
                ca, cb = Counter(src), Counter(mine)
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((ca - cb).most_common(6))} '
                             f'corpus-only {dict((cb - ca).most_common(6))}')
                continue
            for k, x in units.items():
                if letters(x['text']) not in src:
                    probs.append(f'{act["slug"]} {v["from"]} {k}: text not found in order in the source')
                    break
    return probs


# ---------------------------------------------------------------- docs, scaffold, verify, publish

def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {x.strftime("%B")} {x.year}'


def _verified(u: str, extra=()) -> list[dict]:
    out = []
    for p in sorted((folder(u) / 'corpus.d').glob('*.json')):
        if p.with_suffix('.PUBLISH').exists() or p.stem in extra:
            out.append(json.loads(p.read_text(encoding='utf-8')))
    return out


def write_docs(u: str, docs_date: str, extra=(), out: Path | None = None):
    en, native, code, _, _, tz = UNITS[u]
    parts = _verified(u, extra)
    rows, nacts, nvers, nrep = [], 0, 0, 0
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = _long(vs[0]['from']) if len(vs) == 1 else f'{_long(vs[0]["from"])} to {_long(vs[-1]["from"])}'
            hist = ('as first published' if a.get('first_law') else 'oldest version available') + \
                (f', then each change: {span}' if len(vs) > 1 else f': {span}')
            if a.get('repealed'):
                nrep += 1
                by = ((part.get('laws') or {}).get(a['repealed']['by']) or {}).get('label') or a['repealed']['by']
                hist += f'; **repealed** {_long(a["repealed"]["on"])} by {by.replace("|", "/")}'
            upd =a.get('boe_updated') or ''
            upd = f'{upd[:4]}-{upd[4:6]}-{upd[6:8]}' if len(upd) == 8 else ''
            rows.append(f'| `{a["slug"]}/` | {a["title"].replace("|", "/")} | {len(vs)} | {hist} | {upd} |')
    city = u in CITY
    what = 'autonomous city' if city else 'autonomous community'
    has_laws = len(parts) > 1 or nacts > 1
    scope = ('the Estatuto de Autonomía (its statute of autonomy). As an autonomous city it makes no laws of its own '
             '(its assembly makes regulations, which the BOE does not consolidate)' if city else
             'the Estatuto de Autonomía first' + (', then the laws, decree-laws and legislative decrees in force that '
                                                 'the BOE consolidates, oldest first, added in parts of about 50'
                                                 if has_laws else '; its laws in force follow, in parts of about 50'))
    repealed_note = (f'{nrep} of them are repealed norms the BOE consolidates: their whole history is kept, and their last '
                     'commit removes the text on the day the repeal took effect, credited to the repealing norm. '
                     'Regulations are not included (the BOE consolidates no autonomic decrees or orders).'
                     if nrep else 'Regulations and repealed norms are not included.')
    if u == 'navarre':
        scope = scope.replace('the Estatuto de Autonomía', 'the Ley Orgánica de Reintegración y Amejoramiento del '
                              'Régimen Foral de Navarra (LORAFNA, its statute)')
    repo = out or (folder(u) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en}: law history in git

The law of the {what} of {en} ({native}, Spain) as a git history: one file per article, one commit per norm that changed it, dated the day the change took effect, with the amending norm as the commit's author. `git blame` names the norm behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{code.lower()}/`. Spain's national law is in [lexifina/spain-law](https://github.com/lexifina/spain-law).

The text is in Spanish, exactly as the BOE's consolidated text prints it. Texts in co-official languages are not included.

Basado en datos de la Agencia Estatal Boletín Oficial del Estado (<https://www.boe.es>). Every text here is a consolidated text for information only (texto consolidado de carácter meramente informativo), not an official publication.

## What this repository holds

{nacts} norm{"s" if nacts != 1 else ""} with {nvers} versions so far: {scope}. {repealed_note}

| Folder | Norm | Versions | History | BOE last updated |
| --- | --- | ---: | --- | --- |
{chr(10).join(rows)}

## Source

The consolidated legislation of the Agencia Estatal Boletín Oficial del Estado (BOE), through its open-data API, <https://www.boe.es/datosabiertos/api/legislacion-consolidada>. For each consolidated norm it gives every block of the text (article, disposition, annex, heading) with every version of that block, the day each version took effect (fecha_vigencia) and the norm that made it (id_norma). Each version here is the whole text as it stood on one of those days. The last column above is the BOE's own last-update date for the consolidated text.

## Dates

- Each commit is dated at **noon, {tz}, on the day the change took effect**: the fecha_vigencia the BOE gives the new block versions.
- A day on which the BOE records a new block version that changes no words is not a version here.
- Block versions with no in-force date (the BOE's 99999999, a date not yet fixed) are left out.
- An act's first commit is its first publication when the BOE's earliest text is the act as enacted; otherwise it is the oldest version the BOE holds.
- Versions that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.

## Files

`<act>/art-005.md` is Artículo 5, `art-005-bis.md` Artículo 5 bis; `da-01.md` the Disposición adicional primera, `dt-` transitional, `dd-` repealing and `df-` final dispositions (`-unica` for "única"); `preambulo.md` the preamble, `firma.md` the signature, `anexo-*.md` the annexes. The book, title, chapter and section headings sit at the top of the file of the article that follows them. One paragraph per line; a table one line per row, cells separated by ` | `.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the BOE's own text of that day, rebuilt from the source XML by a separate reader, and every file's text appears in it.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

The author of a commit is the norm that changed the text (a law, a decree-law, a ruling of the Constitutional Court), named by its title and BOE identifier, with an e-mail address that cannot exist (`<boe id>@boe.es.invalid`). The committer is always Lexifina.

## Limits

This is not an official publication. Only the texts published in the official journals are authentic. The history starts with the oldest text the BOE consolidates for each norm. Only the norms listed above are included; norms the BOE does not consolidate are not.
"""
    lic = f"""The law texts in this repository are official texts of the {what} of {en} ({native}, Spain) and of
the Spanish State, taken from the consolidated legislation of the Agencia Estatal Boletín Oficial del Estado (BOE),
https://www.boe.es/datosabiertos/api/legislacion-consolidada (consulted {docs_date}).

Spanish law does not protect them by copyright. Ley de Propiedad Intelectual (Real Decreto Legislativo 1/1996),
artículo 13: "No son objeto de propiedad intelectual las disposiciones legales o reglamentarias y sus correspondientes
proyectos, las resoluciones de los órganos jurisdiccionales y los actos, acuerdos, deliberaciones y dictámenes de los
organismos públicos, así como las traducciones oficiales de todos los textos anteriores." (Laws and regulations, court
decisions and the acts of public bodies, and their official translations, are not subject to intellectual property.)

The BOE's reuse conditions (licencia tipo approved by Resolución of 27 June 2024,
https://www.boe.es/informacion/aviso_legal/index.php#reutilizacion) allow reuse for commercial and non-commercial
purposes, including copying, distribution, extraction, rearrangement and combination into derived works, provided
the source is cited, the meaning is not altered, the information is not presented as official, consolidated texts
are marked as informative only, and the last update date is given. Accordingly:

  Basado en datos de la Agencia Estatal Boletín Oficial del Estado (https://www.boe.es).

  Every text in this repository is a consolidated text for information only ("texto consolidado de carácter
  meramente informativo"). The BOE's last-update date for each text is listed in README.md. The Agencia Estatal
  Boletín Oficial del Estado does not take part in, sponsor or endorse this repository.

What is not the BOE's: the division of each text into one file per article (headings kept with the article that
follows them), the history as git commits, the commit messages, the tables and the tools are Lexifina's. The words of
each text are the BOE's, unchanged except for spacing (one paragraph per line; table cells separated by " | ").

Lexifina's own contributions are dedicated to the public domain under CC0 1.0 Universal:
https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': code.lower(), 'code': code, 'name': en, 'level': 'autonomous city' if city else
             'autonomous community', 'parent': 'es', 'repo': f'https://github.com/lexifina/{repo_name(u)}',
             'build': f'built: statute of autonomy{"" if city else " and laws"} ({nacts} norms, {nvers} versions) '
                      'from BOE legislación consolidada',
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


def scaffold(u: str) -> str:
    import tempfile
    en, native, code, _, _, _ = UNITS[u]
    repo = repo_name(u)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    if run('gh', 'api', f'repos/lexifina/{repo}', check=False).returncode != 0:
        run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
            '-f', f'description={en} (Spain) law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    run('git', 'init', '-q', '-b', 'main', cwd=d)
    (d / 'README.md').write_text(f"""# {en}: law as git history

Work in progress. This repository will hold the law of {en} ({native}, Spain) as a git history: one file per
article, one commit per norm that changed it, on the day it took effect, `git blame` and `git log` working line by
line.

Planned first build: the {"Estatuto de Autonomía" if u != "navarre" else "LORAFNA (the statute of Navarre)"}, then
{"its other norms" if u in CITY else "the laws in force"}, with every dated version of the BOE's consolidated legislation.

Source: Agencia Estatal Boletín Oficial del Estado, <https://www.boe.es>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text("""# Sources

- Agencia Estatal Boletín Oficial del Estado, legislación consolidada: <https://www.boe.es/datosabiertos/>

Laws and regulations are not protected by copyright in Spain (Ley de Propiedad Intelectual, art. 13). The BOE's
reuse conditions and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    run('git', 'add', '-A', cwd=d)
    run('git', '-c', 'user.name=Lexifina', '-c', 'user.email=world-law@lexifina.com', 'commit', '-q', '-m',
        f'Spain ({en}): sources, before any law', cwd=d)
    run('git', 'remote', 'add', 'origin', remote, cwd=d)
    for attempt in range(4):
        p = run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
        if p.returncode == 0:
            break
        time.sleep(10 * (attempt + 1))
    _rm(d)
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


def verify_part(u: str, part: str, docs_date: str) -> tuple[bool, str]:
    probs = letters_check(u, part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[0]}'
    src = folder(u)
    tmp = DOCS / f'{repo_name(u)}-verify'
    build = DOCS / f'{repo_name(u)}-verifybuild'
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()] + [part]
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(u, docs_date, extra=[part], out=tmp / 'repo')
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
    nv = sum(len(a['versions']) for a in acts)
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} norm(s), {nv} versions {days[0]}..{days[-1]} from BOE legislación consolidada: letters and '
            f'digits of every version equal the BOE XML state of that day (independent lxml reader) and every unit is '
            f'found in it; scratch build of verified parts + this part: check.py {res["versions"]} versions, '
            f'0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return True, line


def publish(u: str, part: str, docs_date: str) -> str:
    ok, line = verify_part(u, part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    pub = folder(u) / 'corpus.d' / f'{part}.PUBLISH'
    tmp = pub.with_suffix('.ptmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    write_docs(u, docs_date, extra=[part])
    os.replace(tmp, pub)
    top = folder(u) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


# ---------------------------------------------------------------- driver

def claim(u: str) -> bool:
    p = CLAIMS / f'{repo_name(u)}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'{SESSION} {now()} (Spanish autonomous communities and cities via BOE legislación consolidada)\n')
        return True
    except FileExistsError:
        return p.read_text(encoding='utf-8', errors='replace').startswith(SESSION)


def progress(u: str, line: str):
    p = folder(u) / 'PROGRESS.md'
    if not p.exists():
        p.write_text(f'# {repo_name(u)} (private progress, gitlaw-scraper-dell)\n\nBuilder: '
                     'scripts/world-law/es_ccaa.py; source BOE legislación consolidada (open-data API).\n\n',
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


class Builder:
    """Parses, verifies and marks parts one at a time in a background thread (subprocess at BelowNormal)."""

    def __init__(self, docs_date: str):
        import queue
        self.q = queue.Queue()
        self.docs_date = docs_date
        self.t = threading.Thread(target=self.loop, daemon=True)
        self.t.start()

    def loop(self):
        while True:
            u, name = self.q.get()
            while not cpu_ok():
                time.sleep(60)
            p = _low([sys.executable, '-X', 'utf8', str(Path(__file__)), 'partpub', u, name, self.docs_date])
            out = (p.stdout.strip().splitlines() or [''])[-1] + (p.stderr.strip()[-300:] if p.returncode else '')
            say(f'[build] {u} {name}: {out[:400]}')
            progress(u, f'{name}: {out[:600]}')
            self.q.task_done()


def part_publish(u: str, name: str, docs_date: str) -> str:
    ids = dict(plan(u)).get(name)
    rep = parse_part(u, name, ids, docs_date)
    if rep is None:
        return 'not fetched yet'
    if 'empty' in rep:
        return 'no text in any norm of the part: ' + json.dumps(rep)[:200]
    if 'skipped' in rep:
        return 'already published'
    (folder(u) / '.tmp').mkdir(exist_ok=True)
    (folder(u) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                           encoding='utf-8')
    return publish(u, name, docs_date)


def drive(units: list[str], docs_date: str, max_parts: int | None):
    builder = Builder(docs_date)
    active, plans = [], {}
    try:
        norm_list(fetch=True)
        # round 1: claim, scaffold and Estatuto, unit by unit
        for u in units:
            if not claim(u):
                say(f'{u}: claimed by another session, skipped')
                continue
            active.append(u)
            folder(u).mkdir(exist_ok=True)
            gi = folder(u) / '.gitignore'
            if not gi.exists():
                gi.write_text('.cache/\n.tmp/\n', encoding='utf-8', newline='\n')
            say(f'{u}: scaffold {scaffold(u)}')
            plans[u] = plan(u)
            progress(u, f'catalogue: Estatuto + {len(catalogue(u))} norms in force; {len(plans[u])} parts')
            name, ids = plans[u][0]
            for i in ids:
                fetch_norm(i)
            builder.q.put((u, name))
            say(f'{u}: Estatuto fetched ({net().count} requests so far)')
        # round 2..: one more part per unit per round
        k = 1
        while True:
            more = False
            for u in active:
                ps = plans[u][1:]
                if k - 1 < len(ps) and (max_parts is None or k <= max_parts):
                    more = True
                    name, ids = ps[k - 1]
                    if (folder(u) / 'corpus.d' / f'{name}.PUBLISH').exists():
                        continue
                    for i in ids:
                        while not cpu_ok():
                            time.sleep(60)
                        fetch_norm(i)
                    builder.q.put((u, name))
                    say(f'{u}: {name} fetched ({len(ids)} norms; {net().count} requests so far)')
            if not more:
                break
            k += 1
    except Stop as e:
        say(f'STOPPED: {e}')
    builder.q.join()
    say('done')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1]
    if cmd == 'run':
        args = sys.argv[2:]
        mp = None
        if args and args[0].startswith('--max-parts='):
            mp = int(args[0].split('=')[1])
            args = args[1:]
        drive(args or list(UNITS), dt.date.today().isoformat(), mp)
    elif cmd == 'partpub':
        print(part_publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'parse':
        print(json.dumps(parse_part(sys.argv[2], sys.argv[3], dict(plan(sys.argv[2]))[sys.argv[3]], sys.argv[4]),
                         ensure_ascii=False)[:3000])
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
    elif cmd == 'plan':
        for u in sys.argv[2:] or list(UNITS):
            print(u, [(n, len(i)) for n, i in plan(u)])
