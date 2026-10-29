"""Builds a git history of Luxembourg law from Legilux, in which every amending law is one commit, dated the day it took
effect.

    python -X utf8 scripts/luxembourg-law/build.py [--repo ../luxembourg-law] [--today 2026-10-28] [--offline]

Legilux, the official journal of the Grand Duchy (Service central de législation, Ministère d'État), publishes every
consolidated version of an act as linked data (the JOLux ontology, queried over SPARQL) with the day each version applies
from, and each version as Akoma Ntoso XML. Each consolidated version also carries its own account of how it came to be:
a lifecycle (every amending law with the day it took effect), the passive modifications (which law changed which
article) and modification notes printed in the text. We take every version of the acts below, compare consecutive
versions article by article, and credit each change to the amending law the version's own data names for that article
and that day. Nothing is credited by guesswork: a change no law explains is committed apart and labelled as such.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from lxml import etree

from reproduce import write_manifest, write_reproduce

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = HERE / '.cache'
SPARQL = 'https://data.legilux.public.lu/sparqlendpoint'
DATA = 'http://data.legilux.public.lu/'
ELI = DATA + 'eli/'
FRA = 'http://publications.europa.eu/resource/authority/language/FRA'
XML_FORMAT = DATA + 'resource/authority/user-format/xml'
JOLUX = 'PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>\n'
USER_AGENT = 'lexifina-watch/1.0 (+https://lexifina.com; corpus@lexifina.com)'
THROTTLE = 1.0   # seconds between requests to Legilux

# The acts in the record: the ELI of the act (its complex work), a short slug for the repository's folders.
ACTS = [
    {'eli': 'etat/leg/constitution/1868/10/17/n1', 'slug': 'constitution', 'short': 'Constitution'},
    {'eli': 'etat/leg/loi/2020/07/17/a624', 'slug': 'loi-covid-19', 'short': 'Loi Covid-19'},
]


# ---------------------------------------------------------------- fetching

REQUESTS: list[dict] = []   # every request the build made, for REPRODUCE.md
_last = [0.0]


def _download(url: str, data: bytes | None, headers: dict) -> bytes:
    """One polite request: urllib first, curl if the machine's certificate store rejects the chain."""
    wait = THROTTLE - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()
    try:
        req = urllib.request.Request(url, data=data, headers={'User-Agent': USER_AGENT, **headers})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.URLError as e:
        if 'CERTIFICATE' not in str(e).upper():
            raise
    cmd = ['curl', '-sSfL', '--max-time', '120', '-A', USER_AGENT]
    for k, v in headers.items():
        cmd += ['-H', f'{k}: {v}']
    if data is not None:
        cmd += ['--data-binary', '@-']
    out = subprocess.run(cmd + [url], input=data, capture_output=True)
    if out.returncode:
        raise OSError(f'curl {url}: {out.stderr.decode(errors="replace")}')
    return out.stdout


def fetch(url: str, data: bytes | None = None, headers: dict | None = None, offline: bool = False) -> bytes:
    """GET or POST with a file cache keyed by the request, so a rebuild reads the same bytes."""
    key = hashlib.sha256(url.encode() + (data or b'')).hexdigest()[:32]
    path = CACHE / key
    REQUESTS.append({'url': url, 'query': data is not None, 'file': path})
    if path.exists():
        return path.read_bytes()
    if offline:
        raise SystemExit(f'not cached: {url}')
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    for attempt in range(4):
        try:
            body = _download(url, data, headers or {})
            path.write_bytes(body)
            return body
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError


def sparql(query: str, offline: bool = False) -> list[dict]:
    body = urllib.parse.urlencode({'query': JOLUX + query}).encode()
    raw = fetch(SPARQL, body, {'Accept': 'application/sparql-results+json',
                               'Content-Type': 'application/x-www-form-urlencoded'}, offline)
    return [{k: v['value'] for k, v in b.items()} for b in json.loads(raw)['results']['bindings']]


def https(url: str) -> str:
    return url.replace('http://data.legilux.public.lu/', 'https://data.legilux.public.lu/')


# ---------------------------------------------------------------- the act's versions

def versions_of(act: dict, offline: bool) -> list[dict]:
    """Every consolidated version with a French XML file, oldest first, with the days it applies from and to."""
    rows = sparql(f'''SELECT ?c ?from ?to ?pub ?url WHERE {{
      ?c a jolux:Consolidation ; jolux:isMemberOf <{ELI}{act['eli']}> ; jolux:dateApplicability ?from ; jolux:isRealizedBy ?e .
      OPTIONAL {{ ?c jolux:dateEndApplicability ?to }}
      OPTIONAL {{ ?c jolux:publicationDate ?pub }}
      ?e jolux:language <{FRA}> ; jolux:isEmbodiedBy ?m .
      ?m jolux:userFormat <{XML_FORMAT}> ; jolux:isExemplifiedBy ?url .
    }} ORDER BY ?from''', offline)
    out: dict[str, dict] = {}
    for r in rows:
        out[r['from']] = {'from': r['from'], 'to': r.get('to'), 'eli': r['c'], 'url': https(r['url']), 'published': r.get('pub')}
    return [out[k] for k in sorted(out)]


def all_versions(act: dict, offline: bool) -> list[str]:
    """Every consolidated version, with or without XML, so the record can say which ones it could not read."""
    rows = sparql(f'''SELECT ?from WHERE {{ ?c a jolux:Consolidation ; jolux:isMemberOf <{ELI}{act['eli']}> ;
      jolux:dateApplicability ?from }}''', offline)
    return sorted({r['from'] for r in rows})


