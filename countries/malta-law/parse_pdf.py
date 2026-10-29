"""Parse one consolidated version of a Maltese law (a legislation.mt PDF) into units.

The PDFs are typeset the same way across Chapters and subsidiary legislation:
- a running header at the top of every page (dropped);
- the body in 10pt, with article numbers in bold at the start of a line ("57." or "56A. Notwithstanding");
- an 8pt margin column on the outer edge (left on even pages, right on odd), holding each article's heading and its
  history: "Amended by:", "Added by:", "Substituted by:", "Repealed by:", "Renumbered by:" followed by citations such
  as "XXIII.1971.6" (Act XXIII of 1971, section 6) or "L.N. 46 of 1965", and cross references ("Cap. 380.");
- front matter before article 1 (the title, the date, the list of amending laws), and an arrangement table;
- centred headings between articles (BOOK FIRST, Title IV, PART II), and schedules at the end.

Output: {'preamble': [lines], 'units': [{'id', 'kind', 'heading': [..], 'lines': [..], 'notes': [{'kind', 'by'}],
'refs': [..]}]}, units in document order. Inside a schedule, bold numbers are items of the schedule, not articles.
"""
import re
import sys
from dataclasses import dataclass, field

import pymupdf

NOTE_KINDS = re.compile(r'^(Amended|Added|Substituted|Repealed|Renumbered|Revoked|Replaced|Inserted|Deleted|Corrected|'
                        r'Re-numbered)\s+(?:and\s+\w+\s+)?by\s*:?\s*', re.I)
ARTICLE = re.compile(r'^\s*(\d{1,4}[A-Z]{0,3})\.(?:\s|$)')
SCHEDULE = re.compile(r'^\s*((?:[A-Z]+\s+){0,2}SCHEDULE(?:\s+[A-Z0-9]{1,4})?|ANNEX(?:\s+[A-Z0-9]{1,4})?|'
                      r'APPENDIX(?:\s+[A-Z0-9]{1,4})?)\s*$')
ENUM = re.compile(r'^\((?:\d{1,3}[A-Z]{0,2}|[a-z]{1,2}|[ivxl]{1,6}|[A-Z]{1,2})\)')
CITE_SPLIT = re.compile(r'\s*;\s*|\s*,\s*(?=(?:L\.N\.|[IVXLC]+\.\d{4}))')
HEADER_Y = 42


@dataclass
class Line:
    page: int
    y: float
    x: float
    x1: float
    size: float
    bold: bool
    italic: bool
    text: str
    margin: bool = False   # in the margin column
    centred: bool = False  # a centred body row (a heading)
    tx: float = 0.0        # where the words start, relative to the wrap margin, after a lone "(a)" or "57."
    rel: float = 0.0       # x relative to the page's wrap margin


@dataclass
class Unit:
    id: str
    kind: str
    page: int
    y: float
    heading: list[str] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)


LETTER_SPACED = re.compile(r'(?:\b\w ){5,}')


def respace(spans: list[dict]) -> None:
    """Justified lines are sometimes letter-spaced: a space glyph after every letter, flush with its neighbours.
    A real word break is a space glyph with a visible gap beside it; keep only those."""
    chars = [c for s in spans for c in s.get('chars', [])]
    keep: set[int] = set()
    for i, c in enumerate(chars):
        if c['c'] != ' ':
            continue
        before = c['bbox'][0] - chars[i - 1]['bbox'][2] if i > 0 else 0
        after = chars[i + 1]['bbox'][0] - c['bbox'][2] if i + 1 < len(chars) else 0
        if before > 0.5 or after > 0.5 or i == 0 or i + 1 == len(chars):
            keep.add(id(c))
    for s in spans:
        s['text'] = ''.join(c['c'] for c in s.get('chars', []) if c['c'] != ' ' or id(c) in keep)


