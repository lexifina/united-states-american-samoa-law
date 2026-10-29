"""Build the global-law superproject from the per-corpus law repos. Standard library only.

  python scripts/global-law/build.py <out> --date 2026-10-28 [--local ~/Documents] [--site-data FILE]

By default each corpus is read from a fresh bare clone of its published repo, so every pin can be fetched by anyone
who clones this one. `--local DIR` reads unpublished checkouts instead, for trying a corpus rebuild before it is
pushed; do not publish a build made that way.

Each corpus (the US Code, the Grundgesetz, the UK SEND provisions) stays its own repo with its own history, and
becomes a submodule at a path that names its jurisdiction: country (ISO 3166-1), then level (federal, a state's ISO
3166-2 code, ...), then the corpus. The root history interleaves every corpus's commits in the order the changes took
force, one root commit per corpus commit, each moving that corpus's pin. A root commit is therefore the state of all
the law in the tree at one moment. Rebuilding from the same corpus commits gives the same hashes; republishing after a
corpus is rebuilt means a force-push.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMITTER = ('Lexifina', 'global-law@lexifina.com')

JURISDICTIONS = {
    '': {'name': 'Global law', 'level': 'world'},
    'de': {'name': 'Germany', 'level': 'country', 'code': 'DE'},
    'de/bund': {'name': 'Bund (federal law)', 'level': 'federal', 'legislature': 'Bundestag and Bundesrat'},
    'gb': {'name': 'United Kingdom', 'level': 'country', 'code': 'GB'},
    'gb/uk': {'name': 'UK Parliament and UK ministers', 'level': 'national',
              'note': 'Devolved legislatures go beside this as gb/sct, gb/wls and gb/nir.'},
    'us': {'name': 'United States', 'level': 'country', 'code': 'US'},
    'us/federal': {'name': 'Federal law', 'level': 'federal', 'legislature': 'Congress',
                   'note': 'States go beside this by ISO 3166-2 code, for example us/ca.'},
}

CORPORA = [
    {'path': 'de/bund/grundgesetz', 'repo': 'grundgesetz', 'url': 'https://github.com/lexifina/germany-law.git',
     'name': 'Grundgesetz für die Bundesrepublik Deutschland', 'label': 'Germany', 'language': 'de',
     'coverage': '1949 to the 69th amendment, matching the official text of 28 October 2026', 'in_force_trailer': 'In-Kraft',
     'record_to': '2026-10-28', 'record_note': 'Checked against gesetze-im-internet.de on 28 October 2026.'},
    {'path': 'gb/uk/send', 'repo': 'uk-law-history', 'url': 'https://github.com/lexifina/uk-law-history.git',
     'name': 'Special educational needs: Children and Families Act 2014 Part 3 and the SEND Regulations 2014 (selected provisions)',
     'label': 'UK', 'language': 'en', 'coverage': '2014 to 2021', 'in_force_trailer': 'In-force',
     'record_to': '2026-10-28', 'record_note': 'Checked against legislation.gov.uk on 28 October 2026.'},
    {'path': 'us/federal/usc', 'repo': 'us-code-history', 'url': 'https://github.com/lexifina/us-code-history.git',
     'name': 'United States Code, titles 1, 3, 4, 9, 11, 13, 17, 35 and 39', 'label': 'US', 'language': 'en',
     'coverage': 'the 2017 edition (current through 2018-01-12) to release point 119-87', 'in_force_trailer': 'In-force',
     'record_to': '2026-04-01', 'record_note': 'It follows the Code through release point 119-87; later laws are not in it.'},
]

# Corpora built by the shared builder (scripts/gitlaw_common), added once each is pushed and checked. Each entry gives
# the country (ISO 3166-1), its name and the corpus fields above; the country and its national level are added to the
# jurisdiction tree. All of them use the In-force trailer.
COMMON = json.loads((HERE / 'common_corpora.json').read_text(encoding='utf-8')) if (HERE / 'common_corpora.json').exists() else []
for _c in COMMON:
    _iso = _c['path'].split('/')[0]
    JURISDICTIONS.setdefault(_iso, {'name': _c['country'], 'level': 'country', 'code': _iso.upper()})
    JURISDICTIONS.setdefault(f'{_iso}/national', {'name': 'National law', 'level': 'national'})
    CORPORA.append({'in_force_trailer': 'In-force', **{k: v for k, v in _c.items() if k != 'country'}})


def git(*args: str, cwd: Path, env: dict | None = None, data: str | None = None) -> str:
    done = subprocess.run(['git', *args], cwd=cwd, capture_output=True, encoding='utf-8', input=data,
                          env={**os.environ, **(env or {})})
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def trailers(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in body.splitlines():
        key, sep, value = line.partition(': ')
        if sep and key and ' ' not in key and key[0].isupper():
            out.setdefault(key, value.strip())
    return out


def corpus_commits(corpus: dict, repo: Path) -> list[dict]:
    raw = git('log', '--first-parent', '--reverse', '--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f%B%x1e', cwd=repo)
    out = []
    for i, record in enumerate(r for r in raw.split('\x1e') if r.strip()):
        sha, name, email, date, subject, body = record.strip('\n').split('\x1f', 5)
        t = trailers(body)
        in_force = t.get(corpus['in_force_trailer'])
        kind = 'law' if in_force else ('baseline' if i == 0 else 'documentation')
        out.append({'sha': sha, 'name': name, 'email': email, 'date': date, 'subject': subject,
                    'in_force': in_force or date[:10], 'kind': kind,
                    'refs': {k: t[k] for k in ('Gesetz', 'Law', 'Affecting', 'Enacted', 'Made', 'Verkündet', 'Verkuendet') if k in t}})
    return out


def leaf_tags(repo: Path) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for line in git('tag', '--format=%(objectname) %(*objectname) %(refname:short)', cwd=repo).splitlines():
        parts = line.split()
        sha, name = (parts[1], parts[2]) if len(parts) == 3 else (parts[0], parts[1])
        tags.setdefault(sha, []).append(name)
    return tags


def merge(streams: list[list[dict]]) -> list[tuple[int, dict]]:
    """Interleave the corpora by in-force date, keeping each corpus's own order."""
    heads, out = [0] * len(streams), []
    while True:
        ready = [(streams[i][h]['in_force'], i) for i, h in enumerate(heads) if h < len(streams[i])]
        if not ready:
            return out
        _, i = min(ready)
        out.append((i, streams[i][heads[i]]))
        heads[i] += 1


