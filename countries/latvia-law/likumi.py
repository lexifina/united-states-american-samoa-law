"""Read one likumi.lv version page ("redakcija") into units and amendment notes. No network.

A page's text sits in div.doc-body as a flat run of blocks: TV206/TV207 (the act's title), TV208 (preamble),
TV211/TV212 (part and chapter headings), TV213 (articles, data-num="18" or "10.1"), TV216 (signatures), and the
transitional provisions and EU-directive references at the end. Each changed block carries a note,
p.labojumu_pamats: "(30.04.2002. likuma redakcijā, kas stājas spēkā 05.11.2002.)" with a link to the amending law
(/ta/id/<id>-<slug>) and to the version it starts (/redakcijas-datums/YYYY/MM/DD). Notes are not law text: they are
taken out and used only to date and credit changes.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
HIDDEN = ('panta-doc-npk', 'info-icon-wrapper', 'labojumu_pamats', 'tooltip', 'helper', 'court', 'panta-piezimite')
SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')
BLOCK = {'p', 'div', 'br', 'li', 'tr', 'table', 'center', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'blockquote'}


def roman(s: str) -> int | None:
    if not s or any(c not in ROMAN for c in s):
        return None
    n = 0
    for a, b in zip(s, s[1:] + ' '):
        v = ROMAN[a]
        n += -v if b in ROMAN and ROMAN[b] > v else v
    return n


def norm(s: str) -> str:
    s = s.replace('\xa0', ' ').replace(' ', ' ').replace(' ', ' ')
    for z in ('​', '﻿', '⁠', '\xad'):
        s = s.replace(z, '')
    for q in ('“', '”', '„', '‟', '″'):
        s = s.replace(q, '"')
    s = s.replace('‘', "'").replace('’', "'").replace('‚', "'")
    s = s.replace('–', '-').replace('—', '-')
    s = re.sub(r'[ \t\r\n]+', ' ', s).strip()
    s = re.sub(r' ([,;:.)])', r'\1', s)
    s = re.sub(r'\( ', '(', s)
    return s


def hidden(el: Tag) -> bool:
    cls = el.get('class') or []
    if any(c in HIDDEN for c in cls):
        return True
    st = (el.get('style') or '').replace(' ', '').lower()
    return 'display:none' in st


def lines_of(el: Tag) -> list[str]:
    """One line per paragraph (block element or <br>); superscript numbers (70.<sup>11</sup>) become Unicode
    superscript digits (70.¹¹), as printed."""
    out, buf = [], []

    def flush():
        t = norm(''.join(buf))
        if t:
            out.append(t)
        buf.clear()

    def walk(n):
        for c in n.children:
            if isinstance(c, NavigableString):
                if c.__class__.__name__ in ('Comment', 'Script', 'Stylesheet'):
                    continue
                buf.append(str(c))
            elif isinstance(c, Tag):
                if c.name in ('script', 'style') or hidden(c):
                    continue
                if c.name == 'br':
                    flush()
                    continue
                if c.name == 'sup':
                    buf.append(c.get_text().translate(SUP))
                    continue
                blk = c.name in BLOCK
                if blk:
                    flush()
                walk(c)
                if blk:
                    flush()
    walk(el)
    flush()
    return out


DATE = re.compile(r'(\d\d)\.(\d\d)\.(\d{4})')


def iso(d: str) -> str | None:
    m = DATE.search(d)
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None


def note_events(p: Tag, own_id: int) -> list[dict]:
    """[{law_id, law_slug, law_date, in_force, court}] from one note, in order. A version link closes the laws
    named since the previous one."""
    events, pending = [], []
    for a in p.find_all('a'):
        href = a.get('href') or ''
        m = re.search(r'/ta/id/(\d+)(?:-([a-z0-9-]+))?(?:/redakcijas-datums/(\d{4})/(\d\d)/(\d\d))?', href)
        if not m:
            continue
        lid = int(m.group(1))
        if m.group(3):
            day = f'{m.group(3)}-{m.group(4)}-{m.group(5)}'
            # "ar A., B. un C. likumu, kas stājas spēkā D": D is C's day only; A and B stay undated here
            for j, e in enumerate(pending):
                e['in_force'] = day if j == len(pending) - 1 else None
                events.append(e)
            if not pending and events:
                # a second day for the same law: "... stājas spēkā 01.10.2011. Grozījums ... stājas spēkā 01.01.2015."
                events.append({**events[-1], 'in_force': day})
            pending = []
            continue
        if lid == own_id:
            continue
        # text just before the link tells a court ruling from a law
        prev = ''
        for s in a.previous_siblings:
            prev = (s.get_text() if isinstance(s, Tag) else str(s)) + prev
            if len(prev) > 80:
                break
        pending.append({'law_id': lid, 'law_slug': m.group(2) or '', 'law_date': iso(a.get_text()),
                        'court': 'Satversmes tiesas' in prev[-80:] or 'spriedum' in (m.group(2) or '')})
    for e in pending:
        e['in_force'] = None
        events.append(e)
    if not any(e['law_id'] for e in events):
        # some captures print the amending laws' dates without links: "ar 12.06.2003., ... un 17.12.2020. likumu, kas
        # stājas spēkā 01.01.2022."; the law is found later from its date (parse.py, resolve_law_ids)
        events = []
        txt = p.get_text(' ').replace(' ', ' ')
        for m in re.finditer(r'((?:\d\d\.\d\d\.\d{4}\.?\s*(?:,|un)?\s*)+)\.?\s*likum\w*,?\s*kas stājas spēkā\s+(\d\d\.\d\d\.\d{4})', txt):
            ds = re.findall(r'\d\d\.\d\d\.\d{4}', m.group(1))
            for j, d in enumerate(ds):
                events.append({'law_id': None, 'law_slug': '', 'law_date': iso(d), 'court': False,
                               'in_force': iso(m.group(2)) if j == len(ds) - 1 else None})
    # a later in-force day given only in words: "Grozījums par panta izslēgšanu stājas spēkā 01.01.2015." belongs to
    # the last law the note names
    linked = {iso(a.get_text()) for a in p.find_all('a')}
    laws = [e for e in events]
    for m in re.finditer(r'stājas spēkā\s+(\d\d\.\d\d\.\d{4})', p.get_text(' ')):
        d = iso(m.group(1))
        if d and d not in linked and laws:
            events.append({**laws[-1], 'in_force': d, 'text_date': True})
    return events


def heading_key(text: str, used: set) -> str:
    t = text.strip()
    m = re.match(r'^([IVXLC]+)\.?\s*(\d*)\.?\s*nodaļa', t, re.I)
    if m and roman(m.group(1).upper()):
        k = f'nodala-{roman(m.group(1).upper()):02d}' + (f'-{m.group(2)}' if m.group(2) else '')
    else:
        m2 = re.match(r'^(\d+)\.\s*(\d*)\.?\s*nodaļa', t)
        if m2:
            k = f'nodala-{int(m2.group(1)):02d}' + (f'-{m2.group(2)}' if m2.group(2) else '')
        else:
            low = t.lower()
            if low.startswith('vispārējā daļa') or low.startswith('vispārīgā daļa'):
                k = 'dala-1-vispariga'
            elif low.startswith('sevišķā daļa'):
                k = 'dala-2-seviska'
            elif low.startswith('pārejas noteikumi'):
                k = 'parejas-noteikumi'
            elif low.startswith('informatīva atsauce'):
                k = 'zz-es-direktivas'
            else:
                k = 'virsraksts-' + re.sub(r'[^a-z0-9]+', '-', ascii_fold(low))[:40].strip('-')
    k = ascii_fold(k)
    base, i = k, 2
    while k in used:
        k = f'{base}-{i}'
        i += 1
    return k


FOLD = str.maketrans('āčēģīķļņōŗšūžĀČĒĢĪĶĻŅŌŖŠŪŽ', 'acegiklnorsuzACEGIKLNORSUZ')


def ascii_fold(s: str) -> str:
    return s.translate(FOLD)


def art_key(num: str, prefix: str = 'pants') -> str:
    parts = [x for x in re.split(r'[._]', num) if x]
    return f'{prefix}-' + '-'.join([f'{int(parts[0]):03d}'] + parts[1:])


def parse_page(raw: bytes, own_id: int) -> dict:
    """{'version': 'YYYY-MM-DD', 'units': {key: {label, kind, text, events, parent}}, 'removed': {key: events}}"""
    html = raw.decode('utf-8', 'replace')
    soup = BeautifulSoup(html, 'lxml')
    body = soup.select_one('div.doc-body')
    ver = re.search(r'\{"selected":\{"value":"(\d\d)\.(\d\d)\.(\d{4})"', html)
    out = {'version': f'{ver.group(3)}-{ver.group(2)}-{ver.group(1)}' if ver else None, 'units': {}, 'removed': {},
           'order': []}
    used: set = set()
    parent = None
    seen_heading = False
    es = False
    dup = False
    for blk in body.find_all(recursive=False):
        cls = blk.get('class') or []
        if not any(c.startswith('TV') for c in cls):
            continue
        tv = next(c for c in cls if c.startswith('TV'))
        events = []
        izsl = []
        for p in blk.find_all('p', class_='labojumu_pamats'):
            ev = note_events(p, own_id)
            events += ev
            if p.get_text().strip().startswith('(Izslēgts') or p.get_text().strip().startswith('(Izslēgta'):
                izsl += ev
        lines = lines_of(blk)
        if not lines:
            continue
        if tv in ('TV206', 'TV207'):
            continue
        num = re.sub(r'[^0-9._]', '', blk.get('data-num') or '') or None
        pfx = blk.get('data-pfx') or ''
        if tv == 'TV213' and not num:
            # older likumi.lv markup (captures before about 2016): the number is only in the anchor, p12 / pn3
            for a in blk.find_all('a'):
                m = re.fullmatch(r'(pn|p)(\d+(?:[._]\d+)*)', a.get('name') or '')
                if m:
                    pfx, num = m.group(1), m.group(2)
                    break
        if tv == 'TV213' and num and pfx == 'pn':
            key, kind = art_key(num, 'parejas-noteikumi'), 'transitional'
            label = f'Pārejas noteikumu {num.replace("_", ".")}. punkts'
        elif tv == 'TV213' and num:
            key, kind = art_key(num), 'art'
            label = f'{num.replace("_", ".")}. pants'
        elif tv == 'TV208' and es:
            key, kind, label = 'zz-es-direktivas-teksts', 'eu-note', 'Informatīva atsauce uz ES direktīvām (teksts)'
        elif tv == 'TV208' and not seen_heading:
            key, kind, label = 'ievads', 'preamble', 'Ievads'
        elif tv == 'TV215':
            key, kind, label = 'zz-pienemts', 'enactment', 'Pieņemšanas ziņas'
        elif tv == 'TV216':
            key, kind, label = 'zz-paraksti', 'signatures', 'Paraksti'
        elif tv == 'TV217':
            key, kind, label = 'zz-vieta-datums', 'enactment', 'Izsludināšanas vieta un datums'
        elif tv == 'TV403' or (not num and lines[0].lower().startswith('informatīva atsauce')):
            key, kind, label = 'zz-es-direktivas', 'heading', lines[0]
            es = True
            parent = key
        elif not num and tv in ('TV209', 'TV210', 'TV211', 'TV212', 'TV214'):
            seen_heading = True
            key = heading_key(lines[0], used)
            kind, label = 'heading', lines[0]
            parent = key
        elif tv == 'TV430':
            continue  # likumi.lv's editorial "PIEZĪMES" (amending laws' own transitional clauses): not this act's text
        else:
            key = f'zz-bloks-{tv.lower()}-{len(out["order"]) + 1:03d}'
            kind, label = 'other', tv
        if kind == 'heading' and key.startswith('parejas-noteikumi-'):
            dup = True  # older pages repeat the whole transitional section once more; the copy is skipped
            continue
        if kind == 'heading':
            dup = False
        if dup and kind == 'transitional':
            if key in out['units'] and out['units'][key]['text'] != chr(10).join(lines) + chr(10):
                out.setdefault('dup_differs', []).append(key)
            continue
        if key in used and kind != 'heading':
            base, i = key, 2
            while key in used:
                key = f'{base}-{i}'
                i += 1
        used.add(key)
        text_lines = [l for l in lines]
        whole = ' '.join(text_lines)
        gone = None
        if kind in ('art', 'transitional') and re.fullmatch(
                r'[\d.⁰¹²³⁴⁵⁶⁷⁸⁹]*\s*(?:pants\.?)?\s*\((?:Punkts|Pants|Daļa|Nodaļa|Apakšpunkts)[^()]*stājas spēkā[^()]*iekļauts likuma '
                r'redakcijā uz[^()]*\)\.?', whole):
            continue  # "(Punkts stājas spēkā 01.01.2022. un iekļauts likuma redakcijā uz 01.01.2022. ...)": not yet in force
        if kind in ('art', 'transitional'):
            if re.fullmatch(r'[\d.⁰¹²³⁴⁵⁶⁷⁸⁹]*\s*(?:pants\.?)?\s*\(Izslēgt[sa][^)]*\)\.?', whole):
                for a_p in blk.find_all(['span', 'p']):
                    if 'Izslēgt' in a_p.get_text() and 'labojumu_pamats' not in (a_p.get('class') or []):
                        gone = note_events(a_p, own_id)
                        break
                gone = gone or events
            elif izsl and len(text_lines) == 1:
                gone = izsl
        if gone is not None:
            out['removed'][key] = {'label': label, 'events': gone}
            out['order'].append(key)
            continue
        out['units'][key] = {'label': label, 'kind': kind, 'text': '\n'.join(text_lines) + '\n', 'events': events,
                             'parent': parent if kind != 'heading' else None}
        out['order'].append(key)
    return out
