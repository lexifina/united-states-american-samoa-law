"""Mexican states and Mexico City for git-for-law (gitlaw-scraper-dell, coverage wave 2026-10-30): one public repo per
unit, lexifina/mexico-<state>-law, built by scripts/gitlaw_common/build.py from corpus.d parts.

Source: the SCJN's legislation compilation (Suprema Corte de Justicia de la Nación, "Legislación",
legislacion.scjn.gob.mx), which holds, for each state law, every publication that changed it (decree, erratum,
ruling) with the whole consolidated text as it stood after that publication (a Word file) and an extract of the
decree with its transitorios. One fetch process for the host, shared by every state; one request at a time per
thread, a pause between request starts, stops on any challenge.

    python -X utf8 scripts/world-law/mx_states.py run <slug> ...       # claim, scaffold, fetch, parse, verify, publish
    python -X utf8 scripts/world-law/mx_states.py parse <slug>
    python -X utf8 scripts/world-law/mx_states.py publish <slug> <part> <docs-date>
    python -X utf8 scripts/world-law/mx_states.py letters <slug> <part>

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
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # scripts/
DOCS = ROOT.parent.parent                           # ~/Documents
HERE = Path(__file__).resolve().parent
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
HOST = 'legislacion.scjn.gob.mx'
BASE = f'https://{HOST}/Buscador/Paginas/'
PAUSE = 1.0                                          # seconds between request starts on the host
THREADS = 2                                          # Word downloads at once (one process)
PART_SIZE = 50
SESSION = 'gitlaw-scraper-dell'
CLAIMS = HERE / 'claims'

# slug: (SCJN entidad index (None = Ciudad de México ambito), English name, official name, ISO 3166-2, tz,
#        default in-force rule in days after publication when a decree states none (None = not stated by SCJN))
STATES = {
    'state-of-mexico': (10, 'State of Mexico', 'Estado Libre y Soberano de México', 'MX-MEX', 'America/Mexico_City', None),
    'mexico-city': (None, 'Mexico City', 'Ciudad de México', 'MX-CMX', 'America/Mexico_City', None),
    'jalisco': (14, 'Jalisco', 'Estado Libre y Soberano de Jalisco', 'MX-JAL', 'America/Mexico_City', None),
    'veracruz': (29, 'Veracruz', 'Estado Libre y Soberano de Veracruz de Ignacio de la Llave', 'MX-VER', 'America/Mexico_City', 3),
    'puebla': (20, 'Puebla', 'Estado Libre y Soberano de Puebla', 'MX-PUE', 'America/Mexico_City', 3),
    'guanajuato': (11, 'Guanajuato', 'Estado Libre y Soberano de Guanajuato', 'MX-GUA', 'America/Mexico_City', None),
    'nuevo-leon': (18, 'Nuevo León', 'Estado Libre y Soberano de Nuevo León', 'MX-NLE', 'America/Monterrey', 0),
    'chiapas': (5, 'Chiapas', 'Estado Libre y Soberano de Chiapas', 'MX-CHP', 'America/Mexico_City', None),
    'michoacan': (15, 'Michoacán', 'Estado Libre y Soberano de Michoacán de Ocampo', 'MX-MIC', 'America/Mexico_City', None),
    'oaxaca': (19, 'Oaxaca', 'Estado Libre y Soberano de Oaxaca', 'MX-OAX', 'America/Mexico_City', 0),
    'chihuahua': (6, 'Chihuahua', 'Estado Libre y Soberano de Chihuahua', 'MX-CHH', 'America/Chihuahua', None),
    'guerrero': (12, 'Guerrero', 'Estado Libre y Soberano de Guerrero', 'MX-GRO', 'America/Mexico_City', 0),
    'baja-california': (2, 'Baja California', 'Estado Libre y Soberano de Baja California', 'MX-BCN', 'America/Tijuana', None),
    'tamaulipas': (27, 'Tamaulipas', 'Estado Libre y Soberano de Tamaulipas', 'MX-TAM', 'America/Matamoros', None),
    'sinaloa': (24, 'Sinaloa', 'Estado Libre y Soberano de Sinaloa', 'MX-SIN', 'America/Mazatlan', 3),
    'coahuila': (7, 'Coahuila', 'Estado Independiente, Libre y Soberano de Coahuila de Zaragoza', 'MX-COA', 'America/Monterrey', 3),
    'sonora': (25, 'Sonora', 'Estado Libre y Soberano de Sonora', 'MX-SON', 'America/Hermosillo', None),
    'hidalgo': (13, 'Hidalgo', 'Estado Libre y Soberano de Hidalgo', 'MX-HID', 'America/Mexico_City', None),
    'san-luis-potosi': (23, 'San Luis Potosí', 'Estado Libre y Soberano de San Luis Potosí', 'MX-SLP', 'America/Mexico_City', None),
    'tabasco': (26, 'Tabasco', 'Estado Libre y Soberano de Tabasco', 'MX-TAB', 'America/Mexico_City', None),
    'yucatan': (30, 'Yucatán', 'Estado Libre y Soberano de Yucatán', 'MX-YUC', 'America/Merida', None),
    'queretaro': (21, 'Querétaro', 'Estado Libre y Soberano de Querétaro', 'MX-QUE', 'America/Mexico_City', None),
    'morelos': (16, 'Morelos', 'Estado Libre y Soberano de Morelos', 'MX-MOR', 'America/Mexico_City', None),
    'durango': (9, 'Durango', 'Estado Libre y Soberano de Durango', 'MX-DUR', 'America/Monterrey', None),
    'quintana-roo': (22, 'Quintana Roo', 'Estado Libre y Soberano de Quintana Roo', 'MX-ROO', 'America/Cancun', None),
    'zacatecas': (31, 'Zacatecas', 'Estado Libre y Soberano de Zacatecas', 'MX-ZAC', 'America/Mexico_City', None),
    'aguascalientes': (1, 'Aguascalientes', 'Estado Libre y Soberano de Aguascalientes', 'MX-AGU', 'America/Mexico_City', None),
    'tlaxcala': (28, 'Tlaxcala', 'Estado Libre y Soberano de Tlaxcala', 'MX-TLA', 'America/Mexico_City', 1),
    'nayarit': (17, 'Nayarit', 'Estado Libre y Soberano de Nayarit', 'MX-NAY', 'America/Mazatlan', None),
    'campeche': (4, 'Campeche', 'Estado Libre y Soberano de Campeche', 'MX-CAM', 'America/Merida', None),
    'colima': (8, 'Colima', 'Estado Libre y Soberano de Colima', 'MX-COL', 'America/Mexico_City', None),
    'baja-california-sur': (3, 'Baja California Sur', 'Estado Libre y Soberano de Baja California Sur', 'MX-BCS', 'America/Mazatlan', None),
}
# The name SCJN prints in each result's "Estado:" field (to confirm the entidad index).
SCJN_NAME = {'state-of-mexico': 'ESTADO DE MEXICO', 'nuevo-leon': 'NUEVO LEON', 'michoacan': 'MICHOACAN',
             'san-luis-potosi': 'SAN LUIS POTOSI', 'yucatan': 'YUCATAN', 'queretaro': 'QUERETARO',
             'quintana-roo': 'QUINTANA ROO', 'baja-california': 'BAJA CALIFORNIA',
             'baja-california-sur': 'BAJA CALIFORNIA SUR'}
DEFAULT_DAYS = 3   # when neither the decree nor SCJN's note on the state gives a rule


def repo_name(slug: str) -> str:
    return f'mexico-{slug}-law'


def folder(slug: str) -> Path:
    return ROOT / repo_name(slug)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---------------------------------------------------------------- fetching (one process for the host)

class Stop(Exception):
    pass


class Net:
    def __init__(self):
        import requests
        self.local = threading.local()
        self.lock = threading.Lock()
        self.last = 0.0
        self.count = 0
        self.forbidden = 0
        self.requests = requests
        self.log = HERE / 'logs' / 'mx-scjn-requests.jsonl'
        self.log.parent.mkdir(exist_ok=True)

    def session(self):
        s = getattr(self.local, 's', None)
        if s is None:
            s = self.requests.Session()
            s.headers['User-Agent'] = UA
            s.headers['Accept-Encoding'] = 'gzip'
            self.local.s = s
        return s

    def _pace(self):
        with self.lock:
            wait = self.last + PAUSE - time.time()
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.count += 1

    def request(self, method: str, url: str, data: dict | None = None):
        if os.environ.get('MX_OFFLINE') == '1':   # offline re-parse/verify: never touch the host
            raise Stop(f'offline mode, no request made: {url[:120]}')
        for attempt in range(4):
            self._pace()
            t0 = time.time()
            try:
                r = self.session().request(method, url, data=data, timeout=240)
            except self.requests.RequestException as e:
                self._note(method, url, 0, 0, t0)
                if attempt == 3:
                    raise
                time.sleep(15 * (attempt + 1))
                continue
            self._note(method, url, r.status_code, len(r.content), t0)
            head = r.content[:4000].lower()
            if b'incapsula incident' in head or b'request unsuccessful' in head or (
                    b'_incapsula_resource' in head and b'<title>' not in head and r.status_code != 404):
                raise Stop(f'bot challenge at {url}: stopping (never get round one)')
            if r.status_code == 429:
                raise Stop('429 from the host: stopping')
            if r.status_code == 403:
                self.forbidden += 1
                if self.forbidden >= 2:
                    raise Stop('403 twice: stopping')
                time.sleep(60)
                continue
            if r.status_code >= 500 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            return r
        return r

    def _note(self, method, url, status, size, t0):
        with self.lock:
            with open(self.log, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': now(), 'm': method, 'status': status, 'bytes': size,
                                    'secs': round(time.time() - t0, 2), 'url': url[:300]}) + '\n')


NET: Net | None = None


def net() -> Net:
    global NET
    if NET is None:
        NET = Net()
    return NET


def ckey(*parts: str) -> str:
    return hashlib.sha1('\x1f'.join(parts).encode('utf-8')).hexdigest()


def cache_dir(slug: str) -> Path:
    d = folder(slug) / '.cache'
    d.mkdir(parents=True, exist_ok=True)
    gi = folder(slug) / '.gitignore'
    if not gi.exists():
        gi.write_text('.cache/\n', encoding='utf-8', newline='\n')
    return d


def store(slug: str, sub: str, k: str, ext: str, body: bytes) -> None:
    p = cache_dir(slug) / sub / f'{k}.{ext}.gz'
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(body, 6, mtime=0))
    os.replace(tmp, p)


def load(slug: str, sub: str, k: str, ext: str) -> bytes | None:
    p = cache_dir(slug) / sub / f'{k}.{ext}.gz'
    return gzip.decompress(p.read_bytes()) if p.exists() else None


def cpath(slug: str, sub: str, url: str, ext: str) -> Path:
    return cache_dir(slug) / sub / f'{ckey(url)}.{ext}.gz'


def cached_get(slug: str, url: str, sub: str, ext: str) -> bytes | None:
    """GET once; the body (or b'' for an error answer) is stored gzipped. None for an error answer."""
    p = cpath(slug, sub, url, ext)
    if p.exists():
        b = gzip.decompress(p.read_bytes())
        return b or None
    r = net().request('GET', url)
    b = r.content if r.status_code == 200 else b''
    if ext == 'docx' and b and not b.startswith(b'PK'):
        b = b''
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(b, 6, mtime=0))
    os.replace(tmp, p)
    return b or None


def form_fields(page: str) -> dict:
    out = {}
    for m in re.finditer(r'<input[^>]*>', page):
        tag = m.group(0)
        n = re.search(r'name="([^"]*)"', tag)
        if not n:
            continue
        t = re.search(r'type="([^"]*)"', tag)
        t = t.group(1).lower() if t else 'text'
        if t in ('submit', 'image', 'button'):
            continue
        if t in ('checkbox', 'radio') and 'checked' not in tag:
            continue
        v = re.search(r'value="([^"]*)"', tag)
        out[htmlmod.unescape(n.group(1))] = htmlmod.unescape(v.group(1)) if v else ('on' if t in ('checkbox', 'radio') else '')
    for m in re.finditer(r'<select[^>]*name="([^"]*)"[^>]*>(.*?)</select>', page, re.S):
        sel = (re.search(r'<option[^>]*selected[^>]*value="([^"]*)"', m.group(2))
               or re.search(r'<option[^>]*value="([^"]*)"', m.group(2)))
        out[htmlmod.unescape(m.group(1))] = htmlmod.unescape(sel.group(1)) if sel else ''
    return out


def postback(page: str, target: str, argument: str, url: str):
    f = form_fields(page)
    f.pop('q', None)
    f['__EVENTTARGET'] = target
    f['__EVENTARGUMENT'] = argument
    m = re.search(r'<form name="aspnetForm" method="post" action="([^"]*)"', page)
    a = htmlmod.unescape(m.group(1)) if m else url
    action = BASE + a[2:] if a.startswith('./') else (a if a.startswith('http') else url)
    return net().request('POST', action, data=f)


def strip(s: str) -> str:
    return re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


# catalogue: tipo CONSTITUCION (250) / CODIGO (190) / LEY (530), in force, the state's entidad, 50 a page
TYPES = [('250', 'constitucion', 'CONSTITUCION'), ('190', 'codigo', 'CODIGO'), ('530', 'ley', 'LEY')]


def result_records(page: str) -> list[dict]:
    out = []
    for m in re.finditer(r'href="?(wfOrdenamientoDetalle\.aspx\?q=[^"\s>]+)"?[^>]*>(.*?)</a>(.*?)(?=href="?wfOrdenamientoDetalle\.aspx\?q=|Cargando)',
                         page, re.S):
        whole = strip(m.group(2))
        title, _, rest = whole.partition('Última actualizaci')
        rest = 'actualizaci' + rest
        upd = re.search(r'actualizaci.n:\s*(\d\d/\d\d/\d{4})', rest)
        vig = re.search(r'Vigencia:\s*([A-Z ()]+?)\s*Ambito', rest)
        edo = re.search(r'Estado:\s*([A-ZÁÉÍÓÚÑ ]+?)\s*(?:Ver |$)', rest)
        amb = re.search(r'Ambito:\s*([A-ZÁÉÍÓÚÑ ]+?)\s*(?:Estado:|Ver |$)', rest)
        out.append({'q': htmlmod.unescape(m.group(1)).split('q=', 1)[1], 'title': title.strip(),
                    'updated': upd.group(1) if upd else '', 'vigencia': vig.group(1).strip() if vig else '',
                    'estado': edo.group(1).strip() if edo else '', 'ambito': amb.group(1).strip() if amb else ''})
    return out


def search(slug: str, tipo: str, name: str, word: str) -> list[dict]:
    got = load(slug, 'catalogue', f'{name}-all', 'json')
    if got:
        return json.loads(got)
    edo = STATES[slug][0]
    b, e = (6, -1) if edo is None else (1, edo)
    u = (BASE + f'wfResultados.aspx?TPub=6&search={word}&t=1&c=0&x=0&l=0&u=1&r=0&p=0&o=0&b={b}&rn=6&d={tipo}'
         f'&v=1&m=-1&fi=&ff=&edo={e}&sort=2&a=0&page=50&rID=')
    r = net().request('GET', u)
    page, url = r.text, r.url
    m = re.search(r'Se localizaron\s*(?:<[^>]+>\s*)*(\d+)', page)
    n = int(m.group(1)) if m else 0
    out = result_records(page)
    pager = sorted(set(re.findall(r"__doPostBack\(&#39;([^&]*[Pp]ager[^&]*)&#39;", page)))
    k = 1
    while len(out) < n:
        if not pager:
            raise RuntimeError(f'{slug} {name}: no pager')
        r = postback(page, pager[0], f'PN{k}', url)
        page = r.text
        k += 1
        more = result_records(page)
        if not more or more[0]['q'] in {o['q'] for o in out}:
            raise RuntimeError(f'{slug} {name}: page {k} brought nothing new')
        out += more
    if len(out) != n:
        raise RuntimeError(f'{slug} {name}: {len(out)} of {n}')
    store(slug, 'catalogue', f'{name}-all', 'json', json.dumps(out, ensure_ascii=False).encode('utf-8'))
    return out


def fold(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()


def catalogue(slug: str, fetch: bool = True) -> dict[str, list[dict]] | None:
    out = {}
    for tipo, name, word in TYPES:
        if not fetch and not load(slug, 'catalogue', f'{name}-all', 'json'):
            return None
        rows = search(slug, tipo, name, word)
        want = SCJN_NAME.get(slug, fold(STATES[slug][1]))
        keep = []
        for r in rows:
            if STATES[slug][0] is None:
                if 'CIUDAD DE M' not in fold(r['ambito']) and r['ambito']:
                    continue
            elif fold(r['estado']) != want:
                continue
            if r['vigencia'] and r['vigencia'] != 'VIGENTE':
                continue
            t = fold(r['title'])
            if name == 'codigo' and re.search(r'\b(CONDUCTA|ETICA)\b', t):
                continue
            if name == 'ley' and not t.startswith('LEY'):
                continue
            if name == 'constitucion' and not t.startswith('CONSTITUCION'):
                continue
            r['type'] = name
            keep.append(r)
        # a stable order: by title, then the SCJN id
        keep.sort(key=lambda r: (fold(r['title']), r['q']))
        out[name] = keep
    return out


def grid_records(page: str) -> list[dict]:
    def span(cell, name):
        m = re.search(rf'_{name}"[^>]*>(.*?)</span>', cell, re.S)
        return strip(m.group(1)) if m else ''

    def link(cell, name):
        m = re.search(rf'_{name}"[^>]*>\s*<a href="?([^"\s>]+)', cell)
        return htmlmod.unescape(m.group(1)) if m else ''
    out = []
    for row in re.split(r'<tr id="ctl00_MainContentPlaceHolder_gridReformas_DXDataRow\d+"', page)[1:]:
        reg = span(row, 'lbNoRegistro')
        if not reg:
            continue
        out.append({'reg': reg, 'pub': span(row, 'lbFechaPub'), 'exp': span(row, 'lbFechaExpedicion'),
                    'cat': span(row, 'lbCategoria'), 'num': span(row, 'lbSecPublicacion'),
                    'word': link(row, 'lbTextoCompletoWord'), 'extracto': link(row, 'lbExtracto')})
    return out


PAGER = 'ctl00$MainContentPlaceHolder$pagerGridReformas'


def law_records(slug: str, law: dict) -> dict:
    k = ckey(law['q'])
    got = load(slug, 'laws', k, 'json')
    if got:
        return json.loads(got)
    url = BASE + 'wfOrdenamientoDetalle.aspx?q=' + law['q']
    r = net().request('GET', url)
    page = r.text
    m = re.search(r'\[(\d+) Registros en total\]', page)
    n = int(m.group(1)) if m else None
    recs = grid_records(page)
    p = 1
    while n is not None and len(recs) < n:
        r = postback(page, PAGER, f'PN{p}', r.url)
        page = r.text
        p += 1
        more = grid_records(page)
        if not more or more[0]['reg'] in {x['reg'] for x in recs}:
            raise RuntimeError(f"{law['title'][:60]}: page {p} brought nothing new")
        recs += more
    d = {'q': law['q'], 'title': law['title'], 'type': law['type'], 'url': url, 'total': n, 'records': recs}
    if n is None or len(recs) != n:
        # a page without the records grid (seen just before SCJN's block on 2026-10-31) is never cached as a law
        # with no versions; the part is left for a later run
        raise RuntimeError(f"{law['title'][:60]}: {len(recs)} records of {n} (page without the records grid)")
    store(slug, 'laws', k, 'json', json.dumps(d, ensure_ascii=False).encode('utf-8'))
    return d


def fetch_law(slug: str, law: dict, pool) -> dict:
    d = law_records(slug, law)
    futs = []
    for rec in d['records']:
        if rec['extracto']:
            futs.append(pool.submit(cached_get, slug, BASE + rec['extracto'], 'extracto', 'html'))
        if rec['word']:
            futs.append(pool.submit(cached_get, slug, BASE + rec['word'], 'word', 'docx'))
    for f in futs:
        f.result()
    return d


def law_fetched(slug: str, law: dict) -> dict | None:
    """The records of a law whose every extract and Word file is cached; None otherwise."""
    got = load(slug, 'laws', ckey(law['q']), 'json')
    if not got:
        return None
    d = json.loads(got)
    for rec in d['records']:
        for f, sub, ext in (('extracto', 'extracto', 'html'), ('word', 'word', 'docx')):
            if rec[f] and not cpath(slug, sub, BASE + rec[f], ext).exists():
                return None
    return d


# ---------------------------------------------------------------- parsing one Word text

SPACE = re.compile(r'[\s\u00a0\u2000-\u200b\u202f\u205f\u3000]+')
SOFT = re.compile('[\u00ad\ufeff]')
# every "ÚLTIMA REFORMA ..." banner variant ("... PÚBLICADA EN EL PERÍODICO OFICIAL", "... DEL PERIÓDICO OFICIAL"):
# exactly what the letters check leaves out of SCJN's text (BANNER_CHECK)
BANNER = re.compile(r'^(TEXTO ORIGINAL\.?|[ÚU]LTIMA REFORMA\b.*)$', re.I)
ORD = (r'(?:[ÚU]NICO|PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|SETIMO|OCTAVO|NOVENO|D[ÉE]CIMO'
       r'(?:\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO))?|UND[ÉE]CIMO|DUOD[ÉE]CIMO)')
LATIN = (r'(?:BIS|TER|QU[ÁA]TER|QUAT|QUINQUIES|QUINTUS|QUINTO|SEX[IÍ]ES|SEXTUS|SEPTIES|S[ÉE]PTIMUS|OCTIES|OCTAVUS|NONIES|'
         r'NOVIES|NOVENUS|NONUS|DECIES|D[ÉE]CIMUS|UNDECIES|UND[ÉE]CIMUS|DUODECIES|DUOD[ÉE]CIMUS|TERDECIES|'
         r'QUATERDECIES|QUINDECIES|QUINQUIESDECIES|SEXIESDECIES|SEPTDECIES|SEPTIESDECIES|OCTODECIES|OCTIESDECIES|'
         r'NOVODECIES|NONIESDECIES|SEXTIES|VICIES|VIGIES)')
ARTICLE = re.compile(
    r'^(?-i:ART[ÍI]CULO|Art[íi]culo|Art\.|ART\.)\s*'
    r'(?P<n>\d{1,3}(?:,\d{3})+|\d+)(?:[oº°](?![^\W\d_])\.?|\s+[º°]\.?|/o\.?)?'
    r'(?:\s*-\s*(?P<sub>\d+)\b(?=\s*[.\-–]))?'
    r'(?P<latin>(?:\s*(?:\.-)?\s*[-–]?\s*' + LATIN + r'\b)(?:\s*-?\s*\d+\b)?)?'
    r'(?P<letter>\s*(?:\.\s*)?[-–]{0,2}\s*(?:LL|CH|[A-ZÑ])(?=\s*[.\-–]|\s*\(SIC\)|\s+' + LATIN + r'\b))?'
    r'(?:\s*-\s*(?P<lsub>\d+)\b(?=\s*[.\-–]|\s*$|\s+' + LATIN + r'\b))?'
    r'(?P<latin2>\s*[-–]?\s*' + LATIN + r'\b(?:\s*-?\s*\d+\b)?)?'
    r'|^(?:ART[ÍI]CULO|Art[íi]culo)\s+(?P<word>' + ORD + r')\b', re.I)
NOT_HEADING = re.compile(r'\s+(?:[a-záéíóúñ]|Constitucional\b|TRANSITORIO\s+(?:DEL?|QUE)\b)')
HEADING = re.compile(r'^(LIBRO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|PARTE|SUBT[ÍI]TULO|APARTADO)\b', re.I)
NOTE = re.compile(r'^(\(|\[N\. DE E\.|N\. DE E\.)')
TRANS = re.compile(r'^(?:ART[ÍI]CULOS?\s+)?TRANSITORIOS?\s*[.:]?\s*$|^DISPOSICIONES TRANSITORIAS\s*[.:]?$', re.I)
MONTHS = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
          'SEPTIEMBRE': 9, 'SETIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}
# the publication marker that heads each reform decree's transitorios block: "P.O. 19 DE SEPTIEMBRE DE 2026.",
# "G.O. 5 DE FEBRERO DE 2017", "P.O.E. ...", "D.O.F. ...", "B.O. ..." (state gazettes' abbreviations)
MARK = re.compile(r'^(?:(?:SUP\.|ALC\.|EXT\.|ED\.)\s*)*(?:[A-ZÁÉÍÓÚ]{1,4}\.\s*){1,6}(?:(?:NO\.|N[ÚU]M\.)\s*\d+\s*,?\s*)?'
                  r'(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚ]+)\s+(?:DE|DEL)\s+(\d{4})\.?\s*$', re.I)


def clean(p: str) -> str:
    s = SPACE.sub(' ', SOFT.sub('', unicodedata.normalize('NFC', p))).strip()
    s = s.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    return s


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def article_id(line: str) -> str | None:
    m = ARTICLE.match(line)
    if not m or NOT_HEADING.match(line, m.end()):
        return None
    if m.group('word'):
        return ascii_slug(m.group('word'))
    parts = [str(int(m.group('n').replace(',', '')))]
    if m.group('sub'):
        parts.append(m.group('sub'))
    if m.group('latin'):
        parts.append(ascii_slug(m.group('latin')))
    if m.group('letter'):
        parts.append('enye' if 'Ñ' in m.group('letter').upper() else ascii_slug(m.group('letter')))
    if m.group('lsub'):
        parts.append(m.group('lsub'))
    if m.group('latin2'):
        parts.append(ascii_slug(m.group('latin2')))
    return '-'.join(p for p in parts if p)


def mark_date(line: str) -> str | None:
    m = MARK.match(line)
    if not m or fold(m.group(2)) not in MONTHS:
        return None
    try:
        return date(int(m.group(3)), MONTHS[fold(m.group(2))], int(m.group(1))).isoformat()
    except ValueError:
        return None


def is_caps(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 3 and len(s) < 200 and all(not c.islower() for c in letters) and not ARTICLE.match(s)


def docx_paragraphs(b: bytes) -> list[str]:
    import io
    x = zipfile.ZipFile(io.BytesIO(b)).read('word/document.xml').decode('utf-8')
    out = []
    for p in re.findall(r'<w:p[ >].*?</w:p>', x, re.S):
        p = re.sub(r'<w:tab/>', '\t', p)
        p = re.sub(r'<w:br/>', '\n', p)
        out.append(htmlmod.unescape(''.join(a or b for a, b in re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>|(\t|\n)', p))))
    return out


def split_text(paragraphs: list[str]) -> tuple[list[tuple[str, str, list[str]]], list[str]]:
    """Consolidated text -> ordered [(kind, raw id, lines)] and the banner lines left out."""
    lines, dropped = [], []
    for p in paragraphs:
        for part in p.split('\n'):
            c = clean(part)
            if not c:
                continue
            if BANNER.match(c):
                dropped.append(c)
                continue
            lines.append(c)
    files: dict[tuple, list[str]] = {}
    order: list[tuple] = []

    def put(k, ls):
        if k not in files:
            files[k] = []
            order.append(k)
        files[k].extend(ls)
    i, n = 0, len(lines)
    cur = ('front', 'encabezado')
    buf: list[str] = []
    seen_article = False
    seen: dict[str, int] = {}
    while i < n:
        l = lines[i]
        if seen_article and (TRANS.match(l) or mark_date(l)):
            break
        aid = article_id(l)
        if aid:
            k = len(buf)
            while k > 0 and (NOTE.match(buf[k - 1]) or HEADING.match(buf[k - 1]) or is_caps(buf[k - 1])):
                k -= 1
            while k < len(buf) and not (NOTE.match(buf[k]) or HEADING.match(buf[k])):
                k += 1
            put(cur, buf[:k])
            carry = buf[k:]
            seen[aid] = seen.get(aid, 0) + 1
            cur = ('art', aid if seen[aid] == 1 else f'{aid}~{seen[aid]}')
            buf = carry + [l]
            seen_article = True
            i += 1
            continue
        buf.append(l)
        i += 1
    put(cur, buf)
    rest = lines[i:]
    j = 0
    trans = []
    while j < len(rest) and not mark_date(rest[j]):
        trans.append(rest[j])
        j += 1
    if trans:
        put(('trans', 'original'), trans)
    count: dict[str, int] = {}
    while j < len(rest):
        d = mark_date(rest[j])
        block = [rest[j]]
        j += 1
        while j < len(rest) and not mark_date(rest[j]):
            block.append(rest[j])
            j += 1
        count[d] = count.get(d, 0) + 1
        put(('trans', d if count[d] == 1 else f'{d}-{count[d]}'), block)
    return [(k[0], k[1], files[k]) for k in order if files[k]], dropped


def unit_key(kind: str, rid: str, width: int) -> str:
    if kind == 'front':
        return 'encabezado'
    if kind == 'trans':
        return 'transitorios-' + rid
    base, _, dup = rid.partition('~')
    k = re.sub(r'^\d+', lambda m: m.group().zfill(width), base)
    return 'art-' + k + (f'-dup{dup}' if dup else '')


def unit_label(kind: str, rid: str, lines: list[str]) -> str:
    if kind == 'front':
        return 'Encabezado'
    if kind == 'trans':
        return 'Transitorios' + ('' if rid == 'original' else f' (publicación {rid[:10]})')
    base = rid.partition('~')[0]
    if re.match(r'^\d', base):
        return 'Artículo ' + base.replace('-', ' ')
    return 'Artículo ' + base


# ---------------------------------------------------------------- in force (the decree's own rule)

WORDS = {'UN': 1, 'UNO': 1, 'DOS': 2, 'TRES': 3, 'CUATRO': 4, 'CINCO': 5, 'SEIS': 6, 'SIETE': 7, 'OCHO': 8,
         'NUEVE': 9, 'DIEZ': 10, 'ONCE': 11, 'DOCE': 12, 'TRECE': 13, 'CATORCE': 14, 'QUINCE': 15,
         'DIECISEIS': 16, 'DIECISIETE': 17, 'DIECIOCHO': 18, 'DIECINUEVE': 19, 'VEINTE': 20, 'VEINTIUNO': 21,
         'VEINTIUN': 21, 'VEINTIDOS': 22, 'VEINTITRES': 23, 'VEINTICUATRO': 24, 'VEINTICINCO': 25,
         'VEINTISEIS': 26, 'VEINTISIETE': 27, 'VEINTIOCHO': 28, 'VEINTINUEVE': 29, 'TREINTA': 30,
         'CUARENTA': 40, 'CUARENTA Y CINCO': 45, 'CINCUENTA': 50, 'SESENTA': 60, 'SETENTA': 70, 'NOVENTA': 90,
         'CIENTO VEINTE': 120, 'CIENTO OCHENTA': 180, 'CIEN': 100, 'TRESCIENTOS SESENTA Y CINCO': 365}
NUM_WORD = '|'.join(sorted(WORDS, key=len, reverse=True))
VIGOR = (r'(?:ENTRARA|ENTRAN|ENTRARAN|EMPEZARA|EMPEZARAN|COMENZARA|COMENZARAN|INICIARA|INICIARAN)\s+(?:EN\s+VIGOR|A\s+REGIR|'
         r'A\s+SURTIR\s+(?:SUS\s+)?EFECTOS|SU\s+VIGENCIA|EN\s+VIGENCIA)|SURTIRA\s+(?:SUS\s+)?EFECTOS|ENTRARA\s+EN\s+VIGENCIA|'
         r'REGIRA|TENDRA\s+VIGENCIA|INICIARA\s+SU\s+VIGENCIA')


def _add(pub: str, days: int) -> str:
    return (date.fromisoformat(pub) + timedelta(days=days)).isoformat()


def _add_months(pub: str, n: int) -> str:
    d = date.fromisoformat(pub)
    y, m = divmod(d.month - 1 + n, 12)
    for day in (d.day, 30, 29, 28):
        try:
            return date(d.year + y, m + 1, day).isoformat()
        except ValueError:
            continue
    raise ValueError(pub)


def _parse_date(s: str) -> str | None:
    m = re.search(r'(\d{1,2})\s*O?\s+DE\s+(' + '|'.join(MONTHS) + r')\s+(?:DE|DEL)\s+(?:ANO\s+)?(\d{4})', s)
    if not m:
        m2 = re.search(r'PRIMERO\s+DE\s+(' + '|'.join(MONTHS) + r')\s+(?:DE|DEL)\s+(?:ANO\s+)?(\d{4})', s)
        return f'{int(m2.group(2)):04d}-{MONTHS[m2.group(1)]:02d}-01' if m2 else None
    try:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return None


def extracto_text(page: str) -> str:
    t = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', page, flags=re.S)
    t = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', t)))
    i = t.find('Extracto:')
    if i < 0:
        return ''
    j = t.find('Cargando', i)
    return t[i + 9:j if j > 0 else None].strip()


def in_force(extracto: str, pub: str, category: str, default: int | None) -> tuple[str, str]:
    dflt = DEFAULT_DAYS if default is None else default
    dbasis = (f'default: {dflt} days after publication (state rule noted by SCJN)' if default is not None
              else f'default: {dflt} days after publication (no rule in the extract)')
    if fold(category).startswith(('FE DE ERRATA', 'ACLARACION')):
        return pub, 'erratum: day of publication'
    t = fold(extracto)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'(\d)\s*[O°º]\.', r'\1O', t)
    t = t.replace('DEL ANO EN CURSO', f'DE {pub[:4]}').replace('DEL PRESENTE ANO', f'DE {pub[:4]}')
    m = re.search(r'TRANSITORIOS?\s*:?(.*)', t)
    trans = m.group(1) if m else t
    sentences = [s.strip() for s in re.split(r'(?<=\.)\s+(?=[A-Z])', trans)]
    cands = [s for s in sentences if re.search(VIGOR, s)]
    if not cands:
        return _add(pub, dflt), dbasis
    s = cands[0]
    head = re.split(r'\b(?:SALVO|EXCEPTO|CON EXCEPCION|A EXCEPCION|EXCEPCION HECHA)\b', s)[0]
    if re.search(r'(DIA\s+SIGUIENTE|SIGUIENTE\s+DIA)\s+(AL|DEL|DE|A|EN)\b[^.]{0,40}PUBLI', head):
        return _add(pub, 1), 'day after publication'
    m = re.search(r'(?:A\s+LOS|DESPUES\s+DE|TRANSCURRIDOS|AL\s+CABO\s+DE|DENTRO\s+DE\s+LOS)\s+(\d+|' + NUM_WORD +
                  r')\s+DIAS(\s+NATURALES|\s+HABILES)?\s+(SIGUIENTES|POSTERIORES|DESPUES|CONTADOS|DE|A\s+PARTIR)', head)
    if m and (m.group(1).isdigit() or m.group(1) in WORDS) and 'HABILES' not in (m.group(2) or ''):
        n = int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1)]
        return _add(pub, n), f'{n} days after publication'
    m = re.search(r'\b(\d+|' + NUM_WORD + r')\s+DIAS(\s+NATURALES)?\s+(DESPUES|SIGUIENTES|POSTERIORES)\s+(A\s+|DE\s+|AL\s+)?'
                  r'(LA\s+FECHA\s+(EN\s+QUE\s+SE\s+PUBLIQUE|DE)\s+|LA\s+|SU\s+|DE\s+SU\s+|AL\s+DE\s+SU\s+)?PUBLICA', head)
    if m and (m.group(1).isdigit() or m.group(1) in WORDS):
        n = int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1)]
        return _add(pub, n), f'{n} days after publication'
    m = re.search(r'\b(?:A\s+LOS\s+)?(UN|DOS|TRES|CUATRO|SEIS|NUEVE|DOCE|DIECIOCHO|\d+)\s+MESES?\s+(SIGUIENTES\s+)?'
                  r'(DE|A|AL|DESPUES|POSTERIORES)\b[^.]{0,30}PUBLICA', head)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1)]
        if n:
            return _add_months(pub, n), f'{n} months after publication'
    if re.search(r'AL\s+ANO\s+SIGUIENTE\s+DE\s+SU\s+PUBLICACION|UN\s+ANO\s+DESPUES\s+DE\s+SU\s+PUBLICACION', head):
        return _add_months(pub, 12), '1 year after publication'
    if re.search(r'DIA\s+(1|PRIMERO)\s+DEL\s+MES\s+SIGUIENTE', head):
        d = date.fromisoformat(pub)
        return date(d.year + (d.month == 12), d.month % 12 + 1, 1).isoformat(), 'first day of the next month'
    if re.search(r'(EL\s+MISMO\s+DIA|EL\s+DIA|LA\s+FECHA|DESDE\s+LA\s+FECHA|A\s+PARTIR\s+DE\s+LA\s+FECHA|A\s+PARTIR\s+DEL\s+DIA)\s+'
                 r'(DE\s+)?(LA\s+FECHA\s+DE\s+)?SU\s+PUBLICACION', head) or re.search(r'(DESDE|A\s+PARTIR\s+DE)\s+SU\s+PUBLICACION', head):
        return pub, 'day of publication'
    d = _parse_date(head) or _parse_date(s)
    if d and d >= pub:
        return d, 'date named in the decree'
    return _add(pub, dflt), dbasis + ' (rule not read)'


# ---------------------------------------------------------------- one act -> corpus act

def dmy(s: str) -> str:
    d, m, y = s.split('/')
    return f'{y}-{m}-{d}'


def law_kind(cat: str) -> str:
    c = fold(cat)
    if re.search(r'SENTENCIA|ACCION DE INCONSTITUCIONALIDAD|CONTROVERSIA|RESOLUCION|EJECUTORIA|JURISPRUDENCIA|DECLARATORIA', c):
        return 'court'
    if re.search(r'^(DECRETO|LEY|CODIGO|CONSTITUCION|REFORMA|ADICION|DEROGACION|ABROGACION)', c):
        return 'law'
    return 'decree'


def gazette(slug: str) -> str:
    return 'G.O.' if slug == 'mexico-city' else 'P.O.'


def law_entry(slug: str, rec: dict, extracto: str, n: int) -> tuple[str, dict]:
    pub = dmy(rec['pub'])
    cat = rec['cat'] or 'PUBLICACION'
    num = rec['num'].strip()
    key = ascii_slug(f'{cat}-{pub}-{num}')[:90].strip('-') + (f'-{n}' if n > 1 else '')
    label = f'{cat.capitalize()}, {gazette(slug)} {rec["pub"]}' + (f' ({num})' if num else '') + (f' [{n}]' if n > 1 else '')
    title = re.split(r'\s(?:ARTICULO|TRANSITORIOS?)\b', extracto)[0].strip()[:300] if extracto else label
    if not title or len(title) < 5:
        title = label
    enacted = dmy(rec['exp']) if re.match(r'\d\d/\d\d/\d{4}$', rec['exp'] or '') else None
    return key, {'label': label, 'title': title, 'kind': law_kind(cat), 'enacted': enacted, 'published': pub,
                 'url': None, 'temporary_until': None, 'restores': None, 'note': None}


def act_slug(title: str, used: set) -> str:
    t = ascii_slug(title)
    t = re.sub(r'-(del|para el|de)-(estado|la-ciudad)-.*$', '', t)
    for stop in ('-del-estado-libre-y-soberano-de-', '-del-estado-de-', '-para-el-estado-de-', '-de-la-ciudad-de-mexico',
                 '-del-distrito-federal', '-para-el-distrito-federal', '-del-estado-', '-para-el-estado-'):
        i = t.find(stop)
        if i > 0:
            t = t[:i]
    t = t[:60].strip('-') or 'ordenamiento'
    s, k = t, 2
    while s in used:
        s, k = f'{t}-{k}', k + 1
    used.add(s)
    return s


def parse_act(slug: str, d: dict, used_slugs: set, laws_seen: dict) -> tuple[dict, dict, dict] | None:
    """One SCJN ordenamiento (all records fetched) -> (act, laws, report). None if it has no Word text."""
    default = STATES[slug][5]
    recs = []
    for rec in d['records']:
        if not re.match(r'\d\d/\d\d/\d{4}$', rec['pub'] or ''):
            continue
        num = int(rec['reg'].split('/')[0]) if rec['reg'].split('/')[0].isdigit() else 0
        recs.append((dmy(rec['pub']), -num, rec))
    recs.sort(key=lambda x: (x[0], x[1]))
    # laws: one per record (publication); same (category, date, issue) within an act gets a suffix
    seen_k: Counter = Counter()
    entries = []
    for pub, _, rec in recs:
        ext = b''
        if rec['extracto']:
            ext = gzip.decompress(cpath(slug, 'extracto', BASE + rec['extracto'], 'html').read_bytes())
        et = extracto_text(ext.decode('utf-8', 'replace')) if ext else ''
        base = ascii_slug(f'{rec["cat"] or "PUBLICACION"}-{pub}-{rec["num"].strip()}')
        seen_k[base] += 1
        key, law = law_entry(slug, rec, et, seen_k[base])
        f, basis = in_force(et, pub, rec['cat'], default)
        word = None
        if rec['word']:
            p = cpath(slug, 'word', BASE + rec['word'], 'docx')
            b = gzip.decompress(p.read_bytes())
            if b:
                word = (b, BASE + rec['word'])
        entries.append({'pub': pub, 'key': key, 'law': law, 'inforce': f, 'basis': basis, 'word': word, 'rec': rec})
    texts = [e for e in entries if e['word']]
    if not texts:
        return None
    # parse every text
    parsed = []
    width = 3
    for e in texts:
        try:
            paras = docx_paragraphs(e['word'][0])
        except (zipfile.BadZipFile, KeyError):
            e['bad'] = True
            continue
        files, dropped = split_text(paras)
        if not files:
            # a Word file with no text in it counts as no text file: its publication is credited with the next
            # text that has one (an act with only such files has no text)
            e['bad'] = True
            continue
        for kind, rid, _ in files:
            if kind == 'art':
                m = re.match(r'\d+', rid)
                if m and int(m.group()) >= 1000:
                    width = 4
        parsed.append((e, files))
    if not parsed:
        return None
    versions = []
    prev_units = None
    prev_from = None
    run_max = None
    last_text_idx = -1
    laws: dict[str, dict] = {}
    report = {'records': len(entries), 'texts': len(parsed), 'bases': Counter()}
    for e in entries:
        report['bases'][e['basis'].split(' (')[0]] += 1
    eidx = {id(e): i for i, e in enumerate(entries)}
    first_entry_idx = None
    for e, files in parsed:
        units = {}
        for kind, rid, lines in files:
            k = unit_key(kind, rid, width)
            text = '\n'.join(lines) + '\n'
            if kind == 'art':
                text = text  # the article heading line stays as printed
            units[k] = {'label': unit_label(kind, rid, lines), 'kind': {'front': 'preamble', 'art': 'art',
                                                                         'trans': 'transitional'}[kind], 'text': text}
        i = eidx[id(e)]
        window = entries[last_text_idx + 1:i + 1]       # the publications since the previous text, this one last
        last_text_idx = i
        # a text holds every change published up to it: it is in force once all of them are
        f = max([w['inforce'] for w in window] + ([run_max] if run_max else []))
        run_max = f
        sha = hashlib.sha256(e['word'][0]).hexdigest()
        if prev_units is None:
            v = {'from': f, 'source_url': e['word'][1], 'sha256': sha, 'units': units, 'credits': {}}
            first_entry_idx = i
            versions.append(v)
            prev_units, prev_from = units, f
            continue
        changed = sorted(k for k in set(prev_units) | set(units)
                         if prev_units.get(k, {}).get('text') != units.get(k, {}).get('text'))
        if not changed:
            continue
        cred = [w['key'] for w in window]
        for w in window:
            laws[w['key']] = w['law']
        v = {'from': f, 'source_url': e['word'][1], 'sha256': sha,
             'changes': {k: units.get(k) for k in changed}, 'credits': {k: cred for k in changed}}
        if f == prev_from:
            v['same_day'] = True
        versions.append(v)
        prev_units, prev_from = units, f
    # the first version: the act as enacted when it is the original publication and SCJN marks its text original
    e0 = entries[first_entry_idx]
    first_law = None
    earlier = []
    orig = re.match(r'^(LEY|CODIGO|CONSTITUCION|DECRETO|REGLAMENTO|ESTATUTO)', fold(e0['rec']['cat'] or '')) and \
        first_entry_idx == 0 and b'TEXTO ORIGINAL' in fold(' '.join(docx_paragraphs(e0['word'][0])[:30])).encode()
    if orig:
        first_law = e0['key']
        laws[e0['key']] = e0['law']
    else:
        for w in entries[:first_entry_idx + 1]:
            laws[w['key']] = w['law']
            earlier.append(w['key'])
    for k, law in laws.items():
        laws_seen.setdefault(k, law['label'])
        law['label'] = laws_seen[k]
    act = {'slug': act_slug(d['title'], used_slugs), 'short': d['title'][:80], 'title': d['title'],
           'url': d['url'], 'first_law': first_law, 'earlier_laws': earlier, 'versions': versions}
    report['versions'] = len(versions)
    report['bases'] = dict(report['bases'])
    return act, laws, report


# ---------------------------------------------------------------- parts

def country_block(slug: str) -> dict:
    _, en, native, code, tz, default = STATES[slug]
    rule = (f'Decrees take effect on the day their own transitorios name; when they name none, {default} days after '
            'publication in the state gazette, the state rule SCJN cites.' if default is not None else
            'Decrees take effect on the day their own transitorios name (read from the SCJN extract of each decree).')
    return {
        'code': code, 'name': en, 'slug': f'mexico-{slug}', 'lang': 'es', 'tz': tz, 'future_branch': 'futuro',
        'publisher': {'name': 'Suprema Corte de Justicia de la Nación, Legislación (legislacion.scjn.gob.mx)',
                      'email': f'legislacion@{HOST}.invalid'},
        'default_in_force_rule': {'text': rule, 'source': f'https://{HOST}/'},
        'licence_note': ('Text: Suprema Corte de Justicia de la Nación, Legislación, https://legislacion.scjn.gob.mx/. '
                         'Legislative texts are not protected by copyright in Mexico (Ley Federal del Derecho de '
                         'Autor, art. 14, fracción VIII).'),
    }


AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which ordenamientos to include; it wrote no law '
          'text. Every word of law comes from the SCJN compilation\'s consolidated texts.']


def decisions(slug: str) -> list[str]:
    default = STATES[slug][5]
    return [
        'Each version is the whole consolidated text SCJN publishes for one publication that changed the act (decree, '
        'erratum, ruling), as it stood after that publication. Publications without a text file are credited with the '
        'next text that has one.',
        'A version takes effect on its decree\'s own in-force day, read from the first transitorio quoted in SCJN\'s '
        'extract (day after publication, a number of days or months, a named date, or the day of publication); errata '
        'on the day of publication. ' + (f'When the extract states no rule, {default} days after publication (the state '
                                          'rule SCJN cites). ' if default is not None else
                                          f'When the extract states no rule, {DEFAULT_DAYS} days after publication '
                                          '(the general rule of Mexican civil codes, art. 3; not checked for this state). ') +
        'A text holds every change published before it, so it is dated no earlier than the latest in-force day of '
        'those publications; staggered in-force days inside one decree are not split.',
        'Two publications that take effect on the same day keep their order of publication (same-day commits).',
        'Units: the heading and preamble (encabezado), one file per article (with the headings and editor\'s notes '
        'printed just before it), the original transitorios, and the transitorios of each reform decree under its '
        'publication date. The banner "ÚLTIMA REFORMA PUBLICADA ..." / "TEXTO ORIGINAL" is left out; editor\'s notes '
        '("(REFORMADO, P.O. ...)", "N. DE E.") stay as printed.',
        'An act\'s first commit is its first publication only when SCJN\'s oldest record is the act itself and its text '
        'is marked "TEXTO ORIGINAL"; otherwise it is the oldest version available, naming the publications before it.',
        'Codes of conduct and ethics are left out; only ordenamientos SCJN marks as in force are included.',
    ]


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def source_block(retrieved: str) -> dict:
    return {'name': 'Suprema Corte de Justicia de la Nación: Legislación (state compilation)',
            'url': f'https://{HOST}/', 'retrieved': retrieved,
            'licence': 'Ley Federal del Derecho de Autor, art. 14, fr. VIII: legislative texts are not protected. '
                       'SCJN terms: copying for informative and academic purposes, with no commercial use.',
            'notes': 'Every publication record of each ordenamiento with its consolidated Word text and decree extract.'}


def plan(slug: str, cat: dict) -> list[tuple[str, list[dict]]]:
    """The parts of a state, in order: constitution, codes, then laws in parts of PART_SIZE."""
    out = [('10-constitucion', cat['constitucion'][:1])] if cat['constitucion'] else []
    codes = cat['codigo']
    for i in range(0, len(codes), PART_SIZE):
        out.append((f'{20 + i // PART_SIZE}-codigos-{i // PART_SIZE + 1}', codes[i:i + PART_SIZE]))
    leyes = cat['ley']
    for i in range(0, len(leyes), PART_SIZE):
        out.append((f'{30 + i // PART_SIZE}-leyes-{i // PART_SIZE + 1:02d}', leyes[i:i + PART_SIZE]))
    return out


BATCH = 3  # verified parts promoted into corpus.d (each with its .PUBLISH) at once: one autopush rebuild per batch


def stage_dir(slug: str) -> Path:
    """Verified parts wait here (with <part>.VERIFIED) until their batch is promoted. Not a .tmp* folder, so the wip
    snapshot streams them to world-law-ops; outside corpus.d and repo/, so the main build never sees them."""
    return folder(slug) / 'staged'


def part_file(slug: str, name: str) -> Path:
    p = folder(slug) / 'corpus.d' / f'{name}.json'
    return p if p.exists() else stage_dir(slug) / f'{name}.json'


def all_parts(slug: str) -> list[Path]:
    """Every parsed part, promoted or staged, in name order."""
    d = {p.stem: p for p in stage_dir(slug).glob('*.json')}
    d.update({p.stem: p for p in (folder(slug) / 'corpus.d').glob('*.json')})
    return [d[k] for k in sorted(d)]


def is_verified(slug: str, name: str) -> bool:
    return (folder(slug) / 'corpus.d' / f'{name}.PUBLISH').exists() or (stage_dir(slug) / f'{name}.VERIFIED').exists()


def parse_part(slug: str, name: str, members: list[dict], docs_date: str) -> dict | None:
    out = stage_dir(slug) / f'{name}.json'
    if is_verified(slug, name):
        return {'skipped': 'published'}
    used, laws_seen = set(), {}
    for p in all_parts(slug):
        if p.stem == name:
            continue
        pj = json.loads(p.read_text(encoding='utf-8'))
        for a in pj.get('acts', []):
            used.add(a['slug'])
        for k, law in pj.get('laws', {}).items():
            laws_seen.setdefault(k, law['label'])
    acts, laws, rep = [], {}, {}
    for m in members:
        d = law_fetched(slug, m)
        if d is None:
            return None
        r = parse_act(slug, d, used, laws_seen)
        if r is None:
            rep[m['title'][:60]] = 'no text'
            continue
        a, l, rp = r
        acts.append(a)
        for k, v in l.items():
            laws.setdefault(k, v)
        rep[a['slug']] = rp
    if not acts:
        return {'empty': rep}
    has_country_part = any(p.stem != name and p.stem < name for p in all_parts(slug))
    part = {'country': country_block(slug), 'laws': dict(sorted(laws.items())), 'acts': acts}
    if not has_country_part:
        part.update(sources=[source_block(docs_date)], decisions=decisions(slug), ai_use=AI_USE)
    stage_dir(slug).mkdir(parents=True, exist_ok=True)
    write_part(out, part)
    return rep


# ---------------------------------------------------------------- checks

def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def source_paragraphs(b: bytes) -> list[str]:
    """Independent reader (lxml, not the parser's regex): each w:p's own w:t text, in document order."""
    import io
    from lxml import etree
    root = etree.fromstring(zipfile.ZipFile(io.BytesIO(b)).read('word/document.xml'))
    out = []
    for p in root.iter(W + 'p'):
        parts = []
        for t in p.iter(W + 't'):
            a = t.getparent()
            while a is not None and a.tag != W + 'p':
                a = a.getparent()
            if a is p:
                parts.append(t.text or '')
        out.append(''.join(parts))
    return out


BANNER_CHECK = re.compile(r'^\s*(TEXTO ORIGINAL\.?|[ÚU]LTIMA REFORMA\b.*)\s*$', re.I)


def letters_check(slug: str, part_name: str) -> list[str]:
    p = part_file(slug, part_name)
    part = json.loads(p.read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        units = {}
        for v in act['versions']:
            if 'units' in v:
                units = dict(v['units'])
            else:
                for k, u in v['changes'].items():
                    if u is None:
                        units.pop(k, None)
                    else:
                        units[k] = u
            b = gzip.decompress(cpath(slug, 'word', v['source_url'], 'docx').read_bytes())
            if hashlib.sha256(b).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]} {v["from"]}: sha256 differs from the cached source')
                continue
            paras = [x for x in source_paragraphs(b) if not BANNER_CHECK.match(x.replace('\u00a0', ' '))]
            src = letters(''.join(paras))
            mine = ''.join(u['text'] for u in units.values())
            if sorted(src) != sorted(letters(mine)):
                ca, cb = Counter(src), Counter(letters(mine))
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((ca - cb).most_common(6))} '
                             f'corpus-only {dict((cb - ca).most_common(6))}')
                continue
            for k, u in units.items():
                if letters(u['text']) not in src:
                    probs.append(f'{act["slug"]} {v["from"]} {k}: text not found in order in the source')
                    break
    return probs


# ---------------------------------------------------------------- docs, scaffold, verify, publish

def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {x.strftime("%B")} {x.year}'


def _verified(slug: str, extra=()) -> list[dict]:
    out = []
    for p in all_parts(slug):
        if is_verified(slug, p.stem) or p.stem in extra:
            out.append(json.loads(p.read_text(encoding='utf-8')))
    return out


def write_docs(slug: str, docs_date: str, extra=(), out: Path | None = None):
    _, en, native, code, tz, default = STATES[slug]
    parts = _verified(slug, extra)
    rows, nacts, nvers = [], 0, 0
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = _long(vs[0]['from']) if len(vs) == 1 else f'{_long(vs[0]["from"])} to {_long(vs[-1]["from"])}'
            hist = ('as first published' if a.get('first_law') else 'oldest version available') + \
                (f', then each reform: {span}' if len(vs) > 1 else f': {span}')
            rows.append(f'| `{a["slug"]}/` | {a["title"]} | {len(vs)} | {hist} |')
    is_city = slug == 'mexico-city'
    unit = 'Mexico City' if is_city else f'the State of {en}' if slug != 'state-of-mexico' else 'the State of Mexico'
    repo = out or (folder(slug) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    gaz = 'Gaceta Oficial de la Ciudad de México' if is_city else 'the state\'s official gazette (Periódico Oficial)'
    readme = f"""# {en}: law history in git

The law of {unit} ({native}, Mexico) as a git history: one file per article, one commit per publication that changed it, dated the day it took effect, with the decree as the commit's author. `git blame` names the decree behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{code.lower()}/`. Mexico's federal law is in [lexifina/mexico-law](https://github.com/lexifina/mexico-law).

The text is in Spanish, exactly as the source prints it.

## What this repository holds

{nacts} ordenamiento{"s" if nacts != 1 else ""} with {nvers} versions so far: the {"constitution" if not is_city else "Constitution of Mexico City"} first, then the codes and laws in force, added in parts. Regulations, decrees and repealed laws are not included yet.

| Folder | Ordenamiento | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

The legislation compilation of Mexico's Supreme Court, the Suprema Corte de Justicia de la Nación (SCJN), at <https://legislacion.scjn.gob.mx/>. For each ordenamiento it lists every publication in {gaz} that changed it (decree, erratum, ruling), with the date of publication, the decree's extract and the whole consolidated text as it stood after that publication. Each version here is one of those texts.

## Dates

- Each commit is dated at **noon, {tz}, on the day the publication took effect**: the day its own transitorios name, as SCJN's extract quotes them (most often the day after publication).{f" When a decree names none, {default} days after publication, the state rule SCJN cites." if default is not None else f" When a decree names none, {DEFAULT_DAYS} days after publication."}
- A consolidated text holds every change published before it, so it is never dated before the latest of their in-force days. Different in-force days for parts of one decree are not split.
- An act's first commit is its first publication when SCJN holds the original text; otherwise it is the oldest version SCJN holds.
- Versions that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.

## Files

`<act>/art-005.md` is Artículo 5, `art-005-bis.md` Artículo 5 Bis; `encabezado.md` holds the title, the promulgation and preamble; `transitorios-original.md` the original transitory articles and `transitorios-<date>.md` those of the reform published that day. Section headings and editor's notes such as "(REFORMADO, P.O. ...)" stay in the file of the article they stand before. One paragraph per line.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of SCJN's own text of that version (read independently of the parser), and every unit's text appears in it in order.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

The author of a commit is the publication that changed the text (a decree, an erratum or a ruling), named by its category, gazette date and issue, with an e-mail address that cannot exist (`<key>@{HOST}.invalid`). The committer is always Lexifina.

## Limits

This is not an official publication. The binding text is the one published in {gaz}. The history starts with the oldest text SCJN holds for each ordenamiento, which for many is later than its enactment. Only the ordenamientos listed above are included.
"""
    lic = f"""The law texts in this repository are official texts of {unit} ({native}, Mexico), taken from the
legislation compilation of the Suprema Corte de Justicia de la Nación (SCJN), https://legislacion.scjn.gob.mx/.

Mexican law does not protect them by copyright. Ley Federal del Derecho de Autor, artículo 14: "No son objeto de la
protección como derecho de autor a que se refiere esta Ley: [...] VIII. Los textos legislativos, reglamentarios,
administrativos o judiciales, así como sus traducciones oficiales. En caso de ser publicados, deberán apegarse al
texto oficial y no conferirán derecho exclusivo de edición;" (Legislative, regulatory, administrative and judicial
texts and their official translations are not protected; when published they must follow the official text and
confer no exclusive right of publication.)

The SCJN's terms of use allow copying information from its portal for informative, academic and similar purposes,
and ask users not to commercialise it. This repository is free, non-commercial and informative, follows the
official text as SCJN publishes it, and credits the source: Suprema Corte de Justicia de la Nación, Legislación,
https://legislacion.scjn.gob.mx/ (consulted {docs_date}).

This repository is not an official publication; the binding text is the one published in the official gazette.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': code.lower(), 'code': code, 'name': en, 'level': 'state' if not is_city else 'federal entity',
             'parent': 'mx', 'repo': f'https://github.com/lexifina/{repo_name(slug)}',
             'build': f'built: constitution, codes and laws ({nacts} ordenamientos, {nvers} versions) from SCJN Legislación',
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
    _, en, native, code, tz, _ = STATES[slug]
    repo = repo_name(slug)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    # GitHub's API answers 502 now and then (it stopped the first run at 14:22): retry, re-checking first, since a
    # 502 can come after the repository was made.
    for attempt in range(6):
        if run('gh', 'api', f'repos/lexifina/{repo}', check=False).returncode == 0:
            break
        p = run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
                '-f', f'description={en} (Mexico) law as git history', check=False)
        if p.returncode == 0:
            break
        if attempt == 5:
            raise RuntimeError(f'creating {repo} failed: {p.stderr[:400]}')
        time.sleep(30 * (attempt + 1))
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    run('git', 'init', '-q', '-b', 'main', cwd=d)
    (d / 'README.md').write_text(f"""# {en}: law as git history

Work in progress. This repository will hold the law of {en} ({native}, Mexico) as a git history: one file per
article, one commit per publication that changed it, on the day it took effect, `git blame` and `git log` working
line by line.

Planned first build: the {"constitution" if slug != "mexico-city" else "Constitution of Mexico City"}, then the codes and laws in force, with every consolidated
version the Supreme Court's legislation compilation publishes.

Source: <https://legislacion.scjn.gob.mx/>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text("""# Sources

- Suprema Corte de Justicia de la Nación, Legislación: <https://legislacion.scjn.gob.mx/>

Legislative texts are not protected by copyright in Mexico (Ley Federal del Derecho de Autor, art. 14, fr. VIII).
The terms and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    run('git', 'add', '-A', cwd=d)
    run('git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
        f'Mexico ({en}): sources, before any law', cwd=d)
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
    names = [p.stem for p in all_parts(slug) if p.stem != part and is_verified(slug, p.stem)] + [part]
    for n in names:
        shutil.copy2(part_file(slug, n), tmp / 'corpus.d' / f'{n}.json')
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
    pj = json.loads(part_file(slug, part).read_text(encoding='utf-8'))
    acts = pj['acts']
    nv = sum(len(a['versions']) for a in acts)
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} ordenamiento(s), {nv} versions {days[0]}..{days[-1]} from SCJN Legislación: letters and '
            f'digits of every version equal SCJN\'s consolidated Word text (independent lxml reader) and every unit is '
            f'found in order; scratch build of verified parts + this part: check.py {res["versions"]} versions, '
            f'0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return True, line


