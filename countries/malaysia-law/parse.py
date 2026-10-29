"""Malaysia: cached sources -> corpus.json (gitlaw_common SCHEMA.md). gitlaw-MY.

Reads only .cache/ (fetch.get(..., offline=True) never touches the network). Deterministic.

Source: the Attorney General's Chambers' Laws of Malaysia portal (lom.agc.gov.my), English text.

Federal Constitution
- v0 2020-10-15: the Reprint "As at 15 October 2020" (first_law null, oldest version available). That reprint
  already prints the words of Act A1603 section 3 (Article 119) although they were not yet in force; its own
  footnotes give the words they replaced, which are put back for this version (FIX_2020).
- Then each amending Act in force after 15 October 2020, on the day the 2025 Reprint's NOTES give, with the
  provisions those NOTES name; the text each Act gave is the 2025 Reprint's text of that provision. Where two Acts
  changed one Article on different days (Article 160), the intermediate text is the 2025 text without what the
  later Act inserted (INTERMEDIATE), as the NOTES describe it.
- Last version 2025-11-30: the Reprint "As at 30 November 2025", as printed. Any remaining difference from the
  version before is a change no Act explains (publisher, unexplained); parse.py stops if one is unexpected.
- Provisions whose words are identical in both reprints take the 2025 line breaks in every version, so a
  different reading of paragraph breaks is never reported as a change.
"""
import hashlib
import json
import os
import re

import fetch
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
B = 'https://lom.agc.gov.my/ilims/upload/portal/akta/'
FC2020 = B + 'LOM/EN/Federal Constitution (Reprint 2020).pdf'
FC2025 = B + 'outputaktap/2630992_BI/REPRINT 2025 - BI WJW250908 Teks B5.pdf'
FC_PAGE = 'https://lom.agc.gov.my/federal-constitution.php'
AMEND_LIST = 'https://lom.agc.gov.my/json-amendment-2024.php'
AMEND_PAGE = 'https://lom.agc.gov.my/principal.php?type=amendment'
PUBLISHER = {'name': "Attorney General's Chambers of Malaysia (Laws of Malaysia)", 'email': 'lom@agc.gov.my.invalid'}

# Laws applied. enacted = royal assent, published = Gazette, both from the portal's list of amending Acts
# (json-amendment-2024.php); in-force days from the 2025 Reprint's NOTES and LIST OF AMENDMENTS.
LAWS = {
    'act-a1603': ('Act A1603', 'Constitution (Amendment) Act 2019', '2019-09-04', '2019-09-10'),
    'act-a1656': ('Act A1656', 'Constitution (Amendment) (No. 2) Act 2022', '2022-05-31', '2022-06-09'),
    'act-a1642': ('Act A1642', 'Constitution (Amendment) Act 2022', '2022-01-19', '2022-01-25'),
    'act-a1663': ('Act A1663', 'Constitution (Amendment) (No. 3) Act 2022', '2022-08-31', '2022-09-06'),
}
# (in force, law, provisions, the 2025 NOTES' words that state it)
STEPS = [
    ('2021-12-15', 'act-a1603', ['art-119'],
     'Art. 119 Clause (1)(a) and (4)(b): substituted by Act A1603, paragraphs 3(a) and 3(b), in force from 15-12-2021'),
    ('2021-12-15', 'act-a1656', ['art-119a'], 'Art. 119A: inserted by Act A1656, section 2, in force from 15-12-2021'),
    ('2022-02-11', 'act-a1642', ['art-001', 'art-160', 'art-161a'],
     'Art. 1(2), 160(2) "Malaysia Day" and "the Federation", 161A(6)(a) and (7): Act A1642, in force from 11-02-2022'),
    ('2022-10-05', 'act-a1663', ['art-010', 'art-048', 'art-049a', 'art-160', 'sch-08'],
     'Art. 10(1) and (3A), 48(6), 49A, 160(2) "political party", Eighth Schedule s. 6(5) and 7A: Act A1663, '
     'in force from 05-10-2022'),
]
# 2020 Reprint footnotes on Article 119: "*NOTE—The words "eighteen years" substituted for the words "twenty-one
# years" are not yet in force" and "*NOTE—The words "is registered" substituted for the words "applies for
# registration" are not yet in force—see paragraph 3(b) of ... Act A1603".
FIX_2020 = {'art-119': [('the age of eighteen years on the qualifying date', 'the age of twenty-one years on the qualifying date'),
                        ('is registered as an absent voter', 'applies for registration as an absent voter')]}
FIX_2020_NOTES = ['The words "eighteen years" substituted for the words "twenty-one years" are not yet in force',
                  'The words "is registered" substituted for the words "applies for registration" are not yet in force']
# Article 160 between Act A1642 (2022-02-11) and Act A1663 (2022-10-05): without the definition of "political
# party", which "Inserted by Act A1663, section 5, in force from 05-10-2022" (2025 NOTES, Art. 160 s.).
INTERMEDIATE = {('art-160', 'act-a1642'): ('"political party" means—', 'and includes a coalition of such societies')}
UNEXPLAINED_2025 = {'sch-02', 'sch-06'}     # a comma after "section 1"; "I," in the Oath of Secrecy


