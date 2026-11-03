"""Test append.py --corrections: a published history whose text turns out wrong, or that lacks a version found later,
gets labelled correction commits (one per corrected act version) with no published SHA or tag changed.

Usage: python -X utf8 test_corrections.py <work dir> [<append.py to test>]
<work dir>/tools is made from ./tools (build.py, check_repo.py and the files build.py ships, as for test_append.py);
the optional second argument replaces its append.py.

Each case builds a small synthetic corpus as "published", then appends the corrected corpus:
- newest: one unit wrong in the newest version: 1 correction commit;
- middle: one unit wrong in a middle version that the next version changes again: the correction, then the newest
  version's commit setting that file back at the tip (2 commits);
- backfill: the published history lacks the 2010 version: 1 correction (Supersedes is the commit read that day);
- newer: a correction plus a newer version appended after it in the same run.
And, in a repository made by hand: a one-file act whose path has a comma (title-11/362,1.md), in a folder it shares
with another act's file; its correction's open range must hold across the sibling's commit and end at the act's own.
For each corpus case: without --corrections the run refuses and changes nothing; with it, check_corrected() reads 0 mismatches and
an equal tip, the plain check_repo still runs, trailers are as specified, no published SHA or tag changed, a second run
adds 0, and another clone of the same head with the same corpus gets the same hashes.
"""
import ast
import json
import re
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
failures: list[str] = []


def u(label: str, text: str) -> dict:
    return {'label': label, 'text': text}


def corpus(case: str, fixed: bool) -> dict:
    a1, a2, a3 = u('Art. 1', 'One.\n'), u('Art. 2', 'Two.\n'), u('Art. 3', 'Three.\n')
    v1 = {'from': '2000-01-01', 'units': {'art-1': a1, 'art-2': a2, 'art-3': a3}}
    v2 = {'from': '2010-01-01', 'units': {**v1['units'], 'art-2': u('Art. 2', 'Two, amended.\n')},
          'credits': {'art-2': ['act-2']}}
    v3 = {'from': '2020-01-01', 'units': {**v2['units'], 'art-1': u('Art. 1', 'One, amended.\n')},
          'credits': {'art-1': ['act-3']}}
    if case == 'middle':  # the 2020 law changes Art. 2 again
        v3 = {**v3, 'units': {**v3['units'], 'art-2': u('Art. 2', 'Two, amended twice.\n')},
              'credits': {'art-1': ['act-3'], 'art-2': ['act-3']}}
    vs = [v1, v2, v3]
    if not fixed:
        if case in ('newest', 'newer'):  # published with Art. 3 of 2020 misread
            vs = [v1, v2, {**v3, 'units': {**v3['units'], 'art-3': u('Art. 3', 'Three, misread.\n')}}]
        elif case == 'middle':  # published with Art. 2 of 2010 misread
            vs = [v1, {**v2, 'units': {**v2['units'], 'art-2': u('Art. 2', 'Two, misread.\n')}}, v3]
        elif case == 'backfill':  # published without the 2010 version
            vs = [v1, {**v3, 'credits': {'art-1': ['act-3'], 'art-2': ['act-2']}}]
    if case == 'newer' and fixed:
        vs.append({'from': '2024-01-01', 'units': {**v3['units'], 'art-1': u('Art. 1', 'One, amended twice.\n')},
                   'credits': {'art-1': ['act-4']}})
    return {
        'country': {'code': 'XT', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                    'publisher': {'name': 'Testland Gazette', 'email': 'gazette@testland.invalid'}},
        'laws': {'act-1': {'label': 'Act 1', 'enacted': '1999-12-01'},
                 'act-2': {'label': 'Act 2', 'enacted': '2009-12-01'},
                 'act-3': {'label': 'Act 3', 'enacted': '2019-12-01'},
                 'act-4': {'label': 'Act 4', 'enacted': '2023-12-01'}},
        'acts': [{'slug': 'constitution', 'short': 'Const', 'title': 'Constitution', 'first_law': 'act-1',
                  'versions': vs},
                 {'slug': 'other', 'short': 'Other', 'title': 'Other Act', 'first_law': 'act-1',
                  'versions': [{'from': '2001-01-01', 'units': {'s-1': u('S. 1', 'Untouched.\n')}}]}],
        'sources': [{'name': 'Testland Gazette', 'url': 'https://testland.invalid/', 'retrieved': D}]}


