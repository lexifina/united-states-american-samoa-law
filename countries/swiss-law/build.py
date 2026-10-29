"""Reads one Swiss federal act from Fedlex into its articles, versions, changes and authors: the core of the record behind
lexifina.com/watch/swiss-law and the git repository in which every amending act is one commit, dated the day it took
effect. fetch_all.py fills the cache and bulk.py builds the whole record with these functions.

Fedlex (the Federal Chancellery's publication platform) publishes every consolidated version of each act in the
Classified Compilation (SR) as linked data (the JOLux ontology, queried over SPARQL) with the day each version applies
from. Since 2021 each version is also published as Akoma Ntoso XML, and some acts have XML for earlier versions too. We
take every XML version of the acts below, compare consecutive versions provision by provision, and credit each change to
the amending act in the Official Compilation (AS) that made it. Two official sources name that act: Fedlex's impact
records (which act changed which article, in force on which day) and the footnotes printed under each amended provision
("Fassung gemäss …", "Eingefügt durch …", "Angenommen in der Volksabstimmung vom …"). The footnotes also credit text
written before the first XML version, paragraph by paragraph, so the record knows who wrote the oldest text it holds.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
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


ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent / '.cache'
SPARQL = 'https://fedlex.data.admin.ch/sparqlendpoint'
ELI = 'https://fedlex.data.admin.ch/eli/'
AKN = {'a': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'}
JOLUX = 'PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>\n'
DEU = 'http://publications.europa.eu/resource/authority/language/DEU'
ENG = 'http://publications.europa.eu/resource/authority/language/ENG'

# The acts in the record: SR number, Fedlex ELI of the act, a short slug for URLs and the repository's folders.
ACTS = [
    {'sr': '101', 'eli': 'cc/1999/404', 'slug': 'bv'},
    {'sr': '235.1', 'eli': 'cc/2022/491', 'slug': 'dsg'},
    {'sr': '281.1', 'eli': 'cc/11/529_488_529', 'slug': 'schkg'},
]


# ---------------------------------------------------------------- fetching

REQUESTS: list[dict] = []   # every request the build made, for REPRODUCE.md


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
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'lexifina-watch/1.0', **(headers or {})})
            with urllib.request.urlopen(req, timeout=300 if data else 120) as r:
                body = r.read()
            path.write_bytes(body)
            return body
        except Exception:
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    raise AssertionError


def sparql(query: str, offline: bool = False) -> list[dict]:
    body = urllib.parse.urlencode({'query': JOLUX + query}).encode()
    raw = fetch(SPARQL, body, {'Accept': 'application/sparql-results+json', 'Content-Type': 'application/x-www-form-urlencoded'}, offline)
    return [{k: v['value'] for k, v in b.items()} for b in json.loads(raw)['results']['bindings']]


# ---------------------------------------------------------------- the act's versions

def versions_of(act: dict, offline: bool) -> list[dict]:
    """Every consolidated version with a German XML file, oldest first, with the days it applies from and to."""
    rows = sparql(f'''SELECT ?c ?from ?to ?url WHERE {{
      ?c jolux:isMemberOf <{ELI}{act['eli']}> ; jolux:dateApplicability ?from ; jolux:isRealizedBy ?e .
      OPTIONAL {{ ?c jolux:dateEndApplicability ?to }}
      ?e jolux:language <{DEU}> ; jolux:isEmbodiedBy ?m .
      ?m jolux:userFormat <https://fedlex.data.admin.ch/vocabulary/user-format/xml> ; jolux:isExemplifiedBy ?url .
    }} ORDER BY ?from''', offline)
    out: dict[str, dict] = {}
    for r in rows:
        out[r['from']] = {'from': r['from'], 'to': r.get('to'), 'eli': r['c'], 'url': r['url']}
    return [out[k] for k in sorted(out)]


def act_meta(act: dict, offline: bool) -> dict:
    rows = sparql(f'''SELECT ?p ?o WHERE {{ {{ <{ELI}{act['eli']}> ?p ?o }} UNION
      {{ <{ELI}{act['eli']}> jolux:isRealizedBy ?e . ?e jolux:language ?lang ; ?p ?o .
         FILTER(?p IN (jolux:title, jolux:titleShort)) BIND(STR(?lang) AS ?l) FILTER(?lang IN (<{DEU}>, <{ENG}>)) }} }}''', offline)
    # The second branch mixes languages; ask for each language's title separately.
    titles = {}
    for lang, code in ((DEU, 'de'), (ENG, 'en')):
        t = sparql(f'''SELECT ?t ?s WHERE {{ <{ELI}{act['eli']}> jolux:isRealizedBy ?e . ?e jolux:language <{lang}> ; jolux:title ?t .
          OPTIONAL {{ ?e jolux:titleShort ?s }} }}''', offline)
        if t:
            titles[code] = {'title': t[0]['t'], 'short': t[0].get('s')}
    props = {r['p'].rsplit('#', 1)[-1]: r['o'] for r in rows}
    return {
        'title': titles.get('de', {}).get('title'), 'short': titles.get('de', {}).get('short'),
        'titleEn': titles.get('en', {}).get('title'), 'shortEn': titles.get('en', {}).get('short'),
        'adopted': props.get('dateDocument'), 'inForce': props.get('dateEntryInForce'),
        'basicAct': props.get('basicAct'),
    }


def impacts_of(act: dict, offline: bool) -> list[dict]:
    """Fedlex's own record of which act changed which article of this act, and the day it took effect."""
    # The impacts point at the act's subdivisions (an article, or "text" for the whole act). A filter on the target's
    # address scans every impact in Fedlex and the endpoint's firewall answers 400, so we go through the subdivisions.
    rows = sparql(f'''SELECT ?to ?src ?d ?t WHERE {{ ?to jolux:legalResourceSubdivisionIsPartOf <{ELI}{act['eli']}> .
      ?i jolux:impactToLegalResource ?to ; jolux:impactFromLegalResource ?src ; jolux:legalResourceImpactHasType ?t .
      OPTIONAL {{ ?i jolux:legalResourceImpactHasDateEntryInForce ?d }} }}''', offline)
    out, seen = [], set()
    for r in rows:
        m = re.match(re.escape(ELI) + r'(oc/\d{4}/[^/]+)', r['src'])
        target = r['to'][len(ELI + act['eli']) + 1:]
        key = (target, m.group(1) if m else None, r.get('d'))
        if not m or key in seen:
            continue
        seen.add(key)
        out.append({'target': target, 'as': m.group(1), 'date': r.get('d'), 'type': r['t'].rsplit('/', 1)[-1]})
    return out


