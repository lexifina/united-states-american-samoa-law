"""Latvia: cached likumi.lv consolidated versions (via Internet Archive) + vestnesis.lv law metadata -> corpus.json.

Reads only captures.json, acts.json and .cache/ (written by fetch.py). No network, no model. Deterministic.

Method, per act:
1. likumi.lv (published by VSIA "Latvijas Vēstnesis", the official publisher) lists every consolidated version
   ("redakcija") of an act with the day it took effect. fetch.py pins one archived capture of each version's page
   (/ta/id/<id>/redakcijas-datums/YYYY/MM/DD); the page's own version selector must name that version.
2. Each page is split into units (preamble, chapter headings, articles, transitional provisions, signatures); one
   paragraph per line. The notes "(30.04.2002. likuma redakcijā, kas stājas spēkā 05.11.2002.)" are not law text:
   they are taken out and used only to date and credit changes.
3. A unit that differs from the previous version is credited to the law(s) its note names with that version's
   in-force day; failing that, to its chapter heading's note for that day (a chapter replaced as a whole); else it
   is the publisher's ("unexplained"). An article shown as "(Izslēgts ar ... likumu ...)" is removed, credited to
   the law that note names.
4. Text before its law: if a version's page shows a unit whose note names an in-force day after the version starts
   (and before the next version), the unit keeps the previous version's text until that day, and a version of its
   own on that day brings the new words, credited to that law.
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import likumi  # noqa: E402
import vestnesis  # noqa: E402

PLACEHOLDER = '[Avots nedod šajā datumā spēkā esošo tekstu.]'

CACHE = HERE / '.cache'
ACTS = json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))
ORDER = ['satversme', 'kriminallikums', 'fizisko-personu-datu-apstrades-likums']
RETRIEVED = '2026-10-29'


def cached(url: str) -> bytes | None:
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    return p.read_bytes() if p.exists() else None


def wb(c: dict) -> str:
    return f"https://web.archive.org/web/{c['ts']}id_/{c['url']}"


def law_meta(lid: int, ev: dict) -> dict:
    """Title, enacted and published days from the law's official publication on vestnesis.lv."""
    url = f'https://www.vestnesis.lv/ta/id/{lid}'
    raw = cached(url)
    title, enacted, published, issue, issuer = None, ev.get('law_date'), None, None, None
    if raw:
        s = raw.decode('utf-8', 'replace')
        m = re.search(r'<title>(.*?)</title>', s, re.S)
        if m:
            title = likumi.norm(htmllib.unescape(m.group(1)).replace(' - Latvijas Vēstnesis', ''))
            if title.startswith('Latvijas Vēstnesis'):
                title = None  # no publication of this law on vestnesis.lv (it starts in 1993)
        m = re.search(r'Pieņemts:\s*(?:<[^>]+>\s*)*(\d\d\.\d\d\.\d{4})', s)
        if m:
            enacted = likumi.iso(m.group(1))
        t = htmllib.unescape(re.sub(r'<[^>]+>', ' ', s))
        m = re.search(r'Publicēts oficiālajā (?:laikrakstā|izdevumā) "Latvijas Vēstnesis", (\d{1,2})\.(\d{1,2})\.(\d{4})\.?, Nr\. ([0-9A-Za-z()/.]+?)(?=\s|$)', t)
        if m:
            published = f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
            issue = m.group(4).rstrip('.')
        m = re.search(r'Izdevējs:\s*([^\n]+?)\s+Veids:', re.sub(r'\s+', ' ', t))
        if m:
            issuer = m.group(1).strip()
    court = ev.get('court') or (issuer or '').startswith('Satversmes tiesa')
    d = enacted or ev.get('law_date')
    dd = f'{d[8:10]}.{d[5:7]}.{d[0:4]}.' if d else ''
    if court:
        label = f'Satversmes tiesas {dd} spriedums'
    elif issuer and issuer not in ('Saeima',):
        label = f'{issuer} {dd} akts'
    else:
        label = f'Saeimas {dd} likums'
    return {'key': f'{"st" if court else "likums"}-{d}-{lid}' if d else f'lv-{lid}', 'label': label,
            'title': title or ACTS.get('_law_titles', {}).get(str(lid)) or ev.get('law_slug') or str(lid), 'kind': 'court' if court else 'law', 'enacted': enacted,
            'published': published, 'issue': issue,
            'url': f'https://likumi.lv/ta/id/{lid}' + (f'-{ev["law_slug"]}' if ev.get('law_slug') else ''),
            'vestnesis': url if raw else None}


