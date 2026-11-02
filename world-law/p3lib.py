"""Phase 3 helpers: Wikidata fact fetch + corpus assembly for no-text countries (private, never published)."""
import json, re, sys, urllib.request, urllib.parse
UA = {'User-Agent': 'lexifina-lawbot/1.0 (alan@lexifina.com)'}

def jget(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))

def entity(q):
    return jget(f'https://www.wikidata.org/wiki/Special:EntityData/{q}.json')['entities'][q]

_labels = {}
def labels(ids):
    ids = [i for i in ids if i not in _labels]
    for k in range(0, len(ids), 40):
        part = ids[k:k+40]
        r = jget('https://www.wikidata.org/w/api.php?action=wbgetentities&props=labels&languages=en&format=json&ids=' + '|'.join(part))
        for i, e in r['entities'].items():
            _labels[i] = e.get('labels', {}).get('en', {}).get('value', i)
    return _labels

def claim_vals(e, p):
    out = []
    for c in e['claims'].get(p, []):
        if c.get('rank') == 'deprecated': continue
        v = c['mainsnak'].get('datavalue', {}).get('value')
        if v is not None: out.append(v)
    return out

def iso(v):
    t = v['time']; prec = v.get('precision', 11)
    m = re.match(r'([+-])(\d+)-(\d\d)-(\d\d)', t)
    y, mo, d = int(m.group(2)), m.group(3), m.group(4)
    return (f'{y:04d}-{mo}-{d}' if prec >= 11 else f'{y:04d}'), prec

def ids_of(e, p):
    return [v['id'] for v in claim_vals(e, p) if isinstance(v, dict) and 'id' in v]

def wrap(path, obj):
    import os
    tmp = path + '.tmp'
    open(tmp, 'w', encoding='utf8', newline='\n').write(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + '\n')
    os.replace(tmp, path)

RETRIEVED = '2026-10-30'

