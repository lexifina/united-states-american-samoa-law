"""Text helpers shared by parse.py and impo_history.py: one typesetting for IMPO and the Parlamento, and the
rebuilding of IMPO's hard-wrapped lines into paragraphs."""
from __future__ import annotations

import html
import re

# ---------------------------------------------------------------- text helpers


def norm(s: str) -> str:
    """One typesetting for both publishers (IMPO and Parlamento)."""
    s = html.unescape(s)
    s = s.replace(' ', ' ').replace('\t', ' ')
    s = re.sub('[“”„«»]', '"', s)
    s = re.sub('[‘’´`]', "'", s)
    s = re.sub('[–—]', '-', s)
    s = s.replace('°', 'º').replace('ª', 'ª')
    s = re.sub(r'\bN\.\s?o\b\.?', 'Nº', s)
    s = re.sub(r'(\d)\.o\b', r'\1º', s)
    s = re.sub(r'\s*\(\*\)\s*$', '', s)      # IMPO's "amended" marker
    s = re.sub(r"^\s*((?:\d+º?|[A-ZÑa-zñ]|[A-Z]'{1,2})\))(?=[^\s,.;)])", r"\1 ", s)   # "1)Observación" -> "1) Observación"
    s = re.sub(r"^(\d+º\.)(?=[A-ZÁÉÍÓÚÑ])", r"\1 ", s)   # "1º.Ser" -> "1º. Ser"
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\s+([,.;:])', r'\1', s)
    return s.strip()


def key_of(text: str) -> str:
    """Comparison key: the words alone, so typesetting differences do not count as changes."""
    t = text.lower()
    t = re.sub(r'^# [^\n]*\n', '', t)
    t = t.replace('º', '')
    return re.sub(r'[^0-9a-záéíóúüñ]+', '', t)


MARK = re.compile(r"^\s*(?:(?:\d+\s?[º°o]?|[A-Za-zÑñ]|[A-Z](?:['´]{1,2}|\")|[IVXLC]+)\)|\d+\s?[º°]\.(?=\s*[A-ZÁÉÍÓÚÑ])|[*•])(?:\s|(?=[A-ZÁÉÍÓÚÑa-záéíóúñ\"(]))")


WRAP = 72


def wrap_width(texts: list[str]) -> int:
    """IMPO's wrap width for a norm: the 97th percentile of its line lengths, at most 80 (a few lines run long)."""
    lens = sorted(len(l.rstrip()) for t in texts for l in t.splitlines() if l.strip())
    return min(lens[int(len(lens) * 0.97)], 80) if lens else WRAP


def impo_paragraphs(raw: str, width: int = WRAP) -> list[str]:
    """IMPO hard-wraps at ~72 columns. Rebuild paragraphs from the layout: a lettered or numbered item starts a
    paragraph and its next line sets the item's continuation column; any other paragraph's first line is indented
    and it continues at the column of a block it sits in (0 at top level, an item's continuation column inside an
    item). A line at the paragraph's continuation column continues it; any other line starts a paragraph, and so
    does a capitalised line after a line that ends a sentence when its first word would have fitted on that line
    (`width` is the norm's longest line: IMPO sets some texts' paragraphs flush left)."""
    paras: list[str] = []
    cur: list[str] = []
    stack = [0]
    seen = {0}
    cont: int | None = 0
    start, marker = 0, False
    blank = blank_before = False

    def flush():
        if cur:
            paras.append(' '.join(x.strip() for x in cur))
            cur.clear()

    def ended(prev: str, line: str) -> bool:
        prev = re.sub(r'\s*\(\*\)$', '', prev.rstrip())
        if not (prev[-1:] in '.:;' and line.lstrip()[:1].isupper()):
            return False
        if len(prev) > width + 5:
            return True           # an unwrapped paragraph (IMPO sets some amended text on one line)
        return not marker and len(prev) + 1 + len(line.split()[0]) <= width - 1

    def wrapped(prev: str, line: str) -> bool:
        prev = prev.rstrip()
        if prev[-1:] in '.:;':
            return False
        return line.lstrip()[:1].islower() or len(prev) + 1 + len(line.split()[0]) > width - 1

    def begin(line: str, ind: int, is_marker: bool) -> None:
        nonlocal cont, start, marker
        flush()
        while len(stack) > 1 and stack[-1] > ind:
            stack.pop()
        cur.append(line)
        cont = None
        start, marker = ind, is_marker

    raw = re.sub(r'</?(?:i|b|u|em|strong|sup|sub)>', '', raw, flags=re.I)
    for line in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = line.replace('\u00a0', ' ').replace('\t', '    ').rstrip()
        if not line.strip():
            flush()
            blank = True
            continue
        ind = len(line) - len(line.lstrip(' '))
        if not cur:
            blank_before, blank = blank, False
        if MARK.match(line):
            begin(line, ind, True)
        elif not cur:
            begin(line, ind, False)
        elif ended(cur[-1], line):
            begin(line, ind, False)     # the line before ended a sentence although the next word would have fit
        elif wrapped(cur[-1], line):
            cur.append(line)            # the line before ran on: no sentence end, and the next word did not fit
            if cont is None:
                cont = ind
                if marker:
                    seen.add(ind)
                    if ind > stack[-1]:
                        stack.append(ind)
        elif cont is None and marker:
            cont = ind
            seen.add(ind)
            if ind > stack[-1]:
                stack.append(ind)
            cur.append(line)
        elif cont is None:
            # a paragraph's second line continues it only at a known block column left of its first line
            if (ind < start and ind in seen) or ind == start == 0 or (ind == start and blank_before):
                cont = ind
                cur.append(line)
            else:
                begin(line, ind, False)
        elif ind == cont:
            cur.append(line)
        else:
            begin(line, ind, False)
    flush()
    return [p for p in (norm(x) for x in paras) if p]


def strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s)


def cell_paragraphs(cell: str) -> list[str]:
    parts = re.split(r'(?:<br\s*/?>\s*){2,}', cell, flags=re.I)
    return [p for p in (norm(strip_tags(re.sub(r'<br\s*/?>', ' ', x, flags=re.I))) for x in parts) if p]


def _debug_word_diff(a: str, b: str) -> list[str]:
    import difflib
    wa, wb = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if op != 'equal':
            out.append(f'{op}: {" ".join(wa[i1:i2])!r} -> {" ".join(wb[j1:j2])!r}')
    return out
