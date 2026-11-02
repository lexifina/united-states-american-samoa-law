"""Parse one Kenya Gazette Supplement county Act PDF (Government Printer, text layer) into units.

    python -X utf8 parse.py <pdf>            # print meta and units

Private (gitlaw-scraper-dell, 2026-10-31). Layout of the supplements as posted by the county assemblies: a cover
("KENYA GAZETTE SUPPLEMENT ... <COUNTY> COUNTY ACTS, <year> / NAIROBI, <date>"), the Act's title, number, "Date of
Assent" and "Date of Commencement", the ARRANGEMENT OF SECTIONS, then the body from "AN ACT of the County Assembly".
Running heads ("No. 4", the short title, the year, the page number) sit at the top of each page. Section headings are
either bold rows above the section or small-type margin notes beside it. Nothing is reworded: rows are joined with
single spaces.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}
SCHED = re.compile(r'^(?:(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+)?SCHEDULES?\b')
LABEL = re.compile(r'^(\(([a-z]{1,4}|[0-9]{1,3}[A-Z]{0,2}|[ivxl]{1,6})\)|[“"‘\'])')


def norm(s: str) -> str:
    s = s.replace('\xa0', ' ').replace(' ', ' ').replace(' ', ' ').replace(' ', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def date_of(text: str) -> str | None:
    m = re.search(r'(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]+)\s*,?\s*(\d{4})', text or '')
    if not m or m.group(2).lower() not in MONTHS:
        return None
    d, mo, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
    return f'{y:04d}-{mo:02d}-{d:02d}' if 1 <= d <= 31 else None


def page_rows(page):
    """Rows of one page: lines at one height joined left to right. Returns (rows, notes): notes are small-type
    margin lines (size well under the body size, outside the body column)."""
    lines = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            if abs(l['dir'][1]) > 0.1:
                continue
            spans = [s for s in l['spans'] if s['text'].strip()]
            if not spans:
                continue
            # spans are joined with a space where the PDF leaves a gap between them ("1." "This" -> "1. This")
            parts = []
            for k, s in enumerate(spans):
                if k and s['bbox'][0] - spans[k - 1]['bbox'][2] > 1.0:
                    parts.append(' ')
                parts.append(s['text'])
            spans = [dict(spans[0], text=''.join(parts))] + [dict(s, text='') for s in spans[1:]]
            lines.append({'x0': l['bbox'][0], 'x1': l['bbox'][2], 'y0': l['bbox'][1], 'y1': l['bbox'][3],
                          'spans': spans, 'size': max(s['size'] for s in spans),
                          'bold': all(s['flags'] & 16 for s in spans)})
    return lines


def parse(path: Path) -> tuple[dict, dict]:
    doc = pymupdf.open(path)
    if len(doc) == 0:
        raise ValueError('empty PDF')
    if doc[0].rect.width > doc[0].rect.height or (len(doc) > 2 and doc[2].rect.width > doc[2].rect.height):
        raise ValueError('imposed booklet spreads')
    pages = [page_rows(p) for p in doc]
    front = '\n'.join(doc[i].get_text() for i in range(min(3, len(doc))))
    if 'KENYA GAZETTE SUPPLEMENT' not in front.upper():
        raise ValueError('not a Kenya Gazette Supplement')
    meta = {'pages': len(doc)}
    m = re.search(r'NAIROBI,\s*([^\n]+)', front)
    meta['gazette_date'] = date_of(m.group(1)) if m else None
    m = re.search(r'Kenya Gazette Supplement No\.\s*(\d+)\s*\(([^)]*)\)', front, re.I)
    meta['supplement'] = norm(m.group(0)) if m else None
    m = re.search(r'Date of Assent:?\s*([^\n]+)', front)
    meta['assent'] = date_of(m.group(1)) if m else None
    m = re.search(r'Date of Commencement:?\s*([^\n]+)', front)
    meta['commencement_text'] = norm(m.group(1)) if m else None
    meta['commencement'] = date_of(m.group(1)) if m else None
    m = re.search(r'Act\s*—\s*(?:PAGE\s*)?(.+?)\s*\.{3,}', front, re.S)
    meta['short_title'] = norm(m.group(1)) if m else None
    m = re.search(r'\bNo\.\s*(\d+)\s+of\s+(\d{4})', front)
    meta['number'] = f'No. {m.group(1)} of {m.group(2)}' if m else None
    if len(re.findall(r'Date of Assent', '\n'.join(p.get_text() for p in doc))) > 1:
        raise ValueError('more than one Act in the supplement')
    # body size: the commonest size over all rows
    sizes = Counter(round(l['size']) for pg in pages for l in pg)
    body_size = sizes.most_common(1)[0][0]
    # running heads: rows in the top 20% of a page that are a page number, "No. n", a year, or a text that repeats in
    # the top zone of several pages
    tops = Counter()
    for pg, p in zip(pages, doc):
        for l in pg:
            if l['y1'] < 0.2 * p.rect.height:
                tops[norm(''.join(s['text'] for s in l['spans']))] += 1
    furn_re = re.compile(r'^(No\.\s*\d+|\d{1,4}|\d{1,3}[A-Z]?)$')
    rows_all, aside, notes = [], [], []
    started = False
    title_rows: list[dict] = []
    for i, (pg, p) in enumerate(zip(pages, doc)):
        H, W = p.rect.height, p.rect.width
        pg.sort(key=lambda l: (round(l['y1']), l['x0']))
        body = []
        for l in pg:
            t = norm(''.join(s['text'] for s in l['spans']))
            if not t:
                continue
            if l['y1'] < 0.2 * H and (furn_re.match(t) or tops[t] >= 3):
                aside.append(t)
                continue
            if l['y0'] > 0.9 * H and (furn_re.match(t) or 'GOVERNMENT PRINTER' in t.upper()):
                aside.append(t)
                continue
            if 'PRINTED AND PUBLISHED BY THE GOVERNMENT PRINTER' in t.upper():
                aside.append(t)
                continue
            if l['size'] < body_size - 2.5:
                notes.append({'page': i, 'y0': l['y0'], 'y1': l['y1'], 'text': t})
                aside.append(t)
                continue
            body.append(dict(l, text=t, page=i))
        # join lines at one height into rows
        rows = []
        for l in body:
            if rows and abs(rows[-1]['y1'] - l['y1']) < 3.0:
                r = rows[-1]
                r['text'] = norm(r['text'] + ' ' + l['text']) if l['x0'] >= r['x1'] else norm(l['text'] + ' ' + r['text'])
                r['x0'], r['x1'] = min(r['x0'], l['x0']), max(r['x1'], l['x1'])
                r['bold'] = r['bold'] and l['bold']
            else:
                rows.append(dict(l))
        for r in rows:
            if not started:
                if re.match(r'^AN\s+ACT\b', r['text'], re.I):
                    started = True
                    meta['start_page'] = i
                    # the Act's title rows just above "AN ACT" on this page belong to the title unit
                    k = len(title_rows)
                    while k and title_rows[k - 1]['page'] == i and not re.match(r'^\d', title_rows[k - 1]['text']) \
                            and re.search(r'[A-Z]{3}', title_rows[k - 1]['text']) \
                            and title_rows[k - 1]['text'].upper() == title_rows[k - 1]['text']:
                        k -= 1
                    rows_all.extend(title_rows[k:])
                    if k < len(title_rows):
                        meta['start_page'] = title_rows[k]['page']
                else:
                    title_rows.append(r)
                    continue
            rows_all.append(r)
    if not started:
        raise ValueError('body start ("AN ACT") not found')
    meta['end_page'] = len(doc)
    # paragraphs and units
    units: dict[str, dict] = {}
    order: list[str] = []
    cur = None
    expect = 1
    in_sched = False
    nsched = 0
    pending: list[str] = []
    headings: list[str] = []
    title_lines: list[str] = []
    xs = Counter(round(r['x0']) for r in rows_all)
    left = min(x for x, n in xs.items() if n >= 3) if any(n >= 3 for n in xs.values()) else 0

    def open_unit(key, label, kind, first):
        nonlocal cur
        units[key] = {'label': label, 'kind': kind, 'lines': [f'# {label}'] + pending + [first]}
        headings.extend(pending)
        pending.clear()
        order.append(key)
        cur = key

    def note_for(r):
        got = [n['text'] for n in notes if n['page'] == r['page'] and n['y0'] >= r['y0'] - 14 and n['y0'] <= r['y1'] + 30
               and not n.get('used')]
        for n in notes:
            if n['text'] in got and n['page'] == r['page']:
                n['used'] = True
        return [norm(' '.join(got))] if got else []

    prev = None
    for r in rows_all:
        t = r['text']
        msec = re.match(r'^(\d{1,3})([A-Z]{0,2})\s*[.,](?!\d)', t)
        if not in_sched and msec and int(msec.group(1)) == expect and (cur is not None or expect == 1):
            pending.extend(note_for(r))
            num = msec.group(1) + msec.group(2)
            open_unit(f'sec-{int(msec.group(1)):03d}' + (f'-{msec.group(2).lower()}' if msec.group(2) else ''),
                      f'Section {num}', 'section', t)
            expect += 1
            prev = r
            continue
        if cur is not None and SCHED.match(t) and t.upper() == t:
            in_sched = True
            nsched += 1
            open_unit(f'sch-{nsched:02d}', t.title()[:60] if len(t) < 60 else f'Schedule {nsched}', 'schedule', t)
            prev = r
            continue
        heading = (not in_sched) and (r['bold'] and not LABEL.match(t)) or (not in_sched and re.match(r'^PART\s+[IVXL]+\b', t))
        if cur is None and not in_sched:
            if heading and title_lines and re.match(r'^ENACTED\b', title_lines[-1]):
                pending.append(t)  # a Part heading or the first section's heading after the enacting words
            elif title_lines and not re.match(r'^(AN\s+ACT|ENACTED)\b', t, re.I) and t.upper() != t \
                    and title_lines[-1].upper() != title_lines[-1] and not re.match(r'^ENACTED\b', title_lines[-1]):
                title_lines[-1] = norm(title_lines[-1] + ' ' + t)  # the long title runs on
            else:
                title_lines.append(t)
            prev = r
            continue
        if heading and not in_sched:
            pending.append(t)
            prev = r
            continue
        lines = units[cur]['lines']
        if pending:
            lines.extend(pending)
            headings.extend(pending)
            pending.clear()
            lines.append(t)
        else:
            new = (LABEL.match(t) is not None) or prev is None or re.match(r'^\d{1,3}\.\s', t) is not None \
                or (r['page'] == prev['page'] and r['y0'] - prev['y1'] > 3.5)
            if new or len(lines) <= 1:
                lines.append(t)
            else:
                lines[-1] = norm(lines[-1] + ' ' + t)
        prev = r
    if pending and cur is not None:
        units[cur]['lines'].extend(pending)
        headings.extend(pending)
    if expect == 1:
        raise ValueError('no section found')
    out = {'000-title': {'label': 'Title', 'kind': 'title', 'text': '# Title\n' + '\n'.join(title_lines) + '\n'}}
    for k in order:
        u = units[k]
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n'}
    meta.update(aside=aside, headings=headings, sections=expect - 1, title=title_lines[0] if title_lines else None,
                notes_unused=[n['text'] for n in notes if not n.get('used')])
    return out, meta


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    u, m = parse(Path(sys.argv[1]))
    print({k: v for k, v in m.items() if k not in ('aside', 'headings')})
    for k, v in u.items():
        print('==', k)
        print(v['text'])
