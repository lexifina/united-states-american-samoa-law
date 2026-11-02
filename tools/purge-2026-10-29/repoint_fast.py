"""Point global-law's submodules at each country repo's current tip, with one new commit per branch (no rewrite).

    python -X utf8 repoint_fast.py [--push]

global-law main gets each country's current main; global-law preview gets each country's current preview, or main
where the country has no preview. Lookups run in parallel (git ls-remote). A plain fast-forward push; prints a summary.
"""
import os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GL = 'https://github.com/lexifina/global-law.git'


def git(cwd, *a, env=None, data=None):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


def main(push):
    w = Path(r'C:\Users\alany\gl-repoint')  # one clone kept between passes; each pass only fetches what changed
    if not (w / '.git').exists():
        git(None, 'clone', '-q', '--filter=blob:none', '--no-checkout', GL, str(w))
    git(w, 'fetch', '-q', '--filter=blob:none', 'origin', '+refs/heads/main:refs/remotes/origin/main',
        '+refs/heads/preview:refs/remotes/origin/preview')
    urls = {}
    for line in git(w, 'config', '--blob', 'origin/main:.gitmodules', '--get-regexp', r'submodule\..*\.(path|url)').splitlines():
        k, v = line.split(' ', 1)
        urls.setdefault(k.rsplit('.', 1)[0], {})[k.rsplit('.', 1)[1]] = v
    path_url = {m['path']: m['url'] for m in urls.values() if 'path' in m and 'url' in m}

    def heads(url):
        out = {}
        for line in subprocess.run(['git', 'ls-remote', url, 'refs/heads/main', 'refs/heads/preview'], capture_output=True, text=True).stdout.splitlines():
            sha, ref = line.split('\t')
            out[ref.rsplit('/', 1)[1]] = sha
        return url, out

    with ThreadPoolExecutor(32) as ex:
        tips = dict(ex.map(heads, sorted(set(path_url.values()))))
    summary = {}
    for br in ('main', 'preview'):
        base = git(w, 'rev-parse', f'origin/{br}').strip()
        env = {'GIT_INDEX_FILE': str(w / f'.idx-{br}')}
        git(w, 'read-tree', base, env=env)
        changed, missing = 0, []
        for line in git(w, 'ls-tree', '-r', base).splitlines():
            meta, path = line.split('\t', 1)
            if meta.split()[1] != 'commit':
                continue
            old = meta.split()[2]
            t = tips.get(path_url.get(path, ''), {})
            new = t.get(br) or t.get('main')
            if not new:
                missing.append(path)
                continue
            if new != old:
                git(w, 'update-index', '--cacheinfo', f'160000,{new},{path}', env=env)
                changed += 1
        summary[br] = {'repointed': changed, 'no tip found': missing[:8], 'missing_count': len(missing)}
        if changed and push:
            tree = git(w, 'write-tree', env=env).strip()
            msg = (f'Point submodules at the current country commits ({changed} corpora)\n\n'
                   'The country repositories were cleaned on 2026-10-29 (private build files moved out of their history);\n'
                   'law commits kept their ids. This points each submodule at its repository\'s current tip.\n').encode()
            c = git(w, '-c', 'user.name=Lexifina', '-c', 'user.email=global-law@lexifina.com', 'commit-tree', tree, '-p', base, data=msg).strip()
            r = subprocess.run(['git', 'push', '-q', 'origin', f'{c}:refs/heads/{br}'], cwd=w, capture_output=True, text=True)
            summary[br]['pushed'] = c[:9] if r.returncode == 0 else f'FAILED {r.stderr[-200:]}'
    print(summary)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main('--push' in sys.argv)
