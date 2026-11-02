"""PDF paragraphs for the Argentine province adapters (gitlaw-scraper-dell lane 2, 2026-10-30).

The engine's pdf_paragraphs() takes PyMuPDF text blocks in stream order. On pages laid out as tables (an index with page
numbers in a second column) that order differs from poppler's reading order, so the letters check (which compares
letter sequences, not just counts) fails although no letter is lost. pdf_paragraphs_ordered() keeps PyMuPDF's text
(every block, every line) and only puts the lines of such a page in poppler's reading order; consecutive lines of one
PyMuPDF block stay one paragraph. A page it cannot order this way keeps the stream order (and the check then fails, so
the part is not published). Nothing is dropped or added.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from ar_provinces import clean, letters


def _poppler_pages(b: bytes) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'x.pdf'
        f.write_bytes(b)
        out = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(f), '-'], capture_output=True)
        return out.stdout.decode('utf-8', 'replace').split('\f')


def _order_page(lines: list[tuple[int, int, str]], target: str) -> list[tuple[int, int, str]] | None:
    # fold letterless lines into the line before them (same block) so every unit has letters
    units: list[list[tuple[int, int, str]]] = []
    for ln in lines:
        if not letters(ln[2]) and units and units[-1][-1][0] == ln[0]:
            units[-1].append(ln)
        else:
            units.append([ln])
    if units and not letters(''.join(x[2] for x in units[0])) and len(units) > 1:
        units[1] = units[0] + units[1]
        units = units[1:]
    keys = [letters(''.join(x[2] for x in u)) for u in units]
    # depth-first search in stream order first, backtracking when a choice leads nowhere (bounded)
    n = len(units)
    used = [False] * n
    seq: list[int] = []
    budget = [200000]

    def dfs(pos: int) -> bool:
        if len(seq) == n:
            return pos == len(target)
        budget[0] -= 1
        if budget[0] < 0:
            return False
        tried = set()
        for i in range(n):
            if used[i] or keys[i] in tried or not target.startswith(keys[i], pos):
                continue
            tried.add(keys[i])     # identical keys are interchangeable: try the first unused one only
            used[i] = True
            seq.append(i)
            if dfs(pos + len(keys[i])):
                return True
            seq.pop()
            used[i] = False
        return False

    import sys
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 4 * n + 100))
    try:
        ok = dfs(0)
    finally:
        sys.setrecursionlimit(old)
    if not ok:
        return None
    return [ln for i in seq for ln in units[i]]


def pdf_paragraphs_ordered(b: bytes, stream: bool = False) -> list[str]:
    """Paragraphs: a PyMuPDF block is cut at its blank lines and before a line that opens an article ("ARTÍCULO 13:"
    after a marginal heading in the same block); lines of a paragraph are joined with a space."""
    import pymupdf
    from ar_provinces import article_id
    pages = _poppler_pages(b)
    out: list[str] = []
    with pymupdf.open(stream=b, filetype='pdf') as doc:
        for pno, page in enumerate(doc):
            blocks = [blk for blk in page.get_text('blocks', sort=False) if blk[6] == 0]
            lines = [(bi, li, t) for bi, blk in enumerate(blocks) for li, t in enumerate(blk[4].split('\n'))]
            mine = letters(''.join(blk[4] for blk in blocks))
            target = letters(pages[pno]) if pno < len(pages) else ''
            order = lines if stream or mine == target else (_order_page(lines, target) or lines)
            bl = [blk[4].split('\n') for blk in blocks]
            # a line opens an article when it, read with the next two lines of its block, starts "Artículo N"
            # (some PDFs put every word on a line of its own: "Artículo " / "158.­ " / "La ")
            starts = {(bi, li) for bi, li, t in lines
                      if li > 0 and (not bl[bi][li - 1].strip() or article_id(' '.join(bl[bi][li:li + 3])))}
            cur, prev = [], None
            for bi, li, t in order:
                if prev is not None and (not (bi == prev[0] and li == prev[1] + 1) or (bi, li) in starts):
                    c = clean(' '.join(cur))
                    if c:
                        out.append(c)
                    cur = []
                # a marginal heading printed on the article's own line ("RÉGIMEN TRIBUTARIO Artículo 94. ..."): the
                # paragraph is cut before "Artículo" when everything before it on the line is upper case
                m = re.match(r'^(.*?\S)\s+(ART[IÍ]CULO\s+\d.*)$', t, re.I | re.S)
                if m and m.group(1) == m.group(1).upper() and re.search(r'[A-ZÁÉÍÓÚÑ]{3}', m.group(1)) \
                        and not re.search(r'\b(EL|LA|LOS|LAS|DEL|DE|EN|POR|AL|Y|E|O|CON|SEG[UÚ]N|SU|SUS|DICHO|CITADO)$',
                                          m.group(1).upper()) \
                        and article_id(m.group(2) + ' ' + ' '.join(bl[bi][li + 1:li + 3])):
                    cur.append(m.group(1))
                    c = clean(' '.join(cur))
                    if c:
                        out.append(c)
                    cur = [m.group(2)]
                else:
                    cur.append(t)
                prev = (bi, li)
            c = clean(' '.join(cur))
            if c:
                out.append(c)
    return out


def source_letters_pdf_raw(b: bytes) -> str:
    """Independent reader for PDFs whose justified lines poppler's default layout reorders: poppler's pdftotext -raw
    (content-stream order), used with pdf_paragraphs_ordered(b, stream=True)."""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'x.pdf'
        f.write_bytes(b)
        out = subprocess.run(['pdftotext', '-raw', '-enc', 'UTF-8', str(f), '-'], capture_output=True)
        return letters(out.stdout.decode('utf-8', 'replace'))
