"""Point global-law's submodules at each country repo's current tip, with one new commit per branch (no rewrite).

    python -X utf8 repoint_fast.py [--push]

global-law main gets each country's current main; global-law preview gets each country's current preview, or main
where the country has no preview. Lookups run in parallel (git ls-remote). A plain fast-forward push; prints a summary.
One clone is kept between passes, so each pass only fetches what changed.
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GL = 'https://github.com/lexifina/global-law.git'
W = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'gl-repoint'


def git(cwd, *a, env=None, data=None):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


PUSHED_AT: dict = {}


NAMES_F = W.parent / 'gl-repoint-names.json'


def org_law_repos():
    """Every lexifina/*-law repo name, from the GitHub API (the stored git credential; never printed).

    The API quota is shared with every session on this account. When it is spent (403/429), the last listing is
    reused and PUSHED_AT stays empty, so every known repo is checked with git ls-remote, which the quota does not
    cover: global-law keeps repinning while the API is down."""
    import json, urllib.request
    tok = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                         capture_output=True, text=True).stdout
    tok = next((l.split('=', 1)[1] for l in tok.splitlines() if l.startswith('password=')), '')
    names, page, pushed = [], 1, {}
    try:
        while True:
            req = urllib.request.Request(f'https://api.github.com/orgs/lexifina/repos?per_page=100&page={page}&type=all',
                                         headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
            batch = json.load(urllib.request.urlopen(req, timeout=60))
            if not batch:
                break
            names += [r['name'] for r in batch]
            pushed.update({r['name']: r['pushed_at'] for r in batch})
            page += 1
    except Exception as e:
        print(f'api listing failed ({e}); using the cached listing and ls-remote', flush=True)
        try:
            return json.loads(NAMES_F.read_text(encoding='utf-8'))
        except Exception:
            return []
    PUSHED_AT.update(pushed)
    law = [n for n in names if n.endswith('-law')]
    NAMES_F.write_text(json.dumps(law), encoding='utf-8')
    return law


def main(push):
    w = W
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
        for line in subprocess.run(['git', 'ls-remote', url, 'refs/heads/main', 'refs/heads/preview'],
                                   capture_output=True, text=True).stdout.splitlines():
            sha, ref = line.split('\t')
            out[ref.rsplit('/', 1)[1]] = sha
        return url, out

    # New corpora: every lexifina/<slug>-law repo whose main holds real content but is not yet a submodule.
    have_urls = {u.rstrip('/').removesuffix('.git').rsplit('/', 1)[1] for u in path_url.values()}
    new_subs = {}
    for repo in org_law_repos():
        if repo in have_urls or repo == 'global-law':
            continue
        new_subs[repo] = None
    def real_tip(repo):
        url = f'https://github.com/lexifina/{repo}.git'
        ref = f'refs/probe/{repo}'
        r = subprocess.run(['git', 'fetch', '-q', '--depth', '1', '--filter=blob:none', url, f'+refs/heads/main:{ref}'],
                           cwd=w, capture_output=True, text=True)
        if r.returncode:
            return repo, None
        subj = subprocess.run(['git', 'log', '-1', '--format=%s', ref], cwd=w, capture_output=True, text=True).stdout.strip()
        sha = subprocess.run(['git', 'rev-parse', ref], cwd=w, capture_output=True, text=True).stdout.strip()
        if subj.endswith('before any law') or subj.startswith('Paused, not yet law') or 'not yet law' in subj:
            return repo, None
        return repo, sha
    # The GitHub API gives each main's tip and subject in one call per repo, in parallel (no git fetch needed).
    import json, urllib.request
    tok = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                         capture_output=True, text=True).stdout
    tok = next((l.split('=', 1)[1] for l in tok.splitlines() if l.startswith('password=')), '')

    def api_tip(repo):
        try:
            req = urllib.request.Request(f'https://api.github.com/repos/lexifina/{repo}/commits/main',
                                         headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
            d = json.load(urllib.request.urlopen(req, timeout=60))
            subj = d['commit']['message'].split('\n', 1)[0]
            if subj.endswith('before any law') or 'not yet law' in subj:
                return repo, None
            return repo, d['sha']
        except Exception:
            return repo, 'ERR'
    # Repos that are not yet submodules (mostly scaffolds) are asked again only when GitHub says they were pushed,
    # so idle scaffolds cost no API calls; with the API down (no PUSHED_AT) nothing new is added that pass.
    import json as _j
    probe_f = W.parent / 'gl-repoint-probes.json'
    try:
        probes = _j.loads(probe_f.read_text(encoding='utf-8'))
    except Exception:
        probes = {}
    # A "no law yet" answer is asked again every 30 minutes: the API can briefly serve the old scaffold tip right
    # after a push, and pushed_at may not move again, so one stale answer must not hide a repo for good.
    import time as _t
    now = _t.time()
    ask = [r for r in sorted(new_subs) if PUSHED_AT.get(r) and (
        probes.get(r, {}).get('pushed_at') != PUSHED_AT.get(r)
        or (not probes.get(r, {}).get('sha') and now - probes.get(r, {}).get('at', 0) > 1800))]
    with ThreadPoolExecutor(16) as ex:
        for repo, sha in ex.map(api_tip, ask):
            if sha != 'ERR':  # a failed call is asked again next pass
                probes[repo] = {'pushed_at': PUSHED_AT.get(repo), 'sha': sha, 'at': now}
    probe_f.write_text(_j.dumps(probes), encoding='utf-8')
    for repo in new_subs:
        if PUSHED_AT.get(repo) and probes.get(repo, {}).get('pushed_at') == PUSHED_AT.get(repo):
            new_subs[repo] = probes[repo]['sha']
    new_subs = {k: v for k, v in new_subs.items() if v}
    top = {l.split('\t', 1)[1] for l in git(w, 'ls-tree', 'origin/main').splitlines() if l.split()[1] == 'tree'}

    def sub_path(repo):
        slug = repo.removesuffix('-law')
        for country in sorted(top, key=len, reverse=True):
            if slug.startswith(country + '-'):
                return f'{country}/{slug[len(country) + 1:]}/acts'
        return f'{slug}/national/acts'
    new_paths = {sub_path(r): (r, sha) for r, sha in new_subs.items()}
    for path, (repo, _) in new_paths.items():
        path_url[path] = f'https://github.com/lexifina/{repo}.git'

    # Only ask git about repos GitHub says were pushed since the last pass (one API listing instead of ~200 ls-remotes).
    import json as _json
    cache_f = W.parent / 'gl-repoint-tips.json'
    try:
        cache = _json.loads(cache_f.read_text(encoding='utf-8'))
    except Exception:
        cache = {}
    pushed = PUSHED_AT
    urls_all = sorted(set(path_url.values()))
    stale = [u for u in urls_all if u not in cache or cache[u].get('pushed_at') != pushed.get(u.rstrip('/').removesuffix('.git').rsplit('/', 1)[1])]
    with ThreadPoolExecutor(16) as ex:
        for u, h in ex.map(heads, stale):
            cache[u] = {'tips': h, 'pushed_at': pushed.get(u.rstrip('/').removesuffix('.git').rsplit('/', 1)[1])}
    cache_f.write_text(_json.dumps(cache), encoding='utf-8')
    tips = {u: cache[u]['tips'] for u in urls_all}
    summary = {}
    for br in ('main', 'preview'):
        base = git(w, 'rev-parse', f'origin/{br}').strip()
        env = {'GIT_INDEX_FILE': str(w / f'.idx-{br}')}
        git(w, 'read-tree', base, env=env)
        changed = 0
        for line in git(w, 'ls-tree', '-r', base).splitlines():
            meta, path = line.split('\t', 1)
            if meta.split()[1] != 'commit':
                continue
            old = meta.split()[2]
            t = tips.get(path_url.get(path, ''), {})
            new = t.get(br) or t.get('main')
            if new and new != old:
                git(w, 'update-index', '--cacheinfo', f'160000,{new},{path}', env=env)
                changed += 1
        # Repair: a .gitmodules entry whose gitlink is missing from the tree (left by an earlier race) gets its pin.
        linked = {l.split('\t', 1)[1] for l in git(w, 'ls-tree', '-r', base).splitlines() if l.split()[1] == 'commit'}
        for path, url in path_url.items():
            if path in linked or path in new_paths:
                continue
            t = tips.get(url, {})
            new = t.get(br) or t.get('main')
            if new:
                git(w, 'update-index', '--add', '--cacheinfo', f'160000,{new},{path}', env=env)
                changed += 1
        added = []
        gm = git(w, 'show', f'{base}:.gitmodules')
        for path, (repo, sha) in sorted(new_paths.items()):
            if f'path = {path}\n' in gm:
                continue
            t = tips.get(f'https://github.com/lexifina/{repo}.git', {})
            new = t.get(br) or t.get('main') or sha
            gm += f'[submodule "{path}"]\n\tpath = {path}\n\turl = https://github.com/lexifina/{repo}.git\n\tbranch = main\n'
            git(w, 'update-index', '--add', '--cacheinfo', f'160000,{new},{path}', env=env)
            added.append(path)
        if added:
            blob = git(w, 'hash-object', '-w', '--stdin', data=gm.encode()).strip()
            git(w, 'update-index', '--add', '--cacheinfo', f'100644,{blob},.gitmodules', env=env)
        summary[br] = {'repointed': changed, 'added': len(added)}
        if (changed or added) and push:
            tree = git(w, 'write-tree', env=env).strip()
            head = (f'Add {len(added)} corpora as submodules' + (f'; point {changed} at their current commits' if changed else '')
                    if added else f'Point submodules at the current country commits ({changed} corpora)')
            msg = (head + '\n\n' + ''.join(f'- {p}\n' for p in added) +
                   ('\n' if added else '') + 'Each submodule points at its repository\'s current tip.\n').encode()
            c = git(w, '-c', 'user.name=Lexifina', '-c', 'user.email=global-law@lexifina.com', 'commit-tree', tree, '-p', base, data=msg).strip()
            r = subprocess.run(['git', 'push', '-q', 'origin', f'{c}:refs/heads/{br}'], cwd=w, capture_output=True, text=True)
            summary[br]['pushed'] = c[:9] if r.returncode == 0 else f'FAILED {r.stderr[-200:]}'
    print(summary, flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main('--push' in sys.argv)
