"""Emilia-Romagna dated history (gitlaw-scraper-dell, 2026-10-30). Private; never published.

Adds the earlier versions Demetra publishes on each amended law's "storia" tab (the original text and every "Testo
Coordinato") before the current text already in corpus.d (from the open-data NIR zips, see it_emilia_romagna.py).
The current text of every act stays byte for byte; earlier versions are added before it.

    python -X utf8 scripts/world-law/it_er_history.py fetch [--sample N]  # storia + current pages, then versions
    python -X utf8 scripts/world-law/it_er_history.py compare            # HTML reader vs the current units
    python -X utf8 scripts/world-law/it_er_history.py inforce            # in-force rule vs Demetra's vigenza
    python -X utf8 scripts/world-law/it_er_history.py stage              # history-stage/<part>.json + report
    python -X utf8 scripts/world-law/it_er_history.py letters <part>     # independent check of a staged part
    python -X utf8 scripts/world-law/it_er_history.py swap <part> ...    # verify staged parts (scratch build), swap
"""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import lxml.html

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import it_emilia_romagna as E  # noqa: E402
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'emilia-romagna'
BASE = 'https://demetra.regione.emilia-romagna.it/al/'
FOLDER = R.folder(SLUG)
STAGE = FOLDER / 'history-stage'
LOG = FOLDER / 'history-fetch.log'
REPORT = FOLDER / 'history-report.json'
CARRIED = ('intestazione', 'formula-finale', 'allegati')   # not printed on Demetra's version pages
NL = '\n'


