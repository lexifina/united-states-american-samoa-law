"""Neuchatel laws (RSN "Loi ...") in parts of 50, current text only, for switzerland-neuchatel-law.
The list of RSN numbers comes from LexFind's systematics (metadata only, cached); every text is read from
rsn.ne.ch/DATA/program/books/rsne/htm/<n>.htm (the only path robots.txt allows). Private: scripts/world-law.

    python -X utf8 scripts/world-law/ch_neuchatel_laws.py <docs-date> [max]
    python -X utf8 scripts/world-law/ch_neuchatel_laws.py publish <part> <docs-date>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402
import ch_romandy as R  # noqa: E402

SLUG = 'neuchatel'
MONTHS = 'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split()


def fr_date(s):
    m = re.search(r'(\d{1,2})(?:er)?\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})', s or '')
    return f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}' if m else None


def law_numbers():
    lst = json.loads((R.folder(SLUG) / '.cache' / 'lexfind-act-list.json').read_text(encoding='utf-8'))
    out = sorted({sn for sn, title, cat in lst if cat == 4 and title.startswith('Loi') and sn != '101'},
                 key=C.natkey)
    return out


def ne_act(sn, docs_date):
    url = R.NE_BASE + sn + '.htm'
    try:
        raw = R.get(SLUG, url)
    except RuntimeError:
        return None
    t = raw.decode('cp1252', 'replace')
    m = re.search(r'<title>\s*[^:]+:\s*(.*?)</title>', t, re.S)
    title = C.clean(m.group(1)) if m else sn
    units, edition = R.parse_ne_doc(raw, sn)
    frm = fr_date(edition)
    if not frm or len(units) < 2 or frm > docs_date:
        return None
    adopted = fr_date(units.get('ingress', {}).get('text', ''))
    short = None
    ab = re.search(r'\(([A-Z][A-Za-z0-9.-]{1,15})\)', title)
    if ab:
        short = ab.group(1)
    tt = re.sub(r',\s*du\s+\d.*$', '', title)
    act = R.current_only_act(SLUG, units, url, hashlib.sha256(raw).hexdigest(), frm, tt, short, sn,
                             f'Text as the RSN gives it, "Etat au" {frm}; no earlier wording is held.')
    laws = {}
    if adopted:
        k = C.ascii_key(f'ne-{sn}-{adopted}')
        laws[k] = {'label': f'{short or "RSN " + sn} du {C._dmy(adopted)}', 'title': title, 'kind': 'law',
                   'enacted': adopted, 'published': None, 'url': url, 'temporary_until': None, 'restores': None,
                   'note': None}
        act['earlier_laws'] = [k]
    return act, laws


def build(docs_date, mx=None):
    nums = law_numbers()[:mx] if mx else law_numbers()
    print(len(nums), 'laws', flush=True)
    acts, laws, part_no = [], {}, 1
    for sn in nums:
        r = ne_act(sn, docs_date)
        if r and not R.act_ok(SLUG, r[0]):
            print('left out (text check)', sn, flush=True)
            r = None
        if r:
            acts.append(r[0])
            laws.update(r[1])
        if len(acts) == 50:
            R.write_part(R.folder(SLUG) / 'corpus.d' / f'{19 + part_no:02d}-lois-{part_no}.json',
                         {'laws': dict(sorted(laws.items())), 'acts': acts})
            print(part_no, flush=True)
            acts, laws, part_no = [], {}, part_no + 1
    if acts:
        R.write_part(R.folder(SLUG) / 'corpus.d' / f'{19 + part_no:02d}-lois-{part_no}.json',
                     {'laws': dict(sorted(laws.items())), 'acts': acts})
        print(part_no, 'last', len(acts), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'publish':
        print(R.publish(SLUG, sys.argv[2], sys.argv[3]))
    else:
        build(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
