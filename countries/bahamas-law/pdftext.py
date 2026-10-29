"""Reads one Statute Law of The Bahamas consolidation PDF (laws.bahamas.gov.bs) into provisions.

The revised editions (LRO 1/2006, 1/2008, 1/2010, 1/2017 ...) share one layout, read from the PDF's own text layer
(no OCR):
- body text is 10-12 pt (9 pt in the front matter's arrangement of sections), tables in schedules 11 pt;
- marginal notes are 8 pt in the outer margin: the section's heading (roman) and its amendment and cross-reference
  notes (italic, e.g. "34 of 2011, s. 2.");
- each section begins with its number in bold ("290. (1) Whoever ..."); Part, Book and Title headings are centred;
- running heads (above y 62) and the "STATUTE LAW OF THE BAHAMAS / LRO n/yyyy" foot (below y 636) are dropped, and
  so are footnotes (5 pt markers at the foot of a page) and superscript footnote markers.

units(pdf_bytes, ...) returns the provisions in order, each with its paragraphs (lists of printed lines, not yet
joined), its marginal heading, and every marginal note beside it; front_notes are the marginal notes before the first
provision (the act's list of amending laws). join_lines() turns printed lines into one paragraph, undoing the
typesetter's end-of-line hyphenation with a vocabulary taken from the texts themselves.
"""
from __future__ import annotations

import re
from collections import Counter

import fitz  # PyMuPDF

TOP, FOOT = 62.0, 636.0          # running head above, page foot below
MARGIN_MIN, BODY_MIN = 6.5, 8.6  # font sizes: marginal notes 8 pt, body >= 9 pt; smaller is a footnote marker
ORDINAL = r'(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)'
SCHEDULE = re.compile(rf'^(?:({ORDINAL})\s+)?SCHEDULE\b\.?\s*(.*)$')
SECTION = re.compile(r'^(\d+)([A-Z]{0,2})\.(?:\s+|$|(?=[A-Z(]))(.*)$')
BARE = re.compile(r'^(?:\d{1,3}\s+(?:of|or)\s+\d{4}|G\.\s*N\.\s*\d+\s*/\s*\d{4}|S\.\s*I\.\s*[\d/ No.]+)\.?$')
NUMBER_SPAN = re.compile(r'^\d+[A-Z]{0,2}(?:\.|$)')  # the bold first span: "290. (1) Whoever", "326", "205.Whoever"
ENUM_START = re.compile(r'^(?:\(\w{1,6}\)|"|\d+[A-Z]{0,2}\.\s)')
ORD_N = {o: i for i, o in enumerate(['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH', 'SEVENTH', 'EIGHTH',
                                      'NINTH', 'TENTH'], 1)}


def norm(s: str) -> str:
    """Publisher typesetting normalised once: spaces, quotes and dashes."""
    s = s.replace('\xa0', ' ').replace('​', '').replace('­', '')
    s = re.sub('[‘’‚′`]', "'", s)
    s = re.sub('[“”„″]', '"', s)
    s = re.sub('[‐‑‒–—―−]', '-', s)
    s = s.replace('…', '...')
    s = re.sub(r'\[Ch\d+[A-Z]?s\d+[A-Z]?\]', '', s)  # the publisher's hidden link anchors, e.g. "[Ch84s331]"
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'(?<=\w) ([.,;:])(?=\s|$)', r'\1', s)  # "offence ." as typeset


class Row:
    __slots__ = ('page', 'y', 'x0', 'x1', 'size', 'bold', 'italic', 'text', 'first')

    def __init__(self, page, spans):
        spans.sort(key=lambda s: s['bbox'][0])
        self.page = page
        self.y = min(s['bbox'][1] for s in spans)
        self.x0 = spans[0]['bbox'][0]
        self.x1 = max(s['bbox'][2] for s in spans)
        self.size = max(s['size'] for s in spans)
        f = spans[0]['font']
        self.bold = 'Bold' in f or '-Bo' in f
        self.italic = 'Ital' in f or '-It' in f
        self.first = norm(spans[0]['text'])
        out, prev = '', None
        for s in spans:
            t = s['text']
            if prev is not None and (s['bbox'][0] - prev['bbox'][2] > 1.2 or prev['text'].endswith(' ')
                                     or t.startswith(' ')):
                out += ' '
            out += t
            prev = s
        self.text = norm(out)


