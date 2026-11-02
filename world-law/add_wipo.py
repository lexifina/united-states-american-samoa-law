"""Add WIPO Lex catalogue (laws) and treaty actions to a country corpus.
Usage: add_wipo.py <country-folder> <ISO2> <html file> [--treaties]
Laws without a recorded date are left out. Treaties (WIPO-administered and others WIPO tracks) go in act `wipo-treaties`."""
import re, html, json, sys, hashlib
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cat_lib import merge_entries

d = Path(sys.argv[1]); cc = sys.argv[2]; raw = Path(sys.argv[3]).read_bytes(); sha = hashlib.sha256(raw).hexdigest()
t = raw.decode('utf8', errors='replace')
WIPO = 'https://www.wipo.int'; PROFILE = f'{WIPO}/wipolex/en/members/profile/{cc}'


def iso(s):
    s = s.strip()
    return datetime.strptime(s, '%B %d, %Y').strftime('%Y-%m-%d') if s else None


def txt(c):
    return html.unescape(' '.join(re.sub(r'<[^>]+>', ' ', c).split())).replace('\xa0', ' ')


c = json.load(open(d / 'corpus.json', encoding='utf8')); name = c['country']['name']
cat = []
for m in re.finditer(r'<table[^>]*id="members_profile_laws_table">(.*?)</table>', t, re.S):
    for r in re.findall(r'<tr>(.*?)</tr>', m.group(1), re.S)[1:]:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S); cells = [txt(x) for x in tds]
        href = re.search(r'href="(/wipolex/en/legislation/details/(\d+))"', r)
        if not href: continue
        dates = {k.strip().lower(): iso(v) for k, v in re.findall(r'(\w+)\s*:\s*([A-Z][a-z]+ \d+, \d{4})', cells[1])}
        cat.append(dict(id=href.group(2), url=WIPO + href.group(1), version=cells[0], title=cells[2], subject=cells[3], dates=dates, datestr=cells[1]))
entries, undated, seen = [], 0, set()
for x in cat:
    if x['id'] in seen: continue
    seen.add(x['id'])
    dt = (x['dates'].get('promulgated') or x['dates'].get('entry') or x['dates'].get('force') or x['dates'].get('commenced')
          or x['dates'].get('adopted') or x['dates'].get('published'))
    if not dt:
        undated += 1; continue
    text = '\n'.join([f"# {x['title']}", f"Subject matter (WIPO Lex): {x['subject']}", f"Dates recorded by WIPO Lex: {x['datestr']}",
                      f"WIPO Lex version year: {x['version']}", f"Record: {x['url']}"]) + '\n'
    entries.append((dt, f"law-{int(x['id']):05d}", x['title'][:90], text))
if not any(a['slug'] == 'catalogue' for a in c['acts']):
    c['acts'].append({'slug': 'catalogue', 'short': 'Catalogue', 'title': f'Catalogue of laws of {name} recorded by WIPO Lex (title, date, link only; no law text)',
                      'url': PROFILE, 'first_law': None, 'earlier_laws': [], 'versions': []})
a = [a for a in c['acts'] if a['slug'] == 'catalogue'][0]
merge_entries(c, 'catalogue', entries, 'catalogue', 'Catalogue entries dated by the date WIPO Lex records for the law; facts only, no law text.', PROFILE, sha, PROFILE)
a = [a for a in c['acts'] if a['slug'] == 'catalogue'][0]
if a['first_law'] is None and a['versions']:
    a['first_law'] = 'catalogue-' + a['versions'][0]['from']
nt = 0
if '--treaties' in sys.argv:
    tm = re.search(r'<table[^>]*id="members_profile_treaties_table">(.*?)</table>', t, re.S)
    tr = []
    for r in re.findall(r'<tr>(.*?)</tr>', tm.group(1), re.S)[1:]:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
        if len(tds) != 7: continue
        cl = [txt(x) for x in tds]; href = re.search(r'href="(/wipolex/en/treaties/details/(\d+))"', tds[0])
        title = txt(re.search(r'<a [^>]*>(.*?)</a>', tds[0], re.S).group(1))
        adopt, eift, sig, inst, eifp = (iso(x) for x in cl[2:7]); action = inst or eifp or sig
        if not action: continue
        tr.append(dict(id=href.group(2), title=title, url=WIPO + href.group(1), entity=cl[1], adopt=adopt, eift=eift, sig=sig, inst=inst, eifp=eifp, action=action))
    by = {}
    for x in tr: by.setdefault(x['action'], []).append(x)
    versions, laws, units = [], c['laws'], {}
    for day in sorted(by):
        cred = {}
        for x in sorted(by[day], key=lambda x: int(x['id'])):
            key = f"treaty-{int(x['id']):04d}"; lk = f"wipo-treaty-{x['id']}"
            L = [f"# {x['title']}", f"Administered by: {x['entity']}", f"Adopted: {x['adopt'] or 'not given'}", f"Entered into force (treaty): {x['eift'] or 'not given'}"]
            if x['sig']: L.append(f"Signed by {name}: {x['sig']}")
            if x['inst']: L.append(f"Ratification, accession or similar instrument: {x['inst']}")
            if x['eifp']: L.append(f"Entered into force for {name}: {x['eifp']}")
            L.append(f"Record: {x['url']}")
            units[key] = {'label': x['title'][:90], 'kind': 'treaty', 'text': '\n'.join(L) + '\n'}
            cred[key] = [lk]
            laws[lk] = {'label': x['title'][:90], 'title': x['title'], 'kind': 'treaty', 'enacted': day, 'published': day, 'url': x['url'],
                        'temporary_until': None, 'restores': None,
                        'note': f'Action by {name} on this date (signature, ratification, accession or similar), as recorded by WIPO Lex.'}
        versions.append({'from': day, 'source_url': PROFILE, 'sha256': sha, 'credits': cred, 'changes': {k: units[k] for k in cred}})
    if versions:
        versions[0]['units'] = versions[0].pop('changes')
        c['acts'] = [x for x in c['acts'] if x['slug'] != 'wipo-treaties'] + [{
            'slug': 'wipo-treaties', 'short': 'WIPO treaties', 'title': f'Treaty actions of {name} recorded by WIPO Lex (facts only; no treaty text)',
            'url': PROFILE, 'first_law': None, 'earlier_laws': [], 'versions': versions}]
    nt = len(tr)
if not any(s['name'] == 'WIPO Lex member profile' for s in c['sources']):
    c['sources'].append({'name': 'WIPO Lex member profile', 'url': PROFILE, 'retrieved': '2026-10-30',
                         'licence': 'WIPO content: CC BY 4.0 (https://www.wipo.int/web/terms-of-use); only facts copied',
                         'notes': 'List of laws with dates and treaty actions; titles, dates and links only.'})
c['decisions'] = [x for x in c['decisions'] if not x.startswith('WIPO Lex:')]
c['decisions'].append(f"WIPO Lex: {len(entries)} laws from the member profile dated by the date WIPO Lex records (promulgation, entry into force, commencement, adoption, in that order); "
                      f"{undated} laws with no recorded date are left out. Treaty actions: {nt}. Titles, dates and links only; no text. "
                      "WIPO Lex gives some laws only 'January 1' of a year, a placeholder rather than a known date.")
json.dump(c, open(d / 'corpus.json', 'w', encoding='utf8', newline='\n'), ensure_ascii=False, indent=1)
print(len(entries), 'dated laws;', undated, 'undated;', nt, 'treaties')
