"""gitlaw-scraper-dell (2026-10-30): the Flemish Region and Community (lexifina/belgium-flanders-law) from the
Vlaamse Codex Open Data API (codex.opendata.api.vlaanderen.be). Private: fetch code never goes into the repo.

    python -X utf8 be_flanders.py fetch core            # the special decrees (core institutional texts)
    python -X utf8 be_flanders.py fetch decrees [N]     # the decrees with content, newest list order, N at most
    python -X utf8 be_flanders.py parse <docs-date>     # write corpus.d parts from the cache only
    python -X utf8 be_flanders.py letters <part>
    python -X utf8 be_flanders.py publish <part> <docs-date>

One request at a time through be_fetch.py (shared lock per host, >= GAP s apart).
"""
from __future__ import annotations

import datetime as dt
import html as htmlmod
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # scripts/
DOCS = ROOT.parent.parent                # ~/Documents
sys.path.insert(0, str(HERE))
import be_fetch  # noqa: E402

SLUG = 'belgium-flanders'
FOLDER = ROOT / f'{SLUG}-law'
API = 'https://codex.opendata.api.vlaanderen.be/api/'
SITE = 'https://codex.vlaanderen.be/Zoeken/Document.aspx?DID={}&param=informatie'
VERSIONING_FROM = '2006-06-01'   # Codex keeps every version only for texts published in the BS from 1 June 2006
PART_SIZE = 25          # decree parts (small batches: about one every few hours at 5,000 requests a day)
CORE_TYPE, DECREE_TYPE, CODIFIED_TYPE = 1000013, 1000001, 1000008
MONTHS = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus', 'september', 'oktober',
          'november', 'december']
TYPE_ABBR = {'Decreet': 'decr', 'Bijzonder Decreet': 'bijz-decr', 'Gecodificeerd Decreet': 'gecod-decr',
             'Besluit van de Vlaamse Regering': 'bvr', 'Ministerieel besluit': 'mb', 'Wet': 'wet',
             'Bijzondere Wet': 'bijz-wet', 'Koninklijk Besluit': 'kb', 'Samenwerkingsakkoord': 'sa',
             'Grondwet': 'grondwet', 'Ordonnantie van het Brusselse Hoofdstedelijke Parlement': 'ord'}
STOPFILE = FOLDER / '.cache' / 'fetch-stop'


def j(path: str):
    b = be_fetch.get(API + path)
    return None if b is None else json.loads(b)


def jc(path: str):
    """Cached only (parse never fetches)."""
    p = be_fetch.path_for(API + path)
    if p.exists():
        return json.loads(p.read_bytes())
    if p.with_suffix('.404').exists():
        return None
    if p.with_suffix('.err').exists():
        return 'ERR'   # the source answered 5xx for this URL: the act that needs it is left out
    return False


def list_type(type_id: int, getter=j) -> list[dict]:
    out, skip = [], 0
    while True:
        d = getter(f'WetgevingDocumentType/{type_id}/WetgevingDocumenten?skip={skip}&take=100')
        if not d:
            return out if d is not False else out
        out += d['ResultatenLijst']
        skip += 100
        if skip >= d['TotaalAantal']:
            return out


def articles(struct: dict) -> list[dict]:
    """Every article (ItemType A) in document order with its versions."""
    out = []

    def walk(items):
        for x in items or []:
            if x.get('ItemType') == 'A':
                out.append(x)
            walk(x.get('Items'))
    walk(struct.get('Items'))
    return out


def need_rel(doc: dict, art: dict, i: int) -> bool:
    v = art['Versions'][i]
    if i > 0:
        return True
    if (v.get('StartDatum') or '')[:10] > (doc.get('StartDatum') or '9999')[:10]:
        return True   # inserted later
    return len(art['Versions']) == 1 and v.get('EindDatum') is not None   # repealed, no successor


def fetch_doc(did: int) -> bool:
    doc = j(f'WetgevingDocument/{did}')
    if not doc or not doc.get('HeeftInhoud'):
        return True
    st = j(f'v2/WetgevingDocument/{did}/Structuur?includeArtikelen=true&includeVersies=true')
    if not st:
        return True
    for a in articles(st):
        for i, v in enumerate(a['Versions']):
            if v.get('StartDatumConditie') not in (None, 'SpecifiedDate') or not v.get('StartDatum'):
                continue
            j(f'WetgevingArtikelVersie/{v["Id"]}')
            if need_rel(doc, a, i) or (v.get('EindDatum') and i == len(a['Versions']) - 1):
                j(f'WetgevingArtikelVersie/{v["Id"]}/ArtikelversieRelaties')
    return True


