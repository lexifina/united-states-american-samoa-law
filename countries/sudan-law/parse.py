"""Parse Sudan's cached sources into corpus.json (gitlaw_common/SCHEMA.md). Reads only .cache/; no network.

    python -X utf8 scripts/sudan-law/parse.py

Source: the Ministry of Justice ebook "قوانين السودان" (the 9th Revised Edition of the Laws of Sudan, laws in force to
30 March 2015), served unpacked at https://www.moj.gov.sd/sudanlaws/epub/EPUB/. Each act is one XHTML chapter.

The chapters came from a print layout: the marginal note (the section heading) sits in the right margin, so in the
XHTML it is run into the first line of the article and, when it wraps, into the next lines, separated from the text
by a run of spaces. parse.py takes the article number as the anchor (the next number in sequence), puts the marginal
note into the heading line, and keeps every other source paragraph as one line of the unit.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
EPUB = 'https://www.moj.gov.sd/sudanlaws/epub/EPUB/'
RETRIEVED = '2026-10-28'
EDITION_DATE = '2015-03-30'

AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def cached(url: str) -> bytes:
    return (CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()).read_bytes()


def norm(s: str) -> str:
    s = s.replace('\u00a0', ' ').replace('\u200f', '').replace('\u200e', '').replace('\u200b', '')
    s = s.translate(AR_DIGITS)
    s = s.replace('“', '"').replace('”', '"').replace('„', '"')
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


FN_REF = re.compile(r'<sup>\s*<a href="#[^"]*footnote-\d+"[^>]*>\[(\d+)\]</a>\s*</sup>\s*(\(\s*\d+\s*\)|\*+)?')


def blocks(src: str):
    """Yield (tag, style, raw_text_with_spaces, footnote_numbers) for each block element of the body."""
    src = re.sub(r'(?s)<head>.*?</head>', '', src)
    src = re.sub(r'(?s)<ol>\s*<li id="[^"]*footnote.*', '', src)          # the footnote list at the end
    for m in re.finditer(r'(?s)<(p|h[1-6]|tr)(\s[^>]*)?>(.*?)</\1>', src):
        tag, attrs, inner = m.group(1), m.group(2) or '', m.group(3)
        style = re.search(r'style="([^"]*)"', attrs)
        fns = [int(x) for x in re.findall(r'footnote-ref-(\d+)"', inner)]
        inner = FN_REF.sub(' ', inner)
        # fractions in the diya schedule: numerator is <sub><u> n </u></sub>; the denominator is the next paragraph
        inner = re.sub(r'(?s)<sub>\s*<u>\s*(\d+)\s*</u>\s*</sub>', r'\1/⟨d⟩', inner)
        if tag == 'tr':
            cells = [re.sub(r'<[^>]+>', ' ', c) for c in re.findall(r'(?s)<td[^>]*>(.*?)</td>', inner)]
            text = ' | '.join(html.unescape(c).replace('\u00a0', ' ').strip() for c in cells)
        else:
            if '<tr' in inner or '<td' in inner:
                continue
            text = html.unescape(re.sub(r'<br\s*/?>', ' ', inner))
            text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('\u00a0', ' ').translate(AR_DIGITS)
        yield tag, style.group(1) if style else '', text, fns


def footnotes(src: str) -> dict[int, str]:
    out = {}
    for m in re.finditer(r'(?s)<li id="[^"]*footnote-(\d+)">(.*?)</li>', src):
        t = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).replace('↑', '')
        out[int(m.group(1))] = norm(t)
    return out


ORD = {'الأول': 1, 'الاول': 1, 'الثاني': 2, 'الثانى': 2, 'الثالث': 3, 'الرابع': 4, 'الخامس': 5, 'السادس': 6,
       'السابع': 7, 'الثامن': 8, 'التاسع': 9, 'العاشر': 10, 'الحادي عشر': 11, 'الثاني عشر': 12, 'الثالث عشر': 13,
       'الرابع عشر': 14, 'الخامس عشر': 15, 'السادس عشر': 16, 'السابع عشر': 17, 'الثامن عشر': 18,
       'التاسع عشر': 19, 'العشرون': 20, 'الحادي والعشرون': 21, 'الثاني والعشرون': 22}
SEP = r'\s*[-ـ–]+\s*'


def parse_act(url: str, body_marker: str, expect_last: int):
    raw = cached(url).decode('utf-8')
    fn_text = footnotes(raw)
    start = raw.find(body_marker)
    if start < 0:
        raise SystemExit(f'body marker {body_marker!r} not found in {url}')
    start = raw.rfind('<', 0, start)
    blks = list(blocks(raw[:0] + '<body>' + raw[start:]))
    units: dict[str, dict] = {}
    order: list[str] = []
    cur = None            # current unit dict
    head_open = False     # marginal note still wrapping
    last = 0
    part = chap = 0
    sched = 0
    pending_heads: list[str] = []
    problems: list[str] = []
    unit_fns: dict[str, list[int]] = {}

    def new_unit(key, label, kind, lines):
        nonlocal cur
        cur = {'label': label, 'kind': kind, 'lines': lines}
        if key in units:
            problems.append(f'duplicate key {key}')
            key = key + '-dup'
        units[key] = cur
        order.append(key)
        unit_fns[key] = []
        return key

    key = None
    i = 0
    while i < len(blks):
        tag, style, text, fns = blks[i]
        i += 1
        t = norm(text)
        if not t or t in ('بسم الله الرحمن الرحيم',):
            continue
        if '⟨d⟩' in t or (cur and cur['lines'] and '⟨d⟩' in cur['lines'][-1] and re.fullmatch(r'[\d ]+', t)):
            pass
        # a paragraph that is only a denominator (or several) for the fractions above
        if re.fullmatch(r'\d+( \d+)*', t) and cur and cur['lines'] and '⟨d⟩' in cur['lines'][-1]:
            dens = t.split()
            line = cur['lines'][-1]
            for d in dens:
                line = line.replace('⟨d⟩', d, 1)
            cur['lines'][-1] = line
            continue
        centered = 'text-align: center' in style or tag.startswith('h')
        mpart = re.match(r'^الباب\s+(.+)$', t)
        mchap = re.match(r'^الفصل\s+(.+)$', t)
        msched = re.match(r'^الجدول\s+(.+)$', t)
        if mpart and len(t) < 40 and last < expect_last:
            part += 1
            chap = 0
            key = new_unit(f'part-{part:02d}', t, 'part', [t])
            head_open = False
            cur['heading'] = True
            continue
        if mchap and len(t) < 40 and last < expect_last:
            chap += 1
            key = new_unit(f'part-{part:02d}-chapter-{chap:02d}', t, 'chapter', [t])
            head_open = False
            cur['heading'] = True
            continue
        if msched and len(t) < 80 and last >= expect_last:
            sched += 1
            key = new_unit(f'schedule-{sched:02d}', t, 'schedule', [t])
            head_open = False
            continue
        # the next article?
        nxt = last + 1
        m = None
        if last < expect_last:
            m = re.match(rf'^(?P<head>(?:(?!\d).)*?)\s*(?P<num>{nxt})(?P<suf>\s*[أ-ي])?{SEP}(?P<rest>.*)$', t)
            if not m and last:
                m = re.match(rf'^(?P<head>(?:(?!\d).)*?)\s*(?P<num>{last})\s*(?P<suf>[أ-ي]|مكرر[اًة]?)\s*{SEP}(?P<rest>.*)$', t)
        if m:
            num = int(m.group('num'))
            suf = (m.group('suf') or '').strip()
            head = m.group('head').strip()
            last = num
            sk = {'أ': 'a', 'ب': 'b', 'ج': 'c', 'د': 'd'}.get(suf, 'bis' if suf else '')
            k = f'art-{num:03d}' + (f'-{sk}' if sk else '')
            key = new_unit(k, f'المادة {num}{suf}', 'art', [])
            cur['num'] = f'{num}{suf}'
            cur['head'] = head
            head_open = bool(head) and not head.rstrip().endswith('.')
            rest = m.group('rest').strip()
            if rest:
                cur['lines'].append(rest)
            unit_fns[key] += fns
            continue
        if cur is None:
            continue
        if cur.get('heading') and centered and len(t) < 80:
            cur['lines'].append(t)        # the title line of a part or chapter
            cur['label'] = cur['label'] + ': ' + t if ':' not in cur['label'] else cur['label']
            continue
        if cur['kind'] == 'art' and head_open and not style:
            raw_t = re.sub(r'\s', ' ', text).strip()
            mm = re.match(r'^(\S(?:.*?\S)?)\s{3,}(.+)$', raw_t)
            if mm and len(norm(mm.group(1))) <= 45:
                cur['head'] = (cur['head'] + ' ' + norm(mm.group(1))).strip()
                t = norm(mm.group(2))
            elif len(t) <= 30 and t.endswith('.'):
                cur['head'] = (cur['head'] + ' ' + t).strip()
                t = ''
            head_open = not cur['head'].endswith('.')
        if cur.get('heading'):
            problems.append(f'text after heading {key}: {t[:60]}')
            cur.pop('heading', None)
        if t:
            cur['lines'].append(t)
        if key:
            unit_fns[key] += fns
    if last != expect_last:
        problems.append(f'last article {last}, expected {expect_last}')
    out = {}
    for k in order:
        u = units[k]
        lines = list(u['lines'])
        if u['kind'] == 'art':
            h = f"# المادة {u['num']}" + (f" — {u['head']}" if u['head'] else '')
            lines = [h] + lines
        else:
            lines = ['# ' + lines[0]] + lines[1:]
        text = '\n'.join(re.sub(r'\s+([،,.؛:])', r'\1', l) for l in lines) + '\n'
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': text}
    notes = {k: [fn_text[n] for n in v if n in fn_text] for k, v in unit_fns.items() if v}
    return out, notes, problems


ACTS = [
    {'slug': 'criminal-act-1991', 'short': 'CA 1991', 'file': 's53c19', 'title': 'القانون الجنائي لسنة 1991',
     'marker': '(31/1/1991)', 'last': 185},
    {'slug': 'civil-transactions-act-1984', 'short': 'CTA 1984', 'file': 'sr6vg1',
     'title': 'قانون المعاملات المدنية لسنة 1984', 'marker': '(14/2/1984)', 'last': 819},
]


def main() -> None:
    report = {}
    acts = []
    for a in ACTS:
        url = f"{EPUB}xhtml/{a['file']}.html"
        units, notes, problems = parse_act(url, a['marker'], a['last'])
        report[a['slug']] = {'units': len(units), 'problems': problems, 'notes': notes}
        acts.append((a, url, units))
    (CACHE / 'parse-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    for s, r in report.items():
        print(s, r['units'], 'problems', len(r['problems']))
        for p in r['problems'][:20]:
            print('  ', p)
    if '--dry' in sys.argv:
        return
    write_corpus(acts, report)


def write_corpus(acts, report) -> None:
    from corpus_meta import build
    corpus = build(acts, report, cached)
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('corpus.json written:', sum(len(a['versions'][0]['units']) for a in corpus['acts']), 'units')


if __name__ == '__main__':
    main()
