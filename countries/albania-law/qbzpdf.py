"""Reads a QBZ (Qendra e Botimeve Zyrtare) edition of the Constitution, as PDF with a text layer, into units.

    units, notes = read_edition(pdf_bytes)

units: {key: {'label', 'kind', 'text'}} in document order. notes: {key: the publisher's amendment note, e.g.
"(Ndryshuar me ligjin nr. 9904, datë 21.4.2008)"}; notes are kept out of the text and used only to check credits.

QBZ sets the Constitution in Word and exports it with Acrobat PDFMaker, so the text layer is the typesetter's own
text (no OCR). Layout rules used here, read off the editions:
- body paragraphs start indented; their continuation lines start at the left margin;
- "Neni N", "PJESA ...", "KREU ..." and titles are centred lines; titles (and the preamble) are set in bold;
- the publisher's amendment notes are italic lines in parentheses under an article heading;
- page numbers are Times New Roman digits; footnotes are set small.
"""
from __future__ import annotations

import collections
import re
import unicodedata

import fitz  # PyMuPDF

ALB_LETTERS = ['a', 'b', 'c', 'ç', 'd', 'dh', 'e', 'ë', 'f', 'g', 'gj', 'h', 'i', 'j', 'k', 'l', 'll', 'm', 'n', 'nj',
               'o', 'p', 'q', 'r', 'rr', 's', 'sh', 't', 'th', 'u', 'v', 'x', 'xh', 'y', 'z', 'zh']
ORDINALS = ['PARË', 'DYTË', 'TRETË', 'KATËRT', 'PESTË', 'GJASHTË', 'SHTATË', 'TETË', 'NËNTË', 'DHJETË',
            'NJËMBËDHJETË', 'DYMBËDHJETË', 'TREMBËDHJETË', 'KATËRMBËDHJETË', 'PESËMBËDHJETË', 'GJASHTËMBËDHJETË',
            'SHTATËMBËDHJETË', 'TETËMBËDHJETË']
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']

RE_NENI = re.compile(r'^Neni\s+(\d+)(?:\s*/\s*(\d+|[a-zçë]+))?\s*$|^Neni\s+([A-ZÇË]{1,2})\s*$')
RE_PJESA = re.compile(r'^PJESA\s+E\s+(\S+)\s*$')
RE_KREU = re.compile(r'^KREU\s+([IVX]+)\s*$')
RE_NOTE = re.compile(r'^\(\s*(?:Ndryshuar|Shtuar|Shfuqizuar|parashikuar|Zëvendësuar)', re.I)
RE_INDEX = re.compile(r'^(TREGUESI|PËRMBAJTJA)\b')
RE_MARKER = re.compile(r'^(\d+(/\d+)?\.|[a-zçë]{1,2}\))\s')


def letter_key(s: str) -> str:
    """An Albanian letter as an ASCII key part that sorts in Albanian alphabetical order: ç -> c-ced, ë -> e-uml."""
    s = s.lower()
    return s.replace('ç', 'c-ced').replace('ë', 'e-uml')


def neni_key(num: str | None, sub: str | None, annex: str | None) -> tuple[str, str]:
    if annex:
        return f'aneks-neni-{letter_key(annex)}', f'Neni {annex}'
    key = f'neni-{int(num):03d}'
    label = f'Neni {int(num)}'
    if sub:
        if sub.isdigit():
            key += f'-{int(sub):02d}'
        else:
            key += f'-{letter_key(sub)}'
        label += f'/{sub}'
    return key, label


def norm(s: str) -> str:
    s = unicodedata.normalize('NFC', s)
    s = s.replace(' ', ' ').replace('­', '').replace('\t', ' ')
    s = s.replace('–', '-').replace('—', '-').replace('‑', '-')
    s = s.replace('‘', '’').replace("'", '’')
    s = s.replace('”', '”').replace('“', '“').replace('„', '“').replace('"', '”')
    return re.sub(r' {2,}', ' ', s).strip()


