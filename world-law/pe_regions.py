"""Peru's regions and Lima Metropolitana for git-for-law (gitlaw-scraper-dell, coverage wave 2026-10-31): one public
repo per unit, lexifina/peru-<unit>-law, built by scripts/gitlaw_common/build.py from corpus.d parts of about 50
ordinances, newest first.

Source: El Peruano, Normas Legales (busquedas.elperuano.pe), filtered by the issuing entity (each Gobierno Regional,
and the Municipalidad Metropolitana de Lima). Each ordinance is cut from El Peruano's own PDF extract with the
national builder's cutter (scripts/peru-law/penal/lawtext.py, imported, not changed), shown as published, dated on the
day it took effect. One process; one request at a time to the host, at least 3.2 s apart (sa_probe.fetch).

    python -X utf8 scripts/world-law/pe_regions.py run <unit> [<unit> ...] [--parts=N]
    python -X utf8 scripts/world-law/pe_regions.py letters <unit> <part>
    python -X utf8 scripts/world-law/pe_regions.py publish <unit> <part> <docs-date>

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
import tempfile
import time
import warnings
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DOCS = ROOT.parent.parent
sys.path.insert(0, str(HERE))
warnings.filterwarnings('ignore', category=FutureWarning)
import sa_probe  # noqa: E402
import sa_elperuano  # noqa: E402
import ar_provinces as E  # noqa: E402  (split_units, letters, clean: shared text helpers only)

sys.path.insert(0, str(ROOT / 'peru-law' / 'penal'))
import lawtext  # noqa: E402

SESSION = 'gitlaw-scraper-dell'
CLAIMS = HERE / 'claims'
BASE = 'https://busquedas.elperuano.pe'
PART_SIZE = 50
TZ = 'America/Lima'

# slug: (English name, official name, ISO 3166-2, El Peruano entity code, kind)
UNITS = {
    'lima-metropolitana': ('Lima Metropolitana', 'Municipalidad Metropolitana de Lima', 'PE-LMA', '1384', 'mml'),
    'piura': ('Piura', 'Gobierno Regional de Piura', 'PE-PIU', '1969', 'gr'),
    'la-libertad': ('La Libertad', 'Gobierno Regional de La Libertad', 'PE-LAL', '1977', 'gr'),
    'arequipa': ('Arequipa', 'Gobierno Regional de Arequipa', 'PE-ARE', '1964', 'gr'),
    'cajamarca': ('Cajamarca', 'Gobierno Regional de Cajamarca', 'PE-CAJ', '1959', 'gr'),
    'junin': ('Junín', 'Gobierno Regional de Junín', 'PE-JUN', '1955', 'gr'),
    'cusco': ('Cusco', 'Gobierno Regional del Cusco', 'PE-CUS', '1978', 'gr'),
    'lambayeque': ('Lambayeque', 'Gobierno Regional de Lambayeque', 'PE-LAM', '1960', 'gr'),
    'puno': ('Puno', 'Gobierno Regional de Puno', 'PE-PUN', '1956', 'gr'),
    'ancash': ('Áncash', 'Gobierno Regional de Áncash', 'PE-ANC', '1968', 'gr'),
    'callao': ('Callao', 'Gobierno Regional del Callao', 'PE-CAL', '1974', 'gr'),
    'loreto': ('Loreto', 'Gobierno Regional de Loreto', 'PE-LOR', '1970', 'gr'),
    'ica': ('Ica', 'Gobierno Regional de Ica', 'PE-ICA', '1972', 'gr'),
    'lima': ('Lima (region)', 'Gobierno Regional de Lima', 'PE-LIM', '1965', 'gr'),
    'san-martin': ('San Martín', 'Gobierno Regional de San Martín', 'PE-SAM', '8839', 'gr'),
    'huanuco': ('Huánuco', 'Gobierno Regional de Huánuco', 'PE-HUC', '1966', 'gr'),
    'ayacucho': ('Ayacucho', 'Gobierno Regional de Ayacucho', 'PE-AYA', '1973', 'gr'),
    'ucayali': ('Ucayali', 'Gobierno Regional de Ucayali', 'PE-UCA', '1976', 'gr'),
    'apurimac': ('Apurímac', 'Gobierno Regional de Apurímac', 'PE-APU', '1967', 'gr'),
    'amazonas': ('Amazonas', 'Gobierno Regional de Amazonas', 'PE-AMA', '1962', 'gr'),
    'huancavelica': ('Huancavelica', 'Gobierno Regional de Huancavelica', 'PE-HUV', '1958', 'gr'),
    'tacna': ('Tacna', 'Gobierno Regional de Tacna', 'PE-TAC', '1975', 'gr'),
    'pasco': ('Pasco', 'Gobierno Regional de Pasco', 'PE-PAS', '1963', 'gr'),
    'tumbes': ('Tumbes', 'Gobierno Regional de Tumbes', 'PE-TUM', '1961', 'gr'),
    'moquegua': ('Moquegua', 'Gobierno Regional de Moquegua', 'PE-MOQ', '1971', 'gr'),
    'madre-de-dios': ('Madre de Dios', 'Gobierno Regional de Madre de Dios', 'PE-MDD', '1954', 'gr'),
}

ART109 = ('La ley es obligatoria desde el día siguiente de su publicación en el diario oficial, salvo disposición '
          'contraria de la misma ley que posterga su vigencia en todo o en parte.')
ART9 = ('Artículo 9.- No son objeto de protección por el derecho de autor: [...] b. Los textos oficiales de carácter '
        'legislativo, administrativo o judicial, ni las traducciones oficiales de los mismos, sin perjuicio de la '
        'obligación de respetar los textos y citar la fuente.')
ART9_URL = 'https://cdn.www.gob.pe/uploads/document/file/1669698/DL%20822.pdf.pdf?v=1613082608'


def repo_name(u: str) -> str:
    return f'peru-{u}-law'


def folder(u: str) -> Path:
    return ROOT / repo_name(u)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


class Stop(Exception):
    pass


class Gone(Exception):
    """HTTP 404 for one ordinance's PDF: that ordinance is left out; the host is not blocked."""


