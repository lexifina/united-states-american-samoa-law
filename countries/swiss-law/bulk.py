"""Builds the whole Classified Compilation: every act with a German XML version on Fedlex, read from the cache that
fetch_all.py fills. Writes the reader's data (one gzipped bundle per act) and the git repository (with git fast-import,
which writes tens of thousands of commits in minutes where one `git commit` per change would take hours).

    python -X utf8 scripts/swiss-law/bulk.py --today 2026-10-28 [--site saas-webpage] [--repo ../swiss-law] [--only 101,235.1]

The same --today and the same cache give the same commits with the same hashes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as B  # noqa: E402
from reproduce import write_manifest_rows, write_reproduce  # noqa: E402

COMMITTER = ('Lexifina', 'swiss-law@lexifina.com')


# ---------------------------------------------------------------- the catalogue

def slug_of(sr: str | None, eli: str) -> str:
    """The act's folder and URL name: its SR number ("101", "0.101", "235.1"), or its ELI where it has none."""
    return sr if sr and re.fullmatch(r'[0-9.]+[a-z]?', sr) else 'eli-' + eli.replace('cc/', '').replace('/', '-')


def load_catalogue(only: set[str] | None) -> list[dict]:
    cat = json.loads((B.CACHE / 'catalogue.json').read_text(encoding='utf-8'))
    raw = json.loads((B.CACHE / 'impacts.json').read_text(encoding='utf-8'))
    impacts: dict[str, list[dict]] = {}
    for r in raw:
        cc = r['cc'][len(B.ELI):]
        m = re.match(re.escape(B.ELI) + r'(oc/\d{4}/[^/]+)', r['src'])
        if not m:
            continue
        impacts.setdefault(cc, []).append({'target': r['to'][len(B.ELI + cc) + 1:], 'as': m.group(1), 'date': r.get('d'), 'type': r['t'].rsplit('/', 1)[-1]})
    acts, seen = [], set()
    for a in cat:
        slug = slug_of(a.get('sr'), a['eli'])
        if slug in seen:   # two acts under one SR number (an act and its predecessor): the second takes its ELI
            slug = slug_of(None, a['eli'])
        seen.add(slug)
        if only and slug not in only:
            continue
        dedup = {}
        for im in impacts.get(a['eli'], []):
            dedup[(im['target'], im['as'], im['date'])] = im
        acts.append({
            'sr': a.get('sr') or '', 'eli': a['eli'], 'slug': slug, 'status': a.get('status'),
            'versions': a['versions'],
            'meta': {'title': a.get('title'), 'short': a.get('short'), 'titleEn': a.get('titleEn'), 'shortEn': a.get('shortEn'),
                     'adopted': a.get('adopted'), 'inForce': a.get('inForce'), 'basicAct': a.get('basicAct')},
            'impacts': list(dedup.values()),
        })
    return acts


# ---------------------------------------------------------------- the reader's data

def compact_versions(u: dict, today: str) -> list[dict]:
    """Versions for the reader without what it can derive: the text is the runs joined, the redline is worked out on
    the server, and footnotes are kept for the version in force today only."""
    current = next((v for v in reversed(u['versions']) if v['from'] <= today), u['versions'][0])
    out = []
    for v in u['versions']:
        out.append({k: v[k] for k in ('from', 'seen', 'kind', 'repealed', 'heading', 'lines', 'runs', 'causes')} | {'notes': v['notes'] if v is current else []})
    return out


