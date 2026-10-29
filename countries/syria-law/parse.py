"""Read .cache/ only and write corpus.json (scripts/gitlaw_common/SCHEMA.md). Deterministic.

    python -X utf8 scripts/syria-law/parse.py
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
SRC = {d['id']: d for d in json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))['documents']}

ONES = {'الأولى': 1, 'الاولى': 1, 'الحادية': 1, 'الثانية': 2, 'الثالثة': 3, 'الرابعة': 4, 'الخامسة': 5,
        'السادسة': 6, 'السابعة': 7, 'الثامنة': 8, 'التاسعة': 9, 'العاشرة': 10}
TENS = {'العشرون': 20, 'الثلاثون': 30, 'الأربعون': 40, 'الاربعون': 40, 'الخمسون': 50, 'الستون': 60,
        'السبعون': 70, 'الثمانون': 80, 'التسعون': 90}


def ordinal(words: str) -> int | None:
    """'الثامنة والأربعون بعد المئة' -> 148."""
    n = 0
    w = words.replace('المائة', 'المئة')
    if 'بعد المئة' in w:
        n += 100
        w = w.replace('بعد المئة', '')
    elif w.strip() == 'المئة':
        return 100
    for tok in re.split(r'\s+', w.strip()):
        tok = tok[1:] if tok.startswith('و') and tok[1:] in TENS else tok
        if tok in ONES:
            n += ONES[tok]
        elif tok in TENS:
            n += TENS[tok]
        elif tok in ('عشرة', 'عشر'):
            n += 10
        elif tok:
            return None
    return n or None


def cached(doc_id: str) -> tuple[bytes, str, str]:
    d = SRC[doc_id]
    url = f"https://web.archive.org/web/{d['ts']}id_/{d['page']}"
    raw = (CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()).read_bytes()
    return raw, url, hashlib.sha256(raw).hexdigest()


def norm(s: str) -> str:
    s = s.replace('\xa0', ' ').replace('‌', '').replace('‏', '').replace('‎', '')
    s = s.replace('–', '-').replace('—', '-')
    return re.sub(r'\s+', ' ', s).strip()


def lines_of(raw: bytes) -> list[str]:
    t = raw.decode('cp1256', 'replace')
    a = t.find("id='intro'")
    b = t.find('عدد المشاهدات', a)
    t = re.sub(r'(?is)<script.*?</script>', '', t[a:b])
    t = re.sub(r'(?is)<(br|/p|/div|/tr|/li|/h\d)[^>]*>', '\n', t)
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    return [x for x in (norm(l) for l in t.split('\n')) if x]


ART = re.compile(r'^المادة\s+(.+?)$')
HEAD = re.compile(r'^(الباب|الفصل)\s')


def constitution(doc_id: str) -> dict:
    L = lines_of(cached(doc_id)[0])
    # the constitution starts at the second 'المقدمة' (the first is in the printed index)
    starts = [i for i, l in enumerate(L) if l == 'المقدمة']
    i = starts[-1]
    units: dict = {}
    key, label, body = 'preamble', 'المقدمة', []
    expect = 1

    def flush():
        if body:
            units[key] = {'label': label, 'kind': 'preamble' if key == 'preamble' else 'art',
                          'text': f'# {label}\n' + '\n'.join(body) + '\n'}

    for l in L[i + 1:]:
        if l.startswith('المحامي'):  # the page's uploader line after the text, not part of the constitution
            break
        m = ART.match(l)
        if m:
            n = ordinal(m.group(1))
            if n == expect:
                flush()
                key, label, body = f'art-{n:03d}', l, []
                expect += 1
                continue
        if HEAD.match(l) and len(l) < 80:
            continue  # part and chapter headings are dropped (decisions)
        body.append(l)
    flush()
    assert expect == 158, expect
    return units


def main() -> None:
    old = constitution('const2012-pa-2015')
    new = constitution('const2012-pa-2024')
    diff = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    raw, url, sha = cached('const2012-pa-2024')
    corpus = {
        'country': {
            'code': 'SY', 'name': 'Syria', 'slug': 'syria', 'lang': 'ar', 'tz': 'Asia/Damascus',
            'future_branch': 'future',
            'publisher': {'name': "People's Assembly of the Syrian Arab Republic (parliament.gov.sy)",
                          'email': 'publisher@parliament.invalid'},
            'default_in_force_rule': {
                'text': 'Each text names its own in-force day; Decree 94 of 2012 art. 1: the Constitution is in force from 27 February 2012',
                'source': SRC['const2012-pa-2024']['page']},
            'licence_note': "Text of the Constitution as published by the People's Assembly of the Syrian Arab Republic (parliament.gov.sy), read from Internet Archive captures. Official legislative texts.",
        },
        'sources': [{
            'name': "People's Assembly of the Syrian Arab Republic, 'الدستور السوري' page, via Internet Archive",
            'url': SRC['const2012-pa-2024']['page'], 'retrieved': '2026-10-28', 'requests': 2,
            'licence': 'Official legislative text (no licence stated); Internet Archive captures 20150428001050 and 20241207201658',
            'notes': 'parliament.gov.sy does not answer from here; read through pinned id_ captures.'}],
        'laws': {
            'decree-2012-94': {'label': 'Decree 94 of 2012', 'title': 'المرسوم 94 لعام 2012 بنشر دستور الجمهورية العربية السورية',
                               'kind': 'decree', 'enacted': '2012-02-27', 'published': '2012-02-27',
                               'url': SRC['const2012-pa-2024']['page'], 'temporary_until': None, 'restores': None,
                               'note': None}},
        'acts': [{
            'slug': 'constitution-2012', 'short': 'دستور 2012',
            'title': 'دستور الجمهورية العربية السورية 2012',
            'url': SRC['const2012-pa-2024']['page'],
            'first_law': None, 'earlier_laws': ['decree-2012-94'],
            'versions': [{
                'from': '2012-02-27', 'source_url': url, 'sha256': sha, 'units': new, 'credits': {},
                'note': 'Oldest version available: the text the People\'s Assembly published (captures of 28 April 2015 and 7 December 2024 give the same words).'}],
        }],
        'applies': [],
        'decisions': [
            'Phase 1 Constitution: the 2012 text from the People\'s Assembly page, read from the Internet Archive capture of 7 December 2024 (the last before 8 December 2024); the 28 April 2015 capture was compared: %d units differ (%s).' % (len(diff), ', '.join(diff) or 'none'),
            'first_law is null: the site gives no amendment history, so the one version is "oldest version available", credited to the publisher and dated 27 February 2012 from Decree 94 of 2012 art. 1 as printed on the page.',
            'Part and chapter headings (الباب, الفصل) and the printed index are dropped; the preamble is its own unit; the uploader line after the text is dropped.',
            'Not yet modelled: the end of the 2012 Constitution in 2025 and the Constitutional Declaration of 13 March 2025 (no official text fetched yet).',
        ],
        'ai_use': ['Claude Code (claude-opus-5-5) wrote fetch.py and parse.py; no model wrote or edited legal text.'],
    }
    out = HERE / 'corpus.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, out)
    print('units', len(new), 'diff vs 2015', diff)


if __name__ == '__main__':
    main()