def _rows(spans, page):
    """Spans grouped into printed rows (same baseline within 2.5 pt), top to bottom."""
    rows: list[list] = []
    for s in sorted(spans, key=lambda s: (round(s['bbox'][1], 1), s['bbox'][0])):
        for r in rows:
            if abs(r[0]['bbox'][1] - s['bbox'][1]) <= 2.5:
                r.append(s)
                break
        else:
            rows.append([s])
    out = [Row(page, r) for r in rows]
    return sorted([r for r in out if r.text], key=lambda r: r.y)


def pages(pdf: bytes):
    """[(body rows, margin rows, centre x, left x)] for each page."""
    doc = fitz.open(stream=pdf, filetype='pdf')
    out = []
    raw = []
    for pn, p in enumerate(doc):
        body, margin, small = [], [], []
        for b in p.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    if not s['text'].strip():
                        continue
                    y = s['bbox'][1]
                    if y < TOP or y > FOOT:
                        continue
                    if s['size'] >= BODY_MIN:
                        body.append(s)
                    elif s['size'] >= MARGIN_MIN:
                        margin.append(s)
                    else:
                        small.append(s)
        raw.append((body, margin, small, _rows(body, pn)))
    # Justified lines all end at the right edge of the text block (289.4 pt wide in these editions), which sits at
    # one place on odd pages and another on even ones: take the commonest line end for each page parity.
    ends = [Counter(), Counter()]
    for pn, (_b, _m, _s, brows) in enumerate(raw):
        ends[pn % 2].update(round(r.x1) for r in brows if r.size >= 10)
    for pn, (body, margin, small, brows) in enumerate(raw):
        right = ends[pn % 2].most_common(1)[0][0] if ends[pn % 2] else 403
        left = right - 289.4
        # Footnotes: a small marker at the left edge, low on the page, starts the footnote zone. Small markers
        # elsewhere are superscript footnote references and are simply dropped.
        cuts = [s['bbox'][1] - 1 for s in small if s['bbox'][1] > 520 and s['bbox'][0] < left + 12]
        if cuts:
            brows = [r for r in brows if r.y < min(cuts)]
        # A few marginal notes are set at 9 pt: small rows wholly outside the text block are notes too.
        stray = [r for r in brows if r.size < 10 and (r.x0 > right + 3 or r.x1 < left - 3)]
        if stray:
            ids = {id(r) for r in stray}
            brows = [r for r in brows if id(r) not in ids]
            margin += [s for s in body if s['size'] < 10 and (s['bbox'][0] > right + 3 or s['bbox'][2] < left - 3)
                       and TOP <= s['bbox'][1] <= FOOT]
        out.append((brows, _rows(margin, pn), right - 144.7, left))
    return out


def section_key(prefix: str, num: str, suffix: str) -> str:
    return f'{prefix}-{int(num):03d}' + (f'-{suffix.lower()}' if suffix else '')