def log(*a):
    line = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + ' '.join(str(x) for x in a)
    with open(LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(line + '\n')
    print(line, flush=True)


def amended_acts() -> list[tuple[str, dict]]:
    out = []
    for p in sorted((FOLDER / 'corpus.d').glob('*.json')):
        pj = json.loads(p.read_text(encoding='utf-8'))
        for a in pj['acts']:
            if not a.get('first_law'):
                out.append((p.stem, a))
    return out


def storia_url(act_url: str) -> str:
    return act_url + '&dl_t=text/xml&dl_a=y&dl_id=10&pr=storia,1'


def cached(url: str) -> bytes | None:
    p = it_fetch.path_for(url)
    return p.read_bytes() if p.exists() else None


def storia_rows(page: bytes) -> dict:
    """The storia tab: each listed version (dl path, kind, date), oldest first, and the current text's publication
    date ("Data di pubblicazione della legge modificante")."""
    s = page.decode('utf-8', 'replace')
    i = s.find('id="doc_tes_storia"')
    if i < 0:
        return {'rows': [], 'current_pub': None}
    t = s[i:s.find('lex_rif_footer', i)]
    rows = []
    for tr in re.findall(r'(?s)<tr class="hitlist-row-[a-z]+">(.*?)</tr>', t):
        tds = re.findall(r'(?s)<td[^>]*>(.*?)</td>', tr)
        if len(tds) < 4:
            continue
        orig = re.search(r'href="([^"]+)">(\d\d/\d\d/\d{4})</a>', tds[2])
        mod = re.search(r'href="([^"]+)">(\d\d/\d\d/\d{4})</a>', tds[3])
        m = orig or mod
        if not m:
            continue
        href = html.unescape(m.group(1))
        d, mo, y = m.group(2).split('/')
        rows.append({'kind': 'originale' if orig else 'coordinato', 'date': f'{y}-{mo}-{d}',
                     'dl': re.search(r'[?&]dl=([^&]+)', href).group(1),
                     'url': BASE + href.replace('&pr=storia,1', '')})
    cp = re.search(r'Data di pubblicazione della legge modificante :\s*(\d\d)/(\d\d)/(\d{4})', t)
    rows.sort(key=lambda r: (r['date'], r['kind'] != 'originale'))
    return {'rows': rows, 'current_pub': f'{cp[3]}-{cp[2]}-{cp[1]}' if cp else None}


SN = re.compile(r'_s(\d+)/[^/]+$')


def earlier_rows(st: dict) -> list[dict]:
    """The earlier versions: Demetra files them as .../LR_<y>_<n>_s<k>/... (s1 the original); the current text is
    the file without _s<k>, which some storia tabs list too."""
    return sorted((r for r in st['rows'] if SN.search(r['dl'])), key=lambda r: int(SN.search(r['dl']).group(1)))


# ---------------------------------------------------------------- fetch

def get(url: str) -> bytes | None:
    R.wait_cpu()
    was = it_fetch.path_for(url).exists()
    b = it_fetch.get(url, timeout=120)
    if not was:
        log('GET', url, len(b or b''))
    return b


def fetch(sample: int | None = None):
    acts = amended_acts()
    if sample:
        step = max(1, len(acts) // sample)
        acts = acts[::step][:sample]
    log(f'fetch: {len(acts)} amended acts, storia + current pages')
    for _, a in acts:
        get(storia_url(a['url']))
        get(a['url'])
    if sample:
        return
    log('fetch: version pages')
    n = 0
    for _, a in acts:
        st = storia_rows(get(storia_url(a['url'])) or b'')
        for r in earlier_rows(st):
            get(r['url'])
            n += 1
    log(f'fetch: done, {n} version pages')


# ---------------------------------------------------------------- the HTML reader (same units as the NIR reader)

BRK, EAT = '\x01', '\x02'
WS = re.compile(r'\s+')
BLOCKS = {'div', 'p', 'br', 'tr', 'li', 'table', 'tbody', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol'}
HEAD = {'libro', 'parte', 'titolo', 'capo', 'sezione', 'paragrafo'}
INLINE_DIV = {'mod', 'virgolette', 'articolo', 'num'} | HEAD


def classes(el) -> set:
    return set((el.get('class') or '').split())


def is_block(tag: str, cl: set) -> bool:
    """Mirror of the NIR reader's BLOCK set: Demetra's page turns <mod>, <virgolette>, <articolo>/<num> and the
    containers (titolo, capo, ...) into divs, but the NIR reader keeps them inline; their rubrica, comma, el and
    alinea are blocks. Table cells are inline, rows are blocks."""
    if tag == 'div':
        return not (cl & INLINE_DIV)
    if tag == 'span':
        return 'h:p' in cl
    return tag in BLOCKS


def flat(el, out: list, top=True):
    tag = el.tag if isinstance(el.tag, str) else ''
    cl = classes(el)
    if (tag == 'a' and 'ndr_nota' in cl) or 'ndr' in cl:
        return   # editor's note markers and amendment notes, which the NIR reader drops too
    if tag == 'img':
        out.append(EAT)   # the external-link icon after a reference: the space before it is the page's, not the law's
        return
    block = is_block(tag, cl) and not top
    if block:
        out.append(BRK)
    if el.text:
        out.append(WS.sub(' ', el.text))
    num_alone = 'alinea' in cl and 'corpo' not in cl    # <comma><num/><alinea>: the number on its own line
    for ch in el:
        flat(ch, out, top=False)
        if num_alone and isinstance(ch.tag, str) and ch.tag == 'span' and classes(ch) & {'Comma', 'elenco_n'}:
            out.append(BRK)
            num_alone = False
        if ch.tail:
            out.append(WS.sub(' ', ch.tail))
    if block:
        out.append(BRK)


def lines(el, top=True) -> list[str]:
    buf: list[str] = []
    flat(el, buf, top)
    s = re.sub(r'[ \t\n\r]*' + EAT, '', ''.join(buf))
    return [x for x in (R.clean_line(t) for t in s.split(BRK)) if x]


def fragment(s: str, start: str, end: str):
    i = s.find(start)
    j = s.find(end, i) if i >= 0 else -1
    if i < 0 or j < 0:
        return None
    return lxml.html.fragment_fromstring(s[s.rfind('<', 0, i):s.rfind('<', 0, j)], create_parent='div')


ENDS = ('id="doc_tes_formulaFinale"', 'id="doc_tes_annessi"', 'id="doc_piede"')


def body_end(s: str) -> str:
    """Where the articles end: the closing formula (some version pages print it), the annexes or the notes."""
    i = s.find('id="doc_tes_contenuto"')
    return min((e for e in ENDS if s.find(e, i) >= 0), key=lambda e: s.find(e, i))


def parse_page(raw: bytes) -> dict:
    """Units of a Demetra articolo page, keyed and written as it_emilia_romagna.units_of() writes the NIR file."""
    s = raw.decode('utf-8', 'replace')
    units: dict[str, dict] = {}

    def put(key, label, kind, ls):
        if not ls:
            return None
        k, n = key, 2
        while k in units:
            k, n = f'{key}-dup{n}', n + 1
        units[k] = {'label': label, 'kind': kind, 'text': NL.join(ls) + NL}
        return k

    fi = fragment(s, 'id="doc_tes_formulaIniziale"', 'id="doc_tes_contenuto"')
    if fi is not None:
        put('preambolo', 'Preambolo', 'preamble', lines(fi))
    body = fragment(s, 'id="doc_tes_contenuto"', body_end(s))
    st = {'pending': [], 'cur': None, 'key': None, 'last': None, 'idx': 0}

    def close():
        if st['cur'] is not None:
            st['last'] = put(st['key'][0], st['key'][1], 'art', st['cur'])
        st['cur'] = None

    def walk(el):
        for ch in el:
            if not isinstance(ch.tag, str):
                continue
            cl = classes(ch)
            if 'articolo' in cl:
                close()
                st['idx'] += 1
                numt = ''.join(lines(ch))
                st['key'] = (E.art_key(numt, st['idx']), R.clean_line(numt) or f'Articolo {st["idx"]}')
                st['cur'] = st['pending'][:] + lines(ch)
                st['pending'].clear()
            elif cl & HEAD or any(c.endswith('_rubrica') and c.split('_')[0] in HEAD for c in cl):
                close()
                st['pending'].extend(lines(ch))
            elif ch.tag == 'div' and not cl and len(ch):
                walk(ch)
            else:
                (st['cur'] if st['cur'] is not None else st['pending']).extend(lines(ch, top=False))
            if ch.tail and ch.tail.strip():
                (st['cur'] if st['cur'] is not None else st['pending']).append(R.clean_line(WS.sub(' ', ch.tail)))
    if body is not None:
        walk(body)
    close()
    if st['pending']:
        if st['last']:
            units[st['last']]['text'] += NL.join(st['pending']) + NL
        else:
            put('articolato', 'Articolato', 'art', st['pending'])
    return units


def page_meta(raw: bytes) -> dict:
    """The page's heading (without notes), the laws its "Testo coordinato con le modifiche apportate da" note names,
    its annex titles, and what kind of document it says it is."""
    s = raw.decode('utf-8', 'replace')
    head = fragment(s, 'id="doc_tes_intestazione"', 'class="lex_ind_header"') if 'class="lex_ind_header"' in s else \
        fragment(s, 'id="doc_tes_intestazione"', 'id="doc_cor_')
    mods, heading = [], ''
    if head is not None:
        for nd in head.xpath('.//*[contains(concat(" ", @class, " "), " ndr ")]'):
            for a in nd.iter('a'):
                m = E.URN.search(a.get('href') or '')
                if m:
                    mods.append(m)
                elif (a.text or '').strip():
                    lab = label_law(R.clean_line(a.text_content()))
                    mods.append(lab if lab else R.clean_line(a.text_content()))
        for el in head.xpath('.//*[contains(concat(" ", @class, " "), " pubblicazione ")]'):
            el.drop_tree()   # the original text's page adds its Bollettino line; the others do not
        heading = ' '.join(lines(head))
    ann = fragment(s, 'id="doc_tes_annessi"', 'id="doc_piede"')
    annex = [R.clean_line(a.text_content()) for a in ann.iter('a') if 'download.php' in (a.get('href') or '')] \
        if ann is not None else []
    kind = re.search(r'class="NIR_Tipodocumento">([^<]*)<', s)
    return {'mods': mods, 'heading': heading, 'annex': annex, 'kind': kind.group(1).strip() if kind else ''}


LABEL = re.compile(r'^L\.R\.\s+(\d{1,2})°?\s+(' + '|'.join(E.MONTHS) + r')\s+(\d{4}),?\s+n\.\s*(\d+)$', re.I)


def label_law(text: str):
    """A law named only by its label in an amendment note ("L.R. 14 aprile 1975 n. 21"): the same URN match
    it_emilia_romagna.law_of() takes."""
    m = LABEL.match(text)
    if not m:
        return None
    d, mo, y, n = int(m[1]), E.MONTHS.index(m[2].lower()) + 1, m[3], int(m[4])
    return E.URN.search(f'urn:nir:regione.emilia.romagna:legge:{y}-{mo:02d}-{d:02d};{n}')


def fold(t: str) -> str:
    """Letters and digits only, without accents or case: old pages print a title as "SOCIETA'" or in lower case
    where the current one has "SOCIETÀ", and "06 luglio" where it has "6 luglio"."""
    return re.sub(r'[^a-z0-9]', '', re.sub(r'\b0+(\d)', r'\1', R.ascii_slug(t)))


def line_key(ln: str) -> str:
    """Two lines are the same line when their letters and digits are (or, without any, their non-space marks)."""
    return R.letters(ln) or ('\x00' + sq(ln))


def sq(t: str) -> str:
    return re.sub(r'\s+', '', t)


def sq_lines(t: str) -> list[str]:
    return [sq(x) for x in t.split(NL)]


ABROG = re.compile(r'^(abrogat[oaie]\.?) (\d+(?: ?[a-z]+)?\.)$')


def abrog_order(t: str) -> str:
    """Some of Demetra's open-data files store a repealed paragraph with its text before its number ("abrogato. 2.");
    its pages print "2. abrogato.". Used only to compare the two, never to write text."""
    return NL.join(ABROG.sub(r'\2 \1', x) for x in t.split(NL))


def compare(verbose=False):
    ok = bad = miss = spaces = 0
    for _, a in amended_acts():
        raw = cached(a['url'])
        if raw is None:
            miss += 1
            continue
        mine, cur = parse_page(raw), a['versions'][-1]['units']
        ck = [k for k in cur if k not in CARRIED]
        probs = [] if ck == list(mine) else [f'keys differ: {[k for k in ck if k not in mine][:5]} / '
                                             f'{[k for k in mine if k not in ck][:5]}']
        for k in ck:
            if k in mine and mine[k]['text'] != cur[k]['text']:
                if sq_lines(mine[k]['text']) == sq_lines(cur[k]['text']):
                    spaces += 1
                else:
                    probs.append(k)
        if probs:
            bad += 1
            if verbose:
                print(a['slug'], probs[:6])
        else:
            ok += 1
    print(f'current pages read the same as the NIR units (lines equal up to spaces): {ok}; differ: {bad}; '
          f'not fetched: {miss}; units equal only up to spaces: {spaces}')


# ---------------------------------------------------------------- in-force days

MONTHS = E.MONTHS
VERB = r'(?:entra|entrer[àa]|entrano|entreranno)\s+in\s+vigore'
SUBJ = re.compile(r'(?i)\b(?:la\s+presente\s+legge|la\s+legge\s+medesima|essa|il\s+(?:nuovo|presente)\s+statuto)\b')
ORD = {'quindicesimo': 15, 'decimoquinto': 15, 'trentesimo': 30, 'decimo': 10, 'ventesimo': 20, 'sessantesimo': 60}
ORD_EN = {15: 'fifteenth', 30: 'thirtieth', 10: 'tenth', 20: 'twentieth', 60: 'sixtieth'}


def _long(d: dt.date) -> str:
    return R._long(d.isoformat())


def plus_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def term(s: str, pub: dt.date):
    s = s.lower()
    m = re.search(r"\b(?:il|l'|dal|dall')\s*(?:giorno\s+)?(primo|\d{1,2})\s*°?\s*(" + '|'.join(MONTHS) + r')\s+(\d{4})', s)
    if m:
        day = 1 if m[1] == 'primo' else int(m[1])
        try:
            return dt.date(int(m[3]), MONTHS.index(m[2]) + 1, day), 'on the day its own entry-into-force clause names'
        except ValueError:
            return None
    m = re.search(r'\b(' + '|'.join(ORD) + r')\s+giorno', s)
    if m:
        n = ORD[m[1]]
        return pub + dt.timedelta(days=n), f'on the {ORD_EN[n]} day after publication, as its own entry-into-force clause provides'
    if re.search(r'giorno\s+successivo', s):
        return pub + dt.timedelta(days=1), 'on the day after publication, as its own entry-into-force clause provides'
    if re.search(r'giorno\s+stesso|stesso\s+giorno|giorno\s+della\s+(?:sua\s+)?pubblicazione|'
                 r'(?:dalla|alla)\s+data\s+(?:della\s+sua\s+|di\s+)?pubblicazione', s):
        return pub, 'on the day of publication, as its own entry-into-force clause provides'
    m = re.search(r'\b(sei|tre|due|un)\s+mes[ei]\s+dopo', s)
    if m:
        n = {'sei': 6, 'tre': 3, 'due': 2, 'un': 1}[m[1]]
        return plus_months(pub, n), f'{n} month{"s" if n > 1 else ""} after publication, as its own entry-into-force clause provides'
    return None


def clause(text: str, pub: dt.date):
    """(day, how) from the law's own entry-into-force clause ("La presente legge entra in vigore ..."), 'none' when
    it has none, or 'unclear'."""
    found = []
    for sent in re.split(r'(?<=[.;:])\s', re.sub(r'\s+', ' ', text)):
        if not re.search(VERB, sent, re.I):
            continue
        head, rest = re.split(VERB, sent, maxsplit=1, flags=re.I)
        if SUBJ.search(head):
            found.append(term(rest[:200], pub))
    if not found:
        return 'none'
    if any(f is None for f in found) or len({f[0] for f in found}) > 1:
        return 'unclear'
    return found[0]


def rule_text(pub: dt.date) -> str:
    if pub >= dt.date(2005, 4, 1):
        return 'the fifteenth day after publication: the law sets no other term (Statuto, art. 55, comma 1)'
    return ('the fifteenth day after publication: the law sets no other term (the general rule of the disposizioni '
            'preliminari al codice civile, art. 10, which the Statuto of 2005, art. 55, keeps)')


def nir_text(x: str) -> str:
    """A NIR file's own words, without editor's notes and without text it quotes into other laws."""
    body = x[x.find('</meta>') + 7:]
    body = re.sub(r'(?s)<!--.*?-->|<ndr\b[^>]*/>|<ndr\b[^>]*>.*?</ndr>|<virgolette\b.*?</virgolette>', ' ', body)
    return html.unescape(re.sub(r'<[^>]+>', ' ', body))


def page_text(raw: bytes) -> str:
    s = raw.decode('utf-8', 'replace')
    body = fragment(s, 'id="doc_tes_contenuto"', body_end(s))
    if body is None:
        return ''
    for el in body.xpath('.//*[contains(concat(" ", @class, " "), " ndr ") or contains(@class, "virgolette")]'):
        el.drop_tree()
    return body.text_content()


_LAWS: dict | None = None


def law_index() -> dict:
    """Every law file in the open-data zips, by key (lr-<year>-<number>): (tipo, text, published, vigenza, title)."""
    global _LAWS
    if _LAWS is not None:
        return _LAWS
    best: dict[str, tuple] = {}
    for leg, z in E.zips().items():
        for name in z.namelist():
            if not name.endswith('.xml'):
                continue
            raw = z.read(name)
            try:
                x = raw.decode('utf-8')
            except UnicodeDecodeError:
                x = raw.decode('latin-1')
            mu = re.search(r'<urn>(.*?)</urn>', x)
            m = E.URN.search(mu.group(1)) if mu else None
            if not m or m.group(1) != 'legge':
                continue
            key = f'lr-{m.group(2)}-{int(m.group(5))}'
            rank = (name.endswith(f'_LR_{m.group(2)}_{int(m.group(5))}.xml'), leg)
            if key in best and best[key][0] >= rank:
                continue
            tipo = (re.search(r'<NIR[^>]*tipo="(\w+)"', x) or [None, '?'])[1]
            vig = E.nir_date((re.search(r'<vigenza[^>]*inizio="(\d*)"', x) or [None, ''])[1])
            pub = E.nir_date((re.search(r'<pubblicazione[^>]*norm="(\d*)"', x) or [None, ''])[1])
            root_title = re.search(r'(?s)<titoloDoc[^>]*>(.*?)</titoloDoc>', x)
            title = R.clean_line(WS.sub(' ', html.unescape(re.sub(r'<[^>]+>', ' ', root_title.group(1))))) \
                if root_title else ''
            best[key] = (rank, {'tipo': tipo, 'x': x, 'pub': pub, 'vig': vig, 'title': title,
                                'source': E.ZIP.format(leg=leg) + '#' + name})
    _LAWS = {k: v for k, (_, v) in best.items()}
    return _LAWS


def law_in_force(key: str, pub: dt.date) -> tuple[dt.date | None, str]:
    """The in-force day of a law published on `pub` (the date Demetra's storia tab gives), and how it was found."""
    info = law_index().get(key)
    if info is None:
        return pub + dt.timedelta(days=15), (rule_text(pub) + "; the law's own text is not in Demetra's open data")
    c = clause(nir_text(info['x']), pub)
    if isinstance(c, tuple):
        return c
    if info['tipo'] == 'originale' and info['vig'] and info['pub'] == pub.isoformat():
        return dt.date.fromisoformat(info['vig']), 'the start of validity Demetra records for its text'
    if c == 'none':
        return pub + dt.timedelta(days=15), rule_text(pub)
    return None, 'its entry-into-force clause could not be read'


def check_inforce():
    res, rows = Counter(), []
    for key, info in sorted(law_index().items()):
        if info['tipo'] != 'originale' or not (info['vig'] and info['pub']):
            continue
        pub = dt.date.fromisoformat(info['pub'])
        c = clause(nir_text(info['x']), pub)
        d = c[0] if isinstance(c, tuple) else pub + dt.timedelta(days=15) if c == 'none' else None
        how = 'clause' if isinstance(c, tuple) else c
        same = d is not None and d.isoformat() == info['vig']
        res[f'{how} {"agrees" if same else "differs"}'] += 1
        if not same:
            rows.append((key, info['pub'], info['vig'], d and d.isoformat(), how))
    print(dict(res))
    for r in rows:
        print(' ', r)
    return res


# ---------------------------------------------------------------- building the history of one act

class Skip(Exception):
    pass


def mod_keys(meta: dict, laws_out: dict) -> list[str]:
    """The keys of the laws a page's amendment note names (in its order), each law's base entry kept in laws_out."""
    out = []
    for m in meta['mods']:
        k, law = E.law_of(m)
        laws_out.setdefault(k, {}).setdefault('base', law)
        if k not in out:
            out.append(k)
    return out


def build_history(act: dict, laws_out: dict) -> tuple[dict, dict]:
    """The act with its earlier versions before the current one, or raises Skip(reason)."""
    cur_v = act['versions'][-1]
    if len(act['versions']) != 1:
        raise Skip('already has more than one version')
    st_raw, cur_raw = cached(storia_url(act['url'])), cached(act['url'])
    if st_raw is None or cur_raw is None:
        raise Skip('storia tab or current page not fetched')
    st = storia_rows(st_raw)
    rows = earlier_rows(st)
    if not rows:
        raise Skip('Demetra lists no earlier version')
    url, member = cur_v['source_url'].split('#', 1)
    zx = law_index_member(url, member)
    zpub = E.nir_date((re.search(r'<pubblicazione[^>]*norm="(\d*)"', zx) or [None, ''])[1])
    if st['current_pub'] != zpub:
        raise Skip(f'the storia tab\'s current text (published {st["current_pub"]}) is not the open-data file\'s '
                   f'({zpub})')
    X = cur_v['units']
    Hc = parse_page(cur_raw)
    if [k for k in X if k not in CARRIED] != list(Hc):
        raise Skip('the current page does not read into the same units as the open-data file')
    meta_c = page_meta(cur_raw)
    if any(isinstance(m, str) for m in meta_c['mods']):
        raise Skip(f'the current text names a change that is not a regional law: {meta_c["mods"]}')
    proven = {k for k in Hc if k in X and sq_lines(Hc[k]['text']) == sq_lines(abrog_order(X[k]['text']))}

    pages = []
    for r in rows:
        raw = cached(r['url'])
        if raw is None:
            raise Skip(f'version page not fetched: {r["url"]}')
        meta = page_meta(raw)
        if 'vigente' in meta['kind'].lower():
            raise Skip(f'version page is not a "Documento storico": {meta["kind"]!r}')
        if any(isinstance(m, str) for m in meta['mods']):
            raise Skip(f'a version names a change that is not a regional law: {meta["mods"]}')
        if fold(meta['heading']) != fold(meta_c['heading']):
            raise Skip('the heading or title differs between versions')
        if 'allegati' in X and [sq(a) for a in meta['annex']] != [sq(a) for a in meta_c['annex']]:
            raise Skip('the annexes differ between versions')
        pages.append((r, raw, meta, parse_page(raw)))

    # texts, newest first: an earlier unit with the same letters and digits as the later one takes the later text;
    # one that changed takes the page's own lines, each line with the same letters and digits as a line of the later
    # text taking that line (Demetra re-typed old texts: "Emilia - Romagna" / "Emilia-Romagna", "LR" / "L.R.").
    later_T, later_H = X, Hc
    texts = []
    for r, raw, meta, H in reversed(pages):
        T = {}
        if 'intestazione' in X:
            T['intestazione'] = X['intestazione']
        for k, u in H.items():
            if k not in X and k not in Hc and k == 'preambolo':
                continue   # the enacting formula, which the current text does not print: not a change of the law
            lt = later_T.get(k)
            if lt is not None and k in later_H and R.letters(u['text']) == R.letters(later_H[k]['text']):
                T[k] = lt
                continue
            if lt is not None:
                by = {}
                for ln in lt['text'].split(NL)[:-1]:
                    by.setdefault(line_key(abrog_order(ln)), ln)
                txt = NL.join(by.get(line_key(ln), ln) for ln in u['text'].split(NL)[:-1]) + NL
            else:
                txt = u['text']
            T[k] = {'label': u['label'], 'kind': u['kind'], 'text': txt} if lt is None or txt != lt['text'] else lt
            if T[k] is not lt and k in X and k not in proven:
                raise Skip(f'{k} changed, and the current page does not read {k} as the open-data file does')
            if T[k] is not lt and k not in X and k in Hc:
                raise Skip(f'{k}: unit keys do not line up')
        for k in ('formula-finale', 'allegati'):
            if k in X:
                T[k] = X[k]
        texts.append(T)
        later_T, later_H = T, H
    texts.reverse()

    # laws and days
    own = f'lr-{act["url"].rsplit(":", 1)[1].replace(";", "-")}'
    first = pages[0][0]
    versions = []
    prev_mods: list[str] = []
    for i, ((r, raw, meta, H), T) in enumerate(zip(pages, texts)):
        mods = mod_keys(meta, laws_out)
        pub = dt.date.fromisoformat(r['date'])
        v = {'from': None, 'source_url': r['url'], 'sha256': hashlib.sha256(raw).hexdigest(), 'units': T}
        if i == 0 and r['kind'] == 'originale':
            if mods:
                raise Skip('the original text names amending laws')
            laws_out.setdefault(own, {}).setdefault('base', own_law(act))
            check_pub(own, pub, laws_out)
            c = clause(page_text(raw), pub)
            if c == 'unclear':
                raise Skip('the law\'s own entry-into-force clause could not be read')
            day, how = c if isinstance(c, tuple) else (pub + dt.timedelta(days=15), rule_text(pub))
            v['credits'] = {k: [own] for k in T}
            v['note'] = (f'Published in the Bollettino Ufficiale on {_long(pub)} (the date Demetra gives); in force '
                         f'from {_long(day)}, {how}. Text: Demetra\'s "Testo originale" (storia tab).')
            main = own
        else:
            if i == 0:
                raise Skip('Demetra lists no original text')
            new = [m for m in mods if m not in prev_mods]
            if not new or any(m not in mods for m in prev_mods):
                raise Skip(f'version of {r["date"]}: the list of amending laws does not grow by one or more laws')
            main = main_law(new, laws_out)
            check_pub(main, pub, laws_out)
            day, how = law_in_force(main, pub)
            if day is None:
                raise Skip(f'{main}: {how}')
            v['credits'] = changed_credits(versions[-1]['units'], T, new)
            label = laws_out[main]['base']['label']
            v['note'] = (f'{label} was published in the Bollettino Ufficiale on {_long(pub)} (the date Demetra '
                         f'gives); in force from {_long(day)}, {how}. Text: Demetra\'s "Testo Coordinato" (storia '
                         f'tab).')
        if day.isoformat() < enacted_of(main, laws_out):
            raise Skip(f'version of {r["date"]}: in force ({day}) before its law was enacted')
        v['from'] = day.isoformat()
        versions.append(v)
        prev_mods = mods
    # the current version: the laws its note adds; it keeps the day Demetra gives for it
    mods = mod_keys(meta_c, laws_out)
    new = [m for m in mods if m not in prev_mods]
    if not new or any(m not in mods for m in prev_mods):
        raise Skip('the current text\'s list of amending laws does not grow by one or more laws')
    main = main_law(new, laws_out)
    check_pub(main, dt.date.fromisoformat(st['current_pub']), laws_out)
    if cur_v['from'] < enacted_of(main, laws_out):
        raise Skip(f'the current text\'s day ({cur_v["from"]}) is before its latest law was enacted')
    cur = dict(cur_v)
    cur['credits'] = changed_credits(versions[-1]['units'], X, new)
    versions.append(cur)
    days = [v['from'] for v in versions]
    for a_, b_ in zip(days, days[1:]):
        if b_ < a_:
            raise Skip(f'in-force days go backwards ({a_} then {b_})')
    for i in range(1, len(versions)):
        gone = [k for k in versions[i - 1]['units'] if k not in versions[i]['units']]
        for k in gone:
            t = versions[i - 1]['units'][k]['text']
            if not (re.search(r'(?i)\babrogat', t) and len(t) < 300):
                raise Skip(f'{k} disappears from the version of {versions[i]["from"]} without having been repealed '
                           f'before (Demetra no longer prints it)')
        if versions[i]['from'] == versions[i - 1]['from']:
            versions[i]['same_day'] = True
    new_act = dict(act, first_law=own if first['kind'] == 'originale' else None, earlier_laws=[],
                   versions=versions)
    return new_act, {'versions': len(versions), 'own': own}


_MEMBERS: dict = {}


def law_index_member(url: str, member: str) -> str:
    """One file of a cached open-data zip, as text."""
    if url not in _MEMBERS:
        _MEMBERS[url] = zipfile.ZipFile(io.BytesIO(it_fetch.get(url)))
    raw = _MEMBERS[url].read(member)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def changed_credits(prev: dict, cur: dict, laws: list[str]) -> dict:
    """Credits for the units whose text changed (inserted, changed or removed): every law the version adds."""
    keys = [k for k in list(prev) + [k for k in cur if k not in prev]
            if prev.get(k, {}).get('text') != cur.get(k, {}).get('text')]
    return {k: list(laws) for k in keys}


PUB_CAND: dict[str, set] = {}          # pass 1: every publication day Demetra gives for a law, across all acts
PUB_OK: dict[str, str] | None = None   # pass 2: the one accepted day per law


def own_law(act: dict) -> dict:
    """The act's own law entry, as it_emilia_romagna.law_of() writes it (from the act's title)."""
    m = re.match(r'L\.R\. (\d+) (\w+) (\d{4}), n\. (\d+)', act['title']) or \
        re.search(r'L\.R\. (\d+) (\w+) (\d{4}), n\. (\d+)', act['title'])
    if not m:
        raise Skip('no date for the act\'s own law in its title')
    d, mo, y, n = int(m[1]), E.MONTHS.index(m[2]) + 1, m[3], int(m[4])
    return E.law_of(E.URN.search(f'urn:nir:regione.emilia.romagna:legge:{y}-{mo:02d}-{d:02d};{n}'))[1]


def enacted_of(key: str, laws_out: dict) -> str:
    base = laws_out.get(key, {}).get('base') or {}
    return base.get('enacted') or key.split('-')[1]


def main_law(new: list[str], laws_out: dict) -> str:
    """Of the laws a version adds, the latest (by date and number): the version takes effect when it does."""
    return max(new, key=lambda k: (enacted_of(k, laws_out), int(k.split('-')[2])))


def check_pub(key: str, pub: dt.date, laws_out: dict):
    """Pass 1 collects; pass 2 needs the one day accepted for the law (see resolve_pubs)."""
    if PUB_OK is None:
        PUB_CAND.setdefault(key, set()).add(pub.isoformat())
        return
    if PUB_OK.get(key) != pub.isoformat():
        raise Skip(f'{key}: no single plausible publication day in Demetra ({sorted(PUB_CAND.get(key, []))})')
    laws_out.setdefault(key, {})['published'] = pub.isoformat()


def resolve_pubs(laws_seen: dict) -> tuple[dict, dict]:
    """A law's publication day is one the storia tabs give for it that is not before the law's own date nor more than
    60 days after it; when the tabs give several, only if exactly one is plausible (the versions labelled with the
    others are then left out). It must also be the day the law's own open-data file gives when that file is the
    original text and its day is itself plausible."""
    ok, bad = {}, {}
    idx = law_index()
    for k, days in PUB_CAND.items():
        enacted = (laws_seen.get(k, {}).get('base') or {}).get('enacted')
        if not enacted:
            bad[k] = 'no date for the law'
            continue
        last = (dt.date.fromisoformat(enacted) + dt.timedelta(days=60)).isoformat()
        good = sorted(d for d in days if enacted <= d <= last)
        own = idx.get(k, {})
        own_pub = own.get('pub') if own.get('tipo') == 'originale' and own.get('pub') and             enacted <= own['pub'] <= last else None
        if len(good) != 1:
            bad[k] = f'storia tabs give {sorted(days)}, of which {len(good)} within 60 days after the law\'s date {enacted}'
        elif own_pub and own_pub != good[0]:
            bad[k] = f'{good[0]}, but its open-data file says {own_pub}'
        else:
            ok[k] = good[0]
    return ok, bad


# ---------------------------------------------------------------- staging the parts

def merge_laws(into: dict, new: dict):
    for k, rec in new.items():
        have = into.setdefault(k, {})
        for f in ('published', 'note', 'day'):
            if rec.get(f) and have.get(f) and rec[f] != have[f]:
                raise Skip(f'{k}: {f} differs between acts ({have[f]} / {rec[f]})')
        for f, v in rec.items():
            if v is not None:
                have.setdefault(f, v)


def stage(only: list[str] | None = None):
    parts = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted((FOLDER / 'corpus.d').glob('*.json'))}
    canon: dict[str, dict] = {}
    for name, pj in parts.items():
        for k, law in pj['laws'].items():
            canon.setdefault(k, dict(law))
    global PUB_OK
    PUB_OK = None
    PUB_CAND.clear()
    seen: dict[str, dict] = {}
    for name, pj in parts.items():          # pass 1: the publication days Demetra gives
        for a in pj['acts']:
            if not a.get('first_law'):
                try:
                    build_history(a, seen)
                except Skip:
                    pass
    PUB_OK, bad_pubs = resolve_pubs(seen)
    laws_out: dict[str, dict] = {}
    report = {'acts': {}, 'skipped': {}, 'publication_days_rejected': bad_pubs}
    new_acts: dict[str, dict] = {}
    for name, pj in parts.items():
        for a in pj['acts']:
            if a.get('first_law'):
                continue
            local: dict[str, dict] = {}
            try:
                na, info = build_history(a, local)
                pr = check_act(na)
                if pr:
                    raise Skip('letters check against the version pages: ' + pr[0])
                trial = json.loads(json.dumps(laws_out))
                merge_laws(trial, local)
                laws_out = trial
                new_acts[a['slug']] = na
                report['acts'][a['slug']] = {'part': name, 'versions': len(na['versions']),
                                             'days': [v['from'] for v in na['versions']]}
            except Skip as e:
                report['skipped'][a['slug']] = {'part': name, 'why': str(e)}
    # law entries: the existing ones (labels unchanged), with the publication day, title and in-force note found here
    idx = law_index()
    for k, rec in laws_out.items():
        law = canon.get(k) or dict(rec.get('base') or {})
        if not law:
            continue
        if rec.get('published'):
            law['published'] = rec['published']
        if (not law.get('title') or law['title'] == law['label']) and idx.get(k, {}).get('title'):
            law['title'] = idx[k]['title'][:300]
        canon[k] = law
    STAGE.mkdir(exist_ok=True)
    src_country = R.country_block(SLUG, E.SRC)
    for name, pj in parts.items():
        if only and name not in only:
            continue
        out = dict(pj)
        out['country'] = src_country
        out['acts'] = [new_acts.get(a['slug'], a) for a in pj['acts']]
        refs = set(pj['laws'])
        for a in out['acts']:
            if a.get('first_law'):
                refs.add(a['first_law'])
            refs.update(a.get('earlier_laws', []))
            for v in a['versions']:
                for ls in v.get('credits', {}).values():
                    refs.update(ls)
        missing = [k for k in refs if k not in canon]
        if missing:
            raise SystemExit(f'{name}: laws without an entry: {missing[:5]}')
        out['laws'] = {k: canon[k] for k in sorted(refs)}
        if name == '10-statuto':
            out['sources'] = [R.source_block(E.SRC, E.DOCS_DATE)]
            out['decisions'] = E.decisions()
            out['ai_use'] = E.AI_USE
        tmp = STAGE / f'{name}.tmp'
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1) + NL, encoding='utf-8', newline='\n')
        os.replace(tmp, STAGE / f'{name}.json')
    report['counts'] = {'with_history': len(report['acts']), 'current_only': len(report['skipped']),
                        'versions_added': sum(r['versions'] - 1 for r in report['acts'].values())}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + NL, encoding='utf-8', newline='\n')
    why = Counter(re.sub(r'\d{4}-\d\d-\d\d|lr-\d+-\d+|\bart-[\w-]+|[\'"].*', '#', s['why'])[:90]
                  for s in report['skipped'].values())
    print(json.dumps(report['counts']), flush=True)
    for w, n in why.most_common(25):
        print(f'  {n:4d}  {w}')