def core_ids(getter=j) -> list[int]:
    ids = [1015039]   # bijzonder decreet van 7 juli 2006 over de Vlaamse instellingen, first
    for d in list_type(CORE_TYPE, getter):
        if d.get('HeeftInhoud') and d['Id'] not in ids and not d['Opschrift'].startswith('(van het Parlement'):
            ids.append(d['Id'])
    return ids


def decree_ids(getter=j) -> list[int]:
    out = []
    for t in (CODIFIED_TYPE, DECREE_TYPE):
        for d in list_type(t, getter):
            if d.get('HeeftInhoud') and d['Id'] not in out:
                out.append(d['Id'])
    return out


def _load_ok() -> bool:
    try:
        last = (Path(os.environ['LOCALAPPDATA']) / 'gitlaw-cpu.log').read_text().strip().splitlines()[-1]
        f = dict(x.split('=') for x in last.split()[1:])
        return int(f['cpu5']) <= 92 and int(f['ram']) <= 85
    except Exception:
        return True


def _below_normal():
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass


def fetch(which: str, n: int | None):
    import time
    _below_normal()
    ids = core_ids() if which == 'core' else decree_ids()
    done = FOLDER / '.cache' / f'fetched-{which}.txt'
    done.parent.mkdir(parents=True, exist_ok=True)
    have = set(done.read_text().split()) if done.exists() else set()
    k = 0
    for did in ids:
        if STOPFILE.exists():
            print('stop file present; stopping'); return
        if str(did) in have:
            continue
        while not _load_ok():
            time.sleep(60)
        fetch_doc(did)
        with open(done, 'a') as f:
            f.write(f'{did}\n')
        k += 1
        print(f'{which} {did} fetched ({k})', flush=True)
        if n and k >= n:
            break
    if not n or k < n:
        (FOLDER / '.cache' / f'fetch-{which}-done.txt').write_text('done\n')


# ---------------------------------------------------------------- parse

