"""Bosnia and Herzegovina entity builders (gitlaw-scraper-dell, 2026-10-30): text-layer PDF -> article units.
Private (never published). Used by scripts/bosnia-{federation,republika-srpska,brcko}-law/parse.py.

Reading: pymupdf spans. Body text is the larger font; footnotes are the smaller one; superscript spans (flag 1) are
note markers and are dropped from the body. Running headers and page numbers are dropped.
Paragraphs: a blank line, an indented first line, or a list marker starts a new paragraph; wrapped lines are joined
with one space.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

import pymupdf

LIST_MARK = re.compile(r'^(\(\d+[a-z]?\)|\d{1,2}[a-z]?\.\s|\d+\)|[a-zа-шђјљњћџ]\)|[-–•]\s)')
ART = re.compile(r'^\s*(Član|Члан|Članak|Чланак)\s+(\d+)\s*([a-zа-ш]?)\s*\.?\s*$')


def clean(s: str) -> str:
    s = unicodedata.normalize('NFC', s.replace(' ', ' ').replace('', '*').replace('­', ''))
    s = s.replace('\t', ' ')
    return re.sub(r' {2,}', ' ', s).strip()


WHERE = {'page': 0, 'y': 0.0}  # page and line top of the line drop_line is asked about


def read(path, body_min=10.6, headers=(), skip_pages=(), drop_sup=True, drop_line=None, split_gaps=False):
    """-> (lines, notes). lines: list of (text, indent, blank_before)."""
    d = pymupdf.open(path)
    out, notes = [], []
    for pno, page in enumerate(d):
        if pno in skip_pages:
            continue
        pl, ys = [], []
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                bt, nt = '', ''
                for s in l['spans']:
                    sup = bool(s['flags'] & 1)
                    if sup and drop_sup:
                        continue
                    if s['size'] >= body_min:
                        bt += s['text']
                    else:
                        nt += s['text']
                pl.append((bt, nt))
                ys.append(l['bbox'][1])
        # drop running headers and page numbers (first and last body lines of the page)
        idx = [i for i, (bt, _) in enumerate(pl) if bt.strip()]
        for i in idx[:3] + idx[-2:]:
            t = clean(pl[i][0])
            if re.fullmatch(r'\d{1,3}', t) or t in headers:
                pl[i] = ('', pl[i][1])
        for li, (bt, nt) in enumerate(pl):
            WHERE['page'], WHERE['y'] = pno, ys[li]
            if nt.strip():
                notes.append(clean(nt))
            raw = bt.replace(' ', ' ').replace('\t', '    ')
            if drop_line and not split_gaps and raw.strip() and drop_line(clean(raw)):
                continue  # a running letterhead or watermark: gone, without breaking the paragraph
            if not raw.strip():
                out.append(None)
                continue
            indent = len(raw) - len(raw.lstrip(' '))
            pieces = re.split(r'(?<=\S) {5,}(?=\S)', raw.strip()) if split_gaps else [raw]
            for n, piece in enumerate(pieces):  # two columns on one line (signature blocks): one line each
                if drop_line and drop_line(clean(piece)):
                    continue  # each column is judged on its own: a letterhead column never takes law text with it
                out.append((clean(piece), indent if n == 0 else 0))
    lines, blank = [], True
    for x in out:
        if x is None:
            blank = True
            continue
        lines.append((x[0], x[1], blank))
        blank = False
    return lines, notes


def paragraphs(lines, is_heading, indent_min=3):
    """Join wrapped lines into paragraphs. is_heading(text) -> True keeps a line on its own."""
    paras: list[str] = []
    cur = None
    for text, indent, blank in lines:
        if is_heading(text):
            if cur is not None:
                paras.append(cur)
            paras.append(text)
            cur = None
            continue
        ends = cur is not None and cur.rstrip().endswith(('.', ':', ';', '!', '?', '“', '"', ')'))
        new = cur is None or blank or (indent >= indent_min and ends) or LIST_MARK.match(text)
        if new:
            if cur is not None:
                paras.append(cur)
            cur = text
        else:
            cur = cur + ' ' + text if not cur.endswith('-') or cur.endswith(' -') else cur + text
    if cur is not None:
        paras.append(cur)
    return [clean(p) for p in paras if clean(p)]


def letters_digits(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s).lower() if ch.isalnum())


def sha256(path) -> str:
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def art_key(n: int, suffix: str = '', prefix: str = '') -> str:
    lat = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e'}
    suffix = lat.get(suffix, suffix)
    return f'{prefix}clan-{n:03d}' + (f'-{suffix}' if suffix else '')


def check_present(units_text: list[str], source_text: str):
    """Every paragraph's letters and digits occur somewhere in the source's own text; and how many of the source's
    letters and digits our text does not account for (residue). -> (missing list, ours, theirs)"""
    src = letters_digits(source_text)
    missing = [p for p in units_text if letters_digits(p) and letters_digits(p) not in src]
    ours = sum(len(letters_digits(p)) for p in units_text)
    return missing, ours, len(src)


def check_in_order(units_text: list[str], source_text: str):
    """Independent check: the letters and digits of every paragraph occur in the source's own text, in order.
    Returns (found, missing list, residue letters count)."""
    src = letters_digits(source_text)
    pos, missing, matched = 0, [], 0
    for para in units_text:
        ld = letters_digits(para)
        if not ld:
            continue
        j = src.find(ld, pos)
        if j < 0:
            missing.append(para)
            continue
        matched += len(ld)
        pos = j + len(ld)
    return len(units_text) - len(missing), missing, len(src) - matched
