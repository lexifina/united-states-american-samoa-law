"""Helpers shared by gitlaw-scraper-dell's own province adapters (cordoba, santa_fe, tucuman, entre_rios, salta,
misiones). Not the engine: ar_provinces.py is unchanged; these only wrap two of its functions inside the process that
imports the adapter.

- patch_in_force(rules): a constitution's vigencia clause the engine's reader misses (a date in words, or a clause
  outside the last 25 paragraphs) is given as (publication date, exact phrase in the text, in-force day, basis).
  Applied only when both the publication date and the phrase match.
- pdf_paragraphs_layout(b): a text-layer PDF -> paragraphs, using the line geometry (a line that stops short of the
  block's right edge ends a paragraph, and a line starting "Artículo N" / "Art. N" starts one), joining a word broken by a soft hyphen at a line end, and keeping a page number
  printed above a block as its own paragraph. Nothing is dropped; letters equal PyMuPDF's.
"""
from __future__ import annotations

import re
import sys

import ar_provinces as E


def _mods():
    return {id(m): m for m in (sys.modules.get('__main__'), E) if m is not None}.values()


def patch_in_force(rules):
    for mod in _mods():
        orig = getattr(mod, 'in_force', None)
        if orig is None:
            continue
        prev = getattr(orig, '_dell_rules', None)
        if prev is not None:
            prev.extend(r for r in rules if r not in prev)
            continue
        table = list(rules)

        def wrapped(paras, pub, promul, _o=orig, _t=table):
            for opub, phrase, day, basis in _t:
                if pub == opub and any(phrase in p for p in paras):
                    return day, basis
            return _o(paras, pub, promul)
        wrapped._dell_rules = table
        mod.in_force = wrapped


SHY = chr(0xad)
HEAD = re.compile(r'\s*(?:ART[IÍ]CULO|Art[ií]culo|ART\.|Art\.)\s*N?[°º]?\s*\d')  # capitalised only


def pdf_paragraphs_layout(b: bytes, margin: float = 12.0, sort: bool = False) -> list[str]:
    import pymupdf
    out: list[str] = []
    with pymupdf.open(stream=b, filetype='pdf') as doc:
        for page in doc:
            for blk in page.get_text('dict', sort=sort)['blocks']:
                if blk.get('type') != 0:
                    continue
                lines = [(''.join(s['text'] for s in ln['spans']), ln['bbox'][2]) for ln in blk['lines']]
                lines = [(t, x) for t, x in lines if t.strip()]
                if not lines:
                    continue
                right = max(x for _, x in lines)
                if len(lines) > 1 and re.fullmatch(r'\s*\d{1,4}\s*', lines[0][0]):
                    out.append(lines[0][0].strip())
                    lines = lines[1:]
                cur = ''
                for i, (t, x) in enumerate(lines):
                    if cur and HEAD.match(t) and not cur.rstrip().endswith(SHY):
                        c = E.clean(cur)
                        if c:
                            out.append(c)
                        cur = ''
                    if not cur:
                        cur = t
                    elif cur.rstrip().endswith('\xad'):
                        cur = cur.rstrip()[:-1] + t.lstrip()
                    elif re.search(r'\w-\s*$', cur):
                        cur = cur.rstrip() + t.lstrip()
                    else:
                        cur = cur.rstrip() + ' ' + t.lstrip()
                    last = i == len(lines) - 1
                    if last or (x < right - margin and not cur.rstrip().endswith('\xad')):
                        c = E.clean(cur)
                        if c:
                            out.append(c)
                        cur = ''
    return out


def source_letters_pdf_raw(b: bytes) -> str:
    """Independent reader for PDFs whose layout order differs from poppler's default: poppler's pdftotext -raw
    (content-stream order, the order PyMuPDF reads blocks in with sort=False)."""
    import subprocess
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'x.pdf'
        f.write_bytes(b)
        out = subprocess.run(['pdftotext', '-raw', '-enc', 'UTF-8', str(f), '-'], capture_output=True)
        return E.letters(out.stdout.decode('utf-8', 'replace'))


def patch_article_dot():
    """Read "Artículo. 50.-" (a stray full stop after the word, as some sources print it) as the heading of article 50;
    the text is unchanged, only the unit it is filed under."""
    for mod in _mods():
        orig = getattr(mod, 'article_id', None)
        if orig is None or getattr(orig, '_dell_dot', False):
            continue

        def wrapped(line, _o=orig):
            r = _o(line)
            if r is None:
                m = re.match(r'(\s*Art[ií]culo)\.(\s*\d)', line)
                if m:
                    return _o(m.group(1) + m.group(2) + line[m.end():])
            return r
        wrapped._dell_dot = True
        mod.article_id = wrapped
