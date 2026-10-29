"""Choose the pinned captures and official URLs parse.py reads, and write sources.json (gitlaw-FM).

fsmlaw.org is listed through ONE archive.org CDX request per prefix (scripts/gitlaw_common/wayback.py, cached).
For every Constitution page it pins the newest and the oldest capture (parse.py checks they carry the same law
text, and dates the Constitution by the oldest). Code title PDFs are pinned to their newest complete capture.
Public laws come straight from the FSM Congress (cfsm.gov.fm), whose index rows give each law's date.

Usage: python -X utf8 discover.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = os.path.join(HERE, '.cache')
PAGES = ['preamble'] + [f'article{i}' for i in range(1, 17)]
TITLES = {7: '20190715110226', 11: '20260611041125'}     # complete captures (the 2025-01-19 Tit11 capture is cut at 1 MiB)
TITLE_URL = {7: 'http://www.fsmlaw.org:80/fsm/code/PDF/FSMCA2014Tit07.pdf',
             11: 'https://www.fsmlaw.org/fsm/code/PDF/FSMCA2014Tit11.pdf'}
CFSM = 'https://www.cfsm.gov.fm/wp-content/uploads/'
LAWS = {   # public laws after the 2014 edition that amend the titles built (found in the Congress index, below)
    '18-02': CFSM + '2024/07/PUBLIC-LAW-18-02.pdf', '18-19': CFSM + '2024/07/PUBLIC-LAW-18-19.pdf',
    '18-43': CFSM + '2024/07/PUBLIC-LAW-18-43.pdf', '21-08': CFSM + '2026/04/PUBLIC-LAW-NO.-21-08.pdf',
    '21-149': CFSM + '2024/07/PUBLIC_LAW_NO__21-149.pdf', '19-91': CFSM + '2024/07/PUBLIC-LAW-19-91.pdf',
    '23-140': CFSM + '2024/12/PUBLIC-LAW-NO.-23-140.pdf',
    '17-38': CFSM + '2024/07/PUBLIC-LAW-17-38.pdf', '17-54': CFSM + '2024/07/PUBLIC-LAW-17-54.pdf',
}
INDEX = ['17th-public-laws', '18th-cfsm-public-laws', '19th-cfsm-public-laws', '20th-cfsm-public-laws',
         '21st-cfsm-public-laws', '22nd-public-laws', '23rd-cfsm-public-laws', '24th-public-laws']


def main():
    caps = []
    for host in ('fsmlaw.org/fsm/constitution/', 'www.fsmlaw.org/fsm/constitution/'):
        caps += wayback.captures(host, match='prefix', cache=CACHE)
    pages = {}
    for c in caps:
        u = c.get('original') or c.get('url')
        m = re.search(r'/fsm/constitution/(preamble|article\d+)\.htm$', u)
        if not m or not u.startswith('http'):
            continue
        if re.match(r'https?://(www\.)?fsmlaw\.org\./', u):
            continue
        pages.setdefault(m.group(1), []).append((c['timestamp'], u))
    archive = []
    const = {}
    for p in PAGES:
        lst = sorted(pages[p])
        const[p] = {'newest': {'ts': lst[-1][0], 'url': lst[-1][1]}, 'oldest': {'ts': lst[0][0], 'url': lst[0][1]}}
        archive += [const[p]['newest'], const[p]['oldest']]
    titles = {str(t): {'ts': ts, 'url': TITLE_URL[t]} for t, ts in TITLES.items()}
    archive += list(titles.values())
    out = {'archive': archive,
           'direct': [f'https://www.cfsm.gov.fm/{p}/' for p in INDEX] + sorted(LAWS.values()),
           'constitution': const, 'titles': titles, 'laws': LAWS, 'index': INDEX}
    with open(os.path.join(HERE, 'sources.json.tmp'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    os.replace(os.path.join(HERE, 'sources.json.tmp'), os.path.join(HERE, 'sources.json'))
    for p in PAGES:
        print(p, const[p]['oldest']['ts'], const[p]['newest']['ts'])


if __name__ == '__main__':
    main()
