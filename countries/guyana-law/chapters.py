"""corpus.d/50-chapters.json: further chapters of the Laws of Guyana, each from the revised editions online.

Reads only the cache (fetch with `python -X utf8 fetch_chapters.py`). Deterministic. Written atomically. Uses the
layout and segmentation of parse.py (the same as the Civil Law and Criminal Law (Offences) Acts in corpus.json).

    python -X utf8 chapters.py            (CHAPTERS_OUT=... to write elsewhere)

Today's official text on mola.gov.gy is L.R.O. 1/2022 for Cap. 3:02 only; for Caps. 10:01 and 98:01 (and 89:01, in its
own part, companies.py) the Ministry still serves the L.R.O. 1/2012 PDF (byte-identical to the Internet Archive capture of 2022), so those have
one version.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse  # noqa: E402

WB = 'https://web.archive.org/web/'
MOLA = 'https://www.mola.gov.gy/laws/'
PARL = 'https://www.parliament.gov.gy/documents/acts/'
OUT = Path(os.environ.get('CHAPTERS_OUT', HERE / 'corpus.d' / '50-chapters.json'))
RETRIEVED = '2026-10-29'

E2012_NOTE = ('Revised edition L.R.O. 1/2012 (the Laws of Guyana as they stood on 31 December 2012), read from the '
              'Internet Archive (captured {cap}).')

# Amending laws as each chapter's front page lists them (metadata, typed from the page; the PDFs set them in
# columns that the text layer reads out of order).
CHAPTERS = [
    {'slug': 'criminal-law-procedure', 'short': 'Criminal Law (Procedure) Act', 'cap': '10:01',
     'title': 'Criminal Law (Procedure) Act (Cap. 10:01)', 'first': ('act-19-1893', 'Act No. 19 of 1893', 'Criminal Law (Procedure) Ordinance 1893'),
     'editions': {'e2012': (WB + '20220622193927id_/https://mola.gov.gy/sites/default/files/Cap.%201001%20Criminal%20Law%20Procedure.pdf', 13, 169, 9.5)},
     'current': MOLA + 'Volume 3 Cap. 6.03 - 10.071696982382.pdf', 'captured': '22 June 2022',
     'amenders': ['25 of 1893', '11 of 1894', '13 of 1894', '10 of 1903', '3 of 1905', '11 of 1907', '16 of 1909',
                  '18 of 1910', '25 of 1918', '20 of 1918', '2 of 1921', '12 of 1922', '34 of 1922', '5 of 1923',
                  '27 of 1925', '27 of 1927', '4 of 1929', '40 of 1929', '31 of 1930', '21 of 1931', '51 of 1932',
                  '20 of 1932', '20 of 1939', '20 of 1944', 'O. 56/1947', '2 of 1948', '30 of 1950', '57 of 1952',
                  '9 of 1953', '14 of 1955', '38 of 1955', '18 of 1956', '18 of 1957', '22 of 1961', '40 of 1961',
                  'O. 68/1961', '5 of 1962', 'O. 37/1966A', '21 of 1968', '24 of 1969', 'O. 15/1970', '4 of 1972',
                  '25 of 1973', 'O. 4/1974', '21 of 1978', '3 of 1980', 'O. 80/1980', '12 of 1988', '19 of 1990',
                  '19 of 1991', '6 of 1997', '17 of 2008', '7 of 2010'],
     'missing': [('act-4-2023', 'Act No. 4 of 2023', 'Criminal Law (Procedure) (Amendment) Act 2023', '2023-05-12', PARL + '23648-act_no._4_of_2023.pdf'),
                 ('act-11-2024', 'Act No. 11 of 2024', 'Criminal Law Procedure (Paper Committals) Act 2024', '2024-07-15', PARL + '24353-24063-act_no._11_of_2024.pdf')]},
    {'slug': 'high-court', 'short': 'High Court Act', 'cap': '3:02',
     'title': 'High Court Act (Cap. 3:02)', 'first': ('act-10-1915', 'Act No. 10 of 1915', 'High Court Ordinance 1915'),
     'editions': {'e2012': (WB + '20220622190133id_/https://mola.gov.gy/sites/default/files/Cap.302%20High%20Court.pdf', 7, 39, 9.5),
                  'e2022': (MOLA + 'Volume 1 Cap. 1.01 - 3.041785164285.pdf', 6, 37, 9.5)},
     'current': MOLA + 'Volume 1 Cap. 1.01 - 3.041785164285.pdf', 'captured': '22 June 2022',
     'amenders': ['20 of 1919', '2 of 1921', '20 of 1921', '23 of 1923', '10 of 1925', '15 of 1926', '25 of 1930',
                  '16 of 1931', '2 of 1935', '32 of 1936', '16 of 1949', '3 of 1950', '23 of 1955', '42 of 1956',
                  '19 of 1958', '9 of 1959', '12 of 1960', 'O. 68/1961', '26 of 1962', '2 of 1965', 'O. 37/1966B',
                  '12 of 1967', '4 of 1972', 'O. 30/1972', '15 of 1978', '21 of 1978', 'O. 80/1980', '20 of 1984',
                  '14 of 1988', '8 of 1991', '2 of 1993', '6 of 1997', '21 of 2007'],
     'after2012': ['9 of 2013'], 'missing': []},
    # Companies Act (Cap. 89:01): its own part, corpus.d/55-companies.json (companies.py).
    {'slug': 'labour', 'short': 'Labour Act', 'cap': '98:01',
     'title': 'Labour Act (Cap. 98:01)', 'first': ('act-2-1942', 'Act No. 2 of 1942', 'Labour Ordinance 1942'),
     'editions': {'e2012': (WB + '20220730124937id_/https://mola.gov.gy/sites/default/files/Cap.%209801.pdf', 6, 41, 9.5)},
     'current': MOLA + 'Volume 18 Cap. 91.02 - 96.011695660707.pdf', 'captured': '30 July 2022',
     'amenders': ['30 of 1947', '42 of 1955', '39 of 1955', '8 of 1956', '29 of 1960', '12 of 1961', '4 of 1972',
                  '5 of 1974', '8 of 1975', '19 of 1977', '22 of 1978', '9 of 1984', '19 of 1990', '20 of 1994',
                  '19 of 1997'], 'missing': []},
]


def law_key(name: str) -> tuple[str, str, str]:
    m = re.fullmatch(r'(\d+) of (\d{4})', name)
    if m:
        return f'act-{m.group(1)}-{m.group(2)}', f'Act No. {m.group(1)} of {m.group(2)}', 'law'
    m = re.fullmatch(r'O\. (\d+)/(\d{4})([AB]?)', name)
    return (f'order-{m.group(1)}-{m.group(2)}{m.group(3).lower()}', f'Order No. {m.group(1)} of {m.group(2)}{m.group(3)}',
            'decree')


def blank_law(label: str, title: str, kind: str = 'law', **kw) -> dict:
    return {'label': label, 'title': title, 'kind': kind, 'enacted': None, 'published': kw.get('published'),
            'url': kw.get('url'), 'temporary_until': None, 'restores': None, 'note': kw.get('note')}


def laws() -> dict:
    out = {}
    for ch in CHAPTERS:
        k, label, title = ch['first']
        out[k] = blank_law(label, title)
        for n in ch['amenders'] + ch.get('after2012', []):
            k, label, kind = law_key(n)
            out.setdefault(k, blank_law(label, f'{label} (named as amending Cap. {ch["cap"]})', kind))
    return out


# The layout fix for cross-headings now lives in parse.py (shared with Caps. 6:01 and 8:01 in corpus.json).
DROPPED = parse.DROPPED
tidy_sections = parse.tidy_sections


def act(ch: dict) -> dict:
    eds = parse.read_all(ch['editions'], 'sec')
    eds = {ed: (tidy_sections(u), m) for ed, (u, m) in eds.items()}
    note12 = E2012_NOTE.format(cap=ch['captured'])
    url12 = ch['editions']['e2012'][0]
    u12 = parse.as_units(parse.clean_units(eds['e2012'][0]))
    if 'e2022' not in ch['editions']:
        note12 += (' The Ministry of Legal Affairs still serves this same edition (byte-identical) as the chapter\'s '
                   'current text on mola.gov.gy; it lists no amending Act after ' + ch['amenders'][-1].split(' of ')[-1] + '.')
    versions = [{'from': '2012-12-31', 'source_url': url12, 'sha256': parse.sha(url12), 'units': u12, 'credits': {},
                 'note': note12}]
    if 'e2022' in ch['editions']:
        url22 = ch['editions']['e2022'][0]
        u22 = parse.as_units(parse.clean_units(eds['e2022'][0]))
        if u22 != u12:
            versions.append({'from': '2022-12-31', 'source_url': url22, 'sha256': parse.sha(url22), 'units': u22,
                             'credits': {},
                             'note': 'The 2022 revised edition (L.R.O. 1/2022; the Laws of Guyana as they stood on 31 '
                                     'December 2022), today\'s official text on mola.gov.gy. It includes Act No. 9 of '
                                     '2013; its changes are committed as unexplained because the editions do not '
                                     'say which words each Act changed.'})
    if ch['missing']:
        versions[-1]['note'] += (' Not applied: ' + '; '.join(f'{label} ({title}, Official Gazette {day})'
                                                              for _k, label, title, day, _u in ch['missing'])
                                 + ', printed by Parliament only as scans without a text layer (no OCR); the '
                                   'sections they amend show their earlier text.')
    earlier = [ch['first'][0]] + [law_key(n)[0] for n in ch['amenders']]
    return {'slug': ch['slug'], 'short': ch['short'], 'title': ch['title'], 'url': ch['current'],
            'first_law': None, 'earlier_laws': earlier, 'versions': versions}


DECISIONS = [
    'Further chapters (Criminal Law (Procedure) Act Cap. 10:01, High Court Act Cap. 3:02, Labour Act Cap. 98:01): the only texts online are the revised editions, so each starts as "oldest version available" on 2012-12-31 (L.R.O. 1/2012, read from the Internet Archive). For Cap. 3:02 the 2022 revised edition (L.R.O. 1/2022) is on mola.gov.gy and its differences are unexplained changes on 2022-12-31; for Caps. 10:01 and 98:01 the Ministry of Legal Affairs still serves the L.R.O. 1/2012 PDF (byte-identical to the archived copy) as the current chapter, so they have that one version.',
    'Further chapters are read with the same layout and segmentation as Caps. 6:01 and 8:01 (layout.py, parse.py): marginal notes, the arrangement of sections, the long title and Part headings are left out; sections printed only as a repeal note have no file; schedules are units of their own; subsidiary legislation printed after the Act is not included.',
    'Criminal Law (Procedure) Act: Act No. 4 of 2023 (Criminal Law (Procedure) (Amendment) Act 2023, Official Gazette 12 May 2023) and Act No. 11 of 2024 (Criminal Law Procedure (Paper Committals) Act 2024, Official Gazette 15 July 2024) are printed by Parliament only as scans without a text layer, and no revised edition online includes them. Which sections they amend, and when they commence, cannot be read without OCR, so they have no commit; they are named in the version note and the README, and the Act here is the text of L.R.O. 1/2012, which is not the law in force on those points.',
    'Further chapters: two layout slips are fixed the same way in every edition (parse.py tidy_sections): the italic cross-heading between two sections ("Gaol Delivery", "(i) Appeals from the Court"), which the reader takes as the last line of the section before it, is dropped like the Part headings; and s. 152 of Cap. 10:01, printed "152 The Court ..." without its full stop, is split from s. 151.',
    'Criminal Law (Procedure) Act: its Fifth Schedule (Rules) and Sixth Schedule (Remuneration of Witnesses) are units of their own (sch-5, sch-6); until 2026-10-29 the reader knew only four schedule ordinals and printed them at the end of the Fourth Schedule. The lines are the same, in the same order.',
    'High Court Act: the 2022 edition lists Act No. 9 of 2013 among the amending laws; its Gazette print was not read, so its changes are among the 2022 edition\'s unexplained changes, dated 2022-12-31 (the edition), not on the Act\'s own date.',
    'Amending laws of the further chapters are named from each chapter\'s front page (typed from the page, as the text layer reads its columns out of order); Orders keep their letter (Order No. 37 of 1966A / 1966B).',
]

AI_USE = [
    'Further chapters: Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch_chapters.py and chapters.py, chose the chapters and editions and typed the amending-law lists from the front pages; it did not write or alter any legal text.',
]


def main() -> None:
    acts = [act(ch) for ch in CHAPTERS]
    part = {
        'laws': laws(), 'acts': acts,
        'sources': [
            {'name': 'Laws of Guyana, Ministry of Legal Affairs (current chapter PDFs)', 'url': 'https://www.mola.gov.gy/laws-of-guyana',
             'retrieved': RETRIEVED, 'requests': 4, 'licence': 'none stated',
             'notes': 'Cap. 3:02 in L.R.O. 1/2022; Caps. 10:01 and 98:01 still in L.R.O. 1/2012'},
            {'name': 'Internet Archive Wayback Machine (L.R.O. 1/2012 chapter PDFs, mola.gov.gy/sites/default/files)',
             'url': 'https://web.archive.org/', 'retrieved': RETRIEVED, 'requests': 4, 'licence': 'none stated',
             'notes': 'captures of 22 June 2022 (Caps. 3:02, 10:01) and 30 July 2022 (Cap. 98:01)'},
            {'name': 'Acts of Parliament, Parliament of Guyana (Acts 4 of 2023, 11 of 2024)',
             'url': 'https://parliament.gov.gy/publications/acts-of-parliament/', 'retrieved': RETRIEVED, 'requests': 2,
             'licence': 'none stated', 'notes': 'scans without a text layer; dates read from the index and the Gazette head'},
        ],
        'applies': [], 'decisions': DECISIONS, 'ai_use': AI_USE,
    }
    OUT.parent.mkdir(exist_ok=True)
    raw = json.dumps(part, ensure_ascii=False, indent=1) + '\n'
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(raw, encoding='utf-8', newline='\n')
    os.replace(tmp, OUT)
    for a in acts:
        print(a['slug'], [(v['from'], len(v.get('units') or {})) for v in a['versions']])


if __name__ == '__main__':
    main()