def units(pdf: bytes, *, prefix: str = 's', label: str = 's', preamble: str | None = None):
    """Provisions in printed order: {key: {label, kind, paras, heading, notes, start}}, and the front notes."""
    pg = pages(pdf)
    out: dict[str, dict] = {}
    starts: list[tuple[int, float, str]] = []
    cur = None
    para = None
    last = None
    lastnum = (0, '')
    in_sched = False
    nsched = 0
    arrangement: dict[str, list[str]] = {}
    arr_cur, arr_x = None, 0.0

    def new_unit(key, lab, kind, row, first_text, heading=None):
        nonlocal cur, para, last
        if cur is not None:
            strip_headings(cur)
        if key in out:
            raise SystemExit(f'unit {key} twice (page {row.page + 1})')
        cur = out[key] = {'label': lab, 'kind': kind, 'paras': [], 'heading': heading, 'notes': [],
                          'start': (row.page, row.y)}
        starts.append((row.page, row.y, key))
        para = None
        if first_text:
            para = {'lines': [first_text], 'heading': False}
            cur['paras'].append(para)
        last = row

    for brows, _m, centre, left in pg:
        for i, r in enumerate(brows):
            t = r.text
            off = abs((r.x0 + r.x1) / 2 - centre)
            centred = off < 16 and r.x0 > left + 15 and r.x1 - r.x0 < 240 or off < 6 and r.bold and t.upper() == t
            if cur is None:
                if preamble and r.size >= 11 and re.match(preamble, t):
                    new_unit('preamble', 'Preamble', 'preamble', r, t)
                    continue
                m = SECTION.match(t)
                if r.bold and r.size >= 10.5 and m and m.group(1) == '1' and not m.group(2) and NUMBER_SPAN.match(r.first):
                    lastnum = (1, '')
                    new_unit(section_key(prefix, '1', ''), f'{label} 1', 'section', r, m.group(3))
                    continue
                # The arrangement of sections (9 pt): "290. Definition of murder.", run-on lines indented.
                ma = re.match(r'^(\d+[A-Z]{0,2})\.\s*(.*)$', t)
                if r.size < 10.5 and ma and not centred:
                    arr_cur = arrangement.setdefault(ma.group(1), [])
                    arr_cur[:] = [ma.group(2)] if ma.group(2) else []
                    arr_x = r.x0
                elif r.size < 10.5 and arr_cur is not None and not centred and r.x0 > arr_x + 3:
                    arr_cur.append(t)
                else:
                    arr_cur = None
                continue
            ms = SCHEDULE.match(t)
            if ms and r.bold and centred and r.size >= 10:
                nsched += 1
                n = ORD_N.get(ms.group(1), nsched) if ms.group(1) else nsched
                in_sched = True
                name = (ms.group(1).title() + ' ' if ms.group(1) else '') + 'Schedule'
                new_unit(f'schedule-{n}', name, 'schedule', r, None)
                cur['paras'].append({'lines': ['# ' + name + (' - ' + ms.group(2) if ms.group(2) else '')],
                                     'heading': False})
                para = None
                continue
            m = SECTION.match(t)
            if (not in_sched and m and r.bold and r.size >= 10.5 and NUMBER_SPAN.match(r.first)
                    and (int(m.group(1)), m.group(2)) > lastnum):
                lastnum = (int(m.group(1)), m.group(2))
                new_unit(section_key(prefix, m.group(1), m.group(2)), f'{label} {m.group(1)}{m.group(2)}',
                         'section', r, m.group(3))
                continue
            is_head = centred and (r.bold or r.italic or t.upper() == t)
            if para is None or last is None or is_head != para['heading']:
                newp = True
            elif r.page == last.page:
                newp = (r.y - last.y > 1.15 * max(r.size, last.size)
                        or t.startswith('Provided') and last.text.endswith(':')
                        or bool(ENUM_START.match(t)) and r.x0 > left + 10
                        and (r.x0 < last.x0 - 5 or bool(re.search(r'(?:[;:.]| -)$', last.text))))
            else:
                newp = bool(ENUM_START.match(t))
            if newp:
                para = {'lines': [t], 'heading': is_head}
                cur['paras'].append(para)
            else:
                para['lines'].append(t)
                para['heading'] = para['heading'] and is_head
            last = r
    if cur is not None:
        strip_headings(cur)

    # The act's list of amending laws: one column of bare references ("28 of 2008") on the title page, which may run
    # on beside the first sections. It is the act's front matter, not a note on any provision.
    front: list[str] = []
    listed = set()
    first_page = starts[0][0] if starts else len(pg)
    allm = [r for _b, mrows, _c, _l in pg for r in mrows]
    i = next((i for i, r in enumerate(allm) if r.page <= first_page and BARE.match(r.text)), None)
    while i is not None and i < len(allm) and BARE.match(allm[i].text):
        front.append(allm[i].text)
        listed.add(id(allm[i]))
        nxt = allm[i + 1] if i + 1 < len(allm) else None
        if nxt is None or not (nxt.page == allm[i].page and nxt.y - allm[i].y <= 12
                               or nxt.page == allm[i].page + 1 and nxt.y < 100):
            break
        i += 1
    # Marginal notes: each belongs to the provision printed beside it: the one begun above it, unless the next one
    # begins a few points below the note and nearer to it than the one above.
    for brows, mrows, centre, left in pg:
        for r in mrows:
            if id(r) in listed:
                continue
            i = -1
            for j, (p, y, k) in enumerate(starts):
                if (p, y) <= (r.page, r.y):
                    i = j
                else:
                    break
            if i + 1 < len(starts) and starts[i + 1][0] == r.page:
                below = starts[i + 1][1] - r.y
                above = r.y - starts[i][1] if i >= 0 and starts[i][0] == r.page else 1e9
                if below <= 11 and below < above:
                    i += 1
            if i >= 0:
                out[starts[i][2]]['notes'].append(r.text)
    # Headings: the act's own arrangement of sections (front matter), e.g. "290. Definition of murder."
    for key, u in out.items():
        if u['kind'] == 'section':
            u['heading'] = arrangement.get(u['label'].split()[-1])
    return out, front


