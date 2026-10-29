"""Personal Data Protection Act 2010 [Act 709] -> corpus.d/20-pdpa.json. gitlaw-MY.

Reads only .cache/. Deterministic.

- v0 2013-11-15: the First Reprint "As at 1 July 2023", whose LIST OF SECTIONS AMENDED reads "- NIL -": the Act as
  enacted (royal assent 2 June 2010, Gazette 10 June 2010), in force from 15 November 2013 [P.U. (B) 464/2013].
  (The portal's original "Act 709 ori.pdf" answers HTTP 500.)
- Then the Personal Data Protection (Amendment) Act 2024 [Act A1727], on the three days the Reprint "As at
  15 September 2026" gives in its LIST OF SECTIONS AMENDED (and its front page: 1 January 2025: A1727 ss. 7, 11, 13
  and 14; 1 April 2025: ss. 2-5, 8, 10 and 12; 1 June 2025: ss. 6 and 9). Each changed provision takes the 2026
  Reprint's text. Provisions not in that list changed only by A1727 s. 2 (the general amendment, "data user(s)" ->
  "data controller(s)", in force 1 April 2025); parse checks that the substitution alone explains each of them.
- The result must equal the 2026 Reprint as printed; the build stops otherwise.
"""
import hashlib
import json
import os

import fetch
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
B = 'https://lom.agc.gov.my/ilims/upload/portal/akta/'
R2023 = B + 'outputaktap/1726091_BI/ACT 709-REPRINT 2023.pdf'
R2026 = B + 'outputaktap/3301061_BI/Act 709 (Reprint 2026).pdf'
A1727 = B + 'outputaktap/2430673_BI/Act A1727.pdf'
WINDOW = ('2026-10-29T13:40:00Z', '2026-10-29T14:10:00Z')
# LIST OF SECTIONS AMENDED, Reprint 2026: section -> in force from (A1727)
LISTED = {'sec-004': '2025-04-01', 'sec-005': '2025-04-01', 'sec-009': '2025-04-01',
          'part-02-division-01a': '2025-06-01', 'sec-012a': '2025-06-01', 'sec-012b': '2025-06-01',
          'sec-021': '2025-04-01', 'sec-043a': '2025-06-01', 'sec-048': '2025-04-01', 'sec-067': '2025-01-01',
          'sec-129': '2025-04-01', 'sec-136': '2025-01-01'}
LIST_ROWS = ['4 A1727 01-04-2025', '5 A1727 01-04-2025', '9 A1727 01-04-2025', 'Division 1a A1727 01-06-2025',
             '12a A1727 01-06-2025', '12b A1727 01-06-2025', '21 A1727 01-04-2025', '43a A1727 01-06-2025',
             '48 A1727 01-04-2025', '67 A1727 01-01-2025', '129 A1727 01-04-2025', '136 A1727 01-01-2025',
             'General amendment A1727 01-04-2025']
GENERAL_DAY = '2025-04-01'
PAIRS = [('data users', 'data controllers'), ('data user', 'data controller'), ('Data Users', 'Data Controllers'),
         ('Data User', 'Data Controller'), ('Data users', 'Data controllers'), ('Data user', 'Data controller')]


def words(t):
    return ' '.join(t.split())


def general(t):
    for a, b in PAIRS:
        t = t.replace(a, b)
    return t


def units(pdf):
    out = {}
    for u in layout.parse(pdf, 'sec'):
        assert u['key'] not in out, u['key']
        out[u['key']] = {'label': u['label'], 'kind': u['kind'], 'text': u['text']}
    return out


