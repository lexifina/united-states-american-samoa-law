"""One-shot push for what the coordinator's pass skips.
  rtl:     autopush.one(slug) for the 8 held right-to-left/CJK countries -> wip + preview only (none has PUBLISH).
  blocked: folders whose remote wip holds another session's commit -> snapshot pushed to a NEW branch wip-local.
"""
import datetime as dt, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(r'C:\Users\alany\Documents\lexifina'); DOCS = ROOT.parent
sys.path.insert(0, str(ROOT / 'scripts' / 'south-america-law'))
import autopush as ap
sys.stdout.reconfigure(encoding='utf-8')
RTL = ['oman', 'qatar', 'yemen', 'syria', 'sudan', 'united-arab-emirates', 'palestine', 'south-korea']

def snapshot_tree(folder, repo):
    with tempfile.TemporaryDirectory() as tmp:
        env = {'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        for p in sorted(folder.rglob('*')):
            rel = p.relative_to(folder)
            if (not p.is_file() or set(rel.parts) & ap.SKIP_DIRS or any(x.startswith('.tmp') or x == '.git' for x in rel.parts[:-1])
                    or p.name.startswith('.autopush') or p.name == 'BUILD_STATUS.json' or p.stat().st_size > ap.MAX_FILE):
                continue
            sha = ap.git(repo, 'hash-object', '-w', '--', str(p))
            ap.git(repo, 'update-index', '--add', '--cacheinfo', f'100644,{sha},wip/{rel.as_posix()}', env=env)
        return ap.git(repo, 'write-tree', env=env)

def blocked(slug):
    folder = ROOT / 'scripts' / f'{slug}-law'; repo = DOCS / f'{slug}-law'
    if not (repo / '.git').exists():
        return None
    ap.git(repo, 'fetch', '-q', 'origin', '+refs/heads/wip:refs/remotes/origin/wip', check=False)
    parent = ap.git(repo, 'rev-parse', '-q', '--verify', 'refs/remotes/origin/wip', check=False)
    if not parent:
        return None
    email, _, subj = ap.git(repo, 'log', '-1', '--format=%ae%x1f%s', parent, check=False).partition('\x1f')
    ours = email == 'world-law@lexifina.com' or subj.startswith(('Work in progress', 'wip')) or \
        ap.git(repo, 'cat-file', '-t', f'{parent}:wip', check=False) == 'tree'
    if ours:
        return None
    tree = snapshot_tree(folder, repo)
    ap.git(repo, 'fetch', '-q', 'origin', '+refs/heads/wip-local:refs/remotes/origin/wip-local', check=False)
    lp = ap.git(repo, 'rev-parse', '-q', '--verify', 'refs/remotes/origin/wip-local', check=False)
    if lp and ap.git(repo, 'rev-parse', f'{lp}^{{tree}}') == tree:
        return f'{slug:24} wip-local unchanged (remote wip is {email}: {subj[:50]})'
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    msg = (f'Work in progress: scripts/{slug}-law at {now} (local copy; the wip branch holds another session\'s '
           f'commit, so this goes to wip-local)\n').encode()
    c = ap.git(repo, 'commit-tree', tree, *(['-p', lp] if lp else []),
               env={**ap.WIP_AUTHOR, 'GIT_AUTHOR_DATE': now, 'GIT_COMMITTER_DATE': now}, data=msg)
    r = ap.push(repo, f'{c}:refs/heads/wip-local')
    return f'{slug:24} wip-local {r} {c[:7]} (remote wip is {email}: {subj[:50]})'

mode = sys.argv[1]
if mode == 'rtl':
    with ThreadPoolExecutor(2) as ex:
        for line in ex.map(ap.one, RTL):
            print(line, flush=True)
else:
    found = sorted(p.name[:-4] for p in (ROOT / 'scripts').glob('*-law') if p.is_dir() and p.name[:-4] not in ap.FOREIGN
                   and ((p / 'corpus.json').exists() or (p / 'corpus.d').is_dir() or (p / 'PROGRESS.md').exists()))
    with ThreadPoolExecutor(4) as ex:
        for line in ex.map(blocked, found):
            if line:
                print(line, flush=True)
