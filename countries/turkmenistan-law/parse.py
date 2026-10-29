"""Parse the cached official Turkmen texts into corpus.json (scripts/gitlaw_common/SCHEMA.md).

Reads only .cache/ (no network). Deterministic: the same cache gives the same bytes.

    python -X utf8 scripts/turkmenistan-law/parse.py
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
RETRIEVED = '2026-10-28'


def url_bytes(url: str) -> tuple[bytes, str]:
    b = (CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()).read_bytes()
    return b, hashlib.sha256(b).hexdigest()


def cc_bytes(rec: dict) -> tuple[bytes, str]:
    key = f'cc:{rec["filename"]}:{rec["offset"]}:{rec["length"]}'
    b = (CACHE / hashlib.sha256(key.encode('utf-8')).hexdigest()).read_bytes()
    return b, hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- HTML to paragraphs

BLOCK = re.compile(r'</p>|<br\s*/?>|</h\d>|</li>|</div>|</tr>', re.I)


def norm(s: str) -> str:
    s = html.unescape(s)
    s = s.replace('\xa0', ' ').replace('​', '').replace('﻿', '')
    s = s.replace('“', '«').replace('”', '»').replace('„', '«')
    s = s.replace('—', '–').replace(' - ', ' – ')
    s = re.sub(r'[ \t\r\f\v]+', ' ', s)
    s = re.sub(r' ([.,;:)])', r'\1', s)
    s = re.sub(r'\( ', '(', s)
    return s.strip()


def paragraphs(page: str) -> list[tuple[str, bool]]:
    """The text block of a Mejlis page as (text, all_bold) paragraphs, empty ones dropped."""
    a = page.find('class="text_block"')
    b = page.find('<footer', a)
    body = page[a:b]
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', body, flags=re.S | re.I)
    out = []
    for chunk in BLOCK.split(body):
        raw = chunk
        text = norm(re.sub(r'<[^>]+>', '', raw))
        if not text or text == 'text_block">':
            continue
        text = text.replace('text_block">', '').strip()
        if not text:
            continue
        # bold: every visible character sits inside <strong>/<b>
        unbold = re.sub(r'<(strong|b)\b[^>]*>.*?</\1>', '', raw, flags=re.S | re.I)
        all_bold = not norm(re.sub(r'<[^>]+>', '', unbold)).strip(' .')
        # does the paragraph open in bold (article headings: "<strong>5-nji madda</strong>. Text")?
        lead = re.sub(r'^(?:\s|<(?!strong|b)[^>]+>)*', '', raw)
        opens_bold = bool(re.match(r'<(strong|b)', lead, re.I))
        out.append((text, all_bold or opens_bold))
    return out


# ---------------------------------------------------------------- units

ART = re.compile(r'^(\d+)\s*-?\s*(?:nji|njy|nij|inji|ynjy|unjy|njі)\s+madda\s*\.?\s*(.*)$', re.I)
HEAD = re.compile(r'^(?:[IVXLCІ]+\s+(?:BÖLEK|BÖLÜM|BAP)\b|(?:UMUMY|ÝÖRITE|AÝRATYN)\s+BÖLEK\b|\d+\s*-?\s*n[jy][iy]\s+(?:BAP|BÖLÜM)\b)')


def key_of(num: str) -> str:
    parts = num.split('-')
    return 'art-' + '-'.join(p.zfill(3) if i == 0 else p for i, p in enumerate(parts))


def label_of(num: str) -> str:
    parts = num.split('-')
    sup = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')
    return parts[0] + (parts[1].translate(sup) if len(parts) > 1 else '') + '-nji madda'


def split_units(paras: list[tuple[str, bool]], bold_articles: bool = True, titled: bool = True,
                preamble: list[str] | None = None) -> tuple[dict, list[str]]:
    """Article units (+ a preamble unit and a headings unit). Returns (units, decisions)."""
    notes = []
    # first pass: candidate article starts
    starts = []
    for i, (t, bold) in enumerate(paras):
        m = ART.match(t)
        if m and (bold or not bold_articles):
            starts.append(i)
    nums = [int(ART.match(paras[i][0]).group(1)) for i in starts]
    # publisher flattens superscripts: "61-njy madda" between 6 and 7 is article 6¹
    labels = []
    prev = 0
    for k, n in enumerate(nums):
        nxt = nums[k + 1] if k + 1 < len(nums) else None
        s = str(n)
        base = None
        if n > prev + 1 and prev and s.startswith(str(prev)) and nxt == prev + 1:
            base = prev
        elif n > prev + 1 and prev and nxt is not None and nxt == prev + 1:
            # e.g. 6¹ after an earlier 6¹ (6, 61, 62, 7): prev is itself a sub-number
            pass
        if base is not None:
            labels.append(f'{base}-{s[len(str(base)):]}')
            notes.append(f'"{s}" read as {base} superscript {s[len(str(base)):]}')
        else:
            if labels and '-' in labels[-1] and nxt is not None and s.startswith(labels[-1].split('-')[0]) \
                    and n != int(labels[-1].split('-')[0]) + 1:
                b0 = labels[-1].split('-')[0]
                labels.append(f'{b0}-{s[len(b0):]}')
                notes.append(f'"{s}" read as {b0} superscript {s[len(b0):]}')
                continue
            labels.append(s)
            prev = n
    units = {}
    headings = []
    pre = []
    first = starts[0] if starts else len(paras)
    for t, bold in paras[:first]:
        if HEAD.match(t) and bold:
            headings.append(t)
        else:
            pre.append(t)
    if preamble is not None:
        pre = preamble
    if pre:
        units['preambula'] = {'label': 'Preambula', 'kind': 'preamble', 'text': '\n'.join(pre) + '\n'}
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(paras)
        t0, b0 = paras[i]
        m = ART.match(t0)
        rest = m.group(2).strip()
        lines = []
        head = f'# {label_of(labels[k])}'
        j = i + 1
        if titled and rest:
            head += f'. {rest}'
            # heading split over several bold paragraphs
            while j < end and paras[j][1] and not HEAD.match(paras[j][0]) and not ART.match(paras[j][0]) \
                    and len(paras[j][0]) < 160 and not re.match(r'^\d+[.)]', paras[j][0]):
                head += ' ' + paras[j][0]
                j += 1
        elif rest:
            lines.append(rest)
        body = []
        tail_heads = []
        for t, bold in paras[j:end]:
            if HEAD.match(t) and bold:
                tail_heads.append(t)
                continue
            if tail_heads:  # a heading in the middle of an article is not a heading
                body.extend(tail_heads)
                tail_heads = []
            body.append(t)
        headings_after = tail_heads
        key = key_of(labels[k])
        if key in units:
            raise SystemExit(f'duplicate article {key}')
        units[key] = {'label': label_of(labels[k]), 'kind': 'art', 'text': '\n'.join([head] + lines + body) + '\n'}
        if headings_after:
            headings.extend(f'{h}' for h in headings_after)
            units[key]['_next_headings'] = headings_after
    # headings unit: every structural heading, each with the article it opens
    outline = []
    keys = [k for k in units if k.startswith('art-')]
    for t, bold in paras[:first]:
        if HEAD.match(t) and bold:
            outline.append(t)
    for k in keys:
        for h in units[k].pop('_next_headings', []):
            outline.append(h)
    if outline:
        units['bolumler'] = {'label': 'Bölümler we baplar', 'kind': 'headings', 'text': '\n'.join(outline) + '\n'}
    return units, notes


def drop_repealed(units: dict) -> list[str]:
    """Articles the consolidated text shows only as 'repealed by …' notes are absent from the law."""
    gone = []
    for k, u in list(units.items()):
        body = u['text'].split('\n', 1)
        if re.search(r'güýjüni ýitiren diýip ykrar edilen\.?\s*$', u['text'].strip()) and len(u['text']) < 300:
            gone.append(k)
            del units[k]
    return gone


# ---------------------------------------------------------------- acts

def mejlis(url: str) -> tuple[list[tuple[str, bool]], str]:
    b, sha = url_bytes(url)
    return paragraphs(b.decode('utf-8')), sha


def after(paras, pred):
    for i, (t, b) in enumerate(paras):
        if pred(t, b):
            return paras[i + 1:]
    raise SystemExit('marker not found')


def constitution_current():
    url = 'https://mejlis.gov.tm/single-law/107?lang=tm'
    paras, sha = mejlis(url)
    body = after(paras, lambda t, b: t.startswith('(09.10.2017 ý.'))
    units, notes = split_units(body, bold_articles=False, titled=False)
    gone = drop_repealed(units)
    return url, sha, units, notes, gone


def civil_code():
    url = 'https://mejlis.gov.tm/single-code/6?lang=tm'
    paras, sha = mejlis(url)
    body = after(paras, lambda t, b: t == 'TÜRKMENISTANYŇ RAÝAT KODEKSI')
    units, notes = split_units(body, bold_articles=False, titled=True)
    return url, sha, units, notes


def criminal_code():
    url = 'https://mejlis.gov.tm/single-code/27?lang=tm'
    paras, sha = mejlis(url)
    # skip the enacting law and the table of contents (MAZMUNY): the code starts at its second UMUMY BÖLEK
    idx = [i for i, (t, b) in enumerate(paras) if t == 'UMUMY BÖLEK']
    body = paras[idx[1]:]
    units, notes = split_units(body, bold_articles=False, titled=True)
    return url, sha, units, notes


def main() -> None:
    laws = {}
    acts = []
    decisions = []

    # Constitution
    url, sha, units, notes, gone = constitution_current()
    laws['kk-531-vi'] = {'label': 'Konstitusion kanun № 531-VI', 'kind': 'law',
                         'title': 'Türkmenistanyň Konstitusiýasyna üýtgetmeler we goşmaçalar girizmek hakynda',
                         'enacted': '2023-01-21', 'published': '2023-01-21', 'url': url,
                         'temporary_until': None, 'restores': None, 'note': None}
    acts.append({'slug': 'konstitusiya', 'short': 'Konstitusiýa', 'title': 'Türkmenistanyň Konstitusiýasy',
                 'url': url, 'first_law': None, 'earlier_laws': [],
                 'versions': [{'from': '2023-01-21', 'source_url': url, 'sha256': sha, 'units': units, 'credits': {},
                               'note': 'Oldest version available: the Mejlis consolidated text of the 2016 revision, '
                                       'with the amendments of 2017, 2020 and 2023.'}]})
    for k in ['kk-448-v', 'kk-617-v', 'kk-297-vi']:
        pass
    decisions += [f'Constitution: {n}.' for n in notes]
    decisions.append('Constitution: articles shown in the consolidated text only as a red "repealed by …" note are '
                     f'left out of the text: {", ".join(gone)}.')

    # Civil Code 2025
    url, sha, units, notes = civil_code()
    laws['kanun-162-vii'] = {'label': 'Kanun № 162-VII', 'kind': 'law',
                             'title': 'Türkmenistanyň Raýat kodeksini tassyklamak we herekete girizmek hakynda',
                             'enacted': '2025-06-28', 'published': '2025-06-28', 'url': url,
                             'temporary_until': None, 'restores': None, 'note': None}
    acts.append({'slug': 'rayat-kodeksi', 'short': 'RK', 'title': 'Türkmenistanyň Raýat kodeksi', 'url': url,
                 'first_law': 'kanun-162-vii', 'earlier_laws': [],
                 'versions': [{'from': '2026-01-01', 'source_url': url, 'sha256': sha, 'units': units, 'credits': {}}]})
    decisions += [f'Civil Code: {n}.' for n in notes]

    # Criminal Code, 2022 revised edition
    try:
        url, sha, units, notes = criminal_code()
    except SystemExit as e:  # not yet parsed cleanly: left out
        decisions.append(f'Criminal Code left out of this build: parser stopped ({e}).')
        units = None
    if units is not None:
     laws['kanun-456-vi'] = {'label': 'Kanun № 456-VI', 'kind': 'law',
                            'title': 'Türkmenistanyň Jenaýat kodeksine üýtgetmeler we goşmaçalar girizmek hem-de ony '
                                     'rejelenen görnüşde tassyklamak hakynda',
                            'enacted': '2022-04-17', 'published': '2022-04-17', 'url': url,
                            'temporary_until': None, 'restores': None, 'note': None}
     acts.append({'slug': 'jenayat-kodeksi', 'short': 'JK', 'title': 'Türkmenistanyň Jenaýat kodeksi', 'url': url,
                 'first_law': 'kanun-456-vi', 'earlier_laws': [],
                 'versions': [{'from': '2023-01-01', 'source_url': url, 'sha256': sha, 'units': units, 'credits': {}}]})
     decisions += [f'Criminal Code: {n}.' for n in notes]

    reqs = sum(1 for _ in open(CACHE / 'requests.jsonl', encoding='utf-8'))
    corpus = {
        'country': {
            'code': 'TM', 'name': 'Turkmenistan', 'slug': 'turkmenistan', 'lang': 'tk', 'tz': 'Asia/Ashgabat',
            'future_branch': 'future',
            'publisher': {'name': 'Türkmenistanyň Mejlisi (mejlis.gov.tm)', 'email': 'mejlis@mejlis.gov.tm.invalid'},
            'default_in_force_rule': {
                'text': 'A law enters into force on the day its own text names; Turkmen laws state it in their final '
                        'article ("… kabul edilen pursadyndan güýje girýär", "… herekete girizilýär").',
                'source': 'https://mejlis.gov.tm/single-law/107?lang=tm'},
            'licence_note': 'Official texts of the Mejlis of Turkmenistan (mejlis.gov.tm). Official legislative texts; '
                            'the site states "Ähli hukuklar goralan" (all rights reserved) for the site itself.'},
        'sources': [{'name': 'Türkmenistanyň Mejlisi (mejlis.gov.tm): Kanunçylyk', 'url': 'https://mejlis.gov.tm/laws?lang=tm',
                     'retrieved': RETRIEVED, 'requests': reqs,
                     'licence': 'Official text; site "Ähli hukuklar goralan"',
                     'notes': 'HTML full texts of the Constitution (consolidated), codes and laws, in Turkmen.'}],
        'laws': laws,
        'acts': acts,
        'applies': [],
        'decisions': decisions,
        'ai_use': ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py and parse.py and chose the sources. '
                   'No model wrote or altered legal text; all text is parsed by code from the official pages.'],
    }
    out = HERE / 'corpus.json'
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, out)
    for a in acts:
        print(a['slug'], [(v['from'], len(v.get('units') or {})) for v in a['versions']])
    for d in decisions:
        print(' -', d)


if __name__ == '__main__':
    main()