# ---------------------------------------------------------------- the independent check of an earlier version

def page_letters(raw: bytes, with_formula: bool = True) -> tuple[str, str, str]:
    """A second reader, sharing nothing with parse_page(): lxml's text_content() of the enacting formula (unless the
    version has none: the current text does not print it) and the body of the page (notes removed), of its heading
    (notes removed) and of its annex titles."""
    s = raw.decode('utf-8', 'replace')
    i = s.find('id="doc_tes_formulaIniziale"') if with_formula else -1
    if i < 0:
        i = s.find('id="doc_tes_contenuto"')
    end = re.search(r'id="doc_tes_formulaFinale"|id="doc_tes_annessi"|id="doc_piede"', s[i:])
    doc = lxml.html.fromstring('<div>' + s[s.rfind('<', 0, i):s.rfind('<', 0, i + end.start())] + '</div>')
    for el in doc.xpath('//*[contains(@class, "ndr")]'):
        el.drop_tree()
    body = R.letters(html.unescape(doc.text_content()))
    h0 = s.find('id="doc_tes_intestazione"')
    h1 = s.find('id="doc_cor_', h0)
    hd = lxml.html.fromstring('<div>' + s[s.rfind('<', 0, h0):s.rfind('<', 0, h1)] + '</div>')
    for el in hd.xpath('//*[contains(@class, "ndr") or contains(@class, "lex_ind") or contains(@class, "pubblicazione")]'):
        el.drop_tree()
    a0 = s.find('id="doc_tes_annessi"')
    ann = ''
    if a0 >= 0:
        ad = lxml.html.fromstring('<div>' + s[s.rfind('<', 0, a0):s.rfind('<', 0, s.find('id="doc_piede"', a0))]
                                  + '</div>')
        ann = R.letters(' '.join(a.text_content() for a in ad.xpath('//a[contains(@href, "download.php")]')))
    return body, fold(hd.text_content()), ann