def get(url: str) -> bytes:
    for attempt in range(2):
        m = sa_probe.fetch(url, timeout=60)
        if m['status'] == 200 and m['body']:
            if m.get('challenge_markers') and b'<html' in m['body'][:3000].lower() and not url.lower().endswith('.pdf'):
                pass
            return m['body']
        if m['status'] == 404 and url.lower().endswith('.pdf'):
            raise Gone(f'HTTP 404 at {url}')
        if m['status'] in (403, 429, -1):
            raise Stop(f'{m["status"]} {m.get("error", "")} at {url}')
        if m['status'] == 0:
            if attempt == 0:
                time.sleep(20)
                continue
            raise Stop(f'timeout/error at {url}: {m.get("error", "")[:200]}')
        raise Stop(f'HTTP {m["status"]} at {url}')
    raise Stop('unreachable')


# ---------------------------------------------------------------- catalogue

def listing(u: str, start: int, until: str) -> dict:
    code, kind = UNITS[u][3], UNITS[u][4]
    tipo = 'Ordenanzas' if kind == 'mml' else 'ORDENANZA'
    url = (f'{BASE}/?fechaIni=20000101&fechaFin={until}&tipoPublicacion=NL&ci=ONLY&start={start}'
           f'&entidad={code}&tipoDispositivo={quote(tipo)}')
    d = sa_elperuano.page(sa_probe.text(get(url)))
    return d.get('results') or {}


def catalogue(u: str, n: int, until: str) -> list[dict]:
    out, seen, start = [], set(), 0
    while len(out) < n:
        r = listing(u, start, until)
        hits = r.get('hits') or []
        for h in hits:
            if h['op'] in seen:
                continue
            seen.add(h['op'])
            t = (h.get('tipoDispositivo') or '').upper()
            if not t.startswith('ORDENANZA') or 'ERRATA' in (h.get('sumilla') or '').upper()[:30]:
                continue
            out.append(h)
        start += 20
        if not hits or start >= (r.get('totalHits') or 0):
            break
    return out[:n]


# ---------------------------------------------------------------- one ordinance

def number_of(h: dict) -> str:
    return re.sub(r'^N\s*[°º.]*\s*', '', (h.get('numeroDispositivo') or '').strip(), flags=re.I).strip()


def fill_number(h: dict, paras: list[str]) -> dict:
    """El Peruano's index leaves some numbers empty: take it from the ordinance's own heading, else the operation."""
    n = number_of(h)
    if n and re.search(r'(19|20)\d\d', n):
        return h
    m = re.search(r'ORDENANZA(?:\s+REGIONAL)?\s+N\s*[°º.o]*\s*([0-9][\w\-/.]*(?:\s*-\s*[\w/.]+)*)', ' '.join(paras[:4]), re.I)
    t = m.group(1).strip(' .') if m else ''
    if n:
        # the index number without its year: the ordinance's own heading may give the full number
        return {**h, 'numeroDispositivo': 'N° ' + t} if t.startswith(n) and re.search(r'(19|20)\d\d', t) else h
    return {**h, 'numeroDispositivo': 'N° ' + (t or f'(operación {h["op"]})')}


def label_of(u: str, h: dict) -> str:
    kind = 'Ordenanza' if UNITS[u][4] == 'mml' else 'Ordenanza Regional'
    return f'{kind} N° {number_of(h)}'


def pe_in_force(paras: list[str], pub: str, kind: str) -> tuple[str | None, str]:
    """The ordinance's own vigencia clause, else the day after publication."""
    tail = E.fold(' '.join(paras[-30:]))
    rule = ('Ley 27972, art. 44' if kind == 'mml' else 'Ley 27867, art. 42') + ' (as Constitución, art. 109)'
    for s in re.split(r'(?<=[.;])\s+', tail):
        if not re.search(r'(PRESENTE|ESTA)\s+(ORDENANZA|NORMA|DISPOSICION)\b[^.]{0,80}?'
                         r'(ENTRA|ENTRARA|REGIRA|RIGE|TENDRA\s+VIGENCIA|COBRA|COBRARA|SURTE|SURTIRA)\b', s):
            continue
        if re.search(r'DIA\s+SIGUIENTE', s) and 'PUBLICACION' in s:
            return E._add(pub, 1), 'its own clause: the day after publication'
        if re.search(r'(DESDE|A\s+PARTIR\s+DE(L\s+DIA\s+DE)?|EL\s+(MISMO\s+)?DIA\s+DE|AL\s+DIA\s+DE|CON\s+)\s*(LA\s+FECHA\s+DE\s+)?SU\s+PUBLICACION', s):
            return pub, 'its own clause: from publication'
        m = re.search(r'(\d{1,2})\s*(?:[°º]\s*)?DE\s+(' + '|'.join(E.MONTHS) + r')\s+(?:DE|DEL)\s+(?:ANO\s+)?(\d{4})', s)
        if m:
            try:
                d = date(int(m.group(3)), E.MONTHS[m.group(2)], int(m.group(1))).isoformat()
            except ValueError:
                d = None
            if d and d >= pub[:4] + '-01-01':
                return d, 'its own clause: the date it names'
        return None, 'a vigencia clause this reader does not resolve: ' + s[:160]
    return E._add(pub, 1), f'default rule: the day after publication ({rule})'


def _single_lines():
    """lawtext.lines with no top/bottom band: in El Peruano's single-norm PDFs ("representación impresa") the furniture
    is set in other faces (dropped by lawtext's font rule), and the body can start right at the top of a page."""
    import inspect
    src = inspect.getsource(lawtext.lines)
    new = src.replace('top, bottom = 80, page.rect.height - 20', 'top, bottom = 0, page.rect.height')
    assert new != src
    ns = dict(lawtext.__dict__)
    exec(compile(new, lawtext.__file__, 'exec'), ns)
    return ns['lines']


_SINGLE = None
PDFDIR = sa_probe.CACHE / 'pdf'


def is_single(pdf: bytes) -> bool:
    import pymupdf
    with pymupdf.open(stream=pdf, filetype='pdf') as d:
        t = d[0].get_text()
    return 'representación impresa' in t and 'OP N' in t


