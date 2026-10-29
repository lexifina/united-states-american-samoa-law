"""gitlaw-MX parser: the Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP) from the
Cámara de Diputados' consolidated PDFs (LeyesBiblio pdf/LFPDPPP.pdf), every distinct copy the Internet Archive holds
(2011-2025), into corpus.d/20-lfpdppp.json. Reads only .cache/ (fetch.py texts lfpdppp; fetch.py refs lfpdppp).

    python -X utf8 parse_lfpdppp.py

One act, two laws of the same name: the LFPDPPP of 2010 (DOF 05-07-2010, never amended) and the LFPDPPP of 2025
(DOF 20-03-2025), which abrogated it, then amended DOF 14-11-2025. The 2025 law's arrival is one version credited to
its decree: each copy's own heading names the law it prints ("Nueva Ley DOF 20-03-2025"). Later changes are credited
from the paragraph notes as in parse.py. Extraction, normalisation, in-force rules and the coverage check are
parse.py's.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse  # noqa: E402
from parse import CACHE, LEYES, norm, note_dates, unit_text, capture_url, cache_path  # noqa: E402

OUT = HERE / 'corpus.d' / '20-lfpdppp.json'
REF_URL = 'https://web.archive.org/web/20261015124207id_/https://www.diputados.gob.mx/LeyesBiblio/ref/lfpdppp.htm'
ORDINAL_ART = re.compile(r'(?i)^art[íi]culos?\s+(?:primero|segundo|tercero|cuarto|quinto|sexto|s[ée]ptimo|octavo|'
                         r'noveno|d[ée]cimo)\b')
TRANS = re.compile(r'(?i)^(?:art[íi]culos?\s+)?transitorios?\s*:?\.?$')


def dmy(day: str) -> str:
    return f'{day[8:10]}-{day[5:7]}-{day[:4]}'


def ref_decrees() -> list[dict]:
    """The decrees on the Cámara's reform page for the act: 'DECRETO ... | DOF dd-mm-yyyy | Word'."""
    raw = cache_path(REF_URL).read_bytes()
    try:
        t = raw.decode('utf-8')
    except UnicodeDecodeError:
        t = raw.decode('cp1252', 'replace')
    links = re.findall(r'(?i)href="([^"]+\.pdf)"', t)
    text = html.unescape(re.sub(r'(?s)<[^>]+>', ' ', re.sub(r'(?is)<(script|style).*?</\1>', '', t)))
    text = re.sub(r'\s+', ' ', text)
    out = []
    for m in re.finditer(r'(DECRETO por [^|]*?)\s*\|\s*DOF (\d\d)-(\d\d)-(\d{4})', text):
        day = f'{m.group(4)}-{m.group(3)}-{m.group(2)}'
        pdf = next((l for l in links if re.search(r'_' + m.group(2) + r'\D', l) or day.replace('-', '') in l), None)
        out.append({'dof': day, 'name': norm(m.group(1)), 'url': LEYES + 'ref/' + pdf if pdf else LEYES + 'ref/lfpdppp.htm'})
    return out


def segment_law(paras: list[dict]) -> dict:
    """A federal law as the Cámara prints it -> units: decreto (the expedition decree's opening), estructura,
    art-NNN, transitorios (the rest of the expedition decree), transitorios-<DOF date> per reform decree."""
    n = len(paras)
    i = 0
    dropped = []
    while i < n and not re.match(r'(?i)^(al margen|.*a sus habitantes sabed)', paras[i]['t']):
        dropped.append(paras[i]['t'])
        i += 1
    units: dict[str, dict] = {}

    def unit(key, label, kind):
        return units.setdefault(key, {'label': label, 'kind': kind, 'lines': [], 'notes': []})

    def add(u, p):
        u['lines'].append(p['t'])
        u['notes'].extend(p['notes'])

    dec = unit('decreto', 'Decreto de expedición', 'preamble')
    while i < n and not paras[i].get('heading'):
        add(dec, paras[i])
        i += 1
    est = unit('estructura', 'Capítulos y secciones', 'structure')
    cur, last, in_heading = None, 0, False
    while i < n:
        p = paras[i]
        t = p['t']
        if (TRANS.match(t) and p['centered']) or ORDINAL_ART.match(t) or t.upper().startswith('ARTÍCULOS TRANSITORIOS DE DECRETOS'):
            break
        m = parse.ART.match(t)
        if m and (int(m.group(1)) == last + 1 or (p['bold'] and int(m.group(1)) > last)):
            last = int(m.group(1))
            cur = unit(f'art-{last:03d}', f'Artículo {last}', 'art')
            in_heading = False
            add(cur, p)
        elif p.get('heading') or (in_heading and p['centered'] and p['bold']) or (p.get('heading') is None and in_heading and p['centered']):
            in_heading = True
            add(est, p)
        else:
            in_heading = False
            add(cur if cur is not None else est, p)
        i += 1
    tr = unit('transitorios', 'Transitorios del decreto de expedición', 'transitional')
    while i < n and not paras[i]['t'].upper().startswith('ARTÍCULOS TRANSITORIOS DE DECRETOS'):
        add(tr, paras[i])
        i += 1
    i += 1
    anchors = [j for j in range(i, n) if parse.PUB.match(paras[j]['t'])]
    starts = [a - 1 for a in anchors]
    blocks = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else n
        m = parse.PUB.match(paras[s + 1]['t'])
        blocks.append({'date': parse.spanish_date(*m.groups()), 'title': paras[s]['t'], 'paras': paras[s:e]})
    return {'units': units, 'blocks': blocks, 'dropped': dropped, 'articles': last}


