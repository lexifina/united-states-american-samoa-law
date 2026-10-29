"""Builds scripts/mauritius-law/corpus.json from the cache only (no network).

Constitution: the Attorney General's Office consolidation (latest change it records: Act 35 of 2011, w.e.f.
12 December 2011), then the Constitution amendment Acts as passed and gazetted (National Assembly PDFs), replayed.
The inserted words are cut from the cached Act PDFs by code; nothing is typed by hand or by a model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import revised as R  # noqa: E402
import units as U  # noqa: E402
import assembly  # noqa: E402

AG_CON = 'https://attorneygeneral.govmu.org/Documents/Laws%20of%20Mauritius/Constitutions/THE%20CONSTITUTION,%20GN%2054%20of%201968.pdf'
ASM = 'https://mauritiusassembly.govmu.org/mauritiusassembly/wp-content/uploads/'


def sha(url: str) -> str:
    return hashlib.sha256(fetch.path(url).read_bytes()).hexdigest()


def act_paras(url: str, start: str, end: str) -> list[str]:
    """The quoted provision text of an amending Act, between two anchors, one paragraph per line."""
    t = assembly.text(url)
    t = re.sub(r'\n\s*(Acts \d{4}\s+\d+|\d+\s+Acts \d{4})\s*\n', '\n', t)
    t = re.sub(r'\s+', ' ', t)
    start, end = re.sub(r'\s+', ' ', start), re.sub(r'\s+', ' ', end)
    t = t[t.index(start):]
    t = t[:t.index(end) + len(end)]
    flat = R.norm(t)
    parts = re.split(r'\s(?=\((?:[a-z]{1,2}|[ivx]+)\)\s)|\s(?=by way of confiscation)', flat)
    return [p.strip() for p in parts if p.strip()]


def insert_after(text: str, anchor_start: str, new: list[str], skip_until: str | None = None) -> str:
    lines = text.rstrip('\n').split('\n')
    i = next(i for i, l in enumerate(lines) if l.startswith(anchor_start))
    if skip_until:
        i = next(j for j in range(i, len(lines)) if lines[j].startswith(skip_until))
    lines[i + 1:i + 1] = new
    return '\n'.join(lines) + '\n'


def constitution() -> tuple[dict, dict]:
    units, notes = U.revised_units(fetch.path(AG_CON), r'^1\. The State$', r'^LAWS RELATED TO THE CONSTITUTION')
    for u in units.values():
        u['text'] = re.sub(r' \*(?=\s)', '', u['text'])
    laws = {}
    def law(key, label, title, enacted, published, url, note=None, temporary_until=None):
        laws[key] = {'label': label, 'title': title, 'kind': 'law', 'enacted': enacted, 'published': published,
                     'url': url, 'temporary_until': temporary_until, 'restores': None, 'note': note}
    versions = [{'from': '2011-12-12', 'source_url': AG_CON, 'sha256': sha(AG_CON), 'units': copy.deepcopy(units),
                 'credits': {},
                 'note': "Attorney General's Office consolidation (Revised Laws of Mauritius, issues 1-7); the latest "
                         "change it records is Act 35 of 2011 w.e.f. 12 December 2011. Identical text in the Wayback "
                         "capture of 21 December 2015."}]
    # Act 3 of 2014: modifies First Schedule para 3 for one election; no words change.
    u14 = ASM + '2023/03/act0314.pdf'
    law('act-2014-03', 'Act No. 3 of 2014', 'The Constitution (Declaration of Community) (Temporary Provisions) Act 2014',
        '2014-07-14', '2014-07-17', u14,
        note='Applies only to the first general election after 17 July 2014: notwithstanding paragraph 3 of the First '
             'Schedule, a candidate may elect not to declare his community. No words of the Constitution change.')
    versions.append({'from': '2014-07-17', 'source_url': u14, 'sha256': sha(u14), 'credits': {'sch-01': ['act-2014-03']}})
    cur = copy.deepcopy(units)
    # Act 30 of 2015: s. 8(4), new paragraph (aa) after paragraph (a).
    u15 = ASM + '2023/03/act3015.pdf'
    law('act-2015-30', 'Act No. 30 of 2015', 'The Constitution (Amendment) Act 2015', '2015-12-07', '2015-12-10', u15)
    new = act_paras(u15, '(aa) or any other provision', 'reasonably\n                               justifiable in a democratic society; or')
    s8 = cur['s-008']['text'].split('\n')
    i4 = next(i for i, l in enumerate(s8) if l.startswith('(4) '))
    ib = next(i for i in range(i4, len(s8)) if s8[i].startswith('(b) '))
    s8[ib:ib] = new
    cur['s-008']['text'] = '\n'.join(s8)
    versions.append({'from': '2015-12-10', 'source_url': u15, 'sha256': sha(u15), 'units': copy.deepcopy(cur),
                     'credits': {'s-008': ['act-2015-30']}})
    # Acts 28 and 30 of 2016: s. 15(3) and s. 16(4).
    u28, u30 = ASM + '2023/03/act2816.pdf', ASM + '2023/03/act3016.pdf'
    law('act-2016-28', 'Act No. 28 of 2016', 'The Constitution (Amendment) Act 2016', '2016-12-16', '2016-12-17', u28)
    law('act-2016-30', 'Act No. 30 of 2016', 'The Constitution (Amendment No. 2) Act 2016', '2016-12-16', '2016-12-17', u30)
    t28 = R.norm(re.sub(r'\s+', ' ', assembly.text(u28)))
    words = re.search(r'the words "public health", the words "(, otherwise than pursuant to paragraph \(ca\))"', t28).group(1)
    ca = act_paras(u28, '(ca) for the imposition', 'relating to offences or acts of terrorism;')
    s15 = cur['s-015']['text'].split('\n')
    i3 = next(i for i, l in enumerate(s15) if l.startswith('(3) '))
    for j in range(i3, len(s15)):
        if s15[j].startswith('(a) ') or s15[j].startswith('(b) '):
            assert s15[j].count('public health') == 1, s15[j]
            s15[j] = s15[j].replace('public health', 'public health' + words)
        if s15[j].startswith('(b) '):
            s15[j + 1:j + 1] = ca
            break
    cur['s-015']['text'] = '\n'.join(s15)
    ab = act_paras(u30, '(ab) for a minimum number', 'in the\n                               Rodrigues Regional Assembly;')
    s16 = cur['s-016']['text'].split('\n')
    i = next(i for i, l in enumerate(s16) if l.startswith('(aa) '))
    s16[i + 1:i + 1] = ab
    cur['s-016']['text'] = '\n'.join(s16)
    versions.append({'from': '2016-12-17', 'source_url': u28, 'sha256': sha(u28), 'units': copy.deepcopy(cur),
                     'credits': {'s-015': ['act-2016-28'], 's-016': ['act-2016-30']}})
    for v in versions:
        for u in v.get('units', {}).values():
            if not u['text'].endswith('\n'):
                u['text'] += '\n'
    # The laws the publisher's amendment notes name as having produced the oldest text. Each becomes a law key
    # (label only: the notes give no titles, and dates only for some, so none are filled in).
    earlier_found = {(kind, int(num), int(year)) for _, n in notes
                     for kind, num, year in re.findall(r'\b(Act|GN) (\d+) (?:of )?(\d{4})\b', n)}
    earlier = []
    for kind, num, year in sorted(earlier_found, key=lambda x: (x[2], x[1], x[0])):
        key = f'{kind.lower()}-{year}-{num:02d}'
        if key not in laws:
            laws[key] = {'label': f'{"Act No." if kind == "Act" else "GN No."} {num} of {year}',
                         'kind': 'law' if kind == 'Act' else 'decree', 'enacted': None, 'published': None,
                         'url': None, 'temporary_until': None, 'restores': None, 'note': None}
        earlier.append(key)
    act = {'slug': 'constitution', 'short': 'Constitution', 'title': 'The Constitution of Mauritius',
           'url': AG_CON, 'first_law': None, 'earlier_laws': earlier, 'versions': versions}
    return act, laws


def main() -> None:
    con, laws = constitution()
    corpus = {
        'country': {'code': 'MU', 'name': 'Mauritius', 'slug': 'mauritius', 'lang': 'en', 'tz': 'Indian/Mauritius',
                    'future_branch': 'future',
                    'publisher': {'name': "Attorney General's Office (Revised Laws of Mauritius)",
                                  'email': 'ago@attorneygeneral.invalid'},
                    'default_in_force_rule': {
                        'text': "Constitution s. 46(4): no law comes into operation until published in the Gazette; "
                                "Parliament may postpone or make it retrospective. Dates used are the National "
                                "Assembly's 'Date in force' column, or the Act's own commencement section.",
                        'source': AG_CON},
                    'licence_note': "Laws of Mauritius, Attorney General's Office: 'Copyright 2011 – Government of "
                                    "Mauritius'; copies for non-commercial use under the Copyright Act; commercial use "
                                    "needs the prior approval of the Solicitor General. Acts as passed: National "
                                    "Assembly of Mauritius."},
        'sources': [
            {'name': "Attorney General's Office, Laws of Mauritius", 'url': 'https://attorneygeneral.govmu.org/',
             'retrieved': '2026-10-28', 'requests': 0,
             'licence': 'Copyright Government of Mauritius; non-commercial copying allowed; commercial use needs Solicitor General approval',
             'notes': "Site states the Revised Laws are 'updated up to 30 June 2017'; sole authoritative text is the LexisNexis Revised Laws."},
            {'name': 'National Assembly of Mauritius, Acts as passed and gazetted',
             'url': 'https://mauritiusassembly.govmu.org/mauritiusassembly/index.php/acts-2/', 'retrieved': '2026-10-28',
             'requests': 0, 'licence': 'Official texts', 'notes': 'Text-layer PDFs 2010-2026; table gives Date in force.'},
            {'name': 'Internet Archive (Wayback) captures of attorneygeneral.govmu.org', 'url': 'https://web.archive.org/',
             'retrieved': '2026-10-28', 'requests': 0, 'licence': 'Captures of the AG site; same terms',
             'notes': 'Constitution 20151221221339 (same text as today); 20230921131315 truncated at 1 MiB, not used.'},
        ],
        'laws': laws,
        'acts': [con],
        'applies': [],
        'decisions': [
            "Mauritius has no Peachjam LII; sources are the Attorney General's Office consolidations and the National Assembly's Acts as passed.",
            "The AG Constitution text (unchanged since the 2015-12-21 Wayback capture apart from the electoral boundaries GN, now a separate file) is dated 2011-12-12, the commencement of the latest change it records (Act 35 of 2011); it is credited to the publisher as the oldest version available.",
            "Only sections 1-122 and the First to Fourth Schedules are the Constitution; the subsidiary regulations and boundary notices in the same PDF are left out.",
            "The publisher's bracketed amendment notes and the Khoyratty editorial note on s. 5(3A) are kept out of the text.",
            "Acts 30 of 2015, 28 and 30 of 2016 are replayed from the gazetted Act PDFs; their in-force dates are the National Assembly table's 'Date in force' (10 Dec 2015; 17 Dec 2016).",
            "Act 3 of 2014 changes no words; it is recorded as a note on the First Schedule.",
            "Act 10 of 2025 (repeals s. 7(2)) is NOT applied: the Act has no commencement section but the National Assembly table marks it '*' (by Proclamation), and no Proclamation was found. Today's s. 7 may therefore be out of date.",
        ],
        'ai_use': ['none at data-build time: parsing and replay are deterministic code.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('versions', len(con['versions']), 'units', len(con['versions'][0]['units']))


if __name__ == '__main__':
    main()
