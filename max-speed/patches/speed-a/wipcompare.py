"""Runs autopush's wip() as it is and as patched, on a live country folder (read only) into a scratch repo, with the
network calls stubbed and dry_run=True. Prints each one's time and the tree it wrote: they must be equal.
python wipcompare.py <orig.py> <fast.py> <country folder> <scratch repo>"""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r'C:\Users\alany\Documents\lexifina\scripts\gitlaw_common')
orig, fast, folder, repo = sys.argv[1:5]
folder, repo = Path(folder), Path(repo)
if not (repo / '.git').exists():
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    subprocess.run(['git', 'remote', 'add', 'ops', 'https://invalid.invalid/none.git'], cwd=repo, check=True)
res = {}
for label, path in (('orig', orig), ('fast', fast)):
    spec = importlib.util.spec_from_file_location(f'ap_{label}', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    real = m.git
    trees = []

    def stub(r, *args, _real=real, _trees=trees, **kw):
        if args[0] == 'fetch':
            return ''
        if args[0] == 'rev-parse' and 'refs/remotes/ops/wip' in args:
            return ''
        out = _real(r, *args, **kw)
        if args[0] == 'write-tree':
            _trees.append(out)
        return out
    m.git = stub
    t = time.perf_counter()
    msg = m.wip(folder.name[:-4], folder, repo, dry_run=True)
    res[label] = (round(time.perf_counter() - t, 2), trees[-1], msg)
print({'folder': folder.name, **{k: v[:2] for k, v in res.items()}, 'same_tree': res['orig'][1] == res['fast'][1],
       'msg': res['fast'][2]})
