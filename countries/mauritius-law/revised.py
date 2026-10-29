"""Reads the Attorney General's Office "Revised Laws of Mauritius" PDFs (and Acts as passed) into provisions.

Text comes from the PDF text layer through PyMuPDF (no OCR). Every line keeps its position, so paragraphs are
rebuilt from layout: a vertical gap, a first-line indent or a hanging enumerator starts a new paragraph.
Running heads ("Revised Laws of Mauritius", "[Issue N]", "CON – 8"), and the publisher's bracketed amendment
notes ("[S. 7 amended by Act 48 of 1991.]") are kept out of the text; the notes are returned separately.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

ENUM = re.compile(r'^\((?:[a-z]{1,3}|[ivxl]+|\d+[A-Z]{0,2}|[A-Z]{1,2})\)$')
SECTION = re.compile(r'^(\d+[A-Z]{0,3})\.\s+(.*)$')
SECTION_RANGE = re.compile(r'^(\d+[A-Z]{0,3})\.?\s*[–—-]\s*(\d+[A-Z]{0,3})\.\s*(.*)$')


def norm(s: str) -> str:
    s = s.replace(' ', ' ').replace('​', '').replace('�', '')
    s = re.sub('[“”„]', '"', s)
    s = re.sub('[‘’]', "'", s)
    s = re.sub('[–—]', '—', s)
    s = s.replace('--', '—')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def lines_of(pdf: Path, head_top: float = 70.0) -> list[dict]:
    """Every text line of the PDF: {page, x, y, text, bold, enum_gap, x_text}. Running heads are dropped."""
    doc = fitz.open(pdf)
    out = []
    for pno, page in enumerate(doc):
        h = page.rect.height
        rows: dict[int, list] = {}
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                for s in ln['spans']:
                    if not s['text'].strip():
                        continue
                    y = round(s['bbox'][3])
                    key = next((k for k in rows if abs(k - y) <= 2), y)
                    rows.setdefault(key, []).append(s)
        for y in sorted(rows):
            spans = sorted(rows[y], key=lambda s: s['bbox'][0])
            text = ''
            prev_end = None
            for s in spans:
                if prev_end is not None and s['bbox'][0] - prev_end > 1.5 and not text.endswith(' '):
                    text += ' '
                text += s['text']
                prev_end = s['bbox'][2]
            t = norm(text)
            if not t:
                continue
            top = spans[0]['bbox'][1]
            if top < head_top:
                continue  # running head: "Revised Laws of Mauritius", the act's title
            # Page numbers, including inserted pages ("CON — 66 (2)") and their "continued on page CON — 67" pointer.
            if re.fullmatch(r'(\[Issue \d+\]\s*)?[A-Z]{1,4}\d*\s*—\s*\d+[A-Z]?(\s*\(\d+\))?(\s*\[Issue \d+\])?', t) \
                    or re.fullmatch(r'\[Issue \d+\]', t) \
                    or re.fullmatch(r'continued on page [A-Z]{1,4}\d*\s*—\s*\d+[A-Z]?(\s*\(\d+\))?', t):
                continue
            first = spans[0]
            enum_gap = None
            if ENUM.match(norm(first['text'])) and len(spans) > 1:
                enum_gap = spans[1]['bbox'][0] - first['bbox'][2]
            out.append({'page': pno, 'x': first['bbox'][0], 'y': y, 'top': top, 'text': t,
                        'bold': all('Bold' in s['font'] or s['flags'] & 16 for s in spans),
                        'italic': all('Italic' in s['font'] for s in spans),
                        'enum_gap': enum_gap, 'x_text': spans[1]['bbox'][0] if enum_gap and enum_gap > 6 else None,
                        'size': first['size']})
    return out


def paragraphs(lines: list[dict]) -> list[dict]:
    """Join lines into paragraphs. Returns [{text, bold, x, page, lines}]."""
    paras: list[dict] = []
    cur = None
    for ln in lines:
        new = cur is None
        if cur is not None:
            last = cur['_last']
            same_page = ln['page'] == last['page']
            gap = ln['y'] - last['y'] if same_page else None
            in_note = cur['lines'][0].startswith('[') and not cur['lines'][-1].endswith(']')
            if in_note:
                new = False
            elif cur['lines'][0].startswith('[') or ln['text'].startswith('['):
                new = True  # publisher's notes are paragraphs of their own
            elif ln['bold'] != cur['bold']:
                new = True
            elif same_page and gap is not None and (gap > 13.5 or gap < 0):
                new = True
            elif ln['enum_gap'] is not None or ENUM.match(ln['text'].split(' ')[0] or ''):
                new = True
            elif cur['cont_x'] is not None and ln['x'] < cur['cont_x'] - 4:
                new = True  # outdent: text after a hanging list item
            elif cur['cont_x'] is not None and ln['x'] > cur['cont_x'] + 4 and not same_page:
                new = True
            elif cur['cont_x'] is None and len(cur['lines']) == 1 and not same_page and ln['x'] > cur['x0'] + 4:
                new = True
        if new and cur is not None and cur['lines'][0].startswith('[') and not cur['lines'][-1].endswith(']'):
            new = False
        if new:
            if cur is not None:
                paras.append(cur)
            cur = {'lines': [ln['text']], 'bold': ln['bold'], 'x0': ln['x'], 'page': ln['page'],
                   'cont_x': ln['x_text'], '_last': ln, 'italic': ln['italic']}
        else:
            if cur['cont_x'] is None:
                cur['cont_x'] = ln['x']
            cur['lines'].append(ln['text'])
            cur['_last'] = ln
    if cur is not None:
        paras.append(cur)
    return paras


class Dehyphen:
    """Joins words split at line ends, using the document's own vocabulary to tell soft from hard hyphens."""

    def __init__(self, paras: list[dict]):
        words = Counter()
        for p in paras:
            for ln in p['lines']:
                for w in re.findall(r"[A-Za-z][A-Za-z'-]*[A-Za-z]", ln):
                    words[w.lower()] += 1
        self.words = words

    def join(self, lines: list[str]) -> str:
        out = ''
        for ln in lines:
            if not out:
                out = ln
                continue
            m = re.search(r'([A-Za-z]+)-$', out)
            n = re.match(r'([A-Za-z]+)', ln)
            if m and n:
                a, b = m.group(1), n.group(1)
                joined, hyph = (a + b).lower(), (a + '-' + b).lower()
                if b[0].isupper() and a[0].isupper():
                    out = out + ln          # Vice-President, Anti-Money: keep the hyphen
                elif self.words.get(hyph, 0) > self.words.get(joined, 0):
                    out = out + ln
                else:
                    out = out[:-1] + ln
            elif out.endswith('—') or out.endswith('/'):
                out = out + ln
            else:
                out = out + ' ' + ln
        return re.sub(r'\s+', ' ', out).strip()


NOTE = re.compile(r'^\[(?:S\.|Ss\.|Chapter|CHAPTER|Part|PART|First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|'
                  r'Tenth|Sch|R\.|Rr\.|Para|Paras|Article|Art|Sub-?Part|Heading|Title|Book|Section|Schedule|'
                  r'EDITORIAL|Editorial|Amended|Added|Inserted|Repealed|Former)[^\]]*\]$', re.S)


def key_num(num: str, width: int = 3) -> str:
    m = re.match(r'(\d+)([A-Z]*)', num)
    return m.group(1).zfill(width) + (m.group(2).lower() and '-' + m.group(2).lower() or '')
