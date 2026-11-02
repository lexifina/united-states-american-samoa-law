"""Add country repos to global-law as submodules: one fast-forward commit per branch (main, preview). No rewrite.

    python -X utf8 add_submodules.py [--push]

Paths follow global-law's convention (<country>/national/acts, <country>/<state>/acts), reusing the path preview
already gives a repo. Each new submodule is pinned to the repo's current main tip on global-law main, and to its
preview tip (else main) on global-law preview. Repos already in a branch's .gitmodules are left alone.
"""
import os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GL = 'https://github.com/lexifina/global-law.git'
MISSING = ['andorra-law', 'australia-australian-capital-territory-law', 'australia-northern-territory-law',
           'australia-south-australia-law', 'australia-tasmania-law', 'australia-western-australia-law', 'belgium-law',
           'belize-law', 'bermuda-law', 'cabo-verde-law', 'canada-newfoundland-and-labrador-law', 'canada-ontario-law',
           'costa-rica-law', 'faroe-islands-law', 'kosovo-law', 'mauritius-law', 'mozambique-law', 'nauru-law',
           'oman-law', 'pakistan-law', 'palestine-law', 'philippines-law', 'qatar-law', 'republic-of-congo-law',
           'russia-law', 'san-marino-law', 'sao-tome-and-principe-law', 'south-korea-law', 'sri-lanka-law', 'tonga-law',
           'trinidad-and-tobago-law', 'turkmenistan-law', 'tuvalu-law', 'united-states-guam-law',
           'united-states-northern-mariana-islands-law', 'vietnam-law']
SUBNATIONAL = {'canada-ontario-law': 'canada/ontario/acts'}


def git(cwd, *a, env=None, data=None):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


def modules(w, ref):
    out = {}
    try:
        text = git(w, 'config', '--blob', f'{ref}:.gitmodules', '--get-regexp', r'submodule\..*\.(path|url)')
    except RuntimeError:
        return out
    tmp = {}
    for line in text.splitlines():
        k, v = line.split(' ', 1)
        tmp.setdefault(k.rsplit('.', 1)[0], {})[k.rsplit('.', 1)[1]] = v
    for m in tmp.values():
        if 'url' in m and 'path' in m:
            out[m['url'].rstrip('/').rsplit('/', 1)[1].removesuffix('.git')] = m['path']
    return out


def main(push):
    w = Path(tempfile.mkdtemp(prefix='gladd-'))
    git(None, 'clone', '-q', '--filter=blob:none', '--no-checkout', GL, str(w))
    prev = modules(w, 'origin/preview')

    def tips(repo):
        out = {}
        for line in subprocess.run(['git', 'ls-remote', f'https://github.com/lexifina/{repo}.git', 'refs/heads/main', 'refs/heads/preview'],
                                   capture_output=True, text=True).stdout.splitlines():
            sha, ref = line.split('\t')
            out[ref.rsplit('/', 1)[1]] = sha
        return repo, out

    with ThreadPoolExecutor(16) as ex:
        tip = dict(ex.map(tips, MISSING))
    report = {}
    for br in ('main', 'preview'):
        base = git(w, 'rev-parse', f'origin/{br}').strip()
        have = modules(w, f'origin/{br}')
        gm = git(w, 'show', f'{base}:.gitmodules')
        env = {'GIT_INDEX_FILE': str(w / f'.idx-{br}')}
        git(w, 'read-tree', base, env=env)
        added, skipped = [], []
        for repo in MISSING:
            if repo in have:
                continue
            t = tip.get(repo, {})
            sha = (t.get('preview') or t.get('main')) if br == 'preview' else t.get('main')
            if not sha:
                skipped.append(repo)
                continue
            path = prev.get(repo) or SUBNATIONAL.get(repo) or f'{repo.removesuffix("-law")}/national/acts'
            gm += (f'[submodule "{path}"]\n\tpath = {path}\n\turl = https://github.com/lexifina/{repo}.git\n'
                   f'\tbranch = main\n')
            git(w, 'update-index', '--add', '--cacheinfo', f'160000,{sha},{path}', env=env)
            added.append(path)
        report[br] = {'added': len(added), 'skipped (no tip)': skipped}
        if added and push:
            blob = git(w, 'hash-object', '-w', '--stdin', data=gm.encode()).strip()
            git(w, 'update-index', '--add', '--cacheinfo', f'100644,{blob},.gitmodules', env=env)
            tree = git(w, 'write-tree', env=env).strip()
            msg = (f'Add {len(added)} corpora as submodules\n\n' + '\n'.join(f'- {p}' for p in sorted(added)) +
                   '\n\nEach is pinned to its repository\'s current tip. Their laws join the in-force-ordered root\n'
                   'history at the next full global-law build.\n').encode()
            c = git(w, '-c', 'user.name=Lexifina', '-c', 'user.email=global-law@lexifina.com', 'commit-tree', tree, '-p', base, data=msg).strip()
            r = subprocess.run(['git', 'push', '-q', 'origin', f'{c}:refs/heads/{br}'], cwd=w, capture_output=True, text=True)
            report[br]['pushed'] = c[:9] if r.returncode == 0 else f'FAILED {r.stderr[-200:]}'
    print(report)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main('--push' in sys.argv)
