"""Reads one ZH-Lex PDF (Zürcher Loseblattsammlung) into articles, and its endnotes. Private (world-law-ops)."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def clean(s: str) -> str:
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace('­', '')
    return re.sub(r'\s+', ' ', s).strip()


def ascii_key(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def padnum(s: str) -> str:
    return re.sub(r'\d+', lambda m: m.group().zfill(3), s)


ART = re.compile(r'^\s*(Art\.|§)[\s ]*(\d+(?:[  ]?(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)(?![a-zäöü]))?(?:[  ]?[a-z](?![a-zäöü]))?)\.?')
BODY = 9.2


def _is_absnum(spans, i) -> bool:
    s = spans[i]
    if s['size'] >= 7:
        return False
    prev = ''.join(x['text'] for x in spans[:i])
    if prev.strip() and not prev.endswith((' ', ' ')):
        return False  # attached to the word before it: a note reference
    nxt = spans[i + 1]['text'] if i + 1 < len(spans) else ''
    return nxt.startswith(' ') and re.fullmatch(r'\d+[a-z]*', s['text'].strip() or 'x') is not None


def _page_lines(page):
    lines = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            sp = [s for s in l['spans'] if s['text']]
            if sp:
                lines.append(sp)
    return lines


def pdf_lines(path: Path) -> tuple[list[dict], dict]:
    """Body and margin lines in reading order, and the endnotes {number: text}."""
    import pymupdf
    doc = pymupdf.open(path)
    out, notes = [], {}
    cur_note = None
    for pn, page in enumerate(doc):
        lines = _page_lines(page)
        body_x = [s['bbox'][0] for sp in lines for s in sp if abs(s['size'] - BODY) < 0.3]
        left = min(body_x) if body_x else 54
        for sp in sorted(lines, key=lambda sp: (round(sp[0]['bbox'][1]), sp[0]['bbox'][0])):
            y, x = sp[0]['bbox'][1], sp[0]['bbox'][0]
            if y < 62 or y > 530:
                continue  # running head, page number, footer
            sizes = {round(s['size'], 1) for s in sp if s['text'].strip()}
            if not sizes:
                continue
            in_margin = x < left - 5 or x > left + 270
            first_sz = next((s['size'] for s in sp if s['text'].strip()), 9)
            # Endnotes: a number in 4.9 pt, text in 8 pt (they may sit anywhere on the page, even in the margin column)
            note_start = max(sizes) <= 8.05 and first_sz < 5.5
            note_cont = 7.9 <= max(sizes) <= 8.05
            if note_start or note_cont:
                t = ''.join(s['text'] for s in sp)
                m = re.match(r'\s*(\d+)(?:\s+(.*))?$', t, re.S) if note_start else None
                if m:
                    cur_note = int(m.group(1))
                    notes[cur_note] = m.group(2) or ''
                elif cur_note is None:
                    notes.setdefault(0, '')
                    notes[0] += ' ' + t  # small text before any note number: kept out of the law text
                else:
                    prev = notes[cur_note].rstrip(' ')
                    notes[cur_note] = (prev[:-1] if prev.endswith('­') else prev + ' ') + t
                continue
            if in_margin and max(sizes) < 8:
                out.append({'kind': 'margin', 'y': y, 'page': pn,
                            'text': ''.join(s['text'] for s in sp if s['size'] > 7),
                            'refs': [r for s in sp if s['size'] < 7 for r in re.findall(r'\d+', s['text'])]})
                continue
            cur_note = None
            refs, parts, bold = [], [], False
            for i, s in enumerate(sp):
                if s['size'] < 7 and not _is_absnum(sp, i):
                    refs += re.findall(r'\d+', s['text'])
                    continue
                if 'Bold' in s['font'] and s['text'].strip() and not clean(''.join(parts)):
                    bold = True
                parts.append(s['text'])
            first = next((i for i, s in enumerate(sp) if s['text'].strip()), 0)
            out.append({'kind': 'body', 'y': y, 'x': x, 'left': left, 'page': pn, 'text': ''.join(parts),
                        'bold': bold, 'size': max(sizes), 'refs': refs, 'abs': _is_absnum(sp, first)})
    # Margin titles are printed beside the line they belong to, often a point lower: attach each block of margin
    # lines (consecutive lines <= 10 pt apart) to the first body line of its page at or below the block's top.
    res, i = [], 0
    blocks = []
    for ln in out:
        if ln['kind'] == 'margin':
            if blocks and blocks[-1][-1]['page'] == ln['page'] and ln['y'] - blocks[-1][-1]['y'] <= 10.5:
                blocks[-1].append(ln)
            else:
                blocks.append([ln])
    body = [ln for ln in out if ln['kind'] == 'body']
    for ln in body:
        ln['margin'] = []
    for bl in blocks:
        tgt = next((ln for ln in body if ln['page'] == bl[0]['page'] and ln['y'] >= bl[0]['y'] - 4), None)
        if tgt is None:
            tgt = next((ln for ln in body if ln['page'] > bl[0]['page']), None)
        if tgt is not None:
            t = ''
            for mb in bl:
                t = _join(t, mb['text']) if t else mb['text']
            tgt['margin'].append(t)
            tgt['refs'] = tgt['refs'] + [r for mb in bl for r in mb.get('refs', [])]
    return body, {k: clean(v) for k, v in notes.items()}


def _join(a: str, b: str) -> str:
    a = a.rstrip(' ')
    b = b.lstrip()
    if a.endswith('­'):
        return a[:-1] + b
    if a.endswith('-') and b[:1].isupper():
        return a + b
    return a + ' ' + b


def parse_pdf(path: Path) -> tuple[dict, dict]:
    """-> ({unit key: unit}, {'refs': {unit key: [endnote numbers]}, 'notes': {n: text}})."""
    lines, notes = pdf_lines(path)
    units: dict[str, dict] = {}
    refs: dict[str, list[str]] = {}
    order: list[str] = []
    ingress: list[str] = []
    outline: list[str] = []
    st = {'cur': None, 'para': None}
    seen_art = False
    pending_heading = None
    margin_buf: list[dict] = []

    def flush():
        if st['para'] is not None:
            t = clean(st['para'])
            if t:
                (units[st['cur']]['lines'] if st['cur'] else ingress).append(t)
        st['para'] = None

    def new_unit(key, label, first):
        base, i = key, 2
        while key in units:
            key = f'{base}-{i}'
            i += 1
        units[key] = {'label': label, 'lines': [first]}
        refs[key] = []
        order.append(key)
        st['cur'] = key
        return key

    ITEM = re.compile(r'^\s*(?:[a-z]{1,2}|\d{1,2}|[ivx]{1,5})\.(?:\s|$)|^\s*[–-]\s')
    for ln in lines:
        t = ln['text']
        m = ART.match(t) if ln['bold'] or re.match(r'\s*§ \d', t) else None
        if m:
            flush()
            seen_art = True
            label = clean(m.group(1) + ' ' + m.group(2))
            ttxt = ' '.join(ln['margin'])
            key = new_unit('art-' + padnum(ascii_key(re.sub(r'[\s ]+', '', m.group(2)))), label, '# ' + clean(label + ' ' + ttxt))
            refs[key] += ln['refs']
            pending_heading = None
            body = t[m.end():]
            st['para'] = body if clean(body) else None
            continue
        if ln['margin'] and st['cur']:  # a margin title beside a paragraph: a sub-title in the article
            flush()
            units[st['cur']]['lines'] += [clean(x) for x in ln['margin']]
        elif ln['margin'] and seen_art:  # beside a heading: part of the outline
            outline.extend(clean(x) for x in ln['margin'])
        if ln['bold'] or ln['size'] >= 11:
            flush()
            if not seen_art and (ln['size'] >= 11 or re.match(r'\s*Präambel', t) or not outline and not ingress):
                if ingress and ln['size'] >= 11 and ingress[-1].startswith('# '):
                    ingress[-1] = '# ' + clean(ingress[-1][2:] + ' ' + t)
                else:
                    ingress.append(('# ' if ln['size'] >= 11 else '') + clean(t))
                continue
            outline.append('## ' + clean(t))
            pending_heading = clean(t)
            st['cur'] = None
            continue
        if st['cur'] is None and (seen_art or outline):
            h = pending_heading or 'Text'
            if pending_heading and outline and outline[-1] == '## ' + pending_heading:
                outline.pop()
            new_unit('abschnitt-' + (ascii_key(h)[:50] or 'text'), h[:80], '# ' + h)
        if ln['margin'] and not st['cur']:
            ingress.extend(clean(x) for x in ln['margin'])
        refs.setdefault(st['cur'] or 'ingress', []).extend(ln['refs'])
        if st['para'] is None or ln['abs'] or ITEM.match(t.replace(' ', ' ')):
            flush()
            st['para'] = t
        else:
            st['para'] = _join(st['para'], t)
    flush()
    out = {}
    if ingress:
        out['ingress'] = {'label': 'Titel und Ingress', 'kind': 'preamble', 'text': '\n'.join(ingress) + '\n'}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': '\n'.join(units[k]['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Gliederung', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    return out, {'refs': refs, 'notes': notes}


def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


def source_letters(path: Path) -> str:
    """Letters and digits of the PDF read span by span (not through parse_pdf's line logic): every span of body and
    margin size, plus paragraph numbers; not running heads, page footers, endnotes or note references."""
    import pymupdf
    out = []
    for page in pymupdf.open(path):
        for sp in _page_lines(page):
            for i, s in enumerate(sp):
                y = s['bbox'][1]
                if y < 62 or y > 530:
                    continue
                if s['size'] >= 7.2 and not 7.85 <= s['size'] <= 8.05:
                    out.append(s['text'])
                elif s['size'] < 7 and _is_absnum(sp, i):
                    out.append(s['text'])
    return letters(''.join(out))
