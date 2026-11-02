"""Mexican municipalities for git-for-law (gitlaw-scraper-dell, municipal tier, 2026-10-31, via global-law-main-composer):
one public repo per city, lexifina/mexico-<city>-city-law, built by scripts/gitlaw_common/build.py from corpus.d parts
(the bando de policía / main reglamentos first, then the other reglamentos in parts of about 50).

Each city is read from its own municipal site (an adapter per city below). Fetching goes through br_city_get.Host: one
request at a time per host, at least 3 s apart, TLS verified, stops the host on a challenge, 403, 429 or timeout.

    python -X utf8 scripts/world-law/mx_cities.py catalogue <city>
    python -X utf8 scripts/world-law/mx_cities.py fetch <city> <part>        # fetch + parse one part into corpus.d
    python -X utf8 scripts/world-law/mx_cities.py publish <city> <part>...   # letters check + scratch build/check.py, then .PUBLISH
    python -X utf8 scripts/world-law/mx_cities.py scaffold <city>            # create the public repo (one API call) + scaffold

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as htmlmod
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ar_provinces as E  # noqa: E402  (text helpers: split_units, letters, pdf readers)
from ar_adapters._dell import pdf_paragraphs_layout  # noqa: E402
from br_city_get import Host, Stop  # noqa: E402

ROOT = HERE.parent
DOCS = ROOT.parent.parent
CACHE = HERE / '.mx-cities' / 'cache'
SESSION = 'gitlaw-scraper-dell'
CLAIMS = HERE / 'claims'
PART_SIZE = 50

MONTHS = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
          'SEPTIEMBRE': 9, 'SETIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}

LFDA = ('Ley Federal del Derecho de Autor, art. 14: "No son objeto de la protección como derecho de autor a que se '
        'refiere esta Ley: [...] VIII. Los textos legislativos, reglamentarios, administrativos o judiciales, así como '
        'sus traducciones oficiales. En caso de ser publicados, deberán apegarse al texto oficial y no conferirán '
        'derecho exclusivo de edición"')


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


HOSTS: dict[str, Host] = {}


def get(url: str, cached_only: bool = False) -> bytes | None:
    h = url.split('/')[2]
    if h not in HOSTS:
        HOSTS[h] = Host(CACHE / h.replace(':', '_'), h, delay=3.2, timeout=90)
    return HOSTS[h].get(url, cached_only=cached_only)


def es_date(s: str) -> str | None:
    m = re.search(r'(\d{1,2})\s*(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóú]+)\s*,?\s*(?:de\s+|del\s+)?(\d{4})', s or '', re.I)
    if not m:
        return None
    mo = MONTHS.get(E.fold(m.group(2)))
    if not mo:
        return None
    try:
        return dt.date(int(m.group(3)), mo, int(m.group(1))).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- adapters
# catalogue() -> list of {'title', 'url' (the text file), 'page' (where it is listed), 'updated' (ISO or None), 'first'}

class Guadalajara:
    slug = 'guadalajara'
    host = 'transparenciagdl.guadalajara.gob.mx'
    index = ('https://transparenciagdl.guadalajara.gob.mx/sites/default/files/html/'
             'reglamentos_federales_estatales_municipales.html?v=2')
    listing = ('https://transparencia.guadalajara.gob.mx/articulo-8/ii-la-informacion-sobre-el-marco-juridico-aplicable-'
               'al-y-por-el-sujeto-obligado-que-comprende/d-los-reglamentos-federales-estatales-y-municipales')
    source = {
        'name': 'Portal de Transparencia del Gobierno de Guadalajara (transparencia.guadalajara.gob.mx), "Los reglamentos '
                'federales, estatales y municipales" (art. 8, fr. II, inc. d), list of reglamentos municipales vigentes',
        'url': listing,
        'publisher': 'Gobierno Municipal de Guadalajara',
        'gazette': 'Gaceta Municipal de Guadalajara',
        'notes': 'For each reglamento municipal vigente the portal gives its name, the date of its last reform '
                 '("Última reforma") and its current consolidated text as a PDF with a text layer. Earlier versions are '
                 'not published there.',
    }
    FIRST = ['Reglamento de Justicia Cívica del Municipio de Guadalajara', 'Código de Gobierno del Municipio de Guadalajara',
             'Reglamento Orgánico del Municipio de Guadalajara',
             'Reglamento de la Administración Pública Municipal de Guadalajara']
    first_note = ('Guadalajara has no separate Bando de Policía y Buen Gobierno: the city\'s own portal says its '
                  'functions are fulfilled by the Reglamento de Justicia Cívica del Municipio de Guadalajara, which comes '
                  'first, with the Código de Gobierno, the Reglamento Orgánico and the Reglamento de la Administración '
                  'Pública Municipal.')

    def catalogue(self) -> list[dict]:
        s = E.decode(get(self.index))
        out = []
        for blk in re.split(r'(?=<div class="rg-row")', s)[1:]:
            m = re.match(r'<div class="rg-row" data-tipo="(\w+)"', blk)
            if not m or m.group(1) != 'vigente':
                continue
            t = re.search(r'<h3 class="rg-name">(.*?)</h3>', blk, re.S)
            d = re.search(r'class="rg-date">(.*?)</div>', blk, re.S)
            u = re.search(r'data-u="([^"]+)"', blk)
            if not (t and u):
                continue
            title = E.clean(htmlmod.unescape(re.sub(r'<[^>]+>', '', t.group(1))))
            ds = E.clean(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', d.group(1)))) if d else ''
            out.append({'title': title, 'url': htmlmod.unescape(u.group(1)), 'page': self.listing,
                        'updated': es_date(ds), 'date_text': ds})
        return out


class Leon:
    slug = 'leon'
    host = 'normatividadmunicipal.leon.gob.mx'
    base = 'https://normatividadmunicipal.leon.gob.mx/'
    ajax = base + 'modulos/regulaciones/ajax_busquedaregulaciones.php'
    source = {
        'name': 'Normatividad Municipal, Presidencia Municipal de León (normatividadmunicipal.leon.gob.mx)',
        'url': 'https://normatividadmunicipal.leon.gob.mx/',
        'publisher': 'Presidencia Municipal de León',
        'gazette': 'Periódico Oficial del Gobierno del Estado de Guanajuato',
        'notes': 'For each municipal regulation the site gives its record (publication in the Periódico Oficial del '
                 'Gobierno del Estado de Guanajuato, type, and the list of its reforms with their Periódico Oficial '
                 'dates) and its current text as a PDF (and a Word file). Earlier versions are not published there.',
    }
    FIRST = ['Reglamento de Justicia Cívica para el Municipio de León, Guanajuato',
             'Reglamento de Policía y Vialidad para el Municipio de León, Guanajuato',
             'Reglamento Interior del H. Ayuntamiento de León, Guanajuato',
             'Reglamento Interior de la Administración Pública Municipal de León, Guanajuato']
    first_note = ('León has no separate Bando de Policía y Buen Gobierno in the source\'s list: the first part holds '
                  'its Reglamento de Justicia Cívica and Reglamento de Policía y Vialidad, then the Reglamento Interior del '
                  'H. Ayuntamiento and the Reglamento Interior de la Administración Pública Municipal; the rest follow in '
                  'the order the source lists them. Regulations the source marks as abrogated are left out.')

    def catalogue(self) -> list[dict]:
        from urllib.parse import quote
        out, seen = [], set()
        for pg in range(1, 40):
            data = 'filtro=&idtiporegulacion=0&idtipopublicacion=0' + (f'&pagina={pg}' if pg > 1 else '')
            b = HOSTS_get(self.ajax, data)
            s = E.decode(b or b'')
            new = 0
            for row in re.findall(r"(?s)<tr>\s*<td class='detalle'><img class='ico-leyes'.*?</tr>\s*<tr>.*?</tr>", s):
                tds = re.findall(r'(?s)<td>(.*?)</td>', row)
                pdf = re.search(r"href='(archivos/[^']+?\.pdf)'", row, re.I)
                det = re.search(r"href='(detalle-norma\.php\?id=\d+)'", row)
                if len(tds) < 3 or not det:
                    continue
                if det.group(1) in seen:
                    continue
                seen.add(det.group(1))
                new += 1
                out.append({'title': E.clean(htmlmod.unescape(tds[0])), 'kind': E.clean(tds[1]), 'pubtype': E.clean(tds[2]),
                            'url': self.base + quote(htmlmod.unescape(pdf.group(1))) if pdf else None,
                            'page': self.base + det.group(1), 'updated': None})
            m = re.search(r'TOTAL DE REGISTROS:\s*(\d+)', s)
            if not new or (m and len(out) >= int(m.group(1))):
                break
        return [x for x in out if x['pubtype'] != 'Abrogada']

    def detail(self, it: dict):
        s = E.decode(get(it['page']) or b'')
        t = E.clean(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<(script|style).*?</>', '', s))))
        pub = re.search(r'PUBLICACI[ÓO]N PERI[ÓO]DICO OFICIAL:\s*(\d{2})/(\d{2})/(\d{4})', t)
        pub = f'{pub.group(3)}-{pub.group(2)}-{pub.group(1)}' if pub else None
        if pub == '1970-01-01':      # the site's placeholder for an unknown date
            pub = None
        mods = re.findall(r'Reforma\s+\d+\s*:\s*(.*?)(?=Reforma\s+\d+\s*:|REFORMAS:|$)', t)
        days = [d for d in (es_date(m) for m in mods) if d]
        it['published'] = pub
        it['updated'] = max(days + ([pub] if pub else [])) if (days or pub) else None
        it['date_text'] = (f'reform of {max(days)} (Periódico Oficial)' if days else f'publication {pub} (Periódico Oficial)')


class Puebla:
    slug = 'puebla'
    host = 'gobiernoabierto.pueblacapital.gob.mx'
    listing = 'https://gobiernoabierto.pueblacapital.gob.mx/marco-normativo-del-h-ayuntamiento-de-puebla'
    source = {
        'name': 'Gobierno Abierto, H. Ayuntamiento de Puebla (gobiernoabierto.pueblacapital.gob.mx), "Normatividad más '
                'consultada del H. Ayuntamiento de Puebla"',
        'url': listing,
        'publisher': 'H. Ayuntamiento del Municipio de Puebla',
        'gazette': 'Periódico Oficial del Estado de Puebla',
        'notes': 'The page links the current text of the Código Reglamentario para el Municipio de Puebla (COREMUN) and '
                 'other municipal instruments as PDFs with a text layer; each PDF states on its first page the date of its '
                 'last reform (or publication) in the Periódico Oficial del Estado de Puebla. Each PDF says its content '
                 'is informative and that the original is the one published in the Periódico Oficial.',
    }
    MUNICIPAL = ('Código Reglamentario para el Municipio de Puebla (COREMUN)',
                 'Código de Ética del H. Ayuntamiento del Municipio de Puebla',
                 'Lineamientos que establecen el procedimiento de entrega-recepción')
    FIRST = ['Código Reglamentario para el Municipio de Puebla (COREMUN)']
    first_note = ('Puebla has no separate Bando de Policía y Buen Gobierno: its municipal regulations, including the '
                  'rules on public order and civic justice, are codified in the Código Reglamentario para el Municipio de '
                  'Puebla (COREMUN), which comes first. The municipality\'s page links only a few municipal instruments '
                  '(state laws it also links, such as the Ley Orgánica Municipal, are left out).')

    def catalogue(self) -> list[dict]:
        s = E.decode(get(self.listing) or b'')
        out = []
        for u, t in re.findall(r'(?s)<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', s):
            title = E.clean(htmlmod.unescape(re.sub(r'<[^>]+>', '', t)))
            if not title.startswith(self.MUNICIPAL):
                continue
            url = u if u.startswith('http') else 'https://' + self.host + u
            out.append({'title': title, 'url': url, 'page': self.listing, 'updated': None})
        return out

    @staticmethod
    def paragraphs(b: bytes) -> list[str]:
        """COREMUN: PyMuPDF drops a few table labels (roman numerals drawn in table cells), so the text is read with
        pypdf; lines are joined into paragraphs (a line that does not end a sentence continues, unless the next line
        starts an article). Nothing is dropped."""
        import io
        import pypdf
        out: list[str] = []
        for page in pypdf.PdfReader(io.BytesIO(b)).pages:
            for ln in (page.extract_text() or '').split('\n'):
                c = E.clean(ln)
                if not c:
                    continue
                if out and not re.search(r'[.:;!?)]$', out[-1]) and not E.article_id(c) and not out[-1].isupper():
                    out[-1] += ' ' + c
                else:
                    out.append(c)
        return out

    @staticmethod
    def source_letters(b: bytes) -> str:
        """Independent reader: poppler's pdftotext in raw mode (its default mode composes a spacing accent printed
        after "50" into one letter)."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / 'x.pdf'
            f.write_bytes(b)
            out = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-raw', str(f), '-'], capture_output=True)
            return E.letters(out.stdout.decode('utf-8', 'replace'))

    def detail(self, it: dict):
        b = get(it['url'])
        if not b:
            return
        head = E.clean(' '.join(E.pdf_paragraphs(b)[:12])) if False else ''
        import pymupdf
        with pymupdf.open(stream=b, filetype='pdf') as doc:
            head = E.clean(' '.join(doc[i].get_text() for i in range(min(2, len(doc)))))
        g = re.match(r'PERI[ÓO]DICO OFICIAL\b.{0,600}?\b(?:LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+'
                     r'(\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚ]+\s+DE\s+\d{4})', head)
        if g:   # the PDF is the Periódico Oficial issue itself: dated by that issue
            it['updated'] = es_date(g.group(1))
            it['date_text'] = 'Periódico Oficial del Estado de Puebla of ' + g.group(1).lower()
            return
        m = re.search(r'(?:[ÚU]LTIMA REFORMA|PUBLICAD[OA])[^.]{0,120}?(\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚa-záéíóú]+\s+(?:DE|DEL)\s+\d{4})',
                      head, re.I)
        it['updated'] = es_date(m.group(1)) if m else None
        it['date_text'] = E.clean(m.group(0))[:160] if m else ''


