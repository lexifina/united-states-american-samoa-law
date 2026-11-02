"""Regression test: a law credited for a version that changes no words (a referendum, a court ruling) gets a commit that
touches no file. append.py must count it as published, not append it again.

Usage: python -X utf8 test_credit_only.py <work dir> [<append.py to test>]
<work dir>/tools is made from ./tools (build.py, check_repo.py and the files build.py ships, as for test_append.py);
the optional second argument replaces its append.py, to run this test against another version of the tool.
"""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
work = Path(sys.argv[1])
if work.exists():
    shutil.rmtree(work)
tools = work / 'tools'
shutil.copytree(HERE / 'tools', tools)
if len(sys.argv) > 2:
    shutil.copy(sys.argv[2], tools / 'append.py')
D = '2026-01-01'


def corpus(with_ruling: bool) -> dict:
    v1 = {'from': '2000-01-01', 'units': {'art-1': {'label': 'Art. 1', 'text': 'One.\n'},
                                          'art-2': {'label': 'Art. 2', 'text': 'Two.\n'}}}
    v2 = {'from': '2010-01-01', 'units': {'art-1': {'label': 'Art. 1', 'text': 'One, amended.\n'},
                                          'art-2': {'label': 'Art. 2', 'text': 'Two.\n'}},
          'credits': {'art-1': ['act-2']}}
    # The same text as v2, credited to a ruling: a commit with no file changes ("wording unchanged").
    v3 = {'from': '2020-01-01', 'units': v2['units'], 'credits': {'art-2': ['ruling-1']}}
    return {
        'country': {'code': 'XT', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                    'publisher': {'name': 'Testland Gazette', 'email': 'gazette@testland.invalid'}},
        'laws': {'act-1': {'label': 'Act 1', 'enacted': '1999-12-01'},
                 'act-2': {'label': 'Act 2', 'enacted': '2009-12-01'},
                 'ruling-1': {'label': 'Ruling 1', 'kind': 'court', 'enacted': '2019-12-01'}},
        'acts': [{'slug': 'constitution', 'short': 'Const', 'title': 'Constitution', 'first_law': 'act-1',
                  'versions': [v1, v2] + ([v3] if with_ruling else [])}],
        'sources': [{'name': 'Testland Gazette', 'url': 'https://testland.invalid/', 'retrieved': D}]}


def folder(name: str, with_ruling: bool) -> Path:
    f = work / name
    f.mkdir(parents=True)
    (f / 'corpus.json').write_text(json.dumps(corpus(with_ruling), ensure_ascii=False), encoding='utf-8', newline='\n')
    return f


def run(*args) -> str:
    out = subprocess.run([sys.executable, '-X', 'utf8', *map(str, args)], capture_output=True, text=True,
                         encoding='utf-8')
    if out.returncode:
        raise SystemExit(f'failed: {args}\n{out.stdout[-1500:]}\n{out.stderr[-1500:]}')
    return out.stdout


def g(repo: Path, *args) -> str:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout


def append(f: Path, repo: Path) -> dict:
    res = ast.literal_eval(run(tools / 'append.py', f, '--repo', repo, '--docs-date', D).strip().splitlines()[-1])
    print('append:', {k: res[k] for k in ('commits', 'new_acts', 'extended_acts')})
    return res


full, partial = folder('full', True), folder('partial', False)
failures = []

# 1. A full build ending in the credit-only commit, then an append of the same corpus: nothing to add.
repo = work / 'repo'
run(tools / 'build.py', full, '--repo', repo, '--docs-date', D)
log = g(repo, 'log', '--format=%an|%(trailers:key=Words-changed,valueonly,separator=)', 'main')
assert 'Ruling 1|no' in log, f'the build has no credit-only commit:\n{log}'
before = g(repo, 'rev-list', 'main').split()
if append(full, repo)['commits'] != 0 or g(repo, 'rev-list', 'main').split() != before:
    failures.append('full build + append of the same corpus added commits (the credit-only commit again)')

# 2. The credit-only version appended to a build without it: exactly one commit, and a second append adds nothing.
repo2 = work / 'repo2'
run(tools / 'build.py', partial, '--repo', repo2, '--docs-date', D)
n = append(full, repo2)['commits']
if n != 1:
    failures.append(f'appending the credit-only version made {n} commits, not 1')
after = g(repo2, 'rev-list', 'main').split()
if append(full, repo2)['commits'] != 0 or g(repo2, 'rev-list', 'main').split() != after:
    failures.append('a second append re-appended the credit-only commit')
print(run(tools / 'check_repo.py', repo2, '--corpus', full / 'corpus.json').split('"details"')[0].strip())

if failures:
    raise SystemExit('FAILED:\n- ' + '\n- '.join(failures))
print('ALL OK')
