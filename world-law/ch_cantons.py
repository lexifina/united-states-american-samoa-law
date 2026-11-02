"""Swiss cantons for git-for-law (gitlaw-scraper-dell, coverage wave 2026-10-30): one public repo per canton,
lexifina/switzerland-<canton>-law, built by scripts/gitlaw_common/build.py from corpus.d parts.

Most cantons publish their systematic collection on LexWork (Sitrox), whose JSON API gives every consolidated
version of an act ("Version in Kraft von ... bis ...") with its XHTML text and the act's change table (decision
date, in-force date, element, change, entry in the chronological collection). This module fetches (cache, one
thread per host, one request at a time per host, a pause between requests) and parses those into corpus parts.

    python -X utf8 scripts/world-law/ch_cantons.py fetch bern lucerne ...   # one process; one thread per host
    python -X utf8 scripts/world-law/ch_cantons.py parse bern               # corpus.d parts from the cache
    python -X utf8 scripts/world-law/ch_cantons.py docs bern                # repo/README.md etc. from verified parts

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # scripts/
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
PAUSE = 1.0                                          # seconds between requests to one host
PART_SIZE = 50

# slug, code, English name, official name, host, language, constitution number (None = find in the index)
CANTONS = {
    'bern': ('BE', 'Bern', 'Kanton Bern', 'www.belex.sites.be.ch', 'de', '101.1'),
    'lucerne': ('LU', 'Lucerne', 'Kanton Luzern', 'srl.lu.ch', 'de', '1'),
    'uri': ('UR', 'Uri', 'Kanton Uri', 'rechtsbuch.ur.ch', 'de', '1.1101'),
    'obwalden': ('OW', 'Obwalden', 'Kanton Obwalden', 'gdb.ow.ch', 'de', None),
    'nidwalden': ('NW', 'Nidwalden', 'Kanton Nidwalden', 'gesetze.nw.ch', 'de', '111'),
    'glarus': ('GL', 'Glarus', 'Kanton Glarus', 'gesetze.gl.ch', 'de', 'I A/1/1'),
    'zug': ('ZG', 'Zug', 'Kanton Zug', 'bgs.zg.ch', 'de', '111.1'),
    'fribourg': ('FR', 'Fribourg', 'Etat de Fribourg', 'bdlf.fr.ch', 'fr', '10.1'),
    'solothurn': ('SO', 'Solothurn', 'Kanton Solothurn', 'bgs.so.ch', 'de', '111.1'),
    'basel-stadt': ('BS', 'Basel-Stadt', 'Kanton Basel-Stadt', 'www.gesetzessammlung.bs.ch', 'de', '111.100'),
    'basel-landschaft': ('BL', 'Basel-Landschaft', 'Kanton Basel-Landschaft', 'bl.clex.ch', 'de', '100'),
    'schaffhausen': ('SH', 'Schaffhausen', 'Kanton Schaffhausen', 'rechtsbuch.sh.ch', 'de', '101.000'),
    'appenzell-ausserrhoden': ('AR', 'Appenzell Ausserrhoden', 'Kanton Appenzell Ausserrhoden', 'ar.clex.ch', 'de', '111.1'),
    'appenzell-innerrhoden': ('AI', 'Appenzell Innerrhoden', 'Kanton Appenzell Innerrhoden', 'ai.clex.ch', 'de', '101.000'),
    'st-gallen': ('SG', 'St. Gallen', 'Kanton St.Gallen', 'www.gesetzessammlung.sg.ch', 'de', '111.1'),
    'graubunden': ('GR', 'Graubünden', 'Kanton Graubünden', 'www.gr-lex.gr.ch', 'de', '110.100'),
    'aargau': ('AG', 'Aargau', 'Kanton Aargau', 'gesetzessammlungen.ag.ch', 'de', '110.000'),
    'thurgau': ('TG', 'Thurgau', 'Kanton Thurgau', 'www.rechtsbuch.tg.ch', 'de', '101'),
    'valais': ('VS', 'Valais', 'Canton du Valais', 'lex.vs.ch', 'fr', '101.1'),
    'schwyz': ('SZ', 'Schwyz', 'Kanton Schwyz', 'gesetzsammlung.sz.ch', 'de', None),
}
CHG = {'de': 'Änderung vom', 'fr': 'Modification du', 'it': 'Modifica del'}


def _dmy(d: str | None) -> str:
    return f'{d[8:10]}.{d[5:7]}.{d[0:4]}' if d else '?'


LANGNAME = {'de': 'German', 'fr': 'French', 'it': 'Italian'}
FUTURE = {'de': 'zukunft', 'fr': 'futur', 'it': 'futuro'}


def folder(slug: str) -> Path:
    return ROOT / f'switzerland-{slug}-law'


# ---------------------------------------------------------------- fetching

class Host:
    def __init__(self, slug: str):
        self.slug = slug
        code, en, native, self.host, self.lang, self.const = CANTONS[slug]
        self.dir = folder(slug)
        self.cache = self.dir / '.cache'
        self.cache.mkdir(parents=True, exist_ok=True)
        gi = self.dir / '.gitignore'
        if not gi.exists():
            gi.write_text('.cache/\n', encoding='utf-8', newline='\n')
        self.last = 0.0
        self.pause = PAUSE
        self.lock = threading.Lock()
        self.count = 0

    def url(self, path: str) -> str:
        return f'https://{self.host}/api/{self.lang}/{path}'

    def path(self, url: str) -> Path:
        return self.cache / (hashlib.sha256(url.encode()).hexdigest() + '.json')

    def cached(self, url: str):
        p = self.path(url)
        if p.exists():
            b = p.read_bytes()
            return json.loads(b) if b.strip() not in (b'', b'null') else None
        return False

    def get(self, url: str):
        """JSON for url, from the cache or one polite request. None for a 404 (cached as null)."""
        c = self.cached(url)
        if c is not False:
            return c
        for attempt in range(4):
            wait = self.last + self.pause - time.time()
            if wait > 0:
                time.sleep(wait)
            t0 = time.time()
            r = subprocess.run(['curl', '-s', '-m', '120', '--compressed', '-A', UA, '-w', '\n%{http_code}', url],
                               capture_output=True)
            self.last = time.time()
            self.count += 1
            body, _, code = r.stdout.rpartition(b'\n')
            code = code.decode().strip()
            with open(self.cache / 'requests.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'url': url,
                                    'status': code, 'bytes': len(body), 'secs': round(self.last - t0, 2)}) + '\n')
            if code == '200':
                json.loads(body)  # must parse
                tmp = self.path(url).with_suffix('.tmp')
                tmp.write_bytes(body)
                os.replace(tmp, self.path(url))
                return json.loads(body)
            if code == '404':
                self.path(url).write_bytes(b'null')
                return None
            if code in ('403', '429') or code.startswith('5'):
                time.sleep(30 * (attempt + 1))
                if code == '403' and attempt >= 1:
                    raise RuntimeError(f'{self.host}: 403 twice, stopping')
                continue
            time.sleep(5)
        raise RuntimeError(f'{self.host}: {url} failed ({code})')

    # API helpers
    def index(self):
        return self.get(self.url('texts_of_law/lightweight_index'))

    def types(self):
        return self.get(self.url('text_of_law_types'))

    def settings(self):
        return self.get(self.url('settings'))

    def act(self, sn: str):
        return self.get(self.url('texts_of_law/' + urllib.parse.quote(sn, safe='')))

    def version(self, sn: str, vid: int):
        return self.get(self.url(f'texts_of_law/{urllib.parse.quote(sn, safe="")}/versions/{vid}'))


def index_entries(h: Host) -> list[dict]:
    d = h.index()
    out = [x for v in d.values() if isinstance(v, list) for x in v]
    return sorted(out, key=lambda x: natkey(x['systematic_number']))


def natkey(s: str):
    return [(0, int(t), '') if t.isdigit() else (1, 0, t.lower()) for t in re.findall(r'\d+|[^\d\s./-]+', s)]


LAW_TITLE = {
    'de': (re.compile(r'gesetz', re.I), re.compile(r'verordnung|reglement|beschluss|vereinbarung|konkordat|vertrag|'
                                                    r'weisung|richtlinie|tarif|statut|ordnung\b|abkommen', re.I)),
    'fr': (re.compile(r'^\s*loi\b', re.I), re.compile(r'r[èe]glement|arr[êe]t[ée]|ordonnance|concordat|convention', re.I)),
    'it': (re.compile(r'^\s*legge\b', re.I), re.compile(r'regolamento|decreto|concordato|convenzione', re.I)),
}


def constitution_sn(h: Host) -> str:
    if h.const:
        return h.const
    pat = {'de': r'^(Kantons)?verfassung|^Verfassung', 'fr': r'^Constitution', 'it': r'^Costituzione'}[h.lang]
    for x in index_entries(h):
        if re.search(pat, x['title']):
            return x['systematic_number']
    raise RuntimeError(f'{h.slug}: no constitution in the index')


def law_candidates(h: Host) -> list[str]:
    inc, exc = LAW_TITLE[h.lang]
    const = constitution_sn(h)
    return [x['systematic_number'] for x in index_entries(h)
            if x['systematic_number'] != const and not x.get('abrogated') and inc.search(x['title'])
            and not exc.search(x['title'])]


def law_type_ids(h: Host) -> set[int]:
    pat = {'de': r'^Gesetz', 'fr': r'^Loi', 'it': r'^Legg'}[h.lang]
    out = set()
    for t in h.types() or []:
        t = t.get('text_of_law_type', t)
        if re.search(pat, t.get('name', '')) or re.search(pat, t.get('name_singularized', '') or ''):
            out.add(t['id'])
    if not out:
        # Types named by authority (UR, AI, SH, FR): the acts of the people or the parliament; the title filter then
        # keeps the laws (Gesetz / Loi) among them.
        for t in h.types() or []:
            t = t.get('text_of_law_type', t)
            if not re.search(r'Vereinbarung|Vertr|Convention|Verfassung|Constitution|Regierungsrat|Standeskommission|'
                             r'Conseil d.Etat|Direction|anderer|autres|Anderes|judiciaires', t.get('name', '')):
                out.add(t['id'])
    return out


# Ordinances (coverage wave 2, 2026-10-30): an in-force act whose title's first or second word is an ordinance word
# (Verordnung, Vollziehungsverordnung, Reglement, Ordonnance, Règlement, Regolamento; "Kantonale Verordnung ..."),
# that is not the constitution or a law, and whose LexWork type is not an agreement, treaty or directive.
ORD_WORD = re.compile(r'^(\w*(verordnung|reglement)(e|en)?|ordonnances?|r[èe]glements?|regolament[oi])$', re.I)
ORD_TYPE_EXC = re.compile(r'Vereinbarung|Vertr|Convention|Accord|Trait|Verfassung|Constitution|Konvention|Konzession|'
                          r'Bebauungspl|Richtlin|Weisung|Directive|Allgemeinverf', re.I)
ORD_NAME = {'de': ('Verordnungen', 'Verordnungen and Reglemente'), 'fr': ('ordonnances', 'ordonnances and règlements'),
            'it': ('regolamenti', 'regolamenti')}


def ordinance_candidates(h: Host) -> list[str]:
    laws = set(law_candidates(h))
    const = constitution_sn(h)
    out = []
    for x in index_entries(h):
        sn = x['systematic_number']
        if sn == const or sn in laws or x.get('abrogated'):
            continue
        if any(ORD_WORD.match(w) for w in re.findall(r'\w+', x['title'])[:2]):
            out.append(sn)
    return out


def ord_type_ok(h: Host, d: dict) -> bool:
    tid = d['text_of_law'].get('text_of_law_type_id')
    names = {t.get('text_of_law_type', t)['id']: t.get('text_of_law_type', t).get('name', '') for t in h.types() or []}
    return not ORD_TYPE_EXC.search(names.get(tid, ''))


def fetch_ordinances(slug: str):
    """Ordinances of one canton. robots.txt is read again first; any change from the copy read for the laws stops
    the host."""
    h = Host(slug)
    rp = h.cache / 'robots.txt'
    old = rp.read_bytes() if rp.exists() else None
    if old is not None:
        (h.cache / 'robots.laws.txt').write_bytes(old)
    why = robots_ok(h)
    if why:
        print(f'{slug}: STOPPED {why}', flush=True)
        return
    if old is not None and rp.read_bytes() != old:
        print(f'{slug}: STOPPED robots.txt changed since the laws fetch', flush=True)
        return
    try:
        h.settings()
        h.types()
        h.index()
        n = 0
        for sn in ordinance_candidates(h):
            d = h.act(sn)
            if not d or not ord_type_ok(h, d):
                continue
            fetch_act(h, sn)
            n += 1
            if n % 25 == 0:
                print(f'{slug}: {n} ordinances fetched ({h.count} requests)', flush=True)
        (h.cache / 'fetch-ord-done.txt').write_text(f'{n} ordinances' + chr(10), encoding='utf-8')
        print(f'{slug}: ordinances done, {n} ({h.count} requests)', flush=True)
    except Exception as e:
        print(f'{slug}: STOPPED {e}', flush=True)


def fetch_act(h: Host, sn: str) -> bool:
    d = h.act(sn)
    if not d:
        return False
    t = d['text_of_law']
    for v in t.get('old_versions', []) + t.get('future_versions', []):
        h.version(sn, v['id'])
    return True


def robots_ok(h: Host) -> str | None:
    """None when robots.txt lets us fetch the API paths; otherwise the reason to stop."""
    import urllib.robotparser
    r = subprocess.run(['curl', '-s', '-m', '30', '-A', UA, '-w', '\n%{http_code}', f'https://{h.host}/robots.txt'],
                       capture_output=True)
    body, _, code = r.stdout.rpartition(b'\n')
    code = code.decode().strip()
    (h.cache / 'robots.txt').write_bytes(body)
    if code.startswith('5'):
        return f'robots.txt {code}'
    if code != '200':
        return None
    txt = body.decode('utf-8', 'replace')
    if re.search(r'(?im)^\s*user-agent:\s*(claudebot|claude-web|anthropic-ai|gptbot|claude-user|claude-searchbot)', txt):
        return 'robots.txt names an AI agent'
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(txt.splitlines())
    for path in (h.url('texts_of_law/lightweight_index'), h.url('texts_of_law/101'), h.url('settings')):
        if not rp.can_fetch('*', path):
            return f'robots.txt disallows {path}'
    if rp.crawl_delay('*'):
        h.pause = max(h.pause, float(rp.crawl_delay('*')))
    return None


def fetch_canton(slug: str, max_laws: int | None):
    h = Host(slug)
    why = robots_ok(h)
    if why:
        print(f'{slug}: STOPPED {why}', flush=True)
        return
    try:
        h.settings()
        h.types()
        h.index()
        sn = constitution_sn(h)
        fetch_act(h, sn)
        print(f'{slug}: constitution {sn} fetched ({h.count} requests)', flush=True)
        types = law_type_ids(h)
        n = 0
        for sn in law_candidates(h):
            d = h.act(sn)
            if not d or d['text_of_law'].get('text_of_law_type_id') not in types:
                continue
            fetch_act(h, sn)
            n += 1
            if n % 10 == 0:
                print(f'{slug}: {n} laws fetched ({h.count} requests)', flush=True)
            if max_laws and n >= max_laws:
                break
        if not max_laws:
            (h.cache / 'fetch-done.txt').write_text(f'{n} laws' + chr(10), encoding='utf-8')
        print(f'{slug}: done, {n} laws ({h.count} requests)', flush=True)
    except Exception as e:
        print(f'{slug}: STOPPED {e}', flush=True)


# ---------------------------------------------------------------- parsing

DATE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')


def iso(s: str | None) -> str | None:
    m = DATE.search(s or '')
    return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else None


def clean(s: str) -> str:
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace('­', '')
    s = re.sub(r'[ \t\r\n]+', ' ', s).strip()
    return s


def ascii_key(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def padnum(s: str) -> str:
    return re.sub(r'\d+', lambda m: m.group().zfill(3), s)


def unit_key_for_article(num: str) -> str:
    k = ascii_key(num)
    return 'art-' + padnum(k) if k else 'art-x'


def _text(el) -> str:
    return clean(el.text_content())


def parse_xhtml(x: str) -> tuple[dict, list[str]]:
    """XHTML of one LexWork version -> ({unit key: unit}, [unknown classes])."""
    from lxml import html
    root = html.fromstring('<div>' + x + '</div>')
    docs = root.find_class('document')
    doc = docs[0]
    for st in doc.iter('strong'):
        if (st.text_content() or '').strip() in ('*', ''):
            st.drop_tree() if st.getparent() is not None else None
    for el in list(doc.iter()):
        cls = el.get('class') or ''
        if 'footnote' in cls and el.getparent() is not None:
            el.drop_tree()
    units: dict[str, dict] = {}
    order: list[str] = []
    unknown: list[str] = []
    cur = None
    ingress_lines: list[str] = []
    outline: list[str] = []
    egress: list[str] = []
    in_egress = False
    after_heading = False   # a section heading came after the last article: what follows is no longer that article
    annex: list[str] = []

    def add(line: str):
        line = clean(line)
        if not line:
            return
        if in_egress:
            egress.append(line)
        elif cur is None:
            ingress_lines.append(line)
        else:
            units[cur]['lines'].append(line)

    for el in doc:
        cls = (el.get('class') or '').strip()
        tag = el.tag
        if cls == 'systematic_number':
            continue
        if cls == 'title' and tag in ('h1', 'h2'):
            ingress_lines.append('# ' + _text(el))
            continue
        if cls in ('abbreviation', 'ingress_author', 'ingress_foundation', 'ingress_action'):
            if cls == 'ingress_foundation':
                for p in el.findall('.//p') or [el]:
                    if _text(p):
                        ingress_lines.append(_text(p))
            elif _text(el):
                ingress_lines.append(_text(el))
            continue
        if cls == 'enactment':
            t = re.sub(r'\s*\((Stand|état|stato|Etat|État)[^)]*\)', '', _text(el)).strip()
            if t:
                ingress_lines.append(t)
            continue
        if cls.startswith('level_') and 'title' in cls:
            n = re.match(r'level_(\d+)', cls)
            lvl = int(n.group(1)) if n else 1
            outline.append('#' * min(lvl + 1, 6) + ' ' + _text(el))
            after_heading = cur is not None
            continue
        if cls == 'article':
            in_egress = False
            after_heading = False
            num_el = el.find_class('article_number')
            sym = num = ''
            if num_el:
                s = num_el[0].find_class('article_symbol')
                n = num_el[0].find_class('number')
                sym = _text(s[0]) if s else ''
                num = _text(n[0]) if n else _text(num_el[0])
            title_el = el.find_class('article_title')
            title = _text(title_el[0]) if title_el else ''
            label = clean(f'{sym} {num}') or 'Art.'
            key = unit_key_for_article(num or label)
            base, i = key, 2
            while key in units:
                key = f'{base}-{i}'
                i += 1
            cur = key
            units[key] = {'label': label, 'kind': 'art', 'lines': ['# ' + clean(f'{label} {title}')]}
            order.append(key)
            continue
        if cls == 'paragraph':
            n = el.find_class('number')
            num = _text(n[0]) if n else ''
            body = []
            for p in el.findall('p') or []:
                body.append(_text(p))
            if not body:
                t = _text(el)
                body = [t[len(num):].strip() if num and t.startswith(num) else t]
            first = True
            for b in body:
                add((num + ' ' + b) if first and num else b)
                first = False
            continue
        if cls == 'paragraph_post':
            if _text(el):
                add(_text(el))
            continue
        if tag == 'table':
            for tr in el.iter('tr'):
                cells = [_text(td) for td in tr if td.tag in ('td', 'th')]
                cells = [c for c in cells if c]
                if cells:
                    add(' '.join(cells) if 'enumeration' in cls else ' | '.join(cells))
            continue
        if cls.startswith('egress'):
            if cls == 'egress_ags_source':
                continue
            in_egress = True
            ps = el.findall('.//p')
            for p in ps or [el]:
                if _text(p):
                    egress.append(_text(p))
            continue
        # anything else: keep its text where it stands
        if cls not in unknown:
            unknown.append(cls or tag)
        for p in (el.findall('.//p') or [el]):
            if after_heading and not in_egress:
                # e.g. the annex list (annex_title, annex_documents) after a closing section heading: its own file
                if clean(_text(p)):
                    annex.append(clean(_text(p)))
            else:
                add(_text(p))
    out: dict[str, dict] = {}
    if ingress_lines:
        out['ingress'] = {'label': 'Titel und Ingress', 'kind': 'preamble', 'text': '\n'.join(ingress_lines) + '\n'}
    for k in order:
        u = units[k]
        out[k] = {'label': u['label'], 'kind': 'art', 'text': '\n'.join(u['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Gliederung', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    if annex:
        out['anhaenge'] = {'label': 'Anhänge', 'kind': 'annex', 'text': '\n'.join(annex) + '\n'}
    if egress:
        out['schluss'] = {'label': 'Schlussformel', 'kind': 'final', 'text': '\n'.join(egress) + '\n'}
    return out, unknown


HEAD_MAP = [('decided', r'beschluss|d[ée]cision|decisione|adoption|adozione|erlass'),
            ('inforce', r'inkraft|vigueur|vigore|vollzugsbeginn|wirksam'),
            ('element', r'element|[ée]l[ée]ment|elemento|bestimmung|disposition|disposizione'),
            ('change', r'[äa]nderung|modification|modifica|type|wirkung'),
            ('ref', r'fundstelle|source|fonte|publication|pubblicazione|publiziert|lf\. ?nr|abl|amtsblatt|ags|bag|rof|rcv|gs|crs')]


def change_table(x: str) -> list[dict]:
    """Rows of the change table(s); each table is read with its own header (LexWork prints the same rows twice,
    'nach Beschluss' and 'nach Artikel', with the columns in another order)."""
    from lxml import html
    root = html.fromstring('<div>' + x + '</div>')
    mt = root.get_element_by_id('modification_table', None)
    if mt is None:
        return []
    out, seen = [], set()
    for table in mt.iter('table'):
        rows = table.findall('.//tr')
        if not rows:
            continue
        heads = [_text(th).lower() for th in rows[0] if th.tag in ('th', 'td')]
        cols = {}
        for i, hd in enumerate(heads):
            for name, pat in HEAD_MAP:
                if name not in cols and re.search(pat, hd):
                    cols[name] = i
                    break
        if len(cols) < 5:
            continue  # a table whose columns we cannot name is not read
        for tr in rows[1:]:
            tds = [_text(td) for td in tr if td.tag == 'td']
            if len(tds) < 5:
                continue
            r = {k: tds[i] for k, i in cols.items()}
            r['decided'] = iso(r['decided'])
            r['inforce'] = iso(r['inforce'])
            r['first'] = bool(re.search(r'erstfassung|grunderlass|texte original|version originale|testo originale|^original|erlass$',
                                        r['change'] + ' ' + r['element'], re.I)) and not re.search(
                r'(art|§)', r['element'], re.I)
            sig = (r['decided'], r['inforce'], r['element'], r['change'], r['ref'])
            if sig not in seen:
                seen.add(sig)
                out.append(r)
    return out


def change_rows(xhtmls: list[str]) -> list[dict]:
    """The union of the change tables of every version, newest first (a total revision's table drops older rows)."""
    out, seen = [], set()
    for x in xhtmls:
        for r in change_table(x):
            sig = (r['decided'], r['inforce'], r['element'], r['change'], r['ref'])
            if sig not in seen:
                seen.add(sig)
                out.append(r)
    return out


ELEM_ART = re.compile(r'^\s*(?:Art(?:ikel|icle|icolo)?\.?|§+)\s*([0-9]+[a-zA-Z]*(?:[ .-]?(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?(?:[.-]\d+[a-z]*)*|[A-Z]+\d*-\d+)', re.I)


def element_units(el: str) -> set[str]:
    out = set()
    m = ELEM_ART.match(el)
    if m:
        out.add(unit_key_for_article(m.group(1).replace(' ', '')))
    if re.search(r'erlasstitel|titre|titolo|ingress|pr[ée]ambule|preambolo|abk[üu]rzung', el, re.I):
        out.add('ingress')
    if re.search(r'^(titel|kapitel|abschnitt|teil|gliederung|titre|chapitre|section|capitolo|sezione)\b', el, re.I) or \
            re.search(r'überschrift|ueberschrift|intitul|rubrica', el, re.I):
        out.add('gliederung')
    return out


def law_key(chron: str, row: dict) -> tuple[str, str]:
    ref = row['ref'].strip()
    if ref and ref not in ('-', '–'):
        return ascii_key(f'{chron}-{ref}'), f'{chron} {ref}'
    return ascii_key(f'{chron}-beschluss-{row["decided"] or row["inforce"]}'), f'{chron}, Beschluss vom {row["decided"] or row["inforce"]}'


def parse_act(h: Host, sn: str, chron: str, sysname: str, docs_date: str) -> tuple[dict, dict, list[str]] | None:
    d = h.cached(h.url('texts_of_law/' + urllib.parse.quote(sn, safe='')))
    if not d:
        return None
    t = d['text_of_law']
    vids = [('cur', t['selected_version'])]
    vlist = []
    allv = t.get('old_versions', []) + [t['current_version']] + t.get('future_versions', [])
    for v in allv:
        if v['id'] == t['selected_version']['id']:
            full = t['selected_version']
            url = h.url('texts_of_law/' + urllib.parse.quote(sn, safe=''))
        else:
            url = h.url(f'texts_of_law/{urllib.parse.quote(sn, safe="")}/versions/{v["id"]}')
            fv = h.cached(url)
            if not fv:
                return None  # not all versions fetched yet
            full = fv['text_of_law']['selected_version']
        frm = iso(v.get('version_dates_str') or full.get('version_dates_str'))
        if not frm or not full.get('xhtml_tol'):
            continue  # no date, or a version published only as PDF: not used
        raw = h.path(url).read_bytes()
        vlist.append({'from': frm, 'id': v['id'], 'xhtml': full['xhtml_tol'], 'url': url,
                      'sha256': hashlib.sha256(raw).hexdigest(), 'cdocs': fv['text_of_law'].get('change_documents', []) if v['id'] != t['selected_version']['id'] else t.get('change_documents', [])})
    if not vlist:
        return 'skip'  # no version with text (PDF only)
    vlist.sort(key=lambda v: (v['from'], v['id']))
    # one version per day: the last of a day stands
    dedup = {}
    for v in vlist:
        dedup[v['from']] = v
    vlist = sorted(dedup.values(), key=lambda v: v['from'])
    # the change table of the latest version holds every row
    rows = change_rows([v['xhtml'] for v in reversed(vlist)])
    cdocs = {}
    for v in vlist:
        for c in v['cdocs']:
            cdocs.setdefault(str(c.get('number') or '').strip(), c)
    laws: dict[str, dict] = {}

    def key_of(r):
        k, label = law_key(chron, r)
        label = LABELS.setdefault(k, label)  # one label per key across the canton's parts (published ones win)
        if k not in laws:
            cd = cdocs.get(r['ref'].strip())
            title = clean(cd['document_title']) if cd and cd.get('document_title') else (
                clean(t['title']) if r['first'] else
                f"{CHG[h.lang]} {_dmy(r['decided'] or r['inforce'])} ({label})")
            laws[k] = {'label': label, 'title': title, 'kind': 'law', 'enacted': r['decided'],
                       'published': iso(cd.get('date_of_publication_string')) if cd else None,
                       'url': cd.get('pdf_link') if cd else None, 'temporary_until': None, 'restores': None,
                       'note': None}
        return k
    for r in rows:
        if r['inforce'] or r['decided']:
            key_of(r)
    versions = []
    unknown_all: list[str] = []
    prev_units = None
    prev_from = None
    firsts = sorted((r for r in rows if r['first'] and r['inforce']), key=lambda r: r['inforce'])
    first_row = firsts[0] if firsts else None  # the oldest Erstfassung (a later one is a total revision)
    for i, v in enumerate(vlist):
        units, unk = parse_xhtml(v['xhtml'])
        unknown_all += [u for u in unk if u not in unknown_all]
        ver = {'from': v['from'], 'source_url': v['url'].replace('/api/', '/api/', 1), 'sha256': v['sha256']}
        if prev_units is None:
            ver['units'] = units
            ver['credits'] = {}
        else:
            changed = sorted(k for k in set(prev_units) | set(units)
                             if prev_units.get(k, {}).get('text') != units.get(k, {}).get('text'))
            ch = {k: units.get(k) for k in changed}
            ver['changes'] = ch
            # an Erstfassung row inside the window is a new act replacing the old one under the same number
            window = [r for r in rows if r['inforce'] and prev_from < r['inforce'] <= v['from']]
            credits = {}
            day_laws = sorted({key_of(r) for r in window})
            for k in changed:
                ls = sorted({key_of(r) for r in window if k in element_units(r['element'])})
                if not ls:
                    ls = day_laws
                if ls:
                    credits[k] = ls
            ver['credits'] = credits
            if not changed:
                # nothing changed in the text we keep (only markers or the change table): skip the version
                continue
        versions.append(ver)
        prev_units = units
        prev_from = v['from']
    v0 = versions[0]
    earlier = sorted({key_of(r) for r in rows if r['inforce'] and r['inforce'] <= v0['from'] and not r['first']})
    first_law = None
    if first_row and not earlier and first_row['inforce'] and first_row['inforce'] <= v0['from']:
        first_law = key_of(first_row)
    elif first_row and first_row['inforce'] <= v0['from']:
        earlier = sorted({key_of(first_row)} | set(earlier))
    abbr = clean(t.get('abbreviation') or '')
    slug = ascii_key(sn)
    if abbr:
        slug = f'{slug}-{ascii_key(abbr)}' if ascii_key(abbr) else slug
    act = {
        'slug': slug, 'short': abbr or f'{sysname} {sn}', 'title': clean(t['title']),
        'url': t.get('canonical_link'), 'first_law': first_law, 'earlier_laws': earlier,
        'systematic_number': sn, 'enacted': t.get('date_of_decision'), 'in_force': t.get('enactment'),
        'versions': versions,
    }
    used = set()
    for v in versions:
        for ls in v.get('credits', {}).values():
            used.update(ls)
    if first_law:
        used.add(first_law)
    used.update(earlier)
    return act, {k: laws[k] for k in sorted(used)}, unknown_all


def country_block(slug: str, h: Host, settings: dict) -> dict:
    code, en, native, host, lang, _ = CANTONS[slug]
    return {
        'code': f'CH-{code}', 'name': en, 'slug': f'switzerland-{slug}', 'lang': lang, 'tz': 'Europe/Zurich',
        'future_branch': FUTURE[lang],
        'publisher': {'name': f'{native}, {settings["collection_names"]["systematic"]} ({host})',
                      'email': f'gesetzessammlung@{host}.invalid'},
        'default_in_force_rule': {
            'text': ('Each version is dated by the day the canton\'s systematic collection says it took effect '
                     '("in Kraft seit / von"); cantonal acts take effect on the day the act or the government sets.'),
            'source': f'https://{host}/'},
        'licence_note': (f'Text: {native}, {settings["collection_names"]["systematic"]}, https://{host}/. '
                         'Laws and decrees are not protected by copyright in Switzerland (Art. 5 para. 1 let. a URG).'),
    }


LABELS: dict[str, str] = {}


FORCE = False


def parse_canton(slug: str, docs_date: str, max_acts: int | None = None):
    h = Host(slug)
    LABELS.clear()
    parts = sorted((folder(slug) / 'corpus.d').glob('*.json'), key=lambda p: (not p.with_suffix('.PUBLISH').exists(), p.name))
    for p in parts:
        for k, law in json.loads(p.read_text(encoding='utf-8')).get('laws', {}).items():
            LABELS.setdefault(k, law['label'])
    st = h.cached(h.url('settings'))
    chron = st['collection_names']['chronological']
    sysname = st['collection_names']['systematic'].replace(' Nr.', '').strip()
    out = folder(slug) / 'corpus.d'
    out.mkdir(exist_ok=True)
    report = {}
    src = {'name': f'{CANTONS[slug][2]}: {st["collection_names"]["systematic"]} (LexWork)', 'url': f'https://{h.host}/',
           'retrieved': docs_date,
           'licence': 'Laws and decrees are not protected by copyright (Art. 5 para. 1 let. a URG, SR 231.1).',
           'notes': 'Every consolidated version the collection offers for each act, with its change table.'}
    # part 10: the constitution
    const = constitution_sn(h)
    r = None if (out / '10-verfassung.json').exists() and not FORCE else parse_act(h, const, chron, sysname, docs_date)
    if r and r != 'skip':
        act, laws, unk = r
        part = {'country': country_block(slug, h, st), 'sources': [src], 'laws': laws, 'acts': [act],
                'decisions': decisions(chron), 'ai_use': AI_USE}
        write_part(out / '10-verfassung.json', part)
        report['10-verfassung'] = {'acts': 1, 'versions': len(act['versions']), 'unknown': unk}
    # parts 20..: the laws, in systematic order, PART_SIZE each, only when every act of the part is fetched
    types = law_type_ids(h) if h.cached(h.url('text_of_law_types')) else set()
    sns = []
    for sn in law_candidates(h):
        d = h.cached(h.url('texts_of_law/' + urllib.parse.quote(sn, safe='')))
        if d is False:
            break  # not fetched yet: stop at the first gap, so parts stay in order
        if d and d['text_of_law'].get('text_of_law_type_id') in types:
            sns.append(sn)
    for pi in range(0, len(sns), PART_SIZE):
        chunk = sns[pi:pi + PART_SIZE]
        if len(chunk) < PART_SIZE and not (h.cache / 'fetch-done.txt').exists():
            break  # the last, short part waits until every law is fetched
        name = f'{20 + pi // PART_SIZE:02d}-gesetze-{pi // PART_SIZE + 1}'
        if (out / f'{name}.json').exists() and not FORCE:
            continue  # written once; a changed parser means deleting the unpublished part by hand
        acts, laws, unk = [], {}, []
        complete = True
        for sn in chunk:
            r = parse_act(h, sn, chron, sysname, docs_date)
            if r is None:
                complete = False
                break
            if r == 'skip':
                continue
            a, l, u = r
            acts.append(a)
            laws.update(l)
            unk += [x for x in u if x not in unk]
        if not complete:
            break
        write_part(out / f'{name}.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
        report[name] = {'acts': len(acts), 'versions': sum(len(a['versions']) for a in acts), 'unknown': unk,
                        'first': chunk[0], 'last': chunk[-1], 'full': len(chunk) == PART_SIZE}
    # parts 40..: the ordinances, the same way, once their fetch has started
    if h.cached(h.url('text_of_law_types')):
        have = set()
        for p in out.glob('*.json'):
            if 'verordnungen' not in p.stem:
                have.update(a['systematic_number'] for a in json.loads(p.read_text(encoding='utf-8'))['acts'])
        osns = []
        for sn in ordinance_candidates(h):
            d = h.cached(h.url('texts_of_law/' + urllib.parse.quote(sn, safe='')))
            if d is False:
                break
            if d and sn not in have and ord_type_ok(h, d):
                osns.append(sn)
        for pi in range(0, len(osns), PART_SIZE):
            chunk = osns[pi:pi + PART_SIZE]
            if len(chunk) < PART_SIZE and not (h.cache / 'fetch-ord-done.txt').exists():
                break
            name = f'{40 + pi // PART_SIZE:02d}-verordnungen-{pi // PART_SIZE + 1}'
            if (out / f'{name}.json').exists() and not FORCE:
                continue
            acts, laws, unk = [], {}, []
            complete = True
            for sn in chunk:
                r = parse_act(h, sn, chron, sysname, docs_date)
                if r is None:
                    complete = False
                    break
                if r == 'skip':
                    continue
                a, l, u = r
                acts.append(a)
                laws.update(l)
                unk += [x for x in u if x not in unk]
            if not complete:
                break
            write_part(out / f'{name}.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
            report[name] = {'acts': len(acts), 'versions': sum(len(a['versions']) for a in acts), 'unknown': unk,
                            'first': chunk[0], 'last': chunk[-1], 'full': len(chunk) == PART_SIZE}
    print(json.dumps({slug: report}, ensure_ascii=False))


AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which acts to include; it wrote no law text. '
          'Every word of law comes from the canton\'s own collection.']


def decisions(chron: str) -> list[str]:
    return [
        'Each version is the consolidated text the canton\'s systematic collection publishes, dated by its "in force '
        'from" day; when two versions share a day only the last is kept.',
        f'Changes are credited to the entries of the act\'s own change table (decision, in-force day, element, {chron} '
        'reference) whose in-force day falls after the previous version and on or before this one; a change whose '
        'element the table does not name is credited to every entry of that window.',
        'Section headings are kept together in one file per act (gliederung.md); the title, date and preamble in '
        'ingress.md; the signature block in schluss.md. Amendment markers (*) and the "Stand" date are left out.',
        'Annexes published only as separate PDF files are not included.',
        'An act\'s first version is credited to its original enactment only when the change table shows no change '
        'in force before it; otherwise it is the oldest version available.',
    ]


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists() and not FORCE:
        return  # a published part never changes: main is append-only
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


# ---------------------------------------------------------------- checks

def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


def letters_check(slug: str, part_name: str) -> list[str]:
    """Independent check: for every version of every act in the part, the letters and digits of all units equal
    the letters and digits of the source XHTML document (tags stripped by regex, not lxml), less the systematic
    number, the amendment markers and the Stand date."""
    h = Host(slug)
    p = folder(slug) / 'corpus.d' / f'{part_name}.json'
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
            body = h.path(v['source_url']).read_bytes()
            d = json.loads(body)['text_of_law']['selected_version']['xhtml_tol']
            doc = d.split("<div class='footnotes'")[0]
            doc = re.sub(r"(?s)<h1 class='systematic_number'>.*?</h1>", ' ', doc)
            doc = re.sub(r"(?s)<div class='egress_ags_source'>.*?</div>", ' ', doc)
            doc = re.sub(r'<strong>\s*\*\s*</strong>', ' ', doc)
            doc = re.sub(r'(?s)<a class="footnote"[^>]*>.*?</a>', ' ', doc)
            doc = re.sub(r"(?s)<div class='enactment'>(.*?)</div>",
                         lambda m: re.sub(r'\((Stand|état|stato|Etat|État|&eacute;tat|&Eacute;tat)[^)]*\)', ' ', m.group(1)), doc)
            src = htmlmod.unescape(re.sub(r'<[^>]+>', ' ', doc))
            mine = ''.join(u['text'] for u in units.values())
            a, b = sorted(letters(src)), sorted(letters(mine))
            if a != b:
                from collections import Counter
                ca, cb = Counter(letters(src)), Counter(letters(mine))
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((ca - cb).most_common(8))} '
                             f'corpus-only {dict((cb - ca).most_common(8))}')
            # order check per unit: each unit's letters appear in the source as a contiguous run
            sl = letters(src)
            for k, u in units.items():
                lines = u['text'].splitlines()
                chunks = [l.lstrip('# ') for l in lines] if k in ('gliederung', 'ingress') else (
                    ['\n'.join(lines[1:])] if k.startswith('art-') else [u['text']])
                bad = [c for c in chunks if letters(c) and letters(c) not in sl]
                if bad:
                    probs.append(f'{act["slug"]} {v["from"]} {k}: text not found in order in the source: {bad[0][:80]}')
                    break
    return probs


