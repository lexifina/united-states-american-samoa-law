"""Read an act's paragraphs out of a Journal officiel de la République du Congo PDF (text layer only).

The JO is set in two justified columns, with full-width runs (preambles, tables of contents).
Reading order: full-width lines split a page into bands; inside a band, the left column, then the
right one. A paragraph ends where the vertical gap is larger than the line spacing, where a line
stops short of its column edge and the next starts a new sentence, or at a list dash. Words
hyphenated at a line end are rejoined (see `dehyphenate`).
"""
import re

import fitz

HEADER_MAX_Y = 24.0      # running heads ("Journal officiel ...", page number) sit at y ~ 14
LIGATURES = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}

# A hyphen at a line end is kept when the left part is one of these (compound words).
KEEP_HYPHEN_LEFT = {
    'quatre', 'vingt', 'soixante', 'dix', 'celui', 'celle', 'ceux', 'celles', 'peut', "c'est", 'c’est',
    'au', 'ci', 'là', 'vice', 'sous', 'non', 'demi', 'ex', 'contre', 'après', 'avant', 'pro', 'est',
    'lui', 'elle', 'eux', 'elles', 'nous', 'vous', 'moi', 'toi', 'soi', 'grand', 'arrière', 'beau',
    'belle', 'chef', 'garde', 'porte', 'micro', 'socio', 'audio', 'extra', 'franco', 'afro', 'euro',
    'unité', 'travail', 'dit', 'dite', 'dits', 'dites', 'sus', 'susdit', 'outre', 'semi', 'avant',
    'entre', 'hors', 'quasi', 'mi', 'auto', 'inter', 'trans', 'pré', 'post', 'co',
}
KEEP_HYPHEN_RIGHT = {'ci', 'là', 'même', 'mêmes', 'dessus', 'dessous', 'dire', 't', 'il', 'elle', 'on',
                     'ils', 'elles', 'être', 'vingt', 'dix', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six',
                     'sept', 'huit', 'neuf', 'mer'}


def norm_chars(s):
    for k, v in LIGATURES.items():
        s = s.replace(k + ' ', v).replace(k, v)
    s = s.replace('\xa0', ' ').replace(' ', ' ').replace(' ', ' ').replace('`', '’')
    s = s.replace("'", '’')
    return s


