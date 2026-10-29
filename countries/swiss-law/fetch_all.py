"""Fetches everything the Swiss record needs for every act in the Classified Compilation, into the build's cache, so
build.py can then run without the network. Resumable: every request is cached, so a rerun continues where it stopped.

    python -X utf8 scripts/swiss-law/fetch_all.py [--workers 4]

Writes scripts/swiss-law/.cache/catalogue.json (every act with a German XML version: SR number, ELI, titles, in-force
status, versions) and scripts/swiss-law/.cache/PROGRESS.md as it goes.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

OUT = build.CACHE / 'catalogue.json'
PROGRESS = build.CACHE / 'PROGRESS.md'


def paged(query: str, page: int = 4000) -> list[dict]:
    """A SPARQL query read in pages (the endpoint caps a result); the query must have a stable ORDER BY."""
    rows: list[dict] = []
    offset = 0
    while True:
        chunk = build.sparql(f'{query}\nLIMIT {page} OFFSET {offset}')
        rows += chunk
        if len(chunk) < page:
            return rows
        offset += page


def progress(lines: list[str]):
    build.CACHE.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text('# Swiss law fetch\n\n' + '\n'.join(f'- {l}' for l in lines) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args()
    log = [f'started {time.strftime("%Y-%m-%d %H:%M")}']
    progress(log)

    # One query for every version is too heavy for the endpoint (HTTP 500), so the versions are read a year at a time
    # (a decade at a time before 2000, where there are few).
    spans = [(f'{y}-01-01', f'{y + 10}-01-01') for y in range(1840, 2000, 10)] + [(f'{y}-01-01', f'{y + 1}-01-01') for y in range(2000, 2041)]
    versions: list[dict] = []
    for a, b in spans:
        versions += build.sparql(f'''SELECT ?cc ?c ?from ?to ?url WHERE {{
          ?c a jolux:Consolidation ; jolux:dateApplicability ?from .
          FILTER(?from >= "{a}"^^<http://www.w3.org/2001/XMLSchema#date> && ?from < "{b}"^^<http://www.w3.org/2001/XMLSchema#date>)
          ?c jolux:isMemberOf ?cc ; jolux:isRealizedBy ?e .
          OPTIONAL {{ ?c jolux:dateEndApplicability ?to }}
          ?e jolux:language <{build.DEU}> ; jolux:isEmbodiedBy ?m .
          ?m jolux:userFormat <https://fedlex.data.admin.ch/vocabulary/user-format/xml> ; jolux:isExemplifiedBy ?url . }}''')
    log.append(f'{len(versions)} German XML versions listed')
    progress(log)

    # The acts' SR numbers, status, dates and titles, 150 acts per query.
    ccs = sorted({v['cc'] for v in versions})
    meta: list[dict] = []
    titles: dict[str, dict] = {}

    def batch(i: int):
        values = ' '.join(f'<{c}>' for c in ccs[i:i + 75])
        m = build.sparql(f'''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?cc ?sr ?status ?inforce ?adopted ?basic WHERE {{ VALUES ?cc {{ {values} }}
          OPTIONAL {{ ?cc jolux:classifiedByTaxonomyEntry ?e . ?e skos:notation ?sr }}
          OPTIONAL {{ ?cc jolux:inForceStatus ?status }}
          OPTIONAL {{ ?cc jolux:dateEntryInForce ?inforce }}
          OPTIONAL {{ ?cc jolux:dateDocument ?adopted }}
          OPTIONAL {{ ?cc jolux:basicAct ?basic }} }}''')
        t = {code: build.sparql(f'''SELECT ?cc ?t ?s WHERE {{ VALUES ?cc {{ {values} }} ?cc jolux:isRealizedBy ?e .
              ?e jolux:language <{lang}> ; jolux:title ?t . OPTIONAL {{ ?e jolux:titleShort ?s }} }}''')
             for lang, code in ((build.DEU, 'de'), (build.ENG, 'en'))}
        return m, t
    # Each query takes the endpoint half a minute, so a few run at once; results are merged in batch order.
    with cf.ThreadPoolExecutor(3) as pool:
        for m, t in pool.map(batch, range(0, len(ccs), 75)):
            meta += m
            for code, rows in t.items():
                for r in rows:
                    titles.setdefault(r['cc'], {})[code] = (r['t'], r.get('s'))
    log.append(f'{len(meta)} catalogue rows, {len(titles)} acts with titles')
    progress(log)

    acts: dict[str, dict] = {}
    for v in versions:
        eli = v['cc'][len(build.ELI):]
        a = acts.setdefault(eli, {'eli': eli, 'versions': {}})
        a['versions'][v['from']] = {'from': v['from'], 'to': v.get('to'), 'eli': v['c'], 'url': v['url']}
    for r in meta:
        eli = r['cc'][len(build.ELI):]
        if eli in acts:
            a = acts[eli]
            if r.get('sr') and (not a.get('sr') or len(r['sr']) < len(a['sr'])):
                a['sr'] = r['sr']
            a['status'] = (r.get('status') or '').rsplit('/', 1)[-1] or a.get('status')
            a['inForce'] = r.get('inforce') or a.get('inForce')
            a['adopted'] = r.get('adopted') or a.get('adopted')
            a['basicAct'] = r.get('basic') or a.get('basicAct')
    for eli, a in acts.items():
        t = titles.get(build.ELI + eli, {})
        a['title'], a['short'] = t.get('de', (None, None))
        a['titleEn'], a['shortEn'] = t.get('en', (None, None))
        a['versions'] = [a['versions'][k] for k in sorted(a['versions'])]
    cat = sorted(acts.values(), key=lambda a: (a.get('sr') or 'zzz', a['eli']))
    OUT.write_text(json.dumps(cat, ensure_ascii=False, indent=0), encoding='utf-8')
    log.append(f'{len(cat)} acts in the catalogue -> {OUT.name}')
    progress(log)

    # The text: every XML file, a few at a time.
    urls = [v['url'] for a in cat for v in a['versions']]
    done = failed = 0
    started = time.time()

    def get(u: str):
        build.fetch(u)
        return u
    with cf.ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(get, u) for u in urls]
        for f in cf.as_completed(futures):
            try:
                f.result()
                done += 1
            except Exception as e:  # noqa: BLE001 - recorded and retried on the next run
                failed += 1
                log.append(f'failed: {e}'[:200])
            if (done + failed) % 250 == 0:
                rate = (done + failed) / max(time.time() - started, 1)
                progress(log + [f'XML {done + failed}/{len(urls)} ({failed} failed), {rate:.1f}/s'])
    log.append(f'XML files: {done} cached, {failed} failed of {len(urls)}')
    progress(log)

    # Fedlex's impact records for every act, through each act's subdivisions, 60 acts per query.
    impacts: list[dict] = []

    def imp(i: int):
        values = ' '.join(f'<{c}>' for c in ccs[i:i + 60])
        return build.sparql(f'''SELECT ?cc ?to ?src ?d ?t WHERE {{ VALUES ?cc {{ {values} }} ?to jolux:legalResourceSubdivisionIsPartOf ?cc .
          ?i jolux:impactToLegalResource ?to ; jolux:impactFromLegalResource ?src ; jolux:legalResourceImpactHasType ?t .
          OPTIONAL {{ ?i jolux:legalResourceImpactHasDateEntryInForce ?d }} }}''')
    with cf.ThreadPoolExecutor(3) as pool:
        for n, rows in enumerate(pool.map(imp, range(0, len(ccs), 60))):
            impacts += rows
            if n % 20 == 0:
                progress(log + [f'impacts: {n * 60}/{len(ccs)} acts, {len(impacts)} rows'])
    (build.CACHE / 'impacts.json').write_text(json.dumps(impacts, ensure_ascii=False), encoding='utf-8')
    log.append(f'{len(impacts)} impact rows -> impacts.json')
    log.append(f'finished {time.strftime("%Y-%m-%d %H:%M")}')
    progress(log)


if __name__ == '__main__':
    main()