def act_meta(act: dict, offline: bool) -> dict:
    jo = f'{ELI}{act["eli"]}/jo'
    rows = sparql(f'''SELECT ?p ?o WHERE {{ {{ <{jo}> ?p ?o }} UNION {{ <{jo}> jolux:isRealizedBy ?e . ?e jolux:language <{FRA}> ;
      ?p ?o FILTER(?p IN (jolux:title, jolux:titleShort)) }} }}''', offline)
    props: dict[str, str] = {}
    for r in rows:
        props.setdefault(r['p'].rsplit('#', 1)[-1], r['o'])
    return {'jo': jo, 'title': props.get('title'), 'short': props.get('titleShort'), 'adopted': props.get('dateDocument'),
            'published': props.get('publicationDate'), 'inForce': props.get('dateEntryInForce')}


# ---------------------------------------------------------------- reading the XML

AKN = 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13'
SCL = 'http://www.scl.lu'
NS = {'a': AKN, 'scl': SCL}
BLOCKS = {'article', 'quotedStructure', 'mod', 'paragraph', 'subparagraph', 'alinea', 'content', 'p', 'ol', 'ul', 'li',
          'list', 'point', 'intro', 'wrapUp', 'blockList', 'item', 'listIntroduction', 'listWrapUp', 'embeddedStructure',
          'blockContainer', 'table', 'tr'}


def tag(e) -> str:
    return etree.QName(e).localname if isinstance(e.tag, str) else ''


def is_scl(e) -> bool:
    return isinstance(e.tag, str) and etree.QName(e).namespace == SCL


def clean(s: str) -> str:
    """Spacing normalised and the publisher's invisible characters dropped. Nothing else about the words is changed."""
    s = ''.join(ch for ch in s if unicodedata.category(ch) not in ('Cf', 'Cc') or ch == '\n')
    return re.sub(r'\s+', ' ', s).strip()


def struck(x) -> bool:
    """Text the consolidated version prints struck through: repealed, kept only to show what was there."""
    return tag(x) == 'del' or x.get('style') == 'del' if isinstance(x.tag, str) else False


def inline(e, stop=frozenset()) -> str:
    """The words of an element: struck-through (repealed) text, notes and metadata left out, superscripts joined to the
    word before them ("1<sup>er</sup>" reads "1er"). Elements named in `stop` are left out (they make their own lines)."""
    def walk(x) -> str:
        t = tag(x)
        if is_scl(x) or struck(x) or t in ('noteRef', 'authorialNote') or t in stop:
            return ''
        if t == 'br':
            return ' '
        acc = x.text or ''
        for c in x:
            acc = join(acc, c, walk(c))
        return acc
    return walk(e)


def join(acc: str, c, words: str) -> str:
    """Appends a child's words and the text after it. A superscript joins the word before it, as printed: the XML
    has "1<sup>er</sup>" in some versions and "1 <sup>er</sup>" in others, which is not a change to the law."""
    if tag(c) == 'sup' and words.strip():
        acc, words = acc.rstrip(), words.lstrip()
    return acc + words + (c.tail or '')


ROMAN = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi', 'xvii',
         'xviii', 'xix', 'xx', 'xxi', 'xxii', 'xxiii', 'xxiv', 'xxv']


def marker(symbol: str | None, n: int) -> str:
    """The number printed before a list item, from the list's own symbol ("1°", "a)", "i)") and the item's position."""
    if not symbol:
        return ''
    m = re.search(r'1|a|A|i|I', symbol)
    if not m:
        return symbol.strip()
    c = m.group(0)
    if c == '1':
        v = str(n)
    elif c in 'aA':
        v = chr(ord(c) + n - 1) if n <= 26 else str(n)
    else:
        v = ROMAN[n - 1] if n <= len(ROMAN) else str(n)
        v = v.upper() if c == 'I' else v
    return (symbol[:m.start()] + v + symbol[m.end():]).strip()


LINE_BLOCKS = {'p', 'ol', 'ul', 'embeddedStructure', 'quotedStructure', 'article', 'paragraph', 'alinea', 'content',
               'blockList', 'table'}


def lines_of(art) -> list[dict]:
    """An article's body as lines: each alinéa, each paragraph's alinéa and each list item is one line, with its
    paragraph number ("(1)") or list marker ("1°", "a)") in front of its first line."""
    out: list[dict] = []

    def emit(text: str, lvl: int, pending: list):
        t = clean(text)
        if not t:
            return
        line = {'level': lvl, 'text': t}
        if pending[0]:
            line['text'] = f'{pending[0]} {t}'
            if len(pending) > 1:
                line['marker'] = pending[0]   # printed by the publisher from the list's symbol, not in the XML's words
            pending[0] = ''
        out.append(line)

    def mixed(x, lvl: int, pending: list):
        """Text with blocks inside it (a list in a sentence, a quoted article in a list item), in document order:
        the words up to a block are one line, the block makes its own lines, the words after it another line."""
        buf = x.text or ''
        for c in x:
            if tag(c) in LINE_BLOCKS:
                emit(buf, lvl, pending)
                buf = c.tail or ''
                walk(c, lvl, pending if tag(c) == 'p' else [''])
            else:
                buf = join(buf, c, inline(c))
        emit(buf, lvl, pending)

    def walk(x, lvl: int, pending: list):
        t = tag(x)
        if is_scl(x) or struck(x) or t in ('noteRef', 'authorialNote', 'num', 'heading'):
            return
        if t == 'article':
            # An article quoted inside an amending provision ("L'article 4 est remplacé comme suit : Art. 4. ...").
            num = x.find('a:num', NS)
            emit(inline(num) if num is not None else '', lvl, pending)
            for c in x:
                walk(c, lvl, [''])
            return
        if t in ('paragraph', 'subparagraph', 'point'):
            num = x.find('a:num', NS)
            mine = [clean(inline(num)) if num is not None else '']
            for c in x:
                walk(c, lvl, mine)
            return
        if t in ('ol', 'ul'):
            symbol = x.get(f'{{{SCL}}}symbol')
            n = int(x.get(f'{{{SCL}}}start') or 1)
            for li in x:
                if tag(li) != 'li':
                    walk(li, lvl + 1, [''])
                    continue
                # The item's own number where it has one ("2°bis"), else the list's numbering; a list of dashes or
                # of "custom" symbols has no printed number of its own.
                own = (li.get(f'{{{SCL}}}symbol') or '').strip()
                mk = [own or (marker(symbol, n) if t == 'ol' and symbol not in (None, 'custom', 'dash') else ''), 'generated']
                start = len(out)
                if not struck(li):
                    mixed(li, lvl + 1, mk)
                if len(out) > start and not out[start].get('marker'):
                    # A dash typed in front of an item is the list's bullet, which the file shows as "- ".
                    m = re.match(r'[-–—]\s+', out[start]['text'])
                    if m:
                        out[start]['bullet'] = m.group(0)
                        out[start]['text'] = out[start]['text'][m.end():]
                # A struck-through item keeps its place in the count: the official numbering does not move.
                n += 1
            return
        if t == 'p' or t not in BLOCKS:
            mixed(x, lvl, pending)
            return
        for c in x:
            walk(c, lvl, pending)

    for c in art:
        walk(c, 0, [''])
    return out