def header_law(paras: list[dict]) -> str | None:
    """'Nueva Ley publicada en el Diario Oficial de la Federación el 20 de marzo de 2025' on the cover."""
    for p in paras[:6]:
        m = re.search(r'Nueva Ley publicada en el Diario Oficial de la Federaci[óo]n el (\d{1,2}) de ([a-z]+) de (\d{4})', p['t'])
        if m:
            return parse.spanish_date(*m.groups())
    return None


def build() -> dict:
    caps = json.loads((CACHE / 'caps-lfpdppp.json').read_text(encoding='utf-8'))
    for c in caps:
        c['path'] = str(cache_path(capture_url(c)))
    with ProcessPoolExecutor(max_workers=7) as ex:
        res = list(ex.map(parse.extract, [c['path'] for c in caps]))
    for c, r in zip(caps, res):
        c.update(r)
        c['sha256'] = hashlib.sha256(Path(c['path']).read_bytes()).hexdigest()
        c['law_day'] = header_law(c['paras'])
    by_reform: dict[str, dict] = {}
    for c in caps:
        if c['reform'] and (c['reform'] not in by_reform or c['timestamp'] > by_reform[c['reform']]['timestamp']):
            by_reform[c['reform']] = c
    states = [by_reform[r] for r in sorted(by_reform)]
    same_as_newest = {}
    for c in caps:
        c.update(segment_law(c['paras']))
    for c in caps:
        newest = by_reform[c['reform']]
        same_as_newest[c['timestamp']] = {k: unit_text(u) for k, u in c['units'].items()} == \
            {k: unit_text(u) for k, u in newest['units'].items()}

    # laws: the two expedition decrees (named on the copies' covers) and the reform decrees on the reform page
    decrees = []
    for day in sorted({c['law_day'] for c in states if c['law_day']}):
        src = next(c for c in states if c['law_day'] == day)
        title = next((p['t'] for p in src['paras'][:15] if re.match(r'(?i)^(SE EXPIDE|DECRETO POR)', p['t'])), None)
        ref = next((d for d in ref_decrees() if d['dof'] == day), None)
        decrees.append({'key': f'decreto-dof-{day}', 'dof': day, 'name': ref['name'] if ref else norm(title),
                        'url': ref['url'] if ref else capture_url(src), 'expedition': True})
    for d in ref_decrees():
        if not any(x['dof'] == d['dof'] for x in decrees):
            decrees.append({'key': f'decreto-dof-{d["dof"]}', 'dof': d['dof'], 'name': d['name'], 'url': d['url']})
    decrees.sort(key=lambda d: d['dof'])
    # reform-decree transitorios units, and every decree's in-force day from its own transitorios
    paras_of = {}
    for c in states:
        for b in c['blocks']:
            key = f'transitorios-{b["date"]}'
            c['units'][key] = {'label': f'Transitorios del decreto de reforma (DOF {dmy(b["date"])})', 'kind': 'transitional',
                               'lines': [p['t'] for p in b['paras']], 'notes': [x for p in b['paras'] for x in p['notes']],
                               'decree': f'decreto-dof-{b["date"]}'}
            paras_of[f'decreto-dof-{b["date"]}'] = b['paras']
        if c['law_day']:
            tr = c['units']['transitorios']
            paras_of[f'decreto-dof-{c["law_day"]}'] = [{'t': x} for x in tr['lines']]
    force = {}
    for d in decrees:
        force[d['key']] = parse.in_force(d['dof'], paras_of[d['key']]) if d['key'] in paras_of else \
            (parse.add_days(d['dof'], 3), 'Código Civil Federal art. 3 (tres días después de su publicación)')

    notes_from = [{k: set().union(*[note_dates(x) for x in u['notes']]) if u['notes'] else set()
                   for k, u in c['units'].items()} for c in states]
    first = states[0]
    versions = [{'from': force[f'decreto-dof-{first["law_day"]}'][0], 'source_url': capture_url(first),
                 'sha256': first['sha256'], 'units': {k: {'label': u['label'], 'kind': u['kind'], 'text': unit_text(u)}
                                                      for k, u in sorted(first['units'].items())},
                 'credits': {}, 'note': f'The law as published in the DOF on {dmy(first["law_day"])}, as the Cámara de '
                                        f'Diputados prints it (Internet Archive capture {first["timestamp"]}).'}]
    stats = {'credited_header': 0, 'credited_notes': 0, 'credited_self': 0, 'unexplained': 0}
    unexplained = []
    state = {k: unit_text(u) for k, u in first['units'].items()}
    for k in range(1, len(states)):
        a, b = states[k - 1], states[k]
        gap = [d for d in decrees if a['reform'] < d['dof'] <= b['reform']]
        changes, credits, days = {}, {}, set()
        for u in sorted(set(a['units']) | set(b['units'])):
            ta = unit_text(a['units'][u]) if u in a['units'] else None
            tb = unit_text(b['units'][u]) if u in b['units'] else None
            if ta == tb:
                continue
            cred = []
            selfd = b['units'].get(u, {}).get('decree') if tb is not None else None
            if b['law_day'] and b['law_day'] != a['law_day'] and any(d['dof'] == b['law_day'] for d in gap):
                cred = [d for d in gap if d['dof'] == b['law_day']]
                stats['credited_header'] += 1
            elif selfd and any(d['key'] == selfd for d in gap):
                cred = [d for d in gap if d['key'] == selfd]
                stats['credited_self'] += 1
            else:
                later = set().union(*[nf.get(u, set()) for nf in notes_from[k:]])
                hits = [d for d in gap if d['dof'] in later]
                if len({d['dof'] for d in hits}) == len(hits) and hits:
                    cred = hits
                    stats['credited_notes'] += 1
            if not cred:
                stats['unexplained'] += 1
                unexplained.append((b['reform'], u))
            changes[u] = None if tb is None else {'label': b['units'][u]['label'], 'kind': b['units'][u]['kind'], 'text': tb}
            if cred:
                credits[u] = sorted(d['key'] for d in cred)
            days.add(max(force[d['key']][0] for d in cred) if cred else b['reform'])
        if len(days) != 1:
            raise SystemExit(f'LFPDPPP gap to {b["reform"]}: changes on several days {sorted(days)}; split not written')
        day = days.pop()
        for u, x in changes.items():
            if x is None:
                state.pop(u, None)
            else:
                state[u] = x['text']
        versions.append({'from': day, 'source_url': capture_url(b), 'sha256': b['sha256'], 'changes': changes,
                         'credits': credits})
    final = {k: unit_text(u) for k, u in states[-1]['units'].items()}
    cov = [parse.coverage(c['path'], {k: {'lines': u['lines']} for k, u in c['units'].items()}) for c in states]
    report = {'copies': len(caps), 'states': [(c['timestamp'], c['reform'], c['law_day']) for c in states],
              'same_as_newest_copy_of_its_date': same_as_newest, 'versions': [v['from'] for v in versions],
              'stats': stats, 'unexplained': unexplained, 'force': force,
              'final_matches_newest_copy': final == state, 'coverage': [{k: v for k, v in x.items() if k != 'missing'}
                                                                       | {'missing': len(x['missing'])} for x in cov],
              'articles': [c['articles'] for c in states]}
    return {'states': states, 'decrees': decrees, 'force': force, 'versions': versions, 'report': report}


