"""Point global-law's submodules at each country repo's current tip, with one new commit per branch (no rewrite).

    python -X utf8 repoint_fast.py [--push]

global-law main gets each country's current main; global-law preview gets each country's current preview, or main
where the country has no preview. Lookups run in parallel (git ls-remote). A plain fast-forward push; prints a summary.
One clone is kept between passes, so each pass only fetches what changed.
"""
import os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if os.name == 'nt':  # run detached (no console), every console child (git, cmd, python) opens its own visible window
    import ctypes as _ctypes
    if not _ctypes.windll.kernel32.GetConsoleWindow():
        _popen_init = subprocess.Popen.__init__

        def _no_window(self, *args, creationflags=0, **kwargs):
            if not creationflags & 0x18:  # unless DETACHED_PROCESS or CREATE_NEW_CONSOLE was asked for on purpose
                creationflags |= 0x08000000  # CREATE_NO_WINDOW
            _popen_init(self, *args, creationflags=creationflags, **kwargs)

        subprocess.Popen.__init__ = _no_window

GL = 'https://github.com/lexifina/global-law.git'
GL_PREVIEW = 'https://github.com/lexifina/global-law-preview.git'   # preview's home from 2026-11-03
W = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'gl-repoint'


def git(cwd, *a, env=None, data=None):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace")[:300]}')
    return r.stdout.decode('utf-8', 'replace')


PUSHED_AT: dict = {}

# Checks added 2026-11-03 (global-law tools plan, via global-law-fundamentals):
HERE = Path(__file__).resolve().parent
HOLD_FILE = HERE / 'repoint-hold.txt'            # repo names (one per line, '#' comments): never added and never moved
PLACEMENT_FILE = HERE / 'repoint-placement.json'  # {"<repo>": "<path in global-law>"}: explicit path for new corpora
HELD_LOG = HERE / 'repoint-held.log'              # every pin move or push that a check refused
# Batching and gates (2026-11-04): the loop runs one pass every 15 min; repoint_gates.py checks each new commit first.
import repoint_gates  # noqa: E402
NO_GATES = '--no-gates' in sys.argv
GATES = {'checked': set(), 'passed': set(), 'held': {}, 'logged': set(), 'off': False}
HEARTBEAT = HERE / 'heartbeat.json'
ALERTS = HERE / 'alerts.log'
VERIFY_LOG = HERE / 'verify.log'


def held_log(msg):
    import time as _t
    with HELD_LOG.open('a', encoding='utf-8') as f:
        f.write(f"{_t.strftime('%Y-%m-%dT%H:%M:%SZ', _t.gmtime())} {msg}\n")


def hold_list():
    if not HOLD_FILE.exists():
        return set()
    return {l.split('#', 1)[0].strip() for l in HOLD_FILE.read_text(encoding='utf-8').splitlines()} - {''}


def placement():
    import json as _j
    try:
        return _j.loads(PLACEMENT_FILE.read_text(encoding='utf-8')) if PLACEMENT_FILE.exists() else {}
    except ValueError:
        held_log('repoint-placement.json is not valid JSON: ignored this pass')
        return {}


_FWD: dict = {}


