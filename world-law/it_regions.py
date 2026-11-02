"""Italian regions and autonomous provinces for git-for-law (gitlaw-scraper-dell, coverage wave 2026-10-30): one public
repo per unit, lexifina/italy-<unit>-law, built by scripts/gitlaw_common/build.py from corpus.d parts.

Shared pieces only (claim, scaffold, docs, verify, PUBLISH); each region's own fetch and parse live in
scripts/world-law/it_<unit>.py, which write corpus.d parts through write_part() and verify them with publish().
The national lexifina/italy-law is another session's build and is never touched from here.

    python -X utf8 scripts/world-law/it_regions.py claim <slug>
    python -X utf8 scripts/world-law/it_regions.py scaffold <slug>
    python -X utf8 scripts/world-law/it_regions.py release <slug> <verdict line for REGION-TRIAGE.md>

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # scripts/
DOCS = ROOT.parent.parent                           # ~/Documents
HERE = Path(__file__).resolve().parent
SESSION = 'gitlaw-scraper-dell'
CLAIMS = HERE / 'claims'
TZ = 'Europe/Rome'

# slug: (English name, official Italian name, ISO 3166-2, kind)
# kind: 'ordinary' (statuto ordinario), 'special' (statuto speciale, a constitutional law), 'province' (autonomous
# province of Trentino-Alto Adige/Südtirol)
UNITS = {
    'lombardy': ('Lombardy', 'Regione Lombardia', 'IT-25', 'ordinary'),
    'lazio': ('Lazio', 'Regione Lazio', 'IT-62', 'ordinary'),
    'campania': ('Campania', 'Regione Campania', 'IT-72', 'ordinary'),
    'sicily': ('Sicily', 'Regione Siciliana', 'IT-82', 'special'),
    'veneto': ('Veneto', 'Regione del Veneto', 'IT-34', 'ordinary'),
    'emilia-romagna': ('Emilia-Romagna', 'Regione Emilia-Romagna', 'IT-45', 'ordinary'),
    'piedmont': ('Piedmont', 'Regione Piemonte', 'IT-21', 'ordinary'),
    'apulia': ('Apulia', 'Regione Puglia', 'IT-75', 'ordinary'),
    'tuscany': ('Tuscany', 'Regione Toscana', 'IT-52', 'ordinary'),
    'calabria': ('Calabria', 'Regione Calabria', 'IT-78', 'ordinary'),
    'sardinia': ('Sardinia', 'Regione Autonoma della Sardegna', 'IT-88', 'special'),
    'liguria': ('Liguria', 'Regione Liguria', 'IT-42', 'ordinary'),
    'marche': ('Marche', 'Regione Marche', 'IT-57', 'ordinary'),
    'abruzzo': ('Abruzzo', 'Regione Abruzzo', 'IT-65', 'ordinary'),
    'friuli-venezia-giulia': ('Friuli-Venezia Giulia', 'Regione Autonoma Friuli Venezia Giulia', 'IT-36', 'special'),
    'trentino-south-tyrol': ('Trentino-South Tyrol', 'Regione Autonoma Trentino-Alto Adige/Südtirol', 'IT-32',
                             'special'),
    'trento': ('Trento', 'Provincia autonoma di Trento', 'IT-TN', 'province'),
    'bolzano': ('Bolzano', 'Provincia autonoma di Bolzano - Alto Adige / Autonome Provinz Bozen - Südtirol', 'IT-BZ',
                'province'),
    'umbria': ('Umbria', 'Regione Umbria', 'IT-55', 'ordinary'),
    'basilicata': ('Basilicata', 'Regione Basilicata', 'IT-77', 'ordinary'),
    'molise': ('Molise', 'Regione Molise', 'IT-67', 'ordinary'),
    'aosta-valley': ("Aosta Valley", "Regione Autonoma Valle d'Aosta / Région autonome Vallée d'Aoste", 'IT-23',
                     'special'),
}

ART5 = ('Legge 22 aprile 1941, n. 633 (protezione del diritto d\'autore), art. 5: "Le disposizioni di questa legge non '
        'si applicano ai testi degli atti ufficiali dello Stato e delle amministrazioni pubbliche, sia italiane che '
        'straniere." (This law does not apply to the texts of the official acts of the State and of public '
        'administrations, Italian or foreign.)')


def repo_name(slug: str) -> str:
    return f'italy-{slug}-law'


def folder(slug: str) -> Path:
    return ROOT / repo_name(slug)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


def clean_line(s: str) -> str:
    """The shared typesetting normalisation: NBSP and other spaces to a space, runs collapsed, one form of quotes."""
    s = unicodedata.normalize('NFC', s)
    s = re.sub(r'[  -   　\t]', ' ', s).replace('​', '').replace('﻿', '')
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('«', '"').replace('»', '"')
    return re.sub(r' {2,}', ' ', s).strip()


# ---------------------------------------------------------------- claims, progress, load

def claim(slug: str, note: str) -> bool:
    p = CLAIMS / f'{repo_name(slug)}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'{SESSION} {now()} ({note})\n')
        return True
    except FileExistsError:
        return p.read_text(encoding='utf-8', errors='replace').startswith(SESSION)


def release(slug: str):
    p = CLAIMS / f'{repo_name(slug)}.txt'
    if p.exists() and p.read_text(encoding='utf-8', errors='replace').startswith(SESSION):
        p.unlink()


def triage(line: str):
    """Append one verdict to scripts/REGION-TRIAGE.md (append only)."""
    p = ROOT / 'REGION-TRIAGE.md'
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(line.rstrip() + '\n')


def scraping_log(lines: list[str]):
    with open(ROOT / 'SCRAPING-LOG.md', 'a', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines).rstrip() + '\n')


def progress(slug: str, line: str):
    p = folder(slug) / 'PROGRESS.md'
    p.parent.mkdir(exist_ok=True)
    if not p.exists():
        p.write_text(f'# {repo_name(slug)} (private progress, gitlaw-scraper-dell)\n\nShared code: '
                     f'scripts/world-law/it_regions.py; region builder: scripts/world-law/it_{slug.replace("-", "_")}.py\n\n',
                     encoding='utf-8', newline='\n')
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {now()} {line}\n')


def cpu_ok() -> bool:
    try:
        last = Path(os.environ['LOCALAPPDATA'], 'gitlaw-cpu.log').read_text(encoding='utf-8').strip().splitlines()[-1]
        c5 = int(re.search(r'cpu5=(\d+)', last).group(1))
        ram = int(re.search(r'ram=(\d+)', last).group(1))
        return c5 <= 92 and ram <= 85
    except Exception:
        return True


def below_normal():
    """Run this process at BelowNormal priority (Windows), as every build/parse job must."""
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == 'nt' else 10)
    except Exception:
        pass


def wait_cpu():
    while not cpu_ok():
        time.sleep(60)


# ---------------------------------------------------------------- corpus pieces

def country_block(slug: str, src: dict) -> dict:
    en, native, code, kind = UNITS[slug]
    return {
        'code': code, 'name': en, 'slug': f'italy-{slug}', 'lang': src.get('lang', 'it'), 'tz': TZ,
        'future_branch': 'futuro',
        'publisher': {'name': src['publisher'], 'email': f'raccolta@{src["host"]}.invalid'},
        'default_in_force_rule': {'text': src['in_force_rule'], 'source': src.get('in_force_source', src['url'])},
        'licence_note': src['licence_note'],
    }


def source_block(src: dict, retrieved: str) -> dict:
    return {'name': src['publisher'], 'url': src['url'], 'retrieved': retrieved, 'licence': src['licence'],
            'notes': src['source_notes']}


def write_part(slug: str, name: str, part: dict) -> Path:
    d = folder(slug) / 'corpus.d'
    d.mkdir(parents=True, exist_ok=True)
    p = d / f'{name}.json'
    if p.with_suffix('.PUBLISH').exists():
        return p
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)
    return p


def part_names(slug: str) -> list[str]:
    return [p.stem for p in sorted((folder(slug) / 'corpus.d').glob('*.json'))]


def is_first_part(slug: str, name: str) -> bool:
    return not any(n < name for n in part_names(slug) if n != name)


def used_slugs(slug: str, skip: str) -> tuple[set, dict]:
    used, laws = set(), {}
    for p in sorted((folder(slug) / 'corpus.d').glob('*.json')):
        if p.stem == skip:
            continue
        pj = json.loads(p.read_text(encoding='utf-8'))
        for a in pj.get('acts', []):
            used.add(a['slug'])
        for k, law in pj.get('laws', {}).items():
            laws.setdefault(k, law['label'])
    return used, laws


# ---------------------------------------------------------------- docs

def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
              'November', 'December']
    return f'{x.day} {months[x.month - 1]} {x.year}'


def _verified(slug: str, extra=()) -> list[dict]:
    out = []
    for p in sorted((folder(slug) / 'corpus.d').glob('*.json')):
        if p.with_suffix('.PUBLISH').exists() or p.stem in extra:
            out.append(json.loads(p.read_text(encoding='utf-8')))
    return out


def write_docs(slug: str, src: dict, docs_date: str, extra=(), out: Path | None = None):
    """README, LICENSE and jurisdiction.json for the verified parts (plus `extra`). `src` is the region's source
    description (see it_tuscany.SRC)."""
    en, native, code, kind = UNITS[slug]
    parts = _verified(slug, extra)
    rows, nacts, nvers = [], 0, 0
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = _long(vs[0]['from']) if len(vs) == 1 else f'{_long(vs[0]["from"])} to {_long(vs[-1]["from"])}'
            hist = ('as first published' if a.get('first_law') else 'oldest version available') + \
                (f', then each change: {span}' if len(vs) > 1 else f': {span}')
            if src.get('row_hist'):   # optional per-region wording (Tuscany refresh); absent elsewhere
                hist = src['row_hist'](a)
            rows.append(f'| `{a["slug"]}/` | {a["title"].replace("|", "/")[:160]} | {len(vs)} | {hist} |')
    unit = {'province': f'the Autonomous Province of {en}', 'special': f'the autonomous region of {en}'}.get(
        kind, f'the region of {en}')
    statute = ('Statute of Autonomy (a constitutional law of the Italian State)' if kind == 'special' else
               'Statute of Autonomy (the Statute of Trentino-Alto Adige/Südtirol and its implementing rules)'
               if kind == 'province' else 'Statute (Statuto regionale)')
    repo = out or (folder(slug) / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    current = src['history'] == 'current-only'
    dates = (f"""- Each act's text is the consolidated text in force on the retrieval day ({_long(docs_date)}), as {src['short']} publishes it. The source gives no dated past versions{src.get('history_note', '')}, so each act has one commit, its **oldest version available**, dated at **noon, Europe/Rome, on {_long(docs_date)}** and credited to {src['short']} as publisher, naming the act itself.
