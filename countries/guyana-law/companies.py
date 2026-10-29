"""corpus.d/55-companies.json: the Companies Act (Cap. 89:01), one version (L.R.O. 1/2012, today's official text).

Reads only the cache (the PDF is fetched by fetch_chapters.py-style calls to fetch.py; see PROGRESS.md). Deterministic.
Written atomically. Uses the layout and segmentation of parse.py and the cross-heading fix of parse.tidy_sections.

    python -X utf8 companies.py            (COMPANIES_OUT=... to write elsewhere)
    python -X utf8 verify_chapters.py corpus.d/55-companies.json

The Act's sections run 1-285, then "Sections 286- 304 repealed by Act No. 21 of 1998", then 305-540 (parse.RANGE_NOTE
carries the numbering over the repealed run), and it has six schedules.
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

OUT = Path(os.environ.get('COMPANIES_OUT', HERE / 'corpus.d' / '55-companies.json'))
RETRIEVED = '2026-10-29'
URL = chapters.MOLA + 'Volume 16 Cap. 83.01 - 89.011695667005.pdf'
ARCHIVED = (chapters.WB + '20220730120547id_/https://mola.gov.gy/sites/default/files/'
            'Cap.%208901%20Companies.pdf')
PARL = chapters.PARL
# post-2012 Acts whose text layers were searched for "Companies Act" (no hit; several are partly scans)
SEARCHED = ['5373-act_1_of_2015.pdf',
            '5623-anti-money_laundering_and_cointering_the_financing_of_terrorism_(amendment)_no.2_act_2015.pdf',
            '5802-act_no._15_of_2016.pdf', '11106-11106-2_act_no._21_of_2017.pdf', '17174-17174-act_no._17_of_2018.pdf',
            '23475-anti-money_laundering_and_countering_the_financing_of_terrorism_(amendment)_act_no._12_of_2022.pdf',
            '23755-act_no._15_of_2023_pdf.pdf', '24371-24514-act_no._10_of_2025.pdf']

# (url, first page, last page (0-based, inclusive), smallest body font size): the Act, pages 28-490 as printed;
# the subsidiary legislation from page 491 is not included
CH = {'slug': 'companies', 'short': 'Companies Act', 'cap': '89:01', 'title': 'Companies Act (Cap. 89:01)',
      'first': ('act-29-1991', 'Act No. 29 of 1991', 'Companies Act 1991'),
      'editions': {'e2012': (URL, 27, 489, 9.5)}, 'current': URL,
      'amenders': ['13 of 1995', '5 of 1997', '21 of 1998', '11 of 1999'], 'missing': []}

# A cross-heading the PDF sets on the same text line as the end of the section before it (one in the Act).
GLUED = {'sec-471': ' Notices and Documents'}

# The Second Schedule, Part I (Statement in lieu of Prospectus) is a two-column form set in 9 pt on PDF pages 422-426
# (0-based 421-425). layout.read_edition takes text under 9.5 pt for side notes, so it reads none of it as text, and a
# row-by-row reading would interleave the columns. form_paras() reads it as cells instead: the left column holds the
# items (each starts at the hanging indent with a capital), the right column the entries ("1. Shares", "Cash $");
# a row starting lower-case continues the cell above. Cells are ordered by page and top, the item before its entries.
FORM_PAGES = {421: (550, 340), 422: (90, 318), 423: (90, 340), 424: (90, 318), 425: (90, 340)}  # top y, entry x
FORM_FIRST_INDENT = {421: 153, 422: 131, 423: 153, 424: 132, 425: 153}
FORM_AFTER, FORM_BEFORE = '[Insert the name of the company.]', 'PART II'


def form_paras() -> list:
    doc = parse.layout.fitz.open(stream=parse.fetch.cached(URL), filetype='pdf')
    cells: list[list] = []          # [page, top y, column, text]
    open_cell = {0: None, 1: None}
    for pno, (top, split) in FORM_PAGES.items():
        spans = [s for s in parse.layout._spans(doc[pno]) if s[4] < 9.5 and s[0] >= 120 and top < s[1] < 640]
        for row in sorted(parse.layout._rows(spans), key=lambda r: r[0][3]):
            for col in (0, 1):
                part = [s for s in row if (s[0] >= split) == bool(col)]
                if not part:
                    continue
                text = parse.layout.norm(parse.layout._join(sorted(part)), 'e2012').strip()
                if not text:
                    continue
                first = col == 0 and abs(part[0][0] - FORM_FIRST_INDENT[pno]) < 3
                cont = open_cell[col] is not None and (text[:1].islower() or (col == 0 and not first))
                if cont:
                    c = open_cell[col]
                    c[3] = parse.layout._hyph_join(c[3], text)
                else:
                    c = [pno, row[0][1], col, text]
                    cells.append(c)
                    open_cell[col] = c
    cells.sort(key=lambda c: (c[0], c[1], c[2]))
    return [parse.layout.Para(p, y, 0.0, re.sub(r'\s+', ' ', t).strip(), False) for p, y, _c, t in cells]


def fix_form(ed: str, paras: list) -> list:
    i = next(n for n, p in enumerate(paras) if p.text == FORM_AFTER)
    j = next(n for n, p in enumerate(paras) if n > i and p.heading and p.text == FORM_BEFORE)
    assert i + 1 == j, [p.text for p in paras[i + 1:j]]   # the 9.5 pt reading has no text between them
    paras[i].margin, paras[j].margin = [], []             # the form's 9 pt rows, taken for side notes
    return paras[:i + 1] + form_paras() + paras[j:]


def units() -> dict:
    eds = parse.read_all(CH['editions'], 'sec', fix_form)
    raw = parse.tidy_sections(eds['e2012'][0])
    for k, tail in GLUED.items():
        assert raw[k][-1].endswith(tail), (k, raw[k][-1][-80:])
        raw[k][-1] = raw[k][-1][:-len(tail)]
        parse.DROPPED.add(tail.strip())
    return parse.as_units(parse.clean_units(raw))


def act() -> dict:
    note = ('Revised edition L.R.O. 1/2012 (the Laws of Guyana as they stood on 31 December 2012), the PDF the '
            'Ministry of Legal Affairs serves today as the chapter on mola.gov.gy (retrieved 29 October 2026; '
            'byte-identical to the Internet Archive capture of 30 July 2022). It lists no amending Act after 1999. '
            'Sections 286 to 304 were repealed by Act No. 21 of 1998 and have no file.')
    earlier = [CH['first'][0]] + [chapters.law_key(n)[0] for n in CH['amenders']]
    return {'slug': CH['slug'], 'short': CH['short'], 'title': CH['title'], 'url': URL,
            'first_law': None, 'earlier_laws': earlier,
            'versions': [{'from': '2012-12-31', 'source_url': URL, 'sha256': parse.sha(URL), 'units': units(),
                          'credits': {}, 'note': note}]}


def laws() -> dict:
    k, label, title = CH['first']
    out = {k: chapters.blank_law(label, title)}
    for n in CH['amenders']:
        k, label, kind = chapters.law_key(n)
        out[k] = chapters.blank_law(label, f'{label} (named as amending Cap. 89:01)', kind)
    return out


DECISIONS = [
    'Companies Act (Cap. 89:01): the only text online is the revised edition L.R.O. 1/2012, which the Ministry of Legal Affairs still serves as the current chapter on mola.gov.gy (byte-identical to the Internet Archive capture of 30 July 2022), so the Act has one version, "oldest version available" on 2012-12-31. Its front page lists no amending Act after 11 of 1999, and the Parliament index lists no Companies (Amendment) Act after 1997.',
    'Companies Act: Acts after 2012 that could amend it under another title (the Anti-Money Laundering and Countering the Financing of Terrorism (Amendment) Acts 2015-2023, the Criminal Law Miscellaneous Act 2025) were searched for "Companies Act" in their text layers with no hit, but several of those prints are partly scans, so an amendment made by another Act after 2012 cannot be ruled out; none is applied.',
    'Companies Act: the PDF prints "Sections 286- 304 repealed by Act No. 21 of 1998" between ss. 285 and 305; the line is a repeal note (no file), and the segmentation carries the numbering over it (parse.RANGE_NOTE). The Act\'s Fifth and Sixth Schedules are units of their own.',
    'Companies Act: 70 italic cross-headings between sections are dropped like the Part headings (parse.tidy_sections); one of them, "Notices and Documents" before s. 472, is set on the same text line as the end of s. 471 and is cut from it. The subsidiary legislation printed after the Act (Companies Regulations, Winding Up Rules 1905 and 1995, the External Companies Exemption Order 1997) is not included.',
]

AI_USE = [
    'Companies Act: Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote companies.py and the RANGE_NOTE and Fifth/Sixth Schedule handling in parse.py, and typed the amending-law list from the front page; it did not write or alter any legal text.',
]


def main() -> None:
    a = act()
    part = {
        'laws': laws(), 'acts': [a],
        'sources': [
            {'name': 'Laws of Guyana, Ministry of Legal Affairs (Cap. 89:01 PDF, L.R.O. 1/2012)',
             'url': 'https://www.mola.gov.gy/laws-of-guyana', 'retrieved': RETRIEVED, 'requests': 1,
             'licence': 'none stated', 'notes': 'the chapter PDF served as current; 668 pages, the Act on pages 28-490'},
            {'name': 'Internet Archive Wayback Machine (Cap. 89:01, mola.gov.gy/sites/default/files, captured 2022-07-30)',
             'url': ARCHIVED, 'retrieved': RETRIEVED, 'requests': 1, 'licence': 'none stated',
             'notes': 'byte-identical to the current PDF (sha256 pinned in the version); read only to date the edition online'},
            {'name': 'Acts of Parliament, Parliament of Guyana (post-2012 Acts searched for amendments)',
             'url': 'https://parliament.gov.gy/publications/acts-of-parliament/', 'retrieved': RETRIEVED,
             'requests': len(SEARCHED), 'licence': 'none stated',
             'notes': 'text layers searched for "Companies Act": ' + ', '.join(PARL + s for s in SEARCHED)},
        ],
        'applies': [], 'decisions': DECISIONS, 'ai_use': AI_USE,
    }
    OUT.parent.mkdir(exist_ok=True)
    raw = json.dumps(part, ensure_ascii=False, indent=1) + '\n'
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(raw, encoding='utf-8', newline='\n')
    os.replace(tmp, OUT)
    print(a['slug'], [(v['from'], len(v['units'])) for v in a['versions']])


if __name__ == '__main__':
    main()
