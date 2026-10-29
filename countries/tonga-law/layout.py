"""PDF layout -> provisions for the Tongan Revised Editions (1988, 2016, 2020) published by the AGO.

read(pdf_bytes) returns
  {'units': [{'num', 'title', 'kind', 'paras', 'notes'}], 'endnotes': {n: text}, 'outline': [...], 'inline_notes': {num: [..]}}

Layout facts (checked on the Constitution, the Criminal Offences Act and the Land Act):
- every page has a running header (y < 62) and footer (y > height - 50); a big "C"/"T"/"to" in the font "Tonga" is decoration;
- the arrangement pages say "Arrangement of" in the header, endnote pages say "Endnotes";
- a provision starts with a line whose first span is a bold number ("12", "83A") followed by its bold title;
- part / division headings are bold with no number, larger (12-14 pt) or all capitals;
- footnote markers are superscript spans (flag bit 1); they name the endnote that gives the provision's history (2016, 2020);
- the 1988 edition prints its history notes inline, in italics: "(Amended by Act 3 of 1976.)" - removed from the text and kept apart.
"""
import re

import fitz

NOTE_WORDS = r'(?:Law|Laws|Act|Acts|Amended|Substituted|Inserted|Added|Repealed|Replaced|Revoked|Renumbered|See|Ord|Ordinance|G\.?|Gazette|Cap|Proviso|Previously|As amended|Formerly|Originally)\b'


def norm(s):
    for a in '    \t':
        s = s.replace(a, ' ')
    for a in '‘’‛ʻʼ`´':
        s = s.replace(a, "'")
    for a in '“”‟':
        s = s.replace(a, '"')
    for a in '–—‑−‐':
        s = s.replace(a, '-')
    for a in '­‎‏':
        s = s.replace(a, '')
    s = re.sub(r'\.{4,}', '...', s)
    s = re.sub(r'[ ]{2,}', ' ', s)
    return s


def _lines(page):
    """Body lines of one page: [{'y','x','spans':[(x,text,bold,italic,size)], 'sups':[text]}], header/footer removed."""
    h = page.rect.height
    spans = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                t = s['text']
                if not t.strip():
                    continue
                x0, y0, x1, y1 = s['bbox']
                if y0 < 62 or y0 > h - 50:
                    continue
                if s['font'].startswith('Tonga'):
                    continue
                spans.append({'x': x0, 'y0': y0, 'y1': y1, 't': t, 'size': s['size'],
                              'bold': bool(s['flags'] & 16) or 'Bold' in s['font'],
                              'italic': bool(s['flags'] & 2) or 'Italic' in s['font'],
                              'sup': bool(s['flags'] & 1) and s['size'] < 9})
    rows = []
    for s in sorted([s for s in spans if not s['sup']], key=lambda s: (round(s['y1']), s['x'])):
        for r in rows:
            if abs(r['y1'] - s['y1']) < 3:
                r['spans'].append(s)
                break
        else:
            rows.append({'y1': s['y1'], 'y0': s['y0'], 'spans': [s], 'sups': []})
    for s in spans:
        if s['sup']:
            best = min(rows, key=lambda r: abs(r['y0'] - s['y0']), default=None)
            if best is not None and abs(best['y0'] - s['y0']) < 8:
                best['sups'].append((s['x'], s['t'].strip()))
    rows.sort(key=lambda r: r['y1'])
    for r in rows:
        r['spans'].sort(key=lambda s: s['x'])
        r['x'] = r['spans'][0]['x']
    return rows


def _header(page):
    h = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                if s['bbox'][1] < 62:
                    h.append(s['text'])
    return ' '.join(h)


def _text(row):
    """Text of a row with italic runs wrapped in \x01..\x02 (so inline 1988 notes can be cut)."""
    out = []
    for s in row['spans']:
        t = s['t']
        out.append('\x01' + t + '\x02' if s['italic'] else t)
    t = ''.join(out)
    return t


NUM = re.compile(r'^(\d{1,3}[A-Z]{0,2})\s*\.?\s*$')
LABEL = re.compile(r'^\((?:[0-9]{1,3}[A-Za-z]{0,2}|[a-z]{1,2}|[ivxl]{1,5}|[A-Z]{1,2})\)')