def sha(b):
    return hashlib.sha256(b).hexdigest()


def words(t):
    return ' '.join(t.split())


def as_units(us):
    out = {}
    for u in us:
        assert u['key'] not in out, u['key']
        out[u['key']] = {'label': u['label'], 'kind': u['kind'], 'text': u['text']}
    return out


def footnotes(pdf):
    import fitz
    d = fitz.open(stream=pdf, filetype='pdf')
    return ' '.join(layout.page_footnotes(d[i]) for i in range(d.page_count) if not layout.is_notes_page(d[i]))


def constitution():
    b20 = fetch.get(FC2020, offline=True)
    b25 = fetch.get(FC2025, offline=True)
    u20 = as_units(layout.parse(b20))
    u25 = as_units(layout.parse(b25))
    assert len(u20) > 250 and len(u25) > 250
    fn = footnotes(b20)
    for n in FIX_2020_NOTES:
        assert n in fn, n
    # identical words -> 2025 rendering
    for k, u in u20.items():
        if k in u25 and words(u['text']) == words(u25[k]['text']):
            u20[k] = dict(u25[k])
    for k, reps in FIX_2020.items():
        t = u20[k]['text']
        for a, b in reps:
            assert t.count(a) == 1, (k, a)
            t = t.replace(a, b)
        u20[k] = dict(u20[k], text=t)
    versions = [{'from': '2020-10-15', 'source_url': FC2020, 'sha256': sha(b20), 'units': u20,
                 'note': ('Oldest version available: the Federal Constitution Reprint "As at 15 October 2020" '
                          '(Attorney General\'s Chambers). In Article 119 the reprint prints the words of Act A1603 '
                          'section 3, which its own footnotes mark "not yet in force"; the words they replaced, as '
                          'the footnotes give them, are read here until 15 December 2021.')}]
    state = dict(u20)
    by_day = {}
    for day, law, keys, _ in STEPS:
        by_day.setdefault(day, []).append((law, keys))
    for day in sorted(by_day):
        changes, credits = {}, {}
        for law, keys in by_day[day]:
            for k in keys:
                new = dict(u25[k])
                cut = INTERMEDIATE.get((k, law))
                if cut:
                    lines = new['text'].split('\n')
                    i = next(n for n, l in enumerate(lines) if l.startswith(cut[0]))
                    j = next(n for n, l in enumerate(lines) if l.startswith(cut[1]))
                    new['text'] = '\n'.join(lines[:i] + lines[j + 1:])
                assert state.get(k) != new, (day, law, k)
                changes[k] = new
                credits[k] = [law]
        state.update(changes)
        versions.append({'from': day, 'source_url': FC2025, 'sha256': sha(b25), 'changes': changes,
                         'credits': credits})
    # the 2025 reprint as printed
    diff = sorted(k for k in set(state) | set(u25) if state.get(k) != u25.get(k))
    assert set(diff) == UNEXPLAINED_2025, diff
    versions.append({'from': '2025-11-30', 'source_url': FC2025, 'sha256': sha(b25),
                     'changes': {k: u25[k] for k in diff}, 'credits': {},
                     'note': 'The Federal Constitution Reprint "As at 30 November 2025", as printed. Two small '
                             'differences from the 2020 Reprint that no amending Act explains (a comma in the '
                             'Second Schedule, Part II, section 1(3), and "I," in the Sixth Schedule\'s Oath of '
                             'Secrecy) are committed as unexplained, on the reprint\'s date.'})
    return {
        'slug': 'federal-constitution', 'short': 'FC', 'title': 'Federal Constitution',
        'url': FC_PAGE, 'first_law': None,
        'earlier_laws': [], 'versions': versions,
    }, (b20, b25)


def requests_count(t0='', t1='9999'):
    """Network requests logged in .cache/requests.jsonl between two UTC times (each part counts its own window)."""
    n = 0
    with open(os.path.join(fetch.CACHE, 'requests.jsonl'), encoding='utf-8') as f:
        for line in f:
            if t0 <= json.loads(line)['t'] <= t1:
                n += 1
    return n


FC_WINDOW = ('', '2026-10-29T13:40:00Z')       # the Constitution's research and fetches, before PUBLISH