def cut(op: str, pdf: bytes) -> list[str]:
    global _SINGLE
    PDFDIR.mkdir(parents=True, exist_ok=True)
    p = PDFDIR / f'{op}.pdf'
    if not p.exists():
        p.write_bytes(pdf)
    orig = lawtext.lines
    try:
        if is_single(pdf):
            if _SINGLE is None:
                _SINGLE = _single_lines()
            lawtext.lines = lambda doc, elperuano=True: _SINGLE(doc, elperuano) + [
                (10 ** 6, 0, 0, 0, 0, op, 0, 0, '')]
        return lawtext.paragraphs(p, op, r'ORDENANZA')
    except SystemExit as e:
        raise ValueError(str(e)[:200])
    finally:
        lawtext.lines = orig


def build_act(u: str, h: dict, paras: list[str], pdf: bytes, used: set) -> tuple[dict, dict, dict] | None:
    pub = f'{h["fechaPublicacion"][:4]}-{h["fechaPublicacion"][4:6]}-{h["fechaPublicacion"][6:8]}'
    f, basis = pe_in_force(paras, pub, UNITS[u][4])
    if not f:
        return None
    units = E.split_units(paras)
    lab = label_of(u, h)
    key = E.ascii_slug(lab.replace('N°', ''))
    url = BASE + h['urlPDF']
    page = f'{BASE}/dispositivo/NL/{h["op"]}'
    law = {'label': lab, 'title': f'{lab}: {h.get("sumilla") or ""}'.strip(': ')[:300], 'kind': 'law',
           'enacted': None, 'published': pub, 'url': page, 'temporary_until': None, 'restores': None,
           'note': f'Published in El Peruano, Normas Legales, {pub} (operación {h["op"]}). In force {f} ({basis}).'}
    s = E.ascii_slug(number_of(h)) or key
    s = ('ordenanza-' if UNITS[u][4] == 'mml' else 'ordenanza-regional-') + s
    base, k = s, 2
    while s in used:
        s, k = f'{base}-{k}', k + 1
    used.add(s)
    v = {'from': f, 'source_url': url, 'sha256': hashlib.sha256(pdf).hexdigest(), 'units': units, 'credits': {},
         'note': (f'As published in El Peruano, Normas Legales, {pub} (operación {h["op"]}): the oldest version '
                  f'available from this source, which publishes no consolidated texts. In force {f} ({basis}). '
                  'Later ordinances that amend it are separate entries; their changes are not applied to this text.')}
    act = {'slug': s, 'short': lab, 'title': f'{lab}: {h.get("sumilla") or ""}'.strip(': ')[:300], 'url': page,
           'first_law': key, 'earlier_laws': [], 'versions': [v]}
    return act, {key: law}, {'units': len(units), 'from': f, 'op': h['op']}


# ---------------------------------------------------------------- parts

def country_block(u: str) -> dict:
    en, native, code, _, kind = UNITS[u]
    return {
        'code': code, 'name': en, 'slug': f'peru-{u}', 'lang': 'es', 'tz': TZ, 'future_branch': 'futuro',
        'publisher': {'name': native, 'email': f'normas@{u}.elperuano.invalid'},
        'default_in_force_rule': {'text': 'Constitución Política del Perú, art. 109: "' + ART109 + '" '
                                  + ('Ley Orgánica de Municipalidades (Ley 27972), art. 44, applies the same rule to '
                                     'municipal ordinances' if kind == 'mml' else
                                     'Ley Orgánica de Gobiernos Regionales (Ley 27867), art. 42, applies the same rule '
                                     'to regional norms') + ': in force from the day after publication in El Peruano '
                                  'unless the norm itself names another day.',
                                  'source': 'https://www.congreso.gob.pe'},
        'licence_note': f'Fuente: Diario Oficial El Peruano, Normas Legales ({BASE}). Textos oficiales de carácter '
                        'legislativo, no protegidos por el derecho de autor (Decreto Legislativo 822, art. 9 b).',
    }


AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which ordinances to include; it wrote no law '
          'text. Every word of law comes from El Peruano\'s own PDF extracts.']


def decisions(u: str) -> list[str]:
    kind = UNITS[u][4]
    return [
        'Source: the Diario Oficial El Peruano, Normas Legales, which publishes every ordinance of '
        f'{UNITS[u][1]} as enacted. It publishes no consolidated texts, so each ordinance is shown once, as published '
        '(the oldest version available), dated on the day it took effect. An ordinance that amends another is its '
        'own entry; its changes are not applied to the earlier text.',
        'In-force day: the ordinance\'s own vigencia clause (the day after publication, from publication, or a named '
        'date); otherwise the day after publication (Constitución, art. 109; '
        + ('Ley 27972, art. 44' if kind == 'mml' else 'Ley 27867, art. 42') + '). An ordinance whose vigencia '
        'clause this reader cannot resolve is left out.',
        'Text: the ordinance is cut from El Peruano\'s PDF extract, from the end of the previous norm to the '
        'operation number printed under it. El Peruano\'s own furniture (running heads, section headings, its '
        'summary title above the norm, the operation number) is not part of the text. Annexes that El Peruano does '
        'not print are not included.',
        'Units: the heading (encabezado: number, considerandos and enacting formula, everything before Artículo 1) '
        'and one file per article, holding the article and everything printed after it up to the next article '
        '(dispositions, signatures). Nothing printed between those bounds is dropped. One paragraph per line, '
        'spacing normalised, words broken at a line end joined.',
        'Ordinances are added newest first, in parts of about 50.',
    ]


def source_block(retrieved: str) -> dict:
    return {'name': 'Diario Oficial El Peruano, Normas Legales (Empresa Peruana de Servicios Editoriales S.A. - '
                    'Editora Perú)', 'url': BASE, 'retrieved': retrieved,
            'licence': 'Official texts of a legislative nature: not protected by copyright in Peru (Decreto '
                       'Legislativo 822, Ley sobre el Derecho de Autor, art. 9 b: "' + ART9 + '"). The source states '
                       'no restriction on reuse. Reproduced with attribution, respecting the text.',
            'notes': 'Each ordinance\'s PDF extract (/api/archivo/file/<token>/*/<operación>.pdf), found through the '
                     'search site filtered by the issuing entity.'}


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def stage_dir(u: str) -> Path:
    """Older parts wait here, out of corpus.d, until the whole batch is verified (the autopush never sees them)."""
    return folder(u) / '.tmp' / 'stage'


