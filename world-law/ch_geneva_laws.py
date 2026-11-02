"""Geneva laws (rsGE "Loi ..." acts) in parts of 50, current text only, for switzerland-geneva-law.
The act list is SILGENEVE's own sitemap.xml (named in its robots.txt); pages are read on the allowed
/legis/program/books/rsg/htm/ path, >= 5 s apart (Crawl-delay 5). Private: scripts/world-law.

    python -X utf8 scripts/world-law/ch_geneva_laws.py <docs-date> [max]
    python -X utf8 scripts/world-law/ch_geneva_laws.py publish <part> <docs-date>
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402
import ch_romandy as R  # noqa: E402

SLUG = 'geneva'


def law_urls():
    b = R.get(SLUG, 'https://silgeneve.ch/sitemap.xml')
    urls = [u.decode() for u in re.findall(rb'<loc>([^<]+)</loc>', b)]
    return [u for u in urls if re.search(r'/rsg_[a-z]\d+_\d+\.htm$', u) and not u.endswith('rsg_a2_00.htm')]


def ge_act(url, docs_date):
    raw = R.get(SLUG, url)
    t = raw.decode('cp1252', 'replace')
    m = re.search(r'<title>rsGE ([^:]+):\s*(.*?)</title>', t, re.S)
    if not m:
        return None
    code, title = C.clean(m.group(1)), C.clean(m.group(2))
    if not re.match(r'^Loi\b', title):
        return None
    units, rows, _ = R.parse_geneva_doc(raw)
    days = [r['inforce'] for r in rows if r['inforce'] and r['inforce'] <= docs_date]
    if not days or len(units) < 2:
        return None
    frm = max(days)
    short = None
    ab = re.search(r'\(([A-Z][A-Za-z0-9-]{1,15})\)\s*$', title)
    if ab:
        short = ab.group(1)
    act = R.current_only_act(SLUG, units, url, hashlib.sha256(raw).hexdigest(), frm, title, short, code,
                             f'Text in force since {frm} (the latest entry into force in its history table), as '
                             'published on SILGENEVE; no earlier wording is held.')
    first = next((r for r in rows if r['adopted'] and r['inforce']), None)
    laws = {}
    if first:
        k = C.ascii_key(f'ge-{code}-{first["adopted"]}')
        laws[k] = {'label': f'{short or code} du {C._dmy(first["adopted"])}', 'title': f'{title}, du {C._dmy(first["adopted"])}',
                   'kind': 'law', 'enacted': first['adopted'], 'published': None, 'url': url,
                   'temporary_until': None, 'restores': None, 'note': None}
        act['earlier_laws'] = [k]
    return act, laws


def build(docs_date, mx=None):
    urls = law_urls()
    acts, laws, part_no = [], {}, 1
    seen = 0
    for u in urls:
        name = f'{19 + part_no:02d}-lois-{part_no}'  # write_part never rewrites a published part
        r = ge_act(u, docs_date)
        seen += 1
        if r and not R.act_ok(SLUG, r[0]):
            print('left out (text check)', u, flush=True)
            r = None
        if r:
            a, l = r
            if a['slug'] in {x['slug'] for x in acts}:
                a['slug'] = a['slug'] + '-2'
            acts.append(a)
            laws.update(l)
        if len(acts) == 50:
            R.write_part(R.folder(SLUG) / 'corpus.d' / f'{name}.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
            print(name, len(acts), flush=True)
            acts, laws, part_no = [], {}, part_no + 1
        if mx and seen >= mx:
            break
    if acts and not mx:
        name = f'{19 + part_no:02d}-lois-{part_no}'
        R.write_part(R.folder(SLUG) / 'corpus.d' / f'{name}.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
        print(name, len(acts), 'last', flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'publish':
        print(R.publish(SLUG, sys.argv[2], sys.argv[3]))
    else:
        build(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
