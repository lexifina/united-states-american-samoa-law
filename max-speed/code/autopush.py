"""Keeps every South American law repository current, so country agents never wait on a push.

    python -X utf8 scripts/south-america-law/autopush.py            # one pass over all 12 countries, in parallel
    python -X utf8 scripts/south-america-law/autopush.py --loop 180 # a pass every 180 seconds

    python -X utf8 scripts/south-america-law/autopush.py --only uruguay --dry-run   # build and audit, push nothing

For each country, in parallel:
1. wip: snapshots scripts/<slug>-law (no .cache, temporary builds or files over 50 MB) onto the branch
   wip/<slug>-law of the PRIVATE lexifina/world-law-ops, without touching the clone's checkout (a private index and
   plumbing), and pushes it if it changed. The country repos are public: nothing unfinished goes there.
2. main: when corpus.json changed since the last pass, rebuilds the clone with scripts/gitlaw_common/build.py, runs
   check.py, and if the check is clean publishes main, the future branch and the tags through publish(): plain pushes
   only, a rewrite only with the user's recorded approval, and a privacy audit of everything added (see publish()).
The result of each pass is written to scripts/<slug>-law/BUILD_STATUS.json, which the country agent reads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT.parent
COMMON = ROOT / 'scripts' / 'gitlaw_common'
sys.path.insert(0, str(COMMON))
from build import load  # noqa: E402
import private  # noqa: E402  (what stays off shared repos)
SOUTH_AMERICA = ['chile', 'uruguay', 'brazil', 'colombia', 'argentina', 'peru', 'paraguay', 'ecuador', 'bolivia',
                 'venezuela', 'guyana', 'suriname']
# Africa, English-language first (Laws.Africa Peachjam LIIs and South Africa). A country is picked up as soon as its
# folder scripts/<slug>-law exists.
AFRICA = ['kenya', 'uganda', 'zambia', 'malawi', 'zimbabwe', 'namibia', 'lesotho', 'sierra-leone', 'ghana', 'tanzania',
          'eswatini', 'seychelles', 'south-africa', 'botswana', 'mauritius', 'nigeria', 'gambia', 'liberia', 'rwanda',
          'south-sudan',
          # French- and Portuguese-language Africa (left-to-right scripts; no Arabic yet)
          'senegal', 'cote-divoire', 'cameroon', 'madagascar', 'benin', 'togo', 'burkina-faso', 'mali', 'guinea',
          'gabon', 'republic-of-congo', 'dr-congo', 'burundi', 'djibouti', 'chad', 'comoros', 'mozambique', 'angola',
          'cabo-verde']
COUNTRIES = SOUTH_AMERICA + AFRICA
# Folders under scripts/ that other sessions' builders own (their own build.py, their own repos): never touched.
FOREIGN = {'estonia', 'liechtenstein', 'luxembourg', 'malta', 'swiss', 'germany', 'grundgesetz', 'bundesrecht',
           'uk', 'global', 'world', 'south-america', 'africa'}
# Out of scope for now (user: no right-to-left or CJK scripts): held off every branch until the user decides.
FOREIGN |= {'oman', 'qatar', 'yemen', 'syria', 'sudan', 'united-arab-emirates', 'palestine', 'south-korea'}
# Built and published by gitlaw-scraper-dell from alan-dell (2026-10-29): the folders here are stale copies.
FOREIGN |= {'australia', 'australia-northern-territory', 'australia-tasmania', 'australia-south-australia',
            'australia-australian-capital-territory', 'australia-western-australia', 'hong-kong', 'ireland', 'denmark',
            'finland', 'canada-newfoundland-and-labrador', 'canada-northwest-territories', 'kosovo', 'pakistan',
            'faroe-islands', 'belize', 'united-states-guam', 'united-states-northern-mariana-islands', 'san-marino',
            'trinidad-and-tobago', 'andorra', 'bangladesh'}
# Other sessions' own builders (global-law-main-composer and earlier): never touched from here.
FOREIGN |= {'costa-rica', 'spain', 'czechia', 'france', 'russia', 'austria', 'italy', 'portugal', 'poland',
            'cook-islands'}
SKIP_DIRS = {'.cache', '__pycache__', '.tmp-build', '.tmp', 'tmp'}
MAX_FILE = 50 * 1024 * 1024
WIP_AUTHOR = {'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': 'world-law@lexifina.com',
              'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': 'world-law@lexifina.com'}
# The country repos are public (2026-10-29): work in progress goes to the private operations repo instead, one branch
# per country, and rewrites of a shared repo wait for the user's approval (never rewrite, force-push, delete, move or
# change visibility without warning and an explicit yes).
OPS_URL = 'https://github.com/lexifina/world-law-ops.git'
APPROVED = ROOT / 'scripts' / 'world-law' / 'REWRITE-APPROVED.txt'
PENDING = ROOT / 'scripts' / 'world-law' / 'REWRITE-PENDING.json'
PENDING_LOCK = threading.Lock()


def git(repo: Path, *args: str, env: dict | None = None, data: bytes | None = None, check: bool = True) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if check and out.returncode:
        raise RuntimeError(f'git {" ".join(args[:3])}: {out.stderr.decode("utf-8", "replace").strip()[:300]}')
    return out.stdout.decode('utf-8', 'replace').strip()


def push(repo: Path, *refs: str, remote: str = 'origin', leases: dict[str, str] | None = None) -> str:
    """Plain push with retries (GitHub sometimes answers 'Repository not found' when many pushes run at once). Never
    forced: the only rewrite ever pushed is one the user approved, sent with --force-with-lease on its exact old SHA
    (`leases`: destination ref -> the remote SHA the approval names)."""
    lease_args = [f'--force-with-lease={ref}:{old}' for ref, old in (leases or {}).items()]
    last = ''
    for attempt in range(4):
        out = subprocess.run(['git', 'push', '-q', *lease_args, remote, *refs], cwd=repo, capture_output=True, text=True)
        if out.returncode == 0:
            return 'pushed'
        last = out.stderr.strip()
        if 'did not run because of a timeout' in last:
            # GitHub's secret scan gives up on a very large push (thousands of new commits). Push the same refs in
            # steps it can scan, then the whole set once more.
            return push_in_steps(repo, *refs, remote=remote, leases=leases)
        if 'GH013' in last or 'non-fast-forward' in last or 'stale info' in last or 'fetch first' in last:
            break  # a repository rule, or the remote moved: retrying cannot help
        time.sleep(15 * (attempt + 1))
    # The whole message goes to its own log: GitHub names the file and line only near the end of it.
    with open(Path(__file__).resolve().parent / 'logs' / 'push-errors.log', 'a', encoding='utf-8') as f:
        f.write(f'=== {repo.name} {" ".join(refs)} at {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}\n{last}\n')
    return f'push failed: {last[:300]}'


def push_in_steps(repo: Path, *refs: str, step: int = 300, remote: str = 'origin',
                  leases: dict[str, str] | None = None) -> str:
    """Push each branch in `refs` a few hundred first-parent commits at a time, then the tags in batches, then all the
    refs together, so each push is small enough for GitHub's secret scan to finish. An approved rewrite keeps its lease
    step by step: each step expects the remote to hold the previous step."""
    log = Path(__file__).resolve().parent / 'logs' / 'push-errors.log'
    expect = dict(leases or {})

    def run(*args: str, lease: dict[str, str]) -> subprocess.CompletedProcess:
        return subprocess.run(['git', 'push', '-q', *[f'--force-with-lease={r}:{o}' for r, o in lease.items()], remote,
                               *args], cwd=repo, capture_output=True, text=True)

    for ref in refs:
        if not ref.startswith('refs/heads/'):
            continue
        src, _, dst = ref.partition(':')
        commits = git(repo, 'rev-list', '--first-parent', '--reverse', src).split()
        for sha in commits[step - 1::step]:
            r = run(f'{sha}:{dst}', lease={dst: expect[dst]} if dst in expect else {})
            if r.returncode:
                with open(log, 'a', encoding='utf-8') as f:
                    f.write(f'=== {repo.name} step {sha[:8]}:{dst}\n{r.stderr.strip()}\n')
                return f'push failed: step {sha[:8]} of {dst}: {r.stderr.strip()[:200]}'
            if dst in expect:
                expect[dst] = sha
    tag_refs = [r for r in refs if r.startswith('refs/tags/')]
    for i in range(0, len(tag_refs), step):
        batch = [t.partition(':')[2] for t in tag_refs[i:i + step]]
        r = run(*tag_refs[i:i + step], lease={t: expect[t] for t in batch if t in expect})
        if r.returncode:
            return f'push failed: tags batch {i // step}: {r.stderr.strip()[:200]}'
        for t in batch:
            if t in expect:
                expect[t] = git(repo, 'rev-parse', t)
    r = run(*refs, lease=expect)
    if r.returncode:
        with open(log, 'a', encoding='utf-8') as f:
            f.write(f'=== {repo.name} final {" ".join(refs)}\n{r.stderr.strip()}\n')
        return f'push failed: {r.stderr.strip()[:300]}'
    return 'pushed (in steps)'


def approved_rewrites() -> set[tuple[str, str, str, str]]:
    """(slug, ref, old, new) the user approved, one line each in world-law/REWRITE-APPROVED.txt. A coordinator writes a
    line only after the user's explicit yes for that repo; the exact SHAs mean an approval covers that one rewrite."""
    if not APPROVED.exists():
        return set()
    out = set()
    for line in APPROVED.read_text(encoding='utf-8').splitlines():
        f = line.split('#', 1)[0].split()
        if len(f) == 4:
            out.add(tuple(f))
    return out