def unit_key(art) -> str:
    """The article's identifier in Legilux's ELI ("art_1er", "art_32bis"): the element's id, without the date Legilux
    appends to a repealed article kept in the text ("art_121_19990612"). The ELI in the article's own metadata block is
    not used: in some versions it names another article (Art. 109 of the 1999 text carries the address of Art. 122)."""
    return re.sub(r'_\d{8}$', '', art.get('id') or art.get('eId') or 'art')


def section_path(art) -> list[str]:
    out = []
    for anc in art.iterancestors():
        if tag(anc) == 'body':
            break
        if tag(anc) in ('book', 'part', 'title', 'chapter', 'section', 'subsection', 'division', 'level'):
            num, head = anc.find('a:num', NS), anc.find('a:heading', NS)
            s = ' '.join(x for x in (clean(inline(num)) if num is not None else '',
                                     clean(inline(head)) if head is not None else '') if x)
            if s:
                out.append(s)
    return list(reversed(out))


def law_id(href: str | None) -> str | None:
    """'/eli/etat/leg/loi/2023/01/17/a29/jo' -> 'loi/2023/01/17/a29'."""
    if not href:
        return None
    m = re.search(r'(?:eli/)?etat/leg/(.+?)(?:/jo)?/?$', href)   # some versions write the source without "eli/"
    return m.group(1) if m else None


REPEALED = re.compile(r'^\(?\s*(?:abrog[ée]e?s?|supprim[ée]e?s?)\b[^()]*\)?\.?$|^\(\s*(?:\.\.\.|…)\s*\)$|^(?:\.\.\.|…)$', re.I)


def read_version(xml: bytes) -> dict:
    """One consolidated version: its articles in force (struck-through ones left out), the amending laws its own data
    names (lifecycle, passive modifications, modification notes) and which modifications touch each article."""
    root = etree.fromstring(xml)
    body = root.find('.//a:body', NS)
    units: dict[str, dict] = {}
    order: list[str] = []
    # Legilux marks the words a law wrote with a pair of markers, <mod class="mod-start" for="#pm12"/> … mod-end. A pair
    # can open on a chapter's heading and close after its last article, or span the whole text, so the modifications
    # that cover an article are those open where it starts, plus those inside it.
    articles: list[tuple] = []
    open_mods: set[str] = set()
    for x in body.iter():
        if tag(x) == 'mod' and x.get('for'):
            (open_mods.add if x.get('class') == 'mod-start' else open_mods.discard)(x.get('for').lstrip('#'))
        elif tag(x) == 'article' and not any(tag(a) == 'article' for a in x.iterancestors()):
            articles.append((x, set(open_mods)))
    for art, covering in articles:
        key = unit_key(art)
        num, head = art.find('a:num', NS), art.find('a:heading', NS)
        lines = [] if art.get('style') == 'del' else lines_of(art)
        if lines and REPEALED.match(' '.join(l['text'] for l in lines)):
            lines = []   # "Art. 21. (abrogé)": the consolidated text prints the number of a repealed article
        mods = ({m.get('for', '').lstrip('#') for m in art.iter(f'{{{AKN}}}mod')} | covering) - {''}
        u = {'key': key, 'id': art.get('id'), 'ancestors': [a.get('id') for a in art.iterancestors() if a.get('id')],
             'label': clean(inline(num)) if num is not None else key,
             'heading': clean(inline(head)) if head is not None else '', 'section': section_path(art),
             'lines': lines, 'mods': mods}
        if key in units:
            # A repealed article stays in the consolidated text, struck through, beside the one now under its number.
            old = units[key]
            if old['lines'] and lines:
                raise SystemExit(f'two articles in force under {key}')
            keep = old if old['lines'] else u
            keep['mods'] = old['mods'] | mods
            units[key] = keep
            continue
        units[key] = u
        order.append(key)
    refs = {r.get('id'): {'law': law_id(r.get('href')), 'title': r.get('showAs')} for r in root.iterfind('.//a:references/*', NS)}
    lifecycle = [{'date': e.get('date'), 'law': refs.get((e.get('source') or '').lstrip('#'), {}).get('law'), 'type': e.get('type')}
                 for e in root.iterfind('.//a:lifecycle/a:eventRef', NS)]
    tmods = {}
    for tm in root.iterfind('.//a:passiveModifications/a:textualMod', NS):
        src = tm.find('a:source', NS)
        tmods[tm.get('id')] = {'type': tm.get('type'), 'law': law_id(src.get('href') if src is not None else ''),
                               'dest': [d.get('href', '').lstrip('#') for d in tm.findall('a:destination', NS) if d.get('href')]}
    notes = {}
    for n in root.iterfind('.//a:notes/a:note', NS):
        ref = n.find('.//a:ref', NS)
        notes[n.get('refersTo')] = {'title': n.get('title'), 'law': law_id(ref.get('href')) if ref is not None else None,
                                    'text': clean(inline(n))}
    return {'units': units, 'order': order, 'refs': refs, 'lifecycle': lifecycle, 'tmods': tmods, 'notes': notes}