def check_act(act: dict) -> list[str]:
    """The earlier versions of one act against their cached Demetra pages, read by page_letters()."""
    probs = []
    if len(act['versions']) == 1:
        return probs
    cur = act['versions'][-1]
    _, head_c, ann_c = page_letters(cached(act['url']))
    for v in act['versions'][:-1]:
        raw = cached(v['source_url'])
        if raw is None or hashlib.sha256(raw).hexdigest() != v['sha256']:
            probs.append(f'{act["slug"]}: {v["from"]} page missing or sha256 differs')
            continue
        body, head, ann = page_letters(raw, with_formula='preambolo' in v['units'])
        if head != head_c:
            probs.append(f'{act["slug"]}: {v["from"]} heading differs from the current page')
        for k in CARRIED:
            if (k in v['units']) != (k in cur['units']) or (k in cur['units'] and v['units'][k] != cur['units'][k]):
                probs.append(f'{act["slug"]}: {v["from"]} {k} is not the current text\'s')
        if 'allegati' in v['units'] and ann != ann_c:
            probs.append(f'{act["slug"]}: {v["from"]} annex titles differ from the current page')
        mine = [(k, u['text']) for k, u in v['units'].items() if k not in CARRIED]
        whole = ''.join(R.letters(t) for _, t in mine)
        if Counter(body) != Counter(whole):
            ca, cb = Counter(body), Counter(whole)
            probs.append(f'{act["slug"]}: {v["from"]} source-only {dict((ca - cb).most_common(5))} '
                         f'corpus-only {dict((cb - ca).most_common(5))}')
            continue
        pos = 0
        for k, t in mine:
            for lu in (R.letters(t), R.letters(abrog_order(t))):
                i = body.find(lu, pos)
                if i >= 0:
                    break
            if i < 0:
                probs.append(f'{act["slug"]}: {v["from"]} {k} not found in order')
                break
            pos = i + len(lu)
    return probs