def parse_part(u: str, name: str, items: list[tuple[dict, list[str], bytes]], docs_date: str,
               out_dir: Path | None = None) -> dict:
    out = (out_dir or folder(u) / 'corpus.d') / f'{name}.json'
    if out.with_suffix('.PUBLISH').exists():
        return {'skipped': 'published'}
    used, laws_seen = set(), {}
    for p in sorted(list((folder(u) / 'corpus.d').glob('*.json')) + list(stage_dir(u).glob('*.json'))):
        if p.stem == name:
            continue
        pj = json.loads(p.read_text(encoding='utf-8'))
        used.update(a['slug'] for a in pj.get('acts', []))
        laws_seen.update(pj.get('laws', {}))
    acts, laws, rep = [], {}, {}
    for h, paras, pdf in items:
        r = build_act(u, h, paras, pdf, used)
        if r is None:
            rep[h['op']] = {'left out': 'vigencia clause not resolved'}
            continue
        a, l, info = r
        if a['versions'][0]['from'] == docs_date:
            used.discard(a['slug'])
            rep[h['op']] = {'deferred': 'in force on the retrieval day'}
            continue
        clash = any(k in laws_seen or k in laws for k in l)
        n = number_of(h)
        if clash and n and not re.search(r'(19|20)\d\d', n):
            # numbering that restarts each year ("N° 006"): the year of publication tells two of them apart
            used.discard(a['slug'])
            r = build_act(u, {**h, 'numeroDispositivo': f'N° {n} ({h["fechaPublicacion"][:4]})'}, paras, pdf, used)
            a, l, info = r
            clash = any(k in laws_seen or k in laws for k in l)
        if clash:
            used.discard(a['slug'])
            rep[h['op']] = {'left out': 'law key already used (same number twice)'}
            continue
        laws.update(l)
        acts.append(a)
        rep[a['slug']] = info
    has_first = any(p.stem < name for p in (folder(u) / 'corpus.d').glob('*.json') if p.stem != name)
    part = {'country': country_block(u), 'laws': dict(sorted(laws.items())), 'acts': acts}
    if not has_first:
        part.update(sources=[source_block(docs_date)], decisions=decisions(u), ai_use=AI_USE)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_part(out, part)
    return rep


# ---------------------------------------------------------------- letters check (independent reader: poppler)

_DAY = r'(?:Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo)'
_DATE = _DAY + r'\d{1,2}de[a-zé]+de\d{4}'
FURNITURE = re.compile(r'(?:FirmadoporEditoraPer[uú]Fecha\d+'
                       r'|\d{0,6}NORMASLEGALES(?:' + _DATE + r')?ElPeruano\d{0,6}'
                       r'|ElPeruano' + _DATE + r'NORMASLEGALES\d{0,6}'
                       r'|\d{0,6}NORMASLEGALES' + _DATE + r'\d{0,6}'
                       # single-norm PDFs ("representación impresa"): the verification notice and masthead on each page
                       r'|Estaesunarepresentaci[oó]nimpresa\w{0,400}?C[oó]digodevalidaci[oó]nOPN[º°o]?\d{6,8}'
                       r'|C[oó]digodevalidaci[oó]nOPN[º°o]?\d{6,8}'
                       r'|Estaesunarepresentaci[oó]nimpresa\w{0,400}?elperuanopeVerificador'
                       r'|FUNDADOEL22DEOCTUBREDE1825PORELLIBERTADORSIM[OÓ]NBOL[IÍ]VAR'
                       r'|DIARIOOFICIALDELBICENTENARIO|\d{3}a[nñ]os|GerentedePublicacionesOficiales(?:[A-ZÁÉÍÓÚ][a-záéíóú]+){0,4}'
                       r'|NORMASLEGALES|ElPeruano|GOBIERNOSLOCALES|GOBIERNOSREGIONALES|' + _DATE + r'|\d{1,4}(?=NORMASLEGALES)'
                       r')+', re.I)


def source_letters(pdf: bytes, raw: bool = False) -> str:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'x.pdf'
        f.write_bytes(pdf)
        out = subprocess.run(['pdftotext'] + (['-raw'] if raw else []) + ['-enc', 'UTF-8', str(f), '-'],
                             capture_output=True)
        return E.letters(out.stdout.decode('utf-8', 'replace'))


def check_letters(mine: str, src: str) -> str | None:
    """None when `mine` is `src` letter for letter, in order, with nothing between but whole El Peruano furniture
    tokens (signature stamp, running head with page number and date)."""
    i = src.find(mine[:40])
    if i < 0:
        return 'start not found in source'
    p, j, run = 0, i, 0          # run: letters matched since the last skip (how far a skip may reach back)
    while p < len(mine):
        if j < len(src) and src[j] == mine[p]:
            p, j, run = p + 1, j + 1, run + 1
            continue
        # a mismatch: El Peruano furniture starting here, or a few letters back (its first letters may have matched
        # the law text by chance), is skipped whole; anything else is a difference
        for back in range(0, min(run, 12) + 1):
            m = FURNITURE.match(src, j - back)
            if m and m.end() > j:
                # a page number at the end of the furniture may run straight into digits of the law text
                # ("ElPeruano" + "2 de la Ley"): give back trailing digits until the law text continues
                e = m.end()
                while e > j and src[e - 1].isdigit() and not (e < len(src) and src[e] == mine[p - back]):
                    e -= 1
                if not (e < len(src) and src[e] == mine[p - back]):
                    e = m.end()
                p, j, run = p - back, e, 0
                break
        else:
            return f'differs at letter {p}: corpus {mine[max(0, p - 30):p + 30]!r} source {src[max(0, j - 30):j + 30]!r}'
    return None