def _is_heading(row):
    sp = [s for s in row['spans'] if norm(s['t']).replace('‎', '').strip()]
    if not sp or not sp[0]['bold']:
        return None
    first = norm(sp[0]['t']).replace('‎', '').strip()
    m = NUM.match(first)
    rest = norm(''.join(s['t'] for s in sp[1:])).replace('‎', '').strip()
    if m and rest and (all(s['bold'] for s in sp[1:]) or re.match(r'^\(?\s*Repealed', rest)):
        return m.group(1), rest
    m2 = re.match(r'^(\d{1,3}[A-Z]{0,2})\s+(\S.*)$', first)
    if m2 and all(s['bold'] for s in sp) and not first.isupper():
        return m2.group(1), m2.group(2) + rest
    return None


def _is_structure(row):
    sp = row['spans']
    if not all(s['bold'] for s in sp):
        return False
    t = ''.join(s['t'] for s in sp).strip()
    if not t or NUM.match(t):
        return False
    letters = re.sub(r'[^A-Za-z]', '', t)
    return (sp[0]['size'] >= 12 and not sp[0]['italic']) or (letters.isupper() and len(letters) > 3)


def read(pdf, inline_notes=False):
    doc = fitz.open(stream=pdf, filetype='pdf')
    units, outline, endnote_rows = [], [], []
    front = []  # lines before the first provision (title, long title, preamble)
    cur = None
    started_body = False
    in_endnotes = False
    for pno, page in enumerate(doc):
        hdr = _header(page)
        if 'Arrangement of' in hdr or pno == 0 and 'Revised Edition' in page.get_text() and not re.search(r'(Clause|Section|Regulation|Rule)\s*\d', hdr):
            continue
        rows = _lines(page)
        if 'Endnotes' in hdr or 'ENDNOTES' in hdr or in_endnotes:
            endnote_rows.append(rows)
            continue
        page_first = True
        for r in rows:
            t = _text(r)
            plain = norm(t.replace('\x01', '').replace('\x02', '')).strip()
            if plain == 'ENDNOTES':
                in_endnotes = True
                endnote_rows.append([x for x in rows if x['y1'] > r['y1']])
                break
            hd = _is_heading(r)
            if hd:
                started_body = True
                cur = {'num': hd[0], 'title': norm(hd[1]).strip(), 'kind': 'sec', 'paras': [], 'notes': [], 'raw': [], 'page': pno, 'hy': r['y1']}
                cur['notes'] += [n for _, n in r['sups']]
                units.append(cur)
                page_first = False
                continue
            if _is_structure(r) and (started_body or cur is None):
                if re.match(r'^(FIRST |SECOND |THIRD |FOURTH |FIFTH )?SCHEDULE', plain) or re.match(r'^SCHEDULE', plain):
                    started_body = True
                    cur = {'num': 'sch', 'title': plain, 'kind': 'schedule', 'paras': [], 'notes': [], 'raw': [], 'page': pno, 'hy': r['y1']}
                    cur['notes'] += [n for _, n in r['sups']]
                    units.append(cur)
                    continue
                if cur is not None and cur['kind'] == 'schedule':
                    cur['raw'].append((r, t, pno, page_first, True))
                    page_first = False
                    continue
                if started_body:
                    # a structure heading spans one or two lines; merge with the previous heading line when adjacent
                    if outline and outline[-1]['before'] is None and outline[-1]['y'] + 22 > r['y1'] and outline[-1]['page'] == pno:
                        outline[-1]['text'] += ' ' + plain
                        outline[-1]['y'] = r['y1']
                    else:
                        outline.append({'text': plain, 'before': None, 'y': r['y1'], 'page': pno})
                    continue
            if cur is None and re.match(r'^PART [IVXL0-9]+', plain) and all(x['bold'] for x in r['spans']):
                outline.append({'text': plain, 'before': None, 'y': r['y1'], 'page': pno})
                continue
            if cur is None:
                front.append((r, t, pno))
                continue
            cur['raw'].append((r, t, pno, page_first, False))
            cur['notes'] += [n for _, n in r['sups']]
            page_first = False
        # attach outline headings to the provision that follows
    # outline 'before': the first provision that starts after the heading (same page lower y, or a later page)
    for o in outline:
        for u in units:
            fy = u['raw'][0][0]['y1'] if u['raw'] else 0
            if u['page'] > o['page'] or (u['page'] == o['page'] and _head_y(u) > o['y']):
                o['before'] = u['num']
                break
    for u in units:
        u['paras'], u['inline'] = _paras(u['raw'], inline_notes)
        del u['raw']
    fr, _ = _paras([(r, t, p, False, False) for r, t, p in front])
    return {'units': units, 'outline': [(o['text'], o['before']) for o in outline], 'front': fr,
            'endnotes': _endnotes(endnote_rows)}


