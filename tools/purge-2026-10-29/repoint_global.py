"""After the privacy rewrite, point global-law's submodules (main and preview) at the rewritten country commits.

    python -X utf8 repoint_global.py [--push]

For each gitlink in global-law's main and preview, the new commit id comes from, in order:
1. the saved filter-repo commit map (maps/<repo>.commit-map);
2. the same position in first-parent history: the archived branch in world-law-ops (archive/<repo>/<branch>) holding
   the old commit, against the rewritten branch now on the country repo (the rewrite keeps every commit, in order);
3. the old id itself, when the country repo still has it (unchanged law commits).
Then one new commit per branch updates the gitlinks: no history rewrite, a plain fast-forward push. The old ids stay
reachable in the archive. Prints what changed and anything it could not map.
"""
import subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GL = 'https://github.com/lexifina/global-law.git'
OPS = 'https://github.com/lexifina/world-law-ops.git'


def git(cwd, *a, check=True, data=None):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, input=data)
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


def main(push):
    w = Path(tempfile.mkdtemp(prefix='gl-'))
    git(None, 'clone', '-q', '--filter=blob:none', '--no-checkout', GL, str(w))
    git(w, 'remote', 'add', 'ops', OPS)
    modules = {}
    for line in git(w, 'config', '--blob', 'origin/main:.gitmodules', '--get-regexp', r'submodule\..*\.(path|url)').splitlines():
        k, v = line.split(' ', 1)
        modules.setdefault(k.rsplit('.', 1)[0], {})[k.rsplit('.', 1)[1]] = v
    path_repo = {m['path']: m['url'].rstrip('/').rsplit('/', 1)[1].removesuffix('.git') for m in modules.values() if 'path' in m and 'url' in m}
    cache = {}

    def first_parent(remote, ref):
        key = (remote, ref)
        if key not in cache:
            if git(w, 'fetch', '-q', '--filter=blob:none', remote, f'+{ref}:refs/x/{abs(hash(key))}', check=False) == '' and \
                    git(w, 'rev-parse', '-q', '--verify', f'refs/x/{abs(hash(key))}', check=False):
                cache[key] = git(w, 'rev-list', '--first-parent', '--reverse', f'refs/x/{abs(hash(key))}').split()
            else:
                cache[key] = []
        return cache[key]

    def new_id(repo, old):
        cm = HERE / 'maps' / f'{repo}.commit-map'
        if cm.exists():
            for line in cm.read_text().splitlines():
                a, _, b = line.partition(' ')
                if a == old:
                    return b
        url = f'https://github.com/lexifina/{repo}.git'
        heads = [l.split('\t')[1] for l in git(None, 'ls-remote', '--heads', url).splitlines()]
        for ref in heads:
            br = ref.split('/', 2)[2]
            olds = first_parent('ops', f'refs/heads/archive/{repo}/{br}')
            if old in olds:
                news = first_parent(url, ref)
                if len(news) == len(olds):
                    return news[olds.index(old)]
        if any(l.startswith(old) for l in git(None, 'ls-remote', url).splitlines()):
            return old
        return None

    report = {}
    for br in ('main', 'preview'):
        base = git(w, 'rev-parse', f'origin/{br}').strip()
        links = [(l.split('\t')[1], l.split()[2]) for l in git(w, 'ls-tree', '-r', base).splitlines() if l.split()[1] == 'commit']
        env_index = w / f'.idx-{br}'
        env = {'GIT_INDEX_FILE': str(env_index)}
        subprocess.run(['git', 'read-tree', base], cwd=w, env={**__import__('os').environ, **env}, check=True)
        changed, unmapped = 0, []
        for path, old in links:
            repo = path_repo.get(path)
            nid = new_id(repo, old) if repo else None
            if not nid:
                unmapped.append(f'{path} {old[:9]}')
                continue
            if nid != old:
                subprocess.run(['git', 'update-index', '--cacheinfo', f'160000,{nid},{path}'], cwd=w,
                               env={**__import__('os').environ, **env}, check=True)
                changed += 1
        report[br] = {'gitlinks': len(links), 'repointed': changed, 'unmapped': unmapped[:10], 'unmapped_count': len(unmapped)}
        if changed and push:
            tree = subprocess.run(['git', 'write-tree'], cwd=w, env={**__import__('os').environ, **env}, capture_output=True, text=True, check=True).stdout.strip()
            msg = (f'Point submodules at the rewritten country commits ({changed} corpora)\n\n'
                   'The country repositories were rewritten on 2026-10-29 to move private files out of their history;\n'
                   'every law commit kept its id. The old commit ids are kept in a private archive.\n').encode()
            c = git(w, '-c', 'user.name=Lexifina', '-c', 'user.email=global-law@lexifina.com', 'commit-tree', tree, '-p', base, data=msg).strip()
            r = subprocess.run(['git', 'push', '-q', 'origin', f'{c}:refs/heads/{br}'], cwd=w, capture_output=True, text=True)
            report[br]['pushed'] = c[:9] if r.returncode == 0 else f'FAILED {r.stderr[-200:]}'
    print(report)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main('--push' in sys.argv)