ADAPTERS = {'guadalajara': Guadalajara, 'leon': Leon, 'puebla': Puebla}


def HOSTS_get(url: str, data: str) -> bytes | None:
    h = url.split('/')[2]
    if h not in HOSTS:
        HOSTS[h] = Host(CACHE / h.replace(':', '_'), h, delay=3.2, timeout=90)
    return HOSTS[h].get(url, data=data, headers=['Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
                                                 'X-Requested-With: XMLHttpRequest'])

# slug: (English name, official name, code, parent path, state name, tz)
CITIES = {
    'guadalajara': ('Guadalajara', 'Municipio de Guadalajara', 'MX-JAL-GUADALAJARA', 'mx-jal', 'Jalisco',
                    'America/Mexico_City'),
    'puebla': ('Puebla', 'Municipio de Puebla', 'MX-PUE-PUEBLA', 'mx-pue', 'Puebla', 'America/Mexico_City'),
    'leon': ('León', 'Municipio de León', 'MX-GUA-LEON', 'mx-gua', 'Guanajuato', 'America/Mexico_City'),
}


def repo_name(c: str) -> str:
    return f'mexico-{c}-city-law'


def folder(c: str) -> Path:
    return ROOT / repo_name(c)


# ---------------------------------------------------------------- plan + parts

