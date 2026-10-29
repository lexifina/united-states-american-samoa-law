"""Build corpus.json for Guyana from the cache only (no network).

    python -X utf8 parse.py              write corpus.json (atomically)
    python -X utf8 parse.py --compare    print the differences between the Constitution editions

The Constitution's history is built from three official consolidations of Cap. 1:01 and the amending Acts as
published by Parliament (see EDITIONS, LAWS and VERSIONS below; every choice is listed in DECISIONS).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import fetch
import layout

HERE = Path(__file__).resolve().parent

# ------------------------------------------------------------------ the Constitution editions

E2010 = ('https://web.archive.org/web/20121226190242id_/http://legalaffairs.gov.gy:80/information/laws-of-guyana/'
         'doc_download/2-chapter-00101.html')
E2012 = 'https://web.archive.org/web/20210404214043id_/https://mola.gov.gy/sites/default/files/Cap.101%20Constitution.pdf'
E2012_2016 = ('https://web.archive.org/web/20160119185919id_/http://legalaffairs.gov.gy/information/laws-of-guyana/'
              '410-chapter-101-the-constitution-of-the-co-operative-republic-of-guyana/file')
E2022 = 'https://www.mola.gov.gy/laws/Volume 1 Cap. 1.01 - 3.041785162884.pdf'

# (key, url, first page, last page (0-based, inclusive), smallest body font size)
EDITIONS = {
    'e2010': (E2010, 25, 215, 10.0),
    'e2012': (E2012, 29, 265, 9.5),
    'e2022': (E2022, 25, 227, 9.5),
}

ART_RE = re.compile(r'^(\d{1,3})\s?([A-Z]{0,2})\s?\.\s*(.*)$')
RANGE_RE = re.compile(r'^(\d{1,3})\s?\.?\s*-\s*(\d{1,3})\s?\.?\s*(\[.*)$')
RANGE_SPLIT = re.compile(r'(?<=\])\s+(?=\d{1,3}\s?\.?\s*-\s*\d{1,3}\s?\.?\s*\[)')
RANGE_NOTE = re.compile(r'^Sections? (\d{1,3})\s?-\s?(\d{1,3}) repealed\b')
SCHED_RE = re.compile(r'^(?:(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH) )?SCHEDULE\b')
LONG_TITLE = re.compile(r'^(?:\S+ of \d{4}\s+)?An\s+Act\b')
SCHED_NO = {None: 1, 'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5, 'SIXTH': 6}


def art_key(n: int, s: str, prefix: str = 'art') -> str:
    return f'{prefix}-{n:03d}{s.lower()}'


def _order(n: int, s: str) -> tuple:
    return (n, len(s), s)


def segment(paras: list[layout.Para], prefix: str = 'art') -> tuple[dict, dict]:
    """Paragraphs -> {unit key: [lines]} and {unit key: [marginal notes]}.

    prefix 'art': the Constitution, which starts at its PREAMBLE heading. prefix 'sec': an Act of the Laws of Guyana,
    which starts after its long title ("An Act to ..."), so the arrangement of sections before it is skipped."""
    units: dict[str, list[str]] = {}
    margins: dict[str, list[str]] = {}
    cur = None
    last = (0, 0, '')
    mode = 'before'
    for p in paras:
        t = p.text
        if mode == 'before':
            if prefix == 'sec' and LONG_TITLE.match(t):
                mode = 'art'
            elif prefix == 'art' and t == 'PREAMBLE':
                mode, cur = 'preamble', 'preamble'
                units[cur], margins[cur] = [], list(p.margin)
            continue
        m_s = SCHED_RE.match(t)
        # a bare "SCHEDULE" inside a schedule ends a heading ("PROVISIONS APPLYING TO PARTS I AND II OF THIS" /
        # "SCHEDULE", Cap. 89:01); it starts no new schedule
        if m_s and not (mode == 'sch' and m_s.group(1) is None and t == 'SCHEDULE') \
                and (p.heading or t.isupper() or mode in ('art', 'sch')):
            mode, cur = 'sch', f'sch-{SCHED_NO[m_s.group(1)]}'
            units[cur], margins[cur] = [t], list(p.margin)
            continue
        if mode == 'sch':
            units[cur].append(t)
            margins[cur] += p.margin
            continue
        m_r = RANGE_RE.match(t)
        if m_r and int(m_r.group(1)) > last[0]:
            # a run of repealed articles ("79. - 88. [Articles 79 to 88 repealed ...]"): one unit per article
            for part in RANGE_SPLIT.split(t):
                m_r = RANGE_RE.match(part)
                a, b = int(m_r.group(1)), int(m_r.group(2))
                for n in range(a, b + 1):
                    k = art_key(n, '', prefix)
                    units[k], margins[k] = [m_r.group(3)], list(p.margin)
            cur, last, mode = None, _order(b, ''), 'art'
            continue
        m_n = RANGE_NOTE.match(t)
        if m_n and last[0] < int(m_n.group(1)) <= int(m_n.group(2)):
            # "Sections 286- 304 repealed by Act No. 21 of 1998" (Cap. 89:01): no text in force, the numbering goes on
            cur, last, mode = None, _order(int(m_n.group(2)), ''), 'art'
            continue
        m_a = ART_RE.match(t)
        if m_a:
            n, s = int(m_a.group(1)), m_a.group(2)
            if _order(n, s) > last and n <= last[0] + 12:
                cur, last, mode = art_key(n, s, prefix), _order(n, s), 'art'
                units[cur], margins[cur] = [m_a.group(3)], list(p.margin)
                continue
        if (p.heading or layout._is_heading(t)) and len(t) > 2:
            # Part / Chapter / Title headings between articles are structure, not text of an article
            if mode == 'preamble':
                if not re.match(r'(CONSTITUTION OF|PART )', t):
                    units[cur].append(t)          # "WE, THE GUYANESE PEOPLE," is part of the preamble
                    continue
                mode, cur = 'art', None
            continue
        if cur is None:
            continue
        units[cur].append(t)
        margins[cur] += p.margin
    return units, margins


# ------------------------------------------------------------------ line-end hyphens

WORD_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")


def vocabulary(texts: list[str]) -> tuple[set, set]:
    plain, hyph = set(), set()
    for t in texts:
        for w in WORD_RE.findall(t.replace('⁠', ' ')):
            (hyph if '-' in w else plain).add(w.lower())
    return plain, hyph


def unhyphen(t: str, plain: set, hyph: set, unknown: list) -> str:
    def fix(m):
        a, b = m.group(1), m.group(2)
        joined, kept = (a + b).lower(), f'{a}-{b}'.lower()
        if kept in hyph:
            return f'{a}-{b}'
        if joined in plain:
            return a + b
        unknown.append(f'{a}-{b}')
        return f'{a}-{b}'
    return re.sub(r'([A-Za-z]+)-⁠([A-Za-z]+)', fix, t).replace('⁠', ' ')


def tidy(line: str) -> str:
    line = re.sub(r'\s+', ' ', line).strip()
    line = re.sub(r'\s+([,;:.])(?=\s|$)', r'\1', line)
    line = re.sub(r'\(\s+', '(', line)
    line = re.sub(r'\s+\)', ')', line)
    line = re.sub(r'\[\s+', '[', line)
    line = re.sub(r'\s*-$', ' -', line)          # "shall-" / "shall -" / "shall—": one form for a closing dash
    line = re.sub(r'^\((\d+[A-Z]*|[a-z]{1,4})\)(?=[A-Za-z])', r'(\1) ', line)   # "(1)Any" -> "(1) Any"
    line = re.sub(r'(?<=.)(\(\w{1,4}\)) (?=\(\w{1,4}\))', r'\1', line)   # "(3) (a)" -> "(3)(a)" (not at line start)
    line = re.sub(r'(\d[A-Z]{0,2}) (\(\w{1,4}\))', r'\1\2', line)          # "article 60 (2)" -> "article 60(2)"
    line = re.sub(r'([a-z])- ([a-z])', r'\1-\2', line)                       # "co- operative" -> "co-operative"
    line = re.sub(r'\.{4,}', '...', line)                                     # dotted fill-in lines in forms
    return line


def read_all(editions: dict | None = None, prefix: str = 'art', fix=None) -> dict[str, tuple[dict, dict]]:
    """fix(ed, paragraphs) -> paragraphs: an optional per-act layout repair before segmentation (Cap. 89:01's form)."""
    out = {}
    for ed, (url, a, b, bm) in (editions or EDITIONS).items():
        paras = layout.read_edition(url, ed, a, b, bm)
        out[ed] = segment(fix(ed, paras) if fix else paras, prefix)
    texts = [l for u, _ in out.values() for ls in u.values() for l in ls]
    plain, hyph = vocabulary(texts)
    # words printed in at least two editions: the vocabulary used to split words a PDF glued together
    seen: dict[str, int] = {}
    for u, _ in out.values():
        for w in vocabulary([l for ls in u.values() for l in ls])[0]:
            seen[w] = seen.get(w, 0) + 1
    known = {w for w, n in seen.items() if n >= 2}
    unknown: list[str] = []
    for ed, (u, m) in out.items():
        for k in u:
            # only the 2010 PDF glues words together; the revised editions print real compounds ("sociocultural")
            u[k] = [tidy(degl(unhyphen(l, plain, hyph, unknown), known) if ed == 'e2010' else
                         unhyphen(l, plain, hyph, unknown)) for l in u[k]]
            u[k] = [l for l in u[k] if l]
    return out


def _segment_word(w: str, known: set) -> list[str] | None:
    lw = w.lower()
    best: list = [None] * (len(lw) + 1)
    best[0] = []
    for i in range(1, len(lw) + 1):
        for j in range(max(0, i - 25), i):
            piece = lw[j:i]
            if best[j] is not None and piece in known and (len(piece) >= 2 or piece == 'a'):
                cand = best[j] + [(j, i)]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    if best[-1] is None or len(best[-1]) < 2:
        return None
    return [w[a:b] for a, b in best[-1]]


def degl(line: str, known: set) -> str:
    """Split words the PDF printed without spaces ("performthefunctions") into words seen in other editions."""
    def fix(m):
        w = m.group(0)
        if len(w) < 5 or w.lower() in known:
            return w
        parts = _segment_word(w, known)
        return ' '.join(parts) if parts else w
    return re.sub(r'[A-Za-z]+', fix, line)


def compare():
    eds = read_all()
    names = list(eds)
    keys = sorted(set().union(*[set(u) for u, _ in eds.values()]))
    print({e: len(u) for e, (u, _) in eds.items()})
    for a, b in zip(names, names[1:]):
        ua, ub = eds[a][0], eds[b][0]
        print(f'===== {a} -> {b}')
        for k in keys:
            if ua.get(k) == ub.get(k):
                continue
            if k not in ua:
                print(f'+ {k} added'); continue
            if k not in ub:
                print(f'- {k} removed'); continue
            print(f'~ {k}')
            for l in difflib.unified_diff(ua[k], ub[k], lineterm='', n=0):
                if l.startswith(('---', '+++', '@@')):
                    continue
                print('   ', l[:300])


# ------------------------------------------------------------------ units as files

# a repeal note: short (the longest printed is ~60 characters), so a one-paragraph section that only speaks of repeals
# ("14. Where any written law ... is repealed, ...", Cap. 2:01) is text, not a note
PLACEHOLDER = re.compile(r'^(?=.{0,100}$)\[?[^\[\]]*\b(repealed|Repeated)\b[^\[\]]*\]?\.?$', re.I)
SCHED_REF = re.compile(r'^Articles? [0-9A-Z]+(?:\(\d+\))?(?:(?:,| and) ?[0-9A-Z]+(?:\(\d+\))?)*$')
SCHED_NAMES = {1: 'First Schedule', 2: 'Second Schedule', 3: 'Third Schedule', 4: 'Fourth Schedule',
               5: 'Fifth Schedule', 6: 'Sixth Schedule'}


def clean_units(raw: dict[str, list[str]]) -> dict[str, list[str]]:
    """Editorial tidying shared by every edition (each step is listed in DECISIONS)."""
    out = {}
    for k, lines in raw.items():
        # editor's notes printed in the body of L.R.O. 1/2012 of Cap. 8:01: '(is to be removed)', '("to" to be removed)'
        lines = [re.sub(r'\s*\((?:[^()]*\s)?(?:to\s*)?be\s*removed\)', '', l) for l in lines]
        if k.startswith(('art-', 'sec-')) and len(lines) == 1 and PLACEHOLDER.match(lines[0]):
            continue                      # "[Article 11 repealed by Act No. 10 of 2003]": no text in force
        if k.startswith('sch-'):
            lines = [l for l in lines if not SCHED_REF.match(l)]   # the "Article 222A" side reference
            lines = [l for l in lines if not re.fullmatch(r"\w+ Schedule \(cont'd\)", l)]   # running head
            split = []
            for l in lines:
                if k == 'sch-3':
                    split += re.split(r' (?=The [A-Z])', l)
                elif k == 'sch-4':
                    split += re.split(r'(?<=\.) (?=(?:Convention|Covenant|Inter-American) )', l)
                else:
                    split.append(l)
            lines = split
        out[k] = lines
    return out


DROPPED: set[str] = set()   # the cross-headings tidy_sections left out (verify.py counts them as left out)
CROSS_HEAD = re.compile(r"^(\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\) )?[A-Z][A-Za-z,'()\- ]{1,58}$")


def tidy_sections(raw: dict[str, list[str]]) -> dict[str, list[str]]:
    """Two layout slips of the chapter PDFs (Acts with sections), fixed the same way in every edition (DECISIONS):
    - the italic cross-heading set between two sections ("Conspiracy", "(i) Appeals from the Court") is read as the
      last line of the section before it: dropped, like the Part headings;
    - a section number printed without its full stop ("152 The Court shall ...", Cap. 10:01) is read as a line of the
      section before it: split into its own section when that number is the next one and absent."""
    out = {k: list(v) for k, v in raw.items()}
    for k in list(out):
        if not k.startswith('sec-'):
            continue
        lines = out[k]
        while len(lines) > 1 and CROSS_HEAD.match(lines[-1]) and not re.search(r'[.;:,]$', lines[-1]):
            DROPPED.add(lines.pop())
        km = re.match(r'sec-(\d+)([a-z]*)', k)
        n, suf = int(km.group(1)), km.group(2)
        # the next number ("152 The Court", Cap. 10:01), or the next letter after a lettered one ("93B In any", Cap. 5:03)
        nexts = [(art_key(n + 1, '', 'sec'), f'{n + 1}')]
        if len(suf) == 1 and suf < 'z':
            s2 = chr(ord(suf) + 1)
            nexts.append((art_key(n, s2, 'sec'), f'{n}{s2.upper()}'))
        for nxt, printed in nexts:
            for i, line in enumerate(lines):
                m = re.match(rf'^{printed} (?=[A-Z])', line)
                if m and nxt not in out and i > 0:
                    out[nxt] = [line[m.end():]] + lines[i + 1:]
                    del lines[i:]
                    break
    return out


def unit_label(k: str, one_schedule: bool = False) -> str:
    if k == 'preamble':
        return 'Preamble'
    if k.startswith('sch-'):
        return 'Schedule' if one_schedule else SCHED_NAMES[int(k[4:])]
    m = re.fullmatch(r'(art|sec)-(\d+)([a-z]*)', k)
    return f'{"Art." if m.group(1) == "art" else "s."} {int(m.group(2))}{m.group(3).upper()}'


def unit_text(k: str, lines: list[str]) -> str:
    if k == 'preamble':
        head = '# Preamble'
    elif k.startswith('sch-'):
        head = None                       # a schedule's own first line is its heading ("THIRD SCHEDULE")
    elif k.startswith('sec-'):
        head = '# Section ' + unit_label(k)[3:]
    else:
        head = '# Article ' + unit_label(k)[5:]
    body = ([head] if head else []) + lines
    return '\n'.join(body) + '\n'


def as_units(lines_by_key: dict[str, list[str]]) -> dict[str, dict]:
    one = sum(k.startswith('sch-') for k in lines_by_key) == 1 and not any(k.startswith('art-') for k in lines_by_key)
    return {k: {'label': unit_label(k, one), 'kind': 'schedule' if k.startswith('sch-') else
                'preamble' if k == 'preamble' else 'section' if k.startswith('sec-') else 'art',
                'text': unit_text(k, v)}
            for k, v in sorted(lines_by_key.items())}


def sha(url: str) -> str:
    return hashlib.sha256(fetch.cached(url)).hexdigest()


def pdf_text(url: str) -> str:
    import fitz
    doc = fitz.open(stream=fetch.cached(url), filetype='pdf')
    return re.sub(r'\s+', ' ', '\n'.join(p.get_text() for p in doc))


# ------------------------------------------------------------------ laws

PARL = 'https://www.parliament.gov.gy/documents/acts/'
A5_2009 = PARL + '2938-act_no._5.pdf'
A2_2015 = PARL + '5374-5374-act_no._2_of_2015.pdf'
A1_2016 = PARL + '5713-act_no._1_of_2016.pdf'
A22_2007 = PARL + '2795-act_no_22.pdf'
A24_2006 = PARL + '4688-act_no_24_of_2006.pdf'

# Acts named on the front page of Cap. 1:01 (L.R.O. 1/2022) as amending the Constitution, up to Act 22 of 2007,
# the newest one the 2010 consolidation includes. URL = the Act as published by Parliament, where it is online.
EARLIER = [
    ('act-17-1984', 'Act No. 17 of 1984', 'Public Service Appellate Tribunal Act 1984', PARL + '8242-act_no._17_of_1984_public_service_appellate_tribunal_act_1984.pdf', 'law'),
    ('order-38-1987', 'Order No. 38 of 1987', 'Order No. 38 of 1987 (named as amending the Constitution; not online)', None, 'decree'),
    ('act-1-1988', 'Act No. 1 of 1988', 'Constitution (Amendment) Act 1988', PARL + '8533-act_1_of_1988_constitution_amendment.pdf', 'law'),
    ('act-23-1990', 'Act No. 23 of 1990', 'Constitution (Amendment) Act 1990', PARL + '8503-act_23__of_1990_constitution_amendment.pdf', 'law'),
    ('act-1-1991', 'Act No. 1 of 1991', 'Act No. 1 of 1991 (named as amending the Constitution; not online)', None, 'law'),
    ('act-12-1991', 'Act No. 12 of 1991', 'Act No. 12 of 1991 (named as amending the Constitution; not online)', None, 'law'),
    ('act-35-1991', 'Act No. 35 of 1991', 'Act No. 35 of 1991 (named as amending the Constitution; not online)', None, 'law'),
    ('act-36-1991', 'Act No. 36 of 1991', 'Act No. 36 of 1991 (named as amending the Constitution; not online)', None, 'law'),
    ('act-11-1992', 'Act No. 11 of 1992', 'Election Laws (Amendment) Act 1992', PARL + '5890-11_of_1992_election_laws_(_amendment)_act_1992.pdf', 'law'),
    ('act-21-1993', 'Act No. 21 of 1993', 'Constitution (Amendment) Act 1993', PARL + '5939-21_of_1993_constitution_(amendment)_act_1993.pdf', 'law'),
    ('act-15-1995', 'Act No. 15 of 1995', 'Constitution (Amendment) Act 1995', PARL + '6021-15_of_1995_constitution_(amendment)_act_1995.pdf', 'law'),
    ('act-2-2000', 'Act No. 2 of 2000', 'Constitution (Amendment) Act 2000', PARL + '6473-act_no._2_of_2000_constitution_(amendment)_acr_2000.pdf', 'law'),
    ('act-11-2000', 'Act No. 11 of 2000', 'Constitution (Amendment) (No. 2) Act 2000', PARL + '6481-act_no.11_opf_2000_constitution_(amendment)_(no.2_act_2000.pdf', 'law'),
    ('act-14-2000', 'Act No. 14 of 2000', 'Constitution (Amendment) (No. 3) Act 2000', PARL + '6483-act_14_of_2000_constitution_(amendment)_(no.3)_act_2000.pdf', 'law'),
    ('act-17-2000', 'Act No. 17 of 2000', 'Constitution (Amendment) (No. 4) Act 2000', PARL + '6486-act_no.17_of_2000_constitution_(amendment)_(no.4)_act_2000.pdf', 'law'),
    ('act-3-2001', 'Act No. 3 of 2001', 'Act No. 3 of 2001 (Constitution amendment)', PARL + '4458-act_no._3_of_2001.pdf', 'law'),
    ('act-4-2001', 'Act No. 4 of 2001', 'Act No. 4 of 2001 (Constitution amendment)', PARL + '4459-act_no._4_of_2001.pdf', 'law'),
    ('act-5-2001', 'Act No. 5 of 2001', 'Act No. 5 of 2001 (Constitution amendment)', PARL + '4557-act_no._5_of_2001.pdf', 'law'),
    ('act-6-2001', 'Act No. 6 of 2001', 'Act No. 6 of 2001 (Constitution amendment)', PARL + '4558-act_no._6_of_2001.pdf', 'law'),
    ('act-7-2001', 'Act No. 7 of 2001', 'Act No. 7 of 2001 (Constitution amendment)', PARL + '4559-act_no._7_of_2001.pdf', 'law'),
    ('act-8-2001', 'Act No. 8 of 2001', 'Act No. 8 of 2001 (Constitution amendment)', PARL + '4560-act_no._8_of_2001.pdf', 'law'),
    ('act-5-2003', 'Act No. 5 of 2003', 'Act No. 5 of 2003 (named as amending the Constitution; not online)', None, 'law'),
    ('act-10-2003', 'Act No. 10 of 2003', 'Act No. 10 of 2003 (Constitution amendment)', PARL + '4619-act_no_10_of_2003.pdf', 'law'),
    ('act-16-2004', 'Act No. 16 of 2004', 'Caribbean Court of Justice Act 2004', PARL + '4644-act_no._16_of_2004.pdf', 'law'),
    ('act-24-2006', 'Act No. 24 of 2006', 'Constitution (Amendment) Act 2006', A24_2006, 'law'),
    ('act-22-2007', 'Act No. 22 of 2007', 'Constitution (Amendment) Act 2007', A22_2007, 'law'),
]


def laws() -> dict:
    out = {
        'act-2-1980': {'label': 'Act No. 2 of 1980', 'title': 'Constitution of the Co-operative Republic of Guyana Act 1980',
                       'kind': 'law', 'enacted': '1980-02-20', 'published': None, 'url': None,
                       'temporary_until': None, 'restores': None, 'note': None},
    }
    for key, label, title, url, kind in EARLIER:
        out[key] = {'label': label, 'title': title, 'kind': kind, 'enacted': None, 'published': None, 'url': url,
                    'temporary_until': None, 'restores': None, 'note': None}
    out['act-22-2007'].update(enacted='2007-08-28', published='2007-08-28')
    out['act-24-2006'].update(enacted='2006-05-02', published='2006-05-02')
    out['act-5-2009'] = {'label': 'Act No. 5 of 2009', 'title': 'Constitution (Amendment) Act 2009', 'kind': 'law',
                         'enacted': None, 'published': '2009-03-17', 'url': A5_2009,
                         'temporary_until': None, 'restores': None, 'note': None}
    out['act-2-2015'] = {'label': 'Act No. 2 of 2015', 'title': 'Constitution (Amendment) Act 2015', 'kind': 'law',
                         'enacted': None, 'published': '2015-07-10', 'url': A2_2015,
                         'temporary_until': None, 'restores': None, 'note': None}
    out['act-1-2016'] = {'label': 'Act No. 1 of 2016', 'title': 'Constitution (Amendment) Act 2016', 'kind': 'law',
                         'enacted': None, 'published': '2016-01-11', 'url': A1_2016,
                         'temporary_until': None, 'restores': None, 'note': None}
    return out


# ------------------------------------------------------------------ the Constitution's versions

def act_5_2009_119d(e2012_lines: list[str]) -> list[str]:
    """Article 119D in the words of Act 5 of 2009 as printed in the Gazette of 17 March 2009.

    The Gazette PDF is a scan with an OCR text layer, so the article is taken from L.R.O. 1/2012 and the two places
    where the Gazette's wording differs from that edition are restored from the Gazette (each checked here)."""
    gz = pdf_text(A5_2009)
    assert 'There shall be a Standing Committee of the' in gz   # the OCR interleaves the side note here
    assert 'To assist it in its work, the Committee shall' in gz
    lines = [l.replace('There shall be a standing Committee', 'There shall be a Standing Committee')
              .replace('To assist in its work,', 'To assist it in its work,') for l in e2012_lines]
    assert lines != e2012_lines
    return lines


def act_2_2015_entities() -> list[str]:
    t = pdf_text(A2_2015)
    m = re.search(r'addition to the Schedule of the following entities\s*[-–]\s*(.*?)\s*Passed by the National Assembly', t)
    names = re.split(r' (?=The [A-Z])', m.group(1).strip())
    names = [n.strip().rstrip('.') for n in names]
    assert len(names) == 9, names
    return names


def act_1_2016_entity() -> str:
    t = pdf_text(A1_2016)
    m = re.search(r'addition to the Schedule of (The Parliament Office)\.', t)
    return m.group(1)


def constitution(eds: dict) -> dict:
    u10 = clean_units(eds['e2010'][0])
    u12 = clean_units(eds['e2012'][0])
    u22 = clean_units(eds['e2022'][0])
    v1 = dict(u10)
    v2 = dict(v1)
    v2['art-119d'] = act_5_2009_119d(u12['art-119d'])
    v3 = dict(u12)
    v4 = dict(v3)
    v4['sch-3'] = v3['sch-3'] + act_2_2015_entities()
    v5 = dict(v4)
    v5['sch-3'] = v4['sch-3'] + [act_1_2016_entity()]
    v6 = dict(u22)
    versions = [
        {'from': '2007-08-28', 'source_url': E2010, 'sha256': sha(E2010), 'units': as_units(v1), 'credits': {},
         'note': 'Text of the consolidation of Cap. 1:01 published by the Ministry of Legal Affairs (PDF made '
                 '1 October 2010, archived 26 December 2012). It includes Act No. 22 of 2007, in force 28 August '
                 '2007, and not Act No. 5 of 2009, so it is dated from 28 August 2007.'},
        {'from': '2009-03-17', 'source_url': A5_2009, 'sha256': sha(A5_2009), 'units': as_units(v2),
         'credits': {'art-119d': ['act-5-2009']},
         'note': 'Article 119D as inserted by Act No. 5 of 2009 (Official Gazette, Legal Supplement A, 17 March 2009).'},
        {'from': '2012-12-31', 'source_url': E2012, 'sha256': sha(E2012), 'units': as_units(v3), 'credits': {},
         'note': 'The revised edition authorised by Law Revision Order 1/2012 (the Laws of Guyana as they stood on '
                 '31 December 2012). The Law Revision Commission may correct errors and make formal changes '
                 '(Law Revision Act, Cap. 2:02, s. 11), and this edition rewrote the Constitution in gender-neutral '
                 'terms ("he" became "he or she") and corrected the 2010 consolidation in many places. No Act explains '
                 'these changes, so they are committed as unexplained. The same PDF was archived on 19 January 2016.'},
        {'from': '2015-07-10', 'source_url': A2_2015, 'sha256': sha(A2_2015), 'units': as_units(v4),
         'credits': {'sch-3': ['act-2-2015']},
         'note': 'Nine entities added to the Third Schedule by Act No. 2 of 2015 (Official Gazette, 10 July 2015), '
                 'in the words of the Act.'},
        {'from': '2016-01-11', 'source_url': A1_2016, 'sha256': sha(A1_2016), 'units': as_units(v5),
         'credits': {'sch-3': ['act-1-2016']},
         'note': 'The Parliament Office added to the Third Schedule by Act No. 1 of 2016 (Official Gazette, '
                 '11 January 2016), in the words of the Act.'},
        {'from': '2022-12-31', 'source_url': E2022, 'sha256': sha(E2022), 'units': as_units(v6), 'credits': {},
         'note': 'The 2022 revised edition (L.R.O. 1/2022; the Laws of Guyana as they stood on 31 December 2022), '
                 'today\'s official text on mola.gov.gy. Its changes against the earlier versions are revision '
                 'edits that no Act explains (for example "office of President" became "office of the President"), '
                 'so they are committed as unexplained.'},
    ]
    return {'slug': 'constitution', 'short': 'Constitution',
            'title': 'Constitution of the Co-operative Republic of Guyana',
            'url': 'https://www.mola.gov.gy/laws-of-guyana', 'first_law': None,
            'earlier_laws': ['act-2-1980'] + [k for k, *_ in EARLIER], 'versions': versions}


# ------------------------------------------------------------------ other Acts of the Laws of Guyana

CIVIL_2012 = 'https://web.archive.org/web/20220622192734id_/https://mola.gov.gy/sites/default/files/Cap%20601_0.pdf'
CIVIL_2022 = 'https://www.mola.gov.gy/laws/Volume 2 Cap. 3.05 - 6.021785167929.pdf'
CRIM_2012 = 'https://web.archive.org/web/20211123081028id_/https://mola.gov.gy/sites/default/files/Cap%20801.pdf'
CRIM_2022 = 'https://www.mola.gov.gy/laws/Volume 3 Cap. 6.03 - 10.071785253947.pdf'
A12_2021 = PARL + '22860-act_no._12_of_2021.pdf'
A10_2025 = PARL + '24371-24514-act_no._10_of_2025.pdf'

CIVIL_EDITIONS = {'e2012': (CIVIL_2012, 4, 28, 9.5), 'e2022': (CIVIL_2022, 4, 28, 9.5)}
CRIM_EDITIONS = {'e2012': (CRIM_2012, 20, 184, 9.5), 'e2022': (CRIM_2022, 20, 184, 9.5)}

# The amending laws each chapter's front page lists (L.R.O. 1/2022; Cap. 8:01's "25 of 1793" is printed "25 of 1973"
# in the side note to s. 2, and "7 of 2002" is listed only in L.R.O. 1/2012).
CIVIL_AMENDERS = ['26 of 1949', '17 of 1959', '22 of 1960', '11 of 1971', '12 of 1983']
CRIM_AMENDERS = ['11 of 1894', '12 of 1896', '24 of 1903', '10 of 1906', '28 of 1908', '3 of 1910', '29 of 1914',
                 '1 of 1915', '29 of 1918', '21 of 1922', '38 of 1927', '21 of 1932', '15 of 1937', '25 of 1939',
                 '26 of 1946', '23 of 1949', '18 of 1955', '18 of 1957', '14 of 1958', '29 of 1961', '24 of 1969',
                 'O. 15/1970', '4 of 1972', '25 of 1973', 'O. 4/1974', 'O. 166/1974', 'O. 88/1975', '21 of 1978',
                 '12 of 1988', '24 of 1990', '19 of 1991', '7 of 1995', '20 of 1997', '7 of 2002', '16 of 2005',
                 '7 of 2010', '21 of 2010']


def amender_laws(names: list[str], chapter: str) -> dict:
    out = {}
    for n in names:
        m = re.fullmatch(r'(\d+) of (\d{4})', n)
        if m:
            key, label = f'act-{m.group(1)}-{m.group(2)}', f'Act No. {m.group(1)} of {m.group(2)}'
            kind = 'law'
        else:
            m = re.fullmatch(r'O\. (\d+)/(\d{4})', n)
            key, label, kind = f'order-{m.group(1)}-{m.group(2)}', f'Order No. {m.group(1)} of {m.group(2)}', 'decree'
        out[key] = {'label': label, 'title': f'{label} (named as amending {chapter})', 'kind': kind,
                    'enacted': None, 'published': None, 'url': None,
                    'temporary_until': None, 'restores': None, 'note': None}
    return out


def other_laws() -> dict:
    out = {
        'act-15-1916': {'label': 'Act No. 15 of 1916', 'title': 'Civil Law of British Guiana Ordinance 1916',
                        'kind': 'law', 'enacted': None, 'published': None, 'url': None,
                        'temporary_until': None, 'restores': None, 'note': None},
        'act-18-1893': {'label': 'Act No. 18 of 1893', 'title': 'Criminal Law (Offences) Ordinance 1893',
                        'kind': 'law', 'enacted': None, 'published': None, 'url': None,
                        'temporary_until': None, 'restores': None, 'note': None},
    }
    out.update(amender_laws(CIVIL_AMENDERS, 'Cap. 6:01'))
    out.update(amender_laws(CRIM_AMENDERS, 'Cap. 8:01'))
    return out


def two_editions(slug: str, short: str, title: str, editions: dict, first: str, amenders: list[str],
                 notes: tuple[str, str]) -> dict:
    eds = read_all(editions, 'sec')
    u12 = clean_units(tidy_sections(eds['e2012'][0]))
    u22 = clean_units(tidy_sections(eds['e2022'][0]))
    url12, url22 = editions['e2012'][0], editions['e2022'][0]
    versions = [{'from': '2012-12-31', 'source_url': url12, 'sha256': sha(url12), 'units': as_units(u12),
                 'credits': {}, 'note': notes[0]}]
    if as_units(u22) != versions[0]['units']:
        versions.append({'from': '2022-12-31', 'source_url': url22, 'sha256': sha(url22), 'units': as_units(u22),
                         'credits': {}, 'note': notes[1]})
    keys = [first] + list(amender_laws(amenders, '').keys())
    return {'slug': slug, 'short': short, 'title': title, 'url': 'https://www.mola.gov.gy/laws-of-guyana',
            'first_law': None, 'earlier_laws': keys, 'versions': versions}


def civil_law() -> dict:
    return two_editions(
        'civil-law', 'Civil Law Act', 'Civil Law of Guyana Act (Cap. 6:01)', CIVIL_EDITIONS, 'act-15-1916',
        CIVIL_AMENDERS,
        ('Revised edition L.R.O. 1/2012 (the Laws of Guyana as they stood on 31 December 2012), read from the '
         'Internet Archive (captured 22 June 2022). The 2022 revised edition (L.R.O. 1/2022) prints the same text. '
         'Neither includes Act No. 12 of 2021 (Official Gazette, 11 August 2021), which substituted section 5(1)(b); '
         'the Gazette print of that Act is a scan without a text layer, so its words are not reproduced here and '
         'section 5(1)(b) in this file is the text before that Act.', ''))


def criminal_law() -> dict:
    return two_editions(
        'criminal-law-offences', 'Criminal Law (Offences) Act', 'Criminal Law (Offences) Act (Cap. 8:01)',
        CRIM_EDITIONS, 'act-18-1893', CRIM_AMENDERS,
        ('Revised edition L.R.O. 1/2012 (the Laws of Guyana as they stood on 31 December 2012), read from the '
         'Internet Archive (captured 23 November 2021).',
         'The 2022 revised edition (L.R.O. 1/2022; the Laws of Guyana as they stood on 31 December 2022), today\'s '
         'official text on mola.gov.gy. It lists no amending Act after 2010; its changes are revision edits and '
         'corrections that no Act explains, so they are committed as unexplained. The Criminal Law Miscellaneous '
         'Act, Act No. 10 of 2025 (Official Gazette, 5 June 2025), is later than this edition, and its Gazette '
         'print is a scan without a text layer, so it is not applied.'))


# ------------------------------------------------------------------ corpus.json

DECISIONS = [
    'Constitution: no dated versions are published, and the Act of 1980 as enacted and five amending laws (1, 12, 35, 36 of 1991; 5 of 2003; Order 38 of 1987) are not online, so the history starts at the oldest consolidation available (the 2010 consolidation, which includes Act 22 of 2007) and is replayed forward from the Acts as published in the Gazette and the two revised editions (L.R.O. 1/2012 and 1/2022).',
    'In-force dates follow the Interpretation and General Clauses Act, Cap. 2:01, s. 15: an Act comes into operation on the day it is published in the Gazette unless it says otherwise. Acts 5 of 2009, 2 of 2015 and 1 of 2016 name no other day, so their Gazette dates are used, read from the Gazette print itself (the Parliament index dates are wrong for some Acts).',
    'A revised edition is dated by the day it states its text as at: 31 December 2012 for L.R.O. 1/2012 and 31 December 2022 for L.R.O. 1/2022 (Ministry of Legal Affairs; Law Revision Act, Cap. 2:02, s. 9: the authorised pages are the Statute Book as in force on the relevant revision date). The dates of the Law Revision Orders themselves were not found.',
    'Differences between consecutive editions that no Act explains are committed by the publisher as "unexplained": the gender-neutral rewrite and corrections of L.R.O. 1/2012 (for example art. 1 "Referendum to Republic" in the 2010 consolidation, "Co-operative Republic" from 2012), and the revision edits of L.R.O. 1/2022.',
    'Article 119D (Act 5 of 2009) is in the words of the Gazette print: it says "a Standing Committee" and "To assist it in its work", where both revised editions print "a standing Committee" and "To assist in its work". The text is taken from L.R.O. 1/2012 with those two words restored, each checked against the Gazette OCR text in parse.py; the 2012 edition\'s wording then shows as an unexplained change.',
    'Act 2 of 2015 and Act 1 of 2016 add entities to the Third Schedule; the added lines are in the words of each Act ("The Office of the Ombudsman", "The Parliament Office"). L.R.O. 1/2022 prints them as "The office of the Ombudsman" and "The Parliament office.", which shows as an unexplained change on 2022-12-31.',
    'Act 24 of 2006 (Gazette 2 May 2006) made article 61 apply to the Eighth Parliament as if "four months" stood for "three months" without changing its words. It predates the oldest version available, so it has no commit; it is listed with the earlier laws.',
    'Marginal notes (the side headings and "[N of YYYY]" citations) are left out of the text. Cap. 2:01 s. 57(3) makes marginal notes part of the written law, but the 2010 consolidation prints them interleaved with the text, so they cannot be extracted reliably for every version. Each file starts with "# Article N" instead.',
    'Part, Chapter and Title headings are left out: they are structure, not text of an article. Articles printed only as a repeal note ("[Article 11 repealed by Act No. 10 of 2003]") have no file, since nothing of them is in force. Repeal notes inside an article are kept as printed.',
    'In the schedules, the side reference printed under the heading ("Article 222A") is left out, and list entries that the 2010 and 2012 PDFs print run together on one line are split one per line.',
    'Typesetting is normalised in layout.py and parse.py: one form of quotes (the 2010 PDF uses U+201F as an apostrophe, the 2012 PDF U+201A/U+201B as double quotes, and the 2022 PDF one U+201A as a comma), dashes as "-", "..." for leaders, one space, "(3) (a)" as "(3)(a)" and "60 (2)" as "60(2)", and line-end hyphens removed only when the unhyphenated word occurs elsewhere in the three editions. Words that the 2010 PDF prints without spaces ("performthefunctions") are split into words that occur in at least two editions.',
    'Images in the Second Schedule (flag, coat of arms) are not text and are not reproduced.',
    'Civil Law of Guyana Act (Cap. 6:01) and Criminal Law (Offences) Act (Cap. 8:01): the only texts online are the revised editions L.R.O. 1/2012 (read from the Internet Archive) and L.R.O. 1/2022 (mola.gov.gy), so each starts as "oldest version available" on 2012-12-31, and differences in the 2022 edition are unexplained changes on 2022-12-31. The Civil Law Act prints the same text in both editions, so it has one version.',
    'Act 12 of 2021 (Civil Law of Guyana (Amendment) Act 2021, Gazette 11 August 2021) substitutes section 5(1)(b) of Cap. 6:01, and Act 10 of 2025 (Criminal Law Miscellaneous Act 2025, Gazette 5 June 2025) is later than the 2022 edition. Both Gazette prints are scans without a text layer, and no model may write legal text, so neither is applied; the 2022 revised edition does not include Act 12 of 2021 either. Section 5(1)(b) of the Civil Law Act is therefore shown in its text before that Act.',
    'Sections printed only as a repeal note ("Repealed by Act No. 7 of 2010", some printed "Repeated by" in L.R.O. 1/2012) have no file, and the editor\'s notes printed in the body of L.R.O. 1/2012 of Cap. 8:01 ("(is to be removed)", "("to" to be removed)") are left out. Long titles and the arrangement of sections are left out; each file starts with "# Section N".',
    'The front page of Cap. 8:01 lists "25 of 1793" among the amending laws; the side note to section 2 prints it as "25 of 1973", which is used.',
    'Caps. 6:01 and 8:01 get the same layout fix as the further chapters (parse.py tidy_sections, in both editions): the italic cross-heading between two sections, which the reader takes as the last line of the section before it, is dropped like the Part headings. In Cap. 8:01 that is five headings ("Conspiracy" after s. 31, "Injury to Growing Things" after s. 114, "False Pretences" after s. 193, "Counterfeiting Coin" after s. 285, "Supplemental Provisions" after s. 302); Cap. 6:01 has none. No other line changes.',
]

AI_USE = [
    'Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py, sources.py, layout.py and parse.py and chose the sources and editions; it did not write or alter any legal text. parse.py is deterministic and runs no model; every line of law comes from an official PDF in the cache.',
]


def requests_by_host() -> dict:
    hosts: dict[str, int] = {}
    log = fetch.CACHE / 'requests.jsonl'
    for line in log.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        h = re.sub(r'^https?://([^/]+)/.*$', r'\1', r['url'])
        hosts[h] = hosts.get(h, 0) + 1
    return hosts


def corpus() -> dict:
    eds = read_all()
    hosts = requests_by_host()
    return {
        'country': {
            'code': 'GY', 'name': 'Guyana', 'slug': 'guyana', 'lang': 'en', 'tz': 'America/Guyana',
            'future_branch': 'futuro',
            'publisher': {'name': 'Ministry of Legal Affairs, Laws of Guyana', 'email': 'mola@lawsofguyana.invalid'},
            'default_in_force_rule': {
                'text': 'Interpretation and General Clauses Act, Cap. 2:01, s. 15: "Every Act shall be published in '
                        'the Gazette and shall come into operation on the date of publication unless it is provided '
                        'in that Act or some other written law that it shall come into operation on some other date."',
                'source': 'https://www.mola.gov.gy/laws/Volume 1 Cap. 1.01 - 3.041785164106.pdf'},
            'licence_note': 'Laws of Guyana, Ministry of Legal Affairs (mola.gov.gy); Acts as published by the '
                            'Parliament of Guyana (parliament.gov.gy). No licence is stated.',
        },
        'sources': [
            {'name': 'Laws of Guyana, Ministry of Legal Affairs (L.R.O. 1/2022)', 'url': 'https://www.mola.gov.gy/laws-of-guyana',
             'retrieved': '2026-10-28', 'requests': hosts.get('www.mola.gov.gy', 0) + hosts.get('mola.gov.gy', 0),
             'licence': 'none stated', 'notes': 'one PDF per chapter, current revised edition only; robots.txt allows all'},
            {'name': 'Acts of Parliament, Parliament of Guyana', 'url': 'https://parliament.gov.gy/publications/acts-of-parliament/',
             'retrieved': '2026-10-28', 'requests': hosts.get('www.parliament.gov.gy', 0) + hosts.get('parliament.gov.gy', 0),
             'licence': 'none stated', 'notes': 'Acts as published in the Official Gazette, 1928-2025, PDF'},
            {'name': 'Internet Archive Wayback Machine (earlier editions of Cap. 1:01)', 'url': 'https://web.archive.org/',
             'retrieved': '2026-10-28', 'requests': hosts.get('web.archive.org', 0),
             'licence': 'none stated', 'notes': 'the 2010 consolidation (legalaffairs.gov.gy, captured 2012-12-26) and '
                                                'L.R.O. 1/2012 (captured 2016-01-19, 2021-04-04 and 2022-03-08, byte-identical)'},
        ],
        'laws': {**laws(), **other_laws()},
        'acts': [constitution(eds), civil_law(), criminal_law()],
        'applies': [],
        'decisions': DECISIONS,
        'ai_use': AI_USE,
    }


def write():
    c = corpus()
    raw = json.dumps(c, ensure_ascii=False, indent=1, sort_keys=False) + '\n'
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(raw, encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    for a in c['acts']:
        print(a['slug'], [(v['from'], len(v['units']), sorted(v['credits'])) for v in a['versions']])


if __name__ == '__main__':
    if '--compare' in sys.argv:
        compare()
    elif '--dry' in sys.argv:
        c = corpus()
        print(json.dumps(c['acts'][0]['versions'][4]['units']['sch-3'], indent=1))
    else:
        write()
