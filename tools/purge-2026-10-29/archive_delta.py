"""Archive whatever a repo's current branches and tags hold that world-law-ops does not yet have, without ever
overwriting an existing archive ref: a ref absent from the archive goes to archive/<repo>/<ref>; a ref whose archived
SHA differs (the repo moved on after it was archived) goes to archive2/<repo>/<ref>, so both states are kept.

    python -X utf8 archive_delta.py <tmpdir> <repo> [<repo> ...]
"""
import json, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OPS = 'https://github.com/lexifina/world-law-ops.git'
TMP = Path(sys.argv[1])


def git(cwd, *a, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.strip()[:300]}')
    return r.stdout


def ls(url):
    out = {}
    for line in git(None, 'ls-remote', url).splitlines():
        sha, ref = line.split('\t')
        if ref.startswith(('refs/heads/', 'refs/tags/')) and not ref.endswith('^{}'):
            out[ref] = sha
    return out


def name_for(ref, repo, ns):
    kind, short = ref.split('/', 2)[1], ref.split('/', 2)[2]
    return f'refs/{kind}/{ns}/{repo}/{short}'


def one(repo):
    url = f'https://github.com/lexifina/{repo}.git'
    cur, ops = ls(url), ls(OPS)
    todo = {}
    for ref, sha in cur.items():
        a = name_for(ref, repo, 'archive')
        if ops.get(a) == sha or ops.get(name_for(ref, repo, 'archive2')) == sha:
            continue
        todo[ref] = a if a not in ops else name_for(ref, repo, 'archive2')
    if not todo:
        return {'repo': repo, 'status': 'complete'}
    m = TMP / f'{repo}-{int(time.time() * 1000)}'
    git(None, 'clone', '-q', '--mirror', url, str(m))
    git(m, 'remote', 'add', 'ops', OPS)
    try:
        def push(*specs):
            err = ''
            for attempt in range(6):
                r = subprocess.run(['git', 'push', '-q', 'ops', *specs], cwd=m, capture_output=True, text=True)
                if r.returncode == 0:
                    return
                err = r.stderr.strip()[:300]
                time.sleep(15 * (attempt + 1))
            raise RuntimeError(err)
        for ref, dst in todo.items():
            if ref.startswith('refs/heads/'):
                commits = git(m, 'rev-list', '--first-parent', '--reverse', ref).split()
                for sha in commits[299::300]:
                    push(f'{sha}:{dst}')
                push(f'{ref}:{dst}')
        tags = [(r, d) for r, d in todo.items() if r.startswith('refs/tags/')]
        for i in range(0, len(tags), 60):
            push(*[f'{r}:{d}' for r, d in tags[i:i + 60]])
        ops = ls(OPS)
        missing = [r for r, d in todo.items() if ops.get(d) != cur[r]]
        return {'repo': repo, 'archived_now': len(todo), 'status': 'complete' if not missing else f'MISSING {len(missing)}'}
    finally:
        shutil.rmtree(m, ignore_errors=True)


def safe(repo):
    try:
        return one(repo)
    except Exception as e:
        return {'repo': repo, 'status': 'ERROR', 'error': str(e)[:300]}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    TMP.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(3) as ex:
        for r in ex.map(safe, sys.argv[2:]):
            print(json.dumps(r), flush=True)