def site_bundle(b: dict, today: str) -> tuple[dict, dict]:
    """One act for the reader, and its row in the index."""
    act = b['act']
    in_force_now = {}
    for k, u in b['units'].items():
        v = next((v for v in reversed(u['versions']) if v['from'] <= today), None)
        if v and not v['repealed']:
            in_force_now[k] = v['text']
    cites = B.citations(b['units'], in_force_now, act['slug'])
    terms = B.term_uses(B.defined_terms(b['units']), in_force_now)
    sections: list[dict] = []
    arts, changes = [], []
    for k in sorted(b['units'], key=B.unit_order):
        u = b['units'][k]
        vs = u['versions']
        sec = ' › '.join(u['section']) if u['section'] else ''
        if not sections or sections[-1]['title'] != sec:
            sections.append({'title': sec, 'keys': []})
        sections[-1]['keys'].append(k)
        ch = [v for v in vs if v['kind'] != 'start']
        heading = next((v['heading'] for v in reversed(vs) if v['heading']), '')
        arts.append({'key': k, 'label': u['label'], 'heading': heading, 'changes': len(ch), 'lastChange': ch[-1]['from'] if ch else None,
                     'repealed': vs[-1]['repealed'], 'upcoming': any(v['from'] > today for v in ch)})
        for v in ch:
            changes.append({'key': k, 'label': u['label'], 'heading': v['heading'] or heading, 'from': v['from'], 'kind': v['kind'], 'causes': v['causes']})
    changes.sort(key=lambda c: (c['from'], B.unit_order(c['key'])))
    meta = b['meta']
    info = {
        'slug': act['slug'], 'sr': act['sr'], 'eli': B.ELI + act['eli'], 'status': act.get('status'),
        'title': meta.get('title'), 'short': meta.get('short'), 'titleEn': meta.get('titleEn'), 'shortEn': meta.get('shortEn'),
        'adopted': meta.get('adopted'), 'inForce': meta.get('inForce'), 'base': b['base'],
        'versions': [{'from': v['from'], 'to': v['to'], 'eli': v['eli'], 'url': v['url'], 'sha256': v['sha256']} for v in b['versions']],
        'sections': sections, 'articles': arts, 'changes': changes,
        'terms': [{'term': t['term'], 'article': t['article'], 'uses': len(t['rows'])} for t in terms],
        'problems': b['problems'],
        'units': {k: {'key': k, 'label': u['label'], 'eid': u['eid'], 'section': u['section'], 'versions': compact_versions(u, today),
                      'relies': {'cited': cites.get(k, []), 'terms': [t for t in terms if t['article'] == k]}}
                  for k, u in b['units'].items()},
    }
    row = {'slug': act['slug'], 'sr': act['sr'], 'title': meta.get('title'), 'short': meta.get('short'), 'titleEn': meta.get('titleEn'),
           'shortEn': meta.get('shortEn'), 'status': act.get('status'), 'first': b['versions'][0]['from'], 'last': b['versions'][-1]['from'],
           'versions': len(b['versions']), 'articles': len(arts), 'changes': len(changes),
           'corrected': sum(1 for c in changes if c['kind'] == 'corrected')}
    return info, row


# ---------------------------------------------------------------- the repository, by git fast-import

class Stream:
    """A git fast-import stream written to a file: blobs as the acts are built, then the commits in date order."""

    def __init__(self, path: Path):
        self.f = open(path, 'wb')
        self.mark = 0

    def data(self, b: bytes):
        self.f.write(b'data %d\n' % len(b) + b + b'\n')

    def blob(self, content: str) -> int:
        self.mark += 1
        self.f.write(b'blob\nmark :%d\n' % self.mark)
        self.data(content.encode('utf-8'))
        return self.mark

    def commit(self, ref: str, author: tuple[str, str], when: str, msg: str, parent: int | None, merge: int | None, ops: list[tuple]) -> int:
        self.mark += 1
        stamp = when.lstrip('@')
        out = [f'commit {ref}', f'mark :{self.mark}', f'author {author[0]} <{author[1]}> {stamp}', f'committer {COMMITTER[0]} <{COMMITTER[1]}> {stamp}']
        self.f.write(('\n'.join(out) + '\n').encode('utf-8'))
        self.data(msg.encode('utf-8'))
        if parent:
            self.f.write(b'from :%d\n' % parent)
        if merge:
            self.f.write(b'merge :%d\n' % merge)
        for op in ops:
            if op[0] == 'M':
                self.f.write(f'M 100644 :{op[2]} {op[1]}\n'.encode('utf-8'))
            else:
                self.f.write(f'D {op[1]}\n'.encode('utf-8'))
        self.f.write(b'\n')
        return self.mark

    def tag(self, name: str, mark: int):
        self.f.write(f'reset refs/tags/{name}\nfrom :{mark}\n\n'.encode('utf-8'))

    def close(self):
        self.f.close()


