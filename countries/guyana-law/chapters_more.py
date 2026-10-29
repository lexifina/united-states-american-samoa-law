"""corpus.d/60-chapters.json: four more chapters of the Laws of Guyana, each from its two revised editions.

Evidence Act (Cap. 5:03), Limitation Act (Cap. 7:02), Defamation Act (Cap. 6:03) and Interpretation and General Clauses
Act (Cap. 2:01): L.R.O. 1/2012 read from Internet Archive captures of mola.gov.gy (22 June 2022), and L.R.O. 1/2022,
today's chapter PDF on mola.gov.gy. Reads only the cache; deterministic; written atomically. Same layout, segmentation
and cross-heading fix as chapters.py (parse.read_all, parse.tidy_sections).

    python -X utf8 chapters_more.py            (CHAPTERS_MORE_OUT=... to write elsewhere)
    python -X utf8 verify_chapters.py corpus.d/60-chapters.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chapters  # noqa: E402
import parse  # noqa: E402

WB, MOLA = chapters.WB, chapters.MOLA
OUT = Path(os.environ.get('CHAPTERS_MORE_OUT', HERE / 'corpus.d' / '60-chapters.json'))
RETRIEVED = '2026-10-29'
CAPTURED = '22 June 2022'

# editions: (url, first page, last page (0-based, inclusive), smallest body font size). Amending laws as each
# chapter's front page lists them (typed from the page); 'after2012' = listed only in the 2022 edition.
MORE = [
    {'slug': 'evidence', 'short': 'Evidence Act', 'cap': '5:03', 'title': 'Evidence Act (Cap. 5:03)',
     'first': ('act-20-1893', 'Act No. 20 of 1893', 'Act No. 20 of 1893 (named as the origin of Cap. 5:03)'),
     'editions': {'e2012': (WB + '20220622192108id_/https://mola.gov.gy/sites/default/files/Cap%20503.pdf', 7, 71, 9.5),
                  'e2022': (MOLA + 'Volume 2 Cap. 3.05 - 6.021785166353.pdf', 7, 65, 9.5)},
     'current': MOLA + 'Volume 2 Cap. 3.05 - 6.021785166353.pdf',
     'amenders': ['35 of 1929', '21 of 1932', '29 of 1935', '46 of 1952', '29 of 1961', 'O. 37/1966A', 'O. 15/1970',
                  '4 of 1972', '12 of 1983', '5 of 1987', '20 of 1997', '10 of 2002', '10 of 2008', '19 of 2008',
                  '7 of 2010'],
     'after2012': ['1 of 2014', '13 of 2018', '15 of 2021']},
    {'slug': 'limitation', 'short': 'Limitation Act', 'cap': '7:02', 'title': 'Limitation Act (Cap. 7:02)',
     'first': ('act-1-1856', 'Act No. 1 of 1856', 'Act No. 1 of 1856 (named as the origin of Cap. 7:02)'),
     'editions': {'e2012': (WB + '20220622193113id_/https://mola.gov.gy/sites/default/files/Cap%20702.pdf', 2, 6, 9.5),
                  'e2022': (MOLA + 'Volume 3 Cap. 6.03 - 10.071785168480.pdf', 2, 6, 9.5)},
     'current': MOLA + 'Volume 3 Cap. 6.03 - 10.071785168480.pdf',
     'amenders': ['27 of 1918', '54 of 1952', '43 of 1955'], 'after2012': []},
    {'slug': 'defamation', 'short': 'Defamation Act', 'cap': '6:03', 'title': 'Defamation Act (Cap. 6:03)',
     'first': ('act-17-1959', 'Act No. 17 of 1959', 'Act No. 17 of 1959 (named as the origin of Cap. 6:03)'),
     'editions': {'e2012': (WB + '20220622192849id_/https://mola.gov.gy/sites/default/files/Cap%20603.pdf', 2, 12, 9.5),
                  'e2022': (MOLA + 'Volume 3 Cap. 6.03 - 10.071785168085.pdf', 2, 12, 9.5)},
     'current': MOLA + 'Volume 3 Cap. 6.03 - 10.071785168085.pdf',
     'amenders': ['19 of 1990'], 'after2012': []},
    {'slug': 'interpretation', 'short': 'Interpretation and General Clauses Act', 'cap': '2:01',
     'title': 'Interpretation and General Clauses Act (Cap. 2:01)',
     'first': ('act-8-1970', 'Act No. 8 of 1970', 'Act No. 8 of 1970 (named as the origin of Cap. 2:01)'),
     'editions': {'e2012': (WB + '20220622185952id_/https://mola.gov.gy/sites/default/files/Cap.201.pdf', 6, 39, 9.5),
                  'e2022': (MOLA + 'Volume 1 Cap. 1.01 - 3.041785164106.pdf', 6, 39, 9.5)},
     'current': MOLA + 'Volume 1 Cap. 1.01 - 3.041785164106.pdf',
     'amenders': ['4 of 1972', '31 of 1974', '27 of 1975', 'O. 80/1980', '6 of 1981', '10 of 1986', '6 of 1992'],
     'after2012': []},
]
for _ch in MORE:
    _ch['missing'] = []


# ------------------------------------------------------------------ layout repairs (each listed in DECISIONS)

def table_rows(url: str, page: int, header: str) -> list:
    """A schedule table read as rows (Cap. 5:03's "Chapter | Short title | Enactment"): the reader takes printed lines
    across all columns, which interleaves the cells. The first column holds the chapter numbers ("c. 8:02"), the third
    starts with "Sections"; a table row starts with a block of lines (blocks are separated by a blank line) that has
    text in the first column; each row is one line, its cells in column order, each cell's words in printed order."""
    lay = parse.layout
    doc = lay.fitz.open(stream=parse.fetch.cached(url), filetype='pdf')
    spans = [s for s in lay._spans(doc[page]) if s[6].strip()]
    head = next(s for s in spans if s[6].strip().startswith(header.split(' ', 1)[0]))
    body = sorted([s for s in spans if s[1] > head[3] + 2 and not re.fullmatch(r'\s*_+\s*', s[6])
                   and not re.match(r'\s*(L\.R\.O\.|1/20)', s[6]) and s[6].strip() != '2'], key=lambda s: (s[1], s[0]))
    b1 = max(s[2] for s in body if re.match(r'\s*c\. \d', s[6])) + 3     # right of the chapter numbers
    b2 = min(s[0] for s in body if s[6].strip().startswith('Sections')) - 3   # left of the enactment column
    blocks: list[list] = []
    last_y = None
    for s in body:
        # a blank line between table rows leaves > 14 pt (2012: 16 pt; 2022: 25 pt); lines in a cell, 4-12 pt
        if last_y is None or s[1] - last_y > 14:
            blocks.append([])
            last_y = s[3]
        blocks[-1].append((0 if s[0] < b1 else 1 if s[0] < b2 else 2, s))
        last_y = max(last_y, s[3])
    rows: list[list[list]] = []
    for b in blocks:
        if any(c == 0 for c, _s in b) or not rows:
            rows.append([[], [], []])
        for c, s in b:
            rows[-1][c].append(s)
    out = []
    for r in rows:
        cells = [' '.join(lay._join(row) for row in sorted(lay._rows(cell), key=lambda rr: rr[0][3])) for cell in r]
        text = re.sub(r'\s+', ' ', lay.norm(' '.join(x for x in cells if x), 'e2012')).strip()
        out.append(lay.Para(page, 0.0, 0.0, text, False))
    return out


def fix_evidence(ed: str, paras: list) -> list:
    i = next(n for n, p in enumerate(paras) if p.text == 'Chapter Short title Enactment')
    assert all(p.page == paras[i].page for p in paras[i:]), 'the table is the last page'
    url = next(ch for ch in MORE if ch['slug'] == 'evidence')['editions'][ed][0]
    return paras[:i + 1] + table_rows(url, paras[i].page, 'Chapter Short title Enactment')


def split_glued(paras: list, pattern: str, heading_first: bool) -> list:
    """A side note or a Part heading the 2022 PDF sets on the line of the text next to it: split it off as a
    heading paragraph (which segmentation leaves out like other headings)."""
    out = []
    for p in paras:
        m = re.fullmatch(pattern, p.text)
        if not m:
            out.append(p)
            continue
        a, b = m.group(1), m.group(2)
        head, text = (a, b) if heading_first else (b, a)
        parts = [parse.layout.Para(p.page, p.y, p.x0, head, True), parse.layout.Para(p.page, p.y, p.x0, text, False, p.margin)]
        out += parts if heading_first else parts[::-1]
    return out


FIXES = {
    ('evidence', 'e2012'): fix_evidence,
    ('evidence', 'e2022'): fix_evidence,
    # "Short title. 1. This Act may be cited ..." (side note read into the body)
    ('limitation', 'e2022'): lambda ed, ps: split_glued(ps, r'(Short title\.) (1\. .*)', True),
    # "... on a horizontal plane. PART XIII" (the next Part's number read into the last line of s. 43)
    ('interpretation', 'e2022'): lambda ed, ps: split_glued(ps, r'(.*\.) (PART [IVXLC]+)', False),
}


def act(ch: dict) -> dict:
    eds = parse.read_all(ch['editions'], 'sec',
                         lambda ed, ps: FIXES[(ch['slug'], ed)](ed, ps) if (ch['slug'], ed) in FIXES else ps)
    eds = {ed: (parse.tidy_sections(u), m) for ed, (u, m) in eds.items()}
    for u, _m in eds.values():   # a space the text layer lacks after a comma ("repealed,the", Cap. 2:01 s. 51, 2022)
        for k in u:
            u[k] = [re.sub(r',(?=[a-z])', ', ', line) for line in u[k]]
    url12, url22 = ch['editions']['e2012'][0], ch['editions']['e2022'][0]
    u12 = parse.as_units(parse.clean_units(eds['e2012'][0]))
    u22 = parse.as_units(parse.clean_units(eds['e2022'][0]))
    note12 = chapters.E2012_NOTE.format(cap=CAPTURED)
    versions = [{'from': '2012-12-31', 'source_url': url12, 'sha256': parse.sha(url12), 'units': u12, 'credits': {},
                 'note': note12}]
    later = ch['after2012']
    if u22 != u12:
        note22 = ('The 2022 revised edition (L.R.O. 1/2022; the Laws of Guyana as they stood on 31 December 2022), '
                  "today's official text on mola.gov.gy. ")
        if later:
            note22 += ('It lists ' + ', '.join(f'Act No. {n}' for n in later) + ' among the amending laws; their '
                       'changes are committed as unexplained on the edition\'s date, because the editions do not say '
                       'which words each Act changed.')
        else:
            note22 += ('It lists no amending Act after ' + ch['amenders'][-1].split(' of ')[-1].split('/')[-1]
                       + '; its changes are revision edits that no Act explains, committed as unexplained.')
        versions.append({'from': '2022-12-31', 'source_url': url22, 'sha256': parse.sha(url22), 'units': u22,
                         'credits': {}, 'note': note22})
    else:
        versions[0]['note'] += ' The 2022 revised edition (L.R.O. 1/2022, today\'s text on mola.gov.gy) prints the same text.'
    earlier = [ch['first'][0]] + [chapters.law_key(n)[0] for n in ch['amenders']]
    return {'slug': ch['slug'], 'short': ch['short'], 'title': ch['title'], 'url': ch['current'],
            'first_law': None, 'earlier_laws': earlier, 'versions': versions}


def laws() -> dict:
    out = {}
    for ch in MORE:
        k, label, title = ch['first']
        out[k] = chapters.blank_law(label, title)
        for n in ch['amenders'] + ch['after2012']:
            k, label, kind = chapters.law_key(n)
            out.setdefault(k, chapters.blank_law(label, f'{label} (named as amending Cap. {ch["cap"]})', kind))
    return out


DECISIONS = [
    'Evidence Act (Cap. 5:03), Limitation Act (Cap. 7:02), Defamation Act (Cap. 6:03) and Interpretation and General Clauses Act (Cap. 2:01): the only texts online are the revised editions, so each starts as "oldest version available" on 2012-12-31 (L.R.O. 1/2012, read from Internet Archive captures of mola.gov.gy of 22 June 2022); the differences in L.R.O. 1/2022 (today\'s chapter PDF on mola.gov.gy) are unexplained changes on 2022-12-31. An act whose two editions print the same text has one version.',
    'Evidence Act: the 2022 edition lists Acts No. 1 of 2014, 13 of 2018 and 15 of 2021 among the amending laws; their Gazette prints were not read (the Parliament index has no entry for 1 of 2014 or 15 of 2021), so their changes are among the 2022 edition\'s unexplained changes, dated 2022-12-31, not on each Act\'s own date.',
    'The four acts of corpus.d/60-chapters.json are read with the same layout, segmentation and cross-heading fix as the other chapters; long titles, the arrangement of sections, Part headings, cross-headings and marginal notes are left out. The acts of origin are named by number only ("Act No. 1 of 1856"), as the front pages give no titles.',
    'Layout repairs in these four acts, each removing or moving only what the PDF prints (no word added): the running foot "L.R.O. 1/2022" that the 2022 PDF of Cap. 5:03 splits into "1/202" + "2" is dropped like other running feet (layout.py); s. 93B of Cap. 5:03 (2012), printed "93B In any ..." without its full stop, is split from s. 93A (parse.tidy_sections); the two-column table of Cap. 5:03\'s Schedule is read cell by cell, one line per table row (the reader otherwise interleaves the columns line by line); the side note "Short title." that the 2022 PDF of Cap. 7:02 sets on the line of s. 1, and the heading "PART XIII" that the 2022 PDF of Cap. 2:01 sets on the last line of s. 43, are split off and left out like other side notes and headings; a missing space after a comma in the 2022 text layer ("repealed,the", Cap. 2:01 s. 51) is restored.',
    'A one-paragraph section that speaks of repeals (Cap. 2:01 ss. 14, 51, 52) is text, not a repeal note: repeal notes are recognised only up to 100 characters (the longest printed is about 60), so these sections are kept; no published act changed.',
    'Limitation Act and Interpretation and General Clauses Act: the 2022 edition prints the same words as the 2012 edition (after the repairs above), so each has one version.',
    'Sexual Offences Act (Cap. 8:03) was not added: its L.R.O. 1/2012 edition already lists Act No. 2 of 2013 as amending it, so that edition cannot be dated 31 December 2012, and Act 2 of 2013 is not in the Parliament index to date it.',
]

AI_USE = [
    'Corpus part 60-chapters: Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote chapters_more.py, chose the chapters and page ranges and typed the amending-law lists from the front pages; it did not write or alter any legal text.',
]


def main() -> None:
    acts = [act(ch) for ch in MORE]
    part = {
        'laws': laws(), 'acts': acts,
        'sources': [
            {'name': 'Laws of Guyana, Ministry of Legal Affairs (L.R.O. 1/2022 chapter PDFs of Caps. 2:01, 5:03, 6:03, 7:02)',
             'url': 'https://www.mola.gov.gy/laws-of-guyana', 'retrieved': RETRIEVED, 'requests': 3,
             'licence': 'none stated', 'notes': 'Cap. 2:01 was already cached for the commencement rule'},
            {'name': 'Internet Archive Wayback Machine (L.R.O. 1/2012 PDFs of Caps. 2:01, 5:03, 6:03, 7:02, mola.gov.gy/sites/default/files)',
             'url': 'https://web.archive.org/', 'retrieved': RETRIEVED, 'requests': 4, 'licence': 'none stated',
             'notes': 'captures of 22 June 2022, timestamps pinned in each version\'s source_url'},
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
