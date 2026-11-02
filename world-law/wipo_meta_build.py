"""Metadata-only first build from a WIPO Lex member profile + Wikidata results (no law text).
Usage: wipo_meta_build.py <slug>-law   (reads scripts/<slug>-law/.cache/wipo.html, .cache/wikidata.json, meta.json; writes corpus.json)"""
import re, html, json, sys, hashlib
from datetime import datetime
from pathlib import Path

d = Path(__file__).resolve().parents[1] / sys.argv[1]
slug = sys.argv[1].removesuffix('-law')
meta = json.loads((d / 'meta.json').read_text(encoding='utf8'))
raw = (d / '.cache' / 'wipo.html').read_bytes(); sha = hashlib.sha256(raw).hexdigest()
wd_raw = (d / '.cache' / 'wikidata.json').read_bytes(); wd_sha = hashlib.sha256(wd_raw).hexdigest()
t = raw.decode('utf8', errors='replace')
RET = meta['retrieved']
WIPO = 'https://www.wipo.int'
PROFILE = f'{WIPO}/wipolex/en/members/profile/{meta["code"]}'


def iso(s):
    s = s.strip()
    return datetime.strptime(s, '%B %d, %Y').strftime('%Y-%m-%d') if s else None


def txt(c):
    return html.unescape(' '.join(re.sub(r'<[^>]+>', ' ', c).split())).replace('\xa0', ' ')


def kv(lines):
    return '\n'.join(lines) + '\n'


# ---- treaties
tm = re.search(r'<table[^>]*id="members_profile_treaties_table">(.*?)</table>', t, re.S)
treaties = []
for r in re.findall(r'<tr>(.*?)</tr>', tm.group(1), re.S)[1:]:
    tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
    assert len(tds) == 7, len(tds)
    c = [txt(x) for x in tds]
    href = re.search(r'href="(/wipolex/en/treaties/details/(\d+))"', tds[0])
    title = txt(re.search(r'<a [^>]*>(.*?)</a>', tds[0], re.S).group(1))
    adopt, eift, sig, inst, eifp = (iso(x) for x in c[2:7])
    action = inst or eifp or sig
    if not action:
        continue
    treaties.append(dict(id=href.group(2), title=title, url=WIPO + href.group(1), entity=c[1], adopt=adopt, eift=eift,
                         sig=sig, inst=inst, eifp=eifp, action=action))

# ---- laws
catalogue = []
for m in re.finditer(r'<table[^>]*id="members_profile_laws_table">(.*?)</table>', t, re.S):
    for r in re.findall(r'<tr>(.*?)</tr>', m.group(1), re.S)[1:]:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
        c = [txt(x) for x in tds]
        href = re.search(r'href="(/wipolex/en/legislation/details/(\d+))"', r)
        dates = {k.strip().lower(): iso(v) for k, v in re.findall(r'(\w+)\s*:\s*([A-Z][a-z]+ \d+, \d{4})', c[1])}
        catalogue.append(dict(id=href.group(2), url=WIPO + href.group(1), version=c[0], title=c[2], subject=c[3],
                              dates=dates, datestr=c[1]))

laws = {}
acts = []

# ---- treaties act
by = {}
for x in treaties:
    by.setdefault(x['action'], []).append(x)
versions = []
for day in sorted(by):
    ch = {}
    cred = {}
    for x in sorted(by[day], key=lambda x: int(x['id'])):
        key = f"treaty-{int(x['id']):04d}"
        lk = f"treaty-{x['id']}"
        L = [f"# {x['title']}", f"Administered by: {x['entity']}", f"Adopted: {x['adopt'] or 'not given'}",
             f"Entered into force (treaty): {x['eift'] or 'not given'}"]
        if x['sig']:
            L.append(f"Signed by {meta['name']}: {x['sig']}")
        if x['inst']:
            L.append(f"Ratification, accession or similar instrument: {x['inst']}")
        if x['eifp']:
            L.append(f"Entered into force for {meta['name']}: {x['eifp']}")
        L.append(f"Record: {x['url']}")
        ch[key] = {'label': x['title'][:90], 'kind': 'treaty', 'text': kv(L)}
        cred[key] = [lk]
        laws[lk] = {'label': x['title'][:90], 'title': x['title'], 'kind': 'treaty', 'enacted': day, 'published': day,
                    'url': x['url'], 'temporary_until': None, 'restores': None,
                    'note': f"Action by {meta['name']} on this date (signature, ratification, accession or similar), as recorded by WIPO Lex."}
    v = {'from': day, 'source_url': PROFILE, 'sha256': sha, 'credits': cred}
    v['units' if not versions else 'changes'] = ch
    versions.append(v)
first_t = sorted(by[min(by)], key=lambda x: int(x['id']))[0]
acts.append({'slug': 'treaties', 'short': 'Treaties',
             'title': f"Treaty actions of {meta['name']} recorded by WIPO Lex (facts only; no treaty text)", 'url': PROFILE,
             'first_law': f"treaty-{first_t['id']}", 'earlier_laws': [], 'versions': versions})

# ---- catalogue act
dated = {}
undated = []
for x in catalogue:
    dt = x['dates'].get('promulgated') or x['dates'].get('entry') or x['dates'].get('force') or x['dates'].get('commenced') or x['dates'].get('adopted') or x['dates'].get('published')
    if dt:
        dated.setdefault(dt, []).append(x)
    else:
        undated.append(x)
days = sorted(dated)
if undated:
    dated.setdefault(RET, []).extend(undated)
    days = sorted(dated)
