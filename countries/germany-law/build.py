"""Builds lexifina/germany-law: German law as one git history.

    python -X utf8 scripts/germany-law/build.py --docpatch <c3e/grundgesetz-dev> --archive <QuantLaw_gesetze-im-internet.git>
                                                --repo <out> --docs-date YYYY-MM-DD

Two parts, interleaved by date into one history:

- bund/gg/      the Grundgesetz, every version since 1949, one file per article
                (built by grundgesetz.py: DocPatch reconciled with the official text, then the official text)
- bund/gesetze/ every other federal act on Gesetze im Internet, every change since 10 June 2019, one file per act
                (built by bundesrecht.py from QuantLaw's daily archive)

State law (laender/) is to follow. Each commit is one law taking effect, credited to that law; the documentation commit
comes last, dated --docs-date, so the same sources give the same commits.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMMITTER = 'Lexifina <germany-law@lexifina.com>'
GG_DIR = 'bund/gg'


def load(name: str, *candidates: Path):
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module, path
    raise SystemExit(f'cannot find {name}: {candidates}')


# In the repository the three scripts sit side by side in tools/; in Lexifina's own repository they are in
# scripts/grundgesetz/ and scripts/bundesrecht/.
gg, GG_FILE = load('grundgesetz', HERE / 'grundgesetz.py', HERE.parent / 'grundgesetz' / 'build.py')
br, BR_FILE = load('bundesrecht', HERE / 'bundesrecht.py', HERE.parent / 'bundesrecht' / 'build.py')


def noon(day: str, seq: int) -> str:
    """Noon in Berlin on the day. Git cannot store a time before 1970 (UTC): earlier days are 1 January 1970 UTC, a
    second apart in order, with the real date in the message and the tags."""
    d = dt.date.fromisoformat(day)
    off = gg.berlin_offset(d)
    stamp = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone(dt.timedelta(hours=off))).timestamp())
    return f'{seq + 1} +0000' if stamp <= seq else f'{stamp} +0{off}00'


def gg_commits(laws: list[dict], articles: dict) -> list[dict]:
    """The Grundgesetz as commits: one per law and day in force, in order."""
    events: dict[tuple[str, int], list[tuple[str, dict]]] = {}
    for key, a in articles.items():
        for v in a['versions']:
            events.setdefault((v['inForce'], v['nr']), []).append((key, v))
    parts_of = defaultdict(int)
    for (_, nr) in events:
        parts_of[nr] += 1
    seen = defaultdict(int)
    out = []
    for day, nr in sorted(events):
        law = laws[nr]
        seen[nr] += 1
        part = f'Teil {seen[nr]} von {parts_of[nr]}' if parts_of[nr] > 1 else None
        keys = sorted(((k, v['kind']) for k, v in events[(day, nr)]), key=lambda x: gg.unit_order(x[0]))
        ops = {}
        for k, v in events[(day, nr)]:
            path = f'{GG_DIR}/artikel/{gg.file_name(k)}'
            ops[path] = None if v['repealed'] else gg.article_md(k, v['paras']).encode('utf-8')
        out.append({
            'day': day, 'name': law['short'], 'email': f'grundgesetz-{nr}@bgbl.invalid',
            'message': gg.message(law, keys, day, part), 'ops': ops,
            'tags': [f'in-kraft/{day}'] + ([f'gg/{nr:02d}'] if seen[nr] == parts_of[nr] else []),
        })
    return out


def federal_commit(c: dict) -> dict:
    subject, body = br.message(c)
    if c.get('bootstrap'):
        name, email = 'Gesetze im Internet (Bestand)', 'bestand@gesetze-im-internet.invalid'
    elif c['key'] in ('Nicht mehr veröffentlicht', 'Textänderung ohne neue Standangabe', 'Neu aufgenommen'):
        name, email = c['key'], 'ohne-gesetz@bgbl.invalid'
    else:
        name, email = br.law_author(c['key'])
    ops = {}
    for slug, a in c['acts'].items():
        path = 'bund/' + br.path_of(slug)    # bund/gesetze/<letter>/<slug>.md
        ops[path] = None if a['kind'] == 'removed' else a['markdown'].encode('utf-8')
    return {'day': c.get('inForce') or c['day'], 'observed': c['day'], 'name': name, 'email': email,
            'message': f'{subject}\n\n{body}', 'ops': ops, 'tags': []}


class Writer:
    def __init__(self, repo: Path):
        if repo.exists() and any(repo.iterdir()) and not ((repo / '.git').exists() and (repo / 'REPRODUCE.md').exists()):
            raise SystemExit(f'{repo} is not empty and is not an earlier build of this repository; refusing to write into it')
        remote = None
        if (repo / '.git').exists():
            got = subprocess.run(['git', '-C', str(repo), 'remote', 'get-url', 'origin'], capture_output=True, text=True)
            remote = got.stdout.strip() or None
            # git's object files are read-only on Windows, so clear the flag before deleting.
            def force(func, path, _):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(repo / '.git', onerror=force)
            for f in repo.iterdir():
                shutil.rmtree(f, onerror=force) if f.is_dir() else f.unlink()
        repo.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'config', 'core.autocrlf', 'false'], check=True)
        if remote:
            subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', remote], check=True)
        self.repo = repo
        self.fi = subprocess.Popen(['git', '-C', str(repo), 'fast-import', '--quiet', '--done'], stdin=subprocess.PIPE)
        self.out = self.fi.stdin
        self.mark = 0
        self.tags: dict[str, int] = {}

    def data(self, b: bytes) -> None:
        self.out.write(f'data {len(b)}\n'.encode())
        self.out.write(b)
        self.out.write(b'\n')

    def commit(self, c: dict) -> None:
        self.mark += 1
        when = noon(c['day'], self.mark)
        self.out.write(b'commit refs/heads/main\n')
        self.out.write(f'mark :{self.mark}\n'.encode())
        self.out.write(f"author {c['name']} <{c['email']}> {when}\n".encode())
        self.out.write(f'committer {COMMITTER} {when}\n'.encode())
        self.data(c['message'].encode('utf-8'))
        if self.mark > 1:
            self.out.write(f'from :{self.mark - 1}\n'.encode())
        for path in sorted(c['ops']):
            body = c['ops'][path]
            if body is None:
                self.out.write(f'D {path}\n'.encode())
            else:
                self.out.write(f'M 100644 inline {path}\n'.encode())
                self.data(body)
        for t in c['tags']:
            self.tags[t] = self.mark

    def finish(self, files: dict[str, bytes], when_day: str) -> str:
        self.commit({'day': when_day, 'name': 'Lexifina', 'email': 'germany-law@lexifina.com',
                     'message': 'Dokumentation, Verzeichnisse und Werkzeuge\n', 'ops': files, 'tags': []})
        for t, m in sorted(self.tags.items()):
            self.out.write(f'reset refs/tags/{t}\nfrom :{m}\n\n'.encode())
        self.out.write(b'done\n')
        self.out.close()
        if self.fi.wait():
            raise SystemExit('git fast-import failed')
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '-q', '-f', 'main'], check=True)
        return subprocess.run(['git', '-C', str(self.repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b'blob %d\x00' % len(data) + data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--docpatch', default=str(ROOT.parent / 'gg-dev'), help='a clone of c3e/grundgesetz-dev')
    ap.add_argument('--archive', default=str(ROOT.parent / 'german-law-sources' / '03-git' / 'QuantLaw_gesetze-im-internet.git'),
                    help="a clone of QuantLaw/gesetze-im-internet with its 'data' branch")
    ap.add_argument('--repo', default=str(ROOT.parent / 'germany-law'))
    ap.add_argument('--site', default=str(ROOT / 'saas-webpage'), help='where the Grundgesetz reader data goes')
    ap.add_argument('--docs-date', required=True)
    ap.add_argument('--limit', type=int, help='stop the federal part after this many scrapes (testing)')
    args = ap.parse_args()

    # The Grundgesetz.
    revs, steps, fixes, publisher, sources = gg.assemble(Path(args.docpatch), Path(args.archive))
    gg.TEXT_CORRECTIONS.extend(gg.reconciliation_notes(fixes, revs))
    gg.TEXT_CORRECTIONS.extend(gg.publisher_notes(publisher, revs))
    laws, articles, _ = gg.build_record(revs, steps)
    sections = gg.sections_of(articles)
    gg.write_site(Path(args.site), laws, articles, sections, sources, args.docs_date)
    pending = gg_commits(laws, articles)
    print(f'Grundgesetz: {len(pending)} commits, {len(fixes)} articles reconciled', flush=True)

    # Federal law, interleaved: Grundgesetz commits go in before the first federal change observed after them.
    writer = Writer(Path(args.repo))
    state: dict = {}
    stats: dict = defaultdict(int)
    gg_written = 0
    federal = 0
    last_observed = None
    for c in br.iter_commits(Path(args.archive), state, stats, exclude={'gg'}, limit=args.limit):
        while gg_written < len(pending) and pending[gg_written]['day'] <= c['day']:
            writer.commit(pending[gg_written])
            gg_written += 1
        fc = federal_commit(c)
        if last_observed and last_observed != c['day']:
            writer.tags[f'stand/{last_observed}'] = writer.mark
        writer.commit(fc)
        last_observed = c['day']
        federal += 1
    if last_observed:
        writer.tags[f'stand/{last_observed}'] = writer.mark
    for c in pending[gg_written:]:
        writer.commit(c)
    law_commits = writer.mark

    # Documentation, tables and tools, written last.
    tmp = Path(tempfile.mkdtemp(prefix='germany-law-'))
    (tmp / GG_DIR / 'artikel').mkdir(parents=True)
    gg.write_repo_tables(tmp / GG_DIR, laws, articles, sections)
    files: dict[str, bytes] = {}
    for f in sorted(tmp.rglob('*')):
        if f.is_file():
            files[f.relative_to(tmp).as_posix()] = f.read_bytes()
    shutil.rmtree(tmp, ignore_errors=True)
    for f in sorted((HERE / 'repo').rglob('*')):
        if f.is_file():
            files[f.relative_to(HERE / 'repo').as_posix()] = f.read_bytes()
    files['tools/build.py'] = Path(__file__).read_bytes()
    files['tools/grundgesetz.py'] = GG_FILE.read_bytes()
    files['tools/bundesrecht.py'] = BR_FILE.read_bytes()
    index = [{'slug': s, 'path': 'bund/' + br.path_of(s), 'jurabk': a['meta']['jurabk'], 'amtabk': a['meta']['amtabk'],
              'title': a['meta']['title'], 'ausfertigung': a['meta']['ausfertigung'], 'fundstelle': a['meta']['fundstelle'],
              'stand': [list(x) for x in a['meta']['stand']]} for s, a in sorted(state.items())]
    files['bund/gesetze/verzeichnis.json'] = (json.dumps(index, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    numbers = {
        'DOCPATCH_COMMIT': sources['docpatch'],
        'ARCHIVE_COMMIT': subprocess.run(['git', '--git-dir', args.archive, 'rev-parse', 'data'], capture_output=True, text=True).stdout.strip(),
        'GG_COMMITS': str(len(pending)), 'FEDERAL_COMMITS': str(federal), 'LAW_COMMITS': str(law_commits),
        'ACTS': str(len(state)), 'RECONCILED': str(len(fixes)), 'DOCS_DATE': args.docs_date,
        'BUILD_BLOB': blob_id(files['tools/build.py']), 'GG_BLOB': blob_id(files['tools/grundgesetz.py']),
        'BR_BLOB': blob_id(files['tools/bundesrecht.py']),
        'GESETZE_JSON_SHA': hashlib.sha256(files[f'{GG_DIR}/gesetze.json']).hexdigest(),
        'VERZEICHNIS_SHA': hashlib.sha256(files['bund/gesetze/verzeichnis.json']).hexdigest(),
    }
    for name in ('README.md', 'REPRODUCE.md'):
        if name in files:
            text = files[name].decode('utf-8')
            for k, v in numbers.items():
                text = text.replace('{{' + k + '}}', v)
            files[name] = text.encode('utf-8')
    head = writer.finish(files, args.docs_date)
    print(json.dumps({'head': head, **numbers, **stats}, indent=1))


if __name__ == '__main__':
    main()
