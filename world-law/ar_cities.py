"""Argentine cities (municipal tier) for git-for-law (gitlaw-scraper-dell, 2026-10-31, via global-law-main-composer):
one public repo per city, lexifina/argentina-<city>-city-law, built by scripts/gitlaw_common/build.py from corpus.d
parts. The engine is ar_provinces.py (fetching, cache, paragraphs, units, letters check, parts, verify, publish); this
file registers the cities, overrides the docs and the scaffold for the municipal tier and drives the parts.

    python -X utf8 scripts/world-law/ar_cities.py get <url> [<url> ...]            # one polite cached GET each
    python -X utf8 scripts/world-law/ar_cities.py scaffold <slug>                  # create the repo (after the gates)
    python -X utf8 scripts/world-law/ar_cities.py run <slug> [--max-parts=N] [--laws=N] [--no-publish]
    python -X utf8 scripts/world-law/ar_cities.py publish <slug> <part> <docs-date>
    python -X utf8 scripts/world-law/ar_cities.py letters <slug> <part>

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ar_provinces as E  # noqa: E402

# slug: English name, official name (the municipality), code, parent path, tz, province, adapter factory args
CITIES = {
    'la-plata-city': dict(en='La Plata', native='Municipalidad de La Plata', code='AR-B-LA-PLATA', parent='ar-b',
                          tz='America/Argentina/Buenos_Aires', province='Buenos Aires', sibom=(66, 'La Plata', 'La Plata'),
                          what='the city of La Plata, capital of the Province of Buenos Aires (Partido de La Plata)'),
    'mar-del-plata-city': dict(en='Mar del Plata', native='Municipalidad de General Pueyrredon', code='AR-B-MAR-DEL-PLATA',
                               parent='ar-b', tz='America/Argentina/Buenos_Aires', province='Buenos Aires',
                               sibom=(55, 'Mar del Plata', 'General Pueyrredon', True),
                               what='Mar del Plata (Partido de General Pueyrredon, Province of Buenos Aires)'),
    'bahia-blanca-city': dict(en='Bahía Blanca', native='Municipalidad de Bahía Blanca', code='AR-B-BAHIA-BLANCA',
                              parent='ar-b', tz='America/Argentina/Buenos_Aires', province='Buenos Aires',
                              sibom=(9, 'Bahía Blanca', 'Bahía Blanca'),
                              what='the city of Bahía Blanca (Partido de Bahía Blanca, Province of Buenos Aires)'),
    'rosario-city': dict(en='Rosario', native='Municipalidad de Rosario', code='AR-S-ROSARIO', parent='ar-s',
                         tz='America/Argentina/Cordoba', province='Santa Fe',
                         what='the city of Rosario (Province of Santa Fe)'),
}
CRAWL = {}

for _s, _c in CITIES.items():
    E.PROVINCES[_s] = (_c['en'], _c['native'], _c['code'], _c['tz'])
    if 'sibom' in _c:
        from ar_adapters import sibom as _sib
        E.ADAPTERS[_s] = _sib.make(*_c['sibom'])

DEFAULT_RULE = ('An ordinance takes effect on the day its own vigencia clause names; otherwise, as for any general norm, '
                'under Código Civil y Comercial de la Nación, art. 5 ("Las leyes rigen después del octavo día de su '
                'publicación oficial, o desde el día que ellas determinen"), counted under art. 6 (the day of '
                'publication excluded): the ninth day after its publication in the Boletín Oficial Municipal. The '
                'provincial Ley Orgánica de las Municipalidades (Decreto-Ley 6769/58, art. 108 inc. 2 and 18 as given '
                'by Ley 14.491) requires publication in the Boletín Oficial Municipal but sets no day of its own.')


def country_block(slug: str) -> dict:
    c = CITIES[slug]
    src = E.adapter_cls(slug).source
    return {
        'code': c['code'], 'name': c['en'], 'slug': f'argentina-{slug}', 'lang': 'es', 'tz': c['tz'],
        'future_branch': 'futuro',
        'publisher': {'name': src['publisher'], 'email': f'normas@{E.adapter_cls(slug).host}.invalid'},
        'default_in_force_rule': {'text': getattr(E.adapter_cls(slug), 'default_rule', DEFAULT_RULE),
                                  'source': getattr(E.adapter_cls(slug), 'default_rule_source',
                                                    'https://normas.gba.gob.ar/ar-b/ley/2013/14491/11345')},
        'licence_note': f'Fuente: {src["name"]}, {src["url"]}.',
    }


def source_block(slug: str, retrieved: str) -> dict:
    src = E.adapter_cls(slug).source
    return {'name': src['name'], 'url': src['url'], 'retrieved': retrieved,
            'licence': 'Official municipal ordinances, published in the Boletín Oficial Municipal. Argentina\'s copyright '
                       'law (Ley 11.723) has no express exclusion for them; ordinances are public acts of government, '
                       'binding on everyone once officially published. '
                       + (getattr(E.adapter_cls(slug), 'terms', '') or 'The source states no restriction on reuse.')
                       + ' Reproduced with attribution, following the official text.',
            'notes': src['notes']}


def decisions(slug: str) -> list[str]:
    src = E.adapter_cls(slug).source
    if hasattr(E.adapter_cls(slug), 'decisions'):
        return list(E.adapter_cls(slug).decisions)
    return [
        f'Source: the {src["gazette"]} on SIBOM ({src["url"]}). Each ordinance is its text as published in the '
        'bulletin, shown as enacted and dated the day it took effect. Later amendments by other ordinances are not '
        'applied to it; an amending ordinance appears as its own folder when it is included.',
        'In-force day: the ordinance\'s own vigencia clause when its last articles state one (from publication, the day '
        'after, or a named date); otherwise the ninth day after its publication in the Boletín Oficial Municipal '
        '(Código Civil y Comercial, arts. 5 and 6, applied to ordinances as general norms; the Ley Orgánica de las '
        'Municipalidades requires publication but sets no day). The bulletin\'s publication date is the one SIBOM '
        'prints ("Publicado el").',
        'The Province of Buenos Aires gives its municipalities no carta orgánica: their organic law is the provincial '
        'Ley Orgánica de las Municipalidades (Decreto-Ley 6769/58), which is provincial law and not included here. '
        'So this repository starts with ordinances.',
        ('Ordinances are taken from SIBOM\'s ordinance search for the partido, read from its last result page back '
         '(the search lists them only roughly in date order), in parts of about 50, each part in date order. An '
         'ordinance whose page carries only an extract, no article, or its text only as a PDF annex, is left out.'
         if getattr(E.adapter_cls(slug), 'search_mode', False) else
         'Ordinances are added newest bulletin first, in parts of about 50. An ordinance whose page carries only an '
         'extract, or no article, is left out.'),
        'Units: the heading (encabezado: number, place and date, the expediente line and anything before Artículo 1) and '
        'one file per article, holding the article and everything printed after it up to the next article '
        '(signatures, annexes). Nothing is dropped. One paragraph per line, spacing normalised.',
    ]


def _long(d: str) -> str:
    return E._long(d)


def write_docs(slug: str, docs_date: str, extra=(), out: Path | None = None):
    c = CITIES[slug]
    src = E.adapter_cls(slug).source
    parts = E._verified(slug, extra)
    rows, nacts, nvers = [], 0, 0
    first = last = None
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            first = min(first or vs[0]['from'], vs[0]['from'])
            last = max(last or vs[0]['from'], vs[0]['from'])
            t = a['title'].replace('|', '/')
            rows.append(f'| `{a["slug"]}/` | {t[:160]}{"…" if len(t) > 160 else ""} | in force {_long(vs[0]["from"])} |')
    repo = out or (E.folder(slug) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    span = f', in force from {_long(first)} to {_long(last)}' if first else ''
    ad = E.adapter_cls(slug)
    current = getattr(ad, 'current_texts', False)
    if current:
        rows = [r.replace('| in force ', '| current text only, as of ') for r in rows]
        holds = (f'{nacts} norm{"s" if nacts != 1 else ""} so far: {ad.holds}. {ad.level_note}')
        dates = (f'- Each commit is dated at **noon, {c["tz"]}**. {ad.dates_note}\n'
                 '- Versions that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.')
        limits = (f'This is not an official publication. The binding text is the one published in the {src["gazette"]}. '
                  'Only the norms listed above are included, each as its current consolidated text only.')
        terms = ad.terms
    else:
        holds = (f'{nacts} ordinance{"s" if nacts != 1 else ""} so far{span}, each as published in the {src["gazette"]}, '
                 + ('added in parts.' if getattr(ad, 'search_mode', False) else 'added newest first in parts.'))
        dates = (f'- Each commit is dated at **noon, {c["tz"]}, on the day the ordinance took effect**: the day its own '
                 f'vigencia clause names, or otherwise the ninth day after its publication in the {src["gazette"]} '
                 '(Código Civil y Comercial de la Nación, arts. 5 and 6).\n'
                 '- Each ordinance is its text as published. Later ordinances that amend it are separate folders; their '
                 'changes are not merged into the earlier text.\n'
                 '- Versions that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.')
        limits = (f'This is not an official publication. The binding text is the one published in the {src["gazette"]}. '
                  'Only the ordinances listed above are included, and amendments are not consolidated into the texts they '
                  'amend.')
        terms = 'The source states no restriction on reuse.'
    readme = f"""# {c['en']}: municipal law history in git

