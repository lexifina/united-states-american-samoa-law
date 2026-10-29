"""Builds scripts/botswana-law/corpus.json and corpus.d/*.json from the cache only (no network).

    python -X utf8 scripts/botswana-law/parse.py            # write the corpus
    python -X utf8 scripts/botswana-law/parse.py --diff     # also print how the 2019 text differs from today's page

Sources (all in .cache/, named by the sha256 of the URL; see fetch.py and sources.json):
- the Constitution as the publisher's previous site (botswanalaws.com, Blackhall Publishing for the Attorney General's
  Chambers) showed it on 2019-05-26, archive.org capture 20190526221248 (the members-only tag leaked, so the page held
  the full consolidated text, to S.I. 57 of 2018);
- the Constitution on today's official e-Laws site (e-laws.botswanalaws.com), open to all, consolidated to S.I. 93 of
  2024, with per-provision amendment notes ("[1 of 2021, s. 2(a).]");
- the Penal Code (Cap. 08:01) as botswanalaws.com showed it on 2024-12-04, archive.org capture 20241204224821 (full
  text, consolidated to S.I. 93 of 2023);
- e-Laws bulletin excerpts (WordPress API) for commencement dates.

Every other e-Laws page is members-only and was not read. Both page layouts mark each section with
<a name="Ch<chapter>s<N>"> inside p.Level-Iblue, and chapter/part/schedule headings with p.Level-Centeredblue.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'

CONST_2019 = 'https://web.archive.org/web/20190526221248id_/http://www.botswanalaws.com:80/principal-legislation/constitution-of-botswana'
CONST_LIVE = 'https://e-laws.botswanalaws.com/constitution-of-botswana/constitution-of-botswana/'
PENAL_2024 = 'https://web.archive.org/web/20241204224821id_/https://botswanalaws.com/consolidated-statutes/principle-legislation/penal-code'
PENAL_2026 = 'https://web.archive.org/web/20260323141454id_/https://botswanalaws.com/consolidated-statutes/principle-legislation/penal-code'
BULLETIN_ACT_1_2021 = 'https://e-laws.botswanalaws.com/wp-json/wp/v2/posts/1892?_fields=id,date,title,excerpt,content,link'
BULLETIN_ACT_29_2022 = 'https://e-laws.botswanalaws.com/wp-json/wp/v2/posts/1090?_fields=id,date,title,excerpt,content,link'


def cached(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not p.exists():
        raise SystemExit(f'not cached (run fetch.py --all): {url}')
    return p.read_bytes()


def sha(url: str) -> str:
    return hashlib.sha256(cached(url)).hexdigest()


# ---------------------------------------------------------------- HTML to paragraphs

INPUT = re.compile(r'<input\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*>', re.I)  # hidden inputs carry notes in value="..."
PARA = re.compile(r'<p\b([^>]*)>', re.I)
CELL = re.compile(r'</?(?:td|tr|th|table|tbody|thead)\b[^>]*>', re.I)


def clean(s: str) -> str:
    """One line of law text: tags dropped, entities decoded, publisher typesetting normalised once."""
    s = re.sub(r'<br\s*/?>', ' ', s, flags=re.I)
    s = re.sub(r'<[^>]*>', '', s)
    s = html.unescape(s)
    s = s.replace('\xa0', ' ').replace('​', '')
    s = re.sub('[‘’‚′]', "'", s)
    s = re.sub('[“”„″]', '"', s)
    s = re.sub('[‐‑‒–—―−]', '-', s)
    s = s.replace('…', '...')
    s = s.replace("''", '"')  # the 2019 typesetting writes some double quotes as two single ones
    s = s.replace('"/>', '')  # a broken-tag artefact on today's e-Laws page (before s 85's heading)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\(\s+', '(', s)
    s = re.sub(r'\s+\)', ')', s)
    return s


def paragraphs(page: str, start: int, end: int) -> list[tuple[str, str, str]]:
    """(class, raw html, clean text) for each <p> between start and end; table cells become paragraphs too."""
    body = INPUT.sub('', page[start:end])
    out = []
    pieces = PARA.split(body)
    # pieces: [before, attrs1, content1, attrs2, content2, ...]
    for attrs, content in zip(pieces[1::2], pieces[2::2]):
        m = re.search(r'class="([^"]*)"', attrs)
        cls = m.group(1) if m else ''
        for cell in CELL.split(content):
            t = clean(cell)
            if t:
                out.append((cls, cell, t))
    return out


def units_of(page: str, chap: str, start_marker: str, end_marker: str) -> tuple[dict, dict]:
    """Sections (s-NNN) and schedules (schedule-N) of one Blackhall page, and the amendment notes per unit."""
    first = page.find(f'name="{chap}s1"')
    start = page.rfind(start_marker, 0, first)
    if first < 0 or start < 0:
        raise SystemExit(f'layout not recognised ({chap})')
    end = page.find(end_marker, first)
    if end < 0:
        raise SystemExit(f'end marker {end_marker!r} not found')
    units: dict[str, dict] = {}
    notes: dict[str, list[str]] = {}
    cur = None
    lines: list[str] = []
    nth = {'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5, 'SIXTH': 6}

    def close():
        if cur:
            key, label = cur
            if key in units:
                raise SystemExit(f'{chap}: unit {key} twice')
            units[key] = {'label': label, 'kind': 'schedule' if key.startswith('schedule') else 'section',
                          'text': '\n'.join(lines) + '\n'}

    for cls, raw, text in paragraphs(page, start, end):
        a = re.search(rf'name="{chap}s([0-9A-Za-z]+)"', raw)
        if 'Level-Iblue' in cls and a:
            close()
            num = a.group(1)
            m = re.fullmatch(r'(\d+)to(\d+)', num)
            if m:
                key, label = f's-{int(m.group(1)):03d}-to-{int(m.group(2)):03d}', f'ss {m.group(1)}-{m.group(2)}'
            else:
                m = re.fullmatch(r'(\d+)([A-Za-z]*)', num)
                key = f's-{int(m.group(1)):03d}' + (f'-{m.group(2).lower()}' if m.group(2) else '')
                label = f's {m.group(1)}{m.group(2)}'
            cur, lines = (key, label), [f'# {text}']
            continue
        if 'Level-Centeredblue' in cls:
            m = re.match(r'(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH) SCHEDULE\b', text)
            if m:
                close()
                n = nth[m.group(1)]
                cur, lines = (f'schedule-{n}', f'Schedule {n}'), [f'# {text}']
                continue
            if cur and cur[0].startswith('schedule'):
                lines.append(text)  # a heading inside a schedule is part of it
                continue
            close()  # a chapter or part heading ends the section before it
            cur, lines = None, []
            continue
        if 'Annote' in cls:  # the publisher's amendment note: kept as data for credits, not as text
            if cur:
                notes.setdefault(cur[0], []).append(text)
            continue
        if text.startswith('[*Editorial Note'):  # e-Laws' closing editorial note on Act 9 of 2005's word swaps
            close()
            cur, lines = None, []
            continue
        if re.fullmatch(r'\{/?mprestriction[^}]*\}', text):  # the old site's members-only tags, not text
            continue
        if cur:
            lines.append(text)
    close()
    return units, notes


def page(url: str) -> str:
    return cached(url).decode('utf-8', 'replace')


def constitution_2019() -> dict:
    return units_of(page(CONST_2019), 'Ch0000', 'Date of Commencement', '{/mprestriction}')[0]


def constitution_live() -> tuple[dict, dict]:
    return units_of(page(CONST_LIVE), 'Ch0000', 'Date of Commencement', '<hr')


def penal_2024() -> dict:
    return units_of(page(PENAL_2024), 'Ch0801', 'Date of Commencement', '{/mprestriction}')[0]


def amendment_list(url: str, first: str) -> list[str]:
    p = page(url)
    m = re.search(re.escape(first) + r'.*?</p>', p, re.S)
    return [x.strip(' ,.') for x in clean(m.group(0).replace('<br />', '|').replace('<br>', '|')).split('|')] if m else []


def bulletin(url: str) -> str:
    return clean(json.loads(cached(url))['excerpt']['rendered'])


# ---------------------------------------------------------------- the corpus

PUBLISHER = {'name': 'Botswana e-Laws (Attorney General\'s Chambers, published by Blackhall Publishing)',
             'email': 'publisher@botswanalaws.invalid'}


def build() -> tuple[dict, dict, dict]:
    c19 = constitution_2019()
    live, live_notes = constitution_live()
    pc = penal_2024()

    # Act 1 of 2021: the e-Laws notes name it for s 68 only, and its bulletin says "Amends: s 68".
    act1 = sorted(k for k, ns in live_notes.items() if any(re.search(r'\b1 of 2021\b', n) for n in ns))
    if act1 != ['s-068']:
        raise SystemExit(f'Act 1 of 2021 notes: {act1}')
    b1 = bulletin(BULLETIN_ACT_1_2021)
    if 'Date of Commencement: 5th February, 2021' not in b1 or 'Amends: s 68' not in b1:
        raise SystemExit(f'bulletin for Act 1 of 2021 changed: {b1}')
    act29 = sorted(k for k, ns in live_notes.items() if any(re.search(r'\b29 of 2022\b', n) for n in ns))
    if act29 != ['s-058']:
        raise SystemExit(f'Act 29 of 2022 notes: {act29}')
    b29 = bulletin(BULLETIN_ACT_29_2022)
    if 'Date of Commencement: On Notice' not in b29:
        raise SystemExit(f'bulletin for Act 29 of 2022 changed: {b29}')

    v2 = dict(c19)
    v2['s-068'] = live['s-068']

    lst19 = amendment_list(CONST_2019, 'L.N. 83, 1966')
    lst_live = amendment_list(CONST_LIVE, 'L.N. 83, 1966')
    if lst19[-1] != 'S.I. 57, 2018' or lst_live[-4:] != ['S.I. 57, 2018', 'Act 1, 2021', 'Act 29, 2022', 'S.I. 93, 2024']:
        raise SystemExit(f'amendment lists changed: {lst19[-2:]} / {lst_live[-5:]}')
    pl24, pl26 = amendment_list(PENAL_2024, 'Law 2, 1964'), amendment_list(PENAL_2026, 'Law 2, 1964')
    if pl24 != pl26 or pl24[-1] != 'S.I. 93, 2023':
        raise SystemExit(f'Penal Code amendment list changed: {pl24[-3:]} / {pl26[-3:]}')

    country = {
        'code': 'BW', 'name': 'Botswana', 'slug': 'botswana', 'lang': 'en', 'tz': 'Africa/Gaborone',
        'future_branch': 'future',
        'publisher': PUBLISHER,
        'default_in_force_rule': {
            'text': 'Interpretation Act (Cap. 01:04): an enactment comes into operation on the date of its publication '
                    'in the Gazette unless it provides otherwise; amending Acts here name their own commencement '
                    '("Date of Commencement" in the e-Laws bulletin), which is used as given.',
            'source': 'https://e-laws.botswanalaws.com/principal-legislation/interpretation/'},
        'licence_note': 'Botswana e-Laws: "Copyright (c) 2026. All right reserved. Government of Botswana." Text read '
                        'from the publisher\'s open Constitution page and from Internet Archive captures of its earlier '
                        'site (botswanalaws.com). Whether Botswana excludes legislative texts from copyright is not '
                        'verified; this repository is private.',
    }
    sources = [
        {'name': 'Botswana e-Laws: Constitution of Botswana (open page)', 'url': CONST_LIVE, 'retrieved': '2026-10-28',
         'requests': 1, 'sha256': sha(CONST_LIVE),
         'licence': 'All rights reserved, Government of Botswana (site footer)',
         'notes': 'Consolidated to S.I. 93 of 2024, with per-provision amendment notes. Used for s 68 as amended by '
                  'Act 1 of 2021 and to check which provisions later Acts touched. Every other consolidated act on '
                  'e-Laws is members-only and was not read.'},
        {'name': 'botswanalaws.com (same publisher\'s previous site), Internet Archive capture 2019-05-26',
         'url': CONST_2019, 'retrieved': '2026-10-28', 'requests': 1, 'sha256': sha(CONST_2019),
         'licence': 'All rights reserved, Government of Botswana; read through the Internet Archive',
         'notes': 'Full consolidated Constitution to S.I. 57 of 2018 (the members-only tag leaked in this capture).'},
        {'name': 'botswanalaws.com, Internet Archive capture 2024-12-04', 'url': PENAL_2024, 'retrieved': '2026-10-28',
         'requests': 1, 'sha256': sha(PENAL_2024),
         'licence': 'All rights reserved, Government of Botswana; read through the Internet Archive',
         'notes': 'Full consolidated Penal Code (Cap. 08:01) to S.I. 93 of 2023.'},
        {'name': 'botswanalaws.com, Internet Archive capture 2026-03-23 (Penal Code page, members-only)',
         'url': PENAL_2026, 'retrieved': '2026-10-28', 'requests': 1, 'sha256': sha(PENAL_2026),
         'licence': 'All rights reserved, Government of Botswana; read through the Internet Archive',
         'notes': 'No text, but the amendment list, which is the same as on 2024-12-04 (last entry S.I. 93, 2023).'},
        {'name': 'Botswana e-Laws bulletin (WordPress API excerpts)', 'url': 'https://e-laws.botswanalaws.com/wp-json/wp/v2/',
         'retrieved': '2026-10-29', 'requests': 14,
         'licence': 'All rights reserved, Government of Botswana',
         'notes': 'Open excerpts: Act 1 of 2021 "Date of Commencement: 5th February, 2021. Amends: s 68."; Act 29 of '
                  '2022 "Date of Commencement: On Notice. Amends: s 58"; the S.I. 93 of 2024 page itself is '
                  'members-only. A search for "penal code" lists no Penal Code amendment after S.I. 93 of 2023.'},
    ]
    laws = {
        'act-2021-1': {'label': 'Act 1 of 2021', 'title': 'Constitution (Amendment) Act, 2021', 'kind': 'law',
                       'enacted': None, 'published': None,
                       'url': 'https://e-laws.botswanalaws.com/act-bulletin-2021/act-1-of-2021-constitution-amendment-act/',
                       'temporary_until': None, 'restores': None, 'note': None},
    }
    earlier = ['L.N. 83, 1966'] + lst19[1:]
    const = {
        'slug': 'constitution', 'short': 'Constitution', 'title': 'Constitution of Botswana', 'url': CONST_LIVE,
        'first_law': None, 'earlier_laws': [],
        'versions': [
            {'from': '2019-05-26', 'source_url': CONST_2019, 'sha256': sha(CONST_2019), 'units': c19, 'credits': {},
             'note': 'Consolidated by the publisher to S.I. 57 of 2018 (amendment list: ' + ', '.join(earlier) + '). '
                     'Dated by the day the Internet Archive captured it; the date the publisher consolidated it to is '
                     'not given.'},
            {'from': '2021-02-05', 'source_url': CONST_LIVE, 'sha256': sha(CONST_LIVE), 'units': v2,
             'credits': {'s-068': ['act-2021-1']},
             'note': 'Section 68 as amended by Act 1 of 2021 (in force 5 February 2021, e-Laws bulletin), from today\'s '
                     'e-Laws text of s 68, which no later Act touched; every other provision as on 2019-05-26.'},
        ],
    }
    penal = {
        'slug': 'penal-code', 'short': 'Penal Code', 'title': 'Penal Code (Cap. 08:01)',
        'url': 'https://e-laws.botswanalaws.com/principal-legislation/penal-code/',
        'first_law': None, 'earlier_laws': [],
        'versions': [
            {'from': '2024-12-04', 'source_url': PENAL_2024, 'sha256': sha(PENAL_2024), 'units': pc, 'credits': {},
             'note': 'Consolidated by the publisher to S.I. 93 of 2023 (amendment list: ' + ', '.join(pl24) + '). '
                     'Dated by the day the Internet Archive captured it: the commencement date of Act 27 of 2021 '
                     '(S.I. 93 of 2023) is not in any open source.'},
        ],
    }
    decisions_common = [
        'Botswana e-Laws (e-laws.botswanalaws.com) is the official consolidation; only its Constitution page is open. '
        'Every other act is members-only and was never read or worked around; earlier full texts come only from '
        'Internet Archive captures of the publisher\'s previous site (botswanalaws.com) in which the members-only tag '
        'leaked.',
        'Text normalisation: hidden <input> notes, tags and footnote markers dropped; NBSP to space; curly quotes to '
        'straight; en and em dashes to "-"; runs of spaces collapsed. e-Laws amendment notes ("[1 of 2021, s. 2(a).]") '
        'are not text: they are read for credits only. The closing e-Laws editorial note on Act 9 of 2005\'s word '
        'substitutions is not part of any unit.',
        'Units: one file per section (s-NNN, s-051-a, s-020-to-029 for the repealed range) and per schedule '
        '(schedule-N). Chapter and part headings are not units.',
    ]
    decisions_const = [
        'Constitution v1 (2019-05-26): the 2019-05-26 Internet Archive capture, consolidated to S.I. 57 of 2018. Its '
        'own as-at date is not stated, so it is dated by the capture day and credited to the publisher as the oldest '
        'version available.',
        'Constitution v2 (2021-02-05): Act 1 of 2021, "Date of Commencement: 5th February, 2021. Amends: s 68" (e-Laws '
        'bulletin). s 68 is taken from today\'s e-Laws page, whose notes name Act 1 of 2021 for s 68(1) and (5) and '
        'no later Act for s 68; every other section stays as in 2019, because the amendment lists show no other '
        'change between S.I. 57 of 2018 and Act 1 of 2021.',
        'Act 29 of 2022 (amends s 58, commenced by S.I. 93 of 2024) is LEFT OUT: its bulletin says "Date of '
        'Commencement: On Notice", the S.I. 93 of 2024 page and the 2024 subsidiary-legislation list are members-only, '
        'and no other open source gives the day it took effect. So the last version here is not today\'s text, and '
        'this act is not marked verified (no corpus.d/10-constitution.PUBLISH).',
        'Today\'s e-Laws page also differs from the 2019 text in editorial ways no note explains (spelling such as '
        '"Authorisation", "Re-appointments", cross-reference style such as "(Cap. 01:04)"); those are not '
        'built, since they would be unexplained publisher changes on a day the source does not give.',
    ]
    decisions_penal = [
        'Penal Code: one version, the 2024-12-04 Internet Archive capture, consolidated to S.I. 93 of 2023 (Act 27 of '
        '2021, commenced "On Notice"); dated by the capture day because the commencement date of S.I. 93 of 2023 is '
        'in no open source; credited to the publisher as the oldest version available.',
        'Penal Code is today\'s text: the 2026-03-23 capture of the same page lists the same amendments (last S.I. 93, '
        '2023), and the e-Laws bulletin search lists no later Penal Code amendment (retrieved 2026-10-29).',
    ]
    ai = ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py and parse.py and chose the sources. '
          'No model wrote or altered legal text, and no model runs at build time.']
    corpus = {'country': country, 'sources': sources, 'laws': {}, 'acts': [], 'applies': [],
              'decisions': decisions_common, 'ai_use': ai}
    part_const = {'laws': laws, 'acts': [const], 'decisions': decisions_const}
    part_penal = {'acts': [penal], 'decisions': decisions_penal}
    return corpus, part_const, part_penal, live, c19


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(path)


def main(argv: list[str]) -> None:
    corpus, pc, pp, live, c19 = build()
    write(HERE / 'corpus.json', corpus)
    write(HERE / 'corpus.d' / '10-constitution.json', pc)
    write(HERE / 'corpus.d' / '20-penal-code.json', pp)
    print(f'constitution: {len(c19)} units (2019), {len(live)} units (today); '
          f'penal code: {len(pp["acts"][0]["versions"][0]["units"])} units')
    if '--diff' in argv:
        for k in sorted(set(c19) | set(live)):
            a, b = c19.get(k, {}).get('text'), live.get(k, {}).get('text')
            if a != b:
                print('differs:', k)


if __name__ == '__main__':
    main(sys.argv[1:])