versions = []
for day in days:
    ch = {}
    cred = {}
    lk = f'catalogue-{day}'
    for x in sorted(dated[day], key=lambda x: int(x['id'])):
        key = f"law-{int(x['id']):05d}"
        ch[key] = {'label': x['title'][:90], 'kind': 'law',
                   'text': kv([f"# {x['title']}", f"Subject matter (WIPO Lex): {x['subject']}",
                               f"Dates recorded by WIPO Lex: {x['datestr'] or 'none'}",
                               f"WIPO Lex version year: {x['version']}", f"Record: {x['url']}"])}
        cred[key] = [lk]
    laws[lk] = {'label': f'Catalogue entries of {day}', 'title': f'Laws added to the catalogue on {day}',
                'kind': 'publisher' if day == RET and undated else 'law', 'enacted': day, 'published': day, 'url': PROFILE,
                'temporary_until': None, 'restores': None,
                'note': 'Catalogue entries dated by the date WIPO Lex records for the law (the retrieval date for a law with no recorded date); facts only, no law text.'}
    v = {'from': day, 'source_url': PROFILE, 'sha256': sha, 'credits': cred}
    v['units' if not versions else 'changes'] = ch
    versions.append(v)
acts.append({'slug': 'catalogue', 'short': 'Catalogue',
             'title': f"Catalogue of laws of {meta['name']} recorded by WIPO Lex (title, date, link only; no law text)", 'url': PROFILE,
             'first_law': f'catalogue-{days[0]}', 'earlier_laws': [], 'versions': versions})

# ---- legal-system act (Wikidata CC0 + WIPO framework law)
wd = json.loads(wd_raw.decode('utf8'))
groups = {}
for b in wd['results']['bindings']:
    groups.setdefault(b['kind']['value'], {})[b['item']['value'].split('/')[-1]] = b['itemLabel']['value']
lu = {}
for x in [x for x in catalogue if 'Constitution' in x['title']]:
    lu['constitution'] = {'label': 'Constitution', 'kind': 'fact', 'text': kv(
        ["# Constitution", f"Title (WIPO Lex): {x['title']}", f"Date recorded by WIPO Lex: {x['datestr']}",
         f"WIPO Lex text version: {x['version']}", f"Record: {x['url']}"]
        + [f"Wikidata item: {q} ({n}), https://www.wikidata.org/wiki/{q}" for q, n in groups.get('constitution', {}).items()])}
for kind, key, head in (('legislature', 'legislature', 'Legislature'), ('court', 'courts', 'Courts'),
                        ('official language', 'official-languages', 'Official languages')):
    if groups.get(kind):
        lu[key] = {'label': head, 'kind': 'fact', 'text': kv(
            [f"# {head}"] + [f"{n} (Wikidata {q}, https://www.wikidata.org/wiki/{q})" for q, n in groups[kind].items()])}
lu['sources'] = {'label': 'Sources of this act', 'kind': 'fact', 'text': kv(
    ['# Sources', f'Wikidata (CC0), queried {RET}: https://www.wikidata.org/', f'WIPO Lex member profile, retrieved {RET}: {PROFILE}'])}
acts.append({'slug': 'legal-system', 'short': 'Legal system', 'title': f"Legal system of {meta['name']}: open facts (Wikidata, WIPO Lex)",
             'url': 'https://www.wikidata.org/', 'first_law': None, 'earlier_laws': [],
             'versions': [{'from': RET, 'source_url': 'https://query.wikidata.org/sparql', 'sha256': wd_sha, 'units': lu, 'credits': {},
                           'note': 'Oldest version available: facts as retrieved on this date; Wikidata gives no date for them.'}]})

pub = {'name': 'World Intellectual Property Organization (WIPO Lex) and Wikidata', 'email': 'wipo-lex@wipo-int.invalid'}
corpus = {
    'country': {'code': meta['code'], 'name': meta['name'], 'slug': slug, 'lang': 'en', 'tz': meta['tz'], 'future_branch': 'future', 'publisher': pub,
                'default_in_force_rule': {'text': "This repository holds metadata only, no law text. Each treaty is dated by the party's own action (ratification, accession or similar instrument; failing that its entry into force for the party, then signature); each catalogue entry by the date WIPO Lex records for the law.", 'source': PROFILE},
                'licence_note': 'Metadata (titles, dates, numbers, links) from WIPO Lex, https://www.wipo.int/wipolex/, source: WIPO (CC BY 4.0 for WIPO content); open facts from Wikidata (CC0). No law text.'},
    'sources': [{'name': 'WIPO Lex member profile', 'url': PROFILE, 'retrieved': RET, 'licence': 'WIPO content: CC BY 4.0 (https://www.wipo.int/web/terms-of-use); only facts copied', 'notes': 'Treaty actions and a list of laws with dates; titles, dates and links only.'},
                {'name': 'Wikidata', 'url': 'https://www.wikidata.org/', 'retrieved': RET, 'licence': 'CC0', 'notes': 'Constitution, courts, legislature and official languages.'}],
    'laws': laws, 'acts': acts, 'applies': [],
    'decisions': [meta['why'],
                  "Treaty versions are dated by the party's instrument date (ratification, accession or similar), else its entry-into-force date for the party, else signature; treaties with none of these are left out.",
                  'Catalogue entries use the date WIPO Lex records (promulgation, entry into force, commencement or adoption, in that order); WIPO Lex gives some laws only "January 1" of a year, which is a placeholder, not a known date; a law with no date is added on the retrieval date.',
                  'No treaty or law text is included: titles, dates, administering organisation and links only.'],
    'ai_use': ['none']}
(d / 'corpus.json').write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf8', newline='\n')
print(slug, 'treaties', len(treaties), 'catalogue', len(catalogue), 'undated', len(undated), 'wd', {k: len(v) for k, v in groups.items()})
