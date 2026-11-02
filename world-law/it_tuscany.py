"""Tuscany (italy-tuscany-law) for git-for-law, gitlaw-scraper-dell, 2026-10-30. Private (world-law-ops).

Source: Consiglio regionale della Toscana, Raccolta normativa (raccoltanormativa.consiglio.regione.toscana.it), open
data "Scarica i dati" (CC BY 3.0): one zip per legislature with the current coordinated text of every regional law in
Akoma Ntoso; the Statute's own Akoma Ntoso file from its page. The site's multivigenza (from 2005) is a set of PDFs,
so this build is current-only.

    python -X utf8 scripts/world-law/it_tuscany.py fetch
    python -X utf8 scripts/world-law/it_tuscany.py parse <docs-date>
    python -X utf8 scripts/world-law/it_tuscany.py publish <docs-date> [part ...]
    python -X utf8 scripts/world-law/it_tuscany.py letters <part>
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.dom import minidom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'tuscany'
BASE = 'https://raccoltanormativa.consiglio.regione.toscana.it/'
STATUTO_PAGE = BASE + 'articolo?urndoc=urn:nir:regione.toscana:legge:2005-02-11;'
LEGISLATURES = range(1, 11)
PART_SIZE = 50


def bulk_url(leg: int) -> str:
    return f'{BASE}class/download.php?type=zip&formato=akm&tipo=legge&metaleg={leg}'


REFRESH_DATE = '2026-10-30'     # the day every law's page was read again (one docs date for the whole refresh)
_REFRESH_LONG = '30 October 2026'
OPEN_DATA_LONG = 'January 2022'

SRC = {
    'host': 'raccoltanormativa.consiglio.regione.toscana.it',
    'publisher': 'Consiglio regionale della Toscana, Raccolta normativa della Regione Toscana',
    'short': 'the Raccolta normativa of the Consiglio regionale della Toscana',
    'url': BASE,
    'licence': 'Open data "Scarica i dati": Creative Commons Attribution 3.0 (CC BY 3.0); site copyright page: '
               '"I documenti, invece, sono liberamente utilizzabili a condizione che ne sia citata la fonte." '
               'L. 633/1941 art. 5: official acts are not protected.',
    'licence_note': 'Fonte: Consiglio regionale della Toscana, Raccolta normativa della Regione Toscana, '
                    'https://raccoltanormativa.consiglio.regione.toscana.it/ (CC BY 3.0)',
    'source_notes': 'Akoma Ntoso open-data zips of the coordinated text of every regional law (legislatures I-X, '
                    '1970-2020; last updated January 2022), the current Akoma Ntoso file linked from each law\'s page '
                    '(read on the retrieval day) for the laws amended since and the laws of 2020 on, and the Statute\'s '
                    'Akoma Ntoso file; current texts only (the site\'s dated past versions are PDF files, not included).',
    'in_force_rule': 'Statuto della Regione Toscana, art. 43: a law enters into force on the fifteenth day after its '
                     'publication in the Bollettino Ufficiale della Regione Toscana, unless it states otherwise. '
                     '(Not applied here: every text is the current one, dated the retrieval day.)',
    'history': 'current-only',
    'history_note': ' in a form this build reads (its "multivigenza" reconstructions, from 2005, are PDF files)',
    'source_md': ('The Raccolta normativa of the Consiglio regionale della Toscana, <https://raccoltanormativa.consiglio.regione.toscana.it/>.\n\n'
                  '- Its open data (page "Scarica i dati", CC BY 3.0): for each legislature I to X (1970-2020) a zip with the '
                  'coordinated text of every regional law in Akoma Ntoso XML. The zips are no longer kept up to date: the newest '
                  'file in them is dated 28 January 2022 and the latest amending law they reflect is of 28 December 2021. Each '
                  'law\'s first commit here is its text from these zips.\n'
                  '- Each law\'s own page (`articolo?urndoc=urn:nir:regione.toscana:legge:<date>;<number>`) links the current '
                  'text of that law as an Akoma Ntoso file. Every law was read there again on ' + _REFRESH_LONG + '; where that '
                  'text differs from the open data it follows as a second commit. The laws of 2020 on that the open data does '
                  'not hold (the XI and XII legislatures) come from their pages only. They were found without the site\'s search '
                  '(which needs a browser session): from the laws cited in the open data and on the pages read, the newest law '
                  'on the home page, and a few date probes per missing number; numbers not found that way are missing.\n'
                  '- The Statute is read from its own Akoma Ntoso file on its page.\n'
                  '- The site also shows dated past versions of some laws ("multivigenza"), but only as PDF files (for the Statute '
                  'the list stops at l.r. 5/2015 although its text has later amendments), and the open data holds one file per law. '
                  'They are not used, so there is no dated history here.\n'
                  '- Laws repealed in full (marked as removed in the open data) are left out.'),
    'files_md': ('`statuto/art-001.md` is Articolo 1 of the Statute; `lr-2014-065/art-005-bis.md` is Articolo 5 bis of '
                 'legge regionale 10 novembre 2014, n. 65; `intestazione.md` holds the title, date, number and preamble. '
                 'The headings of titles, chapters and sections stay in the file of the article they stand before. '
                 'Editor\'s notes ("Note del redattore") and their markers are left out; annexes (allegati) are not included.'),
    'scope_note': 'Regulations, annexes and laws repealed in full are not included (but see Limits for ten laws repealed '
                  'since January 2022); laws of 2020 on that could only be '
                  'found through the site\'s search are missing.',
    'dates_md': ('- Every text here is a current text, dated the day it was read, not the day it took effect. The source gives '
                 'no dated past versions in a form this build reads (its "multivigenza" versions are PDF files), so the '
                 'dates of the changes are not in this record.\n'
                 '- The first commit of each law, its **oldest version available**, is the text in the open data (zips last '
                 'updated in ' + OPEN_DATA_LONG + '), dated at **noon, Europe/Rome, on ' + _REFRESH_LONG + '**, the day it '
                 'was read. It is the text in force in ' + OPEN_DATA_LONG + ' at the latest, not on that day.\n'
                 '- Where the law\'s own page gave a different current text when it was read on ' + _REFRESH_LONG + ', '
                 'that text follows in a second commit on the same day, authored by the publisher and credited to no law: '
                 'it gathers every change since ' + OPEN_DATA_LONG + ', whose own dates are not recorded here. A law with one '
                 'commit had the same text on its page, except the few named under Limits.\n'
                 '- The laws of 2020 on that are not in the open data, and the Statute, have one commit: the current text '
                 'from their page, read on ' + _REFRESH_LONG + '.\n'
                 '- So `main` holds the text on the law\'s page on ' + _REFRESH_LONG + '; checking out an earlier date '
                 'gives no earlier wording.'),
    'author_md': ('Every commit here is authored by the publisher, the Raccolta normativa of the Consiglio regionale della '
                  'Toscana, with an e-mail address that cannot exist: the "oldest version available" commits and the second '
                  'commits that bring a law to the current text on its page. No commit is credited to a law.'),
    'limits_md': ('Only current texts are recorded (the open-data text of ' + OPEN_DATA_LONG + ' and, where it differs, the '
                  'text on the law\'s page on ' + _REFRESH_LONG + '), not earlier wordings or the dates of changes. '
                  'Ten laws that the open data gave as in force are shown on their pages as repealed in full on '
                  + _REFRESH_LONG + ' (l.r. 29/1996, 1/2004, 30/2006, 14/2007, 64/2011, 57/2014, 34/2017, 58/2017, '
                  '24/2018 and 32/2019); they still hold their open-data text here. For l.r. 93/1993 and 36/2000 the '
                  'page\'s Akoma Ntoso file had no text, and the page of l.r. 300/2019 (so numbered in the open data) '
                  'was not found, so these keep their open-data text unchecked against the page. Laws of 2020 on whose '
                  'page\'s Akoma Ntoso file had no text (l.r. 94/2020, 37/2025, 38/2025, 46/2025, 58/2025, 2/2026 and '
                  '16/2026) are not included. '),
    'row_hist': lambda a: ('oldest version available (open data, ' + OPEN_DATA_LONG + '), then the current text from the '
                           'law\'s page: ' + _REFRESH_LONG if len(a['versions']) > 1 else
                           'oldest version available: ' + _REFRESH_LONG),
    'official_md': 'The Raccolta normativa says its texts have no official character ("La pubblicazione dei testi non ha '
                   'carattere di ufficialità"); the texts with legal value are those published in the Bollettino '
                   'Ufficiale della Regione Toscana (BURT).',
    'terms_md': ('The Consiglio regionale della Toscana releases the open data of the Raccolta normativa under the Creative '
                 'Commons Attribution 3.0 licence (CC BY 3.0, https://creativecommons.org/licenses/by/3.0/), "per il libero '
                 'riuso", and its copyright page says: "I documenti, invece, sono liberamente utilizzabili a condizione che ne '
                 'sia citata la fonte." (The documents may be freely used provided the source is cited.) Its marks and logos '
                 'are not used here.'),
}


# ---------------------------------------------------------------- fetch

def fetch():
    for leg in LEGISLATURES:
        b = it_fetch.get(bulk_url(leg), timeout=900)
        R.say(f'legislature {leg}: {len(b or b"")} bytes')
    t = it_fetch.get(STATUTO_PAGE).decode('utf-8', 'replace')
    akm = re.search(r'class/download_doc\.php\?id=([0-9a-f-]+)&amp;ext=akm', t).group(1)
    b = it_fetch.get(f'{BASE}class/download_doc.php?id={akm}&ext=akm')
    R.say(f'statuto akm {akm}: {len(b)} bytes')


def statuto_url() -> str:
    t = it_fetch.get(STATUTO_PAGE).decode('utf-8', 'replace')
    akm = re.search(r'class/download_doc\.php\?id=([0-9a-f-]+)&amp;ext=akm', t).group(1)
    return f'{BASE}class/download_doc.php?id={akm}&ext=akm'


def cached(url: str) -> bytes:
    p = it_fetch.path_for(url)
    if not p.exists():
        raise SystemExit(f'not fetched: {url}')
    return p.read_bytes()


# ---------------------------------------------------------------- parse (minidom walk)

STRUCT = {'title', 'chapter', 'section', 'part', 'book', 'subsection', 'subchapter'}
SKIP = {'noteRef', 'authorialNote', 'eol'}


def text_of(el) -> str:
    out = []

    def walk(n):
        for c in n.childNodes:
            if c.nodeType == c.TEXT_NODE:
                out.append(c.data)
            elif c.nodeType == c.ELEMENT_NODE and c.tagName not in SKIP:
                walk(c)
    walk(el)
    return ' '.join(''.join(out).split())


def lines_of(el) -> list[str]:
    """One line per <num>-led item or <p>, in document order; a <num> joins the paragraph that follows it."""
    lines: list[str] = []
    pending = ['']   # a num waiting for its paragraph

    def flush_num():
        if pending[0]:
            lines.append(pending[0].strip())
            pending[0] = ''

    def walk(n):
        for c in n.childNodes:
            if c.nodeType != c.ELEMENT_NODE or c.tagName in SKIP:
                continue
            tag = c.tagName
            if tag == 'num':
                flush_num()
                pending[0] = text_of(c)
            elif tag in ('heading', 'subheading'):
                t = text_of(c)
                if pending[0]:
                    pending[0] = (pending[0] + ' ' + t).strip()
                    flush_num()
                elif t:
                    lines.append(t)
            elif tag in ('p', 'docTitle', 'docType', 'docDate', 'docNumber', 'docCommittee'):
                t = text_of(c)
                if pending[0]:
                    t = (pending[0] + ' ' + t).strip()
                    pending[0] = ''
                if t:
                    lines.append(t)
            else:
                walk(c)
    walk(el)
    flush_num()
    return [x for x in (R.clean_line(x) for x in lines) if x]


def art_key(num: str, seen: Counter) -> tuple[str, str]:
    t = R.clean_line(num)
    m = re.match(r'(?i)art(?:icolo)?\.?\s*(\d+)\s*([a-z\s.-]*)$', t)
    if m:
        suf = R.ascii_slug(m.group(2))
        k = f'art-{int(m.group(1)):03d}' + (f'-{suf}' if suf else '')
        lab = 'Articolo ' + m.group(1) + (f' {m.group(2).strip()}' if m.group(2).strip() else '')
    elif re.match(r'(?i)art(icolo)?\.?\s*unico', t):
        k, lab = 'art-001-unico', 'Articolo unico'
    else:
        k, lab = 'art-' + (R.ascii_slug(t) or 'x'), t or 'Articolo'
    seen[k] += 1
    if seen[k] > 1:
        k += f'-dup{seen[k]}'
    return k, lab


def parse_akm(b: bytes) -> dict | None:
    doc = minidom.parseString(b)
    body = doc.getElementsByTagName('body')
    if not body or body[0].getAttribute('status') == 'removed':
        return None
    body = body[0]
    units = {}
    head = []
    for tag in ('preface', 'preamble'):
        for el in doc.getElementsByTagName(tag):
            head += lines_of(el)
    if head:
        units['intestazione'] = {'label': 'Intestazione', 'kind': 'preamble', 'text': '\n'.join(head) + '\n'}
    seen = Counter()
    carry: list[str] = []

    def walk(n):
        for c in n.childNodes:
            if c.nodeType != c.ELEMENT_NODE:
                continue
            if c.tagName == 'article':
                nums = [x for x in c.childNodes if x.nodeType == x.ELEMENT_NODE and x.tagName == 'num']
                k, lab = art_key(text_of(nums[0]) if nums else '', seen)
                ls = carry + lines_of(c)
                carry.clear()
                if ls:
                    units[k] = {'label': lab, 'kind': 'art', 'text': '\n'.join(ls) + '\n'}
            elif c.tagName in STRUCT:
                for x in c.childNodes:
                    if x.nodeType == x.ELEMENT_NODE and x.tagName in ('num', 'heading'):
                        t = R.clean_line(text_of(x))
                        if t:
                            if x.tagName == 'heading' and carry and not carry[-1].endswith(t):
                                carry[-1] = (carry[-1] + ' ' + t).strip()
                            else:
                                carry.append(t)
                walk(c)
            else:
                # loose paragraphs in the body (outside articles)
                ls = lines_of(c) if c.tagName not in ('num', 'heading') else []
                if ls:
                    carry.extend(ls)
    walk(body)
    if carry:
        units['testo-finale'] = {'label': 'Testo finale', 'kind': 'other', 'text': '\n'.join(carry) + '\n'}
    if not any(u['kind'] == 'art' for u in units.values()):
        return None
    pub = doc.getElementsByTagName('publication')
    title = ''
    for el in doc.getElementsByTagName('docTitle'):
        title = R.clean_line(text_of(el))
        break
    date = num = ''
    for el in doc.getElementsByTagName('docDate'):
        date = el.getAttribute('date')
        break
    for el in doc.getElementsByTagName('docNumber'):
        num = R.clean_line(text_of(el))
        break
    return {'units': units, 'title': title, 'date': date, 'num': num,
            'bur': (pub[0].getAttribute('date'), pub[0].getAttribute('number')) if pub else None}


def bulk_entries() -> list[dict]:
    out = []
    for leg in LEGISLATURES:
        url = bulk_url(leg)
        z = zipfile.ZipFile(io.BytesIO(cached(url)))
        for name in z.namelist():
            m = re.match(r'legge_(\d{4})_(\d+)(_s\d+)?_akm(?:_v(\d+))?\.xml$', name)
            if not m or m.group(3):
                continue   # _sN files are separate extracts of a law, not the law itself
            out.append({'leg': leg, 'url': url, 'member': name, 'year': int(m.group(1)), 'n': int(m.group(2)),
                        'v': int(m.group(4) or 0)})
    # one file per law (the highest version if two are listed)
    best = {}
    for e in out:
        k = (e['year'], e['n'])
        if k not in best or e['v'] > best[k]['v']:
            best[k] = e
    return [best[k] for k in sorted(best)]


def member_bytes(e: dict) -> bytes:
    return zipfile.ZipFile(io.BytesIO(cached(e['url']))).read(e['member'])


MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
          'novembre', 'dicembre']


def act_for(p: dict, slug: str, short: str, title: str, url: str, docs_date: str, sha_src: bytes, src_url: str) -> dict:
    import hashlib
    return {'slug': slug, 'short': short, 'title': title, 'url': url, 'first_law': None, 'earlier_laws': [],
            'versions': [{'from': docs_date, 'source_url': src_url, 'sha256': hashlib.sha256(sha_src).hexdigest(),
                          'units': p['units'], 'credits': {},
                          'note': 'Current coordinated text on the retrieval day (oldest version available here).'}]}


def plan() -> list[tuple[str, list]]:
    ents = bulk_entries()
    live = []
    for e in ents:
        p = parse_akm(member_bytes(e))
        if p is not None:
            live.append(e)
    parts = [('10-statuto', ['statuto'])]
    for i in range(0, len(live), PART_SIZE):
        parts.append((f'30-leggi-{i // PART_SIZE + 1:02d}', live[i:i + PART_SIZE]))   # sorts after 10-statuto
    return parts


def build_part(name: str, members: list, docs_date: str) -> dict:
    acts = []
    for m in members:
        if m == 'statuto':
            u = statuto_url()
            b = cached(u)
            p = parse_akm(b)
            acts.append(act_for(p, 'statuto', 'Statuto', 'Statuto della Regione Toscana', STATUTO_PAGE, docs_date, b, u))
            continue
        b = member_bytes(m)
        p = parse_akm(b)
        y, n = m['year'], m['n']
        d = p['date']
        try:
            dd = f'{int(d[8:10])} {MONTHS[int(d[5:7]) - 1]} {d[:4]}'
        except (ValueError, IndexError):
            dd = str(y)
        title = f'Legge regionale {dd}, n. {n}' + (f' - {p["title"]}' if p['title'] else '')
        urn = f'urn:nir:regione.toscana:legge:{d};{n}' if d else ''
        acts.append(act_for(p, f'lr-{y}-{n:03d}', f'l.r. {n}/{y}', title, f'{BASE}articolo?urndoc={urn}', docs_date,
                            b, f'{m["url"]}#{m["member"]}'))
    laws = {}
    for a, m in zip(acts, members):
        key = a['slug'] if a['slug'] != 'statuto' else 'statuto-2005'
        p = parse_akm(cached(statuto_url()) if m == 'statuto' else member_bytes(m))
        bur = p['bur'] or ('', '')
        iso = lambda d: d if d and re.fullmatch(r'\d{4}-\d\d-\d\d', d) else None  # noqa: E731
        laws[key] = {'label': a['short'] if m != 'statuto' else 'Statuto della Regione Toscana (2005)',
                     'title': a['title'], 'kind': 'law', 'enacted': iso(p['date']),
                     'published': iso(bur[0]), 'url': a['url'], 'temporary_until': None, 'restores': None,
                     'note': None}
        a['earlier_laws'] = [key]
    part = {'country': R.country_block(SLUG, SRC), 'laws': laws, 'acts': acts}
    if R.is_first_part(SLUG, name):
        part.update(sources=[R.source_block(SRC, docs_date)], decisions=DECISIONS, ai_use=AI_USE)
    return part


DECISIONS = [
    'Current texts only: each law\'s first commit is its coordinated text in the Consiglio regionale\'s open data (zips '
    'last updated January 2022), an "oldest version available" commit dated the retrieval day. Each law\'s page was read '
    'again (its current Akoma Ntoso file, ' + REFRESH_DATE + '); where that text differs it is a second commit on the same '
    'day, by the publisher and credited to no law, because the changes it gathers have no in-force dates in this source.',
    'No dated history: the site\'s "multivigenza" versions are PDF files listed on each law\'s allegati tab (for the '
    'Statute the list stops at l.r. 5/2015 although its text has amendments to 2023) and the open data holds one file '
    'per law, so no dated past versions are built.',
    'Laws of 2020 on that the open data lacks were found without the site\'s search (it needs a browser session): '
    'laws cited in the open data and on the pages read, the newest law on the home page, and at most 15 date probes '
    'per missing number between the dates of its neighbours (laws are numbered in date order). Each has one commit, '
    'its page\'s current text, dated the retrieval day.',
    'Laws marked as repealed in full in the open data (body status "removed") are left out; laws with no article '
    'text are left out.',
    'Units: intestazione (type, date, number, title, preamble) and one file per article; headings of titles, '
    'chapters and sections go in the file of the next article; editor\'s notes and note markers are left out.',
]
AI_USE = ['A model (Claude) wrote the fetch and parse code and chose the layout; it wrote no law text. Every word of '
          'law comes from the Consiglio regionale della Toscana\'s Akoma Ntoso files.']


# ---------------------------------------------------------------- independent letters check (lxml, all text)

def letters_check(slug: str, part_name: str, path: Path | None = None) -> list[str]:
    """Every version of every act: version 1 against its open-data zip member (or the Statute's akm), a version from
    the refresh against the law's page akm, cached by its download URL (source_url, sha256)."""
    from lxml import etree
    p = path or (R.folder(slug) / 'corpus.d' / f'{part_name}.json')
    part = json.loads(p.read_text(encoding='utf-8'))
    probs = []
    for act, v in ((a, v) for a in part['acts'] for v in a['versions']):
        url = v['source_url']
        if '#' in url:
            u, mem = url.split('#', 1)
            b = zipfile.ZipFile(io.BytesIO(cached(u))).read(mem)
        else:
            b = cached(url)
        import hashlib
        if hashlib.sha256(b).hexdigest() != v['sha256']:
            probs.append(f'{act["slug"]}: sha256 differs ({v["from"]})')
            continue
        root = etree.fromstring(b)
        src = ''
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            ln = etree.QName(el).localname
            if ln in ('preface', 'preamble', 'body'):
                src += ''.join(el.itertext())
        src = R.letters(src)
        mine = ''.join(u['text'] for u in v['units'].values())
        lm = R.letters(mine)
        if Counter(src) != Counter(lm) or len(src) != len(lm):
            ca, cb = Counter(src), Counter(lm)
            probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} corpus-only '
                         f'{dict((cb - ca).most_common(6))}')
            continue
        if src != lm:
            # same letters, different order: each unit must still appear in the source in order
            pos = 0
            for k, un in v['units'].items():
                t = R.letters(un['text'])
                i = src.find(t, pos)
                if i < 0:
                    probs.append(f'{act["slug"]} {k}: text not found in order in the source')
                    break
                pos = i + len(t)
    return probs