def _head_y(u):
    return u.get('hy', 0)


def _paras(raw, inline_notes=False):
    paras, notes = [], []
    prev = None
    for r, t, pno, page_first, struct in raw:
        first = r['spans'][0]['t'].strip()
        start = False
        if prev is None:
            start = True
        elif LABEL.match(first) or LABEL.match(norm(t.replace('\x01', '').replace('\x02', '')).strip()):
            start = True
        elif struct:
            start = True
        elif pno != prev[2]:
            last = paras[-1].rstrip() if paras else ''
            start = bool(re.search(r'[.:;]\s*\x02?$', last)) and bool(re.match(r'^[\x01]?[A-Z"\'(]', t.strip()))
        else:
            gap = r['y1'] - prev[0]['y1']
            start = gap > 1.3 * max(11, r['spans'][0]['size']) + 2
        line = t.strip()
        if start or not paras:
            paras.append(line)
        else:
            if paras[-1].endswith('-') and not paras[-1].endswith(' -'):
                paras[-1] += line
            else:
                paras[-1] += ' ' + line
        prev = (r, t, pno)
    out = []
    for p in paras:
        p = re.sub('\x02\\s*\x01', ' ', p)

        def cut(m):
            seg = m.group(1)

            def drop(mm):
                notes.append(norm(mm.group(0)))
                return ''
            seg = re.sub(r'\(\s*' + NOTE_WORDS + r'(?:[^()]|\([^()]*\))*\)\s*\.?', drop, seg)
            return seg
        p = re.sub('\x01([^\x02]*)\x02', cut, p)
        p = p.replace('\x01', '').replace('\x02', '')
        if inline_notes:
            def drop2(mm):
                notes.append(norm(mm.group(0)).strip())
                return ''
            p = re.sub(r'\s*\(\s*' + NOTE_WORDS + r'[^()]*\bof\s+\d{4}[^()]*\)\s*\.?\s*$', drop2, p)
        p = norm(p).strip()
        p = re.sub(r'^\((\w{1,5})\)\s*', r'(\1) ', p)
        p = re.sub(r'\s+([.,;:])$', r'\1', p)
        if p:
            out.append(p)
    return out, notes


def _endnotes(pages):
    """{n: text} from the endnote pages. An entry starts with its number: a small-type number row of its own,
    a superscript number, or a row beginning with the number; numbers run 1, 2, 3 ... in order."""
    notes, cur, pending = {}, None, None
    for rows in pages:
        for r in rows:
            t = norm(''.join(s['t'] for s in r['spans'])).strip()
            lead = [n for x, n in r['sups'] if x <= r['x'] + 1 and n.isdigit()]
            if lead:
                t = lead[0] + ' ' + t
            if not t or t == 'ENDNOTES':
                continue
            if re.fullmatch(r'\d{1,3}', t) and r['spans'][0]['size'] < 8:
                if cur is None and t == '1' or cur is not None and int(t) == cur + 1:
                    pending = int(t)
                    continue
            if pending is not None:
                cur, pending = pending, None
                notes[cur] = t
                continue
            m = re.match(r'^(\d{1,3})\s*(\D.*)$', t)
            if m and r['x'] < 90 and (cur is None and m.group(1) == '1' or cur is not None and int(m.group(1)) == cur + 1):
                cur = int(m.group(1))
                notes[cur] = m.group(2)
            elif cur is not None:
                notes[cur] += '\n' + t
    return notes