# ---------------------------------------------------------------- the sources of one act

# A decision made by hand after reading the data, checked against the data at build time so that a change at Legilux
# stops the build instead of passing silently. On 1 July 2023 four laws of 17 January 2023 revised the Constitution
# together and renumbered it. Legilux's consolidated version of that day credits the whole new text to one modification
# note naming law A 26 (chapter VI). Law A 29, Art. 4, renumbers the articles the four laws revised and provides that
# "le texte figurant en annexe à la présente loi constitue le texte de la Constitution". The record commits the new text
# once, as a labelled replacement credited to A 29, and names the other three laws in the commit.
REPLACEMENTS = {
    ('constitution', '2023-07-01'): {
        'author': 'loi/2023/01/17/a29',
        'laws': ['loi/2023/01/17/a26', 'loi/2023/01/17/a27', 'loi/2023/01/17/a28', 'loi/2023/01/17/a29'],
        'quote': 'art_4',
        'phrase': 'constitue le texte de la Constitution',
    },
}


def jo_xml(eli: str, offline: bool) -> str:
    """The French XML of an act as published in the Mémorial (its "jo" expression)."""
    rows = sparql(f'''SELECT ?f ?url WHERE {{ <{ELI}{eli}/jo> jolux:isRealizedBy ?e . ?e jolux:language <{FRA}> ;
      jolux:isEmbodiedBy ?m . ?m jolux:userFormat ?f ; jolux:isExemplifiedBy ?url }}''', offline)
    urls = sorted(https(r['url']) for r in rows if r['f'].rsplit('/', 1)[-1] in ('xml', 'xml-akomantoso'))
    if not urls:
        raise SystemExit(f'no XML for {eli}/jo')
    return urls[0]


def sources_of(act: dict, meta: dict, offline: bool) -> list[dict]:
    """The act as published in the Mémorial, in force from its own entry-into-force date, then every consolidated
    version with French XML."""
    vers = versions_of(act, offline)
    first = {'from': meta['inForce'], 'to': vers[0]['from'] if vers else None, 'eli': meta['jo'],
             'url': jo_xml(act['eli'], offline), 'published': meta['published'], 'kind': 'original'}
    return [first] + [{**v, 'kind': 'consolidated'} for v in vers]