def plan(c: str) -> list[tuple[str, list[dict]]]:
    ad = ADAPTERS[c]()
    cat = ad.catalogue()
    first = [x for t in ad.FIRST for x in cat if x['title'] == t]
    rest = [x for x in cat if x not in first]
    out = [('10-reglamentos-principales', first)]
    for i in range(0, len(rest), PART_SIZE):
        out.append((f'{30 + i // PART_SIZE}-reglamentos-{i // PART_SIZE + 1:02d}', rest[i:i + PART_SIZE]))
    return out


def act_slug(title: str, used: set) -> str:
    s = E.ascii_slug(title)
    s = re.sub(r'-(del?|para)-(el-)?municipio-de-' + r'[a-z-]+$', '', s)
    s = re.sub(r'-(de|en)-guadalajara$', '', s)
    s = re.sub(r'-(de|en)-puebla$', '', s)
    s = re.sub(r'-(de|en)-leon(-estado)?(-guanajuato|-gto)?$', '', s)
    s = s[:70].rstrip('-')
    base, k = s, 2
    while s in used:
        s, k = f'{base}-{k}', k + 1
    used.add(s)
    return s


def build_act(c: str, it: dict, paras: list[str], src: bytes, used: set) -> tuple[dict, dict]:
    ad = ADAPTERS[c]
    units = E.split_units(paras)
    s = act_slug(it['title'], used)
    key = f'texto-vigente-{s}'
    day = it['updated']
    law = {'label': f'{it["title"]} (texto vigente)', 'title': it['title'], 'kind': 'law', 'enacted': None,
           'published': day, 'url': it['page'], 'temporary_until': None, 'restores': None,
           'note': f'Current consolidated text as {ad.source["publisher"]} publishes it; last reform {day} '
                   f'("{it.get("date_text", "")}").'}
    v = {'from': day, 'source_url': it['url'], 'sha256': hashlib.sha256(src).hexdigest(), 'units': units, 'credits': {},
         'note': ('Oldest version available: the current consolidated text as the municipality publishes it, dated by '
                  f'its last reform as the source records it ({day}). Earlier versions are not published by the source.')}
    act = {'slug': s, 'short': it['title'][:80], 'title': it['title'][:300], 'url': it['page'], 'first_law': None,
           'earlier_laws': [key], 'versions': [v]}
    return act, {key: law}