def legal_system_act(q, name, extra_items=()):
    """Wikidata (CC0) facts as act 'legal-system'. Returns (act, law_dict, source). Dated facts (day precision) get their own earlier version."""
    e = entity(q)
    url = f'https://www.wikidata.org/wiki/{q}'
    want = {}
    for p in ['P122', 'P37', 'P36', 'P194', 'P208', 'P1906', 'P1313', 'P2184']:
        want[p] = ids_of(e, p)
    labels(sorted({i for v in want.values() for i in v}))
    def lab(i): return _labels[i]
    def joined(p): return '; '.join(f'{lab(i)} ({i})' for i in want[p])
    inc = claim_vals(e, 'P571')
    inc_date, prec = (iso(inc[0]) if inc else (None, 0))
    lines = {
        'state': [f'# {name}', f'Wikidata item: {q} ({url}).'] + ([f'Inception of the state or territory: {inc_date}.'] if inc_date else []),
        'government': [f'# Form of government'] + ([f'Form of government: {joined("P122")}.'] if want['P122'] else []) +
                      ([f'Head of state office: {joined("P1906")}.'] if want['P1906'] else []) +
                      ([f'Head of government office: {joined("P1313")}.'] if want['P1313'] else []),
        'institutions': ['# Institutions'] + ([f'Legislative body: {joined("P194")}.'] if want['P194'] else []) +
                      ([f'Executive body: {joined("P208")}.'] if want['P208'] else []) + ([f'Capital: {joined("P36")}.'] if want['P36'] else []),
        'languages': ['# Official languages'] + ([f'Official languages: {joined("P37")}.'] if want['P37'] else []),
    }
    units = {}
    for k, ls in lines.items():
        if len(ls) > (2 if k == 'state' else 1):
            units[k] = {'label': ls[0][2:], 'kind': 'fact', 'text': '\n'.join(ls) + '\n'}
    for xq in extra_items:  # e.g. constitution items
        xe = entity(xq)
        xl = xe['labels']['en']['value']
        ds = []
        for p, w in [('P571', 'Inception'), ('P577', 'Publication'), ('P1319', 'Earliest date'), ('P585', 'Point in time')]:
            for v in claim_vals(xe, p):
                if isinstance(v, dict) and 'time' in v: ds.append(f'{w}: {iso(v)[0]}.')
        desc = xe.get('descriptions', {}).get('en', {}).get('value')
        t = [f'# {xl}', f'Wikidata item: {xq} (https://www.wikidata.org/wiki/{xq}).'] + ([f'Described as: {desc}.'] if desc else []) + ds
        units['item-' + xq.lower()] = {'label': xl, 'kind': 'fact', 'text': '\n'.join(t) + '\n'}
    law = {'wikidata-' + RETRIEVED: {'label': f'Wikidata facts as retrieved {RETRIEVED}', 'title': 'Wikidata facts (CC0)', 'kind': 'publisher',
           'enacted': RETRIEVED, 'published': RETRIEVED, 'url': url, 'temporary_until': None, 'restores': None,
           'note': 'Facts copied from Wikidata, which is released under CC0; they were not enacted on this date.'}}
    versions = []
    if inc_date and prec >= 11 and 'state' in units and len(units) > 1:
        versions.append({'from': inc_date, 'source_url': url, 'sha256': 'wikidata-entity-' + q, 'units': {'state': units['state']}, 'credits': {},
                         'note': 'Oldest dated fact: the inception date Wikidata records. Only the state item is dated; the other facts come in the next version.'})
        rest = {k: v for k, v in units.items() if k != 'state'}
        versions.append({'from': RETRIEVED, 'source_url': url, 'sha256': 'wikidata-entity-' + q, 'units': dict(units),
                         'credits': {k: ['wikidata-' + RETRIEVED] for k in rest}, 'note': 'Facts as Wikidata held them on the retrieval date.'})
    else:
        versions.append({'from': RETRIEVED, 'source_url': url, 'sha256': 'wikidata-entity-' + q, 'units': units, 'credits': {},
                         'note': 'Oldest version available: Wikidata holds no day-precision date for these facts, so the retrieval date is used.'})
    act = {'slug': 'legal-system', 'short': 'Legal system', 'title': f'{name}: legal system facts (Wikidata)', 'url': url,
           'first_law': None, 'earlier_laws': [], 'versions': versions}
    src = {'name': 'Wikidata', 'url': url, 'retrieved': RETRIEVED, 'licence': 'CC0 1.0', 'notes': 'Structured facts only (no law text).'}
    return act, law, src

def write_docs(folder, slug, code, name, rows, holds, source_md, dates_md, limits_md, licence_text, domain):
    """repo/README.md, LICENSE, jurisdiction.json. rows = [(folder, title, versions, history)]."""
    from pathlib import Path
    d = Path(folder) / 'repo'; d.mkdir(parents=True, exist_ok=True)
    tbl = '\n'.join(f'| `{a}/` | {b} | {c} | {h} |' for a, b, c, h in rows)
    readme = f"""# {name}: law history in git

The law of {name} as a git history: one file per provision, one commit per law on the day it took effect, and the law that made each change as the commit's author. `git blame` names the law behind every paragraph; `git log` lists every change; picking a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

## What this repository holds

{holds}

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{tbl}

## Source

{source_md}

## Dates

{dates_md}

## How it is checked

Every version is read back from git on the day it took effect and on the day before (`tools/check_repo.py`) and must match `corpus.json`; results are in `REPRODUCE.md`.

## What "author" means

The author of a commit is the law (or, for facts, the retrieval) that made the change, with an e-mail address that cannot exist (`<law key>@{domain}.invalid`). The committer is always Lexifina.

## Limits

{limits_md}
"""
    (d / 'README.md').write_text(readme, encoding='utf8', newline='\n')
    (d / 'LICENSE').write_text(licence_text.rstrip() + """

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the
tools) are dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
""", encoding='utf8', newline='\n')
    (d / 'jurisdiction.json').write_text(json.dumps({"path": code.lower(), "code": code, "name": name, "level": "country",
        "repo": f"https://github.com/lexifina/{slug}-law", "build": "built",
        "register": "https://claude.ai/artifact/DdS9F6yqpPZtV2i7FGQhYZ", "register_date": "2026-10-28"}, indent=2) + "\n", encoding='utf8', newline='\n')