def law_meta(ids: list[str], offline: bool) -> dict[str, dict]:
    """Title, kind, dates and Mémorial of each law the record names."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 30):
        chunk = ids[i:i + 30]
        values = ' '.join(f'<{ELI}etat/leg/{x}/jo>' for x in chunk)
        rows = sparql(f'''SELECT ?a ?p ?o WHERE {{ VALUES ?a {{ {values} }}
          {{ ?a ?p ?o FILTER(?p IN (jolux:dateDocument, jolux:publicationDate, jolux:dateEntryInForce, jolux:isPartOf,
                                     jolux:typeDocument)) }}
          UNION {{ ?a jolux:isRealizedBy ?e . ?e jolux:language <{FRA}> ; ?p ?o FILTER(?p IN (jolux:title, jolux:titleShort)) }}
        }}''', offline)
        for r in rows:
            key = law_id(r['a'])
            rec = out.setdefault(key, {'id': key})
            name = r['p'].rsplit('#', 1)[-1]
            rec[name] = min(rec[name], r['o']) if name in rec else r['o']
    for x in ids:
        out.setdefault(x, {'id': x})
    return out


MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre',
          'décembre']
KINDS = {'loi': 'Loi', 'constitution': 'Constitution', 'rgd': 'Règlement grand-ducal', 'agd': 'Arrêté grand-ducal'}


def fr_date(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return f'{"1er" if d.day == 1 else d.day} {MONTHS[d.month - 1]} {d.year}'


def law_name(lid: str) -> str:
    """'loi/1919/05/15/n1' -> 'Loi du 15 mai 1919 (n1)': the kind, the date and the last part of its ELI, which tells
    apart the laws of one day."""
    kind, y, m, d, n = lid.split('/')
    if kind == 'constitution':
        return f'Constitution du {fr_date(f"{y}-{m}-{d}")}'
    return f'{KINDS.get(kind, kind.upper())} du {fr_date(f"{y}-{m}-{d}")} ({n})'


def law_email(lid: str) -> str:
    return lid.replace('/', '-') + '@legilux.invalid'


def memorial(rec: dict) -> str:
    m = re.search(r'memorial/(\d{4})/([a-z]*)(\d+)$', rec.get('isPartOf') or '')
    if not m:
        return ''
    return f'Mémorial {m.group(2).upper() + " " if m.group(2) else ""}n° {m.group(3)} de {m.group(1)}'


def eli_url(lid: str) -> str:
    return f'https://legilux.public.lu/eli/etat/leg/{lid}/jo'


# ---------------------------------------------------------------- the record of one act

def text_of(u: dict | None):
    return None if not u or not u['lines'] else (u['heading'], tuple(l['text'] for l in u['lines']))


def spacing_only(a, b) -> bool:
    if a is None or b is None:
        return False
    squash = lambda t: re.sub(r'\s+', '', t[0] + ''.join(t[1]))
    return squash(a) == squash(b)


def build_act(act: dict, offline: bool) -> dict:
    meta = act_meta(act, offline)
    srcs = sources_of(act, meta, offline)
    parsed = []
    for s in srcs:
        xml = fetch(s['url'], offline=offline)
        s['sha256'] = hashlib.sha256(xml).hexdigest()
        parsed.append(read_version(xml))
    # Legilux numbers an act's modifications once ("pm12") and keeps the numbers from version to version; a version can
    # mark text with a modification that only a later version describes, so the map is built from all of them.
    pmlaw: dict[str, str] = {}
    for p in parsed:
        for k, t in p['tmods'].items():
            if t['law']:
                pmlaw[k] = t['law']
        for k, n in p['notes'].items():
            if n['law']:
                pmlaw.setdefault(k, n['law'])
    changes: list[dict] = []
    for i in range(1, len(srcs)):
        prev, cur = parsed[i - 1], parsed[i]
        lo, day = srcs[i - 1]['from'], srcs[i]['from']
        # The laws that took effect between the two versions, by the version's own lifecycle, and the amending laws
        # whose modifications first appear in it.
        window = {e['law'] for e in cur['lifecycle'] if e['law'] and e['date'] and lo < e['date'] <= day and e['type'] != 'generation'}
        # A law the lifecycle dates a day late (Legilux has 2020-05-20 for a text that applies from 2020-05-19) still
        # counts; acts the lifecycle does not list as amendments (the 1918 "déclarations de révision") do not.
        amending = {e['law'] for e in cur['lifecycle'] if e['type'] == 'amendment'}
        window |= {pmlaw[pm] for pm in set(cur['tmods']) - set(prev['tmods']) if pmlaw.get(pm) in amending}
        window.discard(act['eli'].replace('etat/leg/', ''))
        dests: dict[str, set] = {}
        for tm in cur['tmods'].values():
            dests.setdefault(tm['law'], set()).update(re.sub(r'_\d{8}$', '', d) for d in tm['dest'])
        known = {k for p in (prev, cur) for k in p['units']} | {u['id'] for p in (prev, cur) for u in p['units'].values()}
        repl = REPLACEMENTS.get((act['slug'], day))
        if repl and sorted(window) != sorted(repl['laws']):
            raise SystemExit(f'{act["slug"]} {day}: the laws in force that day are now {sorted(window)}; review REPLACEMENTS')
        for k in sorted(set(prev['units']) | set(cur['units'])):
            pu, cu = prev['units'].get(k), cur['units'].get(k)
            a, b = text_of(pu), text_of(cu)
            if a == b:
                continue
            ids = {x for u in (pu, cu) if u for x in (u['id'], k)}
            anc = {x for u in (pu, cu) if u for x in u['ancestors']}
            marks = {pmlaw.get(pm) for pm in ((cu['mods'] if cu else set()) - (pu['mods'] if pu else set()))} & window
            named = {law for law, ds in dests.items() for d in ds
                     if d in ids or any(d.startswith(x + '.') for x in ids) or d in anc} & window
            rec = {'key': k, 'day': day, 'version': i, 'before': a, 'after': b,
                   'unit': cu if b else pu, 'created': a is None, 'repealed': b is None}
            if repl:
                rec.update(kind='replacement', cause=repl['author'], evidence='replacement')
            elif marks | named:
                if len(marks | named) > 1:
                    raise SystemExit(f'{act["slug"]} {day} {k}: several laws mark this article: {sorted(marks | named)}')
                ev = '+'.join(x for x, s in (('marks', marks), ('destination', named)) if s)
                rec.update(kind='law', cause=(marks | named).pop(), evidence=ev)
            elif spacing_only(a, b):
                rec.update(kind='typesetting', cause=None, evidence='spacing')
            elif len(window) == 1 and not (dests.get(next(iter(window))) and dests[next(iter(window))] <= known):
                # One law took effect that day by the version's own lifecycle, and what it says it changed does not
                # rule this article out (a chapter Legilux does not identify, or nothing). Credited by date only.
                rec.update(kind='law', cause=next(iter(window)), evidence='date')
            else:
                rec.update(kind='unexplained', cause=None, evidence='none',
                           window=sorted(window), targets=sorted(d for w in window for d in dests.get(w, ())))
            changes.append(rec)
    return {'act': act, 'meta': meta, 'sources': srcs, 'parsed': parsed, 'changes': changes}


# ---------------------------------------------------------------- the git repository

def git(repo: Path, *args: str, env: dict | None = None, input: str | None = None) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8', env=env, input=input)
    if out.returncode:
        raise SystemExit(f'git {" ".join(args)} failed: {out.stderr}')
    return out.stdout


def last_sunday(year: int, month: int) -> dt.date:
    d = (dt.date(year, month + 1, 1) if month < 12 else dt.date(year + 1, 1, 1)) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def lux_offset(day: dt.date) -> int:
    """Hours ahead of UTC in Luxembourg on a day: summer time from 1977, ending in September until 1995 and in October
    since 1996, starting on the last Sunday of March (the first Sunday of April from 1977 to 1980)."""
    if day.year < 1977:
        return 1
    if day.year <= 1980:
        start = dt.date(day.year, 4, 1) + dt.timedelta(days=(6 - dt.date(day.year, 4, 1).weekday()) % 7)
    else:
        start = last_sunday(day.year, 3)
    end = last_sunday(day.year, 9 if day.year <= 1995 else 10)
    return 2 if start <= day < end else 1


def commit_date(day: str, clamp: int) -> str:
    """Noon in Luxembourg on the day. Git cannot store a date before 1970: those commits are dated 1970-01-01, one
    second apart in order, and the real day is in the In-force trailer and the tags."""
    if day < '1970-01-01':
        return f'@{clamp} +0000'
    d = dt.date.fromisoformat(day)
    off = lux_offset(d)
    stamp = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone(dt.timedelta(hours=off))).timestamp())
    return f'@{stamp} +0{off}00'


def act_path(act: dict) -> str:
    return act['eli'].replace('etat/leg/', '')


def render(u: dict) -> str:
    """One article as a Markdown file: its number (and heading) as the title, then one line per alinéa or list item."""
    out = ['# ' + u['label'] + (f' {u["heading"]}' if u['heading'] else ''), '']
    for l in u['lines']:
        out += [('  ' * (l['level'] - 1) + '- ' + l['text']) if l['level'] else l['text'], '']
    return '\n'.join(out).rstrip() + '\n'


def label(u: dict) -> str:
    return u['label'].rstrip('.').strip()


def unit_order(key: str) -> tuple:
    m = re.fullmatch(r'art_(\d+)(er|re)?([a-z]*)', key)
    if not m:
        return (1, 0, 0, key)
    order = ['', 'bis', 'ter', 'quater', 'quinquies', 'sexies', 'sexties', 'septies', 'octies', 'nonies', 'decies']
    suffix = m.group(3)
    return (0, int(m.group(1)), order.index(suffix) if suffix in order else 99, suffix)


SCL_AUTHOR = ('Service central de législation (Legilux)', 'scl@legilux.invalid')


def quote_of(repl: dict, offline: bool) -> str:
    """The provision of the replacing law that says its annex is the text, quoted from that law's own XML."""
    law = repl['author']
    p = read_version(fetch(jo_xml('etat/leg/' + law, offline), offline=offline))
    u = p['units'][repl['quote']]
    words = ' '.join(l['text'] for l in u['lines'])
    if repl['phrase'] not in words:
        raise SystemExit(f'{law} {repl["quote"]} no longer says "{repl["phrase"]}"; review REPLACEMENTS')
    return f'{label(u)} : {words}'