# ---------------------------------------------------------------- docs and scaffold

def _verified(slug: str, extra=()) -> list[dict]:
    d = folder(slug) / 'corpus.d'
    out = []
    for p in sorted(d.glob('*.json')):
        if p.with_suffix('.PUBLISH').exists() or p.stem in extra:
            out.append(json.loads(p.read_text(encoding='utf-8')))
    return out


def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {x.strftime("%B")} {x.year}'


def write_docs(slug: str, docs_date: str, extra=(), out: Path | None = None):
    code, en, native, host, lang, _ = CANTONS[slug]
    h = Host(slug)
    st = h.cached(h.url('settings'))
    sysname, chron = st['collection_names']['systematic'], st['collection_names']['chronological']
    parts = _verified(slug, extra)
    rows = []
    nacts = nvers = nords = 0
    ordsns = set()
    for p in (folder(slug) / 'corpus.d').glob('*verordnungen*.json'):
        if p.with_suffix('.PUBLISH').exists() or p.stem in extra:
            ordsns.update(a['systematic_number'] for a in json.loads(p.read_text(encoding='utf-8'))['acts'])
    for part in parts:
        for a in part['acts']:
            nords += a['systematic_number'] in ordsns
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = _long(vs[0]['from']) if len(vs) == 1 else f'{_long(vs[0]["from"])} to {_long(vs[-1]["from"])}'
            hist = ('as enacted, then ' if a.get('first_law') else 'oldest version available, then ') if len(vs) > 1 \
                else ('as enacted, ' if a.get('first_law') else 'one version (the oldest available), ')
            rows.append(f'| `{a["slug"]}/` | {a["title"]} ({sysname} {a["systematic_number"]}) | {len(vs)} | '
                        f'{hist}{"each consolidated version: " if len(vs) > 1 else ""}{span} |')
    repo = out or (folder(slug) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en}: law history in git