- This is not the date the text took effect: it is the day the text was read. Earlier wordings are not in this record.""" if current and not src.get('dates_md') else src['dates_md'])
    readme = f"""# {en}: law history in git

The law of {unit} ({native}, Italy) as a git history: one file per article, one commit per change, dated the day it took effect. `git blame` names the law behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day{' (here: the text in force when it was retrieved)' if current else ''}.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `{code.lower()}/`. Italy's national law is in [lexifina/italy-law](https://github.com/lexifina/italy-law).

The text is in {src.get('language_name', 'Italian')}, exactly as the source prints it.

## What this repository holds

{nacts} act{"s" if nacts != 1 else ""} with {nvers} version{"s" if nvers != 1 else ""} so far: {'the regional laws' if src.get('no_statute') else 'the ' + statute + ' first, then the regional laws'}{' in force' if src.get('in_force_only', True) else ''}, added in parts of about fifty. {src.get('scope_note', 'Regulations and repealed laws are not included yet.')}

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

{src['source_md']}

## Dates

{dates}
- Versions that take effect after the retrieval day are on the `futuro` branch, never merged into `main`.

## Files

{src['files_md']} One paragraph per line.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of {src['short']}'s own text of that version (read by a second, independent reader), and every unit's text appears in it in order.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

{src.get('author_md') or ('The author of a commit is the law that changed the text, with an e-mail address that cannot exist (`<key>@' + src['host'] + '.invalid`).' if not current else 'Every commit here is an "oldest version available" commit, authored by the publisher, ' + src['short'] + ', with an e-mail address that cannot exist.')} The committer is always Lexifina.