The municipal law of {c['what']}, Argentina, as a git history: one file per article, one commit per ordinance on the day it took effect. `git log` lists the changes; checking out a date gives the text the record holds for that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{c['code'].lower()}/`. The province's law is in [lexifina/argentina-{c['province'].lower().replace(' ', '-')}-law](https://github.com/lexifina/argentina-{c['province'].lower().replace(' ', '-')}-law) and Argentina's national law in [lexifina/argentina-law](https://github.com/lexifina/argentina-law).

The text is in Spanish, exactly as the source prints it.

## What this repository holds

{holds}

| Folder | {'Norm' if current else 'Ordinance'} | History |
| --- | --- | --- |
{chr(10).join(rows)}

## Source

{src['name']}, <{src['url']}>. {src['notes']}

## Dates

{dates}

## Files

`<ordinance>/art-005.md` is Artículo 5; `encabezado.md` holds the number, the place and date, the expediente line and anything printed before Artículo 1. Signatures and annexes stay in the file of the article they follow. One paragraph per line.

## How it is checked

- Every version of every ordinance is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the source page it was read from (read again with an independent HTML reader), so no word is lost or added.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## Limits

{limits}
"""
    lic = f"""The law texts in this repository are municipal ordinances of {c['what']}, Argentina, taken from
{src['name']}, {src['url']} (consulted {docs_date}).

They are legal norms: ordinances sanctioned by the Honorable Concejo Deliberante and published in the
{src['gazette']}. Ordinances are public acts of government that bind everyone once officially published.
Argentina's copyright law, Ley 11.723, contains no express exclusion for official texts, and none is claimed over them
here: they are reproduced as public acts of government. {terms} They are reproduced
here with this attribution, following the official text.

Changes made by Lexifina: each text was split into one Markdown file per article, one paragraph per line, with spacing
normalised; the wording was not changed. The municipality and the province do not endorse this repository. This
repository is not an official publication; the binding text is the one published in the {src['gazette']}.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': c['code'].lower(), 'code': c['code'], 'name': c['en'], 'level': 'municipality',
             'parent': c['parent'], 'repo': f'https://github.com/lexifina/{E.repo_name(slug)}',
             'build': f'built: municipal ordinances ({nacts} ordinances, {nvers} versions) from {src["url"]}',
             'language': 'es', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


_build_act = E.build_act


def build_act(slug, d, paras, src, used, docs_date):
    act, laws, rep = _build_act(slug, d, paras, src, used, docs_date)
    if d.get('as_of_note'):
        for v in act['versions']:
            v['note'] = d['as_of_note']
    return act, laws, rep


E.build_act = build_act
E.country_block = country_block
E.source_block = source_block
E.decisions = decisions
E.write_docs = write_docs


def scaffold(slug: str) -> str:
    """Create the public repo (one API call; run only after the gates pass) and push a scaffold main for autopush."""
    c = CITIES[slug]
    repo = E.repo_name(slug)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = E.run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    E.run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
          '-f', f'description={c["en"]} (Argentina) municipal law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    E.run('git', 'init', '-q', '-b', 'main', cwd=d)
    E.run('git', 'config', 'core.autocrlf', 'false', cwd=d)
    src = E.adapter_cls(slug).source
    (d / 'README.md').write_text(f"""# {c['en']}: municipal law as git history

Work in progress. This repository will hold the municipal law of {c['what']}, Argentina, as a git history: one file
per article, one commit per ordinance on the day it took effect.

Source: <{src['url']}>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text(f"""# Sources

- {src['name']}: <{src['url']}>

The terms and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    E.run('git', 'add', '-A', cwd=d)
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-10-31T12:00:00-0300', GIT_COMMITTER_DATE='2026-10-31T12:00:00-0300')
    subprocess.run(['git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
                    f'Argentina ({c["en"]}): sources, before any law'], cwd=d, env=env, check=True)
    E.run('git', 'remote', 'add', 'origin', remote, cwd=d)
    for attempt in range(4):
        p = E.run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
        if p.returncode == 0:
            break
        time.sleep(10 * (attempt + 1))
    E._rm(d)
    return 'CREATED ' + E.run('git', 'ls-remote', remote, check=False).stdout.strip()[:60]


def plan(cat: dict) -> list[tuple[str, list[dict]]]:
    out = [('10-carta-organica', cat['constitucion'][:1])] if cat.get('constitucion') else []
    codes = cat.get('codigo', [])
    for i in range(0, len(codes), E.PART_SIZE):
        out.append((f'{20 + i // E.PART_SIZE}-codigos-{i // E.PART_SIZE + 1}', codes[i:i + E.PART_SIZE]))
    leyes = cat.get('ley', [])
    for i in range(0, len(leyes), E.PART_SIZE):
        out.append((f'{30 + i // E.PART_SIZE}-ordenanzas-{i // E.PART_SIZE + 1:02d}', leyes[i:i + E.PART_SIZE]))
    return out


def drive(slug: str, docs_date: str, n_laws: int, max_parts: int | None, do_publish: bool):
    claim = E.CLAIMS / f'{E.repo_name(slug)}.txt'
    if not claim.exists() or not claim.read_text(encoding='utf-8').startswith(E.SESSION):
        E.say(f'{slug}: not claimed by this session, skipped')
        return
    E.folder(slug).mkdir(exist_ok=True)
    gi = E.folder(slug) / '.gitignore'
    if not gi.exists():
        gi.write_text('.tmp/\n', encoding='utf-8', newline='\n')
    for h, dly in CRAWL.items():
        E.net().pause[h] = dly
    ad = E.adapter_cls(slug)()
    cat = ad.catalogue(n_laws)
    parts = plan(cat)
    E.progress(slug, f'catalogue: {len(cat.get("constitucion", []))} carta orgánica, {len(cat.get("ley", []))} '
                     f'ordinances; {len(parts)} parts')
    for i, (name, members) in enumerate(parts):
        if max_parts is not None and i >= max_parts:
            break
        if (E.folder(slug) / 'corpus.d' / f'{name}.PUBLISH').exists():
            continue
        dets = E.fetch_part(slug, members)
        E.say(f'{slug} {name}: fetched {len(dets)}/{len(members)} ({sum(E.net().count.values())} requests)')
        if not dets:
            E.progress(slug, f'{name}: no text in any member')
            continue
        while not E.cpu_ok():
            time.sleep(60)
        rep = E.parse_part(slug, name, dets, docs_date)
        (E.folder(slug) / '.tmp').mkdir(exist_ok=True)
        (E.folder(slug) / '.tmp' / f'parse-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                                   encoding='utf-8')
        if not do_publish:
            E.say(f'{slug} {name}: parsed, not published (--no-publish)')
            continue
        r = E._low([sys.executable, '-X', 'utf8', str(Path(__file__)), 'publish', slug, name, docs_date])
        out = (r.stdout.strip().splitlines() or [''])[-1] + (r.stderr.strip()[-300:] if r.returncode else '')
        E.say(f'{slug} {name}: {out[:300]}')
        E.progress(slug, f'{name}: {out[:600]}')


def city_get(url: str, refresh: bool = False):
    n = E.net()
    for h, d in CRAWL.items():
        n.pause[h] = d
    return E.get(url, refresh=refresh)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    cmd = sys.argv[1]
    if cmd == 'get':
        for u in sys.argv[2:]:
            try:
                b = city_get(u)
                print(u, len(b or b''), E.cpath(u), flush=True)
            except E.Stop as e:
                print(u, 'STOP', e, flush=True)
                break
    elif cmd == 'scaffold':
        print(sys.argv[2], scaffold(sys.argv[2]))
    elif cmd == 'run':
        args = sys.argv[2:]
        mp, nl, pub = None, 200, True
        for a in list(args):
            if a.startswith('--max-parts='):
                mp = int(a.split('=')[1]); args.remove(a)
            elif a.startswith('--laws='):
                nl = int(a.split('=')[1]); args.remove(a)
            elif a == '--no-publish':
                pub = False; args.remove(a)
        dd = dt.date.today().isoformat()
        for s_ in args:
            try:
                drive(s_, dd, nl, mp, pub)
            except E.Stop as e:
                E.say(f'{s_}: STOPPED {e}')
                E.progress(s_, f'STOPPED: {e}')
    elif cmd == 'publish':
        print(E.publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'letters':
        pr = E.letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
