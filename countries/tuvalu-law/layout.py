"""Read a Tuvalu Revised Edition PDF (tuvalu-legislation.tv) into units.

The Revised Edition PDFs share one typesetting: running header (y < 58) and
footer (y > 668), a 16 pt bold title on the first body page, section headings
in bold sans 11 pt with the number at x ~ 77 and the heading at x ~ 105, Part
headings in bold sans 14 pt (title on the next line in 12 pt), Division
headings in sans 11 pt centred, schedules headed by a bold "SCHEDULE n", and
endnotes after a bold "ENDNOTES" heading. Footnote references are 7 pt
numerals; they are dropped from the text and kept per unit, so parse.py can
credit units from the publisher's own endnotes ("Amended by Act 4 of 2009").

Every PDF has a text layer; nothing here is OCR.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import fitz

TOP, BOTTOM = 58.0, 668.0
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman(s: str) -> int | None:
    s = s.upper()
    if not s or any(ch not in ROMAN for ch in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = ROMAN[ch]
        total += -v if i + 1 < len(s) and ROMAN[s[i + 1]] > v else v
    return total


def num(s: str) -> int | None:
    return int(s) if s.isdigit() else roman(s)


def tidy(t: str) -> str:
    t = unicodedata.normalize('NFC', t)
    t = (t.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace(' ', ' ')
          .replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
          .replace('–', '-').replace('‑', '-').replace('­', '').replace('\t', ' '))
    t = re.sub(r'[-]', '', t)  # private-use glyphs (symbol fonts)
    return re.sub(r' {2,}', ' ', t).strip()


@dataclass
class Line:
    page: int
    y: float
    x: float
    text: str
    bold: bool
    size: float
    fns: list[int]
    lead_bold: str = ''      # text of the first span when bold
    rest_bold: bool = False  # every span after the first is bold too


def page_lines(page: fitz.Page, pno: int) -> list[Line]:
    spans = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                if not s['text'].strip() or s['font'] == 'Tuvalu':
                    continue
                y0, y1 = s['bbox'][1], s['bbox'][3]
                if y1 < TOP or y0 > BOTTOM:
                    continue
                spans.append(s)
    big = sorted((s for s in spans if s['size'] > 8.5), key=lambda s: (s['bbox'][1], s['bbox'][0]))
    small = [s for s in spans if s['size'] <= 8.5]
    rows: list[list[dict]] = []
    for s in big:
        if rows and abs(s['bbox'][1] - rows[-1][0]['bbox'][1]) < 3.0:
            rows[-1].append(s)
        else:
            rows.append([s])
    for s in small:  # attach footnote numerals to the row they overlap
        mid = (s['bbox'][1] + s['bbox'][3]) / 2
        best = min(rows, key=lambda r: abs(mid - (r[0]['bbox'][1] + r[0]['bbox'][3]) / 2), default=None)
        if best is not None:
            best.append(s)
    out = []
    for r in rows:
        r.sort(key=lambda s: s['bbox'][0])
        text, fns, last_x1 = '', [], None
        main = [s for s in r if s['size'] > 8.5]
        for s in r:
            if s['size'] <= 8.5:
                d = re.sub(r'\D', '', s['text'])
                if d:
                    fns.append(int(d))
                continue
            gap = (s['bbox'][0] - last_x1) if last_x1 is not None else 0
            if text and not text.endswith(' ') and not s['text'].startswith(' ') and gap > 1.5:
                text += ' '
            text += s['text']
            last_x1 = s['bbox'][2]
        bold = all(s['flags'] & 16 for s in main)
        first = main[0]
        out.append(Line(pno, round(first['bbox'][1], 1), round(first['bbox'][0], 1), tidy(text), bold,
                        round(max(s['size'] for s in main), 1), fns,
                        lead_bold=tidy(first['text']) if first['flags'] & 16 else '',
                        rest_bold=all(s['flags'] & 16 for s in main[1:]) and len(main) > 1))
    return [l for l in out if l.text]


@dataclass
class Unit:
    key: str
    label: str
    kind: str
    heading: str | None = None
    paras: list[str] = field(default_factory=list)
    fns: list[int] = field(default_factory=list)


@dataclass
class Doc:
    title: str
    commencement: str | None
    units: list[Unit]
    endnotes: dict[int, str]
    pages: int


SEC = re.compile(r'^(\d+)([A-Z]{0,3})$')
SEC1 = re.compile(r'^(\d+)([A-Z]{0,3})\s+([A-Z"].*)$')
MARK = re.compile(r'^(\(\s*[0-9a-zA-Z]{1,6}\s*\)|\d+[A-Z]?\.)(\s|$)')
STUB = re.compile(r'^(\d+)([A-Z]{0,3})\s*(?:-\s*)?\[?\s*((?:Repealed|repealed|Revoked|revoked|Omitted|omitted|Spent|spent)\b.*)$')


def sec_key(n: str, suffix: str) -> str:
    return f's-{int(n):03d}' + (f'-{suffix.lower()}' if suffix else '')


def read(path: str) -> Doc:
    d = fitz.open(path)
    lines: list[Line] = []
    start = end = None
    title = ''
    toc_last = -1
    for pno in range(min(d.page_count, 40)):
        if 'Arrangement of Sections' in d[pno].get_text():
            toc_last = pno
    for pno in range(toc_last + 1, d.page_count):
        pl = page_lines(d[pno], pno)
        if start is None:
            t = [l for l in pl if l.size >= 15 and l.bold]
            if not t:
                continue
            start = pno
            title = ' '.join(l.text for l in t)
        for l in pl:
            if l.bold and l.text.upper() == 'ENDNOTES' and l.size >= 11.5:
                end = (pno, l.y)
                break
            lines.append(l)
        if end:
            # the rest of this page and later pages are endnotes
            break
    endnote_lines: list[Line] = []
    if end:
        pno0, y0 = end
        for pno in range(pno0, d.page_count):
            for l in page_lines(d[pno], pno):
                if pno == pno0 and l.y <= y0:
                    continue
                endnote_lines.append(l)
    endnotes: dict[int, str] = {}
    cur = None
    for l in endnote_lines:
        m = re.match(r'^(\d+)\s+(.*)$', l.text)
        if l.fns and l.x < 100 and (cur is None or l.fns[0] == cur + 1):
            cur = l.fns[0]
            endnotes[cur] = l.text
        elif m and l.x < 90 and (cur is None or int(m.group(1)) == cur + 1):
            cur = int(m.group(1))
            endnotes[cur] = m.group(2)
        elif re.match(r'^\d+$', l.text) and l.x < 90 and (cur is None or int(l.text) == cur + 1):
            cur = int(l.text)
            endnotes[cur] = ''
        elif cur is not None:
            endnotes[cur] = (endnotes[cur] + '\n' + l.text).strip()

    units: list[Unit] = []
    commencement = None
    pending_heads: list[str] = []
    part_no: int | None = None
    cur_u: Unit | None = None
    in_sched = False
    prev: Line | None = None
    para_open = False
    title_cont = False

    def new_unit(u: Unit):
        nonlocal cur_u, para_open, title_cont
        units.append(u)
        cur_u = u
        para_open = False
        title_cont = False

    def add_text(l: Line, force_new: bool):
        nonlocal para_open
        assert cur_u is not None
        cur_u.fns.extend(l.fns)
        if para_open and not force_new and cur_u.paras:
            p = cur_u.paras[-1]
            if re.search(r'[A-Za-z]-$', p) and not p.endswith(' -'):
                cur_u.paras[-1] = p + l.text
            else:
                cur_u.paras[-1] = p + ' ' + l.text
        else:
            cur_u.paras.append(l.text)
        para_open = True

    for i, l in enumerate(lines):
        if l.size >= 15 and l.bold and l.page == start:
            prev = l
            continue
        if l.text.startswith('Commencement [') or (prev and prev.text.startswith('Commencement [') and l.text.startswith('[')):
            m = re.search(r'\[\s*(.*?)\s*\]?$', l.text)
            commencement = m.group(1).rstrip('] ').strip() if m else l.text
            prev = l
            continue
        # schedules
        m_sch = re.match(r'^(?:SCHEDULE|Schedule)\s*(\d+|[IVX]+)?\s*$', l.text) if l.bold else None
        if m_sch and l.x > 120:
            n = num(m_sch.group(1)) if m_sch.group(1) else 1
            in_sched = True
            new_unit(Unit(f'sch-{n:02d}', f'Schedule {n}' if m_sch.group(1) else 'Schedule', 'schedule',
                          paras=[l.text], fns=list(l.fns)))
            prev = l
            continue
        if not in_sched:
            # Part heading
            m_part = re.match(r'^PART\s+([IVXLC]+|\d+)\b\s*(?:[-:]\s*)?(.*)$', l.text)
            if m_part and l.bold and l.size >= 12.5:
                part_no = num(m_part.group(1))
                new_unit(Unit(f'part-{part_no:02d}', f'Part {m_part.group(1)}', 'heading', paras=[l.text], fns=list(l.fns)))
                prev = l
                continue
            m_div = re.match(r'^DIVISION\s+([IVXLC]+|\d+)\b', l.text)
            if m_div and not l.bold and l.x > 120 and part_no is not None and l.text == l.text.upper():
                dn = num(m_div.group(1))
                new_unit(Unit(f'part-{part_no:02d}-div-{dn:02d}', f'Part {part_no}, Division {m_div.group(1)}', 'heading',
                              paras=[l.text], fns=list(l.fns)))
                prev = l
                continue
            # section heading: bold number at the margin, bold heading after it
            m_sec = SEC.match(l.lead_bold) if l.lead_bold and l.x < 92 else None
            one = None
            if not m_sec and l.lead_bold and l.x < 92 and l.text == l.lead_bold:
                one = SEC1.match(l.lead_bold)  # number and heading in one bold span
                m_sec = one
            if m_sec and l.size < 12.5 and (one or l.rest_bold or l.text == l.lead_bold):
                key = sec_key(m_sec.group(1), m_sec.group(2))
                head = (one.group(3) if one else l.text[len(l.lead_bold):]).strip()
                new_unit(Unit(key, f's. {m_sec.group(1)}{m_sec.group(2)}', 'section', heading=head, fns=list(l.fns)))
                title_cont = True
                prev = l
                continue
            m_stub = STUB.match(l.text) if l.x < 92 else None
            if m_stub:
                key = sec_key(m_stub.group(1), m_stub.group(2))
                new_unit(Unit(key, f's. {m_stub.group(1)}{m_stub.group(2)}', 'section', paras=[l.text], fns=list(l.fns)))
                prev = l
                continue
            if (title_cont and cur_u is not None and l.bold and l.x >= 95 and l.size < 12.5 and prev
                    and not MARK.match(l.text) and (l.page != prev.page or l.y - prev.y < 20)):
                cur_u.heading = (cur_u.heading + ' ' + l.text).strip()
                cur_u.fns.extend(l.fns)
                prev = l
                continue
            title_cont = False
            if cur_u is not None and cur_u.kind == 'heading' and not l.bold and l.size >= 11.5 and l.x > 120 and not para_open_body(cur_u):
                cur_u.paras.append(l.text)  # Part title line (12 pt caps)
                cur_u.fns.extend(l.fns)
                prev = l
                continue
        if cur_u is None or (cur_u.kind == 'heading' and not in_sched):
            if cur_u is None:
                new_unit(Unit('preamble', 'Preamble', 'preamble'))
            else:
                # body text right after a heading with no section: keep it in the heading unit
                pass
        add_text(l, starts_paragraph(prev, l, cur_u.paras[-1] if cur_u and cur_u.paras and para_open else ''))
        prev = l
    return Doc(title=title, commencement=commencement, units=units, endnotes=endnotes, pages=d.page_count)


def starts_paragraph(prev: Line | None, l: Line, last_para: str) -> bool:
    """Whether line l starts a new paragraph (else it continues last_para).

    A numbered or lettered marker always starts one. On the same page a gap
    wider than the body leading (about 12.5 pt) does. Across a page break the
    text runs on unless the paragraph before ended a sentence and the new line
    starts like a sentence, since page tops lose the vertical gap.
    """
    if prev is None or not last_para:
        return True
    if l.bold and not prev.bold:
        return True
    if MARK.match(l.text):
        return True
    if l.page == prev.page and l.x < prev.x - 10:  # outdented tail ("is guilty of ...") after a list item
        return True
    if prev.page == l.page:
        return l.y - prev.y > 15.5
    return bool(re.search(r'[.:;—]["\']?$', last_para)) and bool(re.match(r'["(A-Z]', l.text))


def para_open_body(u: Unit) -> bool:
    return len(u.paras) >= 3


def unit_text(u: Unit) -> str:
    head = f'# {u.label}' + (f' {u.heading}' if u.heading else '')
    body = [p for p in u.paras if p]
    if u.kind in ('heading', 'schedule', 'preamble'):
        return '\n'.join(body) + '\n' if body else head + '\n'
    return '\n'.join([head] + body) + '\n'