The law of the canton of {en} ({native}, Switzerland) as a git history: one file per article, one commit per amending act on the day it took effect, and the amending act as the commit's author. `git blame` names the act behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `ch-{code.lower()}/`. The federal law is in [lexifina/switzerland-law](https://github.com/lexifina/switzerland-law).

The text is in {LANGNAME[lang]}, the canton's {"official language" if slug not in ('bern', 'fribourg', 'valais', 'graubunden') else "first official language in the collection"}, exactly as the canton publishes it.

## What this repository holds

{nacts} act{"s" if nacts != 1 else ""} with {nvers} versions so far: {(f"the cantonal constitution, the cantonal laws (Gesetze) in force and {nords} {ORD_NAME[lang][1]} in force, in the order of the systematic collection, added in parts. Other decrees and decisions, intercantonal agreements and repealed acts are not included yet.") if nords else "the cantonal constitution, then the cantonal laws (Gesetze) in force, in the order of the systematic collection, added in parts. Ordinances, decrees, intercantonal agreements and repealed acts are not included yet."}

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

The {sysname} ({"systematic collection" if lang == 'de' else "systematic collection"}) of the canton, published by the canton at <https://{host}/>. For each act it gives every consolidated version it holds, with the day each version took effect, and a change table listing each amendment: its decision date, the day it took effect, the provision it touched and its entry in the chronological collection ({chron}). Annexes the collection publishes only as separate PDF files are not included.