def letters_check(u: str, part_name: str, src_dir: Path | None = None) -> list[str]:
    part = json.loads(((src_dir or folder(u) / 'corpus.d') / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        for v in act['versions']:
            m = sa_probe.fetch(v['source_url'])
            b = m.get('body') if m.get('cached') else None
            if not b or hashlib.sha256(b).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]}: source missing or sha256 differs')
                continue
            mine = E.letters(''.join(x['text'] for x in v['units'].values()))
            err = check_letters(mine, source_letters(b))
            if err:
                err2 = check_letters(mine, source_letters(b, raw=True))
                if err2:
                    probs.append(f'{act["slug"]}: {err}')
    return probs


# ---------------------------------------------------------------- docs, scaffold, verify, publish

def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][x.month - 1]} {x.year}'


def write_docs(u: str, docs_date: str, extra=(), out: Path | None = None, src: Path | None = None):
    en, native, code, _, kind = UNITS[u]
    if src is not None:  # a scratch corpus.d: every part in it counts
        parts = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(src.glob('*.json'))]
    else:
        parts = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((folder(u) / 'corpus.d').glob('*.json'))
                 if p.with_suffix('.PUBLISH').exists() or p.stem in extra]
    rows, n = [], 0
    for part in parts:
        for a in part['acts']:
            n += 1
            t = a['title'].replace('|', '/')
            rows.append(f'| `{a["slug"]}/` | {t[:160]}{"…" if len(t) > 160 else ""} | in force {_long(a["versions"][0]["from"])} |')
    who = 'Lima Metropolitana (the Municipalidad Metropolitana de Lima, which exercises regional functions over the ' \
          'province of Lima)' if kind == 'mml' else f'the {en} region of Peru ({native})'
    what = 'ordinances (ordenanzas) of the Concejo Metropolitano' if kind == 'mml' else \
        'regional ordinances (ordenanzas regionales) of the Consejo Regional'
    repo = out or (folder(u) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en}: law history in git