def note_pending(slug: str, entry: dict | None) -> None:
    """Record (or clear, with None) a rewrite awaiting the user's approval in world-law/REWRITE-PENDING.json."""
    with PENDING_LOCK:
        cur = json.loads(PENDING.read_text(encoding='utf-8')) if PENDING.exists() else {}
        if entry is None:
            if cur.pop(slug, None) is None:
                return
        else:
            cur[slug] = entry
        PENDING.write_text(json.dumps(cur, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


def standing_approval(slug: str, repo: Path, branch: str, old: str, new: str, local_tags: dict, remote_tags: dict) -> str:
    """The rewrites the user approved in advance (2026-10-29 ~19:45 UTC), for main only, after a clean check and audit:
    - 'doc-tip replacement': only the final documentation commit differs (same parent, so every law commit is the same
      object) and every tag the remote holds is unchanged;
    - 'first build': the remote main is the scaffold ("sources, before any law"), an unpaused "Paused, not yet law"
      README, or a thin old corpus of at most 3 law commits.
    Returns the kind, or '' when the rewrite still needs the user's yes."""
    if branch != 'main':
        return ''
    if git(repo, 'rev-parse', f'{old}^', check=False) == git(repo, 'rev-parse', f'{new}^', check=False):
        if all(local_tags.get(t) == s for t, s in remote_tags.items()):
            return 'doc-tip replacement'
        return ''
    email, _, subject = git(repo, 'log', '-1', '--format=%ae%x1f%s', old).partition('\x1f')
    unpaused = ROOT / 'scripts' / 'world-law' / 'UNPAUSED.txt'
    if subject.endswith('sources, before any law') or (
            email == 'world-law@lexifina.com' and subject.startswith('Paused, not yet law') and unpaused.exists()
            and slug in unpaused.read_text(encoding='utf-8').split()):
        return 'first build over the scaffold'
    laws = [c for c in git(repo, 'log', '--format=%ae', old).split() if c.endswith('.invalid')]
    if len(laws) <= 3:
        return f'first build over a thin corpus ({len(laws)} law commits)'
    return ''


def docs_update(slug: str, repo: Path, old: str, new: str) -> str | None:
    """When a rebuild changes only the documentation commit (the laws are the same commits), a commit on top of the
    remote with the new documentation tree, so the update fast-forwards instead of replacing the remote's tip.
    Returns its SHA, 'same' when the remote already has that tree, or None when the laws differ (a real rewrite)."""
    def is_docs(c: str) -> bool:
        email, _, subj = git(repo, 'log', '-1', '--format=%ae%x1f%s', c).partition('\x1f')
        return email == f'{slug}-law@lexifina.com' and subj.startswith('Documentation')
    if not is_docs(new):
        return None
    tip = old
    while is_docs(tip):  # the remote's own documentation commits, newest first, down to its last law commit
        parents = git(repo, 'rev-list', '--parents', '-n', '1', tip).split()[1:]
        if len(parents) != 1:
            return None
        tip = parents[0]
    if tip != git(repo, 'rev-parse', f'{new}^'):
        return None
    tree = git(repo, 'rev-parse', f'{new}^{{tree}}')
    if tree == git(repo, 'rev-parse', f'{old}^{{tree}}'):
        return 'same'
    name, email, date = git(repo, 'log', '-1', '--format=%an%x1f%ae%x1f%ad', '--date=raw', new).split('\x1f')
    old_date = git(repo, 'log', '-1', '--format=%ad', '--date=raw', old)
    date = max(date, old_date, key=lambda d: int(d.split()[0]))  # never earlier than the commit it follows
    body = git(repo, 'log', '-1', '--format=%b', new)
    msg = f'Documentation update: tables, tools and REPRODUCE.md\n\n{body}\n'.encode()
    env = {'GIT_AUTHOR_NAME': name, 'GIT_AUTHOR_EMAIL': email, 'GIT_AUTHOR_DATE': date,
           'GIT_COMMITTER_NAME': name, 'GIT_COMMITTER_EMAIL': email, 'GIT_COMMITTER_DATE': date}
    return git(repo, 'commit-tree', tree, '-p', old, env=env, data=msg)


def publish(slug: str, repo: Path, branches: list[str], dry_run: bool = False) -> str:
    """Push `branches` (local names, same name on the remote) and the tags to the shared repo, without ever
    rewriting it unasked:
    - a branch equal to the remote is skipped; one that fast-forwards it is pushed plainly;
    - one that would replace remote commits (the docs-commit tip included) is pushed only if REWRITE-APPROVED.txt names
      that exact old -> new, with --force-with-lease; otherwise it is recorded in REWRITE-PENDING.json and nothing is
      pushed for the repo;
    - new tags are pushed; a tag the remote holds at another commit moves only with its branch's approval; tags only
      the remote holds are left alone (never deleted);
    - everything that would be added goes through private.audit_push() first; any finding stops the push."""
    git(repo, 'fetch', '-q', '--no-tags', 'origin', *[f'+refs/heads/{b}:refs/remotes/origin/{b}' for b in branches],
        check=False)
    remote_tags = {}
    for line in git(repo, 'ls-remote', '--tags', 'origin', check=False).splitlines():
        sha, _, ref = line.partition('\t')
        if not ref.endswith('^{}'):
            remote_tags[ref] = sha
    local_tags = {}
    for line in git(repo, 'show-ref', '--tags', check=False).splitlines():
        sha, _, ref = line.partition(' ')
        local_tags[ref] = sha
    approved = approved_rewrites()
    refs, leases, plan, rewrites = [], {}, [], []
    for b in branches:
        new = git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{b}', check=False)
        old = git(repo, 'rev-parse', '-q', '--verify', f'refs/remotes/origin/{b}', check=False)
        if not new or new == old:
            plan.append(f'{b} same')
            continue
        if old and subprocess.run(['git', 'merge-base', '--is-ancestor', old, new], cwd=repo).returncode:
            standing = standing_approval(slug, repo, b, old, new, local_tags, remote_tags)
            if standing:
                found = private.audit_push(repo, new, old)
                if found:
                    return f'NOT pushed: privacy audit found {len(found)} in {b}: {"; ".join(found[:5])}'
                leases[f'refs/heads/{b}'] = old
                plan.append(f'{b} {standing} {old[:9]}->{new[:9]} (standing approval, lease)')
                refs.append(f'refs/heads/{b}:refs/heads/{b}')
                continue
            docs = docs_update(slug, repo, old, new)
            if docs == 'same':
                plan.append(f'{b} same (documentation already current)')
                continue
            if docs:
                found = private.audit_push(repo, docs, old)
                if found:
                    return f'NOT pushed: privacy audit found {len(found)} in {b}: {"; ".join(found[:5])}'
                plan.append(f'{b} documentation update {old[:9]}->{docs[:9]} (fast-forward)')
                refs.append(f'{docs}:refs/heads/{b}')
                continue
            replaced = git(repo, 'rev-list', '--count', old, f'^{new}', check=False)
            if (slug, f'refs/heads/{b}', old, new) not in approved:
                rewrites.append({'ref': f'refs/heads/{b}', 'old': old, 'new': new, 'replaces_commits': int(replaced or 0),
                                 'adds_commits': int(git(repo, 'rev-list', '--count', new, f'^{old}') or 0)})
                continue
            leases[f'refs/heads/{b}'] = old
            plan.append(f'{b} approved rewrite {old[:9]}->{new[:9]}')
        else:
            plan.append(f'{b} fast-forward {old[:9] or "(new)"}->{new[:9]}')
        refs.append(f'refs/heads/{b}:refs/heads/{b}')
        found = private.audit_push(repo, new, old or None)
        if found:
            return f'NOT pushed: privacy audit found {len(found)} in {b}: {"; ".join(found[:5])}'
    if rewrites:
        if not dry_run:
            note_pending(slug, {'repo': f'lexifina/{slug}-law', 'at': _now(), 'rewrites': rewrites})
        return ('NOT pushed: needs a rewrite the user has not approved ('
                + ', '.join(f'{r["ref"][11:]} {r["old"][:9]}->{r["new"][:9]}, replaces {r["replaces_commits"]}'
                            for r in rewrites) + ')' + ('' if dry_run else '; recorded in world-law/REWRITE-PENDING.json'))
    if not dry_run:
        note_pending(slug, None)
    moved = [t for t, s in local_tags.items() if t in remote_tags and remote_tags[t] != s]
    if moved and not leases:
        return f'NOT pushed: {len(moved)} tags would move ({", ".join(t[10:] for t in moved[:3])}) with no approved rewrite'
    for t in moved:
        leases[t] = remote_tags[t]
    refs += [f'{t}:{t}' for t, s in sorted(local_tags.items()) if remote_tags.get(t) != s]
    kept = sum(1 for t in remote_tags if t not in local_tags)
    summary = f'{"; ".join(plan)}; {sum(1 for r in refs if r.partition(":")[2].startswith("refs/tags/"))} tags to push' + \
        (f'; {kept} remote-only tags left alone' if kept else '')
    if not refs:
        return f'nothing to push ({summary})'
    if dry_run:
        return f'dry run, would push: {summary}'
    return f'{push(repo, *refs, leases=leases)} ({summary})'


CREDENTIAL = re.compile(r'(code|key|token|sig|apikey)=[A-Za-z0-9_%=-]{20,}')


def wip(slug: str, folder: Path, repo: Path, dry_run: bool = False) -> str:
    """Snapshots scripts/<slug>-law onto branch wip/<slug>-law of the PRIVATE lexifina/world-law-ops (never the public
    country repo), so unfinished work leaves this machine. Each snapshot extends the branch: never forced."""
    files = []
    for p in sorted(folder.rglob('*')):
        rel = p.relative_to(folder)
        if (not p.is_file() or set(rel.parts) & SKIP_DIRS or any(x.startswith('.tmp') or x == '.git' for x in rel.parts[:-1])
                or p.name.startswith('.autopush')
                or p.name == 'BUILD_STATUS.json' or p.stat().st_size > MAX_FILE):
            continue
        files.append((rel.as_posix(), p))
    if 'ops' not in git(repo, 'remote').split():
        git(repo, 'remote', 'add', 'ops', OPS_URL)
    with tempfile.TemporaryDirectory() as tmp:
        env = {'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        for rel, p in files:
            data = p.read_bytes()
            text = data.decode('utf-8', 'replace') if p.suffix in ('.py', '.sh', '.md', '.json', '.txt', '.csv') else ''
            if text and (private.HOME.search(text) or CREDENTIAL.search(text)):
                # Even in the private repo: no machine path, and no credential an agent noted down.
                clean = CREDENTIAL.sub(lambda m: f'{m.group(1)}=<redacted>', private.scrub(text))
                sha = git(repo, 'hash-object', '-w', '--stdin', data=clean.encode('utf-8'))
            else:
                sha = git(repo, 'hash-object', '-w', '--', str(p))
            git(repo, 'update-index', '--add', '--cacheinfo', f'100644,{sha},wip/{rel}', env=env)
        tree = git(repo, 'write-tree', env=env)
    branch = f'wip/{slug}-law'
    git(repo, 'fetch', '-q', '--no-tags', 'ops', f'+refs/heads/{branch}:refs/remotes/ops/wip', check=False)
    parent = git(repo, 'rev-parse', '-q', '--verify', 'refs/remotes/ops/wip', check=False)
    if parent and git(repo, 'rev-parse', f'{parent}^{{tree}}') == tree:
        return 'ops wip unchanged'
    if dry_run:
        return f'dry run, would push a snapshot of {len(files)} files to world-law-ops {branch}'
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    msg = f'Work in progress: scripts/{slug}-law at {now}\n'.encode()
    commit = git(repo, 'commit-tree', tree, *(['-p', parent] if parent else []), env={**WIP_AUTHOR, 'GIT_AUTHOR_DATE': now,
                                                                                     'GIT_COMMITTER_DATE': now}, data=msg)
    git(repo, 'update-ref', 'refs/heads/ops-wip', commit)
    return 'ops wip ' + push(repo, f'refs/heads/ops-wip:refs/heads/{branch}', remote='ops')


def docs_date(corpus: dict) -> str:
    days = sorted(s.get('retrieved', '') for s in corpus.get('sources', []) if s.get('retrieved'))
    return days[-1] if days else dt.date.today().isoformat()


def main_build(slug: str, folder: Path, repo: Path, state: dict, dry_run: bool = False) -> dict:
    corpus_path = folder / 'corpus.json'
    if not corpus_path.exists() and not list((folder / 'corpus.d').glob('*.json')):
        return {'main': 'no corpus.json yet'}
    try:
        corpus, raw = load(folder)  # corpus.json plus corpus.d/ parts, exactly as the builder reads them
    except (ValueError, SystemExit) as e:
        return {'main': f'corpus is being written or invalid; retry next pass ({str(e)[:120]})'}
    # Rebuild when anything the build reads changes: the corpus, the country's static docs, PUBLISH, or the shared
    # builder (so a builder fix reaches every repository on the next pass).
    h = hashlib.sha256(raw)
    # Only the shared files a build reads or ships (wayback.py and the tests change no repository).
    for p in (sorted((folder / 'repo').rglob('*')) + [COMMON / n for n in ('build.py', 'check.py', 'on.py')]
              + sorted(COMMON.glob('*.md'))
              + [folder / 'PUBLISH'] + sorted((folder / 'corpus.d').glob('*.PUBLISH'))):
        if p.is_file() and '__pycache__' not in p.parts:
            h.update(p.as_posix().encode() + b'\0' + p.read_bytes())
    # The privacy rules (what tools/ ships) and this country's rewrite approvals change what may be pushed.
    h.update((COMMON / 'private.py').read_bytes())
    h.update(repr(sorted(a for a in approved_rewrites() if a[0] == slug)).encode())
    sha = h.hexdigest()
    if state.get('built_sha') == sha and not dry_run:
        return {'main': f'unchanged since {state.get("built_at")} ({state.get("result")})'}
    day = docs_date(corpus)
    future = corpus['country'].get('future_branch', 'futuro')
    parts = sorted((folder / 'corpus.d').glob('*.json')) if (folder / 'corpus.d').exists() else []
    unverified = [p.name for p in parts if not p.with_suffix('.PUBLISH').exists()]
    published = (folder / 'PUBLISH').exists()

    def build_check(verified_only: bool) -> tuple[bool, dict]:
        env = {**os.environ, 'GITLAW_VERIFIED_PARTS_ONLY': '1' if verified_only else '0'}
        py = [sys.executable, '-X', 'utf8']
        ver_path = folder / 'verification.json'
        # REPRODUCE.md quotes the check recorded for this exact corpus. When this pass's check is new (first build of
        # this corpus, or the verified-only main build after the full one), build once more so it quotes it.
        for attempt in range(2):
            before = json.loads(ver_path.read_text(encoding='utf-8')).get('check') if ver_path.exists() else None
            b = subprocess.run(py + [str(COMMON / 'build.py'), str(folder), '--repo', str(repo), '--docs-date', day],
                               capture_output=True, text=True, encoding='utf-8', env=env)
            if b.returncode:
                return False, {'stage': 'build', 'error': (b.stderr or b.stdout)[-3000:]}
            c = subprocess.run(py + [str(COMMON / 'check.py'), str(repo), '--corpus', str(corpus_path), '--write'],
                               capture_output=True, text=True, encoding='utf-8', env=env)
            try:
                chk = json.loads(c.stdout)
            except ValueError:
                chk = {'error': (c.stderr or c.stdout)[-2000:]}
            chk = {k: v for k, v in chk.items() if k != 'details'} if isinstance(chk, dict) else chk
            if c.returncode or chk == before:
                break
        return c.returncode == 0, {'stage': 'check', 'check': chk}

    out = {'docs_date': day}
    # 1. Everything, verified or not, is built and checked here, so the agents see the whole country as they have it.
    #    It is no longer pushed to `preview`: the country repos are public and this text is not yet verified.
    if not published or unverified:
        ok, info = build_check(False)
        if not ok:
            state.update(built_sha=sha, built_at=_now(), result=f'{info["stage"]} failed, not pushed')
            return {'main': f'{info["stage"]} failed, not pushed', **info}
        out['preview'] = f'built and checked locally at {git(repo, "rev-parse", "--short", "main")} (not published)'
        out['check'] = info['check']
        if not published:
            state.update(built_sha=sha, built_at=_now(), result=out['preview'])
            return {'main': f'{out["preview"]}; main waits for PUBLISH', **out}
    # 2. main holds only what has been verified against the official text: corpus.json (PUBLISH) and each corpus.d
    #    part whose owner wrote <part>.PUBLISH. Tags are pruned to match, so a part's tags leave with it.
    owner = remote_main_owner(slug, repo)
    if owner != 'ours':
        # Never overwrite a main this pipeline did not make: another session may have built the country with its
        # own builder (Spain, Austria, Italy, ...). The build stays on preview; a person decides.
        state.update(built_sha=sha, built_at=_now(), result=f'main NOT pushed: {owner}')
        return {'main': f'main NOT pushed: remote main is {owner}; build kept on preview only', **out}
    ok, info = build_check(True)
    if not ok:
        state.update(built_sha=sha, built_at=_now(), result=f'main {info["stage"]} failed, not pushed')
        return {'main': f'main {info["stage"]} failed, not pushed', **out, **info}
    branches = ['main'] + ([future] if git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{future}', check=False) else [])
    result = publish(slug, repo, branches, dry_run=dry_run)
    head = git(repo, 'rev-parse', '--short', 'main')
    # A failed push is retried on the next pass: only a pushed (or unchanged, or waiting-for-approval) build is
    # remembered as done. A new approval changes the hash above, so an approved rewrite is pushed on the next pass.
    if not dry_run:
        state.update(built_sha=None if result.startswith('push failed') else sha, built_at=_now(),
                     result=f'{result[:200]} {head}')
    return {'main': f'{result} {head}' + (f' (left out until verified: {", ".join(unverified)})' if unverified else ''),
            **out, 'check': info['check'], 'commits': git(repo, 'rev-list', '--count', 'main')}


def remote_main_owner(slug: str, repo: Path) -> str:
    """'ours' when the remote main is the scaffold ("<Name>: sources, before any law", by world-law@lexifina.com) or a
    build by the shared builder (its head is the documentation commit by <slug>-law@lexifina.com, or it holds
    data/repo.json). Anything else is another builder's work and is described instead."""
    # A full fetch (never --depth): publish() must see whether the remote main is an ancestor of the new build.
    if (repo / '.git' / 'shallow').exists():
        subprocess.run(['git', 'fetch', '-q', '--unshallow', 'origin'], cwd=repo, capture_output=True, timeout=600)
    out = subprocess.run(['git', 'fetch', '-q', '--no-tags', 'origin', '+refs/heads/main:refs/remotes/origin/main'],
                         cwd=repo, capture_output=True, text=True, timeout=600)
    if out.returncode:
        if 'couldn\'t find remote ref' in out.stderr or 'not found' in out.stderr.lower():
            return 'ours'  # no main yet
        return f'unknown (fetch failed: {out.stderr.strip()[:80]})'
    info = git(repo, 'log', '-1', '--format=%ae%x1f%s', 'refs/remotes/origin/main', check=False)
    email, _, subject = info.partition('\x1f')
    if subject.endswith('sources, before any law') or email == f'{slug}-law@lexifina.com':
        return 'ours'
    # A "Paused, not yet law" README commit on the scaffold counts as the scaffold only once the user has resolved
    # that pause and the slug is listed in world-law/UNPAUSED.txt. Pauses for rights (Brunei) stay until listed.
    unpaused = ROOT / 'scripts' / 'world-law' / 'UNPAUSED.txt'
    if (email == 'world-law@lexifina.com' and subject.startswith('Paused, not yet law') and unpaused.exists()
            and slug in unpaused.read_text(encoding='utf-8').split()):
        return 'ours'
    if git(repo, 'cat-file', '-t', 'refs/remotes/origin/main:data/repo.json', check=False) == 'blob':
        return 'ours'
    return f'another build ({email}: {subject[:60]})'


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def one(slug: str, dry_run: bool = False) -> str:
    folder = ROOT / 'scripts' / f'{slug}-law'
    repo = DOCS / f'{slug}-law'
    state_path = folder / '.autopush.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    status = {'at': _now()}
    try:
        if not (repo / '.git').exists():
            subprocess.run(['git', 'clone', '-q', f'https://github.com/lexifina/{slug}-law.git', str(repo)], check=True)
        status['wip'] = wip(slug, folder, repo, dry_run=dry_run)
        status.update(main_build(slug, folder, repo, state, dry_run=dry_run))
    except Exception as e:  # one country's failure never stops the others
        status['error'] = str(e)[:500]
    if dry_run:
        return json.dumps(status, indent=1, ensure_ascii=False)
    state_path.write_text(json.dumps(state, indent=1) + '\n', encoding='utf-8', newline='\n')
    (folder / 'BUILD_STATUS.json').write_text(json.dumps(status, indent=1, ensure_ascii=False) + '\n', encoding='utf-8',
                                              newline='\n')
    return f'{slug:10} {status.get("wip", "")[:28]:28} | {status.get("main", status.get("error", ""))[:80]}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loop', type=int, default=0, help='repeat every N seconds')
    ap.add_argument('--only', nargs='*', default=None)
    ap.add_argument('--each', type=int, default=0, help='run every country on its own loop, every N seconds')
    ap.add_argument('--workers', type=int, default=2, help='countries built and pushed at once in a single pass')
    ap.add_argument('--dry-run', action='store_true',
                    help='build, check and audit the --only countries, print what would be pushed, push nothing')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if args.dry_run:
        for s in args.only or []:
            print(one(s, dry_run=True), flush=True)
        return
    # Only countries that have started (their folder exists), so an empty folder never becomes an empty wip commit.
    countries = [s for s in (args.only or COUNTRIES) if (ROOT / 'scripts' / f'{s}-law').is_dir()]
    if args.each:
        # Every country on its own loop: a small country commits within about a minute of a change, however long the
        # biggest build takes. New country folders are picked up as they appear. The log keeps the "--- pass" lines
        # the watchdog reads, one per round of the scheduler.
        import threading
        running: dict[str, threading.Thread] = {}

        builds = threading.Semaphore(args.workers)  # at most --workers countries build or push at once

        def country_loop(slug: str):
            while True:
                t = time.time()
                try:
                    with builds:
                        line = one(slug)
                except Exception as e:  # one() already catches; this is a last guard so the thread never dies
                    line = f'{slug:10} error {str(e)[:120]}'
                print(line, flush=True)
                time.sleep(max(5, args.each - (time.time() - t)))

        last_site = 0.0
        while True:
            # The listed countries, plus any scripts/<slug>-law folder built by the shared builder (it has corpus.json or
            # corpus.d/). Other sessions' corpora (swiss-law, estonia-law, ...) have their own builders and no
            # corpus.json, so they are never touched.
            # Folders still sourcing (PROGRESS.md, no corpus yet) get wip snapshots too, so their work reaches GitHub.
            found = {p.name[:-4] for p in (ROOT / 'scripts').glob('*-law')
                     if p.is_dir() and p.name[:-4] not in FOREIGN
                     and ((p / 'corpus.json').exists() or (p / 'corpus.d').is_dir() or (p / 'PROGRESS.md').exists())}
            for s in sorted({s for s in COUNTRIES if (ROOT / 'scripts' / f'{s}-law').is_dir()} | found):
                if s not in running or not running[s].is_alive():
                    running[s] = threading.Thread(target=country_loop, args=(s,), daemon=True, name=s)
                    running[s].start()
            print(f'--- pass at {_now()} (scheduler: {len(running)} country loops alive)', flush=True)
            if time.time() - last_site > 120:
                sd = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve().parent / 'site_data.py')],
                                    capture_output=True, text=True, encoding='utf-8')
                print(f'site data: {"ok" if sd.returncode == 0 else "FAILED " + (sd.stderr or sd.stdout)[-300:]}', flush=True)
                last_site = time.time()
            time.sleep(60)
    if not args.only:
        # Same discovery as --each: every started shared-builder country, not only the listed ones.
        countries = sorted(set(countries) | {p.name[:-4] for p in (ROOT / 'scripts').glob('*-law')
                                             if p.is_dir() and p.name[:-4] not in FOREIGN
                                             and ((p / 'corpus.json').exists() or (p / 'corpus.d').is_dir()
                                                  or (p / 'PROGRESS.md').exists())})
    while True:
        t = time.time()
        with ThreadPoolExecutor(min(args.workers, len(countries)) or 1) as ex:
            lines = list(ex.map(one, countries))
        print(f'--- pass at {_now()} ({time.time() - t:.0f} s)', *lines, sep='\n', flush=True)
        # Keep the /watch/south-america reader's data in step with what main holds (a few seconds; never fatal).
        sd = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve().parent / 'site_data.py')],
                            capture_output=True, text=True, encoding='utf-8')
        print(f'site data: {"ok" if sd.returncode == 0 else "FAILED " + (sd.stderr or sd.stdout)[-300:]}', flush=True)
        if not args.loop:
            return
        time.sleep(max(10, args.loop - (time.time() - t)))


if __name__ == '__main__':
    main()