## Limits

This is not an official publication. {src['official_md']} {src.get('limits_md', 'Only the current text of each act is recorded, not its earlier wordings. ' if current else '')}Only the acts listed above are included.
"""
    lic = f"""The law texts in this repository are official texts of {unit} ({native}, Italy), taken from
{src['short']}, {src['url']}.

Italian copyright law does not protect them. {ART5}

{src['terms_md']}

The source is credited as it asks: {src['licence_note']} (consulted {docs_date}).

This repository is not an official publication. {src['official_md']}

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': code.lower(), 'code': code, 'name': en,
             'level': 'autonomous province' if kind == 'province' else 'region',
             'parent': 'it', 'repo': f'https://github.com/lexifina/{repo_name(slug)}',
             'build': f'built: statute and regional laws ({nacts} acts, {nvers} versions) from {src["short"]}'
                      + (' (current text only)' if current else ''),
             'language': src.get('lang', 'it'), 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


# ---------------------------------------------------------------- scaffold

def run(*a, cwd=None, check=True):
    p = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError(f'{a[:3]} failed: {p.stderr[:400]}')
    return p


def scaffold(slug: str, source_name: str, source_url: str) -> str:
    en, native, code, kind = UNITS[slug]
    repo = repo_name(slug)
    remote = f'https://github.com/lexifina/{repo}.git'
    ls = run('git', 'ls-remote', remote, check=False)
    if ls.returncode == 0 and ls.stdout.strip():
        return 'EXISTS ' + ls.stdout.splitlines()[0][:60]
    if run('gh', 'api', f'repos/lexifina/{repo}', check=False).returncode != 0:
        run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false',
            '-f', f'description={en} (Italy) law as git history')
    d = Path(tempfile.mkdtemp(prefix='scaffold-'))
    run('git', 'init', '-q', '-b', 'main', cwd=d)
    (d / 'README.md').write_text(f"""# {en}: law as git history

Work in progress. This repository will hold the law of {en} ({native}, Italy) as a git history: one file per
article, one commit per change, on the day it took effect, `git blame` and `git log` working line by line.

Planned first build: the {'Statute of Autonomy' if kind != 'ordinary' else 'Statute (Statuto)'}, then the regional laws in force.

Source: {source_name}, <{source_url}>.
""", encoding='utf-8', newline='\n')
    (d / 'SOURCES.md').write_text(f"""# Sources

- {source_name}: <{source_url}>

Official acts of public administrations are not protected by copyright in Italy (Legge 22 aprile 1941, n. 633,
art. 5). The terms and attribution will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
    run('git', 'add', '-A', cwd=d)
    run('git', '-c', 'user.name=Lexifina', '-c', 'user.email=world-law@lexifina.com', 'commit', '-q', '-m',
        f'Italy ({en}): sources, before any law', cwd=d)
    run('git', 'remote', 'add', 'origin', remote, cwd=d)
    for attempt in range(4):
        p = run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
        if p.returncode == 0:
            break
        time.sleep(10 * (attempt + 1))
    return 'CREATED ' + run('git', 'ls-remote', remote, check=False).stdout.strip()[:60]


# ---------------------------------------------------------------- verify and publish

def _low(cmd: list[str], env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                          creationflags=0x4000 if os.name == 'nt' else 0)


def _rm(d: Path):
    import stat

    def onerr(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if d.exists():
        shutil.rmtree(d, onexc=onerr)


def verify_part(slug: str, src: dict, part: str, docs_date: str, letters_check) -> tuple[bool, str]:
    """letters_check(slug, part) -> list of problems, from an independent reader of the cached source."""
    probs = letters_check(slug, part)
    if probs:
        return False, f'letters check: {len(probs)} problems: {probs[0]}'
    wait_cpu()
    sfolder = folder(slug)
    tmp = DOCS / f'{repo_name(slug)}-verify'
    build = DOCS / f'{repo_name(slug)}-verifybuild'
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((sfolder / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    names += [part] if part not in names else []
    for n in names:
        shutil.copy2(sfolder / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(slug, src, docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-600:]
    c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
              str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, 'check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force') or c.returncode:
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300] + \
            json.dumps(res.get('details', [])[:3], ensure_ascii=False)[:400]
    pj = json.loads((sfolder / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    acts = pj['acts']
    nv = sum(len(a['versions']) for a in acts)
    days = sorted(v['from'] for a in acts for v in a['versions'])
    line = (f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} from {src["short"]}: letters and digits of '
            f'every version equal the source text (independent reader) and every unit is found in order; scratch '
            f'build of verified parts + this part: check.py {res.get("versions")} versions, 0 mismatches, 0 trailer '
            f'errors, 0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return True, line


def publish(slug: str, src: dict, part: str, docs_date: str, letters_check) -> str:
    ok, line = verify_part(slug, src, part, docs_date, letters_check)
    if not ok:
        progress(slug, f'{part}: NOT VERIFIED {line[:500]}')
        return 'NOT VERIFIED ' + line
    pub = folder(slug) / 'corpus.d' / f'{part}.PUBLISH'
    tmp = pub.with_suffix('.ptmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    write_docs(slug, src, docs_date, extra=[part])
    os.replace(tmp, pub)
    top = folder(slug) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    progress(slug, f'{part}: PUBLISH {line}')
    return 'PUBLISH ' + line


def publish_batch(slug: str, src: dict, names: list[str], docs_date: str, letters_check, drop_bad: bool = True,
                  reader: str = 'independent reader') -> str:
    """Verify 5-10 parts at once (gitlaw-scraper-dell, 2026-10-30 evening): the independent letters check of each part
    (acts it disagrees with are left out and recorded when drop_bad), then ONE scratch build of every verified part
    plus all of these, checked by check.py; on success each part gets its own PUBLISH line. Same checks as publish()."""
    names = [n for n in names if not (folder(slug) / 'corpus.d' / f'{n}.PUBLISH').exists()]
    if not names:
        return 'nothing to publish'
    d = folder(slug) / 'corpus.d'
    for n in list(names):
        probs = letters_check(slug, n)
        if probs and drop_bad:
            bad = sorted({p_.split(' ')[0].rstrip(':') for p_ in probs})
            pj = json.loads((d / f'{n}.json').read_text(encoding='utf-8'))
            pj['acts'] = [a for a in pj['acts'] if a['slug'] not in bad]
            for b_ in bad:
                pj['laws'].pop(b_, None)
            progress(slug, f'{n}: left out (letters check disagrees): {", ".join(bad)}')
            if not pj['acts']:
                (d / f'{n}.json').unlink()
                (d / f'{n}.EMPTY').write_text('every act left out (letters check)\n', encoding='utf-8')
                names.remove(n)
                continue
            tmp = d / f'{n}.tmp'
            tmp.write_text(json.dumps(pj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
            os.replace(tmp, d / f'{n}.json')
            probs = letters_check(slug, n)
        if probs:
            progress(slug, f'{n}: NOT VERIFIED letters check: {len(probs)} problems: {probs[0]}'[:600])
            return f'NOT VERIFIED {n}: letters check {len(probs)} problems: {probs[0]}'
    if not names:
        return 'nothing left to publish'
    wait_cpu()
    tmp, build = DOCS / f'{repo_name(slug)}-verify', DOCS / f'{repo_name(slug)}-verifybuild'
    for x in (tmp, build):
        _rm(x)
    (tmp / 'corpus.d').mkdir(parents=True)
    have = [q.stem for q in sorted(d.glob('*.json')) if q.with_suffix('.PUBLISH').exists()]
    for n in have + [n for n in names if n not in have]:
        shutil.copy2(d / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(slug, src, docs_date, extra=names, out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    if b.returncode:
        msg = 'build failed: ' + (b.stderr or b.stdout)[-600:]
        progress(slug, f'{names[0]}..{names[-1]}: NOT VERIFIED {msg}'[:700])
        return 'NOT VERIFIED ' + msg
    c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
              str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return 'NOT VERIFIED check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]
    if c.returncode or any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated',
                                                'missing_in_force')):
        msg = 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:400]
        progress(slug, f'{names[0]}..{names[-1]}: NOT VERIFIED {msg}'[:700])
        return 'NOT VERIFIED ' + msg
    for n in names:
        acts = json.loads((d / f'{n}.json').read_text(encoding='utf-8'))['acts']
        nv = sum(len(a['versions']) for a in acts)
        days = sorted(v['from'] for a in acts for v in a['versions'])
        line = (f'{len(acts)} act(s), {nv} versions {days[0]}..{days[-1]} from {src["short"]}: letters and digits of '
                f'every version equal the source text ({reader}) and every unit is found in order; scratch build of '
                f'verified parts + parts {names[0]}..{names[-1]}: check.py {res.get("versions")} versions, 0 mismatches, '
                f'0 trailer errors, 0 merges ({docs_date}).')
        (d / f'{n}.PUBLISH').write_text(line + '\n', encoding='utf-8', newline='\n')
        progress(slug, f'{n}: PUBLISH {line}')
    top = folder(slug) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    write_docs(slug, src, docs_date)
    _rm(tmp)
    _rm(build)
    return f'PUBLISH {len(names)} parts ({names[0]}..{names[-1]}), check.py {res.get("versions")} versions clean'


def status(slug: str) -> str:
    p = folder(slug) / 'BUILD_STATUS.json'
    return p.read_text(encoding='utf-8')[:800] if p.exists() else 'no BUILD_STATUS.json yet'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd, slug = sys.argv[1], sys.argv[2]
    if cmd == 'claim':
        print(claim(slug, ' '.join(sys.argv[3:]) or 'Italian regions'))
    elif cmd == 'release':
        release(slug)
        if len(sys.argv) > 3:
            triage(' '.join(sys.argv[3:]))
        print('released')
    elif cmd == 'status':
        print(status(slug))