The {what} of {who}, as a git history: one folder per ordinance, one file per article, one commit per ordinance on the day it took effect.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{code.lower()}/`. Peru's national law is in [lexifina/peru-law](https://github.com/lexifina/peru-law).

The text is in Spanish, exactly as El Peruano prints it.

## What this repository holds

{n} ordinance{"s" if n != 1 else ""} so far, newest first, added in parts of about 50. Each is shown **as published in El Peruano** (the oldest version available from this source): El Peruano publishes no consolidated texts, so an ordinance that amends another is its own entry and its changes are not applied to the earlier text.

| Folder | Ordinance | Date |
| --- | --- | --- |
{chr(10).join(rows)}

## Source

Diario Oficial El Peruano, Normas Legales (Editora Perú), <{BASE}>: each ordinance's own PDF extract, found by filtering the search site by the issuing entity ({native.upper()}).

## Dates

- Each commit is dated at **noon, {TZ}, on the day the ordinance took effect**: the day its own vigencia clause names, or otherwise the day after its publication in El Peruano (Constitución Política del Perú, art. 109: "{ART109}"; {'Ley 27972, art. 44' if kind == 'mml' else 'Ley 27867, art. 42'}, applies the same rule).
- Ordinances that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.

## Files

`<ordinance>/art-005.md` is Artículo 5; `encabezado.md` holds the number, the considerandos and the enacting formula, everything printed before Artículo 1. Dispositions and signatures stay in the file of the article they follow. One paragraph per line. El Peruano's summary title, running heads and operation number are not included.

## How it is checked

- Every version of every ordinance is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every ordinance appear in El Peruano's PDF, read again with an independent reader (poppler's pdftotext), in the same order, with nothing between them but page furniture (running heads and page numbers), so no word is lost or added.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## Limits

This is not an official publication. The binding text is the one published in El Peruano. Only the ordinances listed above are included; annexes El Peruano does not print are not included, and later amendments are not applied.

## En español

Ordenanzas de {native}, tal como se publicaron en el Diario Oficial El Peruano, como historial git: una carpeta por ordenanza, un archivo por artículo, un commit por ordenanza en el día de su entrada en vigencia. No es una publicación oficial.
"""
    lic = f"""The law texts in this repository are official texts of {native} (Peru), taken from the Diario Oficial
El Peruano, Normas Legales, {BASE} (consulted {docs_date}).

They are official texts of a legislative nature. Peru's copyright law, Decreto Legislativo 822 (Ley sobre el Derecho
de Autor), excludes them from protection:

  "{ART9}"

  (official copy: {ART9_URL})

El Peruano states no restriction on reuse. They are reproduced here respecting the text and citing the source:
Fuente: Diario Oficial El Peruano, Normas Legales.

Changes made by Lexifina: each ordinance was cut from El Peruano's page extract and split into one Markdown file per
article, one paragraph per line, with spacing normalised and words broken at a line end joined; the wording was not
changed. Neither {native} nor Editora Perú endorses this repository. This repository is not an official publication;
the binding text is the one published in El Peruano.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': code.lower(), 'code': code, 'name': en,
             'level': 'metropolitan municipality with regional functions' if kind == 'mml' else 'region',
             'parent': 'pe', 'repo': f'https://github.com/lexifina/{repo_name(u)}',
             'build': f'built: {n} ordinances as published in El Peruano', 'language': 'es', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


def scaffold(u: str) -> str:
    en, native = UNITS[u][:2]
    repo = repo_name(u)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = E.run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    E.run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
          '-f', f'description={en} (Peru) law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    E.run('git', 'init', '-q', '-b', 'main', cwd=d)
    E.run('git', 'config', 'core.autocrlf', 'false', cwd=d)
    (d / 'README.md').write_text(f"""# {en}: law as git history

Work in progress. This repository will hold the ordinances of {native} (Peru) as a git history: one file per
article, one commit per ordinance on the day it took effect.

Source: Diario Oficial El Peruano, Normas Legales, <{BASE}>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text(f"""# Sources

- Diario Oficial El Peruano, Normas Legales: <{BASE}>

The terms and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    E.run('git', 'add', '-A', cwd=d)
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-10-31T12:00:00-0500', GIT_COMMITTER_DATE='2026-10-31T12:00:00-0500')
    subprocess.run(['git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
                    f'Peru ({en}): sources, before any law'], cwd=d, env=env, check=True)
    E.run('git', 'remote', 'add', 'origin', remote, cwd=d)
    for attempt in range(4):
        p = E.run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
        if p.returncode == 0:
            break
        time.sleep(10 * (attempt + 1))
    E._rm(d)
    return 'CREATED ' + E.run('git', 'ls-remote', remote, check=False).stdout.strip()[:60]


def verify_part(u: str, part: str, docs_date: str) -> tuple[bool, str]:
    probs = letters_check(u, part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[:3]}'
    src = folder(u)
    tmp = DOCS / f'{repo_name(u)}-verify'
    build = DOCS / f'{repo_name(u)}-verifybuild'
    for d in (tmp, build):
        E._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()] + [part]
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(u, docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = E._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
                '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-600:]
    c = E._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, 'check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force'):
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
    pj = json.loads((src / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    acts = pj['acts']
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} ordinance(s), {days[0]}..{days[-1]}, from {BASE}: letters and digits of every ordinance '
            f'appear in order in its El Peruano PDF (independent reader: pdftotext), with only page furniture between; '
            f'scratch build of verified parts + this part: check.py {res.get("versions")} versions, 0 mismatches, '
            f'0 trailer errors, 0 merges ({docs_date}).')
    E._rm(tmp)
    E._rm(build)
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
            f.write(f'{SESSION} {now()} (South American regional units: Peru, {UNITS[u][1]})\n')
        return True
    except FileExistsError:
        return p.read_text(encoding='utf-8', errors='replace').startswith(SESSION)


def progress(u: str, line: str):
    p = folder(u) / 'PROGRESS.md'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'# {repo_name(u)} (private progress, gitlaw-scraper-dell)\n\nBuilder: '
                     f'scripts/world-law/pe_regions.py; source {BASE} (entidad {UNITS[u][3]}).\n\n',
                     encoding='utf-8', newline='\n')
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {now()} {line}\n')


def cpu_ok() -> bool:
    try:
        last = Path(os.environ['LOCALAPPDATA'], 'gitlaw-cpu.log').read_text(encoding='utf-8').strip().splitlines()[-1]
        return int(re.search(r'cpu5=(\d+)', last).group(1)) <= 90 and int(re.search(r'ram=(\d+)', last).group(1)) <= 85
    except Exception:
        return True


def _attempted(u: str) -> tuple[set, set]:
    """(ops in a published part, ops tried in any part report)."""
    pub, tried = set(), set()
    for f in (folder(u) / 'corpus.d').glob('*.json'):
        if f.with_suffix('.PUBLISH').exists():
            pub.update(re.findall(r'operación (\d+-\d+)', f.read_text(encoding='utf-8')))
    for f in (folder(u) / '.tmp').glob('parse-*.json'):
        d = json.loads(f.read_text(encoding='utf-8'))
        for k, v in d.items():
            tried.add(v.get('op') or k)
    return pub, tried | pub


def do_part(u: str, name: str, members: list[dict], docs_date: str):
    items, left = [], {}
    for h in members:
        pdf = get(BASE + h['urlPDF'])
        try:
            ps = cut(h['op'], pdf)
            mine = E.letters(''.join(x['text'] for x in E.split_units(ps).values()))
            err = check_letters(mine, source_letters(pdf, raw=True)) and check_letters(mine, source_letters(pdf))
            if err:
                left[h['op']] = f'letters: {err[:200]}'
                continue
            items.append((fill_number(h, ps), ps, pdf))
        except Exception as e:  # noqa: BLE001  (a reader problem leaves that ordinance out, never the part)
            left[h['op']] = f'cut failed: {str(e)[:200]}'
    while not cpu_ok():
        time.sleep(60)
    rep = parse_part(u, name, items, docs_date)
    rep.update({k: {'left out': v} for k, v in left.items()})
    (folder(u) / '.tmp').mkdir(exist_ok=True)
    (folder(u) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                           encoding='utf-8')
    if not any('units' in v for v in rep.values()):
        say(f'{u} {name}: nothing to add')
        progress(u, f'{name}: nothing to add ({len(left)} left out)')
        (folder(u) / 'corpus.d' / f'{name}.json').unlink(missing_ok=True)
        return
    r = E._low([sys.executable, '-X', 'utf8', str(Path(__file__)), 'publish', u, name, docs_date])
    out = (r.stdout.strip().splitlines() or [''])[-1] + (r.stderr.strip()[-300:] if r.returncode else '')
    say(f'{u} {name}: {out[:300]}')
    progress(u, f'{name}: {out[:700]}')


def _next_name(u: str, prefix: str) -> str:
    k = 1
    while (folder(u) / 'corpus.d' / f'{prefix}-{k:02d}.PUBLISH').exists():
        k += 1
    return f'{prefix}-{k:02d}'


def drive(u: str, docs_date: str, nparts: int, recover: bool = False):
    if not claim(u):
        say(f'{u}: claimed by another session, skipped')
        return
    folder(u).mkdir(exist_ok=True)
    gi = folder(u) / '.gitignore'
    if not gi.exists():
        gi.write_text('.tmp/\n', encoding='utf-8', newline='\n')
    until = docs_date.replace('-', '')
    pub, tried = _attempted(u)
    cat = catalogue(u, len(tried) + PART_SIZE * nparts + 10, until)
    if not cat:
        progress(u, 'catalogue: no ordinances listed')
        say(f'{u}: no ordinances')
        return
    say(f'{u}: scaffold {scaffold(u)}')
    progress(u, f'catalogue: {len(cat)} ordinances listed (newest {cat[0]["fechaPublicacion"]}, '
                f'oldest {cat[-1]["fechaPublicacion"]}); {len(pub)} published, {len(tried)} tried before')
    if recover:
        retry = [h for h in cat if h['op'] in tried and h['op'] not in pub]
        if retry:
            do_part(u, _next_name(u, '31-recuperadas'), retry, docs_date)
    fresh = [h for h in cat if h['op'] not in tried]
    done = sum(1 for f in (folder(u) / 'corpus.d').glob('30-ordenanzas-*.PUBLISH'))
    for i in range(nparts):
        members = fresh[i * PART_SIZE:(i + 1) * PART_SIZE]
        if not members:
            break
        do_part(u, f'30-ordenanzas-{done + i + 1:02d}', members, docs_date)


# ---------------------------------------------------------------- older ordinances (round 2, 2026-10-31)
# Older ordinances land inside published history, so each batch of 3-6 parts is a full rebuild (the autopush's
# standing yes for verified rebuilds: old tip archived, leased push). A batch is staged in .tmp/stage, never in
# corpus.d, until it passes: letters check of every new part (pdftotext), check.py clean on a scratch build of every
# published part plus the batch, and every already-published ordinance's final tree identical, folder by folder, to
# the one on the published main (or futuro) the remote holds now. Only then are PUBLISH and the parts moved in.

OLDER_PREFIX = '32-anteriores'


def claim_older(u: str) -> bool:
    p = CLAIMS / f'{repo_name(u)}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'{SESSION} {now()} (South American regional units: Peru, {UNITS[u][1]}; older ordinances, '
                    'via global-law-main-composer)\n')
        return True
    except FileExistsError:
        txt = p.read_text(encoding='utf-8', errors='replace')
        if not txt.startswith(SESSION):
            return False
        with open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.write(f'{now()} older ordinances (round 2)\n')
        return True


def remote_heads(u: str) -> dict[str, str]:
    r = E.run('git', 'ls-remote', '--heads', f'https://github.com/lexifina/{repo_name(u)}.git', check=False)
    out = {}
    for line in r.stdout.splitlines():
        sha, _, ref = line.partition('\t')
        out[ref.replace('refs/heads/', '')] = sha
    return out


def _tree(repo: Path, rev: str, path: str) -> str | None:
    r = subprocess.run(['git', 'rev-parse', '-q', '--verify', f'{rev}:{path}'], cwd=repo, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def identity_check(u: str, build: Path, published: list[Path]) -> tuple[bool, str]:
    """Every act of every published part: its folder's tree in the scratch build equals its folder's tree on the
    remote's main (or futuro), read from the local clone's objects."""
    heads = remote_heads(u)
    clone = DOCS / repo_name(u)
    if 'main' not in heads:
        return False, 'remote main not listed by ls-remote'
    for b, sha in heads.items():
        if subprocess.run(['git', 'cat-file', '-e', f'{sha}^{{commit}}'], cwd=clone, capture_output=True).returncode:
            return False, f'remote {b} {sha[:9]} not in the local clone (autopush has not fetched it)'
    order = ['main'] + [b for b in heads if b != 'main']
    n, bad = 0, []
    for p in published:
        for a in json.loads(p.read_text(encoding='utf-8'))['acts']:
            s = a['slug']
            old = next(((b, t) for b in order if (t := _tree(clone, heads[b], s))), None)
            new = next(((b, t) for b in order if (t := _tree(build, f'refs/heads/{b}', s))), None)
            if not old or not new or old != new:
                bad.append(f'{s}: published {old} rebuild {new}')
            n += 1
    if bad:
        return False, f'{len(bad)} of {n} published ordinances differ: {bad[:3]}'
    return True, f'{n} published ordinances byte-identical (final tree per folder vs remote main {heads["main"][:9]})'


def stage_part(u: str, name: str, members: list[dict], docs_date: str) -> bool:
    items, left = [], {}
    for h in members:
        while not cpu_ok():
            time.sleep(60)
        try:
            pdf = get(BASE + h['urlPDF'])
        except Gone as e:
            left[h['op']] = f'source missing: {e}'
            continue
        try:
            ps = cut(h['op'], pdf)
            mine = E.letters(''.join(x['text'] for x in E.split_units(ps).values()))
            err = check_letters(mine, source_letters(pdf, raw=True)) and check_letters(mine, source_letters(pdf))
            if err:
                left[h['op']] = f'letters: {err[:200]}'
                continue
            items.append((fill_number(h, ps), ps, pdf))
        except Exception as e:  # noqa: BLE001  (a reader problem leaves that ordinance out, never the part)
            left[h['op']] = f'cut failed: {str(e)[:200]}'
    rep = parse_part(u, name, items, docs_date, out_dir=stage_dir(u))
    rep.update({k: {'left out': v} for k, v in left.items()})
    (folder(u) / '.tmp').mkdir(exist_ok=True)
    (folder(u) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                           encoding='utf-8')
    added = sum(1 for v in rep.values() if 'units' in v)
    say(f'{u} {name}: staged {added}, left out {len(rep) - added}')
    progress(u, f'{name}: staged {added} ordinance(s) ({len(rep) - added} left out or deferred)')
    if not added:
        (stage_dir(u) / f'{name}.json').unlink(missing_ok=True)
    return bool(added)


def publish_batch(u: str, names: list[str], docs_date: str) -> str:
    src, st = folder(u), stage_dir(u)
    for n in names:
        probs = letters_check(u, n, st)
        if probs:
            return f'NOT VERIFIED {n}: letters check: {len(probs)} problems: {probs[:3]}'
    published = [p for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    tmp, build = DOCS / f'{repo_name(u)}-verify', DOCS / f'{repo_name(u)}-verifybuild'
    for d in (tmp, build):
        E._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    for p in published:
        shutil.copy2(p, tmp / 'corpus.d' / p.name)
    for n in names:
        shutil.copy2(st / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(u, docs_date, out=tmp / 'repo', src=tmp / 'corpus.d')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = E._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
                '--docs-date', docs_date], env=env)
    if b.returncode:
        return 'NOT VERIFIED build failed: ' + (b.stderr or b.stdout)[-600:]
    c = E._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return 'NOT VERIFIED check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force'):
        return 'NOT VERIFIED check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
    for _attempt in range(16):
        ok, ident = identity_check(u, build, published)
        # Only published ordinances the remote does not hold yet (the autopush has not pushed the previous batch, or
        # has not fetched it): wait for it. Any real difference fails at once.
        if ok or not re.search(r'published None|not in the local clone', ident) or re.search(r"published \('", ident):
            break
        time.sleep(60)
    if not ok:
        return 'NOT VERIFIED identity: ' + ident
    # Every check passed: PUBLISH each part, then move it into corpus.d, then the docs.
    lines = []
    for n in names:
        acts = json.loads((st / f'{n}.json').read_text(encoding='utf-8'))['acts']
        days = sorted(v['from'] for a in acts for v in a['versions'])
        line = (f'{len(acts)} ordinance(s), {days[0]}..{days[-1]}, from {BASE}: letters and digits of every ordinance '
                f'appear in order in its El Peruano PDF (independent reader: pdftotext), with only page furniture '
                f'between; scratch build of verified parts + batch {",".join(names)}: check.py {res.get("versions")} '
                f'versions, 0 mismatches, 0 trailer errors, 0 merges; {ident} ({docs_date}).')
        (src / 'corpus.d' / f'{n}.PUBLISH').write_text(line + '\n', encoding='utf-8', newline='\n')
        os.replace(st / f'{n}.json', src / 'corpus.d' / f'{n}.json')
        lines.append(f'{n}: {len(acts)}')
    write_docs(u, docs_date)
    E._rm(tmp)
    E._rm(build)
    return f'PUBLISH {"; ".join(lines)}; check.py {res.get("versions")} versions clean; {ident}'


def older(u: str, docs_date: str, nparts: int) -> str:
    """One batch of up to nparts older parts. Returns 'done' when El Peruano lists nothing older, else a status."""
    if not claim_older(u):
        return 'claimed by another session'
    until = docs_date.replace('-', '')
    for p in stage_dir(u).glob('*.json'):  # a batch left staged by an interrupted run is dropped and refetched
        p.unlink()
        (folder(u) / '.tmp' / f'parse-{p.stem}.json').unlink(missing_ok=True)
    pub, tried = _attempted(u)
    want = len(tried) + PART_SIZE * nparts + 10
    cat = catalogue(u, want, until)
    fresh = [h for h in cat if h['op'] not in tried]
    exhausted = len(cat) < want
    progress(u, f'older: catalogue {len(cat)} listed (oldest {cat[-1]["fechaPublicacion"] if cat else "-"}); '
                f'{len(pub)} published, {len(tried)} tried, {len(fresh)} new')
    if not fresh:
        return 'done'
    # numbered after every part ever staged (published, empty or rejected), so a report is never overwritten
    k = len(list((folder(u) / '.tmp').glob(f'parse-{OLDER_PREFIX}-*.json')))
    names = []
    for i in range(nparts):
        members = fresh[i * PART_SIZE:(i + 1) * PART_SIZE]
        if not members:
            break
        n = f'{OLDER_PREFIX}-{k + len(names) + 1:02d}'
        if stage_part(u, n, members, docs_date):
            names.append(n)
    if names:
        while not cpu_ok():
            time.sleep(60)
        r = E._low([sys.executable, '-X', 'utf8', str(Path(__file__)), 'publish-batch', u, docs_date, *names])
        out = (r.stdout.strip().splitlines() or [''])[-1] + (r.stderr.strip()[-300:] if r.returncode else '')
        say(f'{u} {",".join(names)}: {out[:400]}')
        progress(u, f'{",".join(names)}: {out[:900]}')
        if not out.startswith('PUBLISH'):
            for n in names:  # a failed batch never reaches corpus.d; its ops stay "tried" (parse reports)
                f = stage_dir(u) / f'{n}.json'
                if f.exists():
                    os.replace(f, folder(u) / '.tmp' / f'{n}.rejected.json')
            return 'batch failed: ' + out[:200]
    return 'done' if exhausted and len(fresh) <= nparts * PART_SIZE else 'more'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    cmd = sys.argv[1]
    if cmd == 'run':
        args = [a for a in sys.argv[2:] if not a.startswith('--')]
        np_ = next((int(a.split('=')[1]) for a in sys.argv[2:] if a.startswith('--parts=')), 1)
        rec_ = '--recover' in sys.argv[2:]
        dd = dt.date.today().isoformat()
        for u_ in args:
            try:
                drive(u_, dd, np_, rec_)
            except Stop as e:
                say(f'{u_}: STOPPED {e}')
                progress(u_, f'STOPPED: {e}')
                break
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'publish-batch':
        print(publish_batch(sys.argv[2], sys.argv[4:], sys.argv[3]))
    elif cmd == 'older':
        # older <unit> [<unit> ...] [--parts=N] [--date=YYYY-MM-DD] [--batches=K]: per unit, batches of N parts until
        # El Peruano lists nothing older (or K batches), largest units first as given
        args = [a for a in sys.argv[2:] if not a.startswith('--')]
        np_ = next((int(a.split('=')[1]) for a in sys.argv[2:] if a.startswith('--parts=')), 4)
        dd = next((a.split('=')[1] for a in sys.argv[2:] if a.startswith('--date=')), dt.date.today().isoformat())
        nb = next((int(a.split('=')[1]) for a in sys.argv[2:] if a.startswith('--batches=')), 10 ** 6)
        for u_ in args:
            try:
                for _ in range(nb):
                    st_ = older(u_, dd, np_)
                    say(f'{u_}: {st_}')
                    if st_ != 'more':
                        break
                progress(u_, f'older: stopped with "{st_}"')
            except Stop as e:
                say(f'{u_}: STOPPED {e}')
                progress(u_, f'STOPPED: {e}')
                break
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
    elif cmd == 'dry':
        # catalogue + cut + parse a few, no claim / repo / part
        u_ = sys.argv[2]
        cat = catalogue(u_, int(sys.argv[3]), dt.date.today().strftime('%Y%m%d'))
        for h in cat:
            pdf = get(BASE + h['urlPDF'])
            try:
                ps = cut(h['op'], pdf)
            except ValueError as e:
                print(h['op'], 'CUT FAIL', e)
                continue
            pub = f'{h["fechaPublicacion"][:4]}-{h["fechaPublicacion"][4:6]}-{h["fechaPublicacion"][6:8]}'
            f, basis = pe_in_force(ps, pub, UNITS[u_][4])
            units = E.split_units(ps)
            mine = E.letters(''.join(x['text'] for x in units.values()))
            print(h['op'], label_of(u_, h), pub, f, basis[:60], len(units), 'letters:', check_letters(mine, source_letters(pdf)) or 'ok')
