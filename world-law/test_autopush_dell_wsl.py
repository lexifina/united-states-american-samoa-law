"""autopush_dell's WSL ext4 path, end to end on scratch repos (never GitHub).

    python -X utf8 scripts/world-law/test_autopush_dell_wsl.py

- which repos run in WSL, and that a moved repo never builds on NTFS again;
- the pre-push identity check (`git log <pushed> --not --remotes=origin --format='%ae %ce'`);
- a first publish and an incremental publish of a real corpus (brazil-araucaria-city parts) through the WSL child, to a
  bare origin on ext4: fast-forward only, check.py clean on what was published, only lexifina.com identities, the WSL
  toolchain in REPRODUCE.md, and no home path in any pushed blob.
Needs `python scripts/gitlaw_common/wsl_run.py setup` done once on this machine.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autopush_dell as ap  # noqa: E402

SRC = ap.ROOT / 'scripts' / 'brazil-araucaria-city-law'
SLUG = 'brazil-araucaria-city'
FAIL = []
TMP = Path(tempfile.mkdtemp(prefix='ap-wsl-test-'))
WSL_SCRATCH = f'{ap.WSL_BASE}/.scratch/test-{os.getpid()}'  # under the WSL home
os.environ['GITLAW_AUTOPUSH_SCRATCH'] = str(TMP / 'side')
ap.PENDING, ap.APPROVED = TMP / 'side' / 'REWRITE-PENDING.json', TMP / 'side' / 'REWRITE-APPROVED.txt'
ap.WSL_REPOS, ap.WSL_MIGRATED = TMP / 'WSL-REPOS.txt', TMP / 'WSL-MIGRATED.txt'
(TMP / 'side' / 'fake' / 'logs').mkdir(parents=True)


def ok(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra else ''), flush=True)
    if not cond:
        FAIL.append(name)


def g(repo, *a, env=None):
    return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, encoding='utf-8',
                          env={**os.environ, **(env or {})}).stdout.strip()


def wsl(script: str) -> subprocess.CompletedProcess:
    """A bash script in WSL (home as cwd), under nice; its stdout."""
    return subprocess.run(['wsl.exe', '-d', ap.WSL_DISTRO, '--cd', '~', '--exec', '/usr/bin/nice', '-n', '10',
                           '/bin/bash', '-c', script], capture_output=True, text=True, encoding='utf-8')


# 1. selection and the never-back rule -------------------------------------------------------------------------------
ok('not selected by default', not ap.wsl_selected('x', {}))
ap.WSL_REPOS.write_text('# comment\ny  # note\n', encoding='utf-8')
ok('selected by name', ap.wsl_selected('y', {}) and not ap.wsl_selected('x', {}))
ap.WSL_REPOS.write_text('*\n', encoding='utf-8')
ok('selected by *', ap.wsl_selected('x', {}))
ap.WSL_REPOS.write_text('', encoding='utf-8')
st = {}
ap._mark_migrated('z', st)
ok('marked in state and registry', st.get('wsl') and 'z' in ap._slug_list(ap.WSL_MIGRATED))
ok('moved repo stays in WSL though deselected', ap.wsl_selected('z', {}) and ap.wsl_selected('q', {'wsl': {'since': 1}}))
r = ap.main_build('z', TMP, TMP, {}, dry_run=False)
ok('main_build refuses a moved repo on NTFS', r['main'].startswith('NOT built'), r['main'])
r = ap.main_build('q', TMP, TMP, {'wsl': {'since': 1}}, dry_run=False)
ok('main_build refuses a repo marked only in its state', r['main'].startswith('NOT built'), r['main'])
try:
    ap.one('z', dry_run=False, where='ntfs')
    ok('where= refused outside scratch dry runs', False)
except ValueError:
    ok('where= refused outside scratch dry runs', True)

# 2. the identity check before every push -----------------------------------------------------------------------------
idr = TMP / 'id'
idr.mkdir()
lex = {'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': 'x-law@lexifina.com', 'GIT_COMMITTER_NAME': 'Lexifina',
       'GIT_COMMITTER_EMAIL': 'x-law@lexifina.com'}
g(idr, 'init', '-q', '-b', 'main')
g(idr, 'commit', '-q', '--allow-empty', '-m', 'base', env=lex)
g(idr, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
g(idr, 'commit', '-q', '--allow-empty', '-m', 'law', env={**lex, 'GIT_AUTHOR_EMAIL': 'x@law.invalid'})
ok('identity check: lexifina.com and .invalid pass', ap.push_identities(idr, ['refs/heads/main']) == '')
personal = sorted(ap.private._personal_emails())
g(idr, 'commit', '-q', '--allow-empty', '-m', 'bad', env={**lex, 'GIT_COMMITTER_EMAIL': 'someone@example.org'})
bad = ap.push_identities(idr, ['refs/heads/main'])
ok('identity check: an outside address is refused', 'someone@example.org' in bad, bad)
if personal:
    g(idr, 'reset', '-q', '--hard', 'HEAD~1')
    g(idr, 'commit', '-q', '--allow-empty', '-m', 'mine', env={**lex, 'GIT_AUTHOR_EMAIL': personal[0]})
    bad = ap.push_identities(idr, ['refs/heads/main'])
    ok('identity check: the personal address is refused and not printed', bad and personal[0] not in bad, bad)
ok('identity check: commits already on origin are not re-checked',
   ap.push_identities(idr, ['refs/remotes/origin/main']) == '')

# 3. end to end through the WSL child ---------------------------------------------------------------------------------
F = TMP / f'{SLUG}-law'


def folder(parts):
    if F.exists():
        shutil.rmtree(F)
    (F / 'corpus.d').mkdir(parents=True)
    shutil.copytree(SRC / 'repo', F / 'repo')
    (F / 'PUBLISH').write_text('test\n', encoding='utf-8')
    for n in parts:
        for ext in ('.json', '.PUBLISH'):
            shutil.copy(SRC / 'corpus.d' / f'30-leis-{n}{ext}', F / 'corpus.d' / f'30-leis-{n}{ext}')


folder(['002', '003', '004'])
repo = f'~/{WSL_SCRATCH}/{SLUG}-law'
origin = f'$HOME/{WSL_SCRATCH}/origin.git'
p = wsl(f'set -e; rm -rf "$HOME/{WSL_SCRATCH}"; mkdir -p "$HOME/{WSL_SCRATCH}"; '
        f'git init -q --bare -b main "{origin}"; git init -q -b main "$HOME/{WSL_SCRATCH}/{SLUG}-law"; '
        f'git -C "$HOME/{WSL_SCRATCH}/{SLUG}-law" remote add origin "{origin}"; echo ok')
ok('scratch repos made in WSL', p.stdout.strip() == 'ok', p.stderr[-300:])
state: dict = {}
r1 = ap.main_build_wsl(SLUG, F, state, repo=repo)
ok('first publish through WSL: pushed', str(r1.get('main', '')).startswith('pushed'), json.dumps(r1)[:300])
ok('state marked as moved', bool(state.get('wsl')) and SLUG in ap._slug_list(ap.WSL_MIGRATED))
ok('incremental base recorded', bool(state.get('inc')))
head1 = wsl(f'git -C "{origin}" rev-parse main').stdout.strip()

folder(['001', '002', '003', '004'])
r2 = ap.main_build_wsl(SLUG, F, state, repo=repo)
ok('second publish through WSL: pushed', str(r2.get('main', '')).startswith('pushed'), json.dumps(r2)[:300])
ok('second publish was incremental', '(incremental)' in str(r2.get('main', '')), str(r2.get('main'))[:200])
head2 = wsl(f'git -C "{origin}" rev-parse main').stdout.strip()
ok('fast-forward on the origin', head1 != head2 and wsl(
    f'git -C "{origin}" merge-base --is-ancestor {head1} {head2} && echo ff').stdout.strip() == 'ff')
ids = wsl(f'git -C "{origin}" log --all --format="%ae %ce"').stdout.split()
ok('only lexifina.com / .invalid identities on the origin', ids and all(
    e.endswith(('lexifina.com', '.invalid')) for e in ids), sorted(set(ids))[:6])
ok('no personal address on the origin', not any(e.lower() in personal for e in ids))
repro = wsl(f'git -C "{origin}" show main:REPRODUCE.md').stdout
tool = next((l for l in repro.splitlines() if 'git version' in l), '')
ok('REPRODUCE.md names the WSL toolchain', tool and 'windows' not in tool.lower(), tool)
leak = wsl(f'git -C "{origin}" grep -I -n -i -E "/home/alany|/mnt/c/Users|Users/alany" main -- . | head -3').stdout
ok('no home path in the published tree', not leak.strip(), leak[:200])
chk = wsl(f'set -e; d=$(mktemp -d); git clone -q --no-checkout "{origin}" "$d/c"; '
          f'PYTHONTZPATH= GITLAW_VERIFIED_PARTS_ONLY=1 "$HOME/{ap.WSL_VENV_PY}" -X utf8 '
          f'{ap._to_wsl(ap.COMMON / "check.py")} "$d/c" --corpus {ap._to_wsl(F / "corpus.json")} >/dev/null '
          f'&& echo clean; rm -rf "$d"')
ok('check.py clean on what was published', chk.stdout.strip() == 'clean', chk.stderr[-300:])
r3 = ap.main_build_wsl(SLUG, F, state, repo=repo)
ok('third visit, nothing new: nothing pushed', 'nothing to push' in str(r3.get('main')) or 'unchanged' in str(
    r3.get('main')), str(r3.get('main'))[:200])
ok('origin unchanged by the third visit', wsl(f'git -C "{origin}" rev-parse main').stdout.strip() == head2)

wsl(f'rm -rf "$HOME/{WSL_SCRATCH}"')
shutil.rmtree(TMP, ignore_errors=True)
print(f'{"FAILED: " + ", ".join(FAIL) if FAIL else "all passed"}')
sys.exit(1 if FAIL else 0)