def main():
    fc, _ = constitution()
    acts = [fc]
    laws = {k: {'label': v[0], 'title': v[1], 'kind': 'law', 'enacted': v[2], 'published': v[3],
                'url': AMEND_PAGE, 'temporary_until': None, 'restores': None, 'note': None}
            for k, v in sorted(LAWS.items())}
    corpus = {
        'country': {
            'code': 'MY', 'name': 'Malaysia', 'slug': 'malaysia', 'lang': 'en', 'tz': 'Asia/Kuala_Lumpur',
            'future_branch': 'future', 'publisher': PUBLISHER,
            'default_in_force_rule': {
                'text': 'Interpretation Acts 1948 and 1967 [Act 388], s. 19(1): "The commencement of an Act or '
                        'subsidiary legislation shall be the date provided in or under the Act or subsidiary '
                        'legislation or, where no date is so provided, the date immediately following the date of '
                        'its publication in pursuance of section 18."',
                'source': 'https://lom.agc.gov.my/ilims/upload/portal/akta/outputaktap/16312_BI/Act 388 (Muktamad).pdf'},
            'licence_note': ("Laws of Malaysia, Attorney General's Chambers of Malaysia (lom.agc.gov.my). The portal's "
                             "terms: \"Copyright 2023 by Attorney General's Chambers, Malaysia, all rights reserved\"; "
                             "legislation \"can be accessed and downloaded at no charge\"; online reprints \"are not the "
                             "reprinted version made pursuant to Section 14 of the Revision of Laws Act 1968 [Act 1]\"; "
                             "a print-out \"is NOT A COPY of the Gazette\"."),
        },
        'sources': [{
            'name': "Laws of Malaysia portal, Attorney General's Chambers of Malaysia (lom.agc.gov.my)",
            'url': 'https://lom.agc.gov.my/', 'retrieved': '2026-10-29', 'requests': requests_count(*FC_WINDOW),
            'licence': "Copyright Attorney General's Chambers, Malaysia, all rights reserved (portal terms, tnc.php); "
                       'free download; the repository is private',
            'notes': 'Read directly with curl (no bot challenge; robots.txt answers HTTP 500). Reprint PDFs with a text '
                     'layer; list tables from the portal\'s POST endpoints, decoded with the key the page publishes '
                     '(fetch.decode mirrors js/responseCrypto.js).'}],
        'laws': laws,
        'acts': acts,
        'applies': [],
        'decisions': DECISIONS,
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py, layout.py and parse.py, chose '
                   'the sources and acts and read the reprints\' NOTES to list which provisions each amending Act '
                   'changed and when (STEPS in parse.py). It wrote no legal text: every line of law comes from a '
                   'cached reprint PDF. parse.py runs no model.'],
    }
    out = os.path.join(HERE, 'corpus.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(out + '.tmp', out)
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', [v['from'] for v in a['versions']])


DECISIONS = [
    'English is built: the Attorney General\'s Chambers publish English reprints of the Federal Constitution and '
    'principal Acts; Malay (Rumi) texts exist alongside and are not built. No Jawi text is used.',
    'Federal Constitution: only the 2020 and 2025 reprints are online in English (the 2006 and 2010 reprints are '
    'Malay only), so the history starts at the Reprint as at 15 October 2020, credited to the publisher as the '
    'oldest version available.',
    'Each change between the two reprints is credited to the amending Act and dated by the in-force day the 2025 '
    'Reprint\'s NOTES give for that provision (STEPS in parse.py); the NOTES name every changed provision.',
    'The 2020 Reprint prints Act A1603 section 3\'s words in Article 119 (voting age eighteen; "is registered" as an '
    'absent voter) although its footnotes say they were not yet in force; for 15 October 2020 to 14 December 2021 '
    'the words the footnotes say they replaced ("twenty-one years", "applies for registration") are read instead.',
    'Article 160 changed twice: Act A1642 (11 February 2022) inserted "Malaysia Day" and replaced "the Federation"; '
    'Act A1663 (5 October 2022) inserted "political party". The text between those days is the 2025 text without '
    'the "political party" definition, which the NOTES say A1663 inserted.',
    'Act A1663: the portal\'s list says section 6 (the Eighth Schedule) commenced on other days in some States '
    '(P.U. (B) 596/2022, 8 December 2022; P.U. (B) 282/2023, 24 July 2023), and the 2025 Reprint\'s list of '
    'amendments says "except s.6 (see ss. 1(3))"; its NOTES date both Eighth Schedule changes 5 October 2022 '
    '(P.U. (B) 476/2022), and that day is used.',
    'Act A1656 (royal assent 31 May 2022) put Article 119A in force from 15 December 2021, before it was enacted; '
    'the in-force day is kept.',
    'Acts A1752 and A1767 (2025) are not yet in force; the 2025 Reprint does not incorporate them (its footnotes say '
    '"has been amended by ..., not yet in force"), and they are not applied.',
    'Layout (layout.py): running heads, NOTES pages and 8 pt footnotes are dropped, with their asterisk markers; small '
    'capitals are read as capitals; the Eleventh Schedule\'s table head "Section Subject Matter", repeated on each '
    'page, is dropped. Provisions whose words are the same in both reprints use the 2025 line breaks throughout.',
    'Two differences between the reprints that no Act explains (Second Schedule Part II s. 1(3) comma; Sixth '
    'Schedule "I,") are committed as unexplained on 30 November 2025, the 2025 Reprint\'s date.',
]

if __name__ == '__main__':
    main()
