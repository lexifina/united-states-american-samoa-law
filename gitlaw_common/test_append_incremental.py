"""Tests append_gate.check_appended() (the --incremental check): it must fail on any appended text that differs from
the corpus, on a backwards date, on an In-force day after the data date and on a version left out, and pass a clean
append exactly where the full check (check_main) passes.

    python -X utf8 scripts/gitlaw_common/test_append_incremental.py [<work dir>]

The corpus is the Testland fixture of world-law-ops tools/append-only/test_credit_only.py, grown by one changed
version of a held act, one new act, and one act the append leaves alone. A partial build is "published" to a local
bare repository; append_gate.run() grows a publish clone of it, as autopush does.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import append_gate as AG  # noqa: E402

work = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / 'Documents' / '.gitlaw-append' / 'work' / 'test-incremental'
if work.exists():
    shutil.rmtree(work, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
work.mkdir(parents=True)
D = '2026-01-01'


def u(label, text):
    return {'label': label, 'text': text}


def corpus(full: bool) -> dict:
    v1 = {'from': '2000-01-01', 'units': {'art-1': u('Art. 1', 'One.\n'), 'art-2': u('Art. 2', 'Two.\n')}}
    v2 = {'from': '2010-01-01', 'units': {'art-1': u('Art. 1', 'One, amended.\n'), 'art-2': u('Art. 2', 'Two.\n')},
          'credits': {'art-1': ['act-2']}}
    v3 = {'from': '2020-01-01', 'units': {'art-1': u('Art. 1', 'One, amended.\n'), 'art-2': u('Art. 2', 'Two, again.\n')},
          'credits': {'art-2': ['act-3']}}
    code = {'slug': 'code', 'short': 'Code', 'title': 'Civil Code', 'first_law': 'act-1',
            'versions': [{'from': '2000-01-01', 'units': {'s-1': u('S. 1', 'Code text.\n')}}]}
    acts = [{'slug': 'constitution', 'short': 'Const', 'title': 'Constitution', 'first_law': 'act-1',
             'versions': [v1, v2] + ([v3] if full else [])}, code]
    if full:
        acts.append({'slug': 'statute', 'short': 'Stat', 'title': 'Statute', 'first_law': 'act-4',
                     'versions': [{'from': '2015-01-01', 'units': {'s-1': u('S. 1', 'Statute.\n')}},
                                  {'from': '2024-01-01', 'units': {'s-1': u('S. 1', 'Statute, amended.\n'),
                                                                   's-2': u('S. 2', 'New section.\n')},
                                   'credits': {'s-1': ['act-5'], 's-2': ['act-5']}}]})
    laws = {'act-1': {'label': 'Act 1', 'enacted': '1999-12-01'}, 'act-2': {'label': 'Act 2', 'enacted': '2009-12-01'},
            'act-3': {'label': 'Act 3', 'enacted': '2019-12-01'}, 'act-4': {'label': 'Act 4', 'enacted': '2014-12-01'},
            'act-5': {'label': 'Act 5', 'enacted': '2023-12-01'}}
    return {'country': {'code': 'XT', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                        'publisher': {'name': 'Testland Gazette', 'email': 'gazette@testland.invalid'}},
            'laws': laws, 'acts': acts,
            'sources': [{'name': 'Testland Gazette', 'url': 'https://testland.invalid/', 'retrieved': D}]}


def folder(name: str, c: dict) -> Path:
    f = work / name
    f.mkdir(parents=True, exist_ok=True)
    (f / 'corpus.json').write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8', newline='\n')
    return f


def g(repo: Path, *args, env=None) -> str:
    r = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8',
                       env={**os.environ, **(env or {})})
    if r.returncode:
        raise SystemExit(f'git {args}: {r.stderr}')
    return r.stdout.strip()


def commit_on(repo: Path, parent: str, files: dict[str, str], msg: str, ct: int | None = None,
              author: str = 'Testland Gazette') -> str:
    """A commit on `parent` changing `files` (path -> text), through a private index; ct sets the committer date."""
    env = {'GIT_INDEX_FILE': str(work / 'tmp-index'), 'GIT_AUTHOR_NAME': author,
           'GIT_AUTHOR_EMAIL': 'gazette@testland.invalid', 'GIT_COMMITTER_NAME': 'Lexifina',
           'GIT_COMMITTER_EMAIL': 'testland-law@lexifina.com'}
    if ct is not None:
        env['GIT_COMMITTER_DATE'] = f'{ct} +0000'
    g(repo, 'read-tree', parent, env=env)
    for path, text in files.items():
        # Bytes, not text: a text-mode pipe on Windows would write \r\n.
        blob = subprocess.run(['git', 'hash-object', '-w', '--stdin'], cwd=repo, input=text.encode('utf-8'),
                              capture_output=True).stdout.decode().strip()
        g(repo, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=env)
    tree = g(repo, 'write-tree', env=env)
    r = subprocess.run(['git', 'commit-tree', tree, '-p', parent], cwd=repo, input=msg, capture_output=True, text=True,
                       encoding='utf-8', env={**os.environ, **env})
    return r.stdout.strip()


def failed(chk: dict) -> bool:
    return any(chk.get(k) for k in AG.FAIL_KEYS)  # tip_mismatches comes only from check_corrected()


results: list[tuple[str, bool]] = []


def expect(name: str, ok: bool, info=''):
    results.append((name, ok))
    print(f'{"PASS" if ok else "FAIL"}  {name}  {info}')


# Published: a full build of the partial corpus, served from a local bare repository.
partial, full = folder('partial', corpus(False)), folder('full', corpus(True))
build = work / 'build'
r = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'build.py'), str(partial), '--repo', str(build),
                    '--docs-date', D], capture_output=True, text=True, encoding='utf-8')
assert r.returncode == 0, r.stderr[-2000:]
origin = work / 'origin.git'
g(work, 'clone', '-q', '--bare', str(build), str(origin))
url = str(origin)

# 1. A clean append passes the incremental check, and the full check agrees.
pub = work / 'pub'
res = AG.run(full, pub, url, D, None, incremental=True)
expect('clean append: appended and the incremental check passes', res['result'] == 'appended', json.dumps(res['check']))
old, new = res['old'], res['new']
full_chk = AG.check_main(full, pub, D)
expect('clean append: the full check passes too', not failed(full_chk), json.dumps({k: full_chk.get(k) for k in AG.FAIL_KEYS}))
expect('clean append: touched acts are the appended ones (constitution, statute), not code',
       res['check']['touched_acts'] == 2, f"touched {res['check']['touched_acts']}")
pub2 = work / 'pub2'
res2 = AG.run(full, pub2, url, D, None, incremental=False)
expect('the same append without --incremental gives the same head', res2.get('new') == new and res2['result'] == 'appended')
# "Publish" the append to the local bare origin (as autopush's push would), then run again: nothing to add.
g(pub, 'push', '-q', url, 'refs/heads/main:refs/heads/main', '--tags')
again = AG.run(full, pub, url, D, None, incremental=True)
expect('a second incremental run adds nothing', again['result'] == 'same', again.get('result'))
# AG.run() resets the clone to origin/main on every run; put the appended head back for the injections below.
g(pub, 'update-ref', 'refs/heads/main', new)


def check(c_folder: Path, head: str) -> dict:
    return AG.check_appended(c_folder, pub, D, old, head)


# 1b. A documentation-only append (one Lexifina commit, no trailers, as append_gate.docs_only() makes): passes.
docs = commit_on(pub, new, {'README.md': 'Testland law, updated.\n'}, 'Documentation update: tables\n',
                 author='Lexifina')
try:
    chk = AG.check_appended(full, pub, D, new, docs)
    expect('documentation-only append: passes', not failed(chk), json.dumps({k: chk.get(k) for k in AG.FAIL_KEYS}))
except Exception as e:
    expect('documentation-only append: passes', False, f'{type(e).__name__}: {e}')


# 2. A wrong unit, written into git: an appended act's newest version with one word changed.
trail = '\n\nIn-force: 2024-01-01\nLaw: Act 5\n'
bad = commit_on(pub, new, {'statute/s-2.md': 'New sectiom.\n'}, 'Act 5: statute s. 2' + trail)
chk = check(full, bad)
expect('wrong unit in an appended act (git side): fails', failed(chk) and chk['mismatches'] > 0, chk['details'][:2])
# ... and as a mismatch between what was appended and the corpus: each appended version altered in turn.
for slug, vi, key, text in (('statute', 0, 's-1', 'Statute!\n'), ('statute', 1, 's-2', 'New section?\n'),
                            ('constitution', 2, 'art-2', 'Two, again!\n'), ('constitution', 1, 'art-1', 'One.\n')):
    c = corpus(True)
    act = next(a for a in c['acts'] if a['slug'] == slug)
    act['versions'][vi]['units'][key] = u(key, text)
    chk = check(folder(f'wrong-{slug}-{vi}', c), new)
    expect(f'appended text differs from the corpus ({slug} version {act["versions"][vi]["from"]} {key}): fails',
           failed(chk) and chk['mismatches'] > 0, chk['details'][:1])

# 3. A backwards date: a correct-text commit dated before the commit it follows.
ct_new = int(g(pub, 'log', '-1', '--format=%ct', new))
back = commit_on(pub, new, {}, 'Act 5: statute (no change)' + trail, ct=ct_new - 86400)
chk = check(full, back)
expect('backwards committer date: fails', failed(chk) and chk['backwards'] == 1, chk['details'][-1:])
# ... and in the middle of the appended range (the docs commit after it is later again).
mid = commit_on(pub, old, {}, 'Act 5 (no change)' + trail, ct=int(g(pub, 'log', '-1', '--format=%ct', old)) - 60)
mid2 = commit_on(pub, mid, {}, 'Documentation', ct=ct_new)
chk = check(full, mid2)
expect('backwards date right after the published head: fails', failed(chk) and chk['backwards'] >= 1)

# 4. A future In-force day, and a committer date in the future.
fut = commit_on(pub, new, {}, 'Act 9 (no change)\n\nIn-force: 2030-01-01\nLaw: Act 9\n')
chk = check(full, fut)
expect('In-force after the data date: fails', failed(chk) and chk['future_dated'] >= 1)
fut2 = commit_on(pub, new, {}, 'Act 5 (no change)' + trail, ct=ct_new + 400 * 86400)
fut3 = commit_on(pub, fut2, {}, 'Documentation', ct=ct_new + 400 * 86400)
chk = check(full, fut3)
expect('law commit dated after now: fails', failed(chk) and chk['future_dated'] >= 1)

# 5. A missing trailer.
nt = commit_on(pub, new, {'statute/s-2.md': 'New section.\n'}, 'Act 5 without trailers\n')
chk = check(full, nt)
expect('law commit with no trailers: fails', failed(chk) and chk['trailer_errors'] == 1)

# 6. A version the append left out, in an act it did not touch (the whole-repo sanity check).
c = corpus(True)
code = next(a for a in c['acts'] if a['slug'] == 'code')
code['versions'].append({'from': '2022-01-01', 'units': {'s-1': u('S. 1', 'Code text, amended.\n')}})
chk = check(folder('left-out', c), new)
expect('a version of an untouched act left out: fails', failed(chk) and chk['mismatches'] > 0, chk['details'][:1])
c = corpus(True)
c['acts'].append({'slug': 'decree', 'short': 'Dec', 'title': 'Decree', 'first_law': 'act-1',
                  'versions': [{'from': '2001-01-01', 'units': {'a': u('A', 'Decree.\n')}}]})
chk = check(folder('left-out-act', c), new)
expect('a whole new act left out: fails', failed(chk) and chk['mismatches'] > 0)

# 7. A change to an act the append did not report: a law file of `code` edited in the appended range.
sneak = commit_on(pub, new, {'code/s-1.md': 'Code text, altered.\n'}, 'Act 5' + trail)
chk = check(full, sneak)
expect('a law file of an untouched act changed: fails', failed(chk) and chk['mismatches'] > 0)

# 8. Positive control for the hand-made commits below: the same three changes on their right days pass.
right = commit_on(pub, old, {'statute/s-1.md': 'Statute.\n'}, 'Act 4: statute\n\nIn-force: 2015-01-01\nLaw: Act 4\n')
right = commit_on(pub, right, {'statute/s-1.md': 'Statute, amended.\n', 'statute/s-2.md': 'New section.\n'},
                  'Act 5: statute' + trail)
right = commit_on(pub, right, {'constitution/art-2.md': 'Two, again.\n'},
                  'Act 3: constitution\n\nIn-force: 2020-01-01\nLaw: Act 3\n')
chk = check(full, right)
expect('hand-made correct append (positive control): passes', not failed(chk), chk['details'][:2])

# 9. A version committed on the wrong day (In-force a year early): caught by the day-before reading.
early = commit_on(pub, old, {'statute/s-1.md': 'Statute.\n'}, 'Act 4: statute\n\nIn-force: 2014-01-01\nLaw: Act 4\n')
early = commit_on(pub, early, {'statute/s-1.md': 'Statute, amended.\n', 'statute/s-2.md': 'New section.\n'},
                  'Act 5: statute' + trail)
early = commit_on(pub, early, {'constitution/art-2.md': 'Two, again.\n'},
                  'Act 3: constitution\n\nIn-force: 2020-01-01\nLaw: Act 3\n')
chk = check(full, early)
expect('a new act committed on the wrong day: fails, on the day before its first version',
       failed(chk) and any('before the first version' in d for d in chk['details']), chk['details'][:1])

bad_n = [n for n, ok in results if not ok]
print(f'\n{len(results) - len(bad_n)}/{len(results)} passed')
if bad_n:
    raise SystemExit('FAILED:\n- ' + '\n- '.join(bad_n))
print('ALL OK')
