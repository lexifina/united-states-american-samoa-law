"""Read a Palau Code Commission PDF (text layer only, no OCR) into ordered lines.

Two layouts occur:
- "modern": the 2026 PDFMaker-for-Word exports on the Code Commission's Google Drive (Constitution current as of
  05/13/2026; PNC titles current as of 09/30/2026). Running heads at y < 45, footers at y > 730, law text 12 pt,
  annotations ("Section Notes", "Sources", "Amended", "Supreme Court Cases", ...) 10 pt.
- "typeset": the archived PNCA supplements (Nitro/CID fonts). Running heads 14 pt bold at y < 90, footers at
  y > 700 ("Supp. N", "17 - 21"), law text 12 pt, annotations about 10 pt, centred.

Each line: dict(page, x, y, size, bold, text, kind) with kind 'body' (law text, >= 11 pt) or 'note' (< 11 pt).
Headers, footers and table-of-contents leader lines are dropped.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF

LEADER = re.compile(r'\.{5,}')
WS = re.compile(r'[ \t      ]+')


def norm(s: str) -> str:
    s = s.replace('­', '').replace('﻿', '').replace('​', '')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '—')  # keep em dash, normalise en dash
    s = s.replace('', '-')
    return WS.sub(' ', s).strip()


def lines(data: bytes, layout: str) -> list[dict]:
    doc = fitz.open(stream=data, filetype='pdf')
    out = []
    # the regular text font: the commonest font among 11-13 pt spans (typeset PDFs use CID fonts with no bold flag)
    from collections import Counter
    fc = Counter()
    for page in doc:
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                for s in ln['spans']:
                    if 11 <= s['size'] <= 13 and s['text'].strip():
                        fc[s['font']] += len(s['text'])
    regular = fc.most_common(1)[0][0] if fc else ''
    for pn, page in enumerate(doc):
        h = page.rect.height
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                spans = [s for s in ln['spans'] if s['text'].strip()]
                if not spans:
                    continue
                y = ln['bbox'][1]
                size = max(s['size'] for s in spans)
                main = max(spans, key=lambda s: len(s['text'].strip()))
                if layout == 'modern':
                    bold = bool(main['flags'] & 16) or 'Bold' in main['font']
                else:
                    bold = 'Bold' in main['font'] or (main['size'] >= 11 and main['font'] != regular
                                                      and 'Italic' not in main['font'])
                text = norm(''.join(s['text'] for s in ln['spans']))
                if not text:
                    continue
                if layout == 'modern':
                    if y < 45 or y > h - 54:
                        continue
                else:
                    if y > h - 92 or (y < 125 and size >= 13.5):
                        continue
                if LEADER.search(text):
                    continue
                out.append({'page': pn, 'x': round(ln['bbox'][0], 1), 'y': round(y, 1), 'y1': round(ln['bbox'][3], 1),
                            'size': round(size, 1), 'bold': bold, 'text': text,
                            'kind': 'body' if size >= 11 else 'note'})
    # PyMuPDF block order is mostly reading order; sort within a page by y then x to be safe
    out.sort(key=lambda l: (l['page'], l['y'], l['x']))
    return out


END = re.compile(r'[.;:!?]["\')\]]*$')


def paragraphs(body: list[dict], gap: float = 15.5) -> list[str]:
    """Join wrapped lines into paragraphs: a new paragraph starts after a vertical gap wider than one line
    (or a page break after a line that ends a sentence)."""
    paras: list[str] = []
    prev = None
    for l in body:
        new = prev is None
        if prev is not None:
            if l['page'] != prev['page']:
                new = bool(END.search(paras[-1])) or l['text'].startswith('(')
            else:
                new = (l['y'] - prev['y']) > gap or l['y'] < prev['y']
        if new:
            paras.append(l['text'])
        else:
            joiner = '' if paras[-1].endswith('-') and not paras[-1].endswith(' -') else ' '
            if joiner == '' and re.search(r'[A-Za-z]-$', paras[-1]) and l['text'][:1].islower():
                paras[-1] = paras[-1] + l['text']
            else:
                paras[-1] = paras[-1] + ' ' + l['text']
        prev = l
    return [WS.sub(' ', p).strip() for p in paras if p.strip()]


ENUM_SPLIT = re.compile(r'(?:(?<=[.;:])|(?<=[.;:]")|(?<=; or)|(?<=; and)|(?<=, or)|(?<=, and)|(?<=\.\]))\s+'
                        r'(?=\((?:[a-z]{1,2}|[ivxl]{1,5}|\d{1,3}|[A-Z]{1,2})\)\s)')


def flow(body: list[dict]) -> list[str]:
    """Layout-independent paragraphs: join every line of a section, then start a new paragraph only where an
    enumerator ("(a)", "(1)", "(A)", "(iv)") follows the end of a clause. Typeset and Word-exported editions space
    their paragraphs differently, so line gaps are not used."""
    s = ''
    for l in body:
        t = l['text']
        if not s:
            s = t
        elif re.search(r'[A-Za-z]-$', s) and t[:1].islower():
            s += t
        else:
            s += ' ' + t
    s = WS.sub(' ', s).strip()
    return [p.strip() for p in ENUM_SPLIT.split(s) if p.strip()] if s else []