def amending_acts(ids: list[str], offline: bool) -> dict[str, dict]:
    """Title, dates and AS citation of each act in the Official Compilation that the record names."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        values = ' '.join(f'<{ELI}{x}>' for x in chunk)
        rows = sparql(f'''SELECT ?a ?p ?o WHERE {{ VALUES ?a {{ {values} }}
          {{ ?a ?p ?o FILTER(?p IN (jolux:dateDocument, jolux:publicationDate, jolux:dateEntryInForce, jolux:typeDocument)) }}
          UNION {{ ?a jolux:isRealizedBy ?e . ?e jolux:language <{DEU}> ; ?p ?o FILTER(?p IN (jolux:title, jolux:titleShort)) }}
        }}''', offline)
        for r in rows:
            key = r['a'][len(ELI):]
            rec = out.setdefault(key, {'id': key})
            name = r['p'].rsplit('#', 1)[-1]
            if name == 'publicationDate':
                rec['published'] = min(rec.get('published', r['o']), r['o'])
            else:
                rec[name] = r['o']
    # The kind of act in English ("Federal act", "Federal decree"), from Fedlex's own vocabulary.
    types = sorted({r['typeDocument'] for r in out.values() if r.get('typeDocument')})
    if types:
        rows = sparql('PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\nSELECT ?t ?l WHERE { VALUES ?t { ' + ' '.join(f'<{t}>' for t in types)
                      + ' } ?t skos:prefLabel ?l FILTER(LANG(?l) = "en") }', offline)
        names = {r['t']: r['l'] for r in rows}
        for rec in out.values():
            t = rec.pop('typeDocument', None)
            if t in names:
                rec['type'] = names[t]
            # Fedlex files an accepted popular initiative under a notice type; it is the initiative itself.
            if (rec.get('title') or '').startswith('Eidgenössische Volksinitiative'):
                rec['type'] = 'Popular initiative accepted by the people and the cantons'
    return out


# ---------------------------------------------------------------- reading the XML

def tag(e) -> str:
    return etree.QName(e).localname if isinstance(e.tag, str) else ''


def text_of(e) -> str:
    """The words of an element without its footnotes, with spacing normalised."""
    def walk(x) -> str:
        t = tag(x)
        if t == 'authorialNote':
            return ''
        if t == 'br':
            return ' '
        if t == 'sup' and re.fullmatch(r'\s*\d+\)\s*', x.xpath('string()')):
            return ''   # a footnote marker ("OR<sup>1)</sup>") in versions converted from the old format
        # "a<sup>bis</sup>" reads "abis" in the official text, so superscripts join the word before them.
        return (x.text or '') + ''.join(walk(c) + (c.tail or '') for c in x)
    s = walk(e)
    s = ''.join(ch for ch in s if unicodedata.category(ch) not in ('Cf', 'Cc') or ch in '\n')
    # The publisher's typesetting varies between versions ("..." and "…" for a repealed provision), which is not a
    # change to the law.
    s = s.replace('\u00a0', ' ').replace('...', '…').replace('[tab]', ' ')
    return re.sub(r'\s+', ' ', s).strip()


AS_REF = re.compile(re.escape(ELI) + r'(oc/\d{4}/[^/"#?\s]+)')
MONTHS_DE = {'jan': 1, 'febr': 2, 'feb': 2, 'märz': 3, 'april': 4, 'apr': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'aug': 8,
             'sept': 9, 'sep': 9, 'okt': 10, 'nov': 11, 'dez': 12}
DATE_DE = re.compile(r'(\d{1,2})\.\s*([A-Za-zä]+)\.?\s*(\d{4})')


def de_date(s: str) -> str | None:
    m = DATE_DE.search(s)
    if not m:
        return None
    mon = MONTHS_DE.get(m.group(2).lower().rstrip('.'))
    return f'{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}' if mon else None


EVENT = re.compile(r'(Fassung gemäss|Eingefügt durch|Aufgehoben durch|Aufgehoben in der Volksabstimmung|Angenommen in der Volksabstimmung|'
                   r'Berichtigt von|Berichtigt durch|Ausdruck gemäss|Bezeichnung gemäss|Satz eingefügt|Die Berichtigung)')


def note_events(note) -> list[dict]:
    """A footnote as the events it records, in order: who wrote or repealed the provision, and when it took effect."""
    full = re.sub(r'\s+', ' ', note.xpath('string()')).strip()
    hrefs = [(m.start(), m.group(1)) for m in ()]
    # Find each AS reference's position in the note's plain text by walking the refs in order.
    refs = []
    cursor = 0
    for r in note.iter('{%s}ref' % AKN['a']):
        m = AS_REF.match(r.get('href', ''))
        label = re.sub(r'\s+', ' ', r.xpath('string()')).strip()
        at = full.find(label, cursor) if label else -1
        if at >= 0:
            cursor = at + len(label)
        if m:
            refs.append((at, m.group(1), label))
    starts = [(m.start(), m.group(1)) for m in EVENT.finditer(full)]
    events = []
    for i, (at, word) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(full)
        chunk = full[at:end]
        kind = ('repealed' if word.startswith('Aufgehoben') else 'corrected' if 'Berichtig' in word
                else 'inserted' if word.startswith('Eingefügt') or word.startswith('Satz eingefügt') else 'worded')
        as_ids = [x[1] for x in refs if at <= x[0] < end]
        labels = [x[2] for x in refs if at <= x[0] < end]
        in_force = None
        m = re.search(r'(?:in Kraft seit|mit Wirkung seit|in Kraft ab|in Kraft am)\s+([^,;()]+)', chunk)
        if m:
            in_force = de_date(m.group(1))
        vote = None
        m = re.search(r'Volksabstimmung vom\s+([^,;()]+)', chunk)
        if m:
            vote = de_date(m.group(1))
        events.append({'kind': kind, 'as': as_ids[0] if as_ids else None, 'asLabel': labels[0] if labels else None,
                       'inForce': in_force, 'vote': vote, 'text': chunk.strip()})
    if not events and AS_REF.search(etree.tostring(note, encoding='unicode')) and full.startswith('AS '):
        events.append({'kind': 'worded', 'as': refs[0][1] if refs else None, 'asLabel': refs[0][2] if refs else None,
                       'inForce': None, 'vote': None, 'text': full})
    return events


def own_notes(e) -> list:
    """Footnotes attached to this element's number or heading (not to its children)."""
    out = []
    for c in e:
        if tag(c) in ('num', 'heading'):
            out.extend(c.iter('{%s}authorialNote' % AKN['a']))
    return out


