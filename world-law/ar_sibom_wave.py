"""SIBOM municipal wave (gitlaw-scraper-dell, 2026-11-01, via global-law-main-composer): every Buenos Aires province
partido on SIBOM (sibom.slyt.gba.gob.ar) as its own public repo, lexifina/argentina-<partido>-city-law, built with the
La Plata rules (ar_cities.py + ar_adapters/sibom.py on the ar_provinces engine).

    python -X utf8 scripts/world-law/ar_sibom_wave.py run [--only=<sibom id>,...] [--laws=200]
    python -X utf8 scripts/world-law/ar_sibom_wave.py status

Stop: create scripts/world-law/sibom-wave/STOP. The driver stops before its next SIBOM request, lets the verifier
finish what is queued, and exits; claims of unfinished partidos stay (see sibom-wave/STATUS.md).

Per partido, largest first: the city page (skip when SIBOM has no bulletin for it); claim
(claims/<repo>.txt, exclusive create); SIBOM's ordinance search for the city, read from its last page back until
--laws ordinances are found; each ordinance's page; ordinances sorted by the day they took effect and cut into parts of
about 50, oldest first, so every part appends newer history. A verifier thread checks parts in batches of 2-4 (letters
and digits of every version against the page read by lxml; check.py on a scratch build of the published parts plus the
batch), creates the repo when the first batch verifies (one API call), then writes the batch's <part>.PUBLISH. The
claim is deleted once autopush_dell has pushed main for the last part.

One SIBOM request at a time, >= 3.2 s apart (ar_provinces.Net), BelowNormal priority, at most 2 workers (fetcher +
verifier); waits while cpu5 > 90 or ram > 85. Private: lives in scripts/world-law (world-law-ops), never published.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ar_cities as C  # noqa: E402  (registers the engine overrides)
from ar_adapters import sibom  # noqa: E402

E = C.E
B = sibom.BASE
WAVE = HERE / 'sibom-wave'
STOPF = WAVE / 'STOP'
STATUS = WAVE / 'STATUS.json'
TRIAGE = E.ROOT / 'REGION-TRIAGE.md'
BUILT = {9, 55, 66}           # Bahía Blanca, General Pueyrredon, La Plata: built earlier, left alone
STATUS_LOCK = threading.Lock()

# SIBOM name -> (display name, population at the 2022 census, rounded). The first ten in the coordinator's order.
PARTIDOS = [
    ('La Matanza', 'La Matanza', 1838), ('Lomas de Zamora', 'Lomas de Zamora', 694), ('Quilmes', 'Quilmes', 636),
    ('Almirante Brown', 'Almirante Brown', 586), ('Merlo', 'Merlo', 581), ('Lanús', 'Lanús', 462),
    ('Moreno', 'Moreno', 574), ('Florencio Varela', 'Florencio Varela', 498),
    ('General San Martín', 'General San Martín', 450), ('Tigre', 'Tigre', 447),
    ('Pilar', 'Pilar', 395), ('Avellaneda', 'Avellaneda', 370), ('Berazategui', 'Berazategui', 362),
    ('Malvinas Argentinas', 'Malvinas Argentinas', 349), ('Tres de Febrero', 'Tres de Febrero', 345),
    ('Esteban Echeverría', 'Esteban Echeverría', 344), ('Morón', 'Morón', 334), ('José C. Paz', 'José C. Paz', 324),
    ('San Isidro', 'San Isidro', 300), ('San Miguel', 'San Miguel', 291), ('Vicente López', 'Vicente López', 281),
    ('Escobar', 'Escobar', 256), ('Ezeiza', 'Ezeiza', 203), ('Hurlingham', 'Hurlingham', 182),
    ('Ituzaingó', 'Ituzaingó', 178), ('San Fernando', 'San Fernando', 170), ('San Nicolás', 'San Nicolás', 165),
    ('Tandil', 'Tandil', 150), ('General Rodríguez', 'General Rodríguez', 141), ('Zárate', 'Zárate', 130),
    ('Lujan', 'Luján', 125), ('Olavarria', 'Olavarría', 115), ('Pergamino', 'Pergamino', 110),
    ('Campana', 'Campana', 106), ('Presidente Perón', 'Presidente Perón', 104), ('Junín', 'Junín', 102),
    ('Berisso', 'Berisso', 101), ('Necochea', 'Necochea', 95), ('De la Costa', 'La Costa', 90),
    ('San Vicente', 'San Vicente', 80), ('Cañuelas', 'Cañuelas', 74), ('Mercedes', 'Mercedes', 71),
    ('Azul', 'Azul', 70), ('Marcos Paz', 'Marcos Paz', 69), ('Chivilcoy', 'Chivilcoy', 68),
    ('San Pedro', 'San Pedro', 66), ('Ensenada', 'Ensenada', 63), ('Coronel Rosales', 'Coronel Rosales', 63),
    ('Tres Arroyos', 'Tres Arroyos', 61), ('Chacabuco', 'Chacabuco', 52), ('Nueve de Julio', 'Nueve de Julio', 50),
    ('Chascomús', 'Chascomús', 48), ('Trenque Lauquen', 'Trenque Lauquen', 47),
    ('General Alvarado', 'General Alvarado', 45), ('Balcarce', 'Balcarce', 45), ('Lincoln', 'Lincoln', 43),
    ('Bragado', 'Bragado', 43), ('Pehuajó', 'Pehuajó', 41), ('Exaltación de la Cruz', 'Exaltación de la Cruz', 40),
    ('Lobos', 'Lobos', 40), ('Coronel Suárez', 'Coronel Suárez', 39), ('Villa Gesell', 'Villa Gesell', 37),
    ('Bolivar', 'Bolívar', 37), ('Ramallo', 'Ramallo', 37), ('Veinticinco de Mayo', 'Veinticinco de Mayo', 37),
    ('Baradero', 'Baradero', 36), ('Saladillo', 'Saladillo', 35), ('Pinamar', 'Pinamar', 34),
    ('Patagones', 'Patagones', 34), ('Villarino', 'Villarino', 33), ('Salto', 'Salto', 33),
    ('Arrecifes', 'Arrecifes', 31), ('Brandsen', 'Brandsen', 31), ('General Villegas', 'General Villegas', 31),
    ('Dolores', 'Dolores', 29), ('Mar Chiquita', 'Mar Chiquita', 27), ('Colón', 'Colón', 26),
    ('San Antonio de Areco', 'San Antonio de Areco', 26), ('San Andrés de Giles', 'San Andrés de Giles', 26),
    ('Las Flores', 'Las Flores', 25), ('Monte', 'Monte', 25), ('Rojas', 'Rojas', 24),
    ('Carlos Casares', 'Carlos Casares', 24), ('Coronel Pringles', 'Coronel Pringles', 23),
    ('General Madariaga', 'General Madariaga', 23), ('Benito Juarez', 'Benito Juárez', 21), ('Ayacucho', 'Ayacucho', 21),
    ('Magdalena', 'Magdalena', 21), ('Saavedra', 'Saavedra', 21), ('General Belgrano', 'General Belgrano', 19),
    ('Navarro', 'Navarro', 19), ('General Viamonte', 'General Viamonte', 19), ('Lobería', 'Lobería', 18),
    ('Rivadavia', 'Rivadavia', 18), ('General Las Heras', 'General Las Heras', 17), ('Daireaux', 'Daireaux', 17),
    ('Adolfo Alsina', 'Adolfo Alsina', 17), ('Capitán Sarmiento', 'Capitán Sarmiento', 16),
    ('Carmen de Areco', 'Carmen de Areco', 16), ('Leandro N. Alem', 'Leandro N. Alem', 16),
    ('Coronel Dorrego', 'Coronel Dorrego', 16), ('Puan', 'Puan', 16), ('Rauch', 'Rauch', 16),
    ('General Arenales', 'General Arenales', 15), ('Tornquist', 'Tornquist', 13), ('Roque Pérez', 'Roque Pérez', 13),
    ('General Alvear', 'General Alvear', 12), ('General Paz', 'General Paz', 12),
    ('Adolfo Gonzales Chaves', 'Adolfo Gonzales Chaves', 12), ('General Pinto', 'General Pinto', 12),
    ('Guaminí', 'Guaminí', 12), ('Maipú', 'Maipú', 11), ('Alberti', 'Alberti', 11), ('Carlos Tejedor', 'Carlos Tejedor', 11),
    ('Suipacha', 'Suipacha', 11), ('Punta Indio', 'Punta Indio', 11), ('General La Madrid', 'General La Madrid', 11),
    ('Tapalqué', 'Tapalqué', 10), ('Hipólito Yrigoyen', 'Hipólito Yrigoyen', 10), ('Laprida', 'Laprida', 10),
    ('Castelli', 'Castelli', 9), ('Salliquelo', 'Salliqueló', 9), ('Florentino Ameghino', 'Florentino Ameghino', 9),
    ('San Cayetano', 'San Cayetano', 9), ('Tres Lomas', 'Tres Lomas', 9), ('Monte Hermoso', 'Monte Hermoso', 8),
    ('Lezama', 'Lezama', 6), ('Pellegrini', 'Pellegrini', 6), ('General Lavalle', 'General Lavalle', 4),
    ('Pila', 'Pila', 4), ('General Guido', 'General Guido', 3), ('Tordillo', 'Tordillo', 2),
]


class StopWave(Exception):
    pass


def say(*a):
    E.say(*a)


def stop_requested() -> bool:
    return STOPF.exists()


def load_ok() -> bool:
    try:
        last = Path(os.environ['LOCALAPPDATA'], 'gitlaw-cpu.log').read_text(encoding='utf-8').strip().splitlines()[-1]
        c5 = int(re.search(r'cpu5=(\d+)', last).group(1))
        ram = int(re.search(r'ram=(\d+)', last).group(1))
        return c5 <= 90 and ram <= 85
    except Exception:
        return True


def wait_load():
    while not load_ok():
        if stop_requested():
            raise StopWave('stop file')
        time.sleep(60)


# Daily cap (coordinator rule, 2026-11-01: hosts without a stated Crawl-delay get at most 1 request per 3 s and about
# 5,000 requests a day): every request to SIBOM is counted per UTC day (retries included, seeded from the request log
# at start), and the driver pauses until the next UTC day once the cap is reached. A challenge, 403 or 429 stops the host
# for good: HOST-STOPPED is written and the driver refuses to start again.
HOST = 'sibom.slyt.gba.gob.ar'
DAILY_CAP = 5000
HOST_STOPPED = WAVE / 'HOST-STOPPED'
_day = {'day': None, 'n': 0}


def _utc_day() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')


def _seed_count(day: str) -> int:
    n = 0
    try:
        with open(HERE / 'logs' / 'ar-provinces-requests.jsonl', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith('{"at": "' + day) and HOST in line:
                    n += 1
    except OSError:
        pass
    return n


def _count_today() -> int:
    d = _utc_day()
    if _day['day'] != d:
        _day.update(day=d, n=_seed_count(d))
    return _day['n']


_orig_note = E.Net._note
_orig_net_get = E.Net.get


def _note(self, url, status, size, t0, err=''):
    if url.split('/')[2] == HOST:
        _count_today()
        _day['n'] += 1
    return _orig_note(self, url, status, size, t0, err)


def _net_get(self, url):
    if url.split('/')[2] == HOST:
        while _count_today() >= DAILY_CAP:
            if stop_requested():
                raise StopWave('stop file')
            nxt = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime('%Y-%m-%dT00:00:05Z')
            say(f'daily cap: {_day["n"]} requests to {HOST} on {_day["day"]}; paused until {nxt}')
            status(0, name='driver', state=f'paused: daily cap {DAILY_CAP} reached on {_day["day"]}, resumes {nxt}')
            while _utc_day() == _day['day']:
                if stop_requested():
                    raise StopWave('stop file')
                time.sleep(60)
            status(0, name='driver', state='running')
    try:
        return _orig_net_get(self, url)
    except E.Stop:
        if url.split('/')[2] == HOST:
            HOST_STOPPED.write_text(f'{E.now()} {url}\n', encoding='utf-8')
        raise


E.Net._note = _note
E.Net.get = _net_get


def get(url: str) -> bytes | None:
    """One SIBOM GET through the engine (cached; one request at a time, >= 3.2 s apart). A cache hit costs nothing."""
    if E.cached(url) is None and not E.cpath(url).exists():
        if stop_requested():
            raise StopWave('stop file')
        wait_load()
    return E.get(url)


# ---------------------------------------------------------------- status, triage, claims

def status(sid: int, **kw):
    with STATUS_LOCK:
        st = json.loads(STATUS.read_text(encoding='utf-8')) if STATUS.exists() else {}
        row = st.setdefault(str(sid), {})
        row.update(kw, at=E.now())
        tmp = STATUS.with_suffix('.tmp')
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        os.replace(tmp, STATUS)


def triage(line: str):
    with STATUS_LOCK:
        with open(TRIAGE, 'a', encoding='utf-8', newline='\n') as f:
            f.write(f'- SIBOM municipal wave (gitlaw-scraper-dell, {E.now()}): {line}\n')


def claim_path(slug: str) -> Path:
    return E.CLAIMS / f'{E.repo_name(slug)}.txt'


def take_claim(slug: str) -> bool:
    p = claim_path(slug)
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'{E.SESSION} {E.now()} (SIBOM municipal wave, via global-law-main-composer)\n')
        return True
    except FileExistsError:
        return p.read_text(encoding='utf-8', errors='replace').startswith(E.SESSION)


def remote_main(repo: str) -> str | None:
    """sha of main, '' when the repo exists without main, None when it does not exist (git ls-remote only)."""
    p = subprocess.run(['git', 'ls-remote', f'https://github.com/lexifina/{repo}.git', 'refs/heads/main'],
                       capture_output=True, text=True, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    if p.returncode != 0:
        if 'not found' in (p.stderr or '').lower():
            return None
        raise RuntimeError(f'ls-remote {repo}: {p.stderr.strip()[:200]}')
    return p.stdout.split()[0] if p.stdout.strip() else ''


# ---------------------------------------------------------------- registration

def register(sid: int, sib_name: str, name: str) -> str:
    slug = f'{E.ascii_slug(name)}-city'
    if slug in C.CITIES:
        return slug
    C.CITIES[slug] = dict(
        en=name, native=f'Municipalidad de {name}', code=f'AR-B-{E.ascii_slug(name).upper()}', parent='ar-b',
        tz='America/Argentina/Buenos_Aires', province='Buenos Aires', sibom=(sid, name, name, True),
        what=f'the Partido de {name} (Province of Buenos Aires)')
    E.PROVINCES[slug] = (name, f'Municipalidad de {name}', C.CITIES[slug]['code'], C.CITIES[slug]['tz'])
    base = sibom.make(sid, name, name, True)

    class Adapter(base):
        decisions = [
            f'Source: the Boletín Oficial Municipal de {name} on SIBOM ({B}/cities/{sid}), the Province of Buenos '
            'Aires\' platform for municipal bulletins (Ley 14.491). Each ordinance is its text as published in the '
            'bulletin, shown as enacted and dated the day it took effect. Later amendments by other ordinances are not '
            'applied to it; an amending ordinance appears as its own folder when it is included.',
            'In-force day: the ordinance\'s own vigencia clause when its last articles state one (from publication, the '
            'day after, or a named date). Otherwise our choice is the ninth day after its publication in the Boletín '
            'Oficial Municipal, applying Código Civil y Comercial, arts. 5 and 6, to ordinances as general norms: the '
            'Ley Orgánica de las Municipalidades requires publication but sets no day. The publication date is the one '
            'SIBOM prints for the bulletin.',
            'The Province of Buenos Aires gives its municipalities no carta orgánica: their organic law is the provincial '
            'Ley Orgánica de las Municipalidades (Decreto-Ley 6769/58), which is provincial law and not included here. '
            'So this repository starts with ordinances.',
            'Ordinances are taken from SIBOM\'s ordinance search for the partido, read from its last result page back '
            '(the search lists them only roughly in date order) until about 200 are found, the newest it holds. They are '
            'sorted by the day they took effect and added oldest first in parts of about 50, so each part extends the '
            'history forward. An ordinance whose page carries only an extract, no article, or its text only as a PDF '
            'annex is left out; the README lists every ordinance left out and why. An ordinance published twice is '
            'taken from its first publication.',
            'Units: the heading (encabezado: number, place and date, the expediente line and anything before Artículo 1) '
            'and one file per article, holding the article and everything printed after it up to the next article '
            '(signatures, annexes). Nothing is dropped. One paragraph per line, spacing normalised.',
        ]
    E.ADAPTERS[slug] = Adapter
    return slug


# ---------------------------------------------------------------- left-out list (private file, shown in the README)

def leftout_path(slug: str) -> Path:
    return E.folder(slug) / 'LEFT-OUT.json'


def leftout_load(slug: str) -> dict:
    p = leftout_path(slug)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def leftout_save(slug: str, lo: dict):
    p = leftout_path(slug)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(lo, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def write_docs(slug: str, docs_date: str, extra=(), out: Path | None = None):
    C.write_docs(slug, docs_date, extra=extra, out=out)
    repo = out or (E.folder(slug) / 'repo')
    shown = {p.stem for p in (E.folder(slug) / 'corpus.d').glob('*.json')
             if p.with_suffix('.PUBLISH').exists() or p.stem in extra}
    lo = leftout_load(slug)
    rows = [r for part in sorted(shown) for r in lo.get(part, [])]
    if not rows:
        return
    rows.sort(key=lambda r: (r.get('pub') or '', r.get('number') or ''))
    src = E.adapter_cls(slug).source
    table = '\n'.join(f'| Ordenanza {r["number"]} | {E._long(r["pub"]) if r.get("pub") else "?"} | {r["why"]} | <{r["url"]}> |'
                      for r in rows)
    add = (f'\n## Left out\n\n{len(rows)} ordinance{"s" if len(rows) != 1 else ""} that SIBOM lists in the period '
           f'covered {"are" if len(rows) != 1 else "is"} not included, because the {src["gazette"]} page gives no '
           'article text to read:\n\n| Ordinance | Published | Why | Page |\n| --- | --- | --- | --- |\n' + table + '\n')
    p = repo / 'README.md'
    p.write_text(p.read_text(encoding='utf-8') + add, encoding='utf-8', newline='\n')


E.write_docs = write_docs

# Some partidos print "Artículo-1 º :-" (a dash between the word and the number), which the engine's ARTICLE pattern
# does not take. Read such a heading as "Artículo 1 º :-" for splitting only; the text kept is the line as printed.
# Patched here, for this wave's process only, so other builders on the engine are unchanged.
_article_id = E.article_id
_DASHED = re.compile(r'^(\s*ART[IÍ]CULO)\s*[-–—_]\s*(?=\d)', re.I)


def article_id(line: str) -> str | None:
    return _article_id(_DASHED.sub(r'\1 ', line, count=1))


E.article_id = article_id


# ---------------------------------------------------------------- catalogue and texts

SEARCH_RX = re.compile(r'content-title"><a href="(/bulletins/\d+/contents/\d+)">Ordenanza N[º°o]?\s*([^<\s]*)'
                       r'( en el bolet[íi]n [^<]*)</a></p></div><div class="col-md-1"></div></div><div><span '
                       r'class="text-muted">([0-9/]+)')


def has_bulletins(sid: int) -> tuple[bool, str]:
    s = E.decode(get(f'{B}/cities/{sid}') or b'')
    if not s:
        return False, 'city page not available'
    if 'No existen boletines publicados' in s:
        return False, 'SIBOM shows no bulletin for it ("No existen boletines publicados aún")'
    m = re.findall(r'<p class="bulletin-date">Publicado el ([0-9/]+)</p>', s)
    if not m:
        return False, 'no bulletin listed on its SIBOM page'
    return True, f'newest bulletin {E.dmy(m[0])}'


def catalogue(slug: str, sid: int, n_laws: int) -> list[dict]:
    p = E.folder(slug) / 'CATALOGUE.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))['ley']
    q = f'q%5Bterms%5D%5Bbulletin.city_id%5D={sid}&q%5Bterms%5D%5Btype%5D=Ordinance'
    first = E.decode(get(f'{B}/advanced_search?{q}') or b'')
    pages = [int(x) for x in re.findall(r'advanced_search\?page=(\d+)&', first.replace('&amp;', '&'))]
    last = max(pages or [1])
    laws, seen = [], set()
    for page in range(last, 0, -1):
        s = first if page == 1 else E.decode(get(f'{B}/advanced_search?page={page}&{q}') or b'')
        for href, num, title, pub in SEARCH_RX.findall(s):
            if href in seen:
                continue
            seen.add(href)
            laws.append({'page': B + href, 'number': num.replace('.', ''), 'pub': E.dmy(pub), 'promul': None,
                         'bulletin': E.clean(title)})
        if len(laws) >= n_laws:
            break
    laws.sort(key=lambda x: (x['pub'] or '', int(re.sub(r'\D', '', x['number'])[:9] or 0)))
    E.folder(slug).mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps({'search_pages': last, 'taken': len(laws), 'at': E.now(), 'ley': laws},
                              ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)
    return laws


def why_not(b: bytes | None) -> str:
    if not b:
        return 'page not available'
    s = E.decode(b)
    if len(sibom.COL.findall(s)) != 1:
        return 'page layout not readable'
    if re.search(r'<p class="extracted-version-disclaimer">\s*[^<\s]', s):
        return 'only an extract is published'
    if 'download_annex' in s:
        return 'text only as a PDF annex'
    return 'no article in the published text'


def fetch_texts(slug: str, members: list[dict]) -> tuple[list, list]:
    ad = E.adapter_cls(slug)()
    got, out, keys = [], [], set()
    for m in members:
        row = {'number': m['number'], 'pub': m.get('pub'), 'url': m['page']}
        d = ad.detail(m)
        if not d:
            out.append({**row, 'why': 'number or publication date not readable'})
            continue
        k = E.law_key(d)
        if k in keys:
            out.append({**row, 'why': 'published again; the first publication is included'})
            continue
        get(d['text_url'])
        t = ad.text(d)
        if not t or not t[0]:
            out.append({**row, 'why': why_not(E.cached(d['text_url']))})
            continue
        keys.add(k)
        got.append((d, t[0], t[1]))
    return got, out


def num_key(d: dict) -> int:
    return int(re.sub(r'\D', '', d['number'])[:9] or 0)


def make_parts(slug: str, got: list, out: list, docs_date: str) -> list[str]:
    got.sort(key=lambda x: ((x[0].get('in_force') or (None,))[0] or x[0]['pub'], x[0]['pub'], num_key(x[0])))
    names = []
    for i in range(0, len(got), E.PART_SIZE):
        name = f'{30 + i // E.PART_SIZE}-ordenanzas-{i // E.PART_SIZE + 1:02d}'
        chunk = got[i:i + E.PART_SIZE]
        rep = E.parse_part(slug, name, chunk, docs_date)
        (E.folder(slug) / '.tmp').mkdir(exist_ok=True)
        (E.folder(slug) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                                   encoding='utf-8')
        for d, _, _ in chunk:
            r = rep.get(E.law_key(d))
            if isinstance(r, dict) and r.get('deferred'):
                out.append({'number': d['number'], 'pub': d['pub'], 'url': d['page'],
                            'why': 'in force on the retrieval day; left for a later part'})
        names.append(name)
    # each left-out ordinance is listed with the part whose publication dates reach it
    lo = {}
    ends = []
    for i, name in enumerate(names):
        pubs = [d['pub'] for d, _, _ in got[i * E.PART_SIZE:(i + 1) * E.PART_SIZE]]
        ends.append((max(pubs), name))
    for r in out:
        tgt = next((n for e, n in ends if (r.get('pub') or '') <= e), names[-1] if names else '30-ordenanzas-01')
        lo.setdefault(tgt, []).append(r)
    leftout_save(slug, lo)
    return names


# ---------------------------------------------------------------- verify + publish (verifier thread)

def drop_acts(slug: str, part: str, bad: dict[str, str]):
    p = E.folder(slug) / 'corpus.d' / f'{part}.json'
    pj = json.loads(p.read_text(encoding='utf-8'))
    lo = leftout_load(slug)
    keep = []
    for a in pj['acts']:
        if a['slug'] in bad:
            fl = a.get('first_law')
            law = pj['laws'].pop(fl, None) if fl else None
            num = (law or {}).get('label', a['short']).split()[-1].split('/')[0]
            lo.setdefault(part, []).append({'number': num, 'pub': (law or {}).get('published'), 'url': a['url'],
                                            'why': bad[a['slug']]})
        else:
            keep.append(a)
    pj['acts'] = keep
    E.write_part(p, pj)
    leftout_save(slug, lo)


def verify_batch(slug: str, parts: list[str], docs_date: str) -> tuple[bool, dict[str, str]]:
    for part in parts:
        probs = E.letters_check(slug, part)
        if probs:
            bad = {pr.split()[0]: 'letters check against the source page differs' for pr in probs}
            say(f'{slug} {part}: letters check {len(probs)} problems, left out: {", ".join(bad)}')
            E.progress(slug, f'{part}: letters check failed for {", ".join(bad)}: left out and listed')
            drop_acts(slug, part, bad)
            if E.letters_check(slug, part):
                return False, {part: 'letters check still failing'}
    src = E.folder(slug)
    tmp = E.DOCS / f'{E.repo_name(slug)}-verify'
    build = E.DOCS / f'{E.repo_name(slug)}-verifybuild'
    for d in (tmp, build):
        E._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()] + parts
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(slug, docs_date, extra=parts, out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = E._low([sys.executable, '-X', 'utf8', str(E.ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
                '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, {p: 'build failed: ' + (b.stderr or b.stdout)[-400:] for p in parts}
    c = E._low([sys.executable, '-X', 'utf8', str(E.ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, {p: 'check.py output unreadable: ' + (c.stderr or c.stdout)[-300:] for p in parts}
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force'):
        msg = 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
        return False, {p: msg for p in parts}
    lines = {}
    for part in parts:
        acts = json.loads((src / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))['acts']
        days = sorted(v['from'] for a in acts for v in a['versions'])
        lines[part] = (f'{len(acts)} norm(s), {sum(len(a["versions"]) for a in acts)} versions {days[0]}..{days[-1]} '
                       f'from {E.adapter_cls(slug).host}: letters and digits of every version equal the source document '
                       f'(independent lxml reader); scratch build of verified parts + batch {"+".join(parts)}: check.py '
                       f'{res.get("versions")} versions, 0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    E._rm(tmp)
    E._rm(build)
    return True, lines


def publish_batch(sid: int, slug: str, parts: list[str], docs_date: str) -> bool:
    wait_load()
    parts = [p for p in parts if not (E.folder(slug) / 'corpus.d' / f'{p}.PUBLISH').exists()]
    parts = [p for p in parts if json.loads((E.folder(slug) / 'corpus.d' / f'{p}.json').read_text(encoding='utf-8'))['acts']]
    if not parts:
        return True
    ok, lines = verify_batch(slug, parts, docs_date)
    if not ok and len(parts) > 1:
        # find the parts that pass on their own, in date order; a failing part is held and reported
        res = True
        for p in parts:
            res = publish_batch(sid, slug, [p], docs_date) and res
        return res
    if not ok:
        for p, why in lines.items():
            E.progress(slug, f'{p}: NOT VERIFIED {why[:500]}')
            say(f'{slug} {p}: NOT VERIFIED {why[:200]}')
        status(sid, held=sorted(set(json.loads(json.dumps(lines)).keys())))
        return False
    repo = E.repo_name(slug)
    rm = remote_main(repo)
    if rm is None:
        r = C.scaffold(slug)
        say(f'{slug}: repo {r}')
        E.progress(slug, f'repo {r} (one API call; first batch verified)')
        status(sid, repo_created=E.now())
    write_docs(slug, docs_date, extra=parts)
    for p in parts:
        pub = E.folder(slug) / 'corpus.d' / f'{p}.PUBLISH'
        tmp = pub.with_suffix('.ptmp')
        tmp.write_text(lines[p] + '\n', encoding='utf-8', newline='\n')
        os.replace(tmp, pub)
        E.progress(slug, f'{p}: PUBLISH {lines[p]}')
        say(f'{slug} {p}: PUBLISH {lines[p][:120]}')
    top = E.folder(slug) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return True


def batches(names: list[str]) -> list[list[str]]:
    if len(names) <= 3:
        return [names] if names else []
    out = [names[i:i + 2] for i in range(0, len(names), 2)]
    if len(out[-1]) == 1:
        tail = out.pop()
        out[-1] = out[-1] + tail
    return out


Q: queue.Queue = queue.Queue()
PENDING: dict[str, int] = {}       # slug -> sibom id, waiting for autopush before the claim is released


def verifier():
    while True:
        job = Q.get()
        if job is None:
            Q.task_done()
            return
        sid, slug, names, docs_date = job
        try:
            okall = True
            for bt in batches(names):
                okall = publish_batch(sid, slug, bt, docs_date) and okall
            pub = [p.stem for p in (E.folder(slug) / 'corpus.d').glob('*.PUBLISH')]
            acts = sum(len(json.loads((E.folder(slug) / 'corpus.d' / f'{p}.json').read_text(encoding='utf-8'))['acts'])
                       for p in pub)
            lo = sum(len(v) for v in leftout_load(slug).values())
            status(sid, state='published, waiting for autopush' if okall else 'published in part (parts held)',
                   parts=len(pub), ordinances=acts, left_out=lo)
            if pub:
                PENDING[slug] = sid
        except Exception as e:
            say(f'{slug}: verifier error {e!r}')
            E.progress(slug, f'verifier error: {str(e)[:400]}')
            status(sid, state=f'verifier error: {str(e)[:200]}')
        finally:
            Q.task_done()


# ---------------------------------------------------------------- claim release after autopush

def check_releases():
    if not PENDING:
        return
    sys.path.append(str(E.ROOT / 'gitlaw_common'))
    import autopush_dell as A
    for slug, sid in list(PENDING.items()):
        aslug = E.repo_name(slug)[:-len('-law')]
        try:
            if not A.unchanged(aslug):
                continue
            local = subprocess.run(['git', '-C', str(E.DOCS / E.repo_name(slug)), 'rev-parse', 'refs/heads/main'],
                                   capture_output=True, text=True).stdout.strip()
            rm = remote_main(E.repo_name(slug))
        except Exception as e:
            say(f'{slug}: release check failed {e!r}')
            continue
        if local and rm == local:
            st = json.loads(STATUS.read_text(encoding='utf-8')).get(str(sid), {})
            claim_path(slug).unlink(missing_ok=True)
            PENDING.pop(slug, None)
            E.progress(slug, f'done: main {rm[:10]} pushed by autopush; claim deleted')
            status(sid, state='done', main=rm[:10])
            triage(f'{C.CITIES[slug]["en"]} ({E.repo_name(slug)}, SIBOM city {sid}): PASS, BUILT. '
                   f'{st.get("ordinances")} ordinances in {st.get("parts")} parts (newest ~200 SIBOM lists, as published, '
                   f'dated by vigencia clause or pub+9), {st.get("left_out")} left out and listed in the README '
                   f'(PDF-annex only, extracts, no article); main {rm[:10]}.')


# ---------------------------------------------------------------- driver

def one(sid: int, sib_name: str, name: str, n_laws: int):
    slug = register(sid, sib_name, name)
    repo = E.repo_name(slug)
    fold = E.folder(slug)
    pubs = list((fold / 'corpus.d').glob('*.PUBLISH')) if fold.exists() else []
    st = json.loads(STATUS.read_text(encoding='utf-8')).get(str(sid), {}) if STATUS.exists() else {}
    if st.get('state') in ('done',) or st.get('state', '').startswith('skipped'):
        return
    if pubs and not claim_path(slug).exists():
        return
    ok, why = has_bulletins(sid)
    if not ok:
        status(sid, name=name, repo=repo, state=f'skipped: {why}')
        triage(f'{name} ({repo}, SIBOM city {sid}): SKIP, {why}. No claim, no repo.')
        return
    if not take_claim(slug):
        status(sid, name=name, repo=repo, state='skipped: claimed by another session')
        triage(f'{name} ({repo}): SKIP, claim file held by another session.')
        return
    if not fold.exists() or not (fold / 'PROGRESS.md').exists():
        rm = remote_main(repo)
        if rm is not None:
            claim_path(slug).unlink(missing_ok=True)
            status(sid, name=name, repo=repo, state='skipped: repo already exists (not ours)')
            triage(f'{name} ({repo}): SKIP, the repo already exists and this session has no build of it.')
            return
    fold.mkdir(exist_ok=True)
    gi = fold / '.gitignore'
    if not gi.exists():
        gi.write_text('.tmp/\n', encoding='utf-8', newline='\n')
    status(sid, name=name, repo=repo, state='fetching', bulletins=why)
    docs_date = dt.date.today().isoformat()
    names = sorted(p.stem for p in (fold / 'corpus.d').glob('*.json')) if (fold / 'corpus.d').exists() else []
    if not pubs:
        laws = catalogue(slug, sid, n_laws)
        E.progress(slug, f'catalogue: {len(laws)} ordinances from SIBOM\'s ordinance search (city {sid}), {why}')
        if not laws:
            claim_path(slug).unlink(missing_ok=True)
            status(sid, state='skipped: no ordinance in SIBOM\'s ordinance search')
            triage(f'{name} ({repo}, SIBOM city {sid}): SKIP, SIBOM has bulletins ({why}) but its ordinance search '
                   'lists no ordinance for the partido. Claim released, no repo.')
            return
        got, out = fetch_texts(slug, laws)
        say(f'{slug}: {len(got)} ordinances with text, {len(out)} left out ({sum(E.net().count.values())} requests)')
        if not got:
            claim_path(slug).unlink(missing_ok=True)
            status(sid, state='skipped: no ordinance text in HTML', left_out=len(out))
            triage(f'{name} ({repo}, SIBOM city {sid}): SKIP, none of the {len(out)} ordinances SIBOM lists has its '
                   'articles in HTML (PDF annexes or extracts only). Claim released, no repo.')
            return
        for p in names:
            (fold / 'corpus.d' / f'{p}.json').unlink()
        names = make_parts(slug, got, out, docs_date)
        E.progress(slug, f'parts: {", ".join(names)} ({len(got)} ordinances, {len(out)} left out)')
    status(sid, state='verifying', parts_planned=len(names))
    Q.put((sid, slug, names, docs_date))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    args = sys.argv[1:]
    cmd = args.pop(0) if args else 'status'
    if cmd == 'status':
        st = json.loads(STATUS.read_text(encoding='utf-8')) if STATUS.exists() else {}
        for k, v in st.items():
            print(k, v.get('name'), v.get('state'), v.get('ordinances', ''), v.get('main', ''))
        return
    only, n_laws = None, 200
    for a in args:
        if a.startswith('--only='):
            only = {int(x) for x in a.split('=')[1].split(',')}
        elif a.startswith('--laws='):
            n_laws = int(a.split('=')[1])
    cities = {c['name']: c['id'] for c in json.loads((WAVE / 'cities.json').read_text(encoding='utf-8'))}
    order = [(cities[s], s, n) for s, n, _ in PARTIDOS if s in cities]
    missing = set(cities) - {s for s, _, _ in PARTIDOS} - {'La Plata', 'General Pueyrredon', 'Bahia Blanca'}
    if missing:
        say(f'not in the population list (taken last): {sorted(missing)}')
        order += [(cities[s], s, s) for s in sorted(missing)]
    if HOST_STOPPED.exists():
        say(f'{HOST} was stopped for good ({HOST_STOPPED.read_text(encoding="utf-8").strip()}): not starting')
        return
    say(f'daily cap {DAILY_CAP}: {_count_today()} requests to {HOST} so far on {_day["day"]} (UTC)')
    th = threading.Thread(target=verifier, daemon=True, name='verifier')
    th.start()
    (WAVE / 'driver.pid').write_text(f'{os.getpid()}\n', encoding='utf-8')
    say(f'SIBOM wave: {len(order)} partidos, pid {os.getpid()}')
    stopped = None
    for sid, sib, name in order:
        if sid in BUILT or (only and sid not in only):
            continue
        try:
            one(sid, sib, name, n_laws)
        except StopWave as e:
            stopped = str(e)
            break
        except E.Stop as e:
            stopped = f'SIBOM host stopped: {e}'
            break
        except Exception as e:
            say(f'{sid} {name}: error {e!r}')
            status(sid, state=f'error: {str(e)[:200]}')
        check_releases()
    if stopped:
        say(f'stopping: {stopped}')
    Q.put(None)
    th.join()
    # wait for autopush to push the last mains, then release those claims (up to 3 hours)
    t0 = time.time()
    while PENDING and time.time() - t0 < 3 * 3600 and not (stopped and stop_requested()):
        check_releases()
        if PENDING:
            time.sleep(300)
    say(f'SIBOM wave finished ({stopped or "all partidos visited"}); claims still held: {sorted(PENDING)}')
    status(0, name='driver', state=f'finished: {stopped or "all partidos visited"}', pending=sorted(PENDING))


if __name__ == '__main__':
    main()