def message(b_meta: dict, slug: str, sr: str, eli: str, day: str, cause: str, items: list[tuple], rec: dict | None) -> tuple[tuple[str, str], str]:
    short = b_meta.get('short') or (f'SR {sr}' if sr else slug)
    labels = [lab for _, lab, _ in items]
    affecting = ', '.join(f'SR {sr} {lab}' for lab in labels)
    source = f'{B.ELI}{eli}/{day.replace("-", "")}'
    if cause == 'start':
        msg = [f'{short}: Stand am {day}', '',
               f'{b_meta.get("title")} (SR {sr}), wie in der Systematischen Rechtssammlung am {day} anwendbar:',
               'der erste Stand, den Fedlex als strukturierten Text (Akoma Ntoso) veröffentlicht. Wer den älteren Text',
               'geschrieben hat, sagen die Fussnoten.', '',
               'The first version Fedlex publishes as structured text. The footnotes credit the older text.', '',
               f'Consolidated: {day}', f'Source: {source}']
        return ('Bundeskanzlei (Fedlex)', 'bk@fedlex.invalid'), '\n'.join(msg) + '\n'
    if cause == 'publisher':
        subject = f'{short}: {", ".join(labels)} berichtigt'
        if len(subject) > 72:
            subject = f'{short}: {len(labels)} Artikel berichtigt'
        msg = [subject, '', 'Die Bundeskanzlei hat den konsolidierten Text berichtigt (Schreibweise, Zeilenumbruch).',
               'Kein Erlass hat den Artikel an diesem Tag geändert.', '',
               'The Federal Chancellery corrected the consolidated text. No act changed the article on this day.', '',
               f'Corrected: {day}', f'Affecting: {affecting}', f'Source: {source}']
        return ('Bundeskanzlei (Fedlex)', 'bk@fedlex.invalid'), '\n'.join(msg) + '\n'
    rec = rec or {'id': cause}
    label = B.as_label(rec)
    author = (label + (f' ({rec["titleShort"]})' if rec.get('titleShort') else ''), label.lower().replace(' ', '-') + '@fedlex.invalid')
    subject = f'{short}: {", ".join(labels)} ({label})'
    if len(subject) > 72:   # git tools cut subjects at 72 characters; the articles are listed in the body
        subject = f'{short}: {len(labels)} Artikel ({label})'
    msg = [subject, '']
    if rec.get('title'):
        msg += [rec['title'], '']
    for kind, name in (('created', 'Eingefügt'), ('updated', 'Geändert'), ('repealed', 'Aufgehoben')):
        ls = [lab for _, lab, k in items if k == kind]
        if ls:
            msg.append(f'{name}: {", ".join(ls)}')
    msg.append('')
    if rec.get('type'):
        msg.append(f'Type: {rec["type"]}')
    if rec.get('dateDocument'):
        msg.append(f'Adopted: {rec["dateDocument"]}')
    if rec.get('vote'):
        msg.append(f'Vote: {rec["vote"]}')
    if rec.get('published'):
        msg.append(f'Published: {rec["published"]} ({label})')
    msg += [f'In-force: {day}', f'Affecting: {affecting}', f'Source: {B.ELI}{cause}']
    return author, '\n'.join(msg) + '\n'


