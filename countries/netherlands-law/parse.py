"""Turns the cached BWB versions into scripts/netherlands-law/corpus.json (see scripts/gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/netherlands-law/parse.py

Reads only .cache/ (written by fetch.py); no network. Deterministic: the same cache gives the same bytes.

What it does, per act in acts.json:
- takes every version ("toestand") the BWB manifest still shows (zichtdatum_eind 9999-12-31; a superseded _0 is
  replaced by the corrected _1 for the same day), in order of its in-force date (datum_inwerkingtreding);
- writes one unit per article (artikel), plus one `inhoud` unit holding the act's headings (Boek, Titel, Hoofdstuk,
  Afdeling, Paragraaf). Articles the BWB marks "vervallen" (repealed) or "nogniet" (not yet in force) are absent;
- credits each changed article to the Staatsblad publication the BWB names on that article (bron="Stb.2017-82"),
  but only when the article's own in-force date (inwerking) is the version's day. Anything else is left
  uncredited, so the builder commits it as unexplained, by the publisher;
- names each law by the Staatsblad issue's own metadata title (officielebekendmakingen.nl), where it has one.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

RETRIEVED = '2026-10-28'
STRUCT = {'boek', 'deel', 'titeldeel', 'hoofdstuk', 'afdeling', 'paragraaf', 'sub-paragraaf', 'circulaire.divisie',
          'divisie'}
SKIP = {'meta-data', 'kop', 'lidnr', 'li.nr', 'jcis', 'jci'}
GONE = {'vervallen', 'nogniet'}
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
log: Counter = Counter()
notes: list[str] = []


def roman(s: str) -> int | None:
    if not re.fullmatch(r'[IVXLC]+', s):
        return None
    total = 0
    for a, b in zip(s, s[1:] + ' '):
        v = ROMAN[a]
        total += -v if b != ' ' and ROMAN[b] > v else v
    return total


def norm(s: str) -> str:
    s = s.replace('\xa0', ' ').replace(' ', ' ').replace(' ', ' ').replace('\xad', '')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r' ([,.;:])(?=\s|$)', r'\1', s)


def inline(el: ET.Element) -> str:
    """The running text of an element: references and emphasis as plain text, editorial notes in brackets."""
    out = [el.text or '']
    for ch in el:
        if ch.tag not in SKIP and ch.tag not in ('noot', 'voetnoot', 'aanhaling.noot'):
            t = inline(ch)
            out.append(f'[{norm(t)}]' if ch.tag == 'redactie' and norm(t) else t)
        out.append(ch.tail or '')
    return ''.join(out)


BLOCKS = {'al', 'lid', 'lijst', 'li', 'table', 'tgroup', 'tbody', 'thead', 'row', 'tussenkop', 'al-groep',
          'structuurtekst', 'definitielijst', 'definitie-item', 'aanhaling', 'artikel', 'wat', 'nadruk'}


def render(el: ET.Element) -> list[str]:
    """One line per paragraph, list item or table row."""
    lines: list[str] = []
    for ch in el:
        if ch.tag in SKIP:
            continue
        if ch.tag == 'lid':
            nr = norm(inline(ch.find('lidnr'))) if ch.find('lidnr') is not None else ''
            sub = render(ch)
            if nr and sub:
                sub[0] = f'{nr}{"" if nr[-1] in ".)" else "."} {sub[0]}'
            elif nr:
                sub = [nr]
            lines += sub
        elif ch.tag == 'li':
            nr = norm(inline(ch.find('li.nr'))) if ch.find('li.nr') is not None else ''
            sub = render(ch)
            if not sub and (ch.text or '').strip():
                sub = [norm(inline(ch))]
            if nr and sub:
                sub[0] = f'{nr} {sub[0]}'
            elif nr:
                sub = [nr]
            lines += sub
        elif ch.tag == 'row':
            cells = [norm(inline(e)) for e in ch if e.tag == 'entry']
            if any(cells):
                lines.append(' | '.join(cells))
        elif ch.tag in ('al', 'tussenkop', 'kop.al') or not any(g.tag not in SKIP for g in ch):
            t = norm(inline(ch))
            if t:
                lines.append(t)
        else:
            lines += render(ch)
    return lines


def article_key(nr: str, label: str) -> str:
    n = nr.strip()
    m = re.fullmatch(r'(\d+)\s*([a-z]*)', n.lower())
    if m:
        return f'art-{int(m.group(1)):03d}{m.group(2)}'
    r = roman(n)
    if r:
        return f'add-art-{r:02d}'
    slug = re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')
    log['article number not numeric'] += 1
    return f'art-{slug or re.sub(r"[^a-z0-9]+", "-", label.lower())}'


def heading(el: ET.Element) -> str:
    kop = el.find('kop')
    if kop is None:
        return ''
    parts = [norm(inline(kop.find(t))) for t in ('label', 'nr') if kop.find(t) is not None]
    head = ' '.join(p for p in parts if p)
    titel = kop.find('titel')
    if titel is not None and norm(inline(titel)):
        head = f'{head}. {norm(inline(titel))}' if head else norm(inline(titel))
    return head


def read_version(raw: bytes) -> dict:
    """units {key: {label, kind, text}}, attrs {key: article attributes}, gone {key: attrs}, struct attrs."""
    root = ET.fromstring(raw)
    units: dict = {}
    attrs: dict = {}
    gone: dict = {}
    toc: list[str] = []
    struct: list[dict] = []

    def walk(el: ET.Element, depth: int) -> None:
        for ch in el:
            if ch.tag == 'meta-data':
                continue
            if ch.tag == 'artikel':
                kop = ch.find('kop')
                nr = norm(inline(kop.find('nr'))) if kop is not None and kop.find('nr') is not None else ''
                key = article_key(nr, ch.get('label', '')) if nr else 'art-000'
                if ch.get('status') in GONE:
                    gone[key] = dict(ch.attrib)
                    continue
                if key in units:
                    log[f'duplicate article key {key}'] += 1
                    i = 2
                    while f'{key}-{i}' in units:
                        i += 1
                    key = f'{key}-{i}'
                head = heading(ch) or ch.get('label', key)
                body = render(ch)
                units[key] = {'label': f'Art. {nr}' if nr else head, 'kind': 'art',
                              'text': '\n'.join([f'# {head}'] + body) + '\n'}
                attrs[key] = dict(ch.attrib)
            elif ch.tag in STRUCT:
                if ch.get('status') not in GONE:
                    h = heading(ch)
                    if h:
                        toc.append('#' * min(depth + 2, 6) + ' ' + h)
                        struct.append(dict(ch.attrib))
                walk(ch, depth + 1)
            elif ch.tag in ('wetgeving', 'wet-besluit', 'wettekst', 'regeling', 'regeling-tekst', 'bijlage'):
                walk(ch, depth)
    walk(root.find('wetgeving') if root.find('wetgeving') is not None else root, 0)
    if toc:
        units['inhoud'] = {'label': 'Inhoud', 'kind': 'contents', 'text': '\n'.join(['# Inhoud'] + toc) + '\n'}
    corrections = len(root.findall('./redactionele-correcties/redactionele-correctie'))
    return {'units': units, 'attrs': attrs, 'gone': gone, 'struct': struct, 'corrections': corrections}


def law_key(bron: str) -> str | None:
    m = re.fullmatch(r'(\w+)\.(\d{4})-(\d+)', bron or '')
    return f'{m.group(1).lower()}-{m.group(2)}-{m.group(3)}' if m else None


def wti_laws(raw: bytes) -> dict[str, list[str]]:
    """{in-force day: [Staatsblad ids that the WTI lists as taking effect that day]}"""
    out: dict[str, list[str]] = {}
    for m in re.finditer(rb'<datum waarde="(\d{4}-\d\d-\d\d)">(.*?)</datum>', raw, re.S):
        ids = []
        for o in re.findall(rb'<ontstaansbron>(.*?)</ontstaansbron>', m.group(2), re.S):
            ids += re.findall(rb'urlidentifier="([a-z]+-\d{4}-\d+)"', o)
        out[m.group(1).decode()] = sorted({i.decode() for i in ids})
    return out


def law_meta(bron: str) -> dict:
    p = fetch.cache_path(fetch.law_url(bron))
    if not p.exists():
        return {}
    s = p.read_text(encoding='utf-8')
    get = lambda name: (re.search(rf'name="{re.escape(name)}"[^>]*content="([^"]*)"', s) or [None, None])[1]
    import html
    return {'title': html.unescape(get('DC.title') or ''), 'signed': get('OVERHEIDop.datumOndertekening'),
            'issued': get('DCTERMS.issued'), 'type': get('DC.type')}


def build_act(slug: str, spec: dict, laws: dict, uses: Counter) -> dict:
    bwb = spec['bwb']
    exprs = sorted((e for e in fetch.expressions(fetch.fetch(fetch.manifest_url(bwb), offline=True))
                    if e['seen_until'] == '9999-12-31'), key=lambda e: e['from'])
    wti = wti_laws(fetch.fetch(fetch.wti_url(bwb), offline=True))
    versions = []
    prev = None
    dropped = 0

    def credit(attr: dict | None, day: str) -> list[str]:
        if not attr or attr.get('inwerking') != day or not law_key(attr.get('bron')):
            return []
        key = law_key(attr['bron'])
        if key not in laws:
            m = law_meta(attr['bron'])
            year, nr = key.split('-')[1:]
            title = m.get('title') or ''
            kind = 'decree' if re.match(r'(Koninklijk )?[Bb]esluit', title) else 'law'
            laws[key] = {'label': f'Stb. {year}, {nr}', 'title': title or f'Staatsblad {year}, nr. {nr}',
                         'kind': kind, 'enacted': attr.get('ondertekening_bron') or m.get('signed'),
                         'published': attr.get('publicatie_bron') or m.get('issued'),
                         'url': f'https://zoek.officielebekendmakingen.nl/{key}' if int(year) >= 1995 else None,
                         'temporary_until': None, 'restores': None, 'note': None}
            for d in ('enacted', 'published'):
                if laws[key][d] and not re.fullmatch(r'\d{4}-\d\d-\d\d', laws[key][d]):
                    laws[key][d] = None
        uses[key] += 1
        return [key]

    for e in exprs:
        url = fetch.version_url(bwb, e['label'])
        raw = fetch.fetch(url, offline=True)
        v = read_version(raw)
        day = e['from']
        if prev is None:
            # The first version is the act as enacted only if every article still carries the act's own
            # enacting publication (the bron on its intitule) and took effect on this day.
            first = {(a.get('bron'), a.get('inwerking')) for a in v['attrs'].values()}
            enacting = (re.search(rb'<intitule [^>]*?\sbron="([^"]+)"', raw) or [None, b''])[1].decode()
            first_law = None
            if len(first) == 1:
                bron, inw = next(iter(first))
                if inw == day and law_key(bron) and bron == enacting:
                    first_law = credit({'bron': bron, 'inwerking': inw, **next(iter(v['attrs'].values()))}, day)[0]
            ver = {'from': day, 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'units': v['units'],
                   'credits': {}}
            versions.append(ver)
            prev = v
            continue
        changes = {}
        credits = {}
        for k in sorted(set(prev['units']) | set(v['units'])):
            a, b = prev['units'].get(k), v['units'].get(k)
            if a == b:
                continue
            changes[k] = b
            if k == 'inhoud':
                c = sorted({x for s in v['struct'] for x in credit(s, day)})
            elif b is None:
                c = credit(v['gone'].get(k), day)
                if not c and len(wti.get(day, [])) == 1 and wti[day][0].startswith('stb-'):
                    c = credit({'bron': 'Stb.' + wti[day][0][4:], 'inwerking': day}, day)
                    log['removal credited from the WTI (the only law that day)'] += 1
            else:
                c = credit(v['attrs'].get(k), day)
            if c:
                credits[k] = c
            else:
                log['unexplained unit change'] += 1
        # A Besluit publishing the text of the revised Grondwet (Art. 141 Gw) is the bron the BWB gives the
        # wording, but the revision laws the WTI lists for the same day made the change: say so on the Besluit.
        for k in {x for c in credits.values() for x in c}:
            if 'ter bekendmaking van de tekst' in (laws[k]['title'] or '') and not laws[k]['note']:
                others = [o for o in wti.get(day, []) if o != k]
                if others:
                    labels = '; '.join('Stb. {}, {}'.format(*o.split('-')[1:]) for o in others)
                    laws[k]['note'] = (f'Publishes the text of the revised {spec["title"]} (Art. 141 Grondwet); the BWB names '
                                       f'it as the source of the wording. The revision laws the BWB lists as taking '
                                       f'effect the same day: {labels}.')
        if not changes:
            dropped += 1
            prev = v
            continue
        ver = {'from': day, 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'changes': changes,
               'credits': credits}
        if any(k not in credits for k in changes) and v['corrections']:
            ver['note'] = (f'The BWB lists {v["corrections"]} editorial correction(s) (redactionele correcties) in '
                           'this version; changes it does not attribute to a law are committed as unexplained.')
        versions.append(ver)
        prev = v
    if dropped:
        notes.append(f'{slug}: {dropped} BWB version(s) change no rendered text (only metadata or references) and '
                     'are not separate versions here.')
    return {'slug': slug, 'short': spec['short'], 'title': spec['title'],
            'url': f'https://wetten.overheid.nl/{bwb}', 'first_law': first_law, 'earlier_laws': [],
            'versions': versions}


def main() -> None:
    laws: dict = {}
    uses: Counter = Counter()
    acts = [build_act(slug, spec, laws, uses) for slug, spec in fetch.ACTS.items()]
    reqs = sum(1 for _ in open(fetch.CACHE / 'requests.jsonl', encoding='utf-8'))
    for slug in fetch.ACTS:
        pass
    corpus = {
        'country': {
            'code': 'NL', 'name': 'Netherlands', 'slug': 'netherlands', 'lang': 'nl', 'tz': 'Europe/Amsterdam',
            'future_branch': 'toekomst',
            'publisher': {'name': 'KOOP, wetten.overheid.nl (Basiswettenbestand)', 'email': 'bwb@wetten-overheid.invalid'},
            'default_in_force_rule': {
                'text': 'Bekendmakingswet art. 10(1): where a law names no date, it takes effect on the first day of '
                        'the second calendar month after its publication. Every version here carries the BWB\'s own '
                        'in-force date (datum_inwerkingtreding), which already applies each law\'s own commencement.',
                'source': 'https://wetten.overheid.nl/jci1.3:c:BWBR0004287&artikel=10'},
            'licence_note': 'Wet- en regelgeving: Basiswettenbestand (wetten.overheid.nl), KOOP, Ministerie van '
                            'Binnenlandse Zaken en Koninkrijksrelaties; open data, CC0 1.0 (public domain dedication).',
        },
        'sources': [
            {'name': 'Basiswettenbestand (BWB), wetten.overheid.nl', 'url': 'https://repository.officiele-overheidspublicaties.nl/bwb/',
             'retrieved': RETRIEVED, 'requests': reqs, 'licence': 'CC0 1.0',
             'notes': 'Per act: manifest.xml (every dated version), the toestand XML of each version, and the WTI '
                      '(wetstechnische informatie). Versions in the BWB start between 2002 and 2018 depending on the act.'},
            {'name': 'officielebekendmakingen.nl (Staatsblad metadata)', 'url': 'https://zoek.officielebekendmakingen.nl/',
             'retrieved': RETRIEVED, 'requests': None, 'licence': 'CC0 1.0',
             'notes': 'Title, signature and publication date of each crediting Staatsblad issue, 1995 onwards.'},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': [
            'Acts: the Grondwet, Burgerlijk Wetboek Boek 1, the Wetboek van Strafrecht and the UAVG (Phase 1), chosen because the BWB holds dated versions for each.',
            'History starts at the oldest version the BWB holds for each act (2002 for the codes and the Grondwet, 2018 for the UAVG); earlier history is not reconstructed.',
            'Only versions still visible in the BWB manifest (zichtdatum_eind 9999-12-31) are used; where the BWB re-issued a day as _1, the _1 replaces the _0.',
            'Each version is dated by the BWB\'s datum_inwerkingtreding, the day it took effect.',
            'A changed article is credited to the Staatsblad publication the BWB names on that article (bron), only when the article\'s own inwerking date equals the version\'s day; otherwise it is left unexplained.',
            'A removed article is credited to the bron on its "vervallen" entry; if it vanished without one, to the only Staatsblad issue the WTI lists for that day, if there is exactly one.',
            'Articles marked "vervallen" (repealed) or "nogniet" (not yet in force) are absent from the tree; the BWB\'s "Vervallen" placeholders are not kept as text.',
            'Editorial notes (redactie) are kept in square brackets; footnotes and metadata are dropped.',
            'Headings of Boeken, Titels, Hoofdstukken, Afdelingen and Paragrafen are kept in one inhoud unit per act, credited to the bron of the headings that took effect that day.',
            'Law kind: a Staatsblad title starting "Besluit" is a decree; everything else is a law.',
            'Grondwet 2018-12-21: the BWB credits the text to Stb. 2019, 33 (the Besluit of 16 January 2019 publishing the revised Grondwet, Art. 141 Gw) with in-force date 2018-12-21, before that Besluit was signed; the in-force date is kept as the BWB gives it.',
        ] + notes,
        'ai_use': ['none: no model wrote, summarised or classified any text in this corpus. The parser was written by Claude Code (claude-opus-5-5).'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'corpus.json')
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', 'first_law', a['first_law'])
    print('laws', len(laws), dict(log))


if __name__ == '__main__':
    main()