def write_repo(repo: Path, built: list[dict], laws: dict[str, dict], docs: Path, today: str, offline: bool):
    remote = None
    if (repo / '.git').exists():
        out = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=repo, capture_output=True, text=True)
        remote = out.stdout.strip() or None

    def force(fn, path, _exc):
        os.chmod(path, 0o700)
        fn(path)
    if repo.exists():
        for p in repo.iterdir():
            shutil.rmtree(p, onexc=force) if p.is_dir() else p.unlink()
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'config', 'core.autocrlf', 'false')
    git(repo, 'config', 'core.quotepath', 'false')
    if remote:
        git(repo, 'remote', 'add', 'origin', remote)

    # Events: (day, act, group) -> changes. The group is the law, or the original text, or a labelled kind.
    rank = {'original': 0, 'law': 1, 'replacement': 2, 'typesetting': 3, 'unexplained': 4}
    events: dict[tuple, list] = {}
    for b in built:
        src0 = b['sources'][0]
        events[(src0['from'], b['act']['slug'], 'original', '')] = [
            {'key': k, 'unit': u, 'kind': 'original', 'repealed': False, 'created': True}
            for k, u in b['parsed'][0]['units'].items() if u['lines']]
        for c in b['changes']:
            events.setdefault((c['day'], b['act']['slug'], c['kind'], c['cause'] or ''), []).append(c)
    by_slug = {b['act']['slug']: b for b in built}
    order = sorted(events, key=lambda e: (e[0], e[1], rank[e[2]], e[3]))
    tags: dict[str, str] = {}
    commits: list[dict] = []
    clamp = 0
    future = False
    for ev in order:
        day, slug, kind, cause = ev
        b = by_slug[slug]
        act, short = b['act'], b['act']['short']
        if day > today and not future:
            git(repo, 'checkout', '-q', '-b', 'futur')
            future = True
        items = sorted(events[ev], key=lambda c: unit_order(c['key']))
        base = repo / act_path(act)
        for c in items:
            path = base / f'{c["key"]}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            if c['repealed']:
                path.unlink(missing_ok=True)
            else:
                path.write_text(render(c['unit']), encoding='utf-8', newline='\n')
        git(repo, 'add', '-A')
        if day < '1970-01-01':
            clamp += 1
        src = next(s for s in b['sources'] if s['from'] == day) if kind != 'original' else b['sources'][0]
        labels = ', '.join(label(c['unit']) for c in items)
        affecting = ', '.join(f'{act_path(act)}/{c["key"]}' for c in items)
        if len(items) > 20:
            affecting = (f'{act_path(act)}/ ({sum(1 for c in items if not c["repealed"])} articles written, '
                         f'{sum(1 for c in items if c["repealed"])} removed; listed in the diff)')
        groups = {'Inséré': [c for c in items if c['created']], 'Abrogé': [c for c in items if c['repealed']],
                  'Modifié': [c for c in items if not c['created'] and not c['repealed']]}
        lists = [f'{name} : {", ".join(label(c["unit"]) for c in cs)}' for name, cs in groups.items() if cs]
        trailers = []
        if kind == 'original':
            lid = act_path(act)
            rec = laws.get(lid, {})
            author, email = law_name(lid), law_email(lid)
            title = b['meta']['title'].replace('\\n', ' ').strip()
            msg = [f'{short} : texte d’origine ({author})', '', title, '',
                   f'Le texte tel que publié au Journal officiel (Mémorial), en vigueur le {fr_date(day)} : {len(items)} articles.',
                   'The text as published in the official journal, in force on this day.', '']
            trailers += [f'Adopted: {b["meta"]["adopted"]}', f'Published: {b["meta"]["published"]}' + (f' ({memorial(rec)})' if memorial(rec) else '')]
        elif kind in ('law', 'replacement'):
            rec = laws.get(cause, {})
            author, email = law_name(cause), law_email(cause)
            title = (rec.get('title') or '').replace('\\n', ' ').strip()
            if kind == 'replacement':
                repl = REPLACEMENTS[(slug, day)]
                msg = [f'{short} : texte remplacé, Constitution révisée ({author})', '', title, '',
                       'Texte remplacé. La révision entrée en vigueur ce jour réécrit toute la Constitution et renumérote',
                       'ses articles : un fichier art_N.md après ce commit ne continue pas l’article N d’avant. Quatre lois',
                       'du même jour ont adopté la révision :', '']
                for lid in repl['laws']:
                    msg.append(f'- {law_name(lid)} : {(laws.get(lid, {}).get("title") or "").strip()}')
                msg += ['', f'La {law_name(cause)[0].lower()}{law_name(cause)[1:]} dispose, à son {quote_of(repl, offline)}', '',
                        'Le texte entier est donc attribué à cette loi. La version consolidée de Legilux rattache tout le',
                        'texte à une seule note de modification, qui nomme la loi du 17 janvier 2023 (a26) ; le registre',
                        'ne la suit pas sur ce point.', '',
                        'Replacement. The 2023 revision rewrote and renumbered the whole Constitution. Four laws adopted it;',
                        'the fourth (a29) provides in its Art. 4 that its annex is the text of the Constitution, so the new text',
                        'is credited to it. Legilux credits the whole text to one note naming a26; the record does not.', '']
                trailers += ['Kind: replacement'] + [f'Also-adopted-by: {law_name(x)} <{eli_url(x)}>' for x in repl['laws'] if x != cause]
                trailers.append('Legilux-note: the consolidated version credits the whole text to loi/2023/01/17/a26')
            else:
                msg = [f'{short} : {labels} ({author})', '', title, ''] + lists + ['']
                weak = [c for c in items if c['evidence'] == 'date']
                if weak:
                    msg += [f'Rattachement par la date seulement pour : {", ".join(label(c["unit"]) for c in weak)}. La version',
                            'consolidée de ce jour nomme cette loi comme la seule entrée en vigueur, sans marquer '
                            + ('ces articles.' if len(weak) > 1 else 'cet article.'),
                            'Credited by date only: the version names this law as the only one taking effect that day but does',
                            'not mark ' + ('these articles.' if len(weak) > 1 else 'this article.'), '']
                trailers.append('Evidence: ' + '; '.join(f'{c["key"]} {c["evidence"]}' for c in items))
            if rec.get('dateDocument'):
                trailers.append(f'Adopted: {rec["dateDocument"]}')
            if rec.get('publicationDate'):
                trailers.append(f'Published: {rec["publicationDate"]}' + (f' ({memorial(rec)})' if memorial(rec) else ''))
            if rec.get('dateEntryInForce') and rec['dateEntryInForce'] != day:
                trailers.append(f'Law-in-force: {rec["dateEntryInForce"]} (Legilux metadata of the law; the consolidated text applies from {day})')
        elif kind == 'typesetting':
            author, email = SCL_AUTHOR
            msg = [f'{short} : {labels}, mise en forme (aucune loi)', '',
                   'Le texte consolidé de Legilux ne change ici que par des espaces (par exemple « dusixième » pour',
                   '« du sixième »). Aucune loi n’en est la cause ; le texte est repris tel que publié.', '',
                   'Only the spacing of Legilux’s consolidated text changed. No law is credited; the text is kept as published.', '']
            trailers.append('Kind: typesetting')
        else:
            author, email = SCL_AUTHOR
            w = items[0].get('window') or []
            msg = [f'{short} : {labels}, modification non expliquée (aucune loi)', '',
                   'Le texte consolidé de Legilux change ces articles ce jour-là, mais aucune loi n’y est rattachée : la version',
                   'ne les marque pas, et la loi entrée en vigueur ce jour-là' + (f' ({", ".join(law_name(x) for x in w)})' if w else ''),
                   'ne vise que ' + (', '.join(items[0].get('targets') or []) or 'd’autres dispositions') + '. Le texte est repris tel que publié,',
                   'sans être attribué à une loi.', '',
                   'Legilux’s consolidated text changed these articles on this day, but no law is linked to the change: the',
                   'version marks nothing on them, and the law that took effect that day names other provisions only. The',
                   'text is kept as published and credited to no law.', '']
            trailers.append('Kind: unexplained')
            trailers += [f'Law-that-day: {law_name(x)} <{eli_url(x)}>' for x in w]
        if day < '1970-01-01':
            trailers.append('Date-note: git cannot store dates before 1970; the commit is dated 1970-01-01 and In-force is the real day')
        trailers += [f'In-force: {day}', f'Affecting: {affecting}']
        if kind in ('law', 'replacement'):
            trailers.append(f'Source: {eli_url(cause)}')
        trailers.append(f'Text: {src["eli"]}')
        when = commit_date(day, clamp)
        env = {**os.environ, 'GIT_AUTHOR_NAME': author, 'GIT_AUTHOR_EMAIL': email, 'GIT_AUTHOR_DATE': when,
               'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': 'luxembourg-law@lexifina.com', 'GIT_COMMITTER_DATE': when}
        git(repo, 'commit', '-q', '--allow-empty', '-F', '-', env=env, input='\n'.join(msg + trailers) + '\n')
        head = git(repo, 'rev-parse', 'HEAD').strip()
        tags[f'{slug}/{day}'] = head
        if kind in ('law', 'replacement', 'original'):
            lid = cause or act_path(act)
            tags[lid.split('/')[0] + '/' + '-'.join(lid.split('/')[1:])] = head
        commits.append({'day': day, 'act': slug, 'kind': kind, 'cause': cause, 'articles': [c['key'] for c in items],
                        'evidence': [c.get('evidence') for c in items], 'hash': head})
    for name, head in tags.items():
        git(repo, 'tag', '-f', name, head)
    if future:
        git(repo, 'checkout', '-q', 'main')
    history_tip = git(repo, 'rev-parse', 'HEAD').strip()
    # Documentation, tables, the tools and the record of how the repository was made come last, by Lexifina, dated
    # the --today given to the build (the data's retrieval day), so the same data gives the same hashes.
    for p in sorted(docs.rglob('*')):
        if p.is_file():
            dest = repo / p.relative_to(docs)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    for name in ('build.py', 'reproduce.py', 'check_repo.py'):
        (repo / 'tools' / name).write_bytes((HERE / name).read_bytes())
    write_tables(repo, built, laws, commits, today)
    write_manifest(repo, built, today)
    write_reproduce(repo, built, commits, tags, REQUESTS, today, history_tip)
    git(repo, 'add', '-A')
    when = commit_date(today, 0)
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': 'luxembourg-law@lexifina.com', 'GIT_AUTHOR_DATE': when,
           'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': 'luxembourg-law@lexifina.com', 'GIT_COMMITTER_DATE': when}
    git(repo, 'commit', '-q', '-m', 'Documentation, tableaux, outils et REPRODUCE.md', env=env)
    if future:
        git(repo, 'checkout', '-q', 'futur')
        git(repo, 'merge', '-q', '--no-edit', 'main', env=env)
        git(repo, 'checkout', '-q', 'main')
    return commits, tags, history_tip