def build():
    import fitz
    b23, b26 = fetch.get(R2023, offline=True), fetch.get(R2026, offline=True)
    d23, d26 = fitz.open(stream=b23, filetype='pdf'), fitz.open(stream=b26, filetype='pdf')
    assert '- NIL -' in d23[d23.page_count - 1].get_text()
    last = ' '.join(' '.join(d26[i].get_text() for i in range(d26.page_count - 2, d26.page_count)).split())
    for row in LIST_ROWS:
        assert row in last, row
    u23, u26 = units(b23), units(b26)
    for k, u in u23.items():
        if k in u26 and words(u['text']) == words(u26[k]['text']):
            u23[k] = dict(u26[k])                          # same words: the 2026 line breaks
    sha = lambda b: hashlib.sha256(b).hexdigest()
    assert not set(u23) - set(u26), set(u23) - set(u26)
    days = {}
    for k in sorted(u26):
        if u23.get(k) == u26[k]:
            continue
        if k in LISTED:
            day = LISTED[k]
        else:
            assert k in u23 and words(general(u23[k]['text'])) == words(u26[k]['text']), k
            day = GENERAL_DAY
        if day != GENERAL_DAY and k in u23:
            assert 'data user' not in u23[k]['text'].lower(), k   # no general-amendment words on another day
        days.setdefault(day, {})[k] = u26[k]
    versions = [{'from': '2013-11-15', 'source_url': R2023, 'sha256': sha(b23), 'units': u23,
                 'note': ('The Personal Data Protection Act 2010 as enacted, read from the First Reprint "As at 1 July '
                          '2023" (Commissioner of Law Revision), whose list of sections amended is "NIL"; in force '
                          'from 15 November 2013 [P.U. (B) 464/2013].')}]
    for day in sorted(days):
        versions.append({'from': day, 'source_url': R2026, 'sha256': sha(b26), 'changes': days[day],
                         'credits': {k: ['act-a1727'] for k in days[day]}})
    state = dict(u23)
    for v in versions[1:]:
        state.update(v['changes'])
    assert state == u26
    versions[-1]['note'] = ('With this change the Act reads as the Reprint "As at 15 September 2026" (Commissioner '
                            'of Law Revision), word for word.')
    return {'slug': 'personal-data-protection-act', 'short': 'PDPA',
            'title': 'Personal Data Protection Act 2010 [Act 709]', 'url': R2026,
            'first_law': 'act-709', 'earlier_laws': [], 'versions': versions}


def main():
    import parse
    act = build()
    part = {
        'sources': [{
            'name': "Laws of Malaysia portal, Attorney General's Chambers: Act 709 reprints (2023, 2026) and Act A1727",
            'url': 'https://lom.agc.gov.my/principal.php?type=updated', 'retrieved': '2026-10-29',
            'requests': parse.requests_count(*WINDOW),
            'licence': "Copyright Attorney General's Chambers, Malaysia, all rights reserved (portal terms); reprints "
                       'published by the Commissioner of Law Revision under the Revision of Laws Act 1968; Act A1727 '
                       "printed by Percetakan Nasional Malaysia Berhad (publisher's copyright, all rights reserved)",
            'notes': 'Read directly; PDFs with a text layer. The original Act PDF (outputaktap/Act 709 ori.pdf) answers '
                     'HTTP 500.'}],
        'laws': {
            'act-709': {'label': 'Act 709', 'title': 'Personal Data Protection Act 2010', 'kind': 'law',
                        'enacted': '2010-06-02', 'published': '2010-06-10', 'url': R2023,
                        'temporary_until': None, 'restores': None, 'note': None},
            'act-a1727': {'label': 'Act A1727', 'title': 'Personal Data Protection (Amendment) Act 2024', 'kind': 'law',
                          'enacted': '2024-10-09', 'published': '2024-10-17', 'url': A1727,
                          'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [act],
        'decisions': [
            'PDPA: the First Reprint as at 1 July 2023 lists no amended sections ("- NIL -"), so its text is taken as '
            'the Act as enacted and dated from commencement, 15 November 2013 (P.U. (B) 464/2013, from the portal\'s '
            'list of principal Acts); the original Act PDF on the portal answers HTTP 500. The long title and '
            'enacting words before Part I are not included.',
            'PDPA: Act A1727 is applied on the days the 2026 Reprint\'s LIST OF SECTIONS AMENDED gives per section '
            '(1 January, 1 April, 1 June 2025). Sections not in that list differ only by the general amendment of '
            'A1727 s. 2 ("data user(s)" -> "data controller(s)"; parse checks this word for word) and go on its day, '
            '1 April 2025. A1727 s. 7 changes only the national language text (s. 16(3)) and so nothing here.',
            'PDPA: the 2026 Reprint\'s editorial NOTE quoting A1727 s. 14 (saving), printed under s. 146, is left '
            'out; A1727 s. 14 is not a provision of Act 709.',
        ],
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote pdpa.py and read Act A1727 and the '
                   'reprint\'s lists to map each change to its day (LISTED, LIST_ROWS). No model wrote legal text.'],
    }
    d = os.path.join(HERE, 'corpus.d')
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, '20-pdpa.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(part, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(out + '.tmp', out)
    print(act['slug'], len(act['versions']), 'versions', [(v['from'], len(v.get('changes', v.get('units', {}))))
                                                          for v in act['versions']])


if __name__ == '__main__':
    main()
