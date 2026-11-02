"""Find law files the 2026-10-29 cleanup removed by mistake (read-only).

For every repo the cleanup touched, compare each branch's pre-cleanup tip (world-law-ops archive2/<repo>/<branch> if
present, else archive/<repo>/<branch>, else the local bundle) with the branch now on GitHub. A removed path counts as
LOST unless the corrected rule would remove it too: a .py/.sh script, or a top-level PROGRESS/ISSUES/NOTES/
PERMISSION_REQUEST note. Trees only (blob:none), so it is fast. Writes lost.json.
"""
import json, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPS = 'https://github.com/lexifina/world-law-ops.git'
NOTE = re.compile(r'^(PROGRESS\.md|ISSUES\.md|NOTES\.md|PERMISSION_REQUEST[^/]*\.md)$')
BUNDLES = Path(r'C:\Users\alany\purge-bundles')


def git(cwd, *a):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True).stdout.decode('utf-8', 'replace')


def files(r, ref):
    return set(git(r, 'ls-tree', '-r', '--name-only', ref).splitlines())


def intended(path):
    base = path.rsplit('/', 1)[-1]
    top = path.count('/') == 0 or (path.startswith(('wip/', 'tools/')) and path.count('/') == 1)
    return base.endswith(('.py', '.sh')) or (top and NOTE.match(base)) or base.endswith('.log')


def one(repo):
    w = Path(tempfile.mkdtemp(prefix=f'lost-{repo}-'))
    try:
        if subprocess.run(['git', 'clone', '-q', '--bare', '--filter=blob:none', f'https://github.com/lexifina/{repo}.git', str(w)], capture_output=True).returncode:
            return {'repo': repo, 'error': 'clone failed'}
        heads = git(w, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').split()
        git(w, 'fetch', '-q', '--filter=blob:none', OPS, f'+refs/heads/archive/{repo}/*:refs/a1/*', f'+refs/heads/archive2/{repo}/*:refs/a2/*')
        b = BUNDLES / f'{repo}.bundle'
        if b.exists():
            git(w, 'fetch', '-q', str(b), '+refs/heads/*:refs/bu/*')
        out = {}
        for h in heads:
            orig = None
            for ns in ('bu', 'a2', 'a1'):
                if git(w, 'rev-parse', '-q', '--verify', f'refs/{ns}/{h}').strip():
                    orig = f'refs/{ns}/{h}'
                    break
            if not orig:
                continue
            gone = sorted(files(w, orig) - files(w, h))
            lost = [p for p in gone if not intended(p)]
            if lost:
                out[h] = {'lost': len(lost), 'from': orig, 'e.g.': lost[:5],
                          'kinds': sorted({p.rsplit('/', 1)[-1] for p in lost})[:8]}
        return {'repo': repo, 'branches_with_loss': out}
    finally:
        shutil.rmtree(w, ignore_errors=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    repos = set()
    for f in ('results.jsonl', 'results2.jsonl'):
        for line in open(HERE / f, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('status') == 'pushed and verified':
                repos.add(r['repo'].strip())
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(one, sorted(repos)))
    (HERE / 'lost.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    hit = [r for r in res if r.get('branches_with_loss')]
    print('repos checked', len(res), '| with lost law files', len(hit), '| errors', sum(1 for r in res if r.get('error')))
    for r in hit:
        print(' ', r['repo'], {h: (v['lost'], v['kinds'][:4]) for h, v in r['branches_with_loss'].items()})
