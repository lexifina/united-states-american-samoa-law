"""Archive EVERY branch and tag of every lexifina/<slug>-law repo (and global-law) into the private repo
lexifina/world-law-ops before any history rewrite, so nothing is ever discarded.
  refs/heads/<b> -> refs/heads/archive/<repo>/<b>     refs/tags/<t> -> refs/tags/archive/<repo>/<t>
Each repo is mirror-cloned into a temporary folder (never touching the push loop's working clones), pushed in steps of
300 first-parent commits per branch and 300 tags per batch (so GitHub's secret scan finishes), verified against
`git ls-remote` of world-law-ops (every SHA must match), then the temporary mirror is deleted. Resumable: a repo
whose archive refs already all match is skipped. Log: archive_all.log; result: archive_all.json."""
import json, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
OPS = 'https://github.com/lexifina/world-law-ops.git'
DOCS = Path(r'C:\Users\alany\Documents'); OUT = Path(sys.argv[1]); TMP = Path(sys.argv[2])
sys.stdout.reconfigure(encoding='utf-8')
def git(cwd, *a, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode: raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.strip()[:300]}')
    return r.stdout
def remote_refs(url):
    out = {}
    for l in git(None, 'ls-remote', url).splitlines():
        sha, ref = l.split('\t')
        if ref.startswith(('refs/heads/', 'refs/tags/')) and not ref.endswith('^{}'): out[ref] = sha
    return out
_ops_cache = {'t': 0, 'refs': {}}
def ops_refs(force=False):
    if force or time.time() - _ops_cache['t'] > 60:
        _ops_cache.update(t=time.time(), refs=remote_refs(OPS))
    return _ops_cache['refs']
def arch(ref, name):
    kind, short = ref.split('/', 2)[1], ref.split('/', 2)[2]
    return f'refs/{kind}/archive/{name}/{short}'
def one(name):
    url = f'https://github.com/lexifina/{name}.git'
    src = remote_refs(url)
    want = {arch(r, name): s for r, s in src.items()}
    have = ops_refs()
    if want and all(have.get(k) == v for k, v in want.items()):
        return {'repo': name, 'refs': len(want), 'status': 'already archived'}
    m = TMP / f'{name}-{int(time.time()*1000)}'
    shutil.rmtree(m, ignore_errors=True)
    git(None, 'clone', '-q', '--mirror', url, str(m))
    git(m, 'remote', 'add', 'ops', OPS)
    def push(*specs):
        for attempt in range(6):
            r = subprocess.run(['git', 'push', '-q', '-f', 'ops', *specs], cwd=m, capture_output=True, text=True)
            if r.returncode == 0: return
            time.sleep(15 * (attempt + 1))
        raise RuntimeError(r.stderr.strip()[:300])
    for ref in [r for r in src if r.startswith('refs/heads/')]:
        commits = git(m, 'rev-list', '--first-parent', '--reverse', ref).split()
        for sha in commits[299::300]:
            push(f'{sha}:{arch(ref, name)}')
        push(f'+{ref}:{arch(ref, name)}')
    tags = [r for r in src if r.startswith('refs/tags/')]
    for i in range(0, len(tags), 60):
        push(*[f'+{t}:{arch(t, name)}' for t in tags[i:i + 60]])
    have = ops_refs(force=True)
    missing = [k for k, v in want.items() if have.get(k) != v]
    shutil.rmtree(m, ignore_errors=True)
    return {'repo': name, 'refs': len(want), 'branches': sum(1 for r in src if r.startswith('refs/heads/')),
            'tags': len(tags), 'status': 'archived' if not missing else f'MISSING {len(missing)}', 'missing': missing[:5]}
names = sys.argv[3:]
results = []
with ThreadPoolExecutor(2) as ex:
    def safe(n):
        try: return one(n)
        except Exception as e: return {'repo': n, 'status': 'ERROR', 'error': str(e)[:300]}
    for r in ex.map(safe, names):
        results.append(r); print(json.dumps(r), flush=True)
        OUT.write_text(json.dumps(results, indent=1), encoding='utf-8')
print('DONE', sum(1 for r in results if r['status'] in ('archived', 'already archived')), 'of', len(results))