def read_lines(path: str) -> list[Line]:
    doc = pymupdf.open(path)
    out: list[Line] = []
    for pno, page in enumerate(doc):
        width = page.rect.width
        blocks = page.get_text('rawdict')['blocks']
        # The running header is the top line band of every page (y=26 on the old small pages, about 98 on A4).
        ys = [ln['bbox'][1] for bl in blocks for ln in bl.get('lines', [])
              if ''.join(c['c'] for s in ln['spans'] for c in s.get('chars', [])).strip()]
        top = min(ys) if ys else 0
        header_y = top + 6 if top < page.rect.height * 0.2 else -1
        for block in blocks:
            for ln in block.get('lines', []):
                for s in ln['spans']:
                    s['text'] = ''.join(c['c'] for c in s.get('chars', []))
                if LETTER_SPACED.search(''.join(s['text'] for s in ln['spans'])):
                    respace(ln['spans'])
                spans = [s for s in ln['spans'] if s['text'].strip()]
                if not spans:
                    continue
                x0, y0, x1 = ln['bbox'][0], ln['bbox'][1], ln['bbox'][2]
                if y0 <= header_y:
                    continue
                size = max(s['size'] for s in spans)
                font = spans[0]['font']
                line = Line(pno, round(y0, 1), round(x0, 1), round(x1, 1), round(size, 1),
                            'Bold' in font or bool(spans[0]['flags'] & 16),
                            'Italic' in font or font.endswith('-It') or bool(spans[0]['flags'] & 2),
                            ''.join(s['text'] for s in ln['spans']))
                # The margin column: small type at the outer edge (far left on even pages, past the body on odd).
                line.margin = size <= 8.6 and (x0 < width * 0.19 or x0 > width * 0.70)
                out.append(line)
    return out


def merge_rows(lines: list[Line]) -> list[Line]:
    """Join the pieces of one visual line ("57." "(1)" "The Director...") into one row."""
    rows: list[Line] = []
    for ln in sorted(lines, key=lambda l: (l.page, l.y, l.x)):
        if rows and rows[-1].page == ln.page and abs(rows[-1].y - ln.y) <= 2.5:
            prev = rows[-1]
            lone = prev.text.strip()
            if prev.tx == prev.x and (ENUM.fullmatch(lone) or re.fullmatch(r'\d{1,4}[A-Z]{0,3}\.', lone)
                                      or ENUM.fullmatch(lone.split(' ')[-1])):
                prev.tx = ln.x
            prev.text = prev.text.rstrip() + ' ' + ln.text.lstrip()
            prev.x1 = max(prev.x1, ln.x1)
            continue
        rows.append(Line(ln.page, ln.y, ln.x, ln.x1, ln.size, ln.bold, ln.italic, ln.text, tx=ln.x))
    left: dict[int, float] = {}
    right: dict[int, float] = {}
    for r in rows:
        left[r.page] = min(left.get(r.page, 1e9), r.x)
        right[r.page] = max(right.get(r.page, 0.0), r.x1)
    for r in rows:
        r.rel = r.x - left[r.page]
        r.tx = r.tx - left[r.page]
        mid = (left[r.page] + right[r.page]) / 2
        # A justified full-width row is also "centred"; a heading is clearly shorter than the column.
        r.centred = (r.rel > 25 and abs((r.x + r.x1) / 2 - mid) < 18
                     and (r.x1 - r.x) < 0.72 * (right[r.page] - left[r.page]))
    return rows