def rows(pdf: bytes):
    """Every printed row: (page, y, x0, text, bold, italic, small, times)."""
    doc = fitz.open(stream=pdf, filetype='pdf')
    out = []
    for pn in range(doc.page_count):
        byrow = collections.defaultdict(list)
        for b in doc[pn].get_text('dict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    byrow[round(s['bbox'][3])].append(s)
        for y in sorted(byrow):
            spans = sorted(byrow[y], key=lambda s: s['bbox'][0])
            text = ''.join(s['text'] for s in spans)
            if not text.strip():
                out.append((pn, y, None, '', False, False, False, False))
                continue
            first = next(s for s in spans if s['text'].strip())
            font = first['font']
            out.append((pn, y, first['bbox'][0], text, 'Bold' in font, 'Italic' in font,
                        max(s['size'] for s in spans if s['text'].strip()), 'Times' in font))
    sizes = collections.Counter(round(r[6]) for r in out if r[2] is not None)
    body = sizes.most_common(1)[0][0]
    # footnotes are set well below the body size
    return [r[:6] + (r[2] is not None and r[6] < body - 0.6, r[7]) for r in out]


def read_edition(pdf: bytes):
    rs = rows(pdf)
    xs = collections.Counter(round(r[2]) for r in rs if r[2] is not None)
    margin = min(x for x, n in xs.items() if n > 50)
    units: dict[str, dict] = {}
    notes: dict[str, str] = {}
    cur = None          # current unit key
    para: list[str] = []
    pjesa = 0
    kreu = 0
    in_annex = False
    pending_heading = None   # key of a heading unit waiting for its title line
    state = 'start'
    note_open = False

    def cx_of(x):
        return x > margin + 60

    para_x: list[float] = []

    def flush():
        nonlocal para
        if cur is not None and para:
            units[cur]['lines'].append(norm(' '.join(para)))
        para = []
        para_x.clear()

    def open_unit(key, label, kind, first_line):
        nonlocal cur
        flush()
        if key in units:
            raise ValueError(f'duplicate unit {key}')
        units[key] = {'label': label, 'kind': kind, 'lines': [first_line]}
        cur = key

    for pn, y, x, text, bold, italic, small, times in rs:
        t = norm(text)
        if x is None:
            flush()
            continue
        if small or t.isdigit():
            continue
        if state == 'start':
            # The edition's own title block, up to the preamble.
            if t.startswith('Ne, Populli'):
                state = 'body'
                open_unit('preambula', 'Preambula', 'preamble', '# Preambula')
                para = [t]
            continue
        if RE_INDEX.match(t) and cx_of(x):
            break   # an index or table of contents after the text
        heading_only = cur is not None and not para and units[cur]['kind'] in ('art', 'part', 'annex') \
            and len(units[cur]['lines']) <= 2
        if (RE_NOTE.match(t) and not para) or note_open or (italic and heading_only):
            # the publisher's amendment note under a heading, possibly over several rows
            notes[cur] = (notes.get(cur, '') + ' ' + t).strip()
            note_open = notes[cur].count('(') > notes[cur].count(')')
            continue
        m = RE_NENI.match(t)
        cx = x > margin + 60   # centred
        if m and cx:
            key, label = neni_key(m.group(1), m.group(2), m.group(3) if in_annex else None)
            open_unit(key, label, 'art', f'# {label}')
            pending_heading = key
            continue
        m = RE_PJESA.match(re.sub(r'\s+', ' ', t))
        if m and cx:
            pjesa = ORDINALS.index(m.group(1)) + 1
            kreu = 0
            open_unit(f'pjesa-{pjesa:02d}', f'Pjesa e {m.group(1).lower()}', 'part', f'# {t}')
            pending_heading = cur
            continue
        m = RE_KREU.match(t)
        if m and cx:
            kreu = ROMAN.index(m.group(1)) + 1
            open_unit(f'pjesa-{pjesa:02d}-kreu-{kreu:02d}', f'Pjesa e {ORDINALS[pjesa - 1].lower()}, kreu {m.group(1)}',
                      'chapter', f'# {t}')
            pending_heading = cur
            continue
        if t == 'ANEKS' and cx:
            in_annex = True
            open_unit('aneks', 'Aneks', 'annex', '# ANEKS')
            pending_heading = cur
            continue
        if t.startswith('Dispozita kalimtare të parashikuara me ligjin'):
            num = re.search(r'nr\.\s*(\d+)', t).group(1)
            open_unit(f'kalimtare-ligji-{num}', f'Dispozita kalimtare (ligji nr. {num})', 'transitional', f'# {t}')
            pending_heading = cur
            continue
        if re.match(r'Miratuar me ligjin nr\.\s*8417', t):
            open_unit('miratimi', 'Miratimi dhe shpallja', 'formula', '# Miratimi dhe shpallja')
            para = [t]
            pending_heading = None
            continue
        if cx and pending_heading == cur and not para:
            # a title (or the second line of a heading), set on its own centred line
            if units[cur]['kind'] == 'transitional' and t.startswith('datë'):
                units[cur]['lines'][0] += ' ' + t
            else:
                units[cur]['lines'].append(t)
            continue
        pending_heading = None
        if cur == 'miratimi':
            if x > margin + 8:
                flush()
            para.append(t)
            continue
        # body text: an indented row starts a paragraph, unless it is a hanging continuation (indented further than
        # the row before, as the Assembly's 1998 copy sets lettered items); a list marker always starts one
        prev_x = para_x[-1] if para_x else None
        if x > margin + 8 and (RE_MARKER.match(t) or prev_x is None or prev_x <= margin + 8 or x <= prev_x + 2):
            flush()
        para.append(t)
        para_x.append(x)
    flush()
    out = {}
    for k, u in units.items():
        lines = [l for l in u['lines'] if l]
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(lines) + '\n'}
    return out, notes


def flat(text: str) -> str:
    """Text for comparing two editions: headings dropped, all whitespace collapsed."""
    return re.sub(r'\s+', ' ', text).strip()


if __name__ == '__main__':
    import sys
    data = open(sys.argv[1], 'rb').read()
    units, notes = read_edition(data)
    for k, u in units.items():
        print(f'== {k} [{u["kind"]}] {u["label"]}  {notes.get(k, "")}')
        print(u['text'], end='')