def act_readme(info: dict, today: str) -> str:
    out = [f'# {info["title"]}', '', f'SR {info["sr"]} · {info["short"] or ""} · <{info["eli"]}>', '',
           '| Artikel | Sachüberschrift | Änderungen seit dem ersten Stand | Zuletzt geändert |', '| --- | --- | --- | --- |']
    for a in info['articles']:
        u = info['units'][a['key']]
        v = next((v for v in reversed(u['versions']) if v['from'] <= today), u['versions'][-1])
        n = sum(1 for x in u['versions'] if x['kind'] != 'start' and x['from'] <= today)
        last = next((x['from'] for x in reversed(u['versions']) if x['kind'] != 'start' and x['from'] <= today), '')
        name = a['label'] + (' (aufgehoben)' if v['repealed'] else '')
        out.append(f'| {name if v["repealed"] else f"[{name}]({B.file_name(a["key"])})"} | {a["heading"]} | {n} | {last} |')
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default=str(B.ROOT / 'saas-webpage'))
    ap.add_argument('--repo', default=str(B.ROOT.parent / 'swiss-law'))
    ap.add_argument('--today', required=True)
    ap.add_argument('--only', help='comma-separated SR numbers, for a test build')
    ap.add_argument('--no-repo', action='store_true')
    args = ap.parse_args()
    today = args.today
    only = set(args.only.split(',')) if args.only else None
    t0 = time.time()
    acts = load_catalogue(only)
    print(f'{len(acts)} acts in the catalogue', flush=True)

    data = Path(args.site) / 'app' / 'watch' / 'swiss-law' / '_data'
    data.mkdir(parents=True, exist_ok=True)
    for p in data.iterdir():
        if p.name != 'load.ts':
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    (data / 'acts').mkdir()

    tmp = Path(tempfile.mkdtemp(prefix='swiss-law-'))
    stream = Stream(tmp / 'stream')
    events: dict[tuple, list] = {}          # (day, slug, cause) -> [(path, mark or None, label, kind)]
    acts_info: dict[str, dict] = {}          # slug -> {sr, eli, meta}
    rows, named, readmes, manifest = [], set(), {}, []
    touched: dict[str, list] = {}            # amending act -> the articles it changed
    votes: dict[str, set] = {}
    stats = {'versions': 0, 'changes': 0, 'corrected': 0, 'failed': []}
    for n, act in enumerate(acts):
        try:
            b = B.build_act(act, True, today)
        except Exception as e:  # noqa: BLE001 - an act Fedlex serves badly is listed, not fatal
            stats['failed'].append(f'{act["slug"]}: {type(e).__name__}: {e}'[:200])
            continue
        if not b['units']:
            stats['failed'].append(f'{act["slug"]}: no articles in the XML')
            continue
        for x in b['skipped']:
            stats.setdefault('skipped', []).append(f'{act["slug"]} {x}')
        info, row = site_bundle(b, today)
        (data / 'acts' / f'{act["slug"]}.json.gz').write_bytes(gzip.compress(json.dumps(info, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 6, mtime=0))
        rows.append(row)
        manifest.append({'sr': act['sr'], 'slug': act['slug'], 'eli': B.ELI + act['eli'], 'versions': info['versions']})
        acts_info[act['slug']] = {'sr': act['sr'], 'eli': act['eli'], 'meta': b['meta']}
        named |= b['named']
        for key, u in b['units'].items():
            for v in u['versions']:
                stats['versions'] += 1
                cause = 'start' if v['kind'] == 'start' else (v['causes'][0] if v['causes'] else 'publisher')
                if v['kind'] != 'start':
                    stats['changes'] += 1
                    stats['corrected'] += v['kind'] == 'corrected'
                if cause not in ('start', 'publisher'):
                    touched.setdefault(cause, []).append({'act': act['slug'], 'key': key, 'label': u['label'], 'from': v['from'], 'kind': v['kind']})
                    votes.setdefault(cause, set()).update(ev['vote'] for ev in v['notes'] if ev.get('as') == cause and ev.get('vote'))
                path = f'{act["slug"]}/{B.file_name(key)}'
                mark = None if v['repealed'] else stream.blob(B.article_md('', u['label'], v['heading'], v['text'], v['lines']))
                events.setdefault((v['from'], act['slug'], cause), []).append((path, mark, u['label'], v['kind']))
        readmes[act['slug']] = act_readme(info, today)
        if n % 250 == 0:
            print(f'  {n}/{len(acts)} acts, {stats["versions"]} versions, {time.time() - t0:.0f}s', flush=True)

    # The amending acts, for the commits and the reader.
    acts_meta = B.amending_acts(sorted(x for x in named if x.startswith('oc/')), True)
    amend = []
    for k in sorted(set(acts_meta) | set(touched)):
        rec = acts_meta.get(k, {'id': k})
        rec['vote'] = min(votes[k]) if votes.get(k) else None
        acts_meta[k] = rec
        amend.append({**rec, 'label': B.as_label(rec), 'changes': sorted(touched.get(k, []), key=lambda c: (c['from'], c['act'], B.unit_order(c['key'])))})
    amend.sort(key=lambda a: (a.get('dateEntryInForce') or '', a['id']))
    (data / 'amendments.json').write_text(json.dumps(amend, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    rows.sort(key=lambda r: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', r['sr'] or r['slug'])])
    (data / 'index.json').write_text(json.dumps({'built': today, 'acts': rows, 'failed': stats['failed']}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'site: {len(rows)} acts, {stats["changes"]} changes, {len(stats["failed"])} acts failed, {time.time() - t0:.0f}s', flush=True)
    if args.no_repo:
        return

    # The commits, in the order the changes took effect: the first version of an act before its changes that day.
    order = sorted(events, key=lambda e: (e[0], e[1], e[2] != 'start', e[2]))
    head = future = None
    tags: dict[str, int] = {}
    for day, slug, cause in order:
        items = events[(day, slug, cause)]
        ops = [('D', p) if m is None else ('M', p, m) for p, m, _, _ in sorted(items)]
        ai = acts_info[slug]
        author, msg = message(ai['meta'], slug, ai['sr'], ai['eli'], day, cause, sorted(((p, lab, k) for p, _, lab, k in items), key=lambda x: B.unit_order(x[0].split('/')[-1].replace('art-', '').replace('.md', '').lstrip('0') or '0')), acts_meta.get(cause))
        if day <= today:
            head = stream.commit('refs/heads/main', author, B.commit_date(day), msg, head, None, ops)
            mark = head
        else:
            # Changes adopted but not yet in force: their own branch, so main is the law today.
            future = stream.commit('refs/heads/kuenftig', author, B.commit_date(day), msg, future or head, None, ops)
            mark = future
        if cause not in ('start', 'publisher'):
            tags[f'as/{B.as_label(acts_meta.get(cause, {"id": cause})).replace("AS ", "").replace(" ", "-")}'] = mark

    # Documentation, tables and tools, dated the build day, on main, then merged into kuenftig.
    docs = Path(__file__).resolve().parent / 'repo'
    files: dict[str, str] = {}
    for p in docs.rglob('*'):
        if p.is_file():
            files[p.relative_to(docs).as_posix()] = p.read_text(encoding='utf-8')
    here = Path(__file__).resolve().parent
    for name in ('build.py', 'bulk.py', 'fetch_all.py', 'reproduce.py', 'check_repo.py'):
        files[f'tools/{name}'] = (here / name).read_text(encoding='utf-8')
    for slug, text in readmes.items():
        files[f'{slug}/README.md'] = text
    files['erlasse.csv'] = erlasse_csv(acts_meta)
    files['data/versionen.json'] = write_manifest_rows(manifest, today)
    files['data/erlasse.json'] = json.dumps(rows, ensure_ascii=False, indent=0) + '\n'
    queries = len({r['file'] for r in B.REQUESTS if r['query']}) or len(list(B.CACHE.glob('*')))
    stats.update({'acts': len(rows), 'law_commits': sum(1 for e in order if e[2] not in ('start', 'publisher')),
                  'commits': len(order), 'tags': len(tags), 'retrieved': cache_days()})
    files['REPRODUCE.md'] = write_reproduce(stats, today)
    ops = [('M', path, stream.blob(text)) for path, text in sorted(files.items())]
    docs_commit = stream.commit('refs/heads/main', COMMITTER, B.commit_date(today), 'Dokumentation, Tabellen, Werkzeuge und REPRODUCE.md\n', head, None, ops)
    if future:
        stream.commit('refs/heads/kuenftig', COMMITTER, B.commit_date(today), "Merge branch 'main' into kuenftig\n", future, docs_commit, ops)
    for name, mark in sorted(tags.items()):
        stream.tag(name, mark)
    stream.close()

    repo = Path(args.repo)
    remote = None
    if repo.exists() and any(repo.iterdir()):
        readme = repo / 'README.md'
        if not (repo / '.git').exists() or not readme.exists() or not readme.read_text(encoding='utf-8').startswith('# Swiss federal law'):
            raise SystemExit(f'{repo} is not empty and is not an earlier build of this repository; give an empty or new folder.')
        out = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=repo, capture_output=True, text=True)
        remote = out.stdout.strip() or None

        def force(fn, path, _exc):
            os.chmod(path, 0o700)
            fn(path)
        for p in repo.iterdir():
            shutil.rmtree(p, onexc=force) if p.is_dir() else p.unlink()
    repo.mkdir(parents=True, exist_ok=True)
    B.git(repo, 'init', '-q', '-b', 'main')
    B.git(repo, 'config', 'core.autocrlf', 'false')
    if remote:
        B.git(repo, 'remote', 'add', 'origin', remote)
    with open(tmp / 'stream', 'rb') as f:
        r = subprocess.run(['git', 'fast-import', '--quiet'], cwd=repo, stdin=f, capture_output=True)
    if r.returncode:
        raise SystemExit(r.stderr.decode('utf-8', 'replace')[-2000:])
    B.git(repo, 'checkout', '-q', '-f', 'main')
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'repo: {len(order)} commits, {len(tags)} tags -> {repo}, {time.time() - t0:.0f}s')
    for f in stats['failed'][:20]:
        print('  failed:', f)


def erlasse_csv(acts_meta: dict) -> str:
    import csv
    import io
    rows = [{'as': B.as_label(rec), 'eli': B.ELI + k, 'titel': rec.get('title', ''), 'kurz': rec.get('titleShort', ''), 'art': rec.get('type', ''),
             'beschlossen': rec.get('dateDocument', ''), 'volksabstimmung': rec.get('vote') or '', 'veroeffentlicht': rec.get('published', ''),
             'in_kraft': rec.get('dateEntryInForce', '')} for k, rec in sorted(acts_meta.items(), key=lambda x: (x[1].get('dateEntryInForce') or '', x[0]))]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else ['as'], lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def cache_days() -> str:
    files = [p for p in B.CACHE.iterdir() if p.is_file() and len(p.name) == 32]
    if not files:
        return ''
    days = sorted({time.strftime('%Y-%m-%d', time.localtime(p.stat().st_mtime)) for p in files})
    return days[0] if len(days) == 1 else f'{days[0]} to {days[-1]}'


if __name__ == '__main__':
    main()