def commit(out: Path, tree: str, parent: str | None, message: str, author: tuple[str, str], date: str) -> str:
    env = {'GIT_AUTHOR_NAME': author[0], 'GIT_AUTHOR_EMAIL': author[1], 'GIT_AUTHOR_DATE': date,
           'GIT_COMMITTER_NAME': COMMITTER[0], 'GIT_COMMITTER_EMAIL': COMMITTER[1], 'GIT_COMMITTER_DATE': date}
    args = ['commit-tree', tree] + (['-p', parent] if parent else [])
    return git(*args, cwd=out, env=env, data=message).strip()


def write(out: Path, rel: str, text: str) -> None:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--local', type=Path, help='read corpus checkouts from this folder instead of their published repos')
    ap.add_argument('--site-data', type=Path, help='also write the timeline as JSON for the /watch/global-law page')
    # Required, never "today": a rebuild on another day must give the same hashes.
    ap.add_argument('--date', required=True, help='date of the closing documentation commit, e.g. 2026-10-28')
    a = ap.parse_args()

    out = a.out.resolve()
    if out.exists() and any(out.iterdir()):
        if not (out / 'manifest.json').exists():
            raise SystemExit(f'{out} exists and is not a global-law build; refusing to replace it')
        def writable(func, path, _exc):  # git object files are read-only on Windows
            os.chmod(path, 0o666)
            func(path)
        # Empty the folder rather than remove it: another program may have it open as its working directory.
        for child in out.iterdir():
            shutil.rmtree(child, onexc=writable) if child.is_dir() and not child.is_symlink() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    git('init', '-q', '-b', 'main', cwd=out)
    git('config', 'core.autocrlf', 'false', cwd=out)

    # Commit 1, at the start of git time: the jurisdiction tree and the corpus list, no law yet.
    manifest = {'scheme': 'country (ISO 3166-1 alpha-2) / level (federal, national, or an ISO 3166-2 subdivision) / corpus',
                'date_rule': 'Root commits are in in-force order; the In-force trailer is authoritative (git cannot store dates before 1970).',
                'corpora': [{k: v for k, v in c.items() if k != 'repo'} for c in CORPORA]}
    write(out, 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    for path, info in JURISDICTIONS.items():
        children = sorted({p for p in JURISDICTIONS if p and p.rsplit('/', 1)[0] == path and p != path} if path else
                          {p for p in JURISDICTIONS if p and '/' not in p})
        corpora = [c['path'] for c in CORPORA if c['path'].rsplit('/', 1)[0] == path]
        body = {**info, 'path': path or '.', 'jurisdictions': children, 'corpora': corpora}
        write(out, f'{path}/jurisdiction.json' if path else 'jurisdiction.json', json.dumps(body, ensure_ascii=False, indent=2) + '\n')
    write(out, '.gitmodules', ''.join(f'[submodule "{c["path"]}"]\n\tpath = {c["path"]}\n\turl = {c["url"]}\n' for c in CORPORA))
    git('add', '-A', cwd=out)
    head = commit(out, git('write-tree', cwd=out).strip(), None,
                  'Jurisdictions and corpora, before any law\n\nThe tree of jurisdictions and the list of corpora. Each later commit is one law taking\neffect in one corpus, in the order the changes took force.\n',
                  COMMITTER, '1970-01-01T00:00:00Z')

    # One root commit per corpus commit, in in-force order, each moving that corpus's pin.
    streams, tags = [], []
    for c in CORPORA:
        if a.local:
            repo = a.local / c['repo']
        else:
            repo = out / '.git' / 'corpus-cache' / c['repo']
            git('clone', '-q', '--bare', c['url'], str(repo), cwd=out)
        streams.append(corpus_commits(c, repo))
        tags.append(leaf_tags(repo))
    last = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    count, events = 0, []
    for i, leaf in merge(streams):
        c = CORPORA[i]
        git('update-index', '--add', '--cacheinfo', f"160000,{leaf['sha']},{c['path']}", cwd=out)
        # Never earlier than its parent, so `git log --before` stays a prefix of the history.
        when = max(dt.datetime.fromisoformat(leaf['date'].replace('Z', '+00:00')), last)
        date = when.isoformat()
        message = (f"{c['label']}: {leaf['subject']}\n\n{leaf['name']}, in {c['name']}.\n\n"
                   f"Corpus: {c['path']}\nCorpus-commit: {leaf['sha']}\nLaw: {leaf['name']}\n"
                   f"In-force: {leaf['in_force']}\nKind: {leaf['kind']}\n")
        head = commit(out, git('write-tree', cwd=out).strip(), head, message, (leaf['name'], leaf['email']), date)
        last = when
        count += 1
        events.append({'inForce': leaf['in_force'], 'corpus': c['path'], 'law': leaf['name'], 'subject': leaf['subject'],
                       'kind': leaf['kind'], 'root': head, 'leaf': leaf['sha'], 'refs': leaf['refs']})
        for name in tags[i].get(leaf['sha'], []):
            git('tag', f"{c['path']}/{name}", head, cwd=out)

    # Closing commit: the documentation and the tools, dated the build day.
    docs = [(src, src.relative_to(HERE / 'repo').as_posix()) for src in sorted((HERE / 'repo').rglob('*'))
            if src.is_file() and '__pycache__' not in src.parts]
    docs.append((Path(__file__).resolve(), 'tools/build.py'))  # the builder ships with what it built
    # REPRODUCE.md names the commits pinned, the number of commits and the files' blob hashes as of this build.
    pins = ''.join(f"| `{c['path']}` | {c['url'].removesuffix('.git')} | `{git('ls-tree', head, '--', c['path'], cwd=out).split()[2]}` |\n"
                   for c in CORPORA)
    blob = lambda p: git('hash-object', str(p), cwd=out).strip()  # noqa: E731
    fill = {'{{PINS}}': pins.rstrip('\n'), '{{COMMITS}}': str(count + 2), '{{BUILD_BLOB}}': blob(Path(__file__).resolve()),
            '{{LAW_BLOB}}': blob(HERE / 'repo/tools/law.py'), '{{TEST_BLOB}}': blob(HERE / 'repo/tests/test_law.py'),
            '{{TESTS}}': str((HERE / 'repo/tests/test_law.py').read_text(encoding='utf-8').count('\n    def test_'))}
    for src, rel in docs:
        text = src.read_text(encoding='utf-8')
        if rel in ('REPRODUCE.md', 'README.md'):
            for key, value in fill.items():
                text = text.replace(key, value)
        write(out, rel, text)
        git('add', '--', rel, cwd=out)  # not `add -A`: the corpus folders are not checked out and would drop the pins
    head = commit(out, git('write-tree', cwd=out).strip(), head,
                  'README, tools and tests: how to read the tree on any date\n', COMMITTER,
                  max(dt.datetime.fromisoformat(f'{a.date}T12:00:00+00:00'), last + dt.timedelta(seconds=1)).isoformat())
    git('update-ref', 'refs/heads/main', head, cwd=out)
    git('reset', '-q', '--hard', 'main', cwd=out)
    print(f'{count} corpus commits from {len(CORPORA)} corpora -> {out} ({head[:7]})')
    if a.site_data:
        tree = [{'path': p, **info} for p, info in JURISDICTIONS.items()]
        corpora = [{k: v for k, v in c.items() if k not in ('repo', 'in_force_trailer')} for c in CORPORA]
        data = {'head': head, 'built': a.date, 'jurisdictions': tree, 'corpora': corpora, 'events': events}
        a.site_data.parent.mkdir(parents=True, exist_ok=True)
        a.site_data.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
        print(f'site data -> {a.site_data}')


if __name__ == '__main__':
    main()
