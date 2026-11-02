"""For every scripts/<slug>-law folder the push loop handles, compare the local files (as autopush.wip() selects them)
with the tree on the remote wip branch. Read-only: fetches into each existing clone's remote-tracking ref only."""
import hashlib, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(r'C:\Users\alany\Documents\lexifina'); DOCS = ROOT.parent
sys.path.insert(0, str(ROOT / 'scripts' / 'south-america-law'))
import autopush as ap
sys.stdout.reconfigure(encoding='utf-8')

def local_files(folder):
    out = {}
    for p in sorted(folder.rglob('*')):
        rel = p.relative_to(folder)
        if (not p.is_file() or set(rel.parts) & ap.SKIP_DIRS or any(x.startswith('.tmp') or x == '.git' for x in rel.parts[:-1])
                or p.name.startswith('.autopush') or p.name == 'BUILD_STATUS.json' or p.stat().st_size > ap.MAX_FILE):
            continue
        b = p.read_bytes()
        out['wip/' + rel.as_posix()] = (hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest(), p.stat().st_mtime)
    return out

def git(repo, *a):
    r = subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    return r.returncode, r.stdout

def one(slug):
    folder = ROOT / 'scripts' / f'{slug}-law'; repo = DOCS / f'{slug}-law'
    loc = local_files(folder)
    if not (repo / '.git').exists():
        rc, _ = git(DOCS, 'clone', '-q', '--no-checkout', f'https://github.com/lexifina/{slug}-law.git', str(repo))
    rc, _ = git(repo, 'fetch', '-q', 'origin', '+refs/heads/wip:refs/remotes/origin/wip')
    if rc:
        return slug, 'NO REMOTE WIP', len(loc), len(loc), 0, ''
    _, who = git(repo, 'log', '-1', '--format=%ae | %s | %cI', 'refs/remotes/origin/wip')
    _, ls = git(repo, 'ls-tree', '-r', 'refs/remotes/origin/wip')
    rem = {}
    for line in ls.splitlines():
        meta, path = line.split('\t', 1); rem[path] = meta.split()[2]
    newer = [k for k, (h, _) in loc.items() if rem.get(k) != h]
    missing = [k for k in newer if k not in rem]
    return slug, who.strip(), len(loc), len(newer), len(missing), ', '.join(sorted(x[4:] for x in newer)[:6])

found = sorted(p.name[:-4] for p in (ROOT / 'scripts').glob('*-law') if p.is_dir() and p.name[:-4] not in ap.FOREIGN
               and ((p / 'corpus.json').exists() or (p / 'corpus.d').is_dir() or (p / 'PROGRESS.md').exists()))
with ThreadPoolExecutor(10) as ex:
    rows = list(ex.map(one, found))
behind = [r for r in rows if r[3]]
print(f'{len(found)} country folders checked; {len(behind)} have local files not on remote wip\n')
for s, who, n, d, m, ex_ in sorted(behind, key=lambda r: -r[3]):
    print(f'{s:28} {d:4}/{n:<5} differ ({m} new) | remote wip: {who[:90]}\n{"":30}e.g. {ex_[:150]}')

print('\n--- content check, ignoring paths (for wips another session wrote) ---')
for slug in ['vatican-city','san-marino','trinidad-and-tobago','qatar','bangladesh','belize','dominican-republic','bhutan','andorra','costa-rica','denmark','finland','ireland']:
    folder = ROOT/'scripts'/f'{slug}-law'; repo = DOCS/f'{slug}-law'
    loc = local_files(folder)
    _, ls = git(repo, 'ls-tree', '-r', 'refs/remotes/origin/wip')
    blobs = {l.split('\t')[0].split()[2] for l in ls.splitlines()}
    paths = [l.split('\t',1)[1] for l in ls.splitlines()]
    absent = sorted(k[4:] for k,(h,_) in loc.items() if h not in blobs)
    print(f'{slug:22} {len(absent)}/{len(loc)} local files not on remote wip anywhere: {", ".join(absent)[:120]}  [remote layout: {paths[0] if paths else "-"}]')