def strip_headings(u):
    """Part/Book/Title headings printed after a provision belong to the next one: drop them."""
    while u['paras'] and u['paras'][-1]['heading']:
        u['paras'].pop()


WORD = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")


def vocabulary(all_lines: list[list[str]]):
    """Words as printed inside lines (never across a line end): the evidence for undoing hyphenation."""
    joined, hyph = set(), set()
    for lines in all_lines:
        for ln in lines:
            toks = WORD.findall(ln)
            if ln.rstrip().endswith('-'):
                toks = toks[:-1]
            if toks and lines.index(ln) > 0:
                toks = toks[1:]
            for w in toks:
                lw = w.lower()
                if '-' in lw:
                    hyph.add(lw)
                else:
                    joined.add(lw)
    return joined, hyph


def join_lines(lines: list[str], vocab) -> str:
    joined, hyph = vocab
    out = lines[0]
    for ln in lines[1:]:
        m = re.search(r'((?:[A-Za-z]+-)*)([A-Za-z]+)-$', out)
        n = re.match(r'([A-Za-z]+)', ln)
        if m and n and not out.endswith(' -'):
            a, b = m.group(2), n.group(1)
            if (a + b).lower() in joined:
                out = out[:-1] + ln
            elif (m.group(1) + a + '-' + b).lower() in hyph or b[0].isupper() or a[0].isupper():
                out = out + ln
            else:
                out = out[:-1] + ln
        else:
            out = out + ' ' + ln
    return re.sub(r'\s+', ' ', out).strip()


LAWREF = [
    (re.compile(r'\b(\d{1,3})\s+o[fr]\s+(1[6-9]\d\d|20\d\d)\b'), 'act'),  # the 2010 Penal Code prints "29 or 1953"
    (re.compile(r'\bS\.\s*I\.\s*(?:No\.\s*)?(\d{1,4})\s*/\s*(\d{4})'), 'si'),
    (re.compile(r'\bS\.\s*I\.\s*(\d{4})\s*No\.\s*(\d{1,4})'), 'si-ynum'),
    (re.compile(r'\bG\.\s*N\.\s*(\d{1,4})\s*/\s*(\d{4})'), 'gn'),
]


def lawrefs(notes: list[str]) -> list[tuple[str, str, str]]:
    """(kind, year, number) for every law a list of marginal notes names, in order, without repeats."""
    out = []
    for n in notes:
        for rx, kind in LAWREF:
            for m in rx.finditer(n):
                if kind == 'si-ynum':
                    k = ('si', m.group(1), str(int(m.group(2))))
                else:
                    k = (kind, m.group(2), str(int(m.group(1))))
                if k not in out:
                    out.append(k)
    return out
