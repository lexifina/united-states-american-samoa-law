"""Build corpus.json for Tuvalu from the cache only (no network).

Phase 1 so far: the Constitution, two dated versions from tuvalu-legislation.tv:
- 2008 Revised Edition PDF (Cap. 1.02), consolidated to Act 4 of 2007 (in force 3 August 2007);
- the Constitution of Tuvalu Act 2023 (Act 7 of 2023, commencement 1 October 2023).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import fetch
import layout

HERE = Path(__file__).resolve().parent
C = 'https://tuvalu-legislation.tv/cms/images/LEGISLATION/PRINCIPAL/1986/1986-0001/1986-0001_%d.pdf'


def version(url: str, frm: str, credit: list[str] | None, prev: dict | None) -> dict:
    p = fetch.path_for(url)
    doc = layout.read(str(p))
    units = {u.key: {'label': u.label, 'kind': u.kind, 'text': layout.unit_text(u)} for u in doc.units}
    # Official table row for points 180-181 is a merged-range cell; the text layer interleaves its columns.
    bad = 'TVBP00180- 6°06\'05.60" S- 177°20\'14.42" E- TS,CZ TS,CZ TVBP00181 6°06\'05.52" S 177°20\'12.80" E'
    good = 'TVBP00180-TVBP00181 6°06\'05.60" S-6°06\'05.52" S 177°20\'14.42" E-177°20\'12.80" E TS,CZ'
    for u in units.values():
        u['text'] = u['text'].replace(bad, good)
    v = {'from': frm, 'source_url': url, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'units': units, 'credits': {}}
    if prev is not None and credit:
        for k in sorted(set(units) | set(prev['units'])):
            if units.get(k, {}).get('text') != prev['units'].get(k, {}).get('text'):
                v['credits'][k] = list(credit)
    return v


def corpus() -> dict:
    v1 = version(C % 1, '2007-08-03', None, None)
    v2 = version(C % 3, '2023-10-01', ['act-2023-07'], v1)
    laws = {
        'const-1986': {'label': 'Constitution of Tuvalu 1986', 'title': 'Constitution of Tuvalu (Schedule to Ordinance 1 of 1986)', 'kind': 'law', 'enacted': '1986-10-01', 'published': None, 'url': None},
        'act-1992-02': {'label': 'Act 2 of 1992', 'title': 'Constitution amendment, commences 18 August 1992 (LN 9/1992)', 'kind': 'law', 'enacted': None, 'published': None, 'url': None},
        'act-2000-05': {'label': 'Act 5 of 2000', 'title': 'Constitution amendment, commences 23 August 2000 (LN 5/2000)', 'kind': 'law', 'enacted': None, 'published': None, 'url': None},
        'act-2002-04': {'label': 'Act 4 of 2002', 'title': 'Constitution amendment, commences 1 July 2002 (LN 9/2002)', 'kind': 'law', 'enacted': None, 'published': None, 'url': None},
        'act-2002-05': {'label': 'Act 5 of 2002', 'title': 'Constitution amendment, commences 1 July 2002 (LN 10/2002)', 'kind': 'law', 'enacted': None, 'published': None, 'url': None},
        'act-2007-04': {'label': 'Act 4 of 2007', 'title': 'Constitution amendment, commences 3 August 2007 (LN 3/2007)', 'kind': 'law', 'enacted': None, 'published': None, 'url': None},
        'act-2023-07': {'label': 'Act 7 of 2023', 'title': 'The Constitution of Tuvalu Act 2023', 'kind': 'law', 'enacted': None, 'published': None, 'url': C % 3},
    }
    for l in laws.values():
        l.update({'temporary_until': None, 'restores': None, 'note': None})
    return {
        'country': {'code': 'TV', 'name': 'Tuvalu', 'slug': 'tuvalu', 'lang': 'en', 'tz': 'Pacific/Funafuti', 'future_branch': 'future',
                    'publisher': {'name': 'Office of the Attorney-General of Tuvalu (Tuvalu Legislation Online)', 'email': 'publisher@tuvalu-legislation.invalid'},
                    'default_in_force_rule': {'text': 'Dates are the commencement dates printed by the publisher (endnotes and "Commencement [...]" lines).', 'source': 'https://tuvalu-legislation.tv/cms/'},
                    'licence_note': 'Source: Tuvalu Legislation Online (tuvalu-legislation.tv), Office of the Attorney-General.'},
        'sources': [{'name': 'Tuvalu Legislation Online', 'url': 'https://tuvalu-legislation.tv/cms/', 'retrieved': '2026-10-28',
                     'requests': sum(1 for _ in open(HERE / '.cache' / 'requests.jsonl', encoding='utf-8')),
                     'licence': 'see the site copyright page', 'notes': 'Revised Edition PDFs with a text layer; no OCR.'}],
        'laws': laws,
        'acts': [{'slug': 'constitution', 'short': 'Const', 'title': 'The Constitution of Tuvalu', 'url': C % 3,
                  'first_law': None,
                  'earlier_laws': ['const-1986', 'act-1992-02', 'act-2000-05', 'act-2002-04', 'act-2002-05', 'act-2007-04'],
                  'versions': [v1, v2]}],
        'applies': [],
        'decisions': [
            'Constitution version 1 is the 2008 Revised Edition PDF (version 1 on the site); its endnote 1 lists amendments up to Act 4 of 2007 (commences 3 August 2007), so it is dated 2007-08-03 as the oldest version available. The site dates this file 1986-10-01, the original commencement, which is not the date of this text.',
            'Constitution version 2 is the Constitution of Tuvalu Act 2023 (Act 7 of 2023), commencement 1 October 2023 per its own endnote and Commencement line; every changed unit is credited to it. The site lists it as versions 2 and 3 dated 2022-12-30; both files parse to identical units, so the current file (version 3) is used.',
            'Part and Division headings are their own units (part-NN, part-NN-div-MM); footnote reference numerals are dropped from the text.',
        ],
        'ai_use': ['none: text is extracted from the PDFs text layer by layout.py rules; no model wrote or edited legal text.'],
    }


def write():
    c = corpus()
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    a = c['acts'][0]
    print('versions', len(a['versions']), 'units', [len(v['units']) for v in a['versions']], 'credited', len(a['versions'][1]['credits']))


if __name__ == '__main__':
    write()
