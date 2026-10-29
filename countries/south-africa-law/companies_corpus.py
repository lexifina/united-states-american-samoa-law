"""The Companies Act 71 of 2008 as a corpus.json act (versions as deltas), and its check against the DoJ text."""
from __future__ import annotations

import hashlib
import re

import companies as C
import constitution as K


def as_unit(key: str, u: dict) -> dict:
    kind = 'section' if key.startswith('section-') else 'schedule'
    return {'label': u['label'], 'kind': kind, 'text': K.unit_text(u)}


def build():
    hist, gaps, raw, doj, gaz, final = C.history()
    sha = hashlib.sha256(raw).hexdigest()
    laws = {
        'act-2008-71': {'label': 'Act 71 of 2008', 'title': 'Companies Act, 2008', 'kind': 'law',
                        'enacted': '2009-04-08', 'published': '2009-04-09', 'url': C.GAZ_URL,
                        'temporary_until': None, 'restores': None, 'note': None},
        'proc-r32-2011': {'label': 'Proc. R32 of 2011', 'title': 'Commencement of the Companies Act, 2008',
                          'kind': 'decree', 'enacted': None, 'published': '2011-04-26', 'url': C.DOJ_URL,
                          'temporary_until': None, 'restores': None,
                          'note': 'Proc. R32 in GG 34239 of 26 April 2011 (DoJ commencement table): the whole Act, except '
                                  's. 11(1)(a)(ii) and (iii), in force on 1 May 2011. It changed no words.'},
    }
    for key, (lk, label, title, enacted, published, url) in C.AMENDING.items():
        laws[lk] = {'label': label, 'title': title, 'kind': 'law', 'enacted': enacted, 'published': published,
                    'url': url, 'temporary_until': None, 'restores': None, 'note': None}
    laws['act-2011-3']['note'] = None
    starts, events = {}, {}
    for k, h in hist.items():
        for i, (d, u, group, how) in enumerate(h):
            if i == 0 and not group:
                starts[k] = u
            else:
                events.setdefault(d, {})[k] = (u, group, how)
    v0 = {k: as_unit(k, u) for k, u in sorted(starts.items())}
    versions = [
        {'from': '2011-05-01', 'source_url': C.GAZ_URL, 'sha256': sha, 'units': v0,
         'note': 'The Act as published in Government Gazette 32121 of 9 April 2009, in force from 1 May 2011 (Proc. R32 '
                 'of 2011), except s. 11(1)(a)(ii) and (iii), which commence on 1 May 2014 (s. 225(2)).'},
        {'from': '2011-05-01', 'same_day': True, 'source_url': C.GAZ_URL, 'sha256': sha,
         'credits': {k: ['proc-r32-2011'] for k in sorted(v0)}},
    ]
    gap_days = {}
    for g in gaps:
        m = re.match(r'^(\S+) from (\d{4}-\d{2}-\d{2})', g)
        if m:
            gap_days.setdefault(m.group(2), []).append(m.group(1))
    for d in sorted(events):
        changes, credits = {}, {}
        for k, (u, group, how) in sorted(events[d].items()):
            changes[k] = as_unit(k, u) if u is not None else None
            credits[k] = sorted(set(group))
        v = {'from': d, 'source_url': C.DOJ_URL, 'sha256': sha, 'changes': changes, 'credits': credits}
        if d == '2011-05-01':
            v['same_day'] = True
        if d in gap_days:
            v['note'] = ('No source gives the wording in force from this day for: ' + ', '.join(sorted(set(gap_days[d])))
                         + f'. It reads "{K.PLACEHOLDER}" until the next version a source gives.')
        versions.append(v)
    act = {'slug': 'companies-act', 'short': 'Companies Act', 'title': 'Companies Act 71 of 2008', 'url': C.GAZ_URL,
           'first_law': 'act-2008-71', 'earlier_laws': [], 'versions': versions}
    pending = sorted({k for k, u in doj.items() if u.get('pending')})
    provenance = [f'{k} {d}: {how}' for k, h in sorted(hist.items()) for d, u, g, how in h if g]
    decisions = [
        'Companies Act, as enacted: Government Gazette 32121 of 9 April 2009 (gov.za PDF, born-digital text layer). '
        'Commencement: 1 May 2011 (Proc. R32 of 2011); s. 11(1)(a)(ii) and (iii) on 1 May 2014 (s. 225(2), inserted by '
        'Act 3 of 2011). The DoJ table names s. 11(1)(a)(ii) and (iii), and so does s. 225(2); those are used.',
        'Companies Act, credits and dates: every change is credited to the Act its Department of Justice amendment note '
        'names, on the day in that note ("wef"); the DoJ table gives the commencements (Act 3 of 2011: 1 May 2011 and '
        '1 May 2014; Act 19 of 2012: 3 June 2013; Act 22 of 2022: 31 December 2022 and 1 April 2023; Act 23 of 2021: '
        '1 June 2023; Acts 16 and 17 of 2024: 27 December 2024).',
        'Companies Act, today\'s words: the Department of Justice consolidation (justice.gov.za 2008-071.pdf), set in the '
        'gazette\'s typography (quotes, dashes, "section 118(3)") wherever a line\'s words are unchanged.',
        'Companies Act, wordings between amendments: LawLibrary point-in-time expressions read from pinned Wayback '
        'captures (complete ones: 2014-05-01, 2023-06-01). LawLibrary\'s text of this Act was made by OCR from the '
        'gazette scan; a line that differs from the gazette or the DoJ text only by a known misreading (live/five, '
        'line/fine, held/field, fillfil/fulfil) or by spacing takes the official line.',
        'Companies Act, gaps (placeholder): ' + ' | '.join(gaps) + '. LawLibrary has no complete capture for 2011-05-01 '
        'to 2013-06-03.',
        'Companies Act: provisions of Act 16 of 2024 not yet put into operation (DoJ "NB" notes, "see PENDLEX") are '
        'not in the text and not on the future branch, because no date is set. Sections with such notes: '
        + ', '.join(pending) + '.',
        'Companies Act: sections that no note says were amended keep the gazette text. Where the consolidation differs '
        'from the gazette in such a section (s. 96(1)(c)(ii) drops "or"; s. 117(1)(j)(ii) reads "a[n]"), those are the '
        'consolidator\'s editorial corrections; verify.py lists them.',
        'Companies Act, provenance of every amended version: ' + ' | '.join(provenance),
    ]
    sources = [
        {'name': 'Government Gazette 32121 (via gov.za)', 'url': C.GAZ_URL, 'retrieved': '2026-10-28', 'requests': 1,
         'licence': 'gov.za terms: non-commercial informational or reference use; no copyright in the Act (s. 12(8)(a)).',
         'notes': 'Born-digital gazette of the Act as assented.'},
        {'name': 'Department of Justice consolidation of the Companies Act', 'url': C.DOJ_URL, 'retrieved': '2026-10-28',
         'requests': 1, 'licence': 'justice.gov.za terms: non-commercial informational or reference use.',
         'notes': 'Juta export (2025); commencement table and amendment notes with "wef" dates; today\'s words.'},
        {'name': 'LawLibrary (Laws.Africa), Wayback captures only', 'url': C.LL + '2014-05-01', 'retrieved': '2026-10-28',
         'requests': len(C.LL_CAPTURES), 'licence': 'CC BY-NC 4.0; attribution: LawLibrary (lawlibrary.org.za)',
         'notes': 'Captures: ' + ', '.join(f'{d}={t}' for d, t in sorted(C.LL_CAPTURES.items()))},
    ]
    return act, laws, decisions, sources


def verify(units: dict, words, compare) -> list[dict]:
    final = C.doj_units()
    res = []
    for k in sorted(set(units) | set(final)):
        ours = words(units[k]['text']) if k in units else []
        ref = words(K.unit_text(final[k])) if k in final else []
        res.append(compare(k, ours, ref))
    return res