def publish(slug: str, part: str, docs_date: str) -> str:
    """Verifies a staged part and marks it <part>.VERIFIED; promote() publishes verified parts in batches."""
    if not (stage_dir(slug) / f'{part}.json').exists():
        return 'nothing staged for ' + part
    ok, line = verify_part(slug, part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    ver = stage_dir(slug) / f'{part}.VERIFIED'
    tmp = ver.with_suffix('.vtmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, ver)
    return 'VERIFIED (staged for the next batch) ' + line


def state_done(slug: str) -> bool:
    """Every planned part is published, verified or has no text."""
    cat = catalogue(slug, fetch=False)
    if cat is None:
        return False
    return all(is_verified(slug, n) or (stage_dir(slug) / f'{n}.EMPTY').exists() for n, _ in plan(slug, cat))


def promote(slug: str, docs_date: str, force: bool = False) -> str:
    """Moves every staged verified part into corpus.d with its .PUBLISH, then rewrites the docs once, when BATCH parts
    are waiting (or force: the state's list is complete, or the run ends). Releases the claim once the state is done."""
    sd = stage_dir(slug)
    ready = sorted(p.stem for p in sd.glob('*.VERIFIED')) if sd.exists() else []
    msg = ''
    cd = folder(slug) / 'corpus.d'
    first = not list(cd.glob('*.PUBLISH'))   # a repo's first part (its constitution) is published at once
    if ready and (force or first or len(ready) >= BATCH):
        cd.mkdir(parents=True, exist_ok=True)
        for n in ready:
            line = (sd / f'{n}.VERIFIED').read_text(encoding='utf-8')
            t = cd / f'{n}.ptmp'
            t.write_text(line, encoding='utf-8', newline='\n')
            os.replace(sd / f'{n}.json', cd / f'{n}.json')
            os.replace(t, cd / f'{n}.PUBLISH')
            (sd / f'{n}.VERIFIED').unlink()
        write_docs(slug, docs_date)
        top = folder(slug) / 'PUBLISH'
        top.write_text('corpus.d parts are published in batches, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
        msg = f'PUBLISH batch of {len(ready)}: {", ".join(ready)}'
        progress(slug, msg)
    elif ready:
        msg = f'{len(ready)} verified part(s) waiting for a batch of {BATCH}'
    if state_done(slug) and not (sd.exists() and list(sd.glob('*.VERIFIED'))):
        # The claim is NOT released here: autopush_dell only pushes (and applies the standing yes for verified
        # rebuilds to) repos this session claims, so a claim deleted with the last PUBLISH strands the last batch
        # (2026-10-31: 8 repos). Release it once `git ls-remote` shows main holding the final parts.
        if not msg.endswith('list complete'):
            progress(slug, 'list complete; release the claim once main holds the last batch')
            msg += '; list complete (release the claim once main holds it)'
    return msg


# ---------------------------------------------------------------- driver

def claim(slug: str) -> bool:
    p = CLAIMS / f'{repo_name(slug)}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'{SESSION} {now()} (Mexican states via SCJN Legislación)\n')
        return True
    except FileExistsError:
        if not p.read_text(encoding='utf-8', errors='replace').startswith(SESSION):
            return False
        with open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.write(f'{SESSION} {now()} re-claimed (resumed run: codes and laws)\n')
        return True


def progress(slug: str, line: str):
    p = folder(slug) / 'PROGRESS.md'
    if not p.exists():
        p.write_text(f'# {repo_name(slug)} (private progress, gitlaw-scraper-dell)\n\nBuilder: '
                     'scripts/world-law/mx_states.py; source SCJN Legislación (state compilation).\n\n',
                     encoding='utf-8', newline='\n')
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {now()} {line}\n')


def cpu_ok() -> bool:
    try:
        last = Path(os.environ['LOCALAPPDATA'], 'gitlaw-cpu.log').read_text(encoding='utf-8').strip().splitlines()[-1]
        c5 = int(re.search(r'cpu5=(\d+)', last).group(1))
        ram = int(re.search(r'ram=(\d+)', last).group(1))
        return c5 < 92 and ram < 85
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
            slug, name = self.q.get()
            while not cpu_ok():
                time.sleep(60)
            p = _low([sys.executable, '-X', 'utf8', str(Path(__file__)), 'partpub', slug, name, self.docs_date])
            out = (p.stdout.strip().splitlines() or [''])[-1] + (p.stderr.strip()[-300:] if p.returncode else '')
            say(f'[build] {slug} {name}: {out[:400]}')
            progress(slug, f'{name}: {out[:600]}')
            self.q.task_done()


def part_publish(slug: str, name: str, docs_date: str) -> str:
    cat = catalogue(slug, fetch=False)
    members = dict(plan(slug, cat)).get(name)
    rep = parse_part(slug, name, members, docs_date)
    if rep is None:
        return 'not fetched yet'
    if 'empty' in rep:
        stage_dir(slug).mkdir(parents=True, exist_ok=True)
        (stage_dir(slug) / f'{name}.EMPTY').write_text(json.dumps(rep, ensure_ascii=False) + '\n', encoding='utf-8',
                                                       newline='\n')
        out = 'no text in any ordenamiento of the part: ' + json.dumps(rep)[:200]
    elif 'skipped' in rep:
        out = 'already verified'
    else:
        (folder(slug) / '.tmp').mkdir(exist_ok=True)
        (folder(slug) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                                 encoding='utf-8')
        out = publish(slug, name, docs_date)
    pm = promote(slug, docs_date, force=state_done(slug))
    return out + (f' | {pm}' if pm else '')


def drive(slugs: list[str], docs_date: str, max_parts: int | None):
    from concurrent.futures import ThreadPoolExecutor
    builder = Builder(docs_date)
    pool = ThreadPoolExecutor(THREADS)
    active = []
    plans = {}
    try:
        # round 1: claim, scaffold, catalogue and constitution, state by state (largest first); each state is
        # claimed only when its turn comes, so its first part follows within minutes
        for slug in slugs:
            if not claim(slug):
                say(f'{slug}: claimed by another session, skipped')
                continue
            folder(slug).mkdir(exist_ok=True)
            try:
                say(f'{slug}: scaffold {scaffold(slug)}')
            except RuntimeError as e:  # a GitHub failure skips this unit for the run; it never stops the others
                say(f'{slug}: scaffold FAILED, skipped this run: {e}')
                continue
            active.append(slug)
            cat = catalogue(slug)
            plans[slug] = plan(slug, cat)
            progress(slug, f'catalogue: {len(cat["constitucion"])} constitution, {len(cat["codigo"])} codes, '
                           f'{len(cat["ley"])} laws; {len(plans[slug])} parts')
            say(f'{slug}: {len(cat["constitucion"])} constitution, {len(cat["codigo"])} codes, {len(cat["ley"])} laws')
            if plans[slug] and plans[slug][0][0] == '10-constitucion' and not is_verified(slug, '10-constitucion'):
                name, members = plans[slug][0]
                for m in members:
                    fetch_law(slug, m, pool)
                builder.q.put((slug, name))
                say(f'{slug}: constitution fetched ({net().count} requests so far)')
        # round 2..: one more part per state per round
        k = 1
        while True:
            more = False
            for slug in active:
                ps = [p for p in plans[slug] if p[0] != '10-constitucion']
                if k - 1 < len(ps) and (max_parts is None or k <= max_parts):
                    more = True
                    name, members = ps[k - 1]
                    if is_verified(slug, name) or (stage_dir(slug) / f'{name}.EMPTY').exists():
                        continue
                    while not cpu_ok():
                        time.sleep(60)
                    try:
                        for m in members:
                            fetch_law(slug, m, pool)
                    except Stop:
                        raise
                    except Exception as e:  # one law's failure leaves its part for the next run
                        say(f'{slug}: {name} fetch FAILED, part left for a later run: {str(e)[:300]}')
                        progress(slug, f'{name}: fetch failed ({str(e)[:300]}); left for a later run')
                        continue
                    builder.q.put((slug, name))
                    say(f'{slug}: {name} fetched ({len(members)} ordenamientos; {net().count} requests so far)')
            if not more:
                break
            k += 1
    except Stop as e:
        say(f'STOPPED: {e}')
    builder.q.join()
    # the run is over: publish whatever verified parts are still waiting for a full batch
    for slug in active:
        pm = promote(slug, docs_date, force=True)
        if pm:
            say(f'{slug}: {pm}')
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
        dd = dt.date.today().isoformat()
        drive(args or list(STATES), dd, mp)
    elif cmd == 'partpub':
        print(part_publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
    elif cmd == 'scaffold':
        for s_ in sys.argv[2:]:
            print(s_, scaffold(s_))
