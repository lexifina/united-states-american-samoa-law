"""New Zealand: cached official consolidations (legislation.govt.nz, via Internet Archive captures) -> corpus.json.

Reads only captures.json and .cache/ (written by fetch.py). No network, no model. Deterministic.

Method, per act:
1. Each archived page is one official consolidation, dated by the date it states ("as at 13 November 2025"). Section
   78 of the Legislation Act 2019 makes an electronic consolidation on legislation.govt.nz an official version, which
   each page states in its notes. One capture is used per stated date (the latest capture of that date).
2. Each page is split into units: the long title, every section (div.prov outside schedules) and every schedule.
   A unit's text is its heading line and one subsection or paragraph per line. The PCO's history notes ("Section 3A:
   inserted, on 1 November 1999, by section 2 of the Constitution Amendment Act 1999 (1999 No 86).") are not law text:
   they are taken out of the text and used only to date and credit changes.
3. The oldest archived consolidation is the first version, "oldest version available", credited to the publisher,
   with the Acts its notes name as earlier_laws.
4. Between two archived consolidations P (as at dp) and N (as at dn), a unit whose words changed is dated and
   credited from N's history notes for that unit that fall in (dp, dn]:
   - one date d: the new words take effect on d, credited to the Act(s) named for d;
   - several dates: the source gives no text between them, so the first date gets a placeholder line, credited to
     the Act(s) of that date, and the last date the new words, credited to the Act(s) of the later dates;
   - none: the change is the publisher's, "unexplained", on dn.
   Unit text is compared after normalising typesetting (quotes, dashes, spaces), so layout changes between the three
   generations of the site's HTML are not changes.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
PLACEHOLDER = '[The source does not give the text in force on this date.]'
MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}
SITE = 'https://www.legislation.govt.nz'

ACTS = [
    {'slug': 'constitution-act', 'short': 'Constitution Act', 'title': 'Constitution Act 1986', 'year': 1986, 'no': 114},
    {'slug': 'bill-of-rights-act', 'short': 'NZBORA', 'title': 'New Zealand Bill of Rights Act 1990', 'year': 1990,
     'no': 109},
    {'slug': 'privacy-act', 'short': 'Privacy Act', 'title': 'Privacy Act 2020', 'year': 2020, 'no': 31,
     'in_force': '2020-12-01'},
    {'slug': 'crimes-act', 'short': 'Crimes Act', 'title': 'Crimes Act 1961', 'year': 1961, 'no': 43},
]

BLOCK = {'p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'table', 'tbody', 'thead', 'blockquote',
         'dl', 'dt', 'dd', 'br'}


def iso(s: str) -> str | None:
    m = re.fullmatch(r'(\d{1,2}) ([A-Za-z]+) (\d{4})', s.strip())
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'


def norm(s: str) -> str:
    s = s.replace(chr(0xa0), ' ').replace(chr(0x2009), ' ')
    for z in (0x200b, 0xfeff, 0x2060, 0xad):
        s = s.replace(chr(z), '')
    s = s.replace(chr(0x2018), "'").replace(chr(0x2019), "'").replace(chr(0x201c), '"').replace(chr(0x201d), '"')
    s = s.replace(chr(0x2013), '-')
    s = re.sub(r'[ \t\r\n]+', ' ', s).strip()
    s = re.sub(r' ([,;:.)])', r'\1', s)
    s = re.sub(r'\( ', '(', s)
    return s


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


# ------------------------------------------------------------------ one page -> units

def lines_of(el: Tag) -> list[str]:
    out, cur = [], []

    def flush():
        t = norm(''.join(cur))
        if t:
            out.append(t)
        cur.clear()

    def walk(n):
        for ch in n.children:
            if isinstance(ch, NavigableString):
                if ch.__class__.__name__ in ('Comment', 'Doctype'):
                    continue
                cur.append(str(ch))
            elif isinstance(ch, Tag):
                if ch.name in ('script', 'style'):
                    continue
                if ch.name == 'td' or ch.name == 'th':
                    cur.append(' ')
                    walk(ch)
                    cur.append(' ')
                elif ch.name in BLOCK:
                    flush()
                    walk(ch)
                    flush()
                else:
                    walk(ch)
    walk(el)
    flush()
    # a line that is only a label, "(1)" or "(a)", joins the next line
    merged = []
    for l in out:
        if merged and re.fullmatch(r'\(?[0-9A-Za-z]{1,6}\)(?:(?:,| and| to|-) ?\(?[0-9A-Za-z]{1,6}\))*', merged[-1]):
            merged[-1] = merged[-1] + ' ' + l
        else:
            merged.append(l)
    return merged


def is_cls(el: Tag, name: str) -> bool:
    return isinstance(el, Tag) and name in (el.get('class') or [])


def has_ancestor(el: Tag, test) -> bool:
    p = el.parent
    while isinstance(p, Tag):
        if test(p):
            return True
        p = p.parent
    return False


def unit_key(kind: str, label: str) -> str:
    if kind == 'sch':
        m = re.fullmatch(r'Schedule\s*(\d*)([A-Z]*)', label.strip())
        if not m:
            return 'sch-' + re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
        return 'sch' + (f'-{int(m.group(1)):02d}{m.group(2).lower()}' if m.group(1) else '')
    m = re.fullmatch(r'(\d+)([A-Z]*)', label.strip())
    if not m:
        return 'sec-' + re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
    return f'sec-{int(m.group(1)):03d}{m.group(2).lower()}'


def notes_of(el: Tag) -> list[str]:
    return [norm(n.get_text('')) for n in el.find_all('p', class_='history-note')]


def parse_page(raw: bytes) -> dict:
    soup = BeautifulSoup(raw, 'lxml')
    for t in soup.find_all(['script', 'style', 'noscript', 'button']):
        t.decompose()
    # site furniture and PCO editorial notes inside provisions: not law text
    for cls in ('slInfoAlert', 'editorial-note', 'link-to-sl-button'):
        for t in soup.find_all(class_=cls):
            t.decompose()
    units, notes = {}, {}

    def add(key, label, kind, text, ns):
        k, i = key, 2
        while k in units:
            k = f'{key}-{i}'
            i += 1
        units[k] = {'label': label, 'kind': kind, 'text': text}
        notes[k] = ns

    lts = [t for t in soup.find_all(class_='long-title') if norm(t.get_text(' ')).startswith('An Act')]
    lt = max(lts, key=lambda t: len(t.get_text(' '))) if lts else None
    if lt:
        add('long-title', 'Long title', 'title', '\n'.join(lines_of(lt)) + '\n', [])

    def prov_ok(d):
        return (d.name == 'div' and is_cls(d, 'prov') and d.find('h5', recursive=False) is not None
                and d.get('id'))

    def in_sched(p):
        return p.name == 'div' and is_cls(p, 'schedule')

    # old reprints append the amending Acts' own transitional provisions ("skeletons"): not part of the Act
    for t in soup.find_all(class_='skeletons'):
        t.decompose()

    for d in soup.find_all(prov_ok):
        if has_ancestor(d, lambda p: prov_ok(p) or in_sched(p)):
            continue
        h5 = d.find('h5', recursive=False)
        lab = h5.find('span', class_='label')
        label = norm(lab.get_text('')) if lab else ''
        ns = notes_of(d)
        for h in d.find_all(class_='history'):
            h.decompose()
        for h in d.find_all('p', class_='history-note'):
            h.decompose()
        ls = lines_of(d)
        if not ls:
            continue
        ls[0] = '# ' + ls[0]
        add(unit_key('sec', label), f's {label}', 'section', '\n'.join(ls) + '\n', ns)

    for s in soup.find_all(lambda t: t.name == 'div' and is_cls(t, 'schedule') and t.get('id')):
        if has_ancestor(s, lambda p: in_sched(p) or prov_ok(p)):
            continue
        lab = s.find(class_='label')
        label = norm(lab.get_text('')) if lab else 'Schedule'
        if not label.startswith('Schedule'):
            label = 'Schedule ' + label
        ns = notes_of(s)
        for h in s.find_all(class_='history'):
            h.decompose()
        for h in s.find_all('p', class_='history-note'):
            h.decompose()
        ls = lines_of(s)
        if not ls:
            continue
        if len(ls) > 1 and re.fullmatch(r'Schedule ?[0-9A-Z]*', ls[0]):
            ls[0:2] = [ls[0] + ' ' + ls[1]]
        ls[0] = '# ' + ls[0]
        add(unit_key('sch', label), label, 'schedule', '\n'.join(ls) + '\n', ns)
    return {'units': units, 'notes': notes}


# ------------------------------------------------------------------ history notes -> (date, law)

LAW_RE = re.compile(r"([^;]{1,200}?\d{4}) \((\d{4}) No (\d+)\)")
SEC_RE = re.compile(r"([^;]{1,200}?) \((SR|LI|SL) (\d{4})/(\d+)\)")


def note_events(note: str) -> list[tuple[str, str, str, str]]:
    """[(date, law key, label, kind)] for one history note."""
    dm = re.search(r'(?:on|as from|from|with effect from) (\d{1,2} [A-Z][a-z]+ \d{4})', note)
    if not dm:
        return []
    d = iso(dm.group(1))
    if 'editorial change' in note.lower():
        return [(d, 'pco-editorial', 'Editorial change by the Parliamentary Counsel Office (Legislation Act 2019, '
                 'subpart 2 of Part 3)', 'publisher')]
    rest = note[dm.end():]
    out = []
    def clean(s):
        s = re.split(r'(?<=[."])\s+(?:See\s+)?', s.strip())[-1]
        if ' by ' in ' ' + s:
            s = (' ' + s)[(' ' + s).rfind(' by ') + 4:]
        if ' pursuant to ' in ' ' + s:
            s = (' ' + s)[(' ' + s).rfind(' pursuant to ') + 13:]
        s = re.sub(r'^(?:pursuant to )?(?:the )?(?:(?:sections?|ss?|clauses?|[Ss]chedules?|Parts?|subparts?|regulations?|rules?|items?|'
                   r'paragraphs?|clauses?)\s+[A-Za-z0-9().]+(?:(?:,| and| to)\s+[A-Za-z0-9().]+)*\s+(?:of\s+)?)?(?:the\s+)?', '', s.strip())
        if '/' in s:  # bilingual citation, "wehenga 7 o Te Ture ... 2022/section 7 of the ... Act 2022": English half
            s = s.rsplit('/', 1)[1]
        if s[:1].islower() and re.search(r'\bof (?:the )?(?=[A-Z])', s):
            s = re.split(r'\bof (?:the )?(?=[A-Z])', s)[-1]
        return s.strip(' ,.')
    for m in LAW_RE.finditer(rest):
        name = clean(m.group(1))
        out.append((d, f'act-{m.group(2)}-{int(m.group(3)):03d}', name, 'law'))
    for m in SEC_RE.finditer(rest):
        name = clean(m.group(1))
        out.append((d, f'{m.group(2).lower()}-{m.group(3)}-{int(m.group(4)):04d}', f'{name} ({m.group(2)} {m.group(3)}/{m.group(4)})',
                    'decree'))
    # a Commencement Order named beside the amending Act only sets the day: the Act is the author
    if any(e[3] == 'law' for e in out):
        out = [e for e in out if not (e[3] == 'decree' and 'Commencement' in e[2])]
    return out


# ------------------------------------------------------------------ versions

def comparable(u: dict | None) -> str | None:
    if u is None:
        return None
    return u['text']


def build_act(spec: dict, caps: list[dict], laws: dict, decisions: list, log: list) -> dict | None:
    by_date = {}
    for c in caps:
        if not c.get('as_at') or not c.get('sha256'):
            continue
        raw = cache_path(f'https://web.archive.org/web/{c["timestamp"]}id_/{c["url"]}').read_bytes()
        if b'</html>' not in raw[-4096:].lower():
            log.append(f'{spec["slug"]}: capture {c["timestamp"]} of {c["url"]} is truncated ({len(raw)} bytes, no '
                       f'</html>); not used')
            continue
        rank = (c['kind'].endswith('latest'), c['timestamp'])
        o = by_date.get(c['as_at'])
        if o is None or rank > (o['kind'].endswith('latest'), o['timestamp']):
            by_date[c['as_at']] = c
    if not by_date:
        return None
    floor = spec.get('in_force')
    if floor:
        early = sorted(d for d in by_date if d < floor)
        if early:
            decisions.append(f'{spec["title"]} came into force on {floor}, except subpart 2 of Part 3 and ss 213-215, '
                             f'in force the day after Royal assent (s 2); the PCO consolidations archived for '
                             f'earlier dates ({", ".join(early)}) and the as-enacted pages show text not yet in force, '
                             f'so the history starts with the first archived consolidation on or after {floor}.')
        by_date = {d: c for d, c in by_date.items() if d >= floor}
    pages = []
    for d in sorted(by_date):
        c = by_date[d]
        url = f'https://web.archive.org/web/{c["timestamp"]}id_/{c["url"]}'
        raw = cache_path(url).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == c['sha256'], url
        p = parse_page(raw)
        p.update(date=d, url=url, sha=c['sha256'], orig=c['url'], ts=c['timestamp'], latest=c['kind'].endswith('latest'))
        if not p['units']:
            log.append(f'{spec["slug"]}: no units in {url}')
            continue
        pages.append(p)
    # a page captured before another page that states an EARLIER date is an older rendering of a consolidation the
    # PCO later re-issued (old reprints were labelled by reprint date, re-issues by the last amendment's date)
    sup = [p for p in pages if p['latest'] and any(q['latest'] and q['date'] < p['date'] and q['ts'] > p['ts'] for q in pages)]
    for p in sup:
        q = min((q for q in pages if q['latest'] and q['date'] < p['date'] and q['ts'] > p['ts']), key=lambda q: q['date'])
        log.append(f'{spec["slug"]}: as at {p["date"]} (captured {p["ts"]}) is superseded by the re-issued consolidation '
                   f'as at {q["date"]} (captured {q["ts"]}); not a version')
        decisions.append(f'{spec["title"]}: the page stating "as at {p["date"]}" (archived {p["ts"][:8]}) is an older '
                         f'rendering of the consolidation the PCO later re-issued as "as at {q["date"]}" (archived '
                         f'{q["ts"][:8]}); only the re-issue is used.')
    pages = [p for p in pages if p not in sup]
    # drop a consolidation whose words equal the one before (a relabelled reprint)
    kept = [pages[0]]
    for p in pages[1:]:
        prev = kept[-1]
        same = set(p['units']) == set(prev['units']) and all(
            comparable(p['units'][k]) == comparable(prev['units'][k]) for k in p['units'])
        if same:
            log.append(f'{spec["slug"]}: as at {p["date"]} has the same words as {prev["date"]}; not a version')
        else:
            kept.append(p)
    pages = kept

    def note_law(ev):
        d, key, label, kind = ev
        if key not in laws:
            y = key.split('-')[1]
            url = (f'{SITE}/act/public/{y}/{int(key.split("-")[2])}/en/latest/' if kind == 'law' else
                   f'{SITE}/act/public/2019/58/en/latest/' if kind == 'publisher' else None)
            laws[key] = {'label': label, 'title': label, 'kind': kind, 'enacted': None, 'published': None,
                         'url': url, 'temporary_until': None, 'restores': None, 'note': None}
        return key

    first = pages[0]
    earlier = set()
    for k, ns in first['notes'].items():
        for n in ns:
            for ev in note_events(n):
                earlier.add(note_law(ev))
    own = f'act-{spec["year"]}-{spec["no"]:03d}'
    # no history note anywhere: the oldest page is the Act as enacted
    as_enacted = not any(first['notes'].values())
    if as_enacted:
        log.append(f'{spec["slug"]}: oldest archived page (as at {first["date"]}) has no history notes: the Act as enacted')
    versions = [{'from': first['date'], 'source_url': first['url'], 'sha256': first['sha'],
                 'units': first['units'], 'credits': {},
                 'note': f'Official version as at {first["date"]} (legislation.govt.nz, archived '
                         f'{first["ts"][:8]}): ' + ('the Act as enacted, with no amendment.' if as_enacted else
                                                    'the oldest version archived.')}]
    state = dict(first['units'])
    for prev, nxt in zip(pages, pages[1:]):
        dp, dn = prev['date'], nxt['date']
        keys = sorted(set(prev['units']) | set(nxt['units']))
        per_date: dict[str, dict] = {}  # date -> {'changes':{}, 'credits':{}}
        for k in keys:
            a, b = prev['units'].get(k), nxt['units'].get(k)
            if comparable(a) == comparable(b):
                continue
            evs = sorted({ev for n in (nxt['notes'].get(k) or prev['notes'].get(k) or []) for ev in note_events(n)
                          if dp < ev[0] <= dn})
            dates = sorted({ev[0] for ev in evs})
            if not dates:
                slot = per_date.setdefault(dn, {'changes': {}, 'credits': {}})
                slot['changes'][k] = b
                log.append(f'{spec["slug"]} {k}: changed between {dp} and {dn} with no dated note; unexplained')
                continue
            for ev in evs:
                note_law(ev)
            last = dates[-1]
            if len(dates) > 1:
                d0 = dates[0]
                head = (b or a)['text'].split('\n', 1)[0]
                ph = {'label': (b or a)['label'], 'kind': (b or a)['kind'], 'text': f'{head}\n{PLACEHOLDER}\n'}
                slot = per_date.setdefault(d0, {'changes': {}, 'credits': {}})
                slot['changes'][k] = ph
                slot['credits'][k] = sorted({ev[1] for ev in evs if ev[0] == d0})
                log.append(f'{spec["slug"]} {k}: {len(dates)} amendment dates between {dp} and {dn} ({", ".join(dates)});'
                           f' placeholder on {d0}')
            slot = per_date.setdefault(last, {'changes': {}, 'credits': {}})
            slot['changes'][k] = b
            slot['credits'][k] = sorted({ev[1] for ev in evs if ev[0] > dates[0] or len(dates) == 1})
        for d in sorted(per_date):
            ch = per_date[d]['changes']
            for k, u in ch.items():
                if u is None:
                    state.pop(k, None)
                else:
                    state[k] = u
            v = {'from': d, 'source_url': nxt['url'], 'sha256': nxt['sha'],
                 'changes': {k: ch[k] for k in sorted(ch)},
                 'credits': {k: v for k, v in sorted(per_date[d]['credits'].items())}}
            if d != dn:
                v['note'] = (f'Words from the official consolidation as at {dn}, dated by its history notes '
                             f'(no consolidation as at {d} is archived).')
            else:
                v['note'] = f'Official consolidation as at {dn} (legislation.govt.nz, archived {nxt["ts"][:8]}).'
            versions.append(v)
    return {'slug': spec['slug'], 'short': spec['short'], 'title': spec['title'],
            'url': f'{SITE}/act/public/{spec["year"]}/{spec["no"]}/en/latest/',
            'first_law': own if as_enacted else None, 'earlier_laws': [] if as_enacted else sorted(earlier | {own}),
            'versions': versions,
            '_pages': [(p['date'], p['orig'], p['ts']) for p in pages]}


def main():
    caps = json.loads((HERE / 'captures.json').read_text(encoding='utf-8'))
    args = sys.argv[1:]
    out_path = HERE / 'corpus.json'
    if '--out' in args:  # write elsewhere (to test an act before it goes into corpus.json)
        i = args.index('--out')
        out_path = Path(args[i + 1])
        del args[i:i + 2]
    only = args
    laws, decisions, log, acts, pages = {}, [], [], [], {}
    for spec in ACTS:
        if only and spec['slug'] not in only:
            continue
        a = build_act(spec, caps.get(spec['slug'], []), laws, decisions, log)
        if a:
            pages[a['slug']] = a.pop('_pages')
            acts.append(a)
    for spec in ACTS:
        own = f'act-{spec["year"]}-{spec["no"]:03d}'
        if any(a['slug'] == spec['slug'] for a in acts) and own not in laws:
            laws[own] = {'label': spec['title'], 'title': spec['title'], 'kind': 'law', 'enacted': None,
                         'published': None, 'url': f'{SITE}/act/public/{spec["year"]}/{spec["no"]}/en/latest/',
                         'temporary_until': None, 'restores': None, 'note': None}
    reqs = sum(1 for _ in open(CACHE / 'requests.jsonl', encoding='utf-8')) if (CACHE / 'requests.jsonl').exists() else 0
    corpus = {
        'country': {
            'code': 'NZ', 'name': 'New Zealand', 'slug': 'new-zealand', 'lang': 'en', 'tz': 'Pacific/Auckland',
            'future_branch': 'future',
            'publisher': {'name': 'Parliamentary Counsel Office (New Zealand Legislation)',
                          'email': 'pco@legislation.govt.nz.invalid'},
            'default_in_force_rule': {
                'text': 'Each change is dated by the in-force date the Parliamentary Counsel Office history note for '
                        'the provision states ("Section 25: repealed, on 13 November 2025, by section 51 of the '
                        'Parliament (Repeals and Amendments) Act 2025"); each version is the official consolidation '
                        'as at its stated date (Legislation Act 2019, s 78).',
                'source': SITE},
            'licence_note': 'Sourced from the New Zealand Legislation website (www.legislation.govt.nz), Parliamentary '
                            'Counsel Office. "Under section 27 of the Copyright Act 1994, there is no copyright in New '
                            'Zealand legislation, including in legislation published by the PCO on this website"; all '
                            'other content on the site is Crown copyright, licensed under a Creative Commons Attribution '
                            'licence (CC BY) (legislation.govt.nz/copyright/, archived 2026-07-12).',
        },
        'sources': [
            {'name': 'New Zealand Legislation (legislation.govt.nz), Parliamentary Counsel Office',
             'url': SITE, 'retrieved': '2026-10-29', 'requests': 0,
             'licence': 'no copyright in legislation (Copyright Act 1994 s 27); other site content Crown copyright, CC BY',
             'notes': 'Official consolidations ("as at" versions). Not fetched directly: the site answers automated '
                      'readers with an AWS WAF bot challenge and its API needs a key. Read through Internet Archive '
                      'captures.'},
            {'name': 'Internet Archive Wayback Machine (id_ raw captures)', 'url': 'https://web.archive.org/',
             'retrieved': '2026-10-29', 'requests': reqs,
             'licence': 'Internet Archive terms of use; the legislation itself has no copyright (s 27)',
             'notes': 'Each version pins its capture timestamp in source_url; captures.json lists every capture read.'},
        ],
        'laws': {k: laws[k] for k in sorted(laws)},
        'acts': acts,
        'applies': [],
        'decisions': [
            'English is built: New Zealand legislation is enacted in English (some Acts also have te reo Maori text, '
            'none in these acts).',
            'Versions are the official consolidations archived by the Internet Archive; consolidations that were not '
            'archived are missing, and their changes are dated by the history notes of the next archived one.',
            '"Compare" notes are kept as printed under each section; the PCO history notes and reprint notes are not '
            'law text and are left out of the files (they are used only to date and credit changes).',
            'Units: the long title, each section and each schedule; Part and cross headings are not separate files.',
            'A consolidation whose words equal the previous one (an older reprint relabelled by its reprint date) is '
            'not a version.',
            f'Where one provision was changed on several dates between two archived consolidations, the first date '
            f'reads "{PLACEHOLDER}" and the last date has the new words.',
            'A history note "editorial change made by the PCO" (Legislation Act 2019, subpart 2 of Part 3) credits the '
            'change to pco-editorial, a publisher entry, not to the Legislation Act 2019. The PCO editorial notes, the '
            'reprint notes and the site "secondary legislation" buttons inside provisions are not law text and are '
            'dropped.',
            'Orders in Council and other secondary legislation named in history notes are laws of kind decree, keyed '
            'sl-<year>-<number> (LI and SR citations likewise); Acts are keyed act-<year>-<number>.',
            'A capture of a "latest" page that a later capture contradicts by stating an earlier "as at" date is an '
            'older rendering of a consolidation the PCO re-issued, and is not used.',
        ] + decisions + [f'Pages used for {s}: ' + '; '.join(f'as at {d} from {u} (capture {t})' for d, u, t in ps)
             for s, ps in pages.items()],
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote ccindex.py, fetch.py and parse.py and '
                   'chose the sources; it did not write or alter any legal text. parse.py is deterministic and runs '
                   'no model; every line of law comes from an archived official page in the cache.'],
    }
    out = out_path
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(out)
    (out.parent / 'parse.log').write_text('\n'.join(log) + '\n', encoding='utf-8', newline='\n')
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', [v['from'] for v in a['versions']])
    print(len(laws), 'laws;', len(log), 'log lines')


if __name__ == '__main__':
    main()