def inline(e) -> list[dict]:
    """Footnotes set inside a line's words (after an inserted phrase), which record who wrote that phrase. Notes that
    only cite another act ("SR 220") carry no event and drop out."""
    return [ev for n in e.iter('{%s}authorialNote' % AKN['a']) for ev in note_events(n)]


def unit_key(eid: str) -> str:
    m = re.fullmatch(r'art_(\d+)(?:_([a-z]+))?', eid)
    if m:
        return m.group(1) + (m.group(2) or '')
    return re.sub(r'[^a-z0-9]+', '-', eid.lower()).strip('-')


def unit_order(key: str) -> tuple:
    m = re.fullmatch(r'(\d+)([a-z]*)', key)
    if m:
        suffix = {'': 0, 'bis': 2, 'ter': 3, 'quater': 4, 'quinquies': 5, 'sexies': 6, 'septies': 7, 'octies': 8}.get(m.group(2))
        return (1, int(m.group(1)), suffix if suffix is not None else 1, m.group(2))
    return (0 if key == 'praeambel' else 2, 0, 0, key)


class Line(dict):
    pass


def read_version(xml: bytes) -> dict:
    """One consolidated version as {'units': {key: unit}, 'order': [...]} where a unit is an article (or the preamble)
    with its label, heading, the section it sits in, and its lines; each line carries the footnote events that apply to
    it (its own and its ancestors')."""
    root = etree.fromstring(xml)
    body = root.find('.//a:body', AKN)
    units: dict[str, dict] = {}
    order: list[str] = []

    pre = root.find('.//a:preamble', AKN)
    if pre is not None:
        ps = [text_of(p) for p in pre.findall('a:p', AKN)]
        ps = [p for p in ps if p and p != 'Präambel']
        units['praeambel'] = {'key': 'praeambel', 'label': 'Präambel', 'heading': '', 'section': [], 'notes': [],
                              'lines': [{'path': f'p{i + 1}', 'level': 0, 'text': p, 'notes': []} for i, p in enumerate(ps)]}
        order.append('praeambel')

    def section_path(art) -> list[str]:
        out = []
        for anc in art.iterancestors():
            if tag(anc) in ('part', 'book', 'title', 'chapter', 'section', 'subsection', 'level'):
                num = anc.find('a:num', AKN)
                head = anc.find('a:heading', AKN)
                s = ' '.join(x for x in [text_of(num) if num is not None else '', text_of(head) if head is not None else ''] if x)
                if s:
                    out.append(s)
            if tag(anc) == 'body':
                break
        return list(reversed(out))

    def lines_of(e, level: int, path: str, inherited: list) -> list[dict]:
        out: list[dict] = []
        t = tag(e)
        notes = inherited + [ev for n in own_notes(e) for ev in note_events(n)]
        if t == 'paragraph':
            num = e.find('a:num', AKN)
            n = text_of(num) if num is not None else ''
            content = e.find('a:content', AKN)
            p = f'{path}/{e.get("eId", "").rsplit("/", 1)[-1]}'
            if content is None:
                return out
            first = True
            for c in content:
                if tag(c) == 'p':
                    s = text_of(c)
                    if s:
                        out.append({'path': p, 'level': level, 'text': (f'{n} {s}' if n and first else s), 'notes': notes + inline(c)})
                        first = False
                elif tag(c) == 'blockList':
                    out.extend(block(c, level, p, notes, n if first else ''))
                    first = False
                elif tag(c) == 'table':
                    for tr in c.iter('{%s}tr' % AKN['a']):
                        s = ' | '.join(c for c in (text_of(td) for td in tr) if c)
                        if s.strip(' |'):
                            out.append({'path': p, 'level': level + 1, 'text': s, 'notes': notes})
            return out
        return out

    def block(bl, level: int, path: str, notes: list, num: str) -> list[dict]:
        out = []
        intro = bl.find('a:listIntroduction', AKN)
        if intro is not None:
            s = text_of(intro)
            if s:
                out.append({'path': path, 'level': level, 'text': f'{num} {s}'.strip(), 'notes': notes + inline(intro)})
        for item in bl.findall('a:item', AKN):
            inum = item.find('a:num', AKN)
            label = text_of(inum) if inum is not None else ''
            ipath = f'{path}/{item.get("eId", "").rsplit("/", 1)[-1]}'
            inotes = notes + [ev for n in (inum.iter('{%s}authorialNote' % AKN['a']) if inum is not None else []) for ev in note_events(n)]
            first = True
            for c in item:
                if tag(c) == 'p':
                    s = text_of(c)
                    if s:
                        out.append({'path': ipath, 'level': level + 1, 'text': f'{label} {s}'.strip() if first else s, 'notes': inotes + inline(c)})
                        first = False
                elif tag(c) == 'blockList':
                    out.extend(block(c, level + 1, ipath, inotes, label if first else ''))
                    first = False
            if first and label:
                out.append({'path': ipath, 'level': level + 1, 'text': label, 'notes': inotes})
        return out

    for art in body.iter('{%s}article' % AKN['a']):
        eid = art.get('eId', '')
        key = unit_key(eid)
        num = art.find('a:num', AKN)
        head = art.find('a:heading', AKN)
        label = text_of(num) if num is not None else key
        label = re.sub(r'^Art\.\s*(\d+)\s*([a-z]+)$', r'Art. \1\2', label)
        heading = text_of(head) if head is not None else ''
        heading = re.sub(r'\s*\*$', '', heading)
        art_notes = [ev for n in own_notes(art) for ev in note_events(n)]
        lines: list[dict] = []
        for c in art:
            if tag(c) == 'paragraph':
                lines.extend(lines_of(c, 0, '', art_notes))
            elif tag(c) in ('subdivision', 'level', 'section'):
                # Transitional provisions (Art. 197 "Ziff. 12") hold numbered parts with their own headings.
                sn = c.find('a:num', AKN)
                sh = c.find('a:heading', AKN)
                snotes = art_notes + [ev for n in own_notes(c) for ev in note_events(n)]
                title = ' '.join(x for x in [text_of(sn) if sn is not None else '', text_of(sh) if sh is not None else ''] if x)
                sp = '/' + c.get('eId', '').rsplit('/', 1)[-1]
                if title:
                    lines.append({'path': sp, 'level': 0, 'text': title, 'notes': snotes, 'heading': True})
                for p in c.iter('{%s}paragraph' % AKN['a']):
                    lines.extend(lines_of(p, 1, sp, snotes))
        if key in units:
            key = f'{key}-{eid}'
        units[key] = {'key': key, 'eid': eid, 'label': label, 'heading': heading, 'section': section_path(art),
                      'notes': art_notes, 'lines': lines}
        order.append(key)
    return {'units': units, 'order': order}