def page_lines(page):
    """Lines of one page in reading order: dicts with text, x0, x1, y0, col."""
    w = page.rect.width
    mid = w / 2
    raw = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans'])
            if not t.strip():
                continue
            x0, y0, x1, y1 = l['bbox']
            if y0 < HEADER_MAX_Y:
                continue
            raw.append([x0, y0, x1, y1, t])
    # merge spans of one visual line (justified text is sometimes split into words)
    raw.sort(key=lambda r: (round(r[1]), r[0]))
    merged = []
    for r in raw:
        side = 'L' if r[0] < mid - 8 else 'R'
        for m in merged:
            mside = 'L' if m[0] < mid - 8 else 'R'
            if abs(m[1] - r[1]) < 3 and mside == side and r[0] >= m[2] - 2 and (r[0] - m[2]) < 60:
                m[4] = m[4].rstrip() + ' ' + r[4].lstrip()
                m[2] = max(m[2], r[2])
                break
        else:
            merged.append(list(r))
    fw = sorted(m[1] for m in merged if m[0] < mid - 20 and m[2] > mid + 20)
    out = []
    for x0, y0, x1, y1, t in merged:
        full = x0 < mid - 20 and x1 > mid + 20
        band = sum(1 for y in fw if y < y0 - 0.5)
        if full:
            col, key = 'F', (band, 3, y0, x0)
        elif x0 < mid - 8:
            col, key = 'L', (band, 1, y0, x0)
        else:
            col, key = 'R', (band, 2, y0, x0)
        out.append({'text': norm_chars(t).strip(), 'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'col': col, 'key': key})
    out.sort(key=lambda d: d['key'])
    return out


def col_edges(lines):
    """Right edge of each column on a page: the most common large x1."""
    edges = {}
    for c in 'LRF':
        xs = sorted(round(l['x1']) for l in lines if l['col'] == c)
        if xs:
            edges[c] = xs[int(len(xs) * 0.9)] if len(xs) > 3 else max(xs)
    return edges


def dehyphenate(prev, nxt):
    """Join a line ending in '-' with the next line."""
    m = re.search(r'(\S+)-$', prev)
    left = m.group(1) if m else ''
    first = nxt.split(' ', 1)[0]
    right = re.sub(r'[^\w’-].*$', '', first)
    leftword = re.split(r'[’\'-]', left)[-1].lower() if left else ''
    if (leftword in KEEP_HYPHEN_LEFT or right.lower() in KEEP_HYPHEN_RIGHT or not right[:1].islower()
            or not left[-1:].isalpha()):
        return prev + nxt
    return prev[:-1] + nxt


def paragraphs(pdf_path, start_re, end_re, first_page=0, last_page=None, include_end=True):
    """Paragraphs (strings) of the act starting at the line matching start_re and ending after end_re."""
    doc = fitz.open(pdf_path)
    last_page = doc.page_count - 1 if last_page is None else last_page
    paras = []
    cur = None
    prev = None
    started = False
    for pn in range(first_page, last_page + 1):
        lines = page_lines(doc[pn])
        edges = col_edges(lines)
        for ln in lines:
            t = ln['text']
            if not started:
                if re.search(start_re, t):
                    started = True
                else:
                    continue
            if re.fullmatch(r'\d{1,4}', t) or re.match(r'^Journal off', t) or re.match(r'^(Edition spéciale|N°\s*\d+-\d{4}$|De \w+ \d{4}$|Du \w+ \d)', t):
                continue
            new = False
            if cur is None:
                new = True
            else:
                same_col = prev['page'] == pn and (prev['col'] == ln['col'] or 'F' in (prev['col'], ln['col']))
                gap = ln['y0'] - prev['y0'] if same_col else None
                short = prev['x1'] < edges.get(prev['col'], prev['x1']) - 18 if prev['page'] == pn else prev['short']
                if re.match(r'^(-|•)\s*\S', t) or re.match(r'^Articles?\s+(premier|\d+)', t):
                    new = True
                elif is_caps(t) != is_caps(prev['text']):
                    new = True
                elif cur.endswith('-') and not cur.endswith(' -') and cur != '-':
                    new = False
                elif re.fullmatch(r'-|•', cur.strip()):
                    new = False
                elif gap is not None and (gap > 17.5 or gap < -1):
                    new = True
                elif short and re.match(r'^[A-ZÀ-Ý«]', t) and re.search(r'[.;:!?»]$', cur):
                    new = True
                elif gap is not None and gap > 13.5 and short:
                    new = True
            if new:
                if cur is not None:
                    paras.append(cur)
                cur = t
            else:
                if re.fullmatch(r'-|•', cur.strip()):
                    cur = '- ' + t
                elif cur.endswith('-') and not cur.endswith(' -'):
                    cur = dehyphenate(cur, t)
                else:
                    cur = cur + ' ' + t
            ln = dict(ln)
            ln['page'] = pn
            ln['short'] = ln['x1'] < edges.get(ln['col'], ln['x1']) - 18
            prev = ln
            if re.search(end_re, t):
                if not include_end:
                    cur = cur[:len(cur) - len(t)].rstrip() if cur.endswith(t) else cur
                    if cur == '' or cur == t:
                        cur = None
                if cur:
                    paras.append(cur)
                return [clean(p) for p in paras]
    if cur:
        paras.append(cur)
    return [clean(p) for p in paras]


def is_caps(t):
    letters = [c for c in t if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


def clean(p):
    p = re.sub(r'\s+', ' ', p).strip()
    p = re.sub(r'^[-•]\s*', '- ', p)
    return p