## Dates

- Each commit is dated at **noon, Europe/Zurich, on the day the version took effect**, as the collection gives it ("in Kraft seit / von"). The decision date of each amending act is the `Enacted:` trailer.
- An act's first commit is its oldest version in the collection. It is credited to the act as enacted only when the change table shows no amendment in force before it; otherwise it is the "oldest version available", naming the earlier amendments.
- Versions that take effect after the retrieval day are on the `{FUTURE[lang]}` branch, never merged into `main`.
- `--before="YYYY-MM-DD"` alone uses your clock's time of day; use `T23:59:59Z` or `tools/on.py`.

## Files

`<act>/art-005.md` is Art. 5 (or § 5), `art-005a.md` Art. 5a; `ingress.md` holds the title, date and preamble; `gliederung.md` the section headings; `schluss.md` the closing formula and signatures. One paragraph or list item per line. Amendment markers (`*`), footnote numbers and the "Stand" date are left out.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the canton's own text of that version, and every article's text appears in it in order.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

The author of a commit is the amending act, named by its entry in the chronological collection ({chron}), with an e-mail address that cannot exist (`<act key>@{host}.invalid`). Where one version holds changes by several amending acts and the change table does not say which provision each one touched, the commit names them all. The committer is always Lexifina.

## Limits