def is_repealed(unit: dict | None) -> bool:
    if unit is None:
        return True
    words = ' '.join(l['text'] for l in unit['lines']).strip()
    if not words or re.fullmatch(r'(\d+\s*)?(…|\.\.\.|Aufgehoben\.?)', words):
        return True
    return any(ev['kind'] == 'repealed' for ev in unit['notes'][-1:]) and not unit['lines']


# ---------------------------------------------------------------- words and authorship

TOKEN = re.compile(r'\n|[^\S\n]+|[\w§]+|[^\w\s]')


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text)


def unit_text(u: dict) -> str:
    return '\n'.join(l['text'] for l in u['lines'])


def author_of_line(line: dict, base: str) -> str:
    """The act that wrote a line as its footnotes say: the last event that wrote or inserted it, else the base act."""
    for ev in reversed(line['notes']):
        if ev['kind'] in ('worded', 'inserted') and ev['as']:
            return ev['as']
    return base


def attribute(prev_toks: list[str], prev_by: list[str], toks: list[str], new_by: list[str]) -> list[str]:
    """Words kept from the previous version keep their author; new words take the author the change assigns."""
    by = list(new_by)
    sm = difflib.SequenceMatcher(None, prev_toks, toks, autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            by[b + k] = prev_by[a + k]
    for i in range(1, len(toks) - 1):
        if toks[i].isspace() and toks[i] != '\n' and by[i - 1] == by[i + 1]:
            by[i] = by[i - 1]
    return by


def runs(toks: list[str], by: list[str]) -> list[list[list]]:
    out: list[list[list]] = [[]]
    for t, n in zip(toks, by):
        if t == '\n':
            out.append([])
            continue
        line = out[-1]
        if line and line[-1][1] == n:
            line[-1][0] += t
        else:
            line.append([t, n])
    return out


def redline(old: str, new: str) -> list[list]:
    a, b = tokens(old), tokens(new)
    out: list[list] = []

    def push(kind: str, s: str):
        if out and out[-1][0] == kind:
            out[-1][1] += s
        else:
            out.append([kind, s])
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == 'equal':
            push('=', ''.join(a[i1:i2]))
        else:
            if i2 > i1:
                push('-', ''.join(a[i1:i2]))
            if j2 > j1:
                push('+', ''.join(b[j1:j2]))
    merged: list[list] = []
    for i, seg in enumerate(out):
        if seg[0] == '=' and seg[1].strip() == '' and '\n' not in seg[1] and 0 < i < len(out) - 1 and out[i - 1][0] != '=' and out[i + 1][0] != '=':
            seg = ['-', seg[1]]
        if merged and merged[-1][0] == seg[0]:
            merged[-1][1] += seg[1]
        else:
            merged.append(list(seg))
    return merged


# ---------------------------------------------------------------- the record of one act

def notes_as(u: dict | None) -> set[str]:
    if not u:
        return set()
    out = {ev['as'] for ev in u['notes'] if ev['as']}
    for l in u['lines']:
        out |= {ev['as'] for ev in l['notes'] if ev['as']}
    return out


def build_act(act: dict, offline: bool, today: str) -> dict:
    # For the whole Classified Compilation, fetch_all.py has already read every act's versions, titles and impacts
    # (catalogue.json, impacts.json); for a single act they are queried here.
    meta = act['meta'] if 'meta' in act else act_meta(act, offline)
    vers = [dict(v) for v in act['versions']] if 'versions' in act else versions_of(act, offline)
    impacts = act['impacts'] if 'impacts' in act else impacts_of(act, offline)
    base = meta['basicAct'][len(ELI):] if meta.get('basicAct') else None
    # A version can be listed before its file loads (or the file can fail to parse). It is left out and noted, and the
    # act is built from the versions that do load, so the record never silently ends at an older version unnoticed.
    parsed, kept, skipped = [], [], []
    for v in vers:
        try:
            xml = fetch(v['url'], offline=offline)
            p = read_version(xml)
        except (Exception, SystemExit) as e:  # noqa: BLE001
            skipped.append(f'{v["from"]}: {type(e).__name__}')
            continue
        v['sha256'] = hashlib.sha256(xml).hexdigest()
        parsed.append(p)
        kept.append(v)
    vers = kept
    if not vers:
        raise ValueError(f'no version loads ({"; ".join(skipped)})')
    # Fedlex's impact records by the day they took effect, per article key.
    by_day: dict[str, list[dict]] = {}
    for im in impacts:
        if im['date']:
            by_day.setdefault(im['date'], []).append(im)

    keys = sorted({k for p in parsed for k in p['units']}, key=unit_order)
    units: dict[str, dict] = {}
    named: set[str] = set()
    problems: list[str] = []
    for key in keys:
        out_versions = []
        prev = None
        prev_unit = None
        prev_toks: list[str] = []
        prev_by: list[str] = []
        # A repealed article keeps a stub ("Aufgehoben") in Fedlex's text. An article missing outright from one version
        # that comes back in a later one is a gap in the source, not a repeal and a re-insertion, so it is skipped.
        last_present = max(j for j, p in enumerate(parsed) if key in p['units'])
        for i, (v, p) in enumerate(zip(vers, parsed)):
            u = p['units'].get(key)
            if u is None and i < last_present:
                continue
            gone = is_repealed(u)
            if prev is None and gone:
                continue
            text = '' if gone else unit_text(u)
            head = '' if gone else u['heading']
            if prev is not None and prev['repealed'] == gone and prev['text'] == text and prev['heading'] == head:
                continue
            toks = tokens(text)
            first = prev is None and i == 0
            # Who wrote the new words. In the first version of the record, the footnotes say who wrote each line.
            # Later, the acts that took effect that day and changed this article, narrowed to the act a line's
            # footnote names when there are several.
            eid = (u or prev_unit or {}).get('eid', '')
            day = by_day.get(v['from'], [])
            specific = sorted({im['as'] for im in day if eid and (im['target'] == eid or im['target'].startswith(eid + '/'))})
            general = sorted({im['as'] for im in day if im['target'] == 'text'})
            fresh = sorted(notes_as(u) - notes_as(parsed[i - 1]['units'].get(key) if i else None)) if not gone else []
            causes = specific or [a for a in fresh if a in general] or fresh or general
            if not first and not causes:
                # The footnote names the act even where the impact record is missing, if it took effect that day.
                causes = [ev['as'] for ev in ((u['notes'] + [e for l in u['lines'] for e in l['notes']]) if u else [])
                          if ev['as'] and ev['inForce'] == v['from']][-1:]
            new_by: list[str] = []
            if not gone:
                for li, line in enumerate(u['lines']):
                    who = author_of_line(line, base or 'base')
                    if not first and who not in causes and causes:
                        who = causes[0] if causes[0] != 'publisher' or not prev_by else prev_by[-1]
                    n = len(tokens(line['text'])) + (1 if li < len(u['lines']) - 1 else 0)
                    new_by.extend([who] * n)
                new_by = new_by[:len(toks)] + [new_by[-1] if new_by else (base or 'base')] * max(0, len(toks) - len(new_by))
            by = attribute(prev_toks if prev and not prev['repealed'] else [], prev_by if prev and not prev['repealed'] else [], toks, new_by) if not gone else []
            kind = 'start' if first else 'created' if prev is None or prev['repealed'] and not gone else 'repealed' if gone else 'updated'
            if kind != 'start':
                if not causes:
                    # No act changed the article that day and no footnote names one: the publisher corrected the text
                    # (spelling, a line break). It is shown as the publisher's correction, never credited to a law.
                    kind = 'corrected'
                    causes = ['publisher']
                    problems.append(f'{act["slug"]} {key} {v["from"]}: corrected by the publisher')
                named.update(c for c in causes if c != 'publisher')
            for a in set(by):
                if a not in ('base',):
                    named.add(a)
            # The day the change took effect. Fedlex has XML for only some versions of older acts, so a change can
            # first appear in a version dated after it took effect. The footnote ("in Kraft seit 1. Jan. 2020") or the
            # impact record dates it; it must fall after the previous version in the record, which did not have it.
            in_force = v['from']
            if kind not in ('start', 'corrected'):
                evs = (u['notes'] + [e for l in u['lines'] for e in l['notes']]) if u else []
                cand = [ev['inForce'] for ev in evs if ev['as'] in causes and ev['inForce']]
                cand += [im['date'] for im in impacts if im['as'] in causes and im['date'] and (im['target'] == 'text' or (eid and (im['target'] == eid or im['target'].startswith(eid + '/'))))]
                cand = [d for d in cand if d <= v['from'] and (i == 0 or d > vers[i - 1]['from'])]
                if cand:
                    in_force = max(cand)
            # Footnote events of the lines as printed in this version (for the reader's notes and the git message).
            notes = []
            if u and not gone:
                seen = set()
                for ev in u['notes'] + [e for l in u['lines'] for e in l['notes']]:
                    k2 = (ev['kind'], ev['as'], ev['text'][:80])
                    if k2 not in seen:
                        seen.add(k2)
                        notes.append(ev)
            out_versions.append({
                'from': in_force, 'seen': v['from'], 'kind': kind, 'repealed': gone, 'heading': head, 'text': text,
                'lines': [] if gone else [{'path': l['path'], 'level': l['level'], 'heading': bool(l.get('heading'))} for l in u['lines']],
                'runs': runs(toks, by) if not gone else [],
                'causes': [] if first else causes,
                'redline': [] if first else redline((prev['heading'] + '\n' if prev and not prev['repealed'] else '') + (prev['text'] if prev and not prev['repealed'] else ''), (head + '\n' if not gone else '') + text),
                'notes': notes,
            })
            prev, prev_toks, prev_by = out_versions[-1], toks, by
            prev_unit = u or prev_unit
        if not out_versions:
            continue
        latest_unit = next((p['units'][key] for p in reversed(parsed) if key in p['units']), None)
        units[key] = {'key': key, 'label': latest_unit['label'] if latest_unit else key, 'eid': (latest_unit or {}).get('eid', ''),
                      'section': (latest_unit or {}).get('section', []), 'versions': out_versions}
    problems += [f'version {x} not loaded' for x in skipped]
    return {'act': act, 'meta': meta, 'versions': vers, 'units': units, 'named': named, 'problems': problems, 'impacts': impacts, 'base': base, 'skipped': skipped}


# ---------------------------------------------------------------- what relies on what

REF = re.compile(r'\b(?:Art(?:ikel|ikels|\.)|Artikeln)\s+(\d+[a-z]*)(?:\s*(?:Abs(?:atz|\.)|Ziff(?:er|\.))\s*(\d+[a-z]*))?')
OTHER_ACT = re.compile(r'^\s*(?:Abs\.\s*\d+\s*)?(?:Bst\.\s*[a-z]\s*)?(?:des|der|dieses|vom|in|im)?\s*(?:\w+gesetz|\w+gesetzes|ZGB|OR|StGB|SchKG|BGG|DSG|BV|Bundesgesetz|Verordnung|Übereinkommen|SR\b)')


def citations(units: dict[str, dict], today_text: dict[str, str], slug: str) -> dict[str, list[dict]]:
    """For each article, the other articles of the same act that cite it by number in the text in force today."""
    out: dict[str, list[dict]] = {}
    for key, text in today_text.items():
        for m in REF.finditer(text):
            target = m.group(1)
            if target not in units or target == key:
                continue
            # "Art. 3 des Zivilgesetzbuches" points to another act.
            rest = text[m.end():m.end() + 60]
            if re.match(r'\s*(?:Abs\.\s*\d+\w*\s*)?(?:Bst\.\s*\w+\s*)?(?:und\s+\d+\w*\s*)?(?:des|der)\s+(?!vorliegenden)', rest) and not re.match(r'\s*(?:des|der)\s+(?:Bundesverfassung)', rest if slug == 'bv' else 'x'):
                continue
            s = max(0, m.start() - 90)
            e = min(len(text), m.end() + 90)
            out.setdefault(target, []).append({'from': key, 'before': ('…' if s else '') + text[s:m.start()].replace('\n', ' '),
                                               'match': m.group(0), 'after': text[m.end():e].replace('\n', ' ') + ('…' if e < len(text) else ''),
                                               'para': m.group(2)})
    return out


DEF_HEAD = re.compile(r'^(Begriffe?|Begriffsbestimmungen|Definitionen)$')


def defined_terms(units: dict[str, dict]) -> list[dict]:
    """Terms an act defines in an article headed "Begriffe": "a. Personendaten: alle Angaben, …"."""
    out = []
    for key, u in units.items():
        v = u['versions'][-1]
        if v['repealed'] or not DEF_HEAD.match(v['heading']):
            continue
        for line in v['text'].split('\n'):
            m = re.match(r'^(?:\d+\s+)?[a-z]\.\s+([^:]{3,60}?):\s', line)
            if m:
                out.append({'term': m.group(1).strip(), 'article': key})
    return out


def term_pattern(term: str) -> re.Pattern:
    # German inflects: "betroffene Person" also reads "betroffenen Person", "Personendaten" stays. Allow the usual endings.
    parts = [re.escape(w) for w in term.split()]
    # A defined verb ("Bearbeiten") is used in lower case in a sentence ("Personendaten bearbeiten").
    if parts and parts[0][:1].isalpha():
        parts[0] = f'[{parts[0][0].upper()}{parts[0][0].lower()}]{parts[0][1:]}'
    # Endings vary with case and gender ("der Verantwortliche", "des Verantwortlichen"), so each word is matched by its
    # stem with any of the usual endings.
    def stem(p: str) -> str:
        end = r'(?:e|en|er|es|em|n|s)?'
        m = re.fullmatch(r'(.{5,}?)(er|en|es|e|n|s)', p)
        return f'(?:{p}{end}|{m.group(1)}{end})' if m else p + end
    rx = r'\s+'.join(stem(p) for p in parts)
    return re.compile(r'(?<![\wäöüÄÖÜ])' + rx + r'(?![\wäöüÄÖÜ])')


def term_uses(terms: list[dict], today_text: dict[str, str]) -> list[dict]:
    out = []
    for t in terms:
        rx = term_pattern(t['term'])
        rows = []
        for key, text in today_text.items():
            if key == t['article']:
                continue
            for line in text.split('\n'):
                m = rx.search(line)
                if m:
                    s = max(0, m.start() - 80)
                    e = min(len(line), m.end() + 80)
                    rows.append({'from': key, 'before': ('…' if s else '') + line[s:m.start()], 'match': m.group(0), 'after': line[m.end():e] + ('…' if e < len(line) else '')})
                    break
        out.append({**t, 'rows': rows})
    return out


# ---------------------------------------------------------------- output for the site

def as_label(rec: dict) -> str:
    m = re.match(r'oc/(\d{4})/(.+)', rec['id'])
    return f'AS {m.group(1)} {m.group(2)}' if m else rec['id']


# ---------------------------------------------------------------- the git repository

def git(repo: Path, *args: str, env: dict | None = None, input: str | None = None) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8', env=env, input=input)
    if out.returncode:
        raise SystemExit(f'git {" ".join(args)} failed: {out.stderr}')
    return out.stdout


def last_sunday(year: int, month: int) -> dt.date:
    d = (dt.date(year, month + 1, 1) if month < 12 else dt.date(year + 1, 1, 1)) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def zurich_offset(day: dt.date) -> int:
    """Hours ahead of UTC on a day in Zurich (summer time from the last Sunday in March to the last in October)."""
    return 2 if last_sunday(day.year, 3) < day <= last_sunday(day.year, 10) else 1


def commit_date(day: str) -> str:
    d = dt.date.fromisoformat(day)
    off = zurich_offset(d)
    stamp = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone(dt.timedelta(hours=off))).timestamp())
    return f'@{stamp} +0{off}00'


def article_md(act_short: str, label: str, heading: str, text: str, lines: list[dict]) -> str:
    out = [f'# {label}' + (f' {heading}' if heading else ''), '']
    for t, l in zip(text.split('\n'), lines):
        if l.get('heading'):
            out += [f'## {t}', '']
        else:
            out += [('  ' * l['level'] + ('- ' if l['level'] else '')) + t, ''] if l['level'] else [t, '']
    return '\n'.join(out).rstrip() + '\n'


def file_name(key: str) -> str:
    m = re.fullmatch(r'(\d+)([a-z]*)', key)
    return f'art-{int(m.group(1)):03d}{m.group(2)}.md' if m else f'{key}.md'


def main():
    raise SystemExit('build.py is the library that reads one act. Build the record with bulk.py (and fetch_all.py first).')


if __name__ == '__main__':
    main()
