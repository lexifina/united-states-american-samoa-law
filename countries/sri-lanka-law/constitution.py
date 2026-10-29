"""Parse Parliament of Sri Lanka's consolidated English editions of the Constitution into units.

Each edition is a text-layer PDF (no OCR). We keep body-size text only: running headers,
page numbers, marginal notes and footnotes are typeset smaller or sit above the text block.
Footnote reference markers (small digits or asterisks before an editorial "[") are dropped
along with the editorial brackets; the footnotes themselves are read for credits.
"""
import re
import fitz

ORD = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7,
    'eighth': 8, 'ninth': 9, 'tenth': 10, 'eleventh': 11, 'twelfth': 12, 'thirteenth': 13,
    'fourteenth': 14, 'fifteenth': 15, 'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18,
    'nineteenth': 19, 'twentieth': 20,
}

# per edition: y below which the running header ends, minimum body font size
EDITIONS = {
    '17': {'top': 152, 'min_size': 9.8},
    '18': {'top': 155, 'min_size': 9.8},
    '19': {'top': 64, 'min_size': 10.2},
    '20': {'top': 58, 'min_size': 9.5},
    '21': {'top': 78, 'min_size': 9.95},
}

SENT = '\x01'  # where a footnote marker was dropped


def amendment_numbers(text):
    """Amendment ordinals named in a footnote ("Sixteenth Amendment", "Twenty First Amendment")."""
    out = []
    t = text.lower().replace('-', ' ')
    for m in re.finditer(r'(twenty\s*(first|second|third)?|' + '|'.join(sorted(ORD, key=len, reverse=True)) + r')\s+amendment', t):
        w = re.sub(r'\s+', ' ', m.group(1)).strip()
        if w.startswith('twenty'):
            rest = w[6:].strip()
            n = 20 + ({'first': 1, 'second': 2, 'third': 3}.get(rest, 0))
        else:
            n = ORD[w]
        out.append(n)
    for m in re.finditer(r'\b(\d{1,2})(st|nd|rd|th)\s+amendment', t):
        out.append(int(m.group(1)))
    return out


def page_rows(page, cfg):
    """Body rows of one page as (x0, text) plus footnote rows' text."""
    spans = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                if not s['text'].strip():
                    continue
                x0, y0, x1, y1 = s['bbox']
                spans.append((y0, y1, x0, x1, s['size'], s['font'], s['text']))
    body, small = [], []
    for sp in spans:
        y0, y1, x0, x1, size, font, text = sp
        if y1 < cfg['top']:
            continue
        if size >= cfg['min_size']:
            body.append(sp)
        else:
            small.append(sp)
    # footnote markers: small digit/asterisk spans sitting on a body row
    markers = []
    rest = []
    for sp in small:
        y0, y1, x0, x1, size, font, text = sp
        t = text.strip()
        m = re.match(r'^([\d\*]{1,3})\s*(\[.*)?$', t)
        on_row = any(abs(((b[0] + b[1]) / 2) - ((y0 + y1) / 2)) < max(4, (y1 - y0)) for b in body if b[2] - 2 > x0 - 40 or True)
        if m and on_row and any(b[2] >= x0 - 2 and abs(b[0] - y0) < 8 for b in body):
            markers.append(sp)
            if m.group(2):
                # the rest of the span ("[(2) Tamil ...") is body text typeset small after the marker
                body.append((y0, y1, x0 + 0.02, x1, cfg['min_size'], font, m.group(2)))
                markers[-1] = (y0, y1, x0, x0 + 0.01, size, font, m.group(1))
        else:
            rest.append(sp)
    # a small span carrying a marker followed by body words in the same span: keep words
    items = [(sp, False) for sp in body] + [(sp, True) for sp in markers]
    items.sort(key=lambda it: ((it[0][0] + it[0][1]) / 2, it[0][2]))
    rows = []
    for sp, is_marker in items:
        yc = (sp[0] + sp[1]) / 2
        if rows and abs(rows[-1]['yc'] - yc) <= 4.0:
            rows[-1]['items'].append((sp, is_marker))
        else:
            rows.append({'yc': yc, 'items': [(sp, is_marker)]})
    out = []
    for r in rows:
        its = sorted(r['items'], key=lambda it: it[0][2])
        if all(m for _, m in its):
            continue
        parts = []
        for sp, is_marker in its:
            if is_marker:
                parts.append(SENT + '{' + sp[6].strip() + '}')
            else:
                parts.append(sp[6])
        x0 = min(sp[2] for sp, m in its if not m)
        out.append((x0, ' '.join(parts)))
    # footnotes: small text rows below the last body row
    last_body = max((sp[1] for sp in body), default=0)
    foot = sorted([sp for sp in rest if sp[0] >= last_body - 2], key=lambda s: (round((s[0] + s[1]) / 2), s[2]))
    frows = []
    for sp in foot:
        yc = (sp[0] + sp[1]) / 2
        if frows and abs(frows[-1][0] - yc) <= 3:
            frows[-1][1].append(sp[6])
        else:
            frows.append((yc, [sp[6]]))
    notes = {}
    key = None
    for _, parts in frows:
        t = ' '.join(p.strip() for p in parts).strip()
        m = re.match(r'^(\d{1,3}|\*{1,6})\s*[-–.]?\s+(.*)$', t)
        if m and ('mend' in t or 'epeal' in t or 'nsert' in t or 'ubstitut' in t or 'enumber' in t or 'riginal' in t):
            key = m.group(1)
            notes[key] = m.group(2)
        elif key:
            notes[key] += ' ' + t
    return out, notes


