"""Reads the text layer of a born-digital Government Gazette Act (no OCR) into sections of paragraphs.

The gazette sets an Act in one column (x about 120 to 470) with line numbers in the margins, running heads, bold
section numbers and headings, italic paragraph letters and hanging indents. read_act() returns, in order, a list of
items: ('chapter', text), ('part', text), ('heading', text) and ('section', number, [paragraph, ...]).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF: reads the publisher's own text layer; nothing is OCR'd

LABEL = re.compile(r'^\((\d+[A-Z]*|[a-z]{1,3}|[ivxl]+|[A-Z])\)(?=\s|$)')
ROMAN = re.compile(r'^\((i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)\)(?=\s|$)')
SECTION = re.compile(r'^(\d+[A-Z]*)\.(\s+|$|(?=[A-Z(‘“]))')


@dataclass
class Line:
    page: int
    x0: float
    x1: float
    y: float
    text: str
    bold: bool          # first span bold
    italic: bool        # first span italic
    size: float
    first: str          # text of the first span


def _norm(s: str) -> str:
    s = (s.replace(' ', ' ').replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff')
         .replace('ﬃ', 'ffi').replace('ﬄ', 'ffl'))
    # typesetting glyphs: a dotless i in "offıcio" (ligature residue), and the line-break hyphens
    s = s.replace('ı', 'i').replace('‐', '-').replace('‑', '-')
    s = re.sub('­\\s*$', '-', s)
    return s


def _span_text(span: dict) -> str:
    """A span's characters, with a space wherever the layer leaves a visible gap but no space character
    ("thisAct", "adata" in the gazette's text layer)."""
    out, prev = [], None
    size = span.get('size') or 10
    for ch in span.get('chars', []):
        c = ch['c']
        if prev is not None and c != ' ' and prev['c'] != ' ' and ch['bbox'][0] - prev['bbox'][2] > 0.08 * size:
            out.append(' ')
        out.append(c)
        prev = ch
    return ''.join(out) if span.get('chars') else span.get('text', '')


def _line_text(spans: list[dict]) -> str:
    out = ''
    last = None
    for s in spans:
        t = s['text']
        if last is not None and out and not out.endswith(' ') and not t.startswith(' ') and s['chars'] \
                and s['chars'][0]['bbox'][0] - last > 0.08 * (s.get('size') or 10):
            out += ' '
        out += t
        if s.get('chars'):
            last = s['chars'][-1]['bbox'][2]
    return out


def lines(pdf: bytes, first_page: int = 0, last_page: int | None = None, body=(112, 475), merge: bool = True) -> list[Line]:
    doc = fitz.open(stream=pdf, filetype='pdf')
    out: list[Line] = []
    for pn in range(first_page, last_page if last_page is not None else len(doc)):
        page = doc[pn]
        for b in page.get_text('rawdict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    s['text'] = _span_text(s)
                spans = [s for s in l['spans'] if s['text'].strip()]
                if not spans:
                    continue
                x0, y0, x1, _ = l['bbox']
                text = _norm(_line_text(l['spans'])).strip()
                if y0 < 70:                       # running heads
                    continue
                if 'gpwonline' in text or 'This gazette is also available' in text:
                    continue
                if re.fullmatch(r'\d{1,3}', text) and (x0 > body[1] - 10 or x0 < body[0]):
                    continue                      # margin line numbers
                if x0 > body[1] - 5:
                    continue
                f = spans[0]
                out.append(Line(pn, x0, x1, y0, text, 'Bold' in f['font'] or f['flags'] & 16 > 0,
                                'Italic' in f['font'] or f['flags'] & 2 > 0, f['size'], _norm(f['text'])))
    out.sort(key=lambda l: (l.page, round(l.y), l.x0))
    # merge pieces of one visual line (an italic label and its text are separate lines in the layer)
    if not merge:
        return out
    merged: list[Line] = []
    for l in out:
        if merged and merged[-1].page == l.page and abs(merged[-1].y - l.y) < 2 and l.x0 >= merged[-1].x1 - 1:
            m = merged[-1]
            m.text = m.text + ' ' + l.text
            m.x1 = l.x1
        else:
            merged.append(l)
    return merged


def join(parts: list[str]) -> str:
    s = ''
    for p in parts:
        if not s:
            s = p
        elif s.endswith('-') and not s.endswith(' -') and re.match(r'[a-z]', p) and not s.endswith('—'):
            # a hyphen at the end of a line: the typesetter's break, unless the word is a real compound
            s = s[:-1] + p if not re.search(r'\b(non|co|self|well|re|de|sub|pre|cross|e|semi|anti)-$', s) else s + p
        else:
            s = s + ' ' + p
    return re.sub(r'\s+', ' ', s).strip()


@dataclass
class Para:
    lines: list[str] = field(default_factory=list)
    x0: float = 0
    cont: float | None = None   # x of continuation lines


def paragraphs(ls: list[Line], right: float = 440) -> list[tuple[str, Line]]:
    """Groups lines into paragraphs. Returns (text, first line)."""
    paras: list[tuple[list[str], Line, Para]] = []
    prev: Line | None = None
    for l in ls:
        new = False
        t = l.text
        cur = paras[-1][2] if paras else None
        if prev is None:
            new = True
        elif cur is not None and cur.cont is not None and l.x0 < cur.cont - 10 and l.page == prev.page:
            new = True   # back out to an outer level after a hanging-indent item
        elif l.bold and (SECTION.match(t) or not prev.bold) and not (t[:1].islower() and not prev.text.rstrip().endswith((".", ":", ";"))):
            new = True
        elif l.bold and prev.bold and (prev.x1 < right - 40 or abs(l.x0 - prev.x0) > 15):
            new = True
        elif l.bold and prev.text.rstrip().endswith(('.', ':', '—', ';')) and not t[:1].islower():
            new = True
        elif l.italic and LABEL.match(l.first.strip() or t):
            new = True
        elif LABEL.match(t):
            p = paras[-1][2]
            if p.cont is not None and abs(l.x0 - p.cont) < 0.8 and prev.x1 > right - 25:
                new = False   # a continuation line that happens to start with a bracketed reference
            else:
                new = True
        elif t.startswith('‘‘') and l.bold:
            new = True
        elif prev.x1 < right - 60 and prev.text.rstrip().endswith((';', '.', ':', '—', 'and', 'or', '.’’', '’’;')):
            new = True
        if new:
            paras.append(([t], l, Para([t], l.x0)))
        else:
            paras[-1][0].append(t)
            if paras[-1][2].cont is None:
                paras[-1][2].cont = l.x0
        prev = l
    return [(join(p[0]), p[1]) for p in paras]
