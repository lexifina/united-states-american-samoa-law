"""Merge new dated entries into an act of a corpus.json (catalogue or treaties style).

merge_entries(corpus, slug, entries, law_note, source_url, sha256, law_url, law_label_fmt)
entries: list of (date, key, label, text)   key: [a-z0-9-]+
Rebuilds the act's versions: one version per date; first has `units`, later ones `changes`.
Existing units keep their date (first appearance). Existing law keys catalogue-<date> are reused.
"""
import json, copy

def _events(act):
    ev = []
    state = {}
    for v in act['versions']:
        body = v.get('units') if v.get('units') is not None else v.get('changes', {})
        for k, u in body.items():
            ev.append((v['from'], k, u, v.get('source_url'), v.get('sha256'), (v.get('credits') or {}).get(k)))
    return ev

def merge_entries(c, slug, entries, kind_prefix, law_note, source_url, sha256, law_url, kind='law'):
    act = [a for a in c['acts'] if a['slug'] == slug][0]
    ev = _events(act)
    have = {e[1] for e in ev}
    for date, key, label, text in entries:
        if key in have:
            continue
        have.add(key)
        ev.append((date, key, {'label': label, 'kind': kind, 'text': text}, source_url, sha256, [f'{kind_prefix}-{date}']))
    by = {}
    for d, k, u, su, sh, cr in ev:
        by.setdefault(d, []).append((k, u, su, sh, cr))
    versions = []
    for i, d in enumerate(sorted(by)):
        items = by[d]
        items.sort(key=lambda t: t[0])
        credits = {}
        for k, u, su, sh, cr in items:
            credits[k] = cr
            lk = cr[0]
            if lk not in c['laws']:
                c['laws'][lk] = {'label': f'{kind_prefix.capitalize()} entries of {d}', 'title': f'Entries added to the {kind_prefix} on {d}',
                                 'kind': 'law', 'enacted': d, 'published': d, 'url': law_url, 'temporary_until': None,
                                 'restores': None, 'note': law_note}
        v = {'from': d, 'source_url': items[0][2], 'sha256': items[0][3], 'credits': credits}
        body = {k: u for k, u, *_ in items}
        v['units' if i == 0 else 'changes'] = body
        versions.append(v)
    act['versions'] = versions
    return len(ev)