def clean(text: str) -> str:
    text = text.replace(' ', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def paragraphs(rows: list[Line]) -> list[str]:
    """Rows of one unit into one line per paragraph. A wrapped row comes back to the paragraph's text column (the
    wrap margin, or where the words of an enumerated item start); a row that starts with an enumerator, sits
    further right, is centred, or follows a gap starts a new paragraph."""
    out: list[str] = []
    prev = None
    for r in rows:
        t = clean(r.text)
        if not t:
            continue
        new = (prev is None or bool(ENUM.match(t)) or r.centred or (prev is not None and prev.centred)
               or (r.rel > 6 and abs(r.rel - prev.tx) > 6)
               or (r.page == prev.page and r.y - prev.y > 14.5))
        if new or not out:
            out.append(t)
        else:
            last = out[-1]
            out[-1] = last + t if last.endswith('-') and t[:1].islower() else last + ' ' + t
        prev = r
    return out


def note_blocks(margin: list[Line]) -> list[list[Line]]:
    blocks: list[list[Line]] = []
    for ln in sorted(margin, key=lambda l: (l.page, l.y)):
        if blocks and blocks[-1][-1].page == ln.page and ln.y - blocks[-1][-1].y <= 11:
            blocks[-1].append(ln)
        else:
            blocks.append([ln])
    return blocks


def parse_note(block: list[Line]) -> tuple[str, list[dict], list[str]]:
    heading: list[str] = []
    notes: list[dict] = []
    refs: list[str] = []
    current = None
    for ln in block:
        t = clean(ln.text)
        m = NOTE_KINDS.match(t)
        if m:
            current = {'kind': m.group(1).capitalize(), 'by': []}
            notes.append(current)
            t = t[m.end():]
            if not t:
                continue
        if current is not None and (ln.italic or re.match(r'^(L\.N\.|[IVXLC]+\.\d{4}|Act|Ord|G\.N\.)', t)):
            for c in CITE_SPLIT.split(t):
                c = c.strip().rstrip('.;,').strip()
                if c:
                    current['by'].append(c)
        elif re.match(r'^(Cap\.|S\.L\.)\s*\d', t):
            refs.append(t.rstrip('.'))
        elif current is None:
            heading.append(t)
        else:
            refs.append(t)
    return ' '.join(heading).strip(), notes, refs


def parse(path: str) -> dict:
    lines = read_lines(path)
    body = [l for l in lines if not l.margin and l.size >= 8.9]
    margin = [l for l in lines if l.margin]
    rows = merge_rows(body)

    # Front matter ends at the first bold "1." (the arrangement table has no bold numbers).
    def is_article(r: Line) -> bool:
        return r.bold and bool(ARTICLE.match(r.text))
    start = next((i for i, r in enumerate(rows) if is_article(r) and ARTICLE.match(r.text).group(1) == '1'), None)
    if start is None:
        start = next((i for i, r in enumerate(rows) if is_article(r)), len(rows))
    pre: list[Line] = []
    for r in rows[:start]:
        if re.match(r'^\s*ARRANGEMENT', r.text):
            break
        pre.append(r)

    units: list[Unit] = []
    pending: list[str] = []
    seen: dict[str, int] = {}
    in_schedule = False
    for r in rows[start:]:
        m = ARTICLE.match(r.text) if r.bold and not in_schedule else None
        s = SCHEDULE.match(clean(r.text)) if not m else None
        if s and not in_schedule and units and not r.centred and r.rel < 25:
            s = None  # "SCHEDULE" at the left margin inside an article's text is not a heading
        if m or s:
            in_schedule = in_schedule or bool(s)
            uid = m.group(1) if m else re.sub(r'\s+', '-', s.group(1).strip().lower())
            n = seen.get(uid, 0)
            seen[uid] = n + 1
            u = Unit(uid if n == 0 else f'{uid}~{n + 1}', 'article' if m else 'schedule', r.page, r.y, heading=pending)
            pending = []
            if m:
                rest = r.text[m.end():]
                if rest.strip():
                    u.lines.append(Line(r.page, r.y, r.x, r.x1, r.size, False, r.italic, rest, tx=r.tx, rel=r.tx))
            else:
                u.heading.append(clean(r.text))
            units.append(u)
            continue
        if not units:
            pending.append(clean(r.text))
            continue
        cur = units[-1]
        # Centred headings between articles (BOOK FIRST, Title IV, PART II) belong to the next article.
        if cur.kind == 'article' and r.centred and len(r.text.strip()) < 120 and not ENUM.match(r.text.strip()):
            pending.append(clean(r.text))
            continue
        if pending and cur.kind == 'article' and r.rel > 25 and (r.centred or r.text.strip().isupper()):
            pending.append(clean(r.text))
            continue
        if pending:
            # Not a heading after all (a centred line inside the article): give it back to the article.
            cur.lines.extend(Line(r.page, r.y, r.x, r.x1, r.size, False, False, h, centred=True) for h in pending)
            pending = []
        cur.lines.append(r)
    if pending and units:
        units[-1].lines.extend(Line(0, 0, 0, 0, 10, False, False, h, centred=True) for h in pending)

    # Margin notes belong to the unit that starts nearest at or above them; at the top of a page, to the unit
    # carried over from the page before.
    starts = [(u.page, u.y, i) for i, u in enumerate(units)]
    for block in note_blocks(margin):
        b = block[0]
        target = None
        for page, y, i in starts:
            if (page, y) <= (b.page, b.y + 6):
                target = i
            else:
                break
        if target is None:
            continue
        head, notes, refs = parse_note(block)
        u = units[target]
        if head and head not in u.heading:
            u.heading.append(head)
        u.notes.extend(notes)
        u.refs.extend(refs)

    return {
        'preamble': paragraphs(pre),
        'units': [{'id': u.id, 'kind': u.kind, 'heading': u.heading, 'lines': paragraphs(u.lines), 'notes': u.notes,
                   'refs': u.refs} for u in units],
    }


if __name__ == '__main__':
    import json
    d = parse(sys.argv[1])
    print(json.dumps(d, ensure_ascii=False, indent=1)[:int(sys.argv[2]) if len(sys.argv) > 2 else None])