def corpus(res: dict) -> dict:
    rep, decrees, force = res['report'], res['decrees'], res['force']
    laws = {d['key']: {'label': f'Decreto (DOF {dmy(d["dof"])})', 'title': d['name'], 'kind': 'law', 'enacted': None,
                       'published': d['dof'], 'url': d['url'], 'temporary_until': None, 'restores': None, 'note': None}
            for d in decrees}
    first = res['states'][0]
    act = {'slug': 'lfpdppp', 'short': 'LFPDPPP',
           'title': 'Ley Federal de Protección de Datos Personales en Posesión de los Particulares',
           'url': LEYES + 'pdf/LFPDPPP.pdf', 'first_law': f'decreto-dof-{first["law_day"]}', 'earlier_laws': [],
           'versions': res['versions']}
    cov = rep['coverage']
    decisions = [
        'LFPDPPP: one act for two laws of the same name: the LFPDPPP of 2010 (DOF 05-07-2010, never amended; the four '
        'archived copies 2011-2019 all print it as "Nueva Ley DOF 05-07-2010") and the LFPDPPP of 2025 (DOF 20-03-2025), '
        'whose decree abrogated the 2010 law (transitorio Segundo, fracción I). The replacement is one version credited '
        'to the 2025 decree, because each copy\'s own cover names the law it prints; articles with the same number '
        'are compared across the two laws.',
        'LFPDPPP: the first version is the 2010 law as enacted (first_law), from the newest archived copy that prints '
        'it (' + first['timestamp'] + '); in-force days come from each decree\'s first transitorio: '
        + '; '.join(f'{k} {v[0]} ({v[1]})' for k, v in sorted(force.items())) + '.',
        'LFPDPPP: the reform of DOF 14-11-2025 (homologation with the Código Nacional de Procedimientos Civiles y '
        'Familiares) takes effect the next day by its transitorio Primero; its transitorio Segundo ties application to '
        'the declaratorias of that code, which is not modelled.',
        f'LFPDPPP: credits: {rep["stats"]}; unexplained: {rep["unexplained"]}.',
        f'LFPDPPP, verification: the last version equals the units of the newest copy (capture '
        f'{rep["states"][-1][0]}, last reform DOF {dmy(rep["states"][-1][1])}): {rep["final_matches_newest_copy"]}; '
        'read a second way (plain text, notes removed), each copy used contains every unit paragraph verbatim: '
        + ', '.join(f'{s[0]} {c["paragraphs"]} paragraphs, {c["missing"]} missing, {c["share"]:.2%} of body text'
                    for s, c in zip(rep['states'], cov)) + '.',
    ]
    same = rep['same_as_newest_copy_of_its_date']
    if not all(same.values()):
        decisions.append('LFPDPPP: copies whose units differ from the newest copy of the same date (not used): '
                         + ', '.join(t for t, ok in sorted(same.items()) if not ok) + '.')
    sources = [{'name': 'Cámara de Diputados, LeyesBiblio: Ley Federal de Protección de Datos Personales en Posesión de '
                        'los Particulares (texto vigente, consolidated PDFs), read through the Internet Archive',
                'url': LEYES + 'pdf/LFPDPPP.pdf', 'retrieved': '2026-10-29',
                'requests': parse.logged_requests(r'LeyesBiblio/(?:pdf/LFPDPPP|ref/lfpdppp)'),
                'licence': 'Public legal text (Ley Federal del Derecho de Autor art. 14 VIII); Cámara de Diputados del H. '
                           'Congreso de la Unión. Archived copies: Internet Archive.',
                'notes': f'{rep["copies"]} distinct archived copies 2011-2025; captures used: '
                         + ', '.join(s[0] for s in rep['states']) + '; reform list ref/lfpdppp.htm capture 20261015124207.'}]
    return {'sources': sources, 'laws': laws, 'acts': [act], 'applies': [], 'decisions': decisions, 'ai_use': []}


def main():
    res = build()
    parse.write_atomic(OUT, corpus(res))
    (HERE / '.tmp').mkdir(exist_ok=True)
    (HERE / '.tmp' / 'parse-lfpdppp-report.json').write_text(json.dumps(res['report'], ensure_ascii=False, indent=1),
                                                             encoding='utf-8')
    print(json.dumps(res['report'], ensure_ascii=False)[:3000])


if __name__ == '__main__':
    main()