def clean_text(s: str) -> list[str]:
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|li|tr|h\d)>', '\n', s)
    s = re.sub(r'(?i)</t[dh]>', ' ', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = htmlmod.unescape(s).replace(' ', ' ').replace('​', '')
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    out = []
    for line in s.split('\n'):
        line = re.sub(r'[ \t\r\f\v]+', ' ', line).strip()
        if line:
            out.append(line)
    return out


def padnum(s: str) -> str:
    return re.sub(r'\d+', lambda m: m.group(0).zfill(3), s)


def unit_key(art_type: str, num: str) -> tuple[str, str, str]:
    num = num.strip().rstrip('.').strip()
    t = (art_type or 'ART.').upper().strip()
    if t.startswith('BIJL'):
        base, kind, lab = 'bijlage', 'annex', f'Bijlage {num}'.strip()
    else:
        base, kind, lab = 'art', 'art', f'Art. {num}'
    k = unicodedata.normalize('NFKD', num.lower())
    k = ''.join(c for c in k if c.isascii())
    k = re.sub(r'(?<=[0-9])(?=[a-z])', '-', k)
    k = re.sub(r'[^a-z0-9]+', '-', k).strip('-')
    k = padnum(k) if k else '000'
    return f'{base}-{k}', kind, lab


def day(s: str | None) -> str | None:
    return s[:10] if s else None


def nl_date(d: str) -> str:
    y, m, dd = d.split('-')
    return f'{int(dd)} {MONTHS[int(m) - 1]} {y}'


def law_of(doc: dict) -> tuple[str, dict]:
    typ = doc.get('WetgevingDocumentType') or 'Decreet'
    abbr = TYPE_ABBR.get(typ, re.sub(r'[^a-z0-9]+', '-', typ.lower()).strip('-')[:20])
    did = doc.get('WetgevingDocumentId') or doc.get('Id')
    d = day(doc['Datum'])
    key = f'{abbr}-{d}-{did}'
    law = {'label': f'{typ} van {nl_date(d)}', 'title': (doc.get('Opschrift') or '').strip(), 'kind': 'law'
           if 'Decreet' in typ or typ in ('Wet', 'Bijzondere Wet', 'Grondwet') or 'Ordonnantie' in typ else 'decree',
           'enacted': d, 'published': day(doc.get('BSDatum')), 'url': SITE.format(did),
           'temporary_until': None, 'restores': None, 'note': None}
    return key, law


CHANGE = {'Gewijzigd bij', 'Vervangen bij', 'Ingevoegd bij', 'Opgeheven bij', 'Ingetrokken bij', 'Hersteld bij',
          'Aangevuld bij', 'Vernietigd bij', 'Geschorst bij', 'Vernummerd bij', 'Toegevoegd bij'}


def parse_doc(did: int, docs_date: str):
    """-> (act, laws, notes) or None when not fully cached, 'skip' when there is nothing to build."""
    doc = jc(f'WetgevingDocument/{did}')
    if doc is False:
        return None
    if not doc or not doc.get('HeeftInhoud'):
        return 'skip'
    st = jc(f'v2/WetgevingDocument/{did}/Structuur?includeArtikelen=true&includeVersies=true')
    if st is False:
        return None
    if not st:
        return 'skip'
    own_key, own_law = law_of(doc)
    laws = {}
    pre2006 = (day(doc.get('BSDatum')) or '0000') < VERSIONING_FROM
    # per article: list of (from, to, text lines, credit keys)
    series = {}
    order = []
    labels = {}
    for a in articles(st):
        vs = [v for v in a['Versions'] if v.get('StartDatumConditie') in (None, 'SpecifiedDate') and v.get('StartDatum')]
        if not vs:
            continue
        k, kind, lab = unit_key(vs[0].get('ArtikelType') or a.get('ArtikelType'), (a.get('Titel') or '').strip())
        while k in series and series[k] and series[k][0][4] != a['Id']:
            k += '-x'
        if k not in series:
            series[k] = []
            order.append(k)
        labels[k] = (lab, kind)
        for i, v in enumerate(sorted(vs, key=lambda v: v['StartDatum'])):
            av = jc(f'WetgevingArtikelVersie/{v["Id"]}')
            if av is False:
                return None
            if av == 'ERR':
                return 'skip'
            if not av:
                continue
            rels = []
            rel_needed = need_rel(doc, {'Versions': vs}, i) or (v.get('EindDatum') and i == len(vs) - 1)
            if rel_needed:
                r = jc(f'WetgevingArtikelVersie/{v["Id"]}/ArtikelversieRelaties')
                if r is False:
                    return None
                if r == 'ERR':
                    return 'skip'
                rels = (r or {}).get('ResultatenLijst', [])
            series[k].append((day(v['StartDatum']), day(v.get('EindDatum')), clean_text(av.get('Tekst') or ''),
                              rels, a['Id'], v['Id']))
    if not series:
        return 'skip'

    def credit_for(rels, when: str, kinds: set[str]) -> list[str]:
        ks = []
        cand = [r for r in rels if r.get('RelatieType') in kinds]
        exact = [r for r in cand if day(r.get('StartDatum')) == when]
        for r in (exact or (cand if len(cand) == 1 else [])):
            lk, law = law_of({'WetgevingDocumentType': r.get('WetgevingDocumentType'), 'Datum': r['Datum'],
                              'BSDatum': r.get('BSDatum'), 'Opschrift': r.get('Opschrift'),
                              'WetgevingDocumentId': r['WetgevingDocumentId']})
            laws[lk] = law
            if lk not in ks:
                ks.append(lk)
        return ks

    # the dates at which anything changes
    floor = VERSIONING_FROM if pre2006 else None
    events = set()
    for k, ser in series.items():
        for (f, t, *_rest) in ser:
            events.add(max(f, floor) if floor else f)
            if t:
                nd = (dt.date.fromisoformat(t) + dt.timedelta(days=1)).isoformat()
                if not floor or nd > floor:
                    events.add(nd)
    events = sorted(events)

    def state_at(d: str) -> dict:
        out = {}
        for k in order:
            for (f, t, lines, rels, aid, vid) in series[k]:
                f2 = max(f, floor) if floor else f
                if f2 <= d and (t is None or t >= d) and any(c.isalnum() for c in ''.join(lines)):
                    out[k] = (lines, rels, vid)
        return out

    versions = []
    prev = {}
    first_from = None
    notes = []
    for d in events:
        cur = state_at(d)
        if not cur and not prev:
            continue
        changed = [k for k in order if (k in cur) != (k in prev) or (k in cur and cur[k][0] != prev[k][0])]
        if not changed:
            continue
        if not versions:
            first_from = d
            units = {k: {'label': labels[k][0], 'kind': labels[k][1],
                         'text': f'# {labels[k][0]}\n' + '\n'.join(cur[k][0]) + '\n'} for k in order if k in cur}
            versions.append({'from': d, 'source_url': f'{API}v2/WetgevingDocument/{did}/Structuur?includeArtikelen='
                             f'true&includeVersies=true', 'units': units, 'credits': {},
                             'sources': {k: f'{API}WetgevingArtikelVersie/{cur[k][2]}' for k in units}})
            prev = cur
            continue
        changes, credits = {}, {}
        for k in changed:
            if k in cur:
                changes[k] = {'label': labels[k][0], 'kind': labels[k][1],
                              'text': f'# {labels[k][0]}\n' + '\n'.join(cur[k][0]) + '\n'}
                ks = credit_for(cur[k][1], d, CHANGE - {'Opgeheven bij', 'Ingetrokken bij', 'Vernietigd bij'})
                if not ks and not pre2006 and k not in prev and not cur[k][1]:
                    ks = [own_key]     # staggered commencement of the act's own article
                elif not ks and not pre2006 and k not in prev:
                    ks = credit_for(cur[k][1], d, CHANGE)
            else:
                changes[k] = None
                ks = credit_for(prev[k][1], d, {'Opgeheven bij', 'Ingetrokken bij', 'Vernietigd bij'})
            if ks:
                credits[k] = ks
        if own_key in sum(credits.values(), []):
            laws[own_key] = own_law
        versions.append({'from': d, 'source_url': f'{API}v2/WetgevingDocument/{did}/Structuur?includeArtikelen=true'
                         f'&includeVersies=true', 'changes': changes, 'credits': credits,
                         'sources': {k: f'{API}WetgevingArtikelVersie/{cur[k][2]}' for k in changes if k in cur}})
        prev = cur
    if not versions:
        return 'skip'
    as_enacted = not pre2006
    if as_enacted:
        laws[own_key] = own_law
    # versions after the docs date go to the future branch (the builder does this by date)
    act = {'slug': f'{TYPE_ABBR.get(doc["WetgevingDocumentType"], "doc")}-{day(doc["Datum"])}-{did}',
           'short': own_law['label'],
           'title': f'{own_law["label"]} {own_law["title"]}'.strip(),
           'url': SITE.format(did), 'first_law': own_key if as_enacted else None, 'earlier_laws': [],
           'codex_id': did, 'numac': doc.get('Numac'), 'versions': []}
    for v in versions:
        src = v.pop('sources')
        v['note'] = None
        act['versions'].append(v)
        act.setdefault('_sources', []).append(src)
    srcs = act.pop('_sources')
    # keep per-version article sources out of the corpus, but return them for the letters check
    return act, laws, srcs


COUNTRY = {
    'code': 'BE-VLG', 'name': 'Flanders', 'slug': SLUG, 'lang': 'nl', 'tz': 'Europe/Brussels',
    'future_branch': 'toekomst',
    'publisher': {'name': 'Vlaamse Codex (Flemish Government)', 'email': 'codex@codex.vlaanderen.be.invalid'},
    'default_in_force_rule': {
        'text': ('Each version is dated by the start date the Vlaamse Codex gives the article version; a decree '
                 'without its own commencement clause takes effect ten days after its publication in the Belgisch '
                 'Staatsblad (Act of 31 May 1961, Art. 4).'),
        'source': 'https://codex.vlaanderen.be/'},
    'licence_note': ('Text: Vlaamse Codex, Flemish Government, https://codex.vlaanderen.be/. Official acts of the '
                     'authorities are not protected by copyright in Belgium (Code of Economic Law, Art. XI.172 §2).'),
}
SOURCE = {'name': 'Vlaamse Codex Open Data API', 'url': 'https://codex.opendata.api.vlaanderen.be/',
          'licence': ('Official acts are excluded from copyright (Code of Economic Law, Art. XI.172 §2); the Codex '
                      'publishes the API as open data and states no restriction on reuse.'),
          'notes': 'Every article version the Codex holds for each act, with its start and end dates and the '
                   'amending article ("Gewijzigd bij", "Ingevoegd bij", "Opgeheven bij", ...).'}
DECISIONS = [
    'Each version is the act as the Vlaamse Codex consolidates it, rebuilt article by article from the article '
    'versions and their start and end dates; a version starts on the day an article version starts or the day after '
    'one ends.',
    'Each changed article is credited to the act the Codex names for that article version ("Gewijzigd bij", '
    '"Vervangen bij", "Ingevoegd bij", "Opgeheven bij" and similar) whose start date is that day; an article that '
    'starts later than the rest of a new act with no such relation is credited to the act itself.',
    'The Codex keeps every version only for texts published in the Belgisch Staatsblad from 1 June 2006. For older '
    'acts the oldest available text is dated 1 June 2006 at the earliest and credited to the publisher as the oldest '
    'version available, since the Codex holds only the provisions still in force then.',
    'Article versions whose start date the Codex gives only as a condition ("to be set by the Flemish Government", '
    '"date undetermined") are left out until a date is set.',
    'An article version whose text has no letters or digits (the Codex prints "..." for an elided or '
    'repealed provision) counts as no article that day.',
    'Article text is taken without annotations (geannoteerd=false); one paragraph per line; the heading line is the '
    'article number.',
]
AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which acts to include; it wrote no law text. '
          'Every word of law comes from the Vlaamse Codex.']


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def parse(docs_date: str):
    out = FOLDER / 'corpus.d'
    out.mkdir(parents=True, exist_ok=True)
    srcmap = {}
    report = {}
    src = dict(SOURCE, retrieved=docs_date)

    def build(ids):
        acts, laws, complete = [], {}, True
        for did in ids:
            r = parse_doc(did, docs_date)
            if r is None:
                complete = False
                break
            if r == 'skip':
                continue
            a, l, s = r
            acts.append(a)
            laws.update(l)
            srcmap[a['slug']] = s
        return acts, laws, complete
    # 10: the special decree on the Flemish institutions; 11: the other special decrees
    core = core_ids(jc)
    acts, laws, ok = build(core[:1])
    if ok and acts:
        write_part(out / '10-instellingen.json', {'country': COUNTRY, 'sources': [src], 'laws': laws, 'acts': acts,
                                                 'decisions': DECISIONS, 'ai_use': AI_USE})
        report['10-instellingen'] = len(acts)
    if (FOLDER / '.cache' / 'fetch-core-done.txt').exists():
        acts, laws, ok = build(core[1:])
        if ok and acts:
            write_part(out / '11-bijzondere-decreten.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
            report['11-bijzondere-decreten'] = len(acts)
    dec = decree_ids(jc)
    fetched = (FOLDER / '.cache' / 'fetched-decrees.txt')
    have = set(fetched.read_text().split()) if fetched.exists() else set()
    alldone = (FOLDER / '.cache' / 'fetch-decrees-done.txt').exists()
    for pi in range(0, len(dec), PART_SIZE):
        chunk = dec[pi:pi + PART_SIZE]
        if not all(str(d) in have for d in chunk):
            break
        if len(chunk) < PART_SIZE and not alldone:
            break
        name = f'{20 + pi // PART_SIZE:03d}-decreten-{pi // PART_SIZE + 1}'
        if (out / f'{name}.json').exists():
            continue
        acts, laws, ok = build(chunk)
        if not ok:
            break
        write_part(out / f'{name}.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
        report[name] = len(acts)
    (FOLDER / '.cache' / 'sources.json').write_text(json.dumps(srcmap, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report))


# ---------------------------------------------------------------- independent letters check

class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, d):
        self.parts.append(d)


def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


def src_letters(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    p.close()
    t = ''.join(p.parts)
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return letters(t)


def letters_check(part_name: str) -> list[str]:
    """Re-reads every article version's raw API JSON with html.parser (not the regex cleaner the corpus used) and
    compares the letters and digits of each unit in each version (heading line dropped) with it. Also checks that
    the article number in the heading equals the Codex ArtikelNummer."""
    part = json.loads((FOLDER / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        units, srcs = {}, {}
        # the per-unit source of each version is recomputed from the cache, independently of the parser's state
        did = act['codex_id']
        st = jc(f'v2/WetgevingDocument/{did}/Structuur?includeArtikelen=true&includeVersies=true')
        vids = {}
        for a in articles(st):
            for v in a['Versions']:
                if v.get('StartDatum'):
                    vids.setdefault(a['Id'], []).append(v)
        allv = {}
        for aid, vs in vids.items():
            for v in vs:
                av = jc(f'WetgevingArtikelVersie/{v["Id"]}')
                if av:
                    allv[v['Id']] = av
        for v in act['versions']:
            if 'units' in v:
                units = dict(v['units'])
            else:
                for k, u in v['changes'].items():
                    if u is None:
                        units.pop(k, None)
                    else:
                        units[k] = u
            # expected: for each article, the version whose [start, end] covers this day (pre-2006 floor applied)
            d = v['from']
            exp = []
            for aid, vs in vids.items():
                for x in vs:
                    if x.get('StartDatumConditie') not in (None, 'SpecifiedDate'):
                        continue
                    s0 = x['StartDatum'][:10]
                    pre = act['first_law'] is None
                    s1 = max(s0, VERSIONING_FROM) if pre else s0
                    e = (x.get('EindDatum') or '9999')[:10]
                    if s1 <= d <= e and x['Id'] in allv:
                        t = src_letters(allv[x['Id']].get('Tekst') or '')
                        if t:
                            exp.append(t)
            mine = [letters('\n'.join(u['text'].splitlines()[1:])) for u in units.values()]
            if sorted(exp) != sorted(mine):
                a_, b_ = set(exp) - set(mine), set(mine) - set(exp)
                probs.append(f'{act["slug"]} {d}: {len(a_)} source-only, {len(b_)} corpus-only units; '
                             f'e.g. {(next(iter(a_)) if a_ else next(iter(b_)))[:60]}')
    return probs


# ---------------------------------------------------------------- docs, verify, publish

def _verified(extra=()) -> list[dict]:
    out = []
    for p in sorted((FOLDER / 'corpus.d').glob('*.json')):
        if p.with_suffix('.PUBLISH').exists() or p.stem in extra:
            out.append(json.loads(p.read_text(encoding='utf-8')))
    return out


def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {x.strftime("%B")} {x.year}'


def write_docs(docs_date: str, extra=(), out: Path | None = None):
    parts = _verified(extra)
    rows, nacts, nvers = [], 0, 0
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = _long(vs[0]['from']) if len(vs) == 1 else f'{_long(vs[0]["from"])} to {_long(vs[-1]["from"])}'
            hist = ('as enacted' if a.get('first_law') else 'oldest version available') + \
                (', then each consolidated version: ' if len(vs) > 1 else ', ')
            rows.append(f'| `{a["slug"]}/` | {a["title"][:160]} | {len(vs)} | {hist}{span} |')
    repo = out or (FOLDER / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# Flanders: law history in git

The law of the Flemish Region and Community (Vlaanderen, Belgium) as a git history: one file per article, one commit per amending act on the day it took effect, and the amending act as the commit's author. `git blame` names the act behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `be-vlg/`. The federal law is in [lexifina/belgium-law](https://github.com/lexifina/belgium-law).

The text is in Dutch, the official language of the Flemish institutions, exactly as the Vlaamse Codex publishes it.

## What this repository holds

{nacts} act{"s" if nacts != 1 else ""} with {nvers} versions so far: the special decree of 7 July 2006 on the Flemish institutions first, then the other special decrees and the decrees (codified decrees first), added in parts of about {PART_SIZE}. Orders of the Flemish Government (besluiten), ministerial orders and federal texts the Codex also holds are not included yet.

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

The Vlaamse Codex, the Flemish Government's consolidated collection of Flemish legislation (<https://codex.vlaanderen.be/>), through its Open Data API (<https://codex.opendata.api.vlaanderen.be/>). For each article it gives every version with its start and end date and the article of the act that made the change.

## Dates

- Each commit is dated at **noon, Europe/Brussels, on the day the version took effect**, as the Codex gives it. The date of the amending act is the `Enacted:` trailer, its publication in the Belgisch Staatsblad the `Published:` trailer.
- The Codex keeps every version only for texts published in the Belgisch Staatsblad from 1 June 2006. An act published from that day starts with its text as enacted, credited to the act itself. For an older act the history starts with the oldest text the Codex holds, dated no earlier than 1 June 2006 and credited to the publisher as the "oldest version available".
- Versions that take effect after the retrieval day are on the `toekomst` branch, never merged into `main`. Article versions whose start date is still to be set are left out.
- `--before="YYYY-MM-DD"` alone uses your clock's time of day; use `T23:59:59Z` or `tools/on.py`.

## Files

`<act>/art-005.md` is Art. 5, `art-005-1.md` Art. 5/1, `art-005-bis.md` Art. 5bis; `bijlage-...md` an annex. The first line is the article number; then one paragraph per line. Annotations are left out.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every article in every version equal those of the Codex's own text of the article version in force that day, read by a separate HTML parser.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

The author of a commit is the amending act (decree, special decree, order), with an e-mail address that cannot exist (`<act key>@codex.vlaanderen.be.invalid`). The committer is always Lexifina.

## Limits

This is not an official publication. The binding text is the one published in the Belgisch Staatsblad. Only the acts listed above are included, and for acts published before 1 June 2006 the history starts in 2006 at the earliest.
"""
    lic = """The law texts in this repository are official texts of the Flemish Region and Community (Belgium), taken
from the Vlaamse Codex (Flemish Government, https://codex.vlaanderen.be/) through its Open Data API.

Belgian law does not protect them by copyright. Code of Economic Law, Art. XI.172 §2: "Les actes officiels de
l'autorité ne donnent pas lieu au droit d'auteur." / "Officiële akten van de overheid geven geen aanleiding tot
auteursrecht." (Official acts of the authorities do not give rise to copyright.)

Source: Vlaamse Codex, Flemish Government. This repository is not an official publication; the binding text is the
one published in the Belgisch Staatsblad / Moniteur belge.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': 'be-vlg', 'code': 'BE-VLG', 'name': 'Flanders', 'level': 'region',
             'parent': 'be', 'repo': f'https://github.com/lexifina/{SLUG}-law',
             'build': f'built: special decrees and decrees ({nacts} acts, {nvers} versions) from the Vlaamse Codex',
             'language': 'nl', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


def _low(cmd, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                          creationflags=0x4000 if os.name == 'nt' else 0)


def _rm(d: Path):
    import stat

    def onerr(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if d.exists():
        shutil.rmtree(d, onexc=onerr)


def verify_part(part: str, docs_date: str) -> tuple[bool, str]:
    probs = letters_check(part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[0]}'
    tmp, build = DOCS / f'{SLUG}-law-verify', DOCS / f'{SLUG}-law-verifybuild'
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((FOLDER / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    for n in names + [part]:
        shutil.copy2(FOLDER / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-800:]
    c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
              str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, 'check.py output unreadable: ' + (c.stderr or c.stdout)[-600:]
    if any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated',
                                'missing_in_force')):
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300] + \
            json.dumps(res.get('details', [])[:3], ensure_ascii=False)[:500]
    p = json.loads((FOLDER / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    acts = p['acts']
    nv = sum(len(a['versions']) for a in acts)
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} from the Vlaamse Codex Open Data API: '
            f'letters-and-digits of every article in every version equal the Codex article version in force that day '
            f'(read with html.parser, separately from the corpus parser); scratch build of verified parts + this '
            f'part: check.py {res.get("versions")} versions, 0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return True, line


def publish(part: str, docs_date: str) -> str:
    ok, line = verify_part(part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    pub = FOLDER / 'corpus.d' / f'{part}.PUBLISH'
    tmp = pub.with_suffix('.ptmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    write_docs(docs_date, extra=[part])
    os.replace(tmp, pub)
    top = FOLDER / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'fetch':
        for w in sys.argv[2].split(','):
            fetch(w, int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif cmd == 'parse':
        parse(sys.argv[2])
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2])
        print('\n'.join(pr[:30]) or 'letters check: clean')
        print(len(pr), 'problems')
    elif cmd == 'docs':
        write_docs(sys.argv[2])
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3]))
