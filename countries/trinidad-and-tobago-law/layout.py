"""PDF layout reader for the Laws of Trinidad and Tobago (revised-edition PDFs of the Ministry of the Attorney General
and Legal Affairs). Reads cached bytes only.

Turns pages into paragraphs (one per printed paragraph, subsection or item), each with the marginal notes printed
beside it. Running heads and feet ("LAWS OF TRINIDAD AND TOBAGO", the Ministry line, "UNOFFICIAL VERSION",
"UPDATED TO ...", "L.R.O.") are dropped. Publisher typesetting is normalised once here.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

import fitz  # PyMuPDF

QMAP = {' ': ' ', '–': '-', '—': '-', '‒': '-', '…': '...', '“': '"', '”': '"',
        '’': "'", '‘': "'", '­': '', '\t': ' ', '•': '-', 'ﬁ': 'fi', 'ﬂ': 'fl',
        '‐': '-', '‑': '-'}

HEAD_Y = 135.0   # running head ends above this (body starts at about 142)
FOOT_Y = 680.0
COLUMN = 312.0  # width of the text column   # running foot ("L.R.O.", "UNOFFICIAL VERSION", "UPDATED TO ...") starts below this


def norm(s: str) -> str:
    for a, b in QMAP.items():
        s = s.replace(a, b)
    return re.sub(r'\s+', ' ', s)


@dataclass
class Row:
    page: int
    y: float
    vx: float        # visible left edge (first non-space glyph)
    x1: float
    size: float
    bold: bool
    text: str
    first_bold: str  # text of the leading bold run (a section number), if any


@dataclass
class Para:
    page: int
    y: float
    text: str
    size: float
    heading: bool = False
    centred: bool = False
    bold_lead: str = ''
    margin: list = field(default_factory=list)


def _spans(page):
    out = []
    for bl in page.get_text('rawdict')['blocks']:
        for ln in bl.get('lines', []):
            for s in ln['spans']:
                chars = [c for c in s['chars'] if c['c'].strip()]
                if not chars:
                    continue
                txt = ''.join(c['c'] for c in s['chars'])
                x0 = chars[0]['bbox'][0]
                x1 = chars[-1]['bbox'][2]
                y0, y1 = s['bbox'][1], s['bbox'][3]
                out.append({'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'size': s['size'],
                            'bold': bool(s['flags'] & 16) or 'Bold' in s['font'], 'text': txt,
                            'font': s['font']})
    return out


def _rows(spans, tol=3.0):
    """Group spans into printed lines by baseline; smaller superscripts join the line they overlap."""
    big = sorted([s for s in spans if s['size'] >= 9.5], key=lambda s: (s['y1'], s['x0']))
    small = [s for s in spans if s['size'] < 9.5]
    rows = []
    for s in big:
        for r in rows:
            if abs(r[0]['y1'] - s['y1']) <= tol:
                r.append(s)
                break
        else:
            rows.append([s])
    rest = []
    for s in small:
        mid = (s['y0'] + s['y1']) / 2
        for r in rows:
            if min(x['y0'] for x in r) - 1 <= mid <= max(x['y1'] for x in r) + 1:
                r.append(s)
                break
        else:
            rest.append(s)
    for s in sorted(rest, key=lambda s: (s['y1'], s['x0'])):
        for r in rows:
            if r[0]['size'] < 9.5 and abs(r[0]['y1'] - s['y1']) <= tol:
                r.append(s)
                break
        else:
            rows.append([s])
    for r in rows:
        r.sort(key=lambda s: s['x0'])
    rows.sort(key=lambda r: max(s['y1'] for s in r))
    return rows


def _join(row):
    out = ''
    prev = None
    for s in row:
        t = s['text']
        if prev is not None and s['x0'] - prev['x1'] > 1.0 and not out.endswith(' ') and not t.startswith(' '):
            out += ' '
        out += t
        prev = s
    return out


def page_rows(doc, pno):
    """Body rows and margin rows of one page."""
    page = doc[pno]
    sp = [s for s in _spans(page) if HEAD_Y < s['y0'] and s['y1'] < FOOT_Y]
    body_sp = [s for s in sp if s['size'] >= 9.5]
    if not body_sp:
        return [], [], None
    # text column: the commonest visible left edge of body-size spans that begin a printed line
    rows = _rows(body_sp)
    lefts = [round(r[0]['x0']) for r in rows]
    R = sorted(s['x1'] for s in body_sp)[int(0.95 * (len(body_sp) - 1))]
    # the revised edition prints a 312 pt text column (120-432 on even pages, 180-492 on odd pages)
    L = R - COLUMN
    if not any(abs(x - L) <= 4 for x in lefts) and not any(x < L - 4 for x in lefts):
        L = min([x for x in set(lefts) if lefts.count(x) >= 3] or [min(lefts)])
    body, margin = [], []
    for s in sp:
        if s['size'] < 9.5 and (s['x1'] <= L - 3 or s['x0'] >= R + 3):
            margin.append(s)
        else:
            body.append(s)
    out = []
    for r in _rows(body):
        text = norm(_join(r)).strip()
        if not text:
            continue
        lead = ''
        if r[0]['bold']:
            lead = norm(r[0]['text']).strip()
        out.append(Row(pno, max(s['y1'] for s in r), r[0]['x0'], max(s['x1'] for s in r),
                       max(s['size'] for s in r), all(s['bold'] for s in r if s['text'].strip()), text, lead))
    mrows = []
    for r in _rows(margin):
        text = norm(_join(r)).strip()
        if text:
            mrows.append((pno, min(s['y0'] for s in r), text))
    return out, mrows, (L, R)


MARK = re.compile(r'^(\((?:[a-z]{1,2}|[ivxl]+|\d+[A-Z]?)\)|\d+[A-Z]*\.(\s|$)|"|\'|- )')


def paragraphs(doc, pages):
    """Paragraphs over the given page numbers (in order)."""
    paras: list[Para] = []
    prev = None          # previous body row
    prev_geo = None
    cont = None          # continuation offset (from L) of the current paragraph
    first_off = None
    allm = []
    for pno in pages:
        rows, mrows, geo = page_rows(doc, pno)
        allm.extend(mrows)
        if geo is None:
            continue
        L, R = geo
        mid = (L + R) / 2
        for r in rows:
            off = r.vx - L
            centred = abs((r.vx + r.x1) / 2 - mid) < 20 and off > 8
            heading = centred and (r.bold or r.text.isupper())
            if prev is None:
                start = True
            else:
                pL, pR = prev_geo
                prev_short = prev.x1 < pR - 22
                pt = prev.text.rstrip()
                ended = pt[-1:] in '.;:-' or bool(re.search(r'[;,] ?(or|and)$', pt))
                if heading or (paras and paras[-1].heading):
                    start = True
                elif cont is None:
                    # second row of a paragraph: continuation if it is not to the right of the first row's text
                    start = prev_short or (MARK.match(r.text) is not None and ended) or off > first_off + 30
                else:
                    start = prev_short or abs(off - cont) > 3 or (MARK.match(r.text) is not None and ended
                                                                   and off > cont + 3)
                    if not start and MARK.match(r.text) and ended and abs(off - cont) <= 3 and r.text.startswith('"'):
                        start = True
            if start:
                paras.append(Para(pno, r.y, r.text, r.size, heading, centred, r.first_bold))
                cont = None
                first_off = off
            else:
                paras[-1].text = _hyph_join(paras[-1].text, r.text)
                if cont is None:
                    cont = off
            prev, prev_geo = r, geo
    # margin notes: join rows printed close together into one note, then attach each note to the paragraph that
    # starts nearest at or above it on the same page
    notes = []
    for pno, y, text in allm:
        if notes and notes[-1][0] == pno and 0 <= y - notes[-1][3] <= 10.5:
            notes[-1][2] += ' ' + text
            notes[-1][3] = y
        else:
            notes.append([pno, y, text, y])
    for pno, y, text, _ in notes:
        cands = [p for p in paras if p.page == pno and p.y - 14 <= y + 6]
        if cands:
            best = max(cands, key=lambda p: p.y)
            best.margin.append(text)
        else:
            later = [p for p in paras if p.page == pno]
            if later:
                later[0].margin.append(text)
    return paras


def _hyph_join(a: str, b: str) -> str:
    if re.search(r'[A-Za-z]-$', a) and b[:1].islower():
        return a + '' + b   # resolved later against the document's vocabulary
    return a + ' ' + b


def open_pdf(path):
    return fitz.open(path)
