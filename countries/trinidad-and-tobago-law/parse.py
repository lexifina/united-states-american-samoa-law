"""Reads the cache only and writes corpus.json (scripts/gitlaw_common/SCHEMA.md).

Phase 1 so far: the Constitution, one version (the current revised text, updated to 31 December 2016),
as the oldest version available. Archived dated editions (2009, 2011, 2012, 2013, 2015) are cached under
.cache/wb/ and are the next step.
"""
import hashlib
import json
import os
import re
from collections import Counter

import fetch
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
CONST_URL = 'https://rgd.legalaffairs.gov.tt/Laws2/Constitution.pdf'
ORD = {'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5, 'SIXTH': 6}


def resolve_hyphens(paras):
    vocab = Counter(w.lower() for p in paras for w in re.findall(r"[A-Za-z]+", p.text.replace('\x01', '')))
    def fix(m):
        a, b = m.group(1), m.group(2)
        return a + b if vocab.get((a + b).lower(), 0) > 0 and (a + '-' + b).lower() not in vocab else a + '-' + b
    for p in paras:
        p.text = re.sub(r'([A-Za-z]+)-\x01([A-Za-z]+)', fix, p.text).replace('\x01', '')


def units_of(paras):
    units = {}
    key, label, lines = 'preamble', 'Preamble', ['# Preamble']
    def flush():
        if key and len(lines) > 1:
            units[key] = {'label': label, 'kind': 'preamble' if key == 'preamble' else
                          ('schedule' if key.startswith('schedule') else 'sec'), 'text': '\n'.join(lines) + '\n'}
    for p in paras:
        t = p.text.strip()
        m = re.match(r'^(\d+)([A-Z]*)\.\s', t + ' ')
        ms = re.match(r'^(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH)\s+SCHEDULE', t)
        if ms and p.heading:
            flush()
            n = ORD[ms.group(1)]
            key, label, lines = f'schedule-{n}', f'{ms.group(1).title()} Schedule', [f'# {ms.group(1).title()} Schedule']
            continue
        if m and p.bold_lead and not key.startswith('schedule'):
            flush()
            num, suf = m.group(1), m.group(2)
            key, label = f'sec-{int(num):03d}' + (f'-{suf.lower()}' if suf else ''), f's. {num}{suf}'
            lines = [f'# Section {num}{suf}']
        elif p.heading and not key.startswith('schedule') and key != 'preamble':
            continue   # Part/Chapter headings are structure, left out
        lines.append(t)
    flush()
    return units


def constitution():
    path = fetch.path_for(CONST_URL, '.pdf')
    raw = open(path, 'rb').read()
    doc = layout.open_pdf(path)
    paras = layout.paragraphs(doc, range(11, doc.page_count))
    resolve_hyphens(paras)
    units = units_of(paras)
    return {
        'slug': 'constitution', 'short': 'Constitution',
        'title': 'The Constitution of the Republic of Trinidad and Tobago',
        'url': CONST_URL, 'first_law': None,
        'earlier_laws': ['act-4-1976'],
        'versions': [{'from': '2016-12-31', 'source_url': CONST_URL, 'sha256': hashlib.sha256(raw).hexdigest(),
                      'units': units, 'credits': {},
                      'note': 'Revised text "UPDATED TO 31ST DECEMBER 2016" (unofficial version, Ministry of the '
                              'Attorney General and Legal Affairs); amended by Acts listed on its front page up to 12 of 2007.'}],
    }


def main():
    corpus = {
        'country': {'code': 'TT', 'name': 'Trinidad and Tobago', 'slug': 'trinidad-and-tobago', 'lang': 'en',
                    'tz': 'America/Port_of_Spain', 'future_branch': 'future',
                    'publisher': {'name': 'Ministry of the Attorney General and Legal Affairs (Laws of Trinidad and Tobago)',
                                  'email': 'agla@legalaffairs.invalid'},
                    'default_in_force_rule': {'text': 'Not yet cited: versions so far are dated by the revised edition\'s own "updated to" date.',
                                              'source': 'https://rgd.legalaffairs.gov.tt/laws2/alphabetical_list/lawspdfs/3.01.pdf'},
                    'licence_note': 'Laws of Trinidad and Tobago, unofficial version, Ministry of the Attorney General and Legal Affairs (legalaffairs.gov.tt). No licence is stated.'},
        'sources': [{'name': 'Laws of Trinidad and Tobago, Ministry of the Attorney General and Legal Affairs',
                     'url': 'https://rgd.legalaffairs.gov.tt/Laws2/', 'retrieved': '2026-10-28', 'requests': None,
                     'licence': 'none stated', 'notes': 'revised-edition PDFs, unofficial version, updated to 31 Dec 2016'},
                    {'name': 'Digital Legislative Library (laws.gov.tt)', 'url': 'https://laws.gov.tt/ttdll-web/revision/list',
                     'retrieved': '2026-10-28', 'requests': None, 'licence': 'none stated',
                     'notes': 'point-in-time revised editions per chapter (2004-2016) and amending Acts; not yet used for text'}],
        'laws': {'act-4-1976': {'label': 'Act No. 4 of 1976', 'title': 'Constitution of the Republic of Trinidad and Tobago Act',
                                'kind': 'law', 'enacted': None, 'published': None, 'url': None,
                                'temporary_until': None, 'restores': None, 'note': None}},
        'acts': [constitution()],
        'applies': [],
        'decisions': [
            'The Constitution is built first as one "oldest version available" version: the current revised text (updated to 31 December 2016), credited to the publisher. Dated archived editions (2009-2015) are cached but not yet parsed.',
            'Marginal notes and Part/Chapter headings are left out of the text; each file starts with "# Section N".',
            'The version is dated 2016-12-31, the date the revised text states it is updated to.',
        ],
        'ai_use': ['none: no model wrote or transformed legal text; Claude Code (claude-opus-5-5) wrote the scripts.'],
    }
    tmp = os.path.join(HERE, 'corpus.json.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
    os.replace(tmp, os.path.join(HERE, 'corpus.json'))
    print({a['slug']: len(a['versions'][-1]['units']) for a in corpus['acts']})


if __name__ == '__main__':
    main()