def publish_batch(docs_date: str, names: list[str]) -> str:
    """Verify several parts at once: the letters check of each, then ONE scratch build of every verified part plus all
    of these, checked by check.py; on success each gets its own PUBLISH line. Same checks as R.publish, one build."""
    import os, shutil, subprocess
    for n in names:
        pr = letters_check(SLUG, n)
        if pr:
            return f'{n}: letters check {len(pr)} problems: {pr[0]}'
    R.wait_cpu()
    src = R.folder(SLUG)
    tmp, build = R.DOCS / f'{R.repo_name(SLUG)}-verify', R.DOCS / f'{R.repo_name(SLUG)}-verifybuild'
    for d in (tmp, build):
        R._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    have = [q.stem for q in sorted((src / 'corpus.d').glob('*.json')) if q.with_suffix('.PUBLISH').exists()]
    for n in have + [n for n in names if n not in have]:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    R.write_docs(SLUG, SRC, docs_date, extra=names, out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = R._low([sys.executable, '-X', 'utf8', str(R.ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo',
                str(build), '--docs-date', docs_date], env=env)
    if b.returncode:
        return 'build failed: ' + (b.stderr or b.stdout)[-600:]
    c = R._low([sys.executable, '-X', 'utf8', str(R.ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    res = json.loads(c.stdout[c.stdout.index('{'):])
    if c.returncode or any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated',
                                                'missing_in_force')):
        return 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:400]
    for n in names:
        acts = json.loads((src / 'corpus.d' / f'{n}.json').read_text(encoding='utf-8'))['acts']
        line = (f'{len(acts)} act(s), {len(acts)} versions {docs_date} from {SRC["short"]}: letters and digits of every '
                f'version equal the source text (independent lxml reader) and every unit is found in order; scratch '
                f'build of verified parts + parts {names[0]}..{names[-1]}: check.py {res.get("versions")} versions, '
                f'0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
        (src / 'corpus.d' / f'{n}.PUBLISH').write_text(line + chr(10), encoding='utf-8', newline=chr(10))
        R.progress(SLUG, f'{n}: PUBLISH {line}')
    R.write_docs(SLUG, SRC, docs_date)
    R._rm(tmp)
    R._rm(build)
    return f'PUBLISH {len(names)} parts, check.py {res.get("versions")} versions clean'


# ---------------------------------------------------------------- refresh from each law's page (2026-10-30 evening)
# The open-data zips stop at January 2022. Each law's page (a plain GET) links the current Akoma Ntoso of that law;
# `refresh` reads it for every act in the repo (A), finds the laws of 2020 on that the zips lack (B), and logs to
# REFRESH_DIR. `stage` writes the appended versions and the new parts; `republish` verifies and swaps them in.

REFRESH_DIR = it_fetch.CACHE / '_tuscany_refresh'     # private state, outside the region folder (autopush walks it)
NODOC = b'caricamento del documento fallito'
REF_RES = (rb'urn:nir:regione\.toscana:legge:(\d{4}-\d\d-\d\d);(\d+)',
           rb'/it/legge/regione\.toscana/(\d{4}-\d\d-\d\d)/(\d+)')
MAX_PROBES = 15
NEW_FROM_YEAR = 2020
V2_NOTE = ('Current text from the law\'s page on the retrieval day; the earlier commit is the open-data text (open data '
           'last updated January 2022). This commit gathers every change the Raccolta normativa made to the text since '
           'then; it is dated the day the page was read, not the day those changes took effect.')


def law_page(date: str, n: int) -> str:
    return f'{BASE}articolo?urndoc=urn:nir:regione.toscana:legge:{date};{n}'


def akm_link(page: bytes) -> str | None:
    m = re.search(rb'class/download_doc\.php\?id=([0-9a-f-]+)&amp;ext=akm', page)
    return f'{BASE}class/download_doc.php?id={m.group(1).decode()}&ext=akm' if m else None


def refs_in(b: bytes) -> set[tuple[str, int]]:
    out = set()
    for rx in REF_RES:
        for m in re.finditer(rx, b):
            out.add((m.group(1).decode(), int(m.group(2))))
    return out


def rlog(line: str):
    REFRESH_DIR.mkdir(parents=True, exist_ok=True)
    with open(REFRESH_DIR / 'refresh.log', 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'{R.now()} {line}\n')


def _cached_or_none(url: str) -> bool:
    return it_fetch.path_for(url).exists() or it_fetch.path_for(url).with_suffix('.404').exists()


def fetch_law(date: str, n: int, counter: Counter) -> dict:
    """Page + akm of one law, through it_fetch. counter['requests'] counts real requests (not cache hits)."""
    pu = law_page(date, n)
    rec = {'date': date, 'n': n, 'page_url': pu}
    if not _cached_or_none(pu):
        counter['requests'] += 1
    p = it_fetch.get(pu)
    if p is None:
        rec['status'] = 'page-none'
        return rec
    rec['page_at'] = R.dt.datetime.fromtimestamp(it_fetch.path_for(pu).stat().st_mtime, R.dt.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')
    if len(p) < 400 and NODOC in p:
        rec['status'] = 'nodoc'
        return rec
    m = re.search(rb'id="NIR_tes_tipo" class="([^"]*)"', p)
    rec['page_class'] = m.group(1).decode() if m else ''
    m = re.search(rb'class="tipo_doc_[a-z]+">([^<]*)<', p)
    rec['page_kind'] = m.group(1).decode('utf-8', 'replace') if m else ''
    au = akm_link(p)
    if not au:
        rec['status'] = 'noakm'
        return rec
    rec['akm_url'] = au
    if not _cached_or_none(au):
        counter['requests'] += 1
    b = it_fetch.get(au, timeout=300)
    if b is None:
        rec['status'] = 'akm-none'
        return rec
    rec['status'] = 'ok'
    return rec


def zip_dates() -> dict[tuple[int, int], str]:
    """(year, n) -> docDate for every law file in the zips (live or repealed)."""
    out = {}
    for e in bulk_entries():
        m = re.search(rb'<(?:akn:)?docDate[^>]*date="(\d{4}-\d\d-\d\d)"', member_bytes(e))
        out[(e['year'], e['n'])] = m.group(1).decode() if m else ''
    return out


def repo_acts() -> list[tuple[str, dict]]:
    out = []
    for name in R.part_names(SLUG):
        if not name.startswith('30-leggi-'):
            continue
        for a in json.loads((R.folder(SLUG) / 'corpus.d' / f'{name}.json').read_text(encoding='utf-8'))['acts']:
            out.append((name, a))
    return out


def refresh_job():
    """A then B, one request at a time (it_fetch), resumable from the cache. Writes REFRESH_DIR/fetched.json."""
    import time
    REFRESH_DIR.mkdir(parents=True, exist_ok=True)
    cnt = Counter()
    recs: dict[str, dict] = {}

    def save():
        tmp = REFRESH_DIR / 'fetched.tmp'
        tmp.write_text(json.dumps({'counts': dict(cnt), 'recs': list(recs.values())}, ensure_ascii=False, indent=0),
                       encoding='utf-8', newline='\n')
        import os
        os.replace(tmp, REFRESH_DIR / 'fetched.json')

    acts = repo_acts()
    rlog(f'A: {len(acts)} acts')
    for i, (part, a) in enumerate(acts):
        m = re.search(r'legge:(\d{4}-\d\d-\d\d);(\d+)$', a['url'])
        R.wait_cpu()
        rec = fetch_law(m.group(1), int(m.group(2)), cnt)
        rec.update(slug=a['slug'], part=part, phase='A')
        recs[rec['page_url']] = rec
        cnt['A-' + rec['status']] += 1
        if i % 25 == 0:
            rlog(f'A {i + 1}/{len(acts)} {a["slug"]} {rec["status"]} requests={cnt["requests"]}')
            save()
    save()
    rlog(f'A done: {dict(cnt)}')

    # B: laws from 2020 on that the zips lack
    zd = zip_dates()
    known: dict[tuple[int, int], str] = {k: v for k, v in zd.items() if v}
    found: dict[tuple[int, int], str] = {}
    tried: set[tuple[str, int]] = set()

    def all_refs() -> set[tuple[str, int]]:
        s = set()
        for leg in LEGISLATURES:
            z = zipfile.ZipFile(io.BytesIO(cached(bulk_url(leg))))
            for nm in z.namelist():
                s |= refs_in(z.read(nm))
        home = it_fetch.path_for(BASE)
        if home.exists():
            s |= refs_in(home.read_bytes())
        for r in recs.values():
            for u in (r.get('page_url'), r.get('akm_url')):
                if u and it_fetch.path_for(u).exists():
                    s |= refs_in(it_fetch.path_for(u).read_bytes())
        return s

    def try_one(date: str, n: int, why: str) -> bool:
        y = int(date[:4])
        if (date, n) in tried or (y, n) in found or (y, n) in zd:
            return (y, n) in found
        tried.add((date, n))
        R.wait_cpu()
        rec = fetch_law(date, n, cnt)
        rec.update(phase='B', why=why)
        cnt[f'B-{why}-{rec["status"]}'] += 1
        if rec['status'] == 'nodoc':
            return False
        recs[rec['page_url']] = rec
        if rec['status'] in ('ok', 'noakm', 'akm-none'):
            found[(y, n)] = date
            known[(y, n)] = date
            rlog(f'B found {date};{n} ({why}) {rec["status"]} requests={cnt["requests"]}')
            return True
        return False

    def ref_pass(label: str):
        while True:
            new = sorted(k for k in all_refs() if int(k[0][:4]) >= NEW_FROM_YEAR and k not in tried
                         and (int(k[0][:4]), k[1]) not in found and (int(k[0][:4]), k[1]) not in zd)
            if not new:
                return
            rlog(f'B {label}: {len(new)} cited (date, n) to try')
            for d, n in new:
                try_one(d, n, 'cited')
            save()

    try_one('2026-10-26', 25, 'cited')     # the home page's newest law
    ref_pass('references')
    import datetime as dtm
    this_year = dtm.date.today().year
    per_n: Counter = Counter()      # probes per missing (year, n), at most MAX_PROBES in all
    for y in range(NEW_FROM_YEAR, this_year + 1):
        while True:
            ns = sorted(n for (yy, n) in known if yy == y)
            if not ns:
                break
            missing = [n for n in range(1, ns[-1] + 1) if (y, n) not in known and (y, n) not in zd]
            progress_made = False
            for n in missing:
                lo = max([known[(y, k)] for k in ns if k < n] or [f'{y}-01-01'])
                hi = min([known[(y, k)] for k in ns if k > n] or [f'{y}-12-31'])
                d0, d1 = dtm.date.fromisoformat(lo), dtm.date.fromisoformat(hi)
                days = [(d0 + dtm.timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)]
                order = []
                while days:
                    order.append(days.pop(0))
                    if days:
                        order.append(days.pop())
                for d in order:
                    if per_n[(y, n)] >= MAX_PROBES:
                        break
                    if (d, n) in tried:
                        continue
                    per_n[(y, n)] += 1
                    cnt['probes'] += 1
                    cnt[f'probes-{y}'] += 1
                    if try_one(d, n, 'probe'):
                        progress_made = True
                        break
                save()
            if progress_made:
                ref_pass(f'references after probes {y}')
                continue
            break
        # past the last known number of a finished year: one number at a time while found
        if y < this_year:
            while True:
                ns = sorted(n for (yy, n) in known if yy == y)
                n = ns[-1] + 1
                d0 = dtm.date.fromisoformat(known[(y, ns[-1])])
                days = [(d0 + dtm.timedelta(i)).isoformat() for i in range((dtm.date(y, 12, 31) - d0).days + 1)]
                ok = False
                for d in days[:MAX_PROBES]:
                    if (d, n) in tried:
                        continue
                    cnt['probes'] += 1
                    cnt[f'probes-{y}'] += 1
                    if try_one(d, n, 'probe-tail'):
                        ok = True
                        break
                save()
                if not ok:
                    break
                ref_pass(f'references after tail {y}')
    gaps = {}
    for y in range(NEW_FROM_YEAR, this_year + 1):
        ns = sorted(n for (yy, n) in known if yy == y)
        if ns:
            gaps[y] = [n for n in range(1, ns[-1] + 1) if (y, n) not in known]
    cnt_out = dict(cnt)
    (REFRESH_DIR / 'discover.json').write_text(json.dumps({
        'found': {f'{y}-{n}': d for (y, n), d in sorted(found.items())},
        'gaps': {str(y): g for y, g in gaps.items()}, 'max': {str(y): max(n for (yy, n) in known if yy == y)
                                                              for y in gaps}, 'counts': cnt_out},
        indent=1), encoding='utf-8', newline='\n')
    save()
    rlog(f'B done: found {len(found)}, counts {cnt_out}')
    time.sleep(0)


STAGE = REFRESH_DIR / 'stage'
NEW_PREFIX = '40-leggi-'


def _sha(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()


def _iso(d):
    return d if d and re.fullmatch(r'\d{4}-\d\d-\d\d', d) else None


def stage(docs_date: str) -> dict:
    """Write STAGE/<part>.json for every 30-leggi part with an appended version, and the new 40-leggi parts into
    corpus.d (not PUBLISHed). Returns a summary; nothing already in the repo is rewritten (append only)."""
    import os
    fj = json.loads((REFRESH_DIR / 'fetched.json').read_text(encoding='utf-8'))
    by_slug = {r['slug']: r for r in fj['recs'] if r.get('phase') == 'A'}
    STAGE.mkdir(parents=True, exist_ok=True)
    summ = Counter()
    repealed, unread, changed_slugs = [], [], []
    for name in R.part_names(SLUG):
        if not name.startswith('30-leggi-'):
            continue
        pj = json.loads((R.folder(SLUG) / 'corpus.d' / f'{name}.json').read_text(encoding='utf-8'))
        touched = False
        for a in pj['acts']:
            r = by_slug.get(a['slug'])
            if not r or r['status'] != 'ok':
                unread.append(f'{a["slug"]} ({r["status"] if r else "not fetched"})')
                summ['unread'] += 1
                continue
            b = cached(r['akm_url'])
            p = parse_akm(b)
            if p is None:
                repealed.append(f'{a["slug"]} (page: {r.get("page_kind", "")}, {r.get("page_class", "")})')
                summ['repealed'] += 1
                continue
            if len(a['versions']) > 1:
                summ['already'] += 1
                continue
            if p['units'] == a['versions'][-1]['units']:
                summ['same'] += 1
                continue
            v = {'from': docs_date, 'source_url': r['akm_url'], 'sha256': _sha(b), 'units': p['units'], 'credits': {},
                 'note': V2_NOTE}
            if docs_date == a['versions'][-1]['from']:
                v = {'from': docs_date, 'same_day': True, **{k: x for k, x in v.items() if k != 'from'}}
            a['versions'].append(v)
            touched = True
            summ['changed'] += 1
            changed_slugs.append(a['slug'])
        if touched:
            tmp = STAGE / f'{name}.tmp'
            tmp.write_text(json.dumps(pj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
            os.replace(tmp, STAGE / f'{name}.json')
            summ['staged_parts'] += 1
    # the first part carries the source notes and decisions: restage it when they changed (its act is untouched)
    first = json.loads((R.folder(SLUG) / 'corpus.d' / '10-statuto.json').read_text(encoding='utf-8'))
    srcs = [R.source_block(SRC, s.get('retrieved', docs_date)) for s in first.get('sources', [])]
    if srcs != first.get('sources') or first.get('decisions') != DECISIONS:
        first['sources'], first['decisions'] = srcs, DECISIONS
        tmp = STAGE / '10-statuto.tmp'
        tmp.write_text(json.dumps(first, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        os.replace(tmp, STAGE / '10-statuto.json')
        summ['staged_parts'] += 1
    # new laws (B)
    new = []
    new_repealed = []
    for r in sorted((x for x in fj['recs'] if x.get('phase') == 'B' and x['status'] == 'ok'),
                    key=lambda x: (x['date'][:4], x['n'])):
        b = cached(r['akm_url'])
        p = parse_akm(b)
        y, n = int(r['date'][:4]), r['n']
        if p is None:
            new_repealed.append(f'lr-{y}-{n:03d}')
            continue
        d = p['date'] or r['date']
        try:
            dd = f'{int(d[8:10])} {MONTHS[int(d[5:7]) - 1]} {d[:4]}'
        except (ValueError, IndexError):
            dd = str(y)
        title = f'Legge regionale {dd}, n. {n}' + (f' - {p["title"]}' if p['title'] else '')
        slug = f'lr-{y}-{n:03d}'
        act = {'slug': slug, 'short': f'l.r. {n}/{y}', 'title': title, 'url': r['page_url'], 'first_law': None,
               'earlier_laws': [slug],
               'versions': [{'from': docs_date, 'source_url': r['akm_url'], 'sha256': _sha(b), 'units': p['units'],
                             'credits': {}, 'note': 'Current text from the law\'s page on the retrieval day (oldest '
                                                    'version available here).'}]}
        bur = p['bur'] or ('', '')
        law = {'label': act['short'], 'title': title, 'kind': 'law', 'enacted': _iso(p['date']),
               'published': _iso(bur[0]), 'url': r['page_url'], 'temporary_until': None, 'restores': None,
               'note': None}
        new.append((act, law))
    have_slugs = {a['slug'] for _, a in repo_acts()}
    new = [x for x in new if x[0]['slug'] not in have_slugs]
    written = []
    for i in range(0, len(new), PART_SIZE):
        name = f'{NEW_PREFIX}{i // PART_SIZE + 1:02d}'
        chunk = new[i:i + PART_SIZE]
        part = {'country': R.country_block(SLUG, SRC), 'laws': {a['slug']: l for a, l in chunk},
                'acts': [a for a, _ in chunk]}
        if not (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
            R.write_part(SLUG, name, part)
            written.append(name)
    out = {'counts': dict(summ), 'repealed_in_full_on_page': repealed, 'unread': unread, 'changed': changed_slugs,
           'new_acts': len(new), 'new_parts': written, 'new_repealed_left_out': new_repealed}
    (REFRESH_DIR / 'stage.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8',
                                            newline='\n')
    return out


def _part_path(n: str) -> Path:
    s = STAGE / f'{n}.json'
    return s if s.exists() else R.folder(SLUG) / 'corpus.d' / f'{n}.json'


def republish(docs_date: str, names: list[str]) -> str:
    """Verify staged (re-PUBLISH) and new parts together: letters check of every version, then ONE scratch build of
    every PUBLISHed part (staged copies in place of their originals) plus the new ones, checked by check.py. Then each
    staged json replaces its original (os.replace) and only after that its PUBLISH line is replaced, so a part is never
    without PUBLISH. Acts the letters check disagrees with lose only their appended version (staged) or are left out
    (new)."""
    import os
    import shutil
    import subprocess
    d = R.folder(SLUG) / 'corpus.d'
    for n in names:
        path = _part_path(n)
        probs = letters_check(SLUG, n, path=path)
        if probs:
            bad = sorted({p_.split(' ')[0].rstrip(':') for p_ in probs})
            pj = json.loads(path.read_text(encoding='utf-8'))
            if path.parent == STAGE:
                for a in pj['acts']:
                    if a['slug'] in bad:
                        a['versions'] = a['versions'][:1]
                R.progress(SLUG, f'{n}: page text not appended (letters check disagrees): {", ".join(bad)}')
            else:
                pj['acts'] = [a for a in pj['acts'] if a['slug'] not in bad]
                for b_ in bad:
                    pj['laws'].pop(b_, None)
                R.progress(SLUG, f'{n}: left out (letters check disagrees): {", ".join(bad)}')
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(pj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
            os.replace(tmp, path)
            probs = letters_check(SLUG, n, path=path)
            if probs:
                return f'NOT VERIFIED {n}: letters check {len(probs)} problems: {probs[0]}'
    R.wait_cpu()
    tmp, build = R.DOCS / f'{R.repo_name(SLUG)}-verify', R.DOCS / f'{R.repo_name(SLUG)}-verifybuild'
    for x in (tmp, build):
        R._rm(x)
    (tmp / 'corpus.d').mkdir(parents=True)
    have = [q.stem for q in sorted(d.glob('*.json')) if q.with_suffix('.PUBLISH').exists()]
    for n in have + [n for n in names if n not in have]:
        shutil.copy2(_part_path(n) if n in names else d / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    R.write_docs(SLUG, SRC, docs_date, extra=[n for n in names if n not in have], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = R._low([sys.executable, '-X', 'utf8', str(R.ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo',
                str(build), '--docs-date', docs_date], env=env)
    if b.returncode:
        msg = 'build failed: ' + (b.stderr or b.stdout)[-600:]
        R.progress(SLUG, f'{names[0]}..{names[-1]}: NOT VERIFIED {msg}'[:700])
        return 'NOT VERIFIED ' + msg
    c = R._low([sys.executable, '-X', 'utf8', str(R.ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return 'NOT VERIFIED check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if c.returncode or any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated',
                                                'missing_in_force')):
        msg = 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:400]
        R.progress(SLUG, f'{names[0]}..{names[-1]}: NOT VERIFIED {msg}'[:700])
        return 'NOT VERIFIED ' + msg
    for n in names:
        path = _part_path(n)
        acts = json.loads(path.read_text(encoding='utf-8'))['acts']
        nv = sum(len(a['versions']) for a in acts)
        n2 = sum(1 for a in acts if len(a['versions']) > 1)
        days = sorted(v['from'] for a in acts for v in a['versions'])
        what = (f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} ({n2} with the current text from the law\'s '
                f'page appended to the open-data text)' if path.parent == STAGE else
                f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} (laws of 2020 on, current text from each '
                f'law\'s page)')
        line = (f'{what} from {SRC["short"]}: letters and digits of every version equal the source text (independent '
                f'lxml reader of the cached open-data member or page akm) and every unit is found in order; scratch '
                f'build of verified parts + parts {names[0]}..{names[-1]}: check.py {res.get("versions")} versions, '
                f'0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
        if path.parent == STAGE:
            os.replace(path, d / f'{n}.json')
        ptmp = d / f'{n}.ptmp'
        ptmp.write_text(line + '\n', encoding='utf-8', newline='\n')
        os.replace(ptmp, d / f'{n}.PUBLISH')
        R.progress(SLUG, f'{n}: PUBLISH {line}')
    R.write_docs(SLUG, SRC, docs_date)
    R._rm(tmp)
    R._rm(build)
    return f'PUBLISH {len(names)} parts ({names[0]}..{names[-1]}), check.py {res.get("versions")} versions clean'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd = sys.argv[1]
    if cmd == 'fetch':
        fetch()
    elif cmd == 'parse':
        dd = sys.argv[2]
        pl = plan()
        only = set(sys.argv[3:])
        for name, members in pl:
            if only and name not in only:
                continue
            if (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
                continue
            R.write_part(SLUG, name, build_part(name, members, dd))
            R.say(name, len(members))
    elif cmd == 'publish':
        dd = sys.argv[2]
        names = sys.argv[3:] or R.part_names(SLUG)
        for name in names:
            if (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
                continue
            R.wait_cpu()
            print(name, R.publish(SLUG, SRC, name, dd, letters_check)[:400], flush=True)
    elif cmd == 'publishall':
        dd = sys.argv[2]
        todo = [n for n in R.part_names(SLUG) if not (R.folder(SLUG) / 'corpus.d' / f'{n}.PUBLISH').exists()]
        print(publish_batch(dd, todo), flush=True)
    elif cmd == 'refresh':
        try:
            refresh_job()
        except it_fetch.Stopped as e:
            rlog(f'STOPPED: {e}')
            raise
    elif cmd == 'stage':
        out = stage(sys.argv[2])
        print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 12 else f'{len(v)} items') for k, v in
                          out.items()}, ensure_ascii=False, indent=1))
    elif cmd == 'republish':   # republish <docs-date> <batch size> : every staged part, then every new part
        dd, size = sys.argv[2], int(sys.argv[3])
        todo = [q.stem for q in sorted(STAGE.glob('*.json'))] + \
            [n for n in R.part_names(SLUG) if n.startswith(NEW_PREFIX)
             and not (R.folder(SLUG) / 'corpus.d' / f'{n}.PUBLISH').exists()]
        for i in range(0, len(todo), size):
            r = republish(dd, todo[i:i + size])
            print(r[:500], flush=True)
            if not r.startswith('PUBLISH'):
                break
    elif cmd == 'letters':
        pr = letters_check(SLUG, sys.argv[2])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
