"""Swiss cities for git-for-law (gitlaw-scraper-dell, municipal tier, 2026-10-31): one public repo per city,
lexifina/switzerland-<city>-city-law, built by scripts/gitlaw_common/build.py from corpus.d parts.

Cities that publish their systematic collection on LexWork (Sitrox) reuse ch_cantons.py's fetcher, parser and
letters check; this module only swaps in the city's own selection (the Gemeindeordnung first, then every other act
in force, in systematic order, about 50 per part) and the city's README, LICENSE and jurisdiction.json.

    python -X utf8 scripts/world-law/ch_cities.py fetch winterthur        # one process, one request at a time
    python -X utf8 scripts/world-law/ch_cities.py parse winterthur 2026-10-31
    python -X utf8 scripts/world-law/ch_cities.py publish winterthur 10-verfassung 2026-10-31

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402

MIN_PAUSE = 3.0   # seconds between requests to a city host (new hosts: never faster)

# key -> (code, English name, official name, host, language, Gemeindeordnung number, canton key, canton name,
#         city legal-notice URL, the notice's own words on law texts)
CITIES = {
    'winterthur': ('ZH-WINTERTHUR', 'Winterthur', 'Stadt Winterthur', 'winterthur.tlex.ch', 'de', '1.1-1', 'zurich',
                   'Zurich', 'https://stadt.winterthur.ch/rechtliches',
                   'Die im Internet verwendeten Informationsmittel (wie Texte, Illustrationen, Logos, Fotos, Videos, '
                   'Ton-Dokumente, Grafiken sowie das Layout) der Stadt Winterthur sind immaterialgüterrechtlich und '
                   'insbesondere urheberrechtlich geschützt, soweit sie nicht (wie z.B. Gesetzestexte und '
                   'Gerichtsurteile) durch einschlägige Rechtsnormen ausdrücklich vom Schutz ausgenommen werden.'),
    # Stadt Zug: Impressum (stadtzug.ch/de/compliance/impressum) has no copyright or reproduction clause; its
    # Datenschutz link is the shared Zug "Nutzungsregelung und Datenschutz" (zg.ch), which has none either.
    'zug': ('ZG-ZUG', 'Zug', 'Stadt Zug', 'zug.tlex.ch', 'de', '1.1-1', 'zug', 'Zug',
            'https://stadtzug.ch/de/compliance/impressum',
            'NOCLAUSE:The city\'s own legal notice (https://stadtzug.ch/de/compliance/impressum) and the usage rules '
            'it links to for the shared Zug web platform (https://zg.ch/de/nutzungsregelung-datenschutz) place no '
            'restriction on reproducing the content of the website.'),
    # Stadt Kloten: Impressum (www.kloten.ch/impressum, i-web) has no copyright or reproduction clause; its only
    # permission rule is for the coat of arms (Wappenschutzgesetz Art. 8). Datenschutz page: none either.
    'kloten': ('ZH-KLOTEN', 'Kloten', 'Stadt Kloten', 'kloten.tlex.ch', 'de', '', 'zurich', 'Zurich',
               'https://www.kloten.ch/impressum',
               'NOCLAUSE:The city\'s own legal notice (https://www.kloten.ch/impressum) places no restriction on '
               'reproducing the content of the website; its only permission rule concerns the city\'s coat of arms.'),
    # Gemeinden of the canton of Zug on the shared zg.ch platform: their Impressum and the shared "Nutzungsregelung
    # und Datenschutz" (which names "Internetauftritte ... von Zuger Gemeinden") have no reproduction clause.
    'steinhausen': ('ZG-STEINHAUSEN', 'Steinhausen', 'Gemeinde Steinhausen', 'steinhausen.tlex.ch', 'de', '', 'zug',
                    'Zug', 'https://www.zg.ch/behoerden/gemeinden/steinhausen/verwaltung/kontakt/impressum',
                    'NOCLAUSE:The municipality\'s own legal notice '
                    '(https://www.zg.ch/behoerden/gemeinden/steinhausen/verwaltung/kontakt/impressum) and the usage '
                    'rules of the shared Zug web platform it is published on '
                    '(https://zg.ch/de/nutzungsregelung-datenschutz) place no restriction on reproducing the content '
                    'of the website.'),
    'huenenberg': ('ZG-HUENENBERG', 'Hünenberg', 'Gemeinde Hünenberg', 'huenenberg.tlex.ch', 'de', '', 'zug', 'Zug',
                   'https://zg.ch/de/impressumtwo',
                   'NOCLAUSE:The legal notice of the shared Zug web platform the municipality publishes on '
                   '(https://zg.ch/de/impressumtwo) and its usage rules (https://zg.ch/de/nutzungsregelung-datenschutz) '
                   'place no restriction on reproducing the content of the website.'),
    # Gemeinde Oberägeri (i-web): Impressum has no copyright or reproduction clause; its only consent rule is the
    # social-media netiquette (posts marked with the Oberägeri brand). "Disclaimer" leads to the Datenschutz page.
    'oberaegeri': ('ZG-OBERAEGERI', 'Oberägeri', 'Gemeinde Oberägeri', 'oberaegeri.tlex.ch', 'de', '', 'zug', 'Zug',
                   'https://www.oberaegeri.ch/impressum',
                   'NOCLAUSE:The municipality\'s own legal notice (https://www.oberaegeri.ch/impressum) places no '
                   'restriction on reproducing the content of the website.'),
    # Gemeinde Unterägeri (i-web): Impressum has no copyright or reproduction clause; "Disclaimer" leads to Datenschutz.
    'unteraegeri': ('ZG-UNTERAEGERI', 'Unterägeri', 'Gemeinde Unterägeri', 'unteraegeri.tlex.ch', 'de', '', 'zug',
                    'Zug', 'https://www.unteraegeri.ch/impressum',
                    'NOCLAUSE:The municipality\'s own legal notice (https://www.unteraegeri.ch/impressum) places no '
                    'restriction on reproducing the content of the website.'),
    'menzingen': ('ZG-MENZINGEN', 'Menzingen', 'Gemeinde Menzingen', 'menzingen.tlex.ch', 'de', '', 'zug', 'Zug',
                  'https://zg.ch/de/impressumtwo',
                  'NOCLAUSE:The legal notice of the shared Zug web platform the municipality publishes on '
                  '(https://zg.ch/de/impressumtwo) and its usage rules (https://zg.ch/de/nutzungsregelung-datenschutz) '
                  'place no restriction on reproducing the content of the website.'),
    # Gemeinde Weesen (i-web): Impressum has no copyright or reproduction clause.
    'weesen': ('SG-WEESEN', 'Weesen', 'Gemeinde Weesen', 'weesen.tlex.ch', 'de', '', 'st-gallen', 'St. Gallen',
               'https://www.weesen.ch/impressum',
               'NOCLAUSE:The municipality\'s own legal notice (https://www.weesen.ch/impressum) places no '
               'restriction on reproducing the content of the website.'),
    # Ville de Delémont: Mentions légales hold only a social-media charter; footer "Tous droits réservés", no consent
    # clause.
    'delemont': ('JU-DELEMONT', 'Delémont', 'Ville de Delémont', 'delemont.tlex.ch', 'fr', '', 'jura', 'Jura',
                 'https://www.delemont.ch/fr/Votre-commune/Mentions-legales/Mentions-legales.html',
                 'NOCLAUSE:The city\'s own legal notice '
                 '(https://www.delemont.ch/fr/Votre-commune/Mentions-legales/Mentions-legales.html) places no '
                 'restriction on reproducing the content of the website; the site footer reads "© 2026 Municipalité '
                 'de Delémont. Tous droits réservés", which the copyright exclusion above qualifies for law texts.'),
    # Wave 3 (DNS sweep of every municipality above ~5,000, 2026-11-01 evening).
    # Gemeinde Ilanz/Glion: Impressum says only "Das Copyright für sämtliche Inhalte dieser Website liegt bei der
    # Gemeinde Ilanz/Glion." (no consent clause).
    'ilanz-glion': ('GR-ILANZ-GLION', 'Ilanz/Glion', 'Gemeinde Ilanz/Glion', 'ilanz-glion.tlex.ch', 'de', '11.1',
                    'graubunden', 'Graubünden', 'https://www.ilanz-glion.ch/impressum',
                    'NOCLAUSE:The municipality\'s own legal notice (https://www.ilanz-glion.ch/impressum) says only '
                    '"Das Copyright für sämtliche Inhalte dieser Website liegt bei der Gemeinde Ilanz/Glion." and '
                    'places no restriction on reproduction; the copyright exclusion above covers the law texts.'),
    # Gemeinde Ehrendingen (CommunityNet): Impressum, "Rechtliches" and its privacy statement have no clause.
    'ehrendingen': ('AG-EHRENDINGEN', 'Ehrendingen', 'Gemeinde Ehrendingen', 'ehrendingen.tlex.ch', 'de', '',
                    'aargau', 'Aargau', 'https://www.ehrendingen.ch/impressum/',
                    'NOCLAUSE:The municipality\'s own legal notice (https://www.ehrendingen.ch/impressum/ and '
                    'https://www.ehrendingen.ch/rechtliches/) places no restriction on reproducing the content of '
                    'the website.'),
    # Gemeinde Bad Ragaz (i-web): Impressum without the copyright paragraph.
    'bad-ragaz': ('SG-BAD-RAGAZ', 'Bad Ragaz', 'Gemeinde Bad Ragaz', 'badragaz.tlex.ch', 'de', '', 'st-gallen',
                 'St. Gallen', 'https://www.badragaz.ch/impressum',
                 'NOCLAUSE:The municipality\'s own legal notice (https://www.badragaz.ch/impressum) places no '
                 'restriction on reproducing the content of the website.'),
    # Gemeinde Ettingen: no Impressum on the site (/de/impressum 404); its Datenschutz page has no clause.
    'ettingen': ('BL-ETTINGEN', 'Ettingen', 'Gemeinde Ettingen', 'ettingen.tlex.ch', 'de', '', 'basel-landschaft',
                 'Basel-Landschaft', 'https://www.ettingen.ch/de/datenschutz',
                 'NOCLAUSE:The municipality\'s website (https://www.ettingen.ch/) has no legal notice of its own; '
                 'its data-protection page places no restriction on reproducing the content of the website.'),
}

CHARTER = re.compile(r'^(Gemeindeordnung|Gemeindeverfassung|Verfassung der Gemeinde|Organisationsreglement|R[èe]glement d.organisation)', re.I)
_orig_constitution_sn = C.constitution_sn


def constitution_sn(h):
    """A city whose Gemeindeordnung number is not given: the first in-force act whose title names the charter."""
    if h.host in {CITIES[c][3] for c in CITIES} and not h.const:
        for x in C.index_entries(h):
            if CHARTER.search(x['title']) and not x.get('abrogated'):
                h.const = x['systematic_number']
                return h.const
        raise RuntimeError(f'{h.slug}: no Gemeindeordnung in the index')
    return _orig_constitution_sn(h)


C.constitution_sn = constitution_sn


def key(city: str) -> str:
    return f'{city}-city'


def register(city: str):
    code, en, native, host, lang, go, *_ = CITIES[city]
    C.CANTONS[key(city)] = (code, f'{en} (city)', native, host, lang, go)


for _c in CITIES:
    register(_c)

_CITY_HOSTS = {CITIES[c][3] for c in CITIES}
_orig_law_candidates = C.law_candidates
_orig_ord_candidates = C.ordinance_candidates


def law_candidates(h):
    if h.host in _CITY_HOSTS:
        return []   # a city has no Gesetze: everything after the Gemeindeordnung goes into the Erlasse parts
    return _orig_law_candidates(h)


def ordinance_candidates(h):
    if h.host not in _CITY_HOSTS:
        return _orig_ord_candidates(h)
    go = C.constitution_sn(h)
    return [x['systematic_number'] for x in C.index_entries(h)
            if x['systematic_number'] != go and not x.get('abrogated')]


C.law_candidates = law_candidates
C.ordinance_candidates = ordinance_candidates


# ---------------------------------------------------------------- one LexWork backend: spacing, daily cap, stop
LEXWORK_NET = '93.187.192.0/22'          # every LexWork host seen resolves here: one backend for the cap
DAILY_CAP = 4800                         # coordinator: about 5,000 per host per day; margin for gate probes
GUARD = Path(__file__).resolve().parent / 'ch_towns'
BLOCKED = GUARD / 'LEXWORK-BLOCKED'      # written on any challenge: no LexWork fetch ever again from this code
LAST = GUARD / 'lexwork-last.txt'        # end time of the last request, shared by consecutive fetch processes


def _in_block(hostname: str) -> bool:
    import ipaddress
    import socket
    try:
        return ipaddress.ip_address(socket.gethostbyname(hostname)) in ipaddress.ip_network(LEXWORK_NET)
    except OSError:
        return True   # unknown: count it


def lexwork_today() -> int:
    """Requests sent today (UTC) to the LexWork block, from every request log on this machine."""
    import datetime as _dt
    import glob
    day = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d')
    seen: dict[str, bool] = {}
    n = 0
    logs = set(glob.glob(str(C.ROOT / 'switzerland-*' / '.cache' / 'requests.jsonl')))
    logs.add(str(GUARD / 'probe-cache' / 'requests.jsonl'))
    for f in logs:
        try:
            lines = open(f, encoding='utf-8').read().splitlines()
        except OSError:
            continue
        for line in lines:
            if f'"at": "{day}' not in line:
                continue
            try:
                h = urllib.parse.urlsplit(json.loads(line)['url']).netloc
            except (ValueError, KeyError):
                continue
            if h not in seen:
                seen[h] = _in_block(h)
            n += seen[h]
    return n


_orig_get = C.Host.get


def _guarded_get(self, url):
    if self.host not in _CITY_HOSTS:
        return _orig_get(self, url)
    c = self.cached(url)
    if c is not False:
        return c
    import time as _t
    if BLOCKED.exists():
        raise RuntimeError(f'LexWork blocked earlier ({BLOCKED.read_text(encoding="utf-8").strip()}): no request')
    if not hasattr(self, '_today'):
        self._today = lexwork_today()
    if self._today >= DAILY_CAP:
        raise RuntimeError(f'daily cap: {self._today} LexWork requests today (cap {DAILY_CAP}); resume tomorrow')
    self.pause = max(self.pause, MIN_PAUSE)
    try:
        last = float(LAST.read_text())
    except (OSError, ValueError):
        last = 0.0
    self.last = max(self.last, last)
    wait = self.last + self.pause - _t.time()
    if wait > 0:
        _t.sleep(wait)
    t0 = _t.time()
    r = C.subprocess.run(['curl', '-s', '-m', '60', '--compressed', '-A', C.UA, '-w', '\n%{http_code}', url],
                         capture_output=True)
    self.last = _t.time()
    LAST.write_text(str(self.last))
    self.count += 1
    self._today += 1
    body, _, code = r.stdout.rpartition(b'\n')
    code = code.decode().strip()
    with open(self.cache / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': C.dt.datetime.now(C.dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'url': url,
                            'status': code, 'bytes': len(body), 'secs': round(self.last - t0, 2),
                            'curl_rc': r.returncode}) + '\n')
    if code == '404':
        self.path(url).write_bytes(b'null')
        return None
    if code == '200':
        try:
            d = json.loads(body)
        except ValueError:
            d = None
        if d is not None:
            tmp = self.path(url).with_suffix('.tmp')
            tmp.write_bytes(body)
            C.os.replace(tmp, self.path(url))
            return d
        why = f'{self.host}: HTTP 200 but not JSON (challenge page?) at {url}'
    elif r.returncode:
        why = f'{self.host}: curl error {r.returncode} (timeout or connection) at {url}'
    else:
        why = f'{self.host}: HTTP {code} at {url}'
    # Any challenge, 403, 429, 5xx, timeout or odd answer: stop for good, and stop the chain too. A person decides.
    stamp = C.dt.datetime.now(C.dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    BLOCKED.write_text(f'{stamp} {why}\n', encoding='utf-8')
    (GUARD / 'STOP').write_text(f'{stamp} {why}\n', encoding='utf-8')
    raise RuntimeError('stopped for good: ' + why)


C.Host.get = _guarded_get


def host(city: str) -> C.Host:
    h = C.Host(key(city))
    h.pause = max(h.pause, MIN_PAUSE)
    return h


def fetch(city: str):
    """robots.txt alone first (stop on a refusal), then settings, types, index, the Gemeindeordnung with all its
    versions, then every other act in force with all its versions. One request at a time, MIN_PAUSE apart (or the
    Crawl-delay)."""
    h = host(city)
    why = C.robots_ok(h)
    h.pause = max(h.pause, MIN_PAUSE)
    if why:
        print(f'{city}: STOPPED {why}', flush=True)
        return
    try:
        h.settings()
        h.types()
        h.index()
        C.fetch_act(h, C.constitution_sn(h))
        (h.cache / 'fetch-done.txt').write_text('0 laws (a city has none)\n', encoding='utf-8')
        print(f'{city}: Gemeindeordnung fetched ({h.count} requests)', flush=True)
        n = 0
        for sn in ordinance_candidates(h):
            if (h.dir / 'STOP').exists():
                print(f'{city}: STOPPED by the stop file ({h.count} requests)', flush=True)
                return
            d = h.act(sn)
            if not d or not C.ord_type_ok(h, d):
                continue
            C.fetch_act(h, sn)
            n += 1
            if n % 10 == 0:
                print(f'{city}: {n} acts fetched ({h.count} requests)', flush=True)
        (h.cache / 'fetch-ord-done.txt').write_text(f'{n} acts\n', encoding='utf-8')
        print(f'{city}: done, {n} acts ({h.count} requests)', flush=True)
    except Exception as e:
        print(f'{city}: STOPPED {e}', flush=True)


def country_block(slug: str, h, settings: dict) -> dict:
    city = slug[:-5]
    code, en, native, hst, lang, go, ck, cn, notice, _ = CITIES[city]
    return {
        'code': f'CH-{code}', 'name': f'{en} (city)', 'slug': f'switzerland-{slug}', 'lang': lang,
        'tz': 'Europe/Zurich', 'future_branch': C.FUTURE[lang],
        'publisher': {'name': f'{native}, {settings["collection_names"]["systematic"]} ({hst})',
                      'email': f'rechtssammlung@{hst}.invalid'},
        'default_in_force_rule': {
            'text': ('Each version is dated by the day the city\'s systematic collection says it took effect '
                     '("in Kraft seit / von"); municipal acts take effect on the day the act or the city sets.'),
            'source': f'https://{hst}/'},
        'licence_note': (f'Text: {native}, {settings["collection_names"]["systematic"]}, https://{hst}/. '
                         'Laws and decrees are not protected by copyright in Switzerland (Art. 5 para. 1 let. a URG).'),
    }


C.country_block = country_block
C.AI_USE[:] = ['A model (Claude) wrote the fetch and parse code and chose which acts to include; it wrote no law '
               'text. Every word of law comes from the city\'s own collection.']
_orig_decisions = C.decisions


def decisions(chron: str) -> list[str]:
    return [d.replace('canton\'s', 'city\'s') for d in _orig_decisions(chron)]


C.decisions = decisions


def write_docs(slug: str, docs_date: str, extra=(), out: Path | None = None):
    if not slug.endswith('-city'):
        return _orig_write_docs(slug, docs_date, extra, out)
    city = slug[:-5]
    code, en, native, hst, lang, go, ck, cn, notice, quote = CITIES[city]
    h = host(city)
    st = h.cached(h.url('settings'))
    sysname, chron = st['collection_names']['systematic'], st['collection_names']['chronological']
    rows = []
    nacts = nvers = 0
    for part in C._verified(slug, extra):
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = C._long(vs[0]['from']) if len(vs) == 1 else \
                f'{C._long(vs[0]["from"])} to {C._long(vs[-1]["from"])}'
            hist = ('as enacted, then ' if a.get('first_law') else 'oldest version available, then ') \
                if len(vs) > 1 else ('as enacted, ' if a.get('first_law') else 'one version (the oldest available), ')
            rows.append(f'| `{a["slug"]}/` | {a["title"]} ({sysname} {a["systematic_number"]}) | {len(vs)} | '
                        f'{hist}{"each consolidated version: " if len(vs) > 1 else ""}{span} |')
    repo = out or (C.folder(slug) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en} (city): law history in git

The municipal law of the city of {en} ({native}, canton of {cn}, Switzerland) as a git history: one file per article, one commit per amending act on the day it took effect, and the amending act as the commit's author. `git blame` names the act behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law). The law of the canton of {cn} is in [lexifina/switzerland-{ck}-law](https://github.com/lexifina/switzerland-{ck}-law); federal law is in [lexifina/switzerland-law](https://github.com/lexifina/switzerland-law).

The text is in {C.LANGNAME[lang]}, exactly as the city publishes it.

## What this repository holds

{nacts} act{"s" if nacts != 1 else ""} with {nvers} versions so far: the Gemeindeordnung (the city's charter) first, then the city's other enactments in force (ordinances, regulations, tariffs and decisions), in the order of the systematic collection, added in parts of about 50. Agreements, concessions, directives and repealed acts are not included.

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

The {sysname} (systematic collection) of the city, published by the city at <https://{hst}/>. For each act it gives every consolidated version it holds, with the day each version took effect, and a change table listing each amendment: its decision date, the day it took effect, the provision it touched and its entry in the chronological collection ({chron}). Annexes the collection publishes only as separate PDF files are not included.

## Dates

- Each commit is dated at **noon, Europe/Zurich, on the day the version took effect**, as the collection gives it ("in Kraft seit / von"). The decision date of each amending act is the `Enacted:` trailer.
- An act's first commit is its oldest version in the collection. It is credited to the act as enacted only when the change table shows no amendment in force before it; otherwise it is the "oldest version available", naming the earlier amendments.
- Versions that take effect after the retrieval day are on the `{C.FUTURE[lang]}` branch, never merged into `main`.
- `--before="YYYY-MM-DD"` alone uses your clock's time of day; use `T23:59:59Z` or `tools/on.py`.

## Files

`<act>/art-005.md` is Art. 5 (or § 5), `art-005a.md` Art. 5a; `ingress.md` holds the title, date and preamble; `gliederung.md` the section headings; `schluss.md` the closing formula and signatures. One paragraph or list item per line. Amendment markers (`*`), footnote numbers and the "Stand" date are left out.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the city's own text of that version, and every article's text appears in it in order.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

The author of a commit is the amending act, named by its entry in the chronological collection ({chron}), with an e-mail address that cannot exist (`<act key>@{hst}.invalid`). Where one version holds changes by several amending acts and the change table does not say which provision each one touched, the commit names them all. The committer is always Lexifina.

## Limits

This is not an official publication. The binding text is the one the city publishes as binding. The history starts with the oldest consolidated version the collection holds for each act, which for many acts is later than the act's enactment. Only the acts listed above are included.
"""
    lic = f"""The law texts in this repository are official texts of the city of {en} ({native}), taken from its
systematic collection ({sysname}, https://{hst}/).

Swiss law does not protect them by copyright. Federal Act on Copyright and Related Rights (URG, SR 231.1),
Art. 5 para. 1: "Keinen urheberrechtlichen Schutz geniessen: a. Gesetze, Verordnungen, völkerrechtliche Verträge
und andere amtliche Erlasse; [...]" (Not protected by copyright: a. acts, ordinances, international treaties and
other official enactments.)

{quote[9:] if quote.startswith('NOCLAUSE:') else f'The city{chr(39)}s own legal notice ({notice}) says the same of law texts: "{quote}"'}

This repository is not an official publication; the binding text is the one the city publishes as binding.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': f'ch-{code.lower()}', 'code': f'CH-{code}', 'name': f'{en} (city)', 'level': 'municipality',
             'parent': f'ch-{code.split("-")[0].lower()}', 'repo': f'https://github.com/lexifina/switzerland-{slug}-law',
             'build': f'built: Gemeindeordnung and municipal enactments ({nacts} acts, {nvers} versions) from the {sysname}',
             'language': lang, 'sources': 1}
    if lang == 'fr':
        readme = readme.replace("the Gemeindeordnung (the city's charter)",
                                "the city's charter (its règlement d'organisation)").replace(
            '("in Kraft seit / von")', '("en vigueur")')
        juris['build'] = juris['build'].replace('Gemeindeordnung', "règlement d'organisation")
    if not native.startswith(('Stadt ', 'Ville ', 'Città ')):
        readme, lic = (re.sub(r'(?<![-(])\bcity\b(?![)-])', 'municipality', x) for x in (readme, lic))
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


_orig_write_part = C.write_part


def write_part(p: Path, part: dict):
    # a chunk whose acts are all published only as PDF (no XHTML) yields no act: write no empty part
    if not part.get('acts'):
        return
    _orig_write_part(p, part)


C.write_part = write_part

_orig_write_docs = C.write_docs
C.write_docs = write_docs


def create_repo(city: str) -> str:
    """One API call, only after every gate passed; nothing is pushed here (autopush publishes main)."""
    import subprocess
    code, en, *_ = CITIES[city]
    repo = f'switzerland-{key(city)}-law'
    ls = subprocess.run(['git', 'ls-remote', f'https://github.com/lexifina/{repo}.git'], capture_output=True, text=True)
    if ls.returncode == 0:
        return 'EXISTS ' + (ls.stdout.splitlines() or [''])[0][:60]
    p = subprocess.run(['gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
                        '-f', f'description={en} (Switzerland) municipal law as git history'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return 'created' if p.returncode == 0 else 'FAILED ' + p.stderr[:300]


if __name__ == '__main__':
    cmd, city = sys.argv[1], sys.argv[2]
    if cmd == 'fetch':
        fetch(city)
    elif cmd == 'parse':
        C.parse_canton(key(city), sys.argv[3])
    elif cmd == 'docs':
        write_docs(key(city), sys.argv[3])
    elif cmd == 'letters':
        probs = C.letters_check(key(city), sys.argv[3])
        print('\n'.join(probs[:40]) or 'letters check: clean')
    elif cmd == 'publish':
        for part in sys.argv[3:-1]:
            print(city, part, C.publish(key(city), part, sys.argv[-1]), flush=True)
    elif cmd == 'create':
        print(city, create_repo(city))
