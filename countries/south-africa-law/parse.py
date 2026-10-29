"""Builds scripts/south-africa-law/corpus.json from the cache only (no network).

    python -X utf8 scripts/south-africa-law/parse.py

Acts:
  constitution  Constitution of the Republic of South Africa, 1996   (constitution.py)
  popia         Protection of Personal Information Act 4 of 2013     (below)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fetch      # noqa: E402
import gazette    # noqa: E402

GOV = 'https://www.gov.za/sites/default/files/gcis_document'
JUSTICE = 'https://www.justice.gov.za'
RETRIEVED = '2026-10-28'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm(s: str) -> str:
    """Publisher typesetting, normalised once: spaces, quotes, dashes."""
    s = s.replace(' ', ' ').replace('­', '-').replace('\t', ' ')
    s = s.replace('‘‘', '“').replace('’’', '”').replace('``', '“').replace("''", '”')
    s = s.replace('–', '—').replace(' - ', ' — ')
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s+([,;:.])(?=\s|$)', r'\1', s)
    return s


def unit_key(prefix: str, num: str) -> str:
    m = re.fullmatch(r'(\d+)([A-Z]*)', num)
    return f'{prefix}-{int(m.group(1)):03d}' + (f'-{m.group(2).lower()}' if m.group(2) else '')


# ---------------------------------------------------------------- POPIA

POPIA_URL = f'{GOV}/201409/3706726-11act4of2013popi.pdf'
POPIA_PROC_2020 = 'https://inforegulator.org.za/wp-content/uploads/2020/07/20200622-gg43461-rg11136-pr21-POPIAsections.pdf'
POPIA_DOJ = f'{JUSTICE}/legislation/acts/2013-004.pdf'


def popia_sections() -> tuple[dict, list, bytes]:
    """Every section of the Act as published (GG 37067), and the Schedule rows."""
    raw = fetch.fetch(POPIA_URL, offline=True)
    import fitz
    doc = fitz.open(stream=raw, filetype='pdf')
    # the body runs from the page where "CHAPTER 1" / "Definitions" is set in the body to the Schedule
    body_first = next(i for i in range(len(doc)) if re.search(r'^1\. In this Act', doc[i].get_text(), re.M))
    sched_first = next(i for i in range(len(doc) - 1, 0, -1) if 'No. and year of law' in doc[i].get_text()
                       and 'No. and year of law' not in doc[i - 1].get_text())
    ls = gazette.lines(raw, body_first, sched_first + 1)
    # stop the body at the SCHEDULE heading on the schedule's first page
    cut = next(i for i, l in enumerate(ls) if l.page == sched_first and l.text.startswith('SCHEDULE'))
    body = ls[:cut]
    paras = gazette.paragraphs(body)
    sections: dict[str, dict] = {}
    heading = None
    cur = None
    for text, l in paras:
        m = gazette.SECTION.match(text)
        if l.bold and m and l.x0 > 118:
            num = m.group(1)
            cur = {'num': num, 'heading': heading, 'paras': [norm(text[m.end():])]}
            sections[num] = cur
            heading = None
            continue
        if l.bold and not text.startswith('‘‘'):
            heading = norm(text)
            cur = None if not re.match(r'^(CHAPTER|Part|PART|Condition)\b', text) else cur
            if re.match(r'^(CHAPTER|Part|PART|Condition)\b', text):
                cur = None
            continue
        if cur is not None:
            cur['paras'].append(norm(text))
    sched = gazette.lines(raw, sched_first, len(doc), merge=False)
    sched = [l for l in sched if not (l.page == sched_first and l.y <= ls[cut].y)]
    return sections, sched, raw


def popia_schedule_text(ls) -> str:
    """The Schedule (Laws amended by section 110) as rows: law, short title, then the extent of amendment."""
    rows: list[dict] = []
    for l in ls:
        if l.text in ('No. and year of law', 'Short title', 'Extent of repeal or amendment') or l.text.startswith('SCHEDULE') \
                or l.text.startswith('Laws amended by'):
            continue
        if l.x0 < 205:
            if re.match(r'^Act (No\. )?\d+ of \d{4}', l.text):
                rows.append({'law': [l.text], 'title': [], 'body': []})
            elif rows:
                rows[-1]['law'].append(l.text)
        elif l.x0 < 298:
            if rows:
                rows[-1]['title'].append(l.text)
        elif rows:
            rows[-1]['body'].append(l)
    out = ['# Schedule: Laws amended by section 110']
    for r in rows:
        out.append(norm(f'{gazette.join(r["law"])} — {gazette.join(r["title"])}'))
        for text, _ in gazette.paragraphs(r['body'], right=455):
            out.append(norm(text))
    return '\n'.join(out) + '\n'


def section_text(s: dict, drop_sub: str | None = None) -> str:
    title = f'# {s["num"]}. {s["heading"]}' if s.get('heading') else f'# {s["num"]}.'
    paras = list(s['paras'])
    if drop_sub:
        # leave out one subsection (and its paragraphs) that is not yet in force
        out, skip = [], False
        for p in paras:
            m = re.match(r'^\((\d+[A-Z]*)\)', p)
            if m:
                skip = m.group(1) == drop_sub
            if not skip:
                out.append(p)
        paras = out
    return '\n'.join([title, *paras]) + '\n'


def build_popia() -> tuple[dict, dict, list[str], list[dict]]:
    sections, sched, raw = popia_sections()
    nums = sorted(sections, key=lambda n: (int(re.match(r'\d+', n).group()), n))
    assert nums == [str(i) for i in range(1, 116)], nums
    h = sha(raw)

    def unit(num: str, drop: str | None = None) -> dict:
        return {'label': f's. {num}', 'kind': 'section', 'text': section_text(sections[num], drop)}

    first = ['1', *[str(i) for i in range(39, 55)], '112', '113']
    second = [*[str(i) for i in range(2, 39)], *[str(i) for i in range(55, 110)], '111', '114']
    # s. 115 (short title and commencement) is in force with the Act's first commencement
    first.append('115')
    v1 = {k: unit(n) for n in first for k in [unit_key('section', n)]}
    sched_text = popia_schedule_text(sched)
    laws = {
        'act-2013-4': {'label': 'Act 4 of 2013', 'title': 'Protection of Personal Information Act, 2013', 'kind': 'law',
                       'enacted': '2013-11-19', 'published': '2013-11-26', 'url': POPIA_URL,
                       'temporary_until': None, 'restores': None, 'note': None},
        'proc-r25-2014': {'label': 'Proc. R25 of 2014', 'title': 'Commencement of certain sections of the Protection of '
                          'Personal Information Act, 2013', 'kind': 'decree', 'enacted': '2014-04-11', 'published': '2014-04-11',
                          'url': POPIA_DOJ, 'temporary_until': None, 'restores': None,
                          'note': 'A presidential proclamation under s. 115 of the Act: it brought s. 1, Part A of Chapter 5 '
                                  '(ss. 39 to 54) and ss. 112 and 113 into force on 11 April 2014. It changed no words.'},
        'proc-r21-2020': {'label': 'Proc. R21 of 2020', 'title': 'Commencement of certain sections of the Protection of '
                          'Personal Information Act, 2013', 'kind': 'decree', 'enacted': '2020-06-17', 'published': '2020-06-22',
                          'url': POPIA_PROC_2020, 'temporary_until': None, 'restores': None,
                          'note': 'A presidential proclamation under s. 115 of the Act: ss. 2 to 38, 55 to 109, 111 and '
                                  '114(1) to (3) commence on 1 July 2020; ss. 110 and 114(4) on 30 June 2021. It changed no words.'},
        'gn-297-2021': {'label': 'GN 297 of 2021', 'title': 'Information Regulator: date from which s. 58(2) applies to processing '
                        'referred to in s. 57', 'kind': 'decree', 'enacted': '2021-04-01', 'published': '2021-04-01',
                        'url': POPIA_DOJ, 'temporary_until': None, 'restores': None,
                        'note': 'GN 297 in GG 44383 of 1 April 2021, as amended by GN 560 in GG 44761 of 25 June 2021 and '
                                'GenN 395 in GG 44782 of 30 June 2021: s. 58(2) applies to the processing referred to in '
                                's. 57 only from 1 February 2022. It changed no words.'},
    }
    # s. 114 without subsection (4) until 30 June 2021
    v2_units = dict(v1)
    for n in second:
        v2_units[unit_key('section', n)] = unit(n, drop='4' if n == '114' else None)
    v3_units = dict(v2_units)
    v3_units[unit_key('section', '110')] = unit('110')
    v3_units[unit_key('section', '114')] = unit('114')
    v3_units['schedule'] = {'label': 'Schedule', 'kind': 'schedule', 'text': sched_text}
    added2 = [unit_key('section', n) for n in second]
    added3 = [unit_key('section', '110'), unit_key('section', '114'), 'schedule']
    versions = [
        {'from': '2014-04-11', 'source_url': POPIA_URL, 'sha256': h, 'units': v1, 'credits': {},
         'note': 'Only s. 1, Part A of Chapter 5 (ss. 39 to 54) and ss. 112, 113 and 115 are in force from this day '
                 '(Proc. R25 in GG 37544 of 11 April 2014); the rest of the Act is added on the day it commences.'},
        {'from': '2014-04-11', 'same_day': True, 'source_url': POPIA_URL, 'sha256': h,
         'credits': {k: ['proc-r25-2014'] for k in sorted(v1)}},
        {'from': '2020-07-01', 'source_url': POPIA_URL, 'sha256': h, 'units': v2_units,
         'credits': {k: ['act-2013-4'] for k in added2},
         'note': 'Commenced by Proc. R21 in GG 43461 of 22 June 2020. Section 114(4) is left out until 30 June 2021.'},
        {'from': '2020-07-01', 'same_day': True, 'source_url': POPIA_URL, 'sha256': h,
         'credits': {k: ['proc-r21-2020'] for k in added2}},
        {'from': '2021-06-30', 'source_url': POPIA_URL, 'sha256': h, 'units': v3_units,
         'credits': {k: ['act-2013-4'] for k in added3},
         'note': 'Sections 110 and 114(4) commence (Proc. R21 in GG 43461 of 22 June 2020); the Schedule, which s. 110 '
                 'gives effect to, is added with it.'},
        {'from': '2021-06-30', 'same_day': True, 'source_url': POPIA_URL, 'sha256': h,
         'credits': {k: ['proc-r21-2020'] for k in added3}},
        {'from': '2022-02-01', 'source_url': POPIA_DOJ, 'sha256': h,
         'credits': {unit_key('section', '58'): ['gn-297-2021']}},
    ]
    act = {'slug': 'popia', 'short': 'POPIA', 'title': 'Protection of Personal Information Act 4 of 2013',
           'url': POPIA_URL, 'first_law': 'act-2013-4', 'earlier_laws': [], 'versions': versions}
    decisions = [
        'POPIA text: the Act as published in Government Gazette 37067 of 26 November 2013 (gov.za PDF, born-digital text '
        'layer; no OCR). The Act has not been amended, so its words are the same in every version.',
        'POPIA commencement: each section is added on the day it commenced: 11 April 2014 (Proc. R25 of 2014: ss. 1, '
        '39-54, 112, 113), 1 July 2020 (Proc. R21 of 2020: ss. 2-38, 55-109, 111, 114(1)-(3)) and 30 June 2021 '
        '(Proc. R21 of 2020: ss. 110, 114(4)). The commencement table of the Department of Justice consolidation '
        '(justice.gov.za/legislation/acts/2013-004.pdf) and the text of Proc. R21 (inforegulator.org.za) are the sources.',
        'POPIA s. 115 (short title and commencement) is not named in any proclamation; it is taken as in force from the '
        'first commencement, 11 April 2014, because the proclamations are made under it.',
        'POPIA: each commencement is two commits on the day: the sections, credited to the Act (so blame names Act 4 of '
        '2013), then a no-words commit credited to the proclamation that brought them into force.',
        'POPIA s. 58(2): GN 297 of 2021 (as amended) made it apply to processing referred to in s. 57 only from 1 February '
        '2022; that is a no-words commit on that day.',
        'POPIA Schedule: set as rows (law, short title, extent of amendment). Words in square brackets are the gazette\'s '
        'bold bracketed omissions; the underlining of inserted words is not reproduced. Chapter and Part headings are '
        'not separate files.',
    ]
    sources = [{'name': 'Government Gazette 37067 (via gov.za)', 'url': POPIA_URL, 'retrieved': RETRIEVED, 'requests': 1,
                'licence': 'Official text of an Act; Copyright Act 98 of 1978 s. 12(8)(a): no copyright in official texts '
                           'of a legislative nature.', 'notes': 'Born-digital gazette PDF of the Act as assented.'},
               {'name': 'Department of Justice consolidation of POPIA', 'url': POPIA_DOJ, 'retrieved': RETRIEVED, 'requests': 1,
                'licence': 'Used to check the text and for the commencement table only.', 'notes': ''},
               {'name': 'Information Regulator: Proc. R21 of 2020 (GG 43461)', 'url': POPIA_PROC_2020,
                'retrieved': RETRIEVED, 'requests': 1, 'licence': 'Official text.', 'notes': ''}]
    return act, laws, decisions, sources


def main() -> None:
    acts, laws, decisions, sources = [], {}, [], []
    import companies_corpus
    import constitution_corpus
    only = sys.argv[sys.argv.index('--acts') + 1].split(',') if '--acts' in sys.argv else None
    for slug, builder in [('constitution', constitution_corpus.build), ('popia', build_popia),
                          ('companies-act', companies_corpus.build)]:
        if only and slug not in only:
            continue
        a, l, d, s = builder()
        acts.append(a); laws.update(l); decisions += d; sources += s
    corpus = {
        'country': {
            'code': 'ZA', 'name': 'South Africa', 'slug': 'south-africa', 'lang': 'en', 'tz': 'Africa/Johannesburg',
            'future_branch': 'future',
            'publisher': {'name': 'Government of South Africa (GCIS gov.za; Department of Justice)', 'email': 'gcis@gov-za.invalid'},
            'default_in_force_rule': {
                'text': 'Constitution s. 81: "A Bill assented to and signed by the President becomes an Act of Parliament, '
                        'must be published promptly, and takes effect when published or on a date determined in terms of the Act."',
                'source': 'https://www.justice.gov.za/legislation/constitution/SAConstitution-web-eng.pdf'},
            'licence_note': 'Text of Acts from the Government Gazette (gov.za, justice.gov.za). Copyright Act 98 of 1978 '
                            's. 12(8)(a): no copyright subsists in official texts of a legislative nature.',
        },
        'sources': sources,
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions,
        'ai_use': ['None at data-build time: fetch.py and parse.py are deterministic code, written with Claude Code '
                   '(claude-opus-5-5); no model reads, writes or summarises legal text.'],
    }
    out = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else HERE / 'corpus.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(out)
    print(f'corpus.json: {len(acts)} acts, {len(laws)} laws, '
          + ', '.join(f'{a["slug"]} {len(a["versions"])} versions' for a in acts))


if __name__ == '__main__':
    main()