def country_block(c: str) -> dict:
    en, native, code, parent, state, tz = CITIES[c]
    src = ADAPTERS[c].source
    return {'code': code, 'name': f'{en} (city)', 'slug': f'mexico-{c}-city', 'lang': 'es', 'tz': tz,
            'future_branch': 'futuro',
            'publisher': {'name': src['publisher'], 'email': f'normatividad@{ADAPTERS[c].host}.invalid'},
            'licence_note': f'Fuente: {src["name"]}, {src["url"]}.'}


AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which reglamentos to include; it wrote no law '
          'text. Every word of law comes from the municipality\'s own published texts.']


def decisions(c: str) -> list[str]:
    ad = ADAPTERS[c]
    return [
        f'The source ({ad.source["url"]}) publishes, for each reglamento municipal vigente, only its current consolidated '
        'text and the date of its last reform. Each reglamento is therefore its current text only ("oldest version '
        'available"), dated by that last-reform date; the original text and earlier versions are not shown. That date is '
        f'the one the source gives for the last reform (its publication in the {ad.source["gazette"]}), not a separately '
        'established day of entry into force.',
        ad.first_note,
        'Units: the heading (encabezado: the title and anything before Artículo 1) and one file per article, holding the '
        'article and everything printed after it up to the next article (chapter headings, transitorios and the reform '
        'history the PDF prints). Nothing is dropped. One paragraph per line, spacing normalised. Text-layer PDFs only, '
        'no OCR; a reglamento whose PDF has no text layer is left out.',
        'Reglamentos are added in parts of about 50, in the order the source lists them, after the first part.',
    ]