This is not an official publication. The binding text is the one the canton publishes as binding (its chronological collection, or its systematic collection where cantonal law makes that binding). The history starts with the oldest consolidated version the collection holds for each act, which for many acts is later than the act's enactment. Only the acts listed above are included.
"""
    lic = f"""The law texts in this repository are official texts of the canton of {en} ({native}), taken from its
systematic collection ({sysname}, https://{host}/).

Swiss law does not protect them by copyright. Federal Act on Copyright and Related Rights (URG, SR 231.1),
Art. 5 para. 1: "Keinen urheberrechtlichen Schutz geniessen: a. Gesetze, Verordnungen, völkerrechtliche Verträge
und andere amtliche Erlasse; [...]" (Not protected by copyright: a. acts, ordinances, international treaties and
other official enactments.)

Any copyright notice on the canton's website covers the website's own protected content, not the law texts, which
Art. 5 URG excludes. This repository is not an official publication; the binding text is the one the canton
publishes as binding.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': f'ch-{code.lower()}', 'code': f'CH-{code}', 'name': en, 'level': 'canton',
             'parent': 'ch', 'repo': f'https://github.com/lexifina/switzerland-{slug}-law',
             'build': (f'built: constitution, cantonal laws and {ORD_NAME[lang][0]} ({nacts} acts, {nvers} versions) '
                       f'from the {sysname}') if nords else
                      f'built: constitution and cantonal laws ({nacts} acts, {nvers} versions) from the {sysname}',
             'language': lang, 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