def build_act(slug: str, caps: dict, laws: dict, decisions: list, log: list) -> dict:
    spec = ACTS[slug]
    lid = spec['likumi_id']
    vers = caps['versions']
    pages = []
    missing = []
    for v in vers:
        c = caps['chosen'].get(v['from'])
        if not c and v is vers[0] and spec.get('original'):
            # the base version as first published in the official gazette (vestnesis.py)
            url = f'https://www.vestnesis.lv/ta/id/{spec["original"]["vestnesis_id"]}'
            raw = cached(url)
            p = vestnesis.parse_original(raw, spec['original']['title'])
            p['version'] = v['from']
            p['source_url'] = url
            p['sha256'] = hashlib.sha256(raw).hexdigest()
            pages.append(p)
            decisions.append(f'{spec["short"]}: no capture of the likumi.lv base version ({v["from"]}) is archived; the '
                             f'first version is the act as published in the official gazette ({url}), which in force '
                             f'from {v["from"]} is the act as enacted.')
            continue
        if not c:
            missing.append(v['from'])
            log.append(f'{slug}: version {v["from"]} has no archived page; its changes are dated from the notes of the next '
                       f'page')
            continue
        raw = cached(wb(c))
        p = likumi.parse_page(raw, lid)
        assert p['version'] == v['from'], (slug, v['from'], p['version'])
        p['source_url'] = wb(c)
        p['sha256'] = hashlib.sha256(raw).hexdigest()
        pages.append(p)
    version_days = {v['from'] for v in vers}
    # resolve notes that name a law only by its date (no link) through the act's other notes
    by_date: dict[str, set] = {}
    slugs: dict[int, str] = {}
    for p in pages:
        for u in list(p['units'].values()) + list(p['removed'].values()):
            for e in u['events']:
                if e['law_id']:
                    by_date.setdefault(e['law_date'], set()).add(e['law_id'])
                    slugs[e['law_id']] = e['law_slug']
    unresolved = set()
    for p in pages:
        for u in list(p['units'].values()) + list(p['removed'].values()):
            keep = []
            for e in u['events']:
                if not e['law_id']:
                    ids = by_date.get(e['law_date'], set())
                    if len(ids) != 1:
                        unresolved.add(e['law_date'])
                        continue
                    e['law_id'] = next(iter(ids))
                    e['law_slug'] = slugs[e['law_id']]
                keep.append(e)
            u['events'] = keep
    if unresolved:
        log.append(f'{slug}: notes naming a law only by date that no other note links: {sorted(unresolved)}')
    law_days: dict[int, set] = {}
    for p in pages:
        for u in list(p['units'].values()) + list(p['removed'].values()):
            for e in u['events']:
                if e['in_force']:
                    law_days.setdefault(e['law_id'], set()).add(e['in_force'])
        if p.get('dup_differs'):
            log.append(f'{slug} {p["version"]}: repeated transitional section differs at {p["dup_differs"]}')

    def lawkey(ev):
        m = law_meta(ev['law_id'], ev)
        k = m.pop('key')
        m.pop('issue', None)
        m.pop('vestnesis', None)
        if k not in laws:
            laws[k] = {**m, 'temporary_until': None, 'restores': None, 'note': None}
        return k

    # 1. expand pages into dated states, deferring units whose note names a later in-force day (rule 4)
    states = []  # [{'from', 'units', 'events', 'removed', 'source_url', 'sha256', 'deferred': {...}}]
    prev_units: dict = {}
    def matches(events, day):
        return [e for e in events if e['in_force'] == day or
                (e['in_force'] is None and day in law_days.get(e['law_id'], ()))]

    for i, p in enumerate(pages):
        nxt = pages[i + 1]['version'] if i + 1 < len(pages) else None
        # a listed version with no archived page between the previous page and this one: units whose note in this page
        # names that day take their new words then (a placeholder if they changed again on this page's day)
        for day in [d for d in missing if states and states[-1]['from'] < d < p['version']]:
            u2 = dict(states[-1]['units'])
            only = []
            for k in sorted(set(u2) | set(p['units']) | set(p['removed'])):
                src = p['units'].get(k) or p['removed'].get(k)
                if src is None:
                    continue
                old = u2.get(k)
                new_t = p['units'][k]['text'] if k in p['units'] else None
                if old is not None and new_t is not None and ''.join(old['text'].split()) == ''.join(new_t.split()):
                    continue
                if not matches(src['events'], day):
                    continue
                only.append(k)
                if matches(src['events'], p['version']):
                    u2[k] = {**(old or p['units'].get(k) or {'label': src['label'], 'kind': 'art'}),
                             'text': PLACEHOLDER + '\n', 'events': src['events'], 'parent': None}
                    decisions.append(f'{spec["short"]}: {src["label"]} changed on {day} and again on {p["version"]}; no '
                                     f'version in force on {day} is archived, so that day reads "{PLACEHOLDER}".')
                elif k in p['units']:
                    u2[k] = dict(p['units'][k])
                else:
                    u2.pop(k, None)
            if not only:
                log.append(f'{slug} {day}: no note in the {p["version"]} page names this day; nothing is dated to it')
                decisions.append(f'{spec["short"]}: likumi.lv lists a version from {day}, but no capture of it is archived '
                                 f'and no note in the next version names that day, so the record has no commit on it; '
                                 f'any change made that day shows on {p["version"]}.')
                continue
            states.append({'from': day, 'units': u2, 'page': p, 'same_day': False, 'only': only, 'missing': True})
        if states:
            prev_units = states[-1]['units']
        deferred: dict[str, list[str]] = {}
        units = {k: dict(u) for k, u in p['units'].items()}
        for k, u in p['units'].items():
            later = sorted({e['in_force'] for e in u['events'] if e['in_force'] and e['in_force'] > p['version']
                            and (nxt is None or e['in_force'] < nxt) and e['in_force'] not in version_days})
            if not later:
                continue
            old = prev_units.get(k)
            if old is not None and old['text'] == u['text']:
                continue
            day = later[-1]
            deferred.setdefault(day, []).append(k)
            if old is None:
                units.pop(k)
            else:
                units[k] = dict(old)
                units[k]['events'] = u['events']
            decisions.append(f'{spec["short"]}: {u["label"]} is shown in the {p["version"]} version of likumi.lv with a note '
                             f'putting it in force on {day}; it keeps its earlier text until then and changes on {day}.')
        states.append({'from': p['version'], 'units': units, 'page': p, 'same_day': False})
        for day in sorted(deferred):
            u2 = dict(states[-1]['units'])
            for k in deferred[day]:
                u2[k] = dict(p['units'][k])
            states.append({'from': day, 'units': u2, 'page': p, 'same_day': False, 'only': deferred[day]})
        prev_units = states[-1]['units']

    # 1b. captures of different years break the same paragraphs differently (and the gazette's 1998 page splits headings
    # its own way): a text that differs from the next version's only in spacing or line breaks takes the next one's form,
    # so the newest page's layout runs back through the history and spacing alone is never a change
    canon: dict[str, str] = {}
    for st in reversed(states):
        units2 = {}
        for k, u in st['units'].items():
            t = u['text']
            if k in canon and canon[k] != t and ''.join(canon[k].split()) == ''.join(t.split()):
                u = {**u, 'text': canon[k]}
            canon[k] = u['text']
            units2[k] = u
        st['units'] = units2

    # 2. credits
    out_versions = []
    prev = None
    for st in states:
        p = st['page']
        day = st['from']
        units = {k: {'label': u['label'], 'kind': u['kind'], 'text': u['text']} for k, u in st['units'].items()}
        credits = {}
        if prev is not None:
            keys = sorted(set(prev) | set(units))
            for k in keys:
                a, b = prev.get(k), units.get(k)
                if (a or {}).get('text') == (b or {}).get('text') and (a or {}).get('label') == (b or {}).get('label'):
                    continue
                src = st['units'].get(k) or p['removed'].get(k) or {'events': []}
                def match(events):
                    # a law the note names for this day, or one it names undated whose in-force day elsewhere in the
                    # act's notes is this day
                    return [e for e in events if e['in_force'] == day or
                            (e['in_force'] is None and day in law_days.get(e['law_id'], ()))]
                if a is not None and b is not None and ''.join(a['text'].split()) == ''.join(b['text'].split()) and a['label'] == b['label']:
                    units[k] = dict(a)  # only spacing or line breaks differ between two captures: not a change
                    continue
                evs = match(src['events'])
                if not evs and st['units'].get(k, {}).get('parent'):
                    par = p['units'].get(st['units'][k]['parent'])
                    if par:
                        evs = match(par['events'])
                if evs:
                    credits[k] = sorted({lawkey(e) for e in evs})
                else:
                    log.append(f'{slug} {day}: {k} changed with no note for that day (unexplained)')
        out_versions.append({'from': day, 'source_url': p['source_url'], 'sha256': p['sha256'], 'units': units,
                             'credits': credits})
        prev = units
    # large acts: changes instead of full units after the first version
    if len(out_versions) > 20:
        full_prev = None
        for v in out_versions:
            cur = v['units']
            if full_prev is not None:
                ch = {k: cur.get(k) for k in sorted(set(full_prev) | set(cur)) if full_prev.get(k) != cur.get(k)}
                del v['units']
                v['changes'] = ch
            full_prev = cur
    act = {'slug': slug, 'short': spec['short'], 'title': spec['title'],
           'url': f'https://likumi.lv/ta/id/{lid}-{spec["likumi_slug"]}',
           'first_law': spec.get('first_law', {}).get('key'), 'earlier_laws': [], 'versions': out_versions}
    if spec.get('first_law'):
        fl = dict(spec['first_law'])
        k = fl.pop('key')
        laws[k] = {**fl, 'temporary_until': None, 'restores': None, 'note': fl.get('note')}
    return act


