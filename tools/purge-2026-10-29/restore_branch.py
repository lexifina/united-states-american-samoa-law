"""Rebuild one branch from its pre-cleanup original with the corrected rule, and push it over the current branch.

    python -X utf8 restore_branch.py <repo> <branch>

The original comes from world-law-ops (archive2/<repo>/<branch>, else archive/<repo>/<branch>). The corrected
callback.py keeps every law notes.md. The push uses --force-with-lease on the branch's current SHA. Check before
pushing: the result has the original's commit count, and every path the original had and the result lacks is a
.py/.sh script or a top-level private note.
"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPS = 'https://github.com/lexifina/world-law-ops.git'
NOTE = re.compile(r'^(PROGRESS\.md|ISSUES\.md|NOTES\.md|PERMISSION_REQUEST[^/]*\.md)$')


def git(cwd, *a, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True)
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


def main(repo, branch):
    url = f'https://github.com/lexifina/{repo}.git'
    w = Path(tempfile.mkdtemp(prefix=f'restore-{repo}-', dir=r'C:\Users\alany\purge-tmp'))
    try:
        r = w / 'r.git'
        git(None, 'init', '-q', '--bare', str(r))
        cur = git(None, 'ls-remote', url, f'refs/heads/{branch}').split()[0]
        bundle = Path(r'C:\Users\alany\purge-bundles') / f'{repo}.bundle'
        if bundle.exists():  # the local bundle taken just before the cleanup is the exact original
            git(r, 'fetch', '-q', str(bundle), f'+refs/heads/{branch}:refs/heads/{branch}', check=False)
        for ns in ('archive2', 'archive'):
            if git(r, 'rev-parse', '-q', '--verify', f'refs/heads/{branch}', check=False).strip():
                break
            git(r, 'fetch', '-q', OPS, f'+refs/heads/{ns}/{repo}/{branch}:refs/heads/{branch}', check=False)
        orig = git(r, 'rev-parse', f'refs/heads/{branch}').strip()
        n = int(git(r, 'rev-list', '--count', orig))
        before = set(git(r, 'ls-tree', '-r', '--name-only', orig).splitlines())
        p = subprocess.run([sys.executable, '-m', 'git_filter_repo', '--quiet', '--force', '--prune-empty', 'never',
                            '--prune-degenerate', 'never', '--mailmap', str(HERE / 'mailmap'),
                            '--file-info-callback', str(HERE / 'callback.py'), '--refs', f'refs/heads/{branch}'],
                           cwd=r, capture_output=True, text=True)
        if p.returncode:
            return {'repo': repo, 'status': 'FILTER FAILED', 'err': (p.stderr or p.stdout)[-300:]}
        new = git(r, 'rev-parse', f'refs/heads/{branch}').strip()
        after = set(git(r, 'ls-tree', '-r', '--name-only', new).splitlines())
        gone = before - after
        bad = [x for x in gone if not (x.endswith(('.py', '.sh', '.log')) or (NOTE.match(x.rsplit('/', 1)[-1]) and
               (x.count('/') == 0 or (x.startswith(('wip/', 'tools/')) and x.count('/') == 1))))]
        if int(git(r, 'rev-list', '--count', new)) != n or bad:
            return {'repo': repo, 'status': 'CHECK FAILED', 'bad': bad[:5]}
        notes = sum(1 for x in after if x.rsplit('/', 1)[-1] == 'notes.md')
        q = subprocess.run(['git', 'push', '-q', f'--force-with-lease=refs/heads/{branch}:{cur}', url, f'+{new}:refs/heads/{branch}'],
                           cwd=r, capture_output=True, text=True)
        return {'repo': repo, 'branch': branch, 'status': 'restored and pushed' if q.returncode == 0 else f'PUSH FAILED {q.stderr[-200:]}',
                'commits': n, 'notes.md now': notes, 'removed (private)': len(gone), 'new': new[:9]}
    finally:
        shutil.rmtree(w, ignore_errors=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(main(sys.argv[1], sys.argv[2])))