def csv_text(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def write_tables(repo: Path, built: list[dict], laws: dict[str, dict], commits: list[dict], today: str):
    rows = []
    for lid in sorted(laws, key=lambda x: (laws[x].get('dateDocument') or '', x)):
        rec = laws[lid]
        mine = [c for c in commits if c['cause'] == lid or (c['kind'] == 'original' and act_path(next(b['act'] for b in built if b['act']['slug'] == c['act'])) == lid)]
        rows.append({'eli': lid, 'nom': law_name(lid), 'titre': (rec.get('title') or '').replace('\\n', ' ').strip(),
                     'adoptee': rec.get('dateDocument', ''), 'publiee': rec.get('publicationDate', ''),
                     'memorial': memorial(rec), 'en_vigueur_selon_legilux': rec.get('dateEntryInForce', ''),
                     'en_vigueur_dans_le_registre': ' '.join(sorted({c['day'] for c in mine})),
                     'articles': ' '.join(sorted({f'{c["act"]}:{k}' for c in mine for k in c['articles']}))})
    (repo / 'lois.csv').write_text(csv_text(rows), encoding='utf-8', newline='\n')
    for b in built:
        act = b['act']
        units: dict[str, dict] = {}
        for p in b['parsed']:
            for k, u in p['units'].items():
                if u['lines']:
                    units[k] = u
        last = b['parsed'][-1]['units']
        out = [f'# {b["meta"]["title"].split(chr(92))[0].strip()}', '',
               f'ELI <{ELI}{act["eli"]}> · {len(b["sources"])} versions, {b["sources"][0]["from"]} to {b["sources"][-1]["from"]}', '',
               '| Article | Section | Changes in the record | Last changed | Now |', '| --- | --- | ---: | --- | --- |']
        for k in sorted(units, key=unit_order):
            cs = [c for c in b['changes'] if c['key'] == k and c['day'] <= today]
            live = bool(last.get(k) and last[k]['lines'])
            u = last[k] if live else units[k]
            name = label(u)
            out.append(f'| {f"[{name}]({k}.md)" if live else name} | {" › ".join(u["section"])} | {len(cs)} | '
                       f'{cs[-1]["day"] if cs else ""} | {"in force" if live else "repealed"} |')
        (repo / act_path(act) / 'README.md').write_text('\n'.join(out) + '\n', encoding='utf-8', newline='\n')


# ---------------------------------------------------------------- main

def build_all(offline: bool) -> tuple[list[dict], dict[str, dict]]:
    built = [build_act(a, offline) for a in ACTS]
    ids = sorted({c['cause'] for b in built for c in b['changes'] if c['cause']}
                 | {x for r in REPLACEMENTS.values() for x in r['laws']} | {act_path(b['act']) for b in built})
    return built, law_meta(ids, offline)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(ROOT.parent / 'luxembourg-law'))
    ap.add_argument('--offline', action='store_true', help='read only the cache; fail on anything not cached')
    ap.add_argument('--today', default=dt.date.today().isoformat(),
                    help='the data\'s retrieval day: dates the documentation commit and splits main from futur')
    args = ap.parse_args()
    built, laws = build_all(args.offline)
    for b in built:
        kinds = {}
        for c in b['changes']:
            kinds[c['kind'] + ('/' + c['evidence'] if c['kind'] == 'law' else '')] = kinds.get(c['kind'] + ('/' + c['evidence'] if c['kind'] == 'law' else ''), 0) + 1
        print(f'{b["act"]["slug"]}: {len(b["sources"])} texts {b["sources"][0]["from"]}..{b["sources"][-1]["from"]}, '
              f'{len(b["changes"])} article changes {dict(sorted(kinds.items()))}')
    commits, tags, tip = write_repo(Path(args.repo), built, laws, HERE / 'repo', args.today, args.offline)
    print(f'repo: {len(commits)} history commits + 1 documentation commit, {len(tags)} tags, history tip {tip} -> {args.repo}')


if __name__ == '__main__':
    main()
