"""Build scripts/palau-law/corpus.json from the cache only (no network).

Sources (all official): the Palau Code Commission / Publication And Law Access Unit ("PALAU Office") Google Drive,
linked from the Code Commission's site palaulaw.gov.pw (folder ids in sources.json). Every file is read from
.cache/<sha256(url)> as fetched by fetch.py.

Method
- Constitution: the Code Commission prints the Constitution as adopted (Preamble, Articles I-XV) with the
  amendments appended in order (First ... Twenty-Eighth), each with a "Source" note giving the day the amendment was
  enacted. That arrangement is kept: version 1 (1981-01-01) holds the Preamble and Articles; each later version adds
  the amendment(s) enacted that day, credited to that amendment. Annotations (Amended/Repealed notes, case lists) are
  not law text and are left out.
- PNC titles: see pnc() below.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import layout  # noqa: E402

SRC = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
DRIVE_FILE = 'https://drive.google.com/uc?export=download&id={}'
VIEW = 'https://drive.google.com/file/d/{}/view'

ROMAN = {v: i for i, v in enumerate(
    'I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX'.split(), 1)}
ORD = ['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH', 'SEVENTH', 'EIGHTH', 'NINTH', 'TENTH',
       'ELEVENTH', 'TWELFTH', 'THIRTEENTH', 'FOURTEENTH', 'FIFTEENTH', 'SIXTEENTH', 'SEVENTEENTH', 'EIGHTEENTH',
       'NINETEENTH', 'TWENTIETH']
MONTHS = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                      'September', 'October', 'November', 'December'], 1)}


def ordinal(word: str) -> int:
    word = word.upper().replace('TWENTY-EIGHT', 'TWENTY-EIGHTH')
    if word.startswith('TWENTY-'):
        return 20 + ORD.index(word[7:]) + 1
    return ORD.index(word) + 1


def cached(file_id: str) -> tuple[bytes, str, str]:
    url = DRIVE_FILE.format(file_id)
    b = fetch.path(url).read_bytes()
    return b, url, hashlib.sha256(b).hexdigest()


def mdy(s: str) -> str:
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})', s)
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}' if m else ''


# ------------------------------------------------------------------ Constitution

ART = re.compile(r'^ARTICLE ([IVX]+) — (.+)$')
AMEND = re.compile(r'^([A-Z-]+?)(?: AND ([A-Z-]+))? AMENDMENTS?$')
SEC = re.compile(r'^Section (\d+)\.\s*(.*)$')


def constitution() -> tuple[dict, dict, list[str]]:
    data, url, sha = cached(SRC['constitution']['id'])
    L = layout.lines(data, 'modern')
    # start at the Preamble heading
    start = next(i for i, l in enumerate(L) if l['text'] == 'Preamble' and l['size'] >= 13)
    units: dict[str, dict] = {}
    notes: dict[str, list[str]] = {}
    order: list[str] = []
    cur = None
    art = None
    art_title = ''
    pending_title = None
    for l in L[start:]:
        t = l['text']
        if l['kind'] == 'note':
            if cur:
                notes.setdefault(cur, []).append(t)
            continue
        if l['size'] >= 13:
            m = ART.match(t)
            a = AMEND.match(t)
            if t == 'Preamble':
                cur = 'preamble'
                units[cur] = {'label': 'Preamble', 'kind': 'preamble', 'head': '# Preamble', 'body': []}
                order.append(cur)
            elif m:
                art = ROMAN[m.group(1)]
                art_title = m.group(2).title()
                pending_title = (m.group(1), m.group(2))
                cur = None
            elif a:
                n1 = ordinal(a.group(1))
                key = f'amend-{n1:02d}' + (f'-{ordinal(a.group(2)):02d}' if a.group(2) else '')
                label = t.title().replace('Twenty-Eight ', 'Twenty-Eighth ').replace(' And ', ' and ')
                cur = key
                art = None
                units[cur] = {'label': label, 'kind': 'amendment', 'head': f'# {label}', 'body': []}
                order.append(cur)
            elif pending_title and cur is None:
                # a heading that wraps onto a second line (ARTICLE VI)
                art_title = (pending_title[1] + ' ' + t).title()
                pending_title = (pending_title[0], pending_title[1] + ' ' + t)
            continue
        m = SEC.match(t)
        if m and l['bold'] and art is not None:
            n = int(m.group(1))
            cur = f'art-{art:02d}-sec-{n:02d}'
            title = pending_title[1].title() if pending_title else art_title
            units[cur] = {'label': f'Art. {pending_title[0]}, § {n}', 'kind': 'section',
                          'head': f'# Article {pending_title[0]} — {title.replace(" Of ", " of ").replace(" The ", " the ")}, Section {n}',
                          'body': []}
            order.append(cur)
            if m.group(2):
                units[cur]['body'].append(dict(l, text=m.group(2)))
            continue
        if cur is None and art is not None and pending_title:
            # an Article with no numbered sections (VI, VII)
            cur = f'art-{art:02d}'
            title = pending_title[1].title()
            units[cur] = {'label': f'Art. {pending_title[0]}', 'kind': 'article',
                          'head': f'# Article {pending_title[0]} — {title.replace(" Of ", " of ").replace(" The ", " the ")}',
                          'body': []}
            order.append(cur)
        if cur:
            units[cur]['body'].append(l)
    out = {}
    for k in order:
        u = units[k]
        paras = layout.paragraphs(u['body'])
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join([u['head'], *paras]) + '\n'}
    meta = {'url': url, 'sha': sha, 'notes': notes, 'order': order}
    return out, meta, []


def constitution_act(laws: dict, decisions: list[str]) -> dict:
    units, meta, _ = constitution()
    base = {k: v for k, v in units.items() if not k.startswith('amend-')}
    amends = [k for k in meta['order'] if k.startswith('amend-')]
    dated: dict[str, list[str]] = {}
    for k in amends:
        src = ' '.join(meta['notes'].get(k, []))
        tail = src.split('Source', 1)[1] if 'Source' in src else src
        d = mdy(tail.split('enacted', 1)[1]) if 'enacted' in tail else mdy(tail)
        if k == 'amend-01':
            # The source note reads only "RPPL 3-76 § 3": the Code Commission does not date the First Amendment.
            d = SRC['constitution']['first_amendment_date']
        if not d:
            raise SystemExit(f'no date for {k}: {src[:200]}')
        dated.setdefault(d, []).append(k)
    laws['rop-constitution'] = {
        'label': 'Constitution of the Republic of Palau', 'title': 'Constitution of the Republic of Palau (Palau Constitutional Convention, 1979)',
        'kind': 'referendum', 'enacted': None, 'published': None, 'url': None,
        'temporary_until': None, 'restores': None, 'note': None}
    versions = [{
        'from': SRC['constitution']['in_force'],
        'source_url': VIEW.format(SRC['constitution']['id']),
        'sha256': meta['sha'],
        'units': base,
        'credits': {},
        'note': 'The Preamble and Articles I-XV as printed by the Palau Code Commission (current as of 05/13/2026), '
                'which prints the original articles and appends every amendment.'}]
    cur = dict(base)
    for d in sorted(dated):
        keys = dated[d]
        credits = {}
        for k in keys:
            n = k.split('-')[1:]
            lk = 'const-amend-' + '-'.join(n)
            label = units[k]['label']
            src = ' '.join(meta['notes'].get(k, []))
            note_src = re.sub(r'^.*?Source\s*', '', src)
            note_src = re.split(r'\s(?:Amended|Repealed|Supreme Court Cases|Notes)\s', ' ' + note_src + ' ')[0].strip()
            laws[lk] = {'label': label + ' to the Constitution', 'title': f'{label} to the Constitution of the Republic of Palau',
                        'kind': 'referendum', 'enacted': d, 'published': None, 'url': None,
                        'temporary_until': None, 'restores': None,
                        'note': None}
            cur[k] = units[k]
            credits[k] = [lk]
        versions.append({'from': d, 'source_url': VIEW.format(SRC['constitution']['id']), 'sha256': meta['sha'],
                         'units': dict(cur), 'credits': credits})
    decisions.append('Constitution: version 1 is dated 1981-01-01 (art. XV: "This Constitution shall take effect on '
                     'January 1, 1981"); its text is the Preamble and Articles as the Code Commission prints them, '
                     'credited to the Constitution itself.')
    decisions.append('Constitution: each amendment is a file of its own (amend-NN), added on the day its Code Commission '
                     '"Source" note says it was enacted (2004-11-06, 2008-11-19, 2020-11-17); the Code Commission prints '
                     'amendments after the Articles rather than merging them into the Articles, and this record keeps '
                     'that arrangement, so the Article files keep their 1981 wording.')
    decisions.append('Constitution: the First Amendment\'s note gives only "RPPL 3-76 § 3"; it is dated 1992-11-04, the '
                     'referendum that approved it (art. XIV § 1: effective "when approved"); that date comes from the '
                     'public referendum record, not from the Code Commission.')
    decisions.append('Constitution: Code Commission annotations ("Amended", "Repealed", "Notes", "Supreme Court Cases", '
                     '"Source") are editorial and are not part of the provision files.')
    return {
        'slug': 'constitution', 'short': 'ROP Const.', 'title': 'Constitution of the Republic of Palau',
        'url': 'https://palaulaw.gov.pw/', 'first_law': 'rop-constitution', 'earlier_laws': [],
        'versions': versions}


# ------------------------------------------------------------------ corpus

def write(corpus: dict) -> None:
    out = HERE / 'corpus.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, out)


def main() -> None:
    laws: dict = {}
    decisions: list[str] = []
    acts = [constitution_act(laws, decisions)]
    try:
        import pnc  # noqa: F401
        acts += pnc.acts(laws, decisions)
    except ImportError:
        pass
    reqs = sum(1 for _ in open(HERE / '.cache' / 'requests.jsonl', encoding='utf-8'))
    corpus = {
        'country': SRC['country'],
        'sources': [dict(s, requests=reqs if s.get('count_requests') else s.get('requests', 0)) for s in SRC['sources']],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions + SRC['decisions'],
        'ai_use': SRC['ai_use'],
    }
    for s in corpus['sources']:
        s.pop('count_requests', None)
    write(corpus)
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', len(a['versions'][-1].get('units') or {}), 'units (last)')


if __name__ == '__main__':
    main()