def edition_rows(path, ed):
    cfg = EDITIONS[ed]
    doc = fitz.open(path)
    allrows = []
    for i, page in enumerate(doc):
        rows, notes = page_rows(page, cfg)
        for x0, t in rows:
            allrows.append({'page': i, 'x0': x0, 'text': t, 'notes': notes})
    return allrows


# ---------------------------------------------------------------- normalisation

def norm(t):
    t = t.replace(' ', ' ').replace('\t', ' ')
    t = t.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    t = t.replace('``', '"').replace("''", '"')
    t = t.replace('–', '-').replace('—', '-').replace('‒', '-').replace('‐', '-').replace('­', '')
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'\s+([,;:.])', r'\1', t)
    t = re.sub(r'([,;:])(?=[A-Za-z(])', r'\1 ', t)
    t = re.sub(r'^(\(\w{1,4}\))(?=[A-Za-z"])', r' ', t)
    t = re.sub(r'\(\s+', '(', t)
    t = re.sub(r'\s+\)', ')', t)
    t = re.sub(r'"\s+', '"', t) if t.count('"') == 1 else t
    return t


def strip_editorial(t):
    """Drop footnote markers and the editorial brackets they open; drop unmatched closing brackets."""
    t = re.sub(SENT + r'\{[^}]*\}\s*\[?', SENT, t)
    t = re.sub(r'(?<![\w\]])\*{1,6}\s*\[', SENT, t)   # body-size "*[" (17th/18th editions)
    t = re.sub(r'(^|\s)\*{1,6}(?=\s|$)', r'\1', t)
    t = t.replace(SENT, '')
    out, depth = [], 0
    for ch in t:
        if ch == '[':
            depth += 1
            out.append(ch)
        elif ch == ']':
            if depth:
                depth -= 1
                out.append(ch)
        else:
            out.append(ch)
    return ''.join(out)


def markers_in(t):
    return re.findall(SENT + r'\{([^}]*)\}', t)


# ---------------------------------------------------------------- units