def scaffold(slug: str) -> str:
    import tempfile
    code, en, native, host, lang, _ = CANTONS.get(slug, OTHER.get(slug))
    repo = f'switzerland-{slug}-law'
    remote = f'https://github.com/lexifina/{repo}.git'

    def run(*a, cwd=None, check=True):
        p = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if check and p.returncode:
            raise SystemExit(f'{a[:3]} failed: {p.stderr[:400]}')
        return p
    ls = run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    if run('gh', 'api', f'repos/lexifina/{repo}', check=False).returncode != 0:
        run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
            '-f', f'description={en} (Switzerland) cantonal law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    run('git', 'init', '-q', '-b', 'main', cwd=d)
    (d / 'README.md').write_text(f"""# {en}: law as git history

Work in progress. This repository will hold the law of the canton of {en} ({native}, Switzerland) as a git
history: one file per article, one commit per amending act on the day it took effect, `git blame` and `git log`
working line by line.

Planned first build: the cantonal constitution, then the cantonal laws, with every consolidated version the
canton's systematic collection publishes.

Source: <https://{host}/>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text(f"""# Sources

- {native}, systematic collection: <https://{host}/>

Laws and decrees are not protected by copyright in Switzerland (Art. 5 para. 1 let. a URG, SR 231.1). The terms
and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    run('git', 'add', '-A', cwd=d)
    run('git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
        f'Switzerland ({en}): sources, before any law', cwd=d)
    run('git', 'remote', 'add', 'origin', remote, cwd=d)
    p = run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
    return (p.stderr[-200:] + run('git', 'ls-remote', remote).stdout).strip()


OTHER: dict = {}

DOCS = ROOT.parent.parent   # ~/Documents


def _low(cmd: list[str], env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                          creationflags=0x4000 if os.name == 'nt' else 0)   # BELOW_NORMAL_PRIORITY_CLASS


def _rm(d: Path):
    import shutil
    import stat

    def onerr(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if d.exists():
        shutil.rmtree(d, onexc=onerr)


def verify_parts(slug: str, parts: list[str], docs_date: str) -> dict[str, tuple[bool, str]]:
    """Several parts at once: letters check each, then ONE scratch build of the verified parts plus those that passed,
    and check.py on it. Returns {part: (ok, line)}."""
    out = {}
    good = []
    for part in parts:
        probs = letters_check(slug, part)
        if probs:
            out[part] = (False, f'letters check: {len(probs)} problems: {probs[0]}')
        else:
            good.append(part)
    if not good:
        return out
    src = folder(slug)
    tmp = DOCS / f'switzerland-{slug}-law-verify'
    build = DOCS / f'switzerland-{slug}-law-verifybuild'
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    import shutil
    names = sorted({p.stem for p in (src / 'corpus.d').glob('*.json')
                    if p.with_suffix('.PUBLISH').exists() and p.stem not in out} | set(good))
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(slug, docs_date, extra=good, out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    res = None
    if not b.returncode:
        c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                  str(tmp / 'corpus.json')])
        try:
            res = json.loads(c.stdout[c.stdout.index('{'):])
        except Exception:
            res = None
    clean_ok = res is not None and not any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards',
                                                                 'future_dated', 'missing_in_force'))
    for part in good:
        if not clean_ok:
            why = ('build failed: ' + (b.stderr or b.stdout)[-400:]) if b.returncode else \
                ('check.py: ' + json.dumps({k: v for k, v in (res or {}).items() if k != 'details'})[:300])
            out[part] = (False, why)
            continue
        p = json.loads((src / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
        acts = p['acts']
        nv = sum(len(a['versions']) for a in acts)
        days = sorted(v['from'] for a in acts for v in a['versions'])
        out[part] = (True, f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} from the canton\'s LexWork '
                           f'collection ({CANTONS[slug][3]}): letters-and-digits of every version equal the source XHTML '
                           f'and every article is found in order; scratch build of all verified parts: check.py '
                           f'{res["versions"]} versions, 0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return out


def verify_part(slug: str, part: str, docs_date: str) -> tuple[bool, str]:
    """Letters check, then a scratch build of the verified parts plus this one, and check.py on it."""
    import shutil
    probs = letters_check(slug, part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[0]}'
    src = folder(slug)
    tmp = DOCS / f'switzerland-{slug}-law-verify'
    build = DOCS / f'switzerland-{slug}-law-verifybuild'
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
    p = json.loads((src / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    acts = p['acts']
    nv = sum(len(a['versions']) for a in acts)
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} from the canton\'s LexWork collection '
            f'({CANTONS[slug][3]}): letters-and-digits of every version equal the source XHTML and every article is '
            f'found in order; scratch build of verified parts + this part: check.py {res["versions"]} versions, '
            f'0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
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
    if not top.exists():  # autopush publishes main only once the canton folder has PUBLISH; parts still need theirs
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'fetch':
        args = sys.argv[2:]
        maxl = None
        if args and args[0].startswith('--max='):
            maxl = int(args[0].split('=')[1])
            args = args[1:]
        ths = [threading.Thread(target=fetch_canton, args=(s, maxl)) for s in args]
    elif cmd == 'fetch-ord':
        ths = [threading.Thread(target=fetch_ordinances, args=(s_,)) for s_ in sys.argv[2:]]
    if cmd in ('fetch', 'fetch-ord'):
        for t in ths:
            t.start()
        for t in ths:
            t.join()
    elif cmd == 'reparse':
        FORCE = True
        parse_canton(sys.argv[2], sys.argv[3])
    elif cmd == 'parse':
        parse_canton(sys.argv[2], sys.argv[3])
    elif cmd == 'docs':
        write_docs(sys.argv[2], sys.argv[3])
    elif cmd == 'scaffold':
        for s_ in sys.argv[2:]:
            print(s_, scaffold(s_))
    elif cmd == 'publish':
        print(sys.argv[2], sys.argv[3], publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'letters':
        probs = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(probs[:40]) or 'letters check: clean')
        print(f'{len(probs)} problems')
