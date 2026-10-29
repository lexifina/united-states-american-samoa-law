"""autopush wip(): the tree it writes, per file (2 git processes a file, as now) vs batched (2 processes in all).
python wipbench.py <country folder> <scratch git repo>; prints both times and whether the trees agree.
Mirrors wip()'s file selection, without the privacy scrub (a scrubbed file goes through --stdin in both)."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKIP_DIRS = {'.cache', '__pycache__', '.tmp-build', '.tmp', 'tmp'}
MAX_FILE = 50 * 1024 * 1024
folder, repo = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
if not (repo / '.git').exists():
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)


def git(*a, env=None, data=None):
    return subprocess.run(['git', *a], cwd=repo, capture_output=True, input=data,
                          env={**os.environ, **(env or {})}, check=True).stdout.decode().strip()


t = time.perf_counter()
files = []
for p in sorted(folder.rglob('*')):
    rel = p.relative_to(folder)
    if (not p.is_file() or set(rel.parts) & SKIP_DIRS or any(x.startswith('.tmp') or x == '.git' for x in rel.parts[:-1])
            or p.name.startswith('.autopush') or p.name == 'BUILD_STATUS.json' or p.stat().st_size > MAX_FILE):
        continue
    files.append((rel.as_posix(), p))
t_list = time.perf_counter() - t

t = time.perf_counter()
with tempfile.TemporaryDirectory() as tmp:
    env = {'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
    for rel, p in files:
        sha = git('hash-object', '-w', '--', str(p))
        git('update-index', '--add', '--cacheinfo', f'100644,{sha},wip/{rel}', env=env)
    tree_a = git('write-tree', env=env)
t_a = time.perf_counter() - t

t = time.perf_counter()
with tempfile.TemporaryDirectory() as tmp:
    env = {'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
    shas = git('hash-object', '-w', '--stdin-paths', data=''.join(f'{p}\n' for _, p in files).encode()).split()
    info = ''.join(f'100644 {s}\twip/{rel}\n' for s, (rel, _) in zip(shas, files))
    git('update-index', '--add', '--index-info', env=env, data=info.encode())
    tree_b = git('write-tree', env=env)
t_b = time.perf_counter() - t
print({'folder': folder.name, 'files': len(files), 'list_s': round(t_list, 2), 'per_file_s': round(t_a, 2),
       'batched_s': round(t_b, 2), 'same_tree': tree_a == tree_b})