def source_block(c: str, retrieved: str) -> dict:
    src = ADAPTERS[c].source
    return {'name': src['name'], 'url': src['url'], 'retrieved': retrieved,
            'licence': 'Official municipal regulations, not protected by copyright in Mexico: ' + LFDA + '. Reproduced '
                       'following the official text, with attribution.',
            'notes': src['notes']}


def fetch_part(c: str, part: str, docs_date: str) -> dict:
    members = dict(plan(c))[part]
    out = folder(c) / 'corpus.d' / f'{part}.json'
    if out.with_suffix('.PUBLISH').exists():
        return {'skipped': 'published'}
    used, others = set(), []
    for p in sorted((folder(c) / 'corpus.d').glob('*.json')):
        if p.stem != part:
            pj = json.loads(p.read_text(encoding='utf-8'))
            used.update(a['slug'] for a in pj.get('acts', []))
            others.append(p.stem)
    acts, laws, rep = [], {}, {}
    ad = ADAPTERS[c]()
    for it in members:
        if hasattr(ad, 'detail') and it.get('url'):
            ad.detail(it)
        if not it.get('url'):
            rep[it['title']] = 'left out: no PDF listed'
            continue
        if not it.get('updated'):
            rep[it['title']] = 'left out: the source gives no date for it'
            continue
        if it['updated'] >= docs_date:
            rep[it['title']] = 'left out: dated on/after the retrieval day'
            continue
        b = get(it['url'])
        if not b or not b.startswith(b'%PDF'):
            rep[it['title']] = 'left out: no PDF'
            continue
        paras = ad.paragraphs(b) if hasattr(ad, 'paragraphs') else pdf_paragraphs_layout(b)
        if sum(len(p) for p in paras) < 200:
            rep[it['title']] = 'left out: no text layer'
            continue
        a, l = build_act(c, it, paras, b, used)
        acts.append(a)
        laws.update(l)
        rep[it['title']] = f'{a["slug"]}: {len(a["versions"][0]["units"])} units, {it["updated"]}'
    part_d = {'country': country_block(c), 'laws': dict(sorted(laws.items())), 'acts': acts}
    if not any(o < part for o in others):
        part_d.update(sources=[source_block(c, docs_date)], decisions=decisions(c), ai_use=AI_USE)
    out.parent.mkdir(parents=True, exist_ok=True)
    E.write_part(out, part_d)
    (folder(c) / '.tmp').mkdir(exist_ok=True)
    (folder(c) / '.tmp' / f'parse-{part}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    return rep


# ---------------------------------------------------------------- checks

def letters_check(c: str, part: str) -> list[str]:
    pj = json.loads((folder(c) / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    probs = []
    for act in pj['acts']:
        for v in act['versions']:
            b = get(v['source_url'], cached_only=True)
            if b is None or hashlib.sha256(b).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]}: source missing or sha256 differs')
                continue
            ad = ADAPTERS[c]
            src = ad.source_letters(b) if hasattr(ad, 'source_letters') else E.source_letters_pdf(b)  # not the parser's reader
            mine = E.letters(''.join(u['text'] for u in v['units'].values()))
            if src != mine and sorted(src) != sorted(mine):
                ca, cb = Counter(src), Counter(mine)
                probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} '
                             f'corpus-only {dict((cb - ca).most_common(6))}')
    return probs