def letters_check(slug: str, part_name: str, path: Path | None = None) -> list[str]:
    """Every version: the current one by it_emilia_romagna.letters_check's reader of the open-data file, each earlier
    one by check_act(): its letters and digits against lxml's text of its cached Demetra page, each unit in order. The
    heading, closing formula and annex titles of an earlier version are the current version's (Demetra's version
    pages do not print the closing formula): they must be the current text's exactly, and the page's heading and
    annex titles must be the current page's. A repealed paragraph the open-data file stores as "abrogato. 2." may be
    found as the page's "2. abrogato." (same letters, order of the two words only)."""
    p = path or (R.folder(slug) / 'corpus.d' / f'{part_name}.json')
    part = json.loads(p.read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        probs += check_act(act)
    # the current versions, by the open-data reader
    tmpd = STAGE / '.letters'
    tmpd.mkdir(parents=True, exist_ok=True)
    tp = tmpd / f'{part_name}.json'
    tp.write_text(json.dumps({'acts': [dict(a, versions=a['versions'][-1:]) for a in part['acts']]},
                             ensure_ascii=False), encoding='utf-8')
    probs += E.letters_check(slug, part_name, path=tp)
    return probs


# ---------------------------------------------------------------- verify staged parts with one scratch build, swap

def swap(names: list[str], dry: bool = False) -> str:
    d = FOLDER / 'corpus.d'
    for n in names:
        if not (STAGE / f'{n}.json').exists():
            return f'{n}: not staged'
    bad = {}
    for n in names:
        pr = letters_check(SLUG, n, path=STAGE / f'{n}.json')
        if pr:
            bad[n] = pr
    if bad:
        for n, pr in bad.items():
            R.progress(SLUG, f'{n} (history): NOT VERIFIED letters check: {len(pr)} problems: {pr[0]}'[:600])
        return 'NOT VERIFIED letters: ' + json.dumps({n: pr[:3] for n, pr in bad.items()}, ensure_ascii=False)[:1500]
    R.wait_cpu()
    tmp, build = R.DOCS / f'{R.repo_name(SLUG)}-verify', R.DOCS / f'{R.repo_name(SLUG)}-verifybuild'
    for x in (tmp, build):
        R._rm(x)
    (tmp / 'corpus.d').mkdir(parents=True)
    have = [q.stem for q in sorted(d.glob('*.json')) if q.with_suffix('.PUBLISH').exists()]
    for n in sorted(set(have) | set(names)):
        shutil.copy2(STAGE / f'{n}.json' if n in names else d / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
        (tmp / 'corpus.d' / f'{n}.PUBLISH').write_text('scratch\n', encoding='utf-8')
    real_folder = R.folder
    R.folder = lambda slug: tmp    # the scratch build's docs read the scratch parts
    try:
        R.write_docs(SLUG, E.SRC, E.DOCS_DATE, out=tmp / 'repo')
    finally:
        R.folder = real_folder
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = R._low([sys.executable, '-X', 'utf8', str(R.ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo',
                str(build), '--docs-date', E.DOCS_DATE], env=env)
    if b.returncode:
        msg = 'build failed: ' + (b.stderr or b.stdout)[-600:]
        R.progress(SLUG, f'{names[0]}..{names[-1]} (history): NOT VERIFIED {msg}'[:700])
        return 'NOT VERIFIED ' + msg
    c = R._low([sys.executable, '-X', 'utf8', str(R.ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return 'NOT VERIFIED check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if c.returncode or any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards',
                                                'future_dated', 'missing_in_force')):
        msg = 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:400] + \
            json.dumps(res.get('details', [])[:3], ensure_ascii=False)[:400]
        R.progress(SLUG, f'{names[0]}..{names[-1]} (history): NOT VERIFIED {msg}'[:700])
        return 'NOT VERIFIED ' + msg
    if dry:
        return f'DRY RUN clean: check.py {res.get("versions")} versions, scratch build in {build}'
    # verified: replace each part, its PUBLISH line last (the old PUBLISH stays in place until then)
    for n in names:
        pj = json.loads((STAGE / f'{n}.json').read_text(encoding='utf-8'))
        acts = pj['acts']
        nv = sum(len(a['versions']) for a in acts)
        nh = sum(1 for a in acts if len(a['versions']) > 1)
        days = sorted(v['from'] for a in acts for v in a['versions'])
        line = (f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} ({nh} with earlier versions from Demetra\'s '
                f'storia pages) from {E.SRC["short"]}: letters and digits of every version equal the source text '
                f'(independent readers: the open-data XML for current texts, lxml text of the cached version page for '
                f'earlier ones) and every unit is found in order; scratch build of verified parts + parts '
                f'{names[0]}..{names[-1]}: check.py {res.get("versions")} versions, 0 mismatches, 0 trailer errors, '
                f'0 merges ({E.DOCS_DATE}; history rebuild {R.now()}).')
        os.replace(STAGE / f'{n}.json', d / f'{n}.json')
        ptmp = d / f'{n}.ptmp'
        ptmp.write_text(line + NL, encoding='utf-8', newline='\n')
        os.replace(ptmp, d / f'{n}.PUBLISH')
        R.progress(SLUG, f'{n}: PUBLISH (history rebuild) {line}')
    R.write_docs(SLUG, E.SRC, E.DOCS_DATE)
    R._rm(tmp)
    R._rm(build)
    return f'PUBLISH {len(names)} parts ({names[0]}..{names[-1]}), check.py {res.get("versions")} versions clean'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd = sys.argv[1]
    if cmd == 'fetch':
        smp = int(sys.argv[sys.argv.index('--sample') + 1]) if '--sample' in sys.argv else None
        try:
            fetch(smp)
        except it_fetch.Stopped as e:
            log('STOPPED', e)
    elif cmd == 'compare':
        compare('-v' in sys.argv)
    elif cmd == 'inforce':
        check_inforce()
    elif cmd == 'stage':
        stage(sys.argv[2:] or None)
    elif cmd == 'letters':
        pr = letters_check(SLUG, sys.argv[2], path=STAGE / f'{sys.argv[2]}.json')
        print('\n'.join(pr[:40]) or 'clean', len(pr))
    elif cmd == 'swap':
        names = [a for a in sys.argv[2:] if not a.startswith('--')]
        print(swap(names, dry='--dry' in sys.argv))