def main():
    caps_all = json.loads((HERE / 'captures.json').read_text(encoding='utf-8'))
    laws, decisions, log, acts = {}, [], [], []
    decisions += [
        'Built in Latvian, the official language; the README is in English first.',
        'Text comes from likumi.lv, the consolidated-legislation site of VSIA "Latvijas Vēstnesis" (the official '
        'publisher). likumi.lv states that its consolidated texts are informative; the official publication is the '
        'gazette "Latvijas Vēstnesis" (vestnesis.lv), from which each amending law\'s title and publication are taken.',
        'likumi.lv does not answer from this machine (HTTPS times out), so every version page is an Internet Archive '
        '`id_` capture, pinned by timestamp in source_url; the page\'s own version selector must name the version.',
        'In-force days are the ones likumi.lv gives for each version ("redakcija") and in each note '
        '("kas stājas spēkā"); a version is never dated by publication.',
        'Notes in the consolidated text ("... likuma redakcijā, kas stājas spēkā ...", "Ar grozījumiem, kas izdarīti '
        'ar ...") are left out of the files and used only for credits.',
        'An article shown as "(Izslēgts ar ... likumu ...)" is removed from the tree on that day, credited to the law '
        'named; its number is not kept as a placeholder file.',
        'Typesetting is normalised once: no-break spaces become spaces, curly double quotes become ", en and em dashes '
        'become -; guillemets (« ») are kept as printed; superscript numbers (70.<sup>11</sup>) become Unicode '
        'superscript digits (70.¹¹).',
        'Captures from different years break the same paragraphs differently; a unit whose text differs from the next '
        'version only in spacing or line breaks takes the next version\'s layout, so spacing alone is never a change.',
        'likumi.lv editorial blocks are left out: "PIEZĪMES" (TV430, quoting amending laws\' own transitional clauses), '
        'placeholders for provisions not yet in force ("(Punkts stājas spēkā ... un iekļauts likuma redakcijā uz ...)"), '
        'and the second copy of the transitional provisions that pages captured before about 2016 repeat.',
        'A note that lists several amending laws but dates only the last ("ar A., B. un C. likumu, kas stājas spēkā D") '
        'dates only C; A and B are credited on a day only when another note of the act gives that day for them. Notes '
        'that name a law by its date without a link are resolved to the one law of that date linked elsewhere in the act.',
        'legalize-dev/legalize-lv was checked (data "brīvi pieejams"): for these acts it holds no real history (one '
        'commit of today\'s text for the Criminal Law and the data law; 2026 snapshots for the Satversme), so no text '
        'was taken from it.',
    ]
    for slug in ORDER:
        if slug in caps_all and ACTS.get(slug):
            acts.append(build_act(slug, caps_all[slug], laws, decisions, log))
    decisions += ACTS.get('_decisions', [])
    req = 0
    rq = CACHE / 'requests.jsonl'
    wb_n = vs_n = 0
    if rq.exists():
        for l in rq.read_text(encoding='utf-8').splitlines():
            r = json.loads(l)
            if 'archive.org' in r['url']:
                wb_n += 1
            elif 'vestnesis.lv' in r['url']:
                vs_n += 1
    corpus = {
        'country': {
            'code': 'LV', 'name': 'Latvia', 'slug': 'latvia', 'lang': 'lv', 'tz': 'Europe/Riga',
            'future_branch': 'nakotne',
            'publisher': {'name': 'Latvijas Vēstnesis (likumi.lv)', 'email': 'likumi@likumi.lv.invalid'},
            'default_in_force_rule': {
                'text': 'Satversme art. 69: a law takes effect fourteen days after its promulgation unless the law sets '
                        'another term ("Likums stājas spēkā četrpadsmit dienas pēc izsludināšanas, ja likumā nav '
                        'noteikts cits termiņš"). Each in-force day here is the one likumi.lv records for the version or '
                        'provision, which applies that rule or the law\'s own clause.',
                'source': 'https://likumi.lv/ta/id/57980-latvijas-republikas-satversme'},
            'licence_note': 'Text: likumi.lv, VSIA "Latvijas Vēstnesis" (consolidated versions, informative), read '
                            'through Internet Archive captures; law metadata: the official gazette "Latvijas Vēstnesis" '
                            '(www.vestnesis.lv). Legislation is not protected by copyright in Latvia (Autortiesību '
                            'likums, art. 6). Latvijas Vēstnesis states that re-use of officially published information '
                            'is to be agreed with the official publisher in writing (vestnesis.lv/atkalizmantosana, read '
                            '2026-10-29); no such agreement has been made, so this repository stays private.'},
        'sources': [
            {'name': 'likumi.lv (VSIA "Latvijas Vēstnesis")', 'url': 'https://likumi.lv', 'retrieved': RETRIEVED,
             'requests': 0, 'licence': 'no copyright in legislation (Autortiesību likums art. 6); re-use terms of the '
                                      'official publisher apply (vestnesis.lv/atkalizmantosana)',
             'notes': 'Consolidated versions ("redakcijas") with in-force days and per-article notes naming the '
                      'amending law. Not fetched directly: HTTPS to likumi.lv times out from this machine.'},
            {'name': 'Internet Archive Wayback Machine (id_ raw captures)', 'url': 'https://web.archive.org/',
             'retrieved': RETRIEVED, 'requests': wb_n,
             'licence': 'Internet Archive terms of use', 'notes': 'Every version pins its capture timestamp in '
                                                                    'source_url; captures.json lists them.'},
            {'name': 'Latvijas Vēstnesis, official gazette (www.vestnesis.lv)', 'url': 'https://www.vestnesis.lv',
             'retrieved': RETRIEVED, 'requests': vs_n,
             'licence': 'official publication; re-use to be agreed in writing with the publisher (MK noteikumi Nr. 536)',
             'notes': 'Title, adoption day and gazette issue of every amending law (/ta/id/<id>). robots.txt '
                      'Crawl-delay 1 kept.'},
            {'name': 'data.gov.lv (Latvian open data portal)', 'url': 'https://data.gov.lv', 'retrieved': RETRIEVED,
             'requests': 2, 'licence': 'n/a', 'notes': 'Checked for a legislation dataset or bulk route: none '
                                                       '(Saeima publishes only sitting data; CC0).'},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions,
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) chose the sources and wrote fetch.py, likumi.py '
                   'and parse.py; it did not write, edit or summarise any legal text. parse.py is deterministic and runs '
                   'no model; every line of law comes from an archived likumi.lv page in the cache.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    tmp.replace(HERE / 'corpus.json')
    (HERE / 'parse.log').write_text('\n'.join(log) + '\n', encoding='utf-8')
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions')
    print(len(laws), 'laws;', len(log), 'log lines')


if __name__ == '__main__':
    main()
