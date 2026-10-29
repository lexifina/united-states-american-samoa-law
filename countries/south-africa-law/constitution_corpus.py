"""Turns the Constitution's history (constitution.history()) into the corpus.json act, laws and decisions,
and checks today's text against the Department of Justice consolidation (verify)."""
from __future__ import annotations

import hashlib
import re

from constitution import (AMENDMENTS, JUSTICE_PDF, LL, LL_CAPTURES, PLACEHOLDER, eighteenth, history,
                          hyphen_vocab, justice_units, original, unit_text)


def as_unit(key: str, u: dict) -> dict:
    if key.startswith('section-'):
        kind, label = 'section', u['label']
    elif key == 'preamble':
        kind, label = 'preamble', 'Preamble'
    else:
        kind, label = 'schedule', u['label']
    return {'label': label, 'kind': kind, 'text': unit_text(u)}


def build():
    hist, gaps, raw = history()
    sha = hashlib.sha256(raw).hexdigest()
    laws = {
        'act-1996-108': {'label': 'Act 108 of 1996', 'title': 'Constitution of the Republic of South Africa, 1996',
                         'kind': 'law', 'enacted': '1996-12-10', 'published': '1996-12-18', 'url': JUSTICE_PDF,
                         'temporary_until': None, 'restores': None, 'note': None},
        'proc-r6-1997': {'label': 'Proc. R6 of 1997',
                         'title': 'Commencement: Constitution of the Republic of South Africa, 1996',
                         'kind': 'decree', 'enacted': '1997-01-22', 'published': None,
                         'url': 'https://www.justice.gov.za/constitution/history/act/AMEND/PROC0697.PDF',
                         'temporary_until': None, 'restores': None,
                         'note': 'A presidential proclamation under s. 243 of the Constitution: the Constitution, except '
                                 's. 160(1)(b), comes into effect on 4 February 1997, and s. 160(1)(b) on 30 June 1997.'},
    }
    for k, (label, title, actno, enacted, published, inforce, url) in AMENDMENTS.items():
        laws[k] = {'label': label, 'title': title + (f' ({actno})' if actno else ''), 'kind': 'law',
                   'enacted': enacted, 'published': published, 'url': url, 'temporary_until': None,
                   'restores': None, 'note': None}
    # Department of Justice amendments poster: the 13th "amends the Constitution ... so as to correct invalid
    # provisions relating to the re-determination of the provincial boundary between the Eastern Cape and KwaZulu-Natal"
    laws['a23-2007']['note'] = ('It re-enacted the Eastern Cape and KwaZulu-Natal determinations in Schedule 1A "so as to '
                                'correct invalid provisions relating to the re-determination of the provincial boundary '
                                'between the Eastern Cape and KwaZulu-Natal" (Department of Justice). The words of '
                                'Schedule 1A did not change.')
    starts: dict[str, dict] = {}
    events: dict[str, dict[str, tuple]] = {}
    for k, h in hist.items():
        for i, (d, u, group, how) in enumerate(h):
            if i == 0 and not group and d == '1997-02-04':
                starts[k] = u
            else:
                events.setdefault(d, {})[k] = (u, group or ['act-1996-108'], how)
    v0 = {k: as_unit(k, u) for k, u in sorted(starts.items())}
    versions = [
        {'from': '1997-02-04', 'source_url': JUSTICE_PDF, 'sha256': sha, 'units': v0,
         'note': 'The Constitution as adopted (text from gov.za: "As adopted on 8 May 1996 and amended on 11 October '
                 '1996 by the Constitutional Assembly"), in force from 4 February 1997 (Proc. R6 of 1997). Sections '
                 '213-216, 218 and 226-230 are added on 1 January 1998 (s. 243(5)); s. 160(1)(b) on 30 June 1997.'},
        {'from': '1997-02-04', 'same_day': True, 'source_url': JUSTICE_PDF, 'sha256': sha,
         'credits': {k: ['proc-r6-1997'] for k in sorted(v0)}},
    ]
    gap_days: dict[str, list[str]] = {}
    for g in gaps:
        m = re.match(r'^(\S+)(?: item \d+)? from (\d{4}-\d{2}-\d{2})', g)
        if m:
            gap_days.setdefault(m.group(2), []).append(m.group(1))
    for d in sorted(events):
        changes, credits = {}, {}
        for k, (u, cr, how) in sorted(events[d].items()):
            changes[k] = as_unit(k, u) if u is not None else None
            credits[k] = sorted(set(cr))
        v = {'from': d, 'source_url': JUSTICE_PDF, 'sha256': sha, 'changes': changes, 'credits': credits}
        if d == '1997-02-04':
            v['same_day'] = True
        if d in gap_days:
            v['note'] = ('No text layer or consolidation gives the wording in force from this day for: '
                         + ', '.join(sorted(set(gap_days[d]))) + f'. It reads "{PLACEHOLDER}" until the next '
                         'version that a source gives.')
        versions.append(v)
    act = {'slug': 'constitution', 'short': 'Constitution',
           'title': 'Constitution of the Republic of South Africa, 1996', 'url': JUSTICE_PDF,
           'first_law': 'act-1996-108', 'earlier_laws': [], 'versions': versions}
    used_ll = sorted({f'{k} @{d}' for k, h in hist.items() for d, u, g, how in h
                      if how.startswith(('LawLibrary', 'item 22'))})
    provenance = [f'{k} {d}: {how}' for k, h in sorted(hist.items()) for d, u, g, how in h if g]
    decisions = [
        'Constitution, sources: the 1996 text as adopted from gov.za (Wayback captures 1999-2000 of '
        'gov.za/constitution/1996/*.htm, a page GCIS never updated); intermediate wordings from GCIS consolidations on '
        'info.gov.za (Wayback captures 2004-2012) chosen by their amendment notes; the text from each provision\'s last '
        'amendment from the Department of Justice consolidation (justice.gov.za SAConstitution-web-eng.pdf, up to the '
        '17th Amendment), with the 18th Amendment applied from its born-digital gazette text.',
        'Constitution: where no government source gives an intermediate wording, a LawLibrary (Laws.Africa) '
        'point-in-time expression read from a pinned Wayback capture fills it (allowed by the user for gaps; the site '
        'itself was never fetched). Licence CC BY-NC 4.0, attribution: LawLibrary (lawlibrary.org.za). Used for: '
        + '; '.join(used_ll) + '.',
        'Constitution: the amendment Acts of 1997-2008 on gov.za and justice.gov.za are scans whose text layers are OCR; '
        'under the no-OCR rule their wording is not used. Only the 16th, 17th and 18th Amendment Acts are born-digital.',
        'Constitution, dates: each amendment is dated by its commencement: its own clause, a proclamation, or '
        'publication (s. 81). Sources: the Department of Justice amendments poster (20yearsConstitution-Amendments_poster.pdf), '
        'Proc. R6 of 1997, Proc. R20, R21 and R22 of 2009, Proc. R35 of 2013, and Proclamation Notice 321 of 2026 with '
        'its erratum Notice 324 of 2026 (signed 26 March 2026, published 26 June 2026 "with immediate effect", so in '
        'force 26 June 2026).',
        'Constitution: the Seventh Amendment is in force from 26 April 2002 except its ss. 4 and 7 (ss. 163 and 221 of '
        'the Constitution, per the consolidation\'s notes), from 1 December 2003 (DoJ poster).',
        'Constitution: the Twelfth Amendment is in force from 1 March 2006, except s. 103(3) as inserted by its s. 1, in '
        'force on publication, 23 December 2005 (s. 5(2) of that Act).',
        'Constitution: s. 4 of the Second Amendment (Act 65 of 1998) substitutes "South African Human Rights Commission" '
        'for "Human Rights Commission" wherever it occurs; that substitution is applied by code on 7 October 1998.',
        'Constitution: the Eighth Amendment\'s Schedule 6A (municipal floor-crossing, 20 June 2002) was renumbered 6B by '
        'the Tenth Amendment (20 March 2003), which inserted a new Schedule 6A; both were repealed on 17 April 2009 '
        '(14th and 15th Amendments).',
        'Constitution: one file per section, the Preamble and each Schedule. A provision not yet in force is absent '
        'until it commences.',
        'Constitution, gaps (placeholder "' + PLACEHOLDER + '"): ' + ' | '.join(gaps),
        'Constitution: typography follows the Department of Justice consolidation wherever a historical line has the '
        'same words, so diffs show changes of words.',
        'Constitution: the 1999 and 2004-2012 GCIS web pages sometimes number lists differently from the DoJ '
        'consolidation; restarted lettered lists are renumbered by code, but a few label differences remain and show as '
        'changes inside amendment commits (s. 61(2)(b), s. 100, s. 168(3), s. 196).',
        'Constitution: the Citation of Constitutional Laws Act 5 of 2005 renamed the amendment Acts; it changed no '
        'words of the Constitution\'s provisions and has no commit.',
        'Constitution, provenance of every amended version: ' + ' | '.join(provenance),
    ]
    sources = [
        {'name': 'Department of Justice: Constitution consolidation', 'url': JUSTICE_PDF, 'retrieved': '2026-10-28',
         'requests': 1, 'licence': 'justice.gov.za terms: non-commercial informational or reference use (see README); '
         'the text of the Constitution is not subject to copyright (Copyright Act 98 of 1978 s. 12(8)(a)).',
         'notes': 'Born-digital PDF, up to the 17th Amendment.'},
        {'name': 'gov.za / info.gov.za (GCIS), Wayback captures 1999-2012',
         'url': 'https://web.archive.org/web/19991013161422/http://www.gov.za:80/constitution/1996/96cons.htm',
         'retrieved': '2026-10-28', 'requests': 0,
         'licence': 'gov.za terms: non-commercial informational or reference use.',
         'notes': 'Captures pinned by timestamp; see decisions for which capture gives which version.'},
        {'name': 'LawLibrary (Laws.Africa), Wayback captures only', 'url': LL + '1998-10-07', 'retrieved': '2026-10-28',
         'requests': len(LL_CAPTURES), 'licence': 'CC BY-NC 4.0; attribution: LawLibrary (lawlibrary.org.za)',
         'notes': 'Gap fill only; captures: ' + ', '.join(f'{d}={t}' for d, t in sorted(LL_CAPTURES.items()))},
    ]
    return act, laws, decisions, sources


def verify(units: dict, words, compare) -> list[dict]:
    """Today's text (last version) against the DoJ consolidation with the 18th Amendment applied."""
    final, _ = justice_units(hyphen_vocab(original()))
    final = {k: u for k, u in final.items() if u['lines']}
    final['section-006'] = eighteenth(final)
    res = []
    for k in sorted(set(units) | set(final)):
        ours = words(units[k]['text']) if k in units else []
        ref = words(unit_text(final[k])) if k in final else []
        res.append(compare(k, ours, ref))
    return res
