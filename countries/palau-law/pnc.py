"""Palau National Code titles for corpus.json (imported by parse.py; reads the cache only).

Each title is read from the Code Commission's PDFs:
- every full-title edition in the Drive's "Former Supplements" archive (1st Edition through 9/30/94; 15th, 16th,
  17th and 18th Supplements) and the current title (current as of 09/30/2026);
- the 1st and 2nd Supplements are pocket parts holding only changed sections; they are not used (see decisions).

A version is dated by its edition's "through" date (the date in the folder name, which the Certificate of
Authenticity gives as the date the Commission's approved version runs "through"); see decisions. A section that
changed between two editions is credited to the RPPLs that its "Source" note in the later edition names and the
earlier one did not; if no new RPPL is named, the change is the publisher's ("unexplained").
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import fetch
import layout

HERE = Path(__file__).resolve().parent
DRIVE_FILE = 'https://drive.google.com/uc?export=download&id={}'
VIEW = 'https://drive.google.com/file/d/{}/view'
IDX = json.loads((HERE / '.cache' / 'drive' / 'index.json').read_text(encoding='utf-8'))

HEAD = re.compile(r'^§\s?(\d+)([A-Za-z]?)((?:\.\d+)?)\.\s+(.*)$')
RPPL = re.compile(r'RPPL\s+(?:No\.\s*)?(\d{1,2})\s*-\s*(\d{1,3})')

EDITIONS = [  # (folder name, through date, file-name pattern, layout)
    ('1st Edition (9/30/94)', '1994-09-30', 'ARCHIVES (First Ed) Title {n}.pdf', 'typeset'),
    ('15th Supplement - PNC (5/14/21)', '2021-05-14', 'ARCHIVES (15th) {n} PNCA.pdf', 'typeset'),
    ('16th Supplement - PNC (5/26/21)', '2021-05-26', 'ARCHIVES (16th) {n} PNCA.pdf', 'typeset'),
    ('17th Supplement - PNC (6/2/22)', '2022-06-02', 'ARCHIVES (17th) {n} PNCA.pdf', 'typeset'),
    ('18th Supplement - PNC (4/25/23)', '2023-04-25', 'ARCHIVES (18th) {n} PNCA.pdf', 'typeset'),
]
CURRENT_DATE = '2026-09-30'

TITLES = [
    {'n': 17, 'slug': 'title-17-penal-code', 'short': '17 PNC', 'title': 'Palau National Code, Title 17: Penal Code',
     'current': '17 PNC - Penal Code'},
    {'n': 1, 'slug': 'title-01-general-provisions', 'short': '1 PNC', 'title': 'Palau National Code, Title 1: General Provisions',
     'current': '1 PNC - General Provisions'},
]


def key_of(num: str, letter: str, dec: str) -> str:
    k = f's-{int(num):04d}'
    if letter:
        k += '-' + letter.lower()
    if dec:
        k += '-' + dec[1:]
    return k


def sections(data: bytes, lay: str, n: int) -> dict[str, dict]:
    L = layout.lines(data, lay)
    secs: dict[str, dict] = {}
    cur = None
    in_head = False
    for l in L:
        t = l['text']
        if l['kind'] == 'note':
            if cur:
                secs[cur]['notes'].append(t)
            in_head = False
            continue
        m = HEAD.match(t)
        if m and l['bold']:
            k = key_of(m.group(1), m.group(2), m.group(3))
            if k in secs:  # a chapter table of contents repeated the heading; keep the first full one
                k = k + '-dup'
            cur = k
            secs[cur] = {'head': t, 'body': [], 'notes': [], 'num': m.group(1) + m.group(2) + m.group(3)}
            in_head = not re.search(r'[.\]]$', t)
            continue
        if l['bold'] and (l['size'] >= 13.5 or l['x'] > 150):
            cur = None  # Division / Chapter / Subchapter heading
            in_head = False
            continue
        if cur and in_head and l['bold']:
            secs[cur]['head'] += ' ' + t
            in_head = not re.search(r'[.\]]$', t)
            continue
        in_head = False
        if cur:
            secs[cur]['body'].append(l)
    out = {}
    for k, s in secs.items():
        if k.endswith('-dup'):
            continue
        head = layout.WS.sub(' ', s['head']).strip()
        head = re.sub(r'^§\s?', '§ ', head)
        paras = layout.flow(s["body"])
        out[k] = {'label': f'{n} PNC § {s["num"]}', 'kind': 'section', 'text': '\n'.join(['# ' + head, *paras]) + '\n',
                  'notes': ' '.join(s['notes'])}
    return out


def rppls(note: str) -> set[str]:
    src = note
    # only the Sources part of the notes names the enacting/amending laws
    m = re.search(r'Sources?\s(.*?)(?:\s(?:Notes|Cross-references?|Supreme Court Cases|Commission Comments?|Case Notes|Amended)\s|$)', note)
    if m:
        src = m.group(1)
    return {f'rppl-{int(a):02d}-{int(b):03d}' for a, b in RPPL.findall(src)}


def load(file_id: str) -> tuple[bytes, str]:
    b = fetch.path(DRIVE_FILE.format(file_id)).read_bytes()
    return b, hashlib.sha256(b).hexdigest()


def title_act(t: dict, laws: dict, decisions: list[str]) -> dict:
    n = t['n']
    eds = []
    for folder, date, pat, lay in EDITIONS:
        fid = IDX['supplements'][folder].get(pat.format(n=n))
        if fid:
            eds.append((date, fid, lay, folder))
    eds.append((CURRENT_DATE, IDX['current'][t['current']], 'modern', 'current'))
    versions = []
    prev = None
    for date, fid, lay, folder in eds:
        data, sha = load(fid)
        secs = sections(data, lay, n)
        units = {k: {f: v[f] for f in ('label', 'kind', 'text')} for k, v in sorted(secs.items())}
        credits = {}
        if prev is not None:
            pu, pn = prev
            for k in sorted(set(units) | set(pu)):
                if units.get(k, {}).get('text') == pu.get(k, {}).get('text'):
                    continue
                new = rppls(secs[k]['notes']) - rppls(pn.get(k, '')) if k in secs else set()
                if new:
                    credits[k] = sorted(new, key=lambda s: tuple(int(x) for x in s.split('-')[1:]))
                    for lk in credits[k]:
                        a, b = (int(x) for x in lk.split('-')[1:])
                        laws.setdefault(lk, {'label': f'RPPL {a}-{b}', 'title': f'Republic of Palau Public Law No. {a}-{b}',
                                             'kind': 'law', 'enacted': None, 'published': None, 'url': None,
                                             'temporary_until': None, 'restores': None, 'note': None})
        v = {'from': date, 'source_url': VIEW.format(fid), 'sha256': sha, 'units': units, 'credits': credits,
             'note': ('Palau National Code Annotated, ' + (folder if folder != 'current' else
                      f'current title (current as of {CURRENT_DATE[5:7]}/{CURRENT_DATE[8:]}/{CURRENT_DATE[:4]})'))}
        versions.append(v)
        prev = (units, {k: s['notes'] for k, s in secs.items()})
    return {'slug': t['slug'], 'short': t['short'], 'title': t['title'], 'url': 'https://palaulaw.gov.pw/',
            'first_law': None, 'earlier_laws': [], 'versions': versions}


def acts(laws: dict, decisions: list[str]) -> list[dict]:
    out = [title_act(t, laws, decisions) for t in TITLES]
    decisions.append('PNC titles: each version is one full edition of the title from the Code Commission archive '
                     '(1st Edition through 1994-09-30; 15th-18th Supplements; current as of 2026-09-30) and is dated '
                     'by that edition\'s "through" date, the day the Commission certifies the text as current; the true '
                     'in-force day of each change is earlier and is not given by the source.')
    decisions.append('PNC titles: the 1st and 2nd Supplements (1996, 1997) are pocket parts with only the changed '
                     'sections and the 3rd-14th Supplements are not in the archive, so the record jumps from the 1994 '
                     'First Edition to the 15th Supplement (2021-05-14).')
    decisions.append('PNC titles: a section that changed between editions is credited to the RPPL(s) its "Sources" note '
                     'names in the later edition and not in the earlier; if the note names none, the change is the '
                     'publisher\'s and committed as unexplained. RPPL enactment dates are not in the source, so laws '
                     'carry no enacted date.')
    decisions.append('PNC titles: RPPL keys are zero-padded (rppl-09-021 for RPPL 9-21) so that, with no enactment dates '
                     'in the source, the builder orders laws named together by their number (Olbiil Era Kelulau, then law).')
    decisions.append('PNC titles: Code Commission annotations (Sources, Notes, Cross-references, Supreme Court Cases, '
                     'Commission Comments) and the chapter tables of contents are not part of the section files.')
    return out