def forward(tok, repo, old, new):
    """True when `new` is `old` or a descendant of it in lexifina/<repo> (GitHub compare API): pins only move forward.
    False (hold) when it is behind or diverged, or when the answer can't be had this pass."""
    if old == new:
        return True
    key = (repo, old, new)
    if key not in _FWD:
        import json as _j, urllib.request as _u
        try:
            req = _u.Request(f'https://api.github.com/repos/lexifina/{repo}/compare/{old}...{new}',
                             headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
            st = _j.load(_u.urlopen(req, timeout=60)).get('status')
            _FWD[key] = st in ('ahead', 'identical')
            if not _FWD[key]:
                held_log(f'{repo}: pin {old[:9]} -> {new[:9]} is {st}, not a fast-forward: held')
        except Exception as e:
            held_log(f'{repo}: could not check {old[:9]} -> {new[:9]} ({str(e)[:80]}): held this pass')
            return False
    return _FWD[key]


NAMES_F = W.parent / 'gl-repoint-names.json'


def org_law_repos():
    """Every lexifina/*-law repo name, from the GitHub API (the stored git credential; never printed).

    The API quota is shared with every session on this account. When it is spent (403/429), the last listing is
    reused and PUSHED_AT stays empty, so every known repo is checked with git ls-remote, which the quota does not
    cover: global-law keeps repinning while the API is down."""
    import json, urllib.request
    from speedwatch import token as _gh_token  # gh keyring first; git credential fill can hang on a hidden prompt
    tok = _gh_token()
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


# Audit row 1 (2026-11-04): global-law's tools/law.py reads a corpus's future branch beside main once its laws are
# due, from data/future-pins.tsv (corpus, branch, future_sha, main_pin). A row is read only while its main_pin is the
# corpus's gitlink, so the file is written again in the same root commit whenever gitlinks move.
FUTURE_PINS = 'data/future-pins.tsv'
FUTURE_SKIP = ('romania/', 'bulgaria/', 'serbia/', 'bosnia', 'albania/', 'north-macedonia/', 'montenegro/', 'kosovo/',
               'croatia/', 'slovenia/', 'greece/')  # held on another machine: no tags pushed to them from here


def future_pins_tsv(w, base, env):
    """data/future-pins.tsv for the gitlinks staged in `env`'s index, from global-law's own tools/future_pins.py at
    `base` (ls-remote + blob-less fetches into w/.git/global-law-cache/future-clones, kept between passes). None when
    the tool is not on main yet or fails (logged): the tree then keeps the old file, whose rows name the old pins, so
    law.py reads main alone, with a note, for the corpora whose pin moved. Never fatal to the pass."""
    try:
        src = git(w, 'show', f'{base}:tools/future_pins.py')
    except RuntimeError:
        return None
    tool = w / '.future-pins' / 'tools' / 'future_pins.py'  # inside the clone, so git finds it as the tree root
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_bytes(src.encode('utf-8'))
    pins_f, out_f = w / '.future-pins' / 'pins.tsv', w / '.future-pins' / 'future-pins.tsv'
    pins = []
    for line in git(w, 'ls-files', '-s', env=env).splitlines():
        meta, path = line.split('\t', 1)
        if meta.startswith('160000 '):
            pins.append(f'{path}\t{meta.split()[1]}\n')
    pins_f.write_bytes(''.join(pins).encode('utf-8'))
    out_f.unlink(missing_ok=True)
    try:
        r = subprocess.run([sys.executable, '-X', 'utf8', str(tool), '--pins', str(pins_f), '--tree-ref', base,
                            '--out', str(out_f), '--report', str(W.parent / 'gl-future-pins-report.json')],
                           cwd=w, capture_output=True, text=True, timeout=300,
                           env={**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'})
    except subprocess.TimeoutExpired:
        held_log('future-pins: tools/future_pins.py ran past 300 s; old data/future-pins.tsv kept this pass')
        return None
    if r.returncode or not out_f.exists():
        held_log(f'future-pins: tools/future_pins.py failed ({r.stderr.strip()[-200:]}); old file kept this pass')
        return None
    return out_f.read_bytes()


def protect_future_pins(w, base, tsv, path_url, held):
    """Tag each newly recorded future commit on its corpus repo (refs/tags/global-law/future-pinned-<sha>), so a
    rebuild that rewrites the branch cannot let it be collected. New tag refs only: never forced, never deleted."""
    try:
        before = git(w, 'show', f'{base}:{FUTURE_PINS}')
    except RuntimeError:
        before = ''
    old = {tuple(l.split('\t')[:3]) for l in before.splitlines() if l and not l.startswith('#')}
    cache = w / '.git' / 'global-law-cache' / 'future-clones'
    for line in tsv.decode('utf-8').splitlines():
        parts = line.split('\t')
        if line.startswith('#') or len(parts) != 4 or tuple(parts[:3]) in old or parts[0].startswith(FUTURE_SKIP):
            continue
        url = path_url.get(parts[0], '')
        if not url or url.rstrip('/').removesuffix('.git').rsplit('/', 1)[1] in held:
            continue
        repo, sha = cache / (parts[0].replace('/', '~') + '.git'), parts[2]
        r = subprocess.run(['git', '-C', str(repo), 'push', '-q', url, f'{sha}:refs/tags/global-law/future-pinned-{sha}'],
                           capture_output=True, text=True, timeout=120,
                           env={**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'})
        if r.returncode:
            held_log(f'future-pins: tag for {parts[0]} {sha[:10]} not pushed ({r.stderr.strip()[-160:]})')


def main(push):
    w = W
    if not (w / '.git').exists():
        git(None, 'clone', '-q', '--filter=blob:none', '--no-checkout', GL, str(w))
    git(w, 'fetch', '-q', '--filter=blob:none', 'origin', '+refs/heads/main:refs/remotes/origin/main')
    # preview moved out of global-law (Alan, 2026-11-03): it is lexifina/global-law-preview's main now. Until that repo
    # has a main, the preview build is skipped; global-law's own refs/heads/preview is never written again.
    have_preview = subprocess.run(['git', 'fetch', '-q', '--filter=blob:none', GL_PREVIEW,
                                   '+refs/heads/main:refs/remotes/pv/main'], cwd=w, capture_output=True).returncode == 0
    urls = {}
    for line in git(w, 'config', '--blob', 'origin/main:.gitmodules', '--get-regexp', r'submodule\..*\.(path|url)').splitlines():
        k, v = line.split(' ', 1)
        urls.setdefault(k.rsplit('.', 1)[0], {})[k.rsplit('.', 1)[1]] = v
    path_url = {m['path']: m['url'] for m in urls.values() if 'path' in m and 'url' in m}

    def heads(url):
        out = {}
        # No console here, so the credential manager must never prompt, and each lookup is bounded (2026-11-04:
        # unbounded ls-remotes under a window-less loop took minutes each and stalled the loop for 45 min).
        env = {**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'}
        try:
            r = subprocess.run(['git', 'ls-remote', url, 'refs/heads/main', 'refs/heads/preview'],
                               capture_output=True, text=True, timeout=45, env=env)
        except subprocess.TimeoutExpired:
            print(f'ls-remote timed out: {url}', flush=True)
            return url, out
        for line in r.stdout.splitlines():
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
    from speedwatch import token as _gh_token  # gh keyring first; git credential fill can hang on a hidden prompt
    tok = _gh_token()

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
    held = hold_list()
    new_subs = {k: v for k, v in new_subs.items() if v and k not in held}
    top = {l.split('\t', 1)[1] for l in git(w, 'ls-tree', 'origin/main').splitlines() if l.split()[1] == 'tree'}
    place = placement()
    repo_of = lambda url: url.rstrip('/').removesuffix('.git').rsplit('/', 1)[1]

    def declared_path(repo):
        """corpus standard v1: the repo's root corpus.json names its global-law folder in `path`."""
        import base64 as _b64
        try:
            req = urllib.request.Request(f'https://api.github.com/repos/lexifina/{repo}/contents/corpus.json',
                                         headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
            d = json.loads(_b64.b64decode(json.load(urllib.request.urlopen(req, timeout=60))['content']))
            p = (d.get('path') or '').strip().strip('/')
            if p and '..' not in p.split('/') and re.fullmatch(r'[a-z0-9][a-z0-9/-]*', p):
                return p
            if p:
                held_log(f'{repo}: corpus.json path {p!r} is not a plain folder path: ignored')
        except Exception:
            pass
        return None

    def sub_path(repo):
        if repo in place:  # explicit placement wins, then the repo's own corpus.json path, then the slug guess
            return place[repo]
        p = declared_path(repo)
        if p:
            return p
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
    # Phase 1 (2026-11-04 batching): every pin each branch would move, and every corpus it would add, before any gate.
    plans = {}
    for br in ('main', 'preview'):
        if br == 'preview' and not have_preview:
            continue
        base = git(w, 'rev-parse', 'origin/main' if br == 'main' else 'pv/main').strip()
        moves = []
        for line in git(w, 'ls-tree', '-r', base).splitlines():
            meta, path = line.split('\t', 1)
            if meta.split()[1] != 'commit':
                continue
            old = meta.split()[2]
            url = path_url.get(path, '')
            t = tips.get(url, {})
            new = t.get(br) or t.get('main')
            if new and new != old:
                repo = repo_of(url) if url else ''
                if repo in held or not forward(tok, repo, old, new):
                    continue  # held, or not a fast-forward of the current pin (logged in repoint-held.log)
                moves.append((path, old, new, repo, url))
        plans[br] = (base, moves)
    # Phase 2: the gates (repoint_gates.py: global-law's check_corpus.py and the stale-HEAD check) on each new commit,
    # in parallel and time-boxed. A corpus that fails is held for this pass only, with its reason in repoint-held.log.
    items = {}
    for br, (base, moves) in plans.items():
        for path, old, new, repo, url in moves:
            items.setdefault((repo, new, old), {'url': url, 'wip': br == 'preview' and new != tips.get(url, {}).get('main')})
        for path, (repo, sha) in new_paths.items():
            u = f'https://github.com/lexifina/{repo}.git'
            t = tips.get(u, {})
            new = t.get(br) or t.get('main') or sha
            items.setdefault((repo, new, None), {'url': u, 'wip': br == 'preview' and new != t.get('main')})
    verdict, gates_on = {}, bool(items) and not NO_GATES
    if gates_on:
        gate_base = plans.get('main', plans.get('preview'))[0]
        verdict = repoint_gates.gate(w, gate_base, items)
        if verdict is None:
            held_log('gates: tools/check_corpus.py is not on global-law main; pins moved without gates this pass')
            GATES['off'] = True
            verdict, gates_on = {}, False
        for (repo, new, old), (ok_, why) in sorted(verdict.items(), key=lambda kv: kv[0][0]):
            GATES['checked'].add((repo, new, old))
            if ok_:
                GATES['passed'].add((repo, new, old))
            else:
                GATES['held'][repo] = why
                if (repo, new, old) not in GATES['logged']:
                    GATES['logged'].add((repo, new, old))
                    held_log(f"gate: {repo} {(old or 'new')[:9]} -> {new[:9]}: {why}: held this pass")
    # with gates on, a pin with no verdict is held (never moved unchecked)
    gate_ok = lambda repo, new, old: (not gates_on) or (verdict.get((repo, new, old)) or (False, ''))[0]
    for br in ('main', 'preview'):
        if br not in plans:
            summary[br] = {'repointed': 0, 'added': 0, 'skipped': 'global-law-preview has no main yet'}
            continue
        base, moves = plans[br]
        env = {'GIT_INDEX_FILE': str(w / f'.idx-{br}')}
        git(w, 'read-tree', base, env=env)
        changed = gate_held = 0
        for path, old, new, repo, url in moves:
            if not gate_ok(repo, new, old):
                gate_held += 1
                continue
            git(w, 'update-index', '--cacheinfo', f'160000,{new},{path}', env=env)
            changed += 1
        # Repair: a .gitmodules entry whose gitlink is missing from the tree (left by an earlier race) gets its pin.
        linked = {l.split('\t', 1)[1] for l in git(w, 'ls-tree', '-r', base).splitlines() if l.split()[1] == 'commit'}
        # Only entries in this branch's own .gitmodules (path_url is main's): on 2026-11-04 main renamed three Swiss
        # city paths, and preview got gitlinks at the new paths beside its old entries (716 links, 713 entries: refused).
        own = set(re.findall(r'^\s*path = (.+?)\s*$', git(w, 'show', f'{base}:.gitmodules'), re.M))
        for path, url in path_url.items():
            if path in linked or path in new_paths or repo_of(url) in held or path not in own:
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
            if not gate_ok(repo, new, None):
                gate_held += 1
                continue
            gm +=f'[submodule "{path}"]\n\tpath = {path}\n\turl = https://github.com/lexifina/{repo}.git\n\tbranch = main\n'
            git(w, 'update-index', '--add', '--cacheinfo', f'160000,{new},{path}', env=env)
            added.append(path)
        if added:
            blob = git(w, 'hash-object', '-w', '--stdin', data=gm.encode()).strip()
            git(w, 'update-index', '--add', '--cacheinfo', f'100644,{blob},.gitmodules', env=env)
        summary[br] = {'repointed': changed, 'added': len(added)}
        if gate_held:
            summary[br]['gate_held'] = gate_held
        future_tsv = None
        if br == 'main' and (changed or added) and push:
            future_tsv = future_pins_tsv(w, base, env)
            if future_tsv is not None:
                blob = git(w, 'hash-object', '-w', '--stdin', data=future_tsv).strip()
                git(w, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{FUTURE_PINS}', env=env)
                summary[br]['future_pins'] = sum(1 for l in future_tsv.decode('utf-8').splitlines()
                                                 if l and not l.startswith('#'))
        if (changed or added) and push:
            tree = git(w, 'write-tree', env=env).strip()
            # every gitlink needs its .gitmodules entry and the reverse (3fa43f4 had 710 links and 705 entries)
            n_links = sum(1 for l in git(w, 'ls-tree', '-r', tree).splitlines() if l.split()[1] == 'commit')
            gm_now = git(w, 'cat-file', '-p', f'{tree}:.gitmodules')
            n_entries = sum(1 for l in gm_now.splitlines() if l.strip().startswith('path = '))
            if n_links != n_entries:
                held_log(f'{br}: push refused: {n_links} gitlinks but {n_entries} .gitmodules entries')
                summary[br]['pushed'] = f'REFUSED {n_links} gitlinks != {n_entries} .gitmodules entries'
                continue
            head = (f'Add {len(added)} corpora as submodules' + (f'; point {changed} at their current commits' if changed else '')
                    if added else f'Point submodules at the current country commits ({changed} corpora)')
            msg = (head + '\n\n' + ''.join(f'- {p}\n' for p in added) +
                   ('\n' if added else '') + 'Each submodule points at its repository\'s current tip.\n' +
                   (f'{FUTURE_PINS} records the future branches read beside these pins.\n' if future_tsv else '')).encode()
            c = git(w, '-c', 'user.name=Lexifina', '-c', 'user.email=global-law@lexifina.com', 'commit-tree', tree, '-p', base, data=msg).strip()
            dest = ['origin', f'{c}:refs/heads/main'] if br == 'main' else [GL_PREVIEW, f'{c}:refs/heads/main']
            r = subprocess.run(['git', 'push', '-q', *dest], cwd=w, capture_output=True, text=True)
            summary[br]['pushed'] = c[:9] if r.returncode == 0 else f'FAILED {r.stderr[-200:]}'
            if r.returncode == 0 and future_tsv:
                try:
                    protect_future_pins(w, base, future_tsv, path_url, held)
                except Exception as e:  # a tag never fails the pass; the reader falls back without the commit
                    held_log(f'future-pins: tags: {str(e)[:200]}')
    print(summary, flush=True)
    return summary


DESCRIBE = W.parent / 'gl-describe'   # sparse checkout: tools/, manifest.json and every jurisdiction.json


def describe_followup():
    """After a pass that added corpora: run global-law's tools/describe.py (manifest.json and jurisdiction.json from the
    tree) in a sparse checkout of main, and push its changes as one fast-forward follow-up commit (requested by
    global-law-fundamentals, 2026-11-03). Never forced; a race is retried from a fresh fetch."""
    d = DESCRIBE
    if not (d / '.git').exists():
        git(None, 'clone', '-q', '--filter=blob:none', '--no-checkout', GL, str(d))
        git(d, 'sparse-checkout', 'set', '--no-cone', '/tools/', '/manifest.json', 'jurisdiction.json')
    for attempt in range(3):
        git(d, 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main')
        git(d, 'checkout', '-q', '-B', 'main', 'origin/main')
        git(d, 'reset', '-q', '--hard', 'origin/main')  # this scratch checkout only ever mirrors origin/main
        if not (d / 'tools' / 'describe.py').exists():
            print('describe: tools/describe.py not on main; skipped', flush=True)
            return
        r = subprocess.run([sys.executable, '-X', 'utf8', 'tools/describe.py'], cwd=d, capture_output=True, text=True,
                           timeout=3600)
        if r.returncode != 0:
            held_log(f'describe.py failed ({r.stderr.strip()[-200:]}): no manifest commit this pass')
            return
        changed = git(d, 'status', '--porcelain').strip()
        if not changed:
            print('describe: manifest and jurisdiction files already current', flush=True)
            return
        git(d, 'add', '-A', '--', 'manifest.json', ':(glob)**/jurisdiction.json', 'jurisdiction.json')
        git(d, '-c', 'user.name=Lexifina', '-c', 'user.email=global-law@lexifina.com', 'commit', '-q', '-m',
            'Describe the corpora the tree pins (tools/describe.py)\n\nmanifest.json and jurisdiction.json rewritten '
            'from each corpus\'s own repository at its pinned commit, after new corpora were added.')
        p = subprocess.run(['git', 'push', '-q', 'origin', 'HEAD:refs/heads/main'], cwd=d, capture_output=True, text=True)
        if p.returncode == 0:
            print(f"describe: pushed {git(d, 'rev-parse', '--short', 'HEAD').strip()}", flush=True)
            return
        import time as _t
        _t.sleep(10 * (attempt + 1))
    held_log('describe follow-up: push failed 3 times (race); next pass that adds corpora retries')


if __name__ == '__main__' and '--describe' in sys.argv:
    sys.stdout.reconfigure(encoding='utf-8')
    _lock = HERE / 'describe.lock'
    try:
        _lock.write_text(str(os.getpid()))
        describe_followup()
    except Exception as e:  # never let the manifest step break anything else
        held_log(f'describe follow-up error: {str(e)[:200]}')
    finally:
        _lock.unlink(missing_ok=True)
    sys.exit(0)

def utc(t=None):
    import time as _t
    return _t.strftime('%Y-%m-%dT%H:%M:%SZ', _t.gmtime(t))


def alert(msg):
    with ALERTS.open('a', encoding='utf-8') as f:
        f.write(f'{utc()} {msg}\n')


def run_verify(commit):
    """global-law's tools/verify.py --remote --github-heads at the commit just pushed, in the loop's clone. verify.py
    keeps its own checkpoint (.git/global-law-verify/verified.json), so each run checks only the commits since the last
    clean one, and fetches only the corpora whose main moved. It must sit at the clone's root (its git calls read paths
    from there), so it is written to <gl-repoint>/tools/verify.py; the clone has no checkout, so nothing else is there.
    The clone's own refs/heads/main (HEAD) is moved to the pushed commit; the pass itself only reads origin/main."""
    import time as _t
    t0 = _t.time()
    w = W
    try:
        src = git(w, 'show', f'{commit}:tools/verify.py')
    except RuntimeError:
        return {'result': 'skipped', 'line': 'tools/verify.py not on main'}
    (w / 'tools').mkdir(exist_ok=True)
    (w / 'tools' / 'verify.py').write_bytes(src.encode('utf-8'))
    git(w, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    git(w, 'update-ref', 'refs/heads/main', commit)
    try:
        r = subprocess.run([sys.executable, '-X', 'utf8', str(w / 'tools' / 'verify.py'), '--remote', '--github-heads'],
                           cwd=w, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600,
                           env={**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'})
        out, rc = (r.stdout + r.stderr).strip(), r.returncode
    except subprocess.TimeoutExpired:
        out, rc = 'verify.py ran past 600 s', None
    lines = out.splitlines()
    with VERIFY_LOG.open('a', encoding='utf-8') as f:
        f.write(f'=== {utc()} {commit[:10]} exit {rc} [{_t.time() - t0:.0f} s]\n' + '\n'.join(lines[-30:]) + '\n')
    last = lines[-1] if lines else ''
    return {'result': 'ok' if rc == 0 else 'timeout' if rc is None else 'fail', 'commit': commit[:10],
            'line': last[:300], 'seconds': round(_t.time() - t0)}


def write_heartbeat(started, summary, verify, error=None):
    import json as _j, time as _t
    try:
        prev = _j.loads(HEARTBEAT.read_text(encoding='utf-8'))
    except Exception:
        prev = {}
    s = summary or {}
    m, p = s.get('main', {}), s.get('preview', {})
    pushed = [b for b, v in (('main', m), ('preview', p)) if v.get('pushed') and not
              str(v['pushed']).startswith(('FAILED', 'REFUSED'))]
    failed = [b for b, v in (('main', m), ('preview', p)) if str(v.get('pushed', '')).startswith(('FAILED', 'REFUSED'))]
    result = ('error' if error else 'push failed' if failed else 'pushed' if pushed
              else 'held only' if GATES['held'] else 'nothing to do')
    now = _t.time()
    hb = {'at': utc(now), 'started_at': utc(started), 'seconds': round(now - started), 'pid': os.getpid(),
          'result': result, 'error': error,
          'last_success_at': prev.get('last_success_at') if error else utc(now),
          'last_push_at': utc(now) if pushed else prev.get('last_push_at'),
          'counts': {'moved_main': m.get('repointed', 0), 'moved_preview': p.get('repointed', 0),
                     'added': m.get('added', 0), 'future_pins': m.get('future_pins'),
                     'gate_checked': len(GATES['checked']), 'gate_passed': len(GATES['passed']),
                     'gate_held': len(GATES['held']), 'hold_list': len(hold_list())},
          'gates': 'off' if (GATES['off'] or NO_GATES) else 'on',
          'gate_held': GATES['held'], 'summary': s,
          'verify': verify or prev.get('verify'), 'interval_min': 15}
    HEARTBEAT.write_text(_j.dumps(hb, indent=1) + '\n', encoding='utf-8')
    return hb


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import time as _time
    _started = _time.time()
    # The loop's `timeout` cannot stop a Windows python (2026-11-04: one pass ran 45+ min); exit by ourselves,
    # printing where we were stuck. A git push already started finishes on its own and is all-or-nothing.
    # 25 min since 2026-11-04: a 15-min batch now also runs the gates (<= 9 min), future pins (<= 5) and verify (<= 10).
    import faulthandler
    faulthandler.dump_traceback_later(1500, exit=True)
    try:
        summary = main('--push' in sys.argv)
    except Exception as _e:
        if '--push' in sys.argv:
            write_heartbeat(_started, None, None, error=f'{type(_e).__name__}: {str(_e)[:300]}')
        raise
    # Another writer (e.g. gitlaw-mcp's tools commits) pushed global-law between our fetch and push: refetch and redo
    # the pass once now instead of waiting a whole loop interval. Fast-forward only, as always.
    # Up to 3 more attempts with back-off, each from a fresh fetch, so a race never forces anything.
    import time as _time
    for attempt in range(3):
        if not ('--push' in sys.argv and any('FAILED' in str(v.get('pushed', '')) for v in (summary or {}).values())):
            break
        _time.sleep(10 * (attempt + 1))
        try:
            summary = main(True)
        except Exception as _e:
            write_heartbeat(_started, summary, None, error=f'{type(_e).__name__}: {str(_e)[:300]}')
            raise
    # manifest.json and jurisdiction.json follow new corpora (only main carries them; preview is not described)
    m = (summary or {}).get('main', {})
    if '--push' in sys.argv and m.get('added') and str(m.get('pushed', '')).strip() and 'FAILED' not in str(m.get('pushed')) \
            and 'REFUSED' not in str(m.get('pushed')):
        # describe.py reads all ~710 corpora and can take over 10 minutes: run it as its own windowless process (the
        # pass itself is capped at 600 s), one at a time (describe.lock), so it never delays or kills a pointer pass
        lock = HERE / 'describe.lock'
        stale = lock.exists() and _time.time() - lock.stat().st_mtime > 7200  # a killed run never blocks it for good
        if not lock.exists() or stale:
            subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--describe'], cwd=HERE,
                             creationflags=0x08000000 | 0x00004000,  # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
                             stdout=open(HERE / 'describe.log', 'a', encoding='utf-8'), stderr=subprocess.STDOUT)
    # After a push: verify.py on the pushed main (incremental from its own checkpoint), then the heartbeat. A failed
    # verify is written to alerts.log once per distinct problem line, not every pass.
    verify = None
    _pm = str(m.get('pushed', ''))
    if '--push' in sys.argv and _pm and not _pm.startswith(('FAILED', 'REFUSED')):
        import json as _json, re as _re
        try:
            _prev = _json.loads(HEARTBEAT.read_text(encoding='utf-8')).get('verify') or {}
        except Exception:
            _prev = {}
        try:
            verify = run_verify(git(W, 'rev-parse', _pm).strip())
        except Exception as e:
            verify = {'result': 'error', 'line': str(e)[:300]}
        _key = lambda v: _re.sub(r'\[[0-9.]+ s\]', '', (v or {}).get('line', '')).strip()
        if verify['result'] in ('fail', 'error') and not (_prev.get('result') == verify['result'] and _key(_prev) == _key(verify)):
            alert(f"global-law verify.py {verify['result']} at {verify.get('commit', '?')}: {verify['line'][:200]} (see verify.log)")
        elif verify['result'] == 'timeout' and _prev.get('result') == 'timeout':
            alert('global-law verify.py ran past 600 s twice in a row (see verify.log)')
        print(f"verify: {verify['result']} {verify.get('line', '')[:120]}", flush=True)
    if '--push' in sys.argv:
        hb = write_heartbeat(_started, summary, verify)
        # last line, which the loop keeps in repoint_loop.log: the summary as before, plus the gate and verify results
        print({**(summary or {}), 'gates': {'held': len(GATES['held']), 'passed': len(GATES['passed'])},
               'verify': (verify or {}).get('result', '-')}, flush=True)