def folder(name: str, c: dict) -> Path:
    f = work / name
    f.mkdir(parents=True)
    (f / 'corpus.json').write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8', newline='\n')
    return f


def run(*args, ok=True, cwd=None) -> subprocess.CompletedProcess:
    out = subprocess.run([sys.executable, '-X', 'utf8', *map(str, args)], capture_output=True, text=True,
                         encoding='utf-8', cwd=cwd)
    if ok and out.returncode:
        raise SystemExit(f'failed: {args}\n{out.stdout[-1500:]}\n{out.stderr[-1500:]}')
    return out


def g(repo: Path, *args) -> str:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout


def append(f: Path, repo: Path, *flags) -> dict:
    return ast.literal_eval(run(tools / 'append.py', f, '--repo', repo, '--docs-date', D, *flags)
                            .stdout.strip().splitlines()[-1])


def snapshot(repo: Path) -> tuple[list[str], dict[str, str]]:
    return g(repo, 'rev-list', 'main').split(), {t: g(repo, 'rev-parse', t).strip() for t in g(repo, 'tag', '--list').split()}


READ = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import append as A
c, _ = A.B.load(A.Path(sys.argv[3]))
res = A.check_corrected(A.Path(sys.argv[2]), c, sys.argv[4])
rd = A.Reader(A.Path(sys.argv[2]), [a['slug'] for a in c['acts']])
res['reads'] = {f'{d} {s}': rd.files(s, d) for s in ('constitution', 'other') for d in sys.argv[5:]}
rd.close()
print(json.dumps(res))
'''


def case(name: str, expect: int, expect_new: int = 0):
    pub, fix = folder(f'{name}-published', corpus(name, False)), folder(f'{name}-fixed', corpus(name, True))
    repo, ref = work / f'{name}-repo', work / f'{name}-ref'
    run(tools / 'build.py', pub, '--repo', repo, '--docs-date', D)
    before, tags_before = snapshot(repo)
    r = run(tools / 'append.py', fix, '--repo', repo, '--docs-date', D, ok=False)
    if r.returncode == 0 or 'main does not match the corpus' not in r.stdout + r.stderr:
        failures.append(f'{name}: without --corrections the run did not refuse')
    if snapshot(repo) != (before, tags_before):
        failures.append(f'{name}: a refused run changed the repository')
    res = append(fix, repo, '--corrections')
    print(f'{name}:', {k: res.get(k) for k in ('commits', 'corrections', 'corrected', 'extended_acts')})
    if res['corrections'] != expect or res['commits'] != expect + expect_new:
        failures.append(f'{name}: {res["corrections"]} corrections and {res["commits"]} commits, expected {expect} '
                        f'and {expect + expect_new}')
    after, tags_after = snapshot(repo)
    if after[-len(before):] != before:
        failures.append(f'{name}: published history changed')
    if [t for t, s in tags_before.items() if tags_after.get(t) != s]:
        failures.append(f'{name}: a published tag moved')
    # The check for a corrected main, and the reading with corrections applied.
    days = ['2005-06-01', '2015-06-01', '2022-06-01', '2025-06-01']
    chk = json.loads(run('-c', READ, tools, repo, fix, D, *days).stdout)
    print(f'{name}: check_corrected', {k: chk[k] for k in ('versions', 'mismatches', 'tip_mismatches', 'corrections',
                                                          'trailer_errors', 'backwards')})
    if any(chk[k] for k in ('mismatches', 'tip_mismatches', 'trailer_errors', 'missing_in_force', 'merges',
                            'backwards', 'future_dated')):
        failures.append(f'{name}: check_corrected found problems: {chk["details"][:5]}')
    c = corpus(name, True)
    import hashlib
    for key, files in chk['reads'].items():
        d, s = key.split()
        act = next(a for a in c['acts'] if a['slug'] == s)
        v = [w for w in act['versions'] if w['from'] <= d][-1]
        want = {f'{s}/{k}.md': hashlib.sha1(b'blob %d\0' % len(x['text'].encode()) + x['text'].encode()).hexdigest()
                for k, x in v['units'].items()}
        if files != want:
            failures.append(f'{name}: read with corrections on {key} gives the wrong text')
    # The plain check (readers that ignore the trailers) still runs.
    plain = run(tools / 'check_repo.py', repo, '--corpus', fix / 'corpus.json', ok=False)
    try:
        json.loads(plain.stdout)
    except ValueError:
        failures.append(f'{name}: check_repo crashed on a corrected main: {plain.stderr[-300:]}')
    # Trailers, and order by in-force day then act.
    log = g(repo, 'log', '--reverse', '--format=%H%x1f%(trailers:key=Kind,valueonly,separator=)%x1f'
            '%(trailers:key=In-force,valueonly,separator=)%x1f%(trailers:key=Corrects,valueonly,separator=|)%x1f'
            '%(trailers:key=Supersedes,valueonly,separator=|)%x1f%(trailers:key=Reason,valueonly,separator=|)%x1e',
            'main')
    fixes = [x.strip('\n').split('\x1f') for x in log.split('\x1e') if '\x1fcorrection\x1f' in x]
    if len(fixes) != expect:
        failures.append(f'{name}: {len(fixes)} commits labelled Kind: correction, expected {expect}')
    order = []
    for h, _, day, cor, sup, why in fixes:
        m = re.fullmatch(r'([a-z0-9-]+) (\d{4}-\d\d-\d\d)\.\.(\d{4}-\d\d-\d\d)?', cor)
        if not m or m.group(2) != day or not (sup == 'none' or sup in before) or not why or '|' in cor + sup + why:
            failures.append(f'{name}: correction {h[:10]} has In-force {day!r}, Corrects {cor!r}, Supersedes {sup!r}, '
                            f'Reason {why!r}')
            continue
        order.append((day, m.group(1)))
    if order != sorted(order):
        failures.append(f'{name}: corrections are not in in-force order: {order}')
    if append(fix, repo, '--corrections')['commits'] != 0 or snapshot(repo)[0] != after:
        failures.append(f'{name}: a second run added commits')
    run(tools / 'build.py', pub, '--repo', ref, '--docs-date', D)
    append(fix, ref, '--corrections')
    if g(ref, 'rev-parse', 'main') != g(repo, 'rev-parse', 'main'):
        failures.append(f'{name}: corrections are not deterministic')
    return repo, fixes


repo, fixes = case('newest', 1)
body = g(repo, 'log', '-1', '--format=%B', fixes[0][0])
for want in ('Correction: Const, version in force from 2020-01-01', 'Wording differed: Art. 3.',
             'Corrects: constitution 2020-01-01..\n', 'Reason: text corrected from the official source'):
    if want not in body:
        failures.append(f'newest: the message lacks {want!r}:\n{body}')
if g(repo, 'diff-tree', '-r', '--name-only', '--no-commit-id', fixes[0][0]).split() != ['constitution/art-3.md']:
    failures.append('newest: the correction does not change exactly the one wrong file')
keys = g(repo, 'log', '-1', '--format=%(trailers:keyonly,separator=%x2C)', fixes[0][0]).strip()
if keys != 'Kind,In-force,Corrects,Supersedes,Reason,Act-path,Files':
    failures.append(f'newest: trailer order is {keys}')
if 'Act-path: constitution\nFiles: constitution/art-3.md\n' not in body:
    failures.append(f'newest: Act-path / Files lines are wrong:\n{body}')
repo, fixes = case('middle', 2)
if [f[3] for f in fixes] != ['constitution 2010-01-01..2019-12-31', 'constitution 2020-01-01..']:
    failures.append(f'middle: Corrects are {[f[3] for f in fixes]}')
repo, fixes = case('backfill', 1)
if fixes and (fixes[0][3] != 'constitution 2010-01-01..2019-12-31' or 'found late' not in fixes[0][5]):
    failures.append(f'backfill: {fixes[0][3:]}')
case('newer', 1, 1)


def shared_folder():
    """A one-file act (title-11/362,1.md: a path with a comma) in a folder it shares with another act's file. The
    correction's open range must not end at the sibling's ordinary commit, only at the next one touching Act-path."""
    import os
    repo = work / 'shared-repo'
    repo.mkdir()
    g(repo, 'init', '-q', '-b', 'main')
    act, sib = 'title-11/362,1.md', 'title-11/363.md'
    n = [0]

    def commit(files: dict, msg: str) -> str:
        for path, text in files.items():
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_bytes(text.encode('utf-8'))
        subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
        n[0] += 1
        when = f'{1700000000 + n[0]} +0000'
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@testland.invalid', 'commit', '-q', '-m',
                        msg], cwd=repo, check=True, env={**os.environ, 'GIT_AUTHOR_DATE': when, 'GIT_COMMITTER_DATE': when})
        return g(repo, 'rev-parse', 'HEAD').strip()

    a = commit({act: 'Old.\n', sib: 'Sibling.\n'}, 'Both\n\nIn-force: 2000-01-01')
    commit({act: 'Fixed.\n'}, 'Correction: s. 362\n\nKind: correction\nIn-force: 2010-01-01\nCorrects: us-11-362 '
           f'2010-01-01..\nSupersedes: {a}\nReason: test\nAct-path: {act}\nFiles: {act}')
    commit({sib: 'Sibling, amended.\n'}, 'Sibling\n\nIn-force: 2015-01-01')
    commit({act: 'New.\n'}, 'New text\n\nIn-force: 2020-01-01')
    probe = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import append as A
repo = A.Path(sys.argv[2])
rd = A.Reader(repo, ['us-11-362'])
out = {'fixes': [{k: f[k] for k in ('ranges', 'paths', 'files')} for f in rd.fixes],
       'reads': {d: rd.files('us-11-362', d) for d in ('2005-06-01', '2012-06-01', '2016-06-01', '2021-06-01')}}
rd.close()
print(json.dumps(out))
'''
    res = json.loads(run('-c', probe, tools, repo).stdout)
    import hashlib

    def oid(t: str) -> str:
        return hashlib.sha1(b'blob %d\0' % len(t.encode()) + t.encode()).hexdigest()

    want_fix = [{'ranges': {'us-11-362': ['2010-01-01', None]}, 'paths': {'us-11-362': act},
                 'files': {'us-11-362': {act: oid('Fixed.\n')}}}]
    if res['fixes'] != want_fix:
        failures.append(f'shared folder: corrections read as {res["fixes"]}')
    for d, t in (('2005-06-01', 'Old.\n'), ('2012-06-01', 'Fixed.\n'), ('2016-06-01', 'Fixed.\n'),
                 ('2021-06-01', 'New.\n')):
        if res['reads'][d] != {act: oid(t)}:
            failures.append(f'shared folder: on {d} the act reads {res["reads"][d]}, expected {t!r}')
    print('shared folder:', 'reads', {d: v for d, v in res['reads'].items()})


shared_folder()

if failures:
    raise SystemExit('FAILED:\n- ' + '\n- '.join(failures))
print('ALL OK')
