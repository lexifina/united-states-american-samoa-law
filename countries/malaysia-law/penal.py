"""Penal Code [Act 574] -> corpus.d/30-penal-code.json. gitlaw-MY.

Reads only .cache/. Deterministic.

- v0 2023-07-04: the updated Reprint "As at 4 July 2023" (latest amendment Act 846, in force 4 July 2023), the oldest
  version available here (first_law null).
- Then the three later amending Acts, from their official English PDFs on the portal, applied as their own words
  say ("substituting for section 305 the following section", "inserting after section 424 the following sections",
  "deleting section 309"), each on the commencement day the portal's list of amending Acts gives:
    Act A1721 (2024-10-30, P.U. (B) 433/2024): new ss. 424A-424D;
    Act A1750 (2025-07-11): new ss. 507B-507G;
    Act A1691 (2025-09-10, P.U. (B) 328/2025): ss. 305 and 306 substituted, s. 309 deleted.
  amending.py reads the quoted sections. parse checks that every section of each Act is accounted for.
- No later English reprint is online, so the text after 4 July 2023 is the replay of these Acts and is not checked
  against a consolidation; verify.py checks every applied paragraph against the amending Act's PDF.
"""
import hashlib
import json
import os
import re

import fitz

import amending
import fetch
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
B = 'https://lom.agc.gov.my/ilims/upload/portal/akta/'
R2023 = B + 'outputaktap/1841145_BI/WJW231011 Act 574.pdf'
ACTS = [  # key, label, title, royal assent, Gazette, in force, PDF, sections of the amending Act
    ('act-a1721', 'Act A1721', 'Penal Code (Amendment) Act 2024', '2024-09-11', '2024-09-25', '2024-10-30',
     B + 'outputaktap/2368163_BI/Act A1721.pdf', 2),
    ('act-a1750', 'Act A1750', 'Penal Code (Amendment) Act 2025', '2025-02-25', '2025-03-07', '2025-07-11',
     B + 'outputaktap/2731052_BI/Penal Code (Amendment) Act 2025 A1750.pdf', 2),
    ('act-a1691', 'Act A1691', 'Penal Code (Amendment) (No. 2) Act 2023', '2023-08-05', '2023-08-11', '2025-09-10',
     B + 'outputaktap/1845383_BI/A1691 BI.pdf', 4),
]
WINDOW = ('2026-10-29T14:10:00Z', '2026-10-29T15:00:00Z')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def act_sections(pdf):
    """Numbers of the amending Act's own sections (bold "N." at a line start, outside quotations)."""
    d = fitz.open(stream=pdf, filetype='pdf')
    nums = set()
    for i in range(d.page_count):
        for ln in layout.page_lines(d[i]):
            t = layout.clean(ln['text'])
            m = re.match(r'^(\d+)\.\s', t)
            if ln['bold'] and m and ln['x'] < 100:
                nums.add(int(m.group(1)))
    return nums


def build():
    b23 = fetch.get(R2023, offline=True)
    u23 = {}
    for u in layout.parse(b23, 'sec', chapters=True):
        assert u['key'] not in u23, u['key']
        u23[u['key']] = {'label': u['label'], 'kind': u['kind'], 'text': u['text']}
    assert len(u23) > 600
    versions = [{'from': '2023-07-04', 'source_url': R2023, 'sha256': sha(b23), 'units': u23,
                 'note': 'Oldest version available: the Penal Code updated Reprint "As at 4 July 2023" (Attorney '
                         "General's Chambers), latest amendment Act 846 in force 4 July 2023."}]
    state = dict(u23)
    laws = {}
    for key, label, title, ra, pub, day, url, nsec in ACTS:
        pdf = fetch.get(url, offline=True)
        ops = amending.ops(pdf)
        assert sorted({o[0] for o in ops}) == list(range(2, nsec + 1)), (key, [o[0] for o in ops])
        changes = {}
        for sec, op, target, us in ops:
            tk = amending.key(target)
            if op == 'delete':
                assert tk in state, (key, tk)
                changes[tk] = None
            elif op == 'substitute':
                assert tk in state and list(us) == [tk], (key, tk, list(us))
                changes[tk] = us[tk]
            else:
                assert tk in state and all(k not in state for k in us), (key, tk, list(us))
                changes.update(us)
        for k, v in changes.items():
            if v is None:
                state.pop(k)
            else:
                state[k] = v
        versions.append({'from': day, 'source_url': url, 'sha256': sha(pdf), 'changes': changes,
                         'credits': {k: [key] for k in changes}})
        laws[key] = {'label': label, 'title': title, 'kind': 'law', 'enacted': ra, 'published': pub, 'url': url,
                     'temporary_until': None, 'restores': None, 'note': None}
    versions.sort(key=lambda v: v['from'])
    act = {'slug': 'penal-code', 'short': 'PC', 'title': 'Penal Code [Act 574]', 'url': R2023, 'first_law': None,
           'earlier_laws': ['act-846'], 'versions': versions}
    laws['act-846'] = {'label': 'Act 846', 'title': 'Act 846 (latest amendment in the Reprint as at 4 July 2023)',
                       'kind': 'law', 'enacted': None, 'published': None, 'url': R2023, 'temporary_until': None,
                       'restores': None, 'note': None}
    return act, laws


def main():
    import parse
    act, laws = build()
    part = {
        'sources': [{
            'name': "Laws of Malaysia portal, Attorney General's Chambers: Penal Code updated reprint (as at 4 July "
                    "2023) and Acts A1721, A1750, A1691",
            'url': 'https://lom.agc.gov.my/principal.php?type=updated', 'retrieved': '2026-10-29',
            'requests': parse.requests_count(*WINDOW),
            'licence': "Copyright Attorney General's Chambers, Malaysia, all rights reserved (portal terms); amending "
                       "Acts printed by Percetakan Nasional Malaysia Berhad (publisher's copyright)",
            'notes': 'Read directly; PDFs with a text layer. Commencement days from the portal\'s list of amending Acts '
                     '(json-amendment-2024.php).'}],
        'laws': laws,
        'acts': [act],
        'decisions': [
            'Penal Code: the updated Reprint as at 4 July 2023 is the oldest English version online here and the '
            'history starts there (first_law null, crediting the publisher; it names Act 846 as the latest '
            'amendment). Its chapter headings are units chapter-NN and its centred cross-headings ("Mischief") units '
            'xh-<next section>.',
            'Penal Code: Acts A1721, A1750 and A1691 are applied from their own official PDFs by the operations they '
            'state, on the commencement days the portal gives (30 October 2024, 11 July 2025, 10 September 2025); '
            'A1691 was enacted in 2023 but came into force last. No English reprint after July 2023 is online, so '
            'the result is not compared with a consolidation.',
            'Penal Code: letter-spaced justified lines in the amending Acts ("a  l i c e n s e d") are rejoined '
            '(amending.despace); section 309, deleted by A1691, is removed rather than shown as "(Deleted)".',
        ],
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote penal.py and amending.py and chose the '
                   'acts; the amendment operations are read from the Acts by code. No model wrote legal text.'],
    }
    d = os.path.join(HERE, 'corpus.d')
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, '30-penal-code.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(part, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(out + '.tmp', out)
    print(act['slug'], [(v['from'], len(v.get('changes', v.get('units', {})))) for v in act['versions']])


if __name__ == '__main__':
    main()