def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][x.month - 1]} {x.year}'


def write_docs(c: str, docs_date: str, extra=(), out: Path | None = None):
    en, native, code, parent, state, tz = CITIES[c]
    src = ADAPTERS[c].source
    parts = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((folder(c) / 'corpus.d').glob('*.json'))
             if p.with_suffix('.PUBLISH').exists() or p.stem in extra]
    rows, nacts = [], 0
    for part in parts:
        for a in part['acts']:
            nacts += 1
            t = a['title'].replace('|', '/')
            rows.append(f'| `{a["slug"]}/` | {t[:160]}{"…" if len(t) > 160 else ""} | current text only, last reform '
                        f'{_long(a["versions"][0]["from"])} |')
    repo = out or (folder(c) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en} (city): municipal law in git

The municipal law of {native} ({state}, Mexico) as a git history: its reglamentos, one file per article, one paragraph per line, so `git log`, `git blame` and `git diff` work article by article.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{code.lower()}/`. The law of the State of {state} is in [lexifina/mexico-{repo_state(c)}-law](https://github.com/lexifina/mexico-{repo_state(c)}-law), and Mexico's federal law in [lexifina/mexico-law](https://github.com/lexifina/mexico-law).

The text is in Spanish, exactly as the source prints it.

## What this repository holds

{nacts} reglamento{"s" if nacts != 1 else ""} so far, each as its **current consolidated text only** (the oldest version available from the source), added in parts. {ADAPTERS[c].first_note}

| Folder | Reglamento | History |
| --- | --- | --- |
{chr(10).join(rows)}

## Source

{src['name']}, <{src['url']}>. {src['notes']}

## Dates

- Each reglamento is one commit, dated at **noon, {tz}, on the date of its last reform** as the source records it. Its original text and earlier versions are not shown, because the source does not publish them.
- Versions dated after the retrieval day would go on the `futuro` branch, never merged into `main`.

## Files

`<reglamento>/art-005.md` is Artículo 5, `art-005-bis.md` Artículo 5 bis; `encabezado.md` holds the title and anything printed before Artículo 1. Chapter headings, transitorios and the reform notes the source prints stay in the file of the article they follow. One paragraph per line.

## How it is checked

- Every version is read back from git on its day (`tools/check_repo.py`) and must match `corpus.json`.
- The letters and digits of every version equal those of the source PDF read again with an independent reader (poppler's pdftotext), so no word is lost or added.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## Limits

This is not an official publication. The binding text is the one published in the {src['gazette']}. Only the reglamentos listed above are included, each as its current text only.
"""
    lic = f"""The texts of law in this repository are reglamentos and other general provisions of the {native}
({state}, Mexico), taken from {src['name']}, {src['url']} (consulted {docs_date}).

Copyright: they are not protected by copyright in Mexico. {LFDA}.
They are reproduced here following the official text.

Attribution: Fuente: {src['publisher']}, {src['url']}.

Changes made by Lexifina: each text was split into one Markdown file per article, one paragraph per line, with spacing
normalised; the wording was not changed. The municipality does not endorse this repository. This repository is not an
official publication; the binding text is the one published in the {src['gazette']}.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': code.lower(), 'code': code, 'name': f'{en} (city)', 'level': 'municipality', 'parent': parent,
             'repo': f'https://github.com/lexifina/{repo_name(c)}',
             'build': f'built: reglamentos municipales vigentes of {en}, current text only ({nacts}), from {src["url"]}',
             'language': 'es', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


STATE_REPO = {'mx-jal': 'jalisco', 'mx-nle': 'nuevo-leon', 'mx-pue': 'puebla', 'mx-gua': 'guanajuato',
              'mx-yuc': 'yucatan', 'mx-bcn': 'baja-california', 'mx-chh': 'chihuahua', 'mx-que': 'queretaro'}


def repo_state(c: str) -> str:
    return STATE_REPO[CITIES[c][3]]


def verify_part(c: str, part: str, docs_date: str) -> tuple[bool, str]:
    probs = letters_check(c, part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[:3]}'
    tmp = DOCS / f'{repo_name(c)}-verify'
    build = DOCS / f'{repo_name(c)}-verifybuild'
    for d in (tmp, build):
        E._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((folder(c) / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    names += [part] if part not in names else []
    for n in names:
        shutil.copy2(folder(c) / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(c, docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = E._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
                '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-600:]
    r = E._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(r.stdout[r.stdout.index('{'):])
    except Exception:
        return False, 'check.py output unreadable: ' + (r.stderr or r.stdout)[-400:]
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force'):
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
    pj = json.loads((folder(c) / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    days = sorted(v['from'] for a in pj['acts'] for v in a['versions'])
    line = (f'{len(pj["acts"])} reglamento(s), versions {days[0]}..{days[-1]} from {ADAPTERS[c].host}: letters and digits '
            f'of every version equal the source PDF (independent pdftotext reader); scratch build of verified parts + '
            f'this part: check.py {res.get("versions")} versions, 0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    E._rm(tmp)
    E._rm(build)
    return True, line


def publish(c: str, part: str, docs_date: str) -> str:
    ok, line = verify_part(c, part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    pub = folder(c) / 'corpus.d' / f'{part}.PUBLISH'
    write_docs(c, docs_date, extra=[part])
    pub.write_text(line + '\n', encoding='utf-8', newline='\n')
    top = folder(c) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    progress(c, f'{part}: PUBLISH {line}')
    return 'PUBLISH ' + line


def progress(c: str, line: str):
    p = folder(c) / 'PROGRESS.md'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'# {repo_name(c)} (private progress, gitlaw-scraper-dell)\n\nBuilder: scripts/world-law/mx_cities.py; '
                     f'source {ADAPTERS[c].source["url"]}.\n\n', encoding='utf-8', newline='\n')
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {now()} {line}\n')


def scaffold(c: str) -> str:
    import tempfile
    en, native, code, parent, state, tz = CITIES[c]
    repo = repo_name(c)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = E.run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    E.run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
          '-f', f'description={en} (city, {state}, Mexico) municipal law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    E.run('git', 'init', '-q', '-b', 'main', cwd=d)
    E.run('git', 'config', 'core.autocrlf', 'false', cwd=d)
    src = ADAPTERS[c].source
    (d / 'README.md').write_text(f"""# {en} (city): municipal law as git history

Work in progress. This repository will hold the municipal law of {native} ({state}, Mexico) as a git history: one
file per article.

Source: <{src['url']}>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text(f"# Sources\n\n- {src['name']}: <{src['url']}>\n\nThe terms and attribution will be "
                                  "recorded in LICENSE with the first build.\n", encoding='utf-8', newline='\n')
    E.run('git', 'add', '-A', cwd=d)
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-10-31T12:00:00-0600', GIT_COMMITTER_DATE='2026-10-31T12:00:00-0600')
    subprocess.run(['git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
                    f'Mexico ({en} city): sources, before any law'], cwd=d, env=env, check=True)
    E.run('git', 'remote', 'add', 'origin', remote, cwd=d)
    for attempt in range(4):
        p = E.run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
        if p.returncode == 0:
            break
        time.sleep(10 * (attempt + 1))
    return 'CREATED ' + E.run('git', 'ls-remote', remote, check=False).stdout.strip()[:60]


def wait_cpu():
    while not E.cpu_ok() or _cpu90():
        time.sleep(60)


def _cpu90() -> bool:
    try:
        last = Path(os.environ['LOCALAPPDATA'], 'gitlaw-cpu.log').read_text(encoding='utf-8').strip().splitlines()[-1]
        return int(re.search(r'cpu5=(\d+)', last).group(1)) > 90
    except Exception:
        return False


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    cmd, c = sys.argv[1], sys.argv[2]
    dd = dt.date.today().isoformat()
    try:
        if cmd == 'catalogue':
            for name, mem in plan(c):
                print(name, len(mem), sum(1 for m in mem if m.get('updated')))
        elif cmd == 'fetch':
            for part in sys.argv[3:]:
                wait_cpu()
                rep = fetch_part(c, part, dd)
                say(part, sum(1 for v in rep.values() if not str(v).startswith('left out')), 'built;',
                    [k for k, v in rep.items() if str(v).startswith('left out')])
        elif cmd == 'publish':
            for part in sys.argv[3:]:
                wait_cpu()
                say(part, publish(c, part, dd)[:400])
        elif cmd == 'prune':
            # leave out of an unpublished part every reglamento whose letters differ between the two PDF readers
            for part in sys.argv[3:]:
                f = folder(c) / 'corpus.d' / f'{part}.json'
                if f.with_suffix('.PUBLISH').exists():
                    continue
                bad = {x.split(':')[0] for x in letters_check(c, part)}
                pj = json.loads(f.read_text(encoding='utf-8'))
                keep = [a for a in pj['acts'] if a['slug'] not in bad]
                keys = {k for a in keep for k in a['earlier_laws'] + ([a['first_law']] if a['first_law'] else [])}
                pj['acts'] = keep
                pj['laws'] = {k: v for k, v in pj['laws'].items() if k in keys}
                E.write_part(f, pj)
                lo = folder(c) / '.tmp' / 'left-out.json'
                old = json.loads(lo.read_text(encoding='utf-8')) if lo.exists() else {}
                old.update({b: f'{part}: letters differ between PyMuPDF and pdftotext (font encoding)' for b in bad})
                lo.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf-8')
                say(part, 'pruned', sorted(bad), 'kept', len(keep))
        elif cmd == 'letters':
            print(letters_check(c, sys.argv[3]) or 'clean')
        elif cmd == 'scaffold':
            print(scaffold(c))
        elif cmd == 'docs':
            write_docs(c, dd)
    except Stop as e:
        say('STOPPED', e)
        progress(c, f'STOPPED: {e}')