ART_RE = re.compile(r'^\s*(?:' + SENT + r'\{[^}]*\}\s*)?(?:\*{1,6}\s*)?\[?\s*(\d{1,3})\s*([A-Z]{0,2})\s*\.\s*(.*)$')
TOKEN_RE = re.compile(r'^(\(\d+[A-Z]?\)|\([a-z]{1,2}\)|\([ivxl]+\)|\([A-Z]\)|Provided\b|Explanation\b|"[A-Za-z])')
SCHED_RE = re.compile(r'^(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH)\s+SCHEDULE\b', re.I)
SCHED_N = {'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5, 'SIXTH': 6, 'SEVENTH': 7, 'EIGHTH': 8, 'NINTH': 9}


def akey(num, suf):
    return 'art-%03d%s' % (num, suf.lower())


def art_order(num, suf):
    return (num, suf)


def plain(t):
    return re.sub(SENT + r'\{[^}]*\}', '', t)


def is_heading(t):
    p = plain(t).strip()
    letters = re.sub(r'[^A-Za-z]', '', p)
    if re.match(r'^CHAPTER\b', p, re.I) and len(p) < 40:
        return True
    return len(letters) >= 3 and letters.upper() == letters and not re.match(r'^\(?\d', p)


def split_units(rows, last_article=(170, '')):
    """Group rows into units: preamble, art-NNNx, schedule-NN. Returns ordered dict key -> list of rows."""
    units = {}
    order = []
    cur = None
    cur_art = (0, '')
    started = False
    in_sched = False
    drop_caps = False
    for r in rows:
        t = r['text']
        p = plain(t).strip()
        if not started:
            if re.match(r'^SVASTI\b', p) or re.match(r'^The\s+PEOPLE\s+OF\s+SRI\s+LANKA', p, re.I):
                started = True
                cur = 'preamble'
                units[cur] = []
                order.append(cur)
            else:
                continue
        if re.match(r'^Other\s+Consequential\s+Amendments', p, re.I) or re.match(r'^Devo\s+Vassatu', p, re.I):
            cur = None
            continue
        ms = SCHED_RE.match(re.sub(r'^[\[\*"\s]+', '', p))
        if ms and cur_art >= last_article:
            n = SCHED_N[ms.group(1).upper()]
            key = 'schedule-%02d' % n
            if key not in units:
                cur = key
                units[cur] = []
                order.append(cur)
                in_sched = True
                continue
        if not in_sched:
            m = ART_RE.match(t if not t.lstrip().startswith(SENT) else t)
            mm = ART_RE.match(re.sub(r'(?<![A-Za-z])l(?=\d)|(?<=\d)l(?=[\dA-Z]*\s*\.)', '1', p))
            if not mm:
                mr = re.match(r'^\s*\[?\s*(\d{1,3})\s*([A-Z]{0,2})\s+(Repealed)', p)
                mm = mr
            if mm:
                num, suf = int(mm.group(1)), mm.group(2)
                nxt = (num, suf)
                ok = nxt > cur_art and (num - cur_art[0]) <= 4 and (cur != 'preamble' or num == 1)
                if ok and (r['x0'] is not None):
                    cur_art = nxt
                    cur = akey(num, suf)
                    units[cur] = []
                    order.append(cur)
            if cur == 'preamble' and is_heading(t) and not re.search(r'SUPREME LAW|CONSTITUTION|DEMOCRATIC|SOCIALIST|REPUBLIC|SRI LANKA|PEOPLE', p):
                pass
            elif cur != 'preamble' and is_heading(t):
                if re.match(r'^CHAPTER', p, re.I):
                    drop_caps = True
                    continue
                if drop_caps or not re.match(r'^(SCHEDULE|PART\s+[IVX]+|LIST)', p):
                    continue
            drop_caps = False
        if cur is None:
            continue
        units[cur].append(r)
    return order, units


def unit_text(rows, key):
    """Join rows into paragraphs, one per line."""
    paras = []
    prev = ''
    for i, r in enumerate(rows):
        t = r['text']
        p = plain(t).strip()
        if key.startswith('art-') and i == 0:
            mm = re.match(r'^\s*((?:' + SENT + r'\{[^}]*\}\s*)?(?:\*{1,6}\s*)?\[?\s*)([l\d]{1,3}\s*[A-Z]{0,2}\s*(?:\.|(?=\s+Repealed))\s*)(.*)$', t)
            if mm:
                t = mm.group(1) + mm.group(3)
                p = plain(t).strip()
        start = False
        if not paras:
            start = True
        else:
            pe = plain(prev).rstrip()
            if TOKEN_RE.match(strip_editorial(t).strip().lstrip('[').strip()) and re.search(r'([:;.\-–—]|\b(and|or))\s*\]?$', pe):
                start = True
            elif key.startswith('schedule') and re.search(r'[:;.]\s*\]?$', pe) and r['x0'] > rows[i - 1]['x0'] + 5:
                start = True
        if start:
            paras.append(t)
        else:
            a = paras[-1].rstrip()
            if a.endswith('-') and not a.endswith(' -') and re.match(r'^[a-z]', p):
                paras[-1] = a + t.lstrip()
            else:
                paras[-1] = a + ' ' + t.lstrip()
        prev = t
    lines = []
    marks = []
    for para in paras:
        marks += markers_in(para)
        s = norm(strip_editorial(para))
        if s:
            lines.append(s)
    return lines, marks


def parse_edition(path, ed):
    rows = edition_rows(path, ed)
    order, units = split_units(rows)
    out = {}
    notes_by_unit = {}
    for key in order:
        lines, marks = unit_text(units[key], key)
        if key.startswith('art-'):
            label = 'Article ' + key[4:].lstrip('0').upper()
        elif key == 'preamble':
            label = 'Preamble'
        else:
            label = key.replace('schedule-0', 'Schedule ').replace('schedule-', 'Schedule ')
        out[key] = {'label': label, 'lines': lines}
        # credits from the edition's own footnotes, matched by marker on the unit's pages
        amends = set()
        pages = {}
        for r in units[key]:
            for mk in markers_in(r['text']):
                note = r['notes'].get(mk)
                if note:
                    amends.update(amendment_numbers(note))
            # "*[" body-size markers (17th/18th): match asterisk notes on the same page
            for mk in re.findall(r'(?<![\w\]])(\*{1,6})\s*\[', plain(r['text'])):
                note = r['notes'].get(mk)
                if note:
                    amends.update(amendment_numbers(note))
        notes_by_unit[key] = sorted(amends)
    return out, notes_by_unit
