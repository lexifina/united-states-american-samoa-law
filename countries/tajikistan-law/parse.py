"""Tajikistan: read only the cache and write corpus.json (atomically).

Phase 1 so far: the Constitution, 1999+2003 edition, from the Majlisi namoyandagon page
http://parlament.tj/konstitutsiyai-jt/ as archived by the Internet Archive on 2017-06-07 (id_ capture).
"""
import hashlib, html, json, os, re
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / '.cache'
CONST_URL = 'http://parlament.tj/konstitutsiyai-jt/'
CONST_TS = '20170607141323'
ARCHIVE_URL = f'https://web.archive.org/web/{CONST_TS}id_/{CONST_URL}'

ORD = {'якум': 1, 'дуюм': 2, 'сеюм': 3, 'чорум': 4, 'панҷум': 5, 'шашум': 6, 'ҳафтум': 7, 'ҳаштум': 8,
       'нӯҳум': 9, 'нўҳум': 9, 'нуҳум': 9, 'чаҳорум': 4, 'даҳум': 10}


def norm(s: str) -> str:
    s = html.unescape(s).replace('\xa0', ' ')
    s = s.replace('ў', 'ӯ').replace('Ў', 'Ӯ')  # one form of the Tajik u-macron (publisher mixes Belarusian ў)
    s = re.sub(r'[ \t]+', ' ', s).strip()
    return s


def constitution():
    raw = (CACHE / hashlib.sha256(ARCHIVE_URL.encode()).hexdigest()).read_bytes()
    t = raw.decode('utf-8')
    body = t[t.index('<div class="text">'):]
    body = body[:body.index('</div>')]
    body = re.sub(r'(?i)<br\s*/?>|</p>|<p[^>]*>', '\n', body)
    body = re.sub(r'<[^>]+>', '', body)
    lines = [norm(l) for l in body.split('\n')]
    lines = [l for l in lines if l]
    start = next(i for i, l in enumerate(lines) if l.startswith('МО, ХАЛҚИ ТОҶИКИСТОН'))
    units, cur, key = {}, [], 'preamble'
    labels = {'preamble': ('Муқаддима', 'preamble')}

    def flush():
        if cur:
            units[key] = {'label': labels[key][0], 'kind': labels[key][1], 'text': '\n'.join(cur) + '\n'}

    chapter_pending = []
    for l in lines[start:]:
        m = re.match(r'^Моддаи (\d+)\.\s*(.*)$', l)
        mb = re.match(r'^Боби (\S+)$', l)
        if mb:
            flush(); cur = []
            n = ORD.get(mb.group(1).lower())
            key = f'bob-{n:02d}' if n else 'bob-' + re.sub(r'[^a-z0-9]', '', mb.group(1).lower())
            labels[key] = (l, 'chapter')
            cur = [l]
            continue
        if m:
            flush()
            key = f'art-{int(m.group(1)):03d}'
            labels[key] = (f'Моддаи {int(m.group(1))}', 'art')
            cur = [f'Моддаи {int(m.group(1))}.'] + ([m.group(2)] if m.group(2) else [])
            continue
        cur.append(l)
    flush()
    return {
        'slug': 'konstitutsiya',
        'short': 'Конститутсия',
        'title': 'Конститутсияи (Сарқонуни) Ҷумҳурии Тоҷикистон',
        'url': CONST_URL,
        'first_law': None,
        'earlier_laws': ['raypursi-1994-11-06', 'raypursi-1999-09-26'],
        'versions': [{
            'from': '2003-06-22',
            'source_url': ARCHIVE_URL,
            'sha256': hashlib.sha256(raw).hexdigest(),
            'units': units,
            'note': 'Edition with the amendments of the referendums of 26 September 1999 and 22 June 2003, '
                    'as published by the Majlisi namoyandagon (Internet Archive capture of 7 June 2017). '
                    'The 1994 and 1999 texts are not in this build.',
        }],
    }


def main():
    corpus = {
        'country': {
            'code': 'TJ', 'name': 'Tajikistan', 'slug': 'tajikistan', 'lang': 'tg', 'tz': 'Asia/Dushanbe',
            'future_branch': 'future',
            'publisher': {'name': 'Majlisi namoyandagoni Majlisi Olii Jumhurii Tojikiston (parlament.tj)',
                          'email': 'publisher@parlament.invalid'},
            'default_in_force_rule': {'text': 'Constitutional amendments adopted by national referendum; '
                                              'this build dates the edition by the referendum day the source names.',
                                      'source': CONST_URL},
            'licence_note': 'Official text of the Constitution of the Republic of Tajikistan, as published by the '
                            'Majlisi namoyandagon of the Majlisi Oli (parlament.tj); read from an Internet Archive capture.',
        },
        'sources': [{'name': 'Majlisi namoyandagon (parlament.tj), via Internet Archive', 'url': CONST_URL,
                     'retrieved': '2026-10-28', 'requests': 1,
                     'licence': 'Official legislative text (public domain as an official act); Internet Archive capture',
                     'notes': f'capture {CONST_TS}; Tajik (official language), Cyrillic'}],
        'laws': {
            'raypursi-1994-11-06': {'label': 'Раъйпурсии 6.11.1994', 'title': 'Adoption of the Constitution by national referendum',
                                    'kind': 'referendum', 'enacted': '1994-11-06', 'published': None, 'url': None,
                                    'temporary_until': None, 'restores': None, 'note': None},
            'raypursi-1999-09-26': {'label': 'Раъйпурсии 26.09.1999', 'title': 'Constitutional amendments by national referendum',
                                    'kind': 'referendum', 'enacted': '1999-09-26', 'published': None, 'url': None,
                                    'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [constitution()],
        'applies': [],
        'decisions': [
            'Tajik is the official language; the Tajik text is built. Russian texts exist (adlia.tj) but anonymous access shows only 1,500 characters.',
            'All .tj sites time out from the build machine, so the official pages are read from Internet Archive id_ captures, pinned by timestamp.',
            'Constitution: the oldest text available is the 1999+2003 edition published by the Majlisi namoyandagon; it is the first version (first_law null), dated 2003-06-22, the referendum day the source names for the edition.',
            'The 1994 original and the 1999 edition were not found online at an official source; they are named in earlier_laws.',
            'Belarusian ў in the publisher text is normalised to Tajik ӯ.',
        ],
        'ai_use': ['none: no model wrote or transformed legal text; Claude Opus 5.5 wrote the scripts.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    a = corpus['acts'][0]['versions'][0]['units']
    print(len(a), 'units', sorted(a)[:3], sorted(a)[-3:])


if __name__ == '__main__':
    main()
