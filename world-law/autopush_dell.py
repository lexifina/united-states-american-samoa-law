"""gitlaw-scraper-dell's copy of south-america-law/autopush.py (2026-10-30): streams only the repos whose
scripts/world-law/claims/<repo>.txt names gitlaw-scraper-dell, so it never touches hp-omen's.

Keeps every claimed law repository current, so country agents never wait on a push.

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
sys.path.append(str(COMMON))  # LAST, so a country's own build.py is never shadowed
from build import load  # noqa: E402
import build as B  # noqa: E402
import check as K  # noqa: E402  (gitlaw_common/check.py)
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
COUNTRIES: list[str] = []  # this copy owns no fixed list: only claims
# Every country this coordinator owns (South America, Africa and the wave countries). Nothing else is ever pushed.
OWN: set[str] = set()
# Folders under scripts/ that other sessions' builders own (their own build.py, their own repos): never touched.
FOREIGN = {'estonia', 'liechtenstein', 'luxembourg', 'malta', 'swiss', 'germany', 'grundgesetz', 'bundesrecht',
           'uk', 'global', 'world', 'south-america', 'africa'}
# Out of scope for now (user: no right-to-left or CJK scripts): held off every branch until the user decides.
FOREIGN |= {'oman', 'qatar', 'yemen', 'syria', 'sudan', 'united-arab-emirates', 'palestine', 'south-korea'}
# First builds of the empty repos by global-law-main-composer's agents (2026-10-29/30, push_clean.py), plus the five
# scaffolds of ours with no corpus that it took over.
FOREIGN |= set('''afghanistan aland algeria antigua-and-barbuda australia-new-south-wales bahrain barbados belarus benin
    bhutan bosnia-and-herzegovina british-virgin-islands brunei burundi cambodia canada-nova-scotia canada-quebec
    canada-saskatchewan cayman-islands central-african-republic chad comoros cuba djibouti dominica egypt el-salvador
    eritrea ethiopia gabon gambia grenada guatemala guernsey guinea-bissau haiti honduras hungary iceland india indonesia
    iran iraq isle-of-man israel jamaica jersey jordan kazakhstan kiribati kuwait laos lebanon libya macau maldives
    marshall-islands mauritania morocco myanmar nepal niger north-korea panama papua-new-guinea puerto-rico
    saint-kitts-and-nevis saint-vincent-and-the-grenadines samoa singapore somalia south-sudan tunisia ukraine
    united-states-american-samoa uzbekistan'''.split())
# The fork's L-Z countries, whose built law sat only on preview: published from world-law-ops wip by the composer.
FOREIGN |= set('''philippines russia saint-lucia sao-tome-and-principe serbia solomon-islands sri-lanka syria tajikistan
    tonga turkmenistan vanuatu vietnam yemen oman qatar united-arab-emirates palestine south-korea sudan
    republic-of-congo'''.split())
# Other sessions' own builders (global-law-main-composer and earlier): never touched from here.
FOREIGN |= {'romania'}  # controlled by Alan's laptop session (lexifina-cc) since 2026-11-02
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
# Set in the WSL child (see "WSL ext4" below): this process builds and publishes one repo on ext4.
IN_WSL = os.environ.get('GITLAW_AUTOPUSH_WSL') == '1'


class _file_lock:
    """A lock file next to `path` (O_EXCL create), shared by the Windows loop and its WSL children. A lock older than
    `stale` seconds is taken over (its holder died)."""

    def __init__(self, path: Path, stale: float = 120):
        self.lock, self.stale = path.with_name(path.name + '.lock'), stale

    def __enter__(self):
        while True:
            try:
                os.close(os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.lock.stat().st_mtime > self.stale:
                        self.lock.unlink(missing_ok=True)
                        continue
                except OSError:
                    continue
                time.sleep(0.2)

    def __exit__(self, *exc):
        self.lock.unlink(missing_ok=True)


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


def push_new_tags(repo: Path, tag_refs: list[str], size: int = 1000) -> str:
    """Push `tag_refs` ('<sha>:refs/tags/<name>', none on the remote yet) in batches through throwaway bare repos."""
    import shutil
    objects = Path(git(repo, 'rev-parse', '--absolute-git-dir')) / 'objects'
    url = git(repo, 'remote', 'get-url', 'origin')
    if '://' not in url and not Path(url).is_absolute():  # a local path relative to the repo
        url = (repo / url).resolve().as_posix()
    for i in range(0, len(tag_refs), size):
        part = tag_refs[i:i + size]
        tmp = Path(tempfile.mkdtemp(prefix='tagpush-'))
        try:
            git(tmp, 'init', '-q', '--bare')
            # bytes: a text-mode write on Windows would end the path with \r
            (tmp / 'objects' / 'info' / 'alternates').write_bytes((objects.as_posix() + '\n').encode())
            git(tmp, 'update-ref', '--stdin', data=''.join(f'create {r.partition(":")[2]} {r.partition(":")[0]}\n'
                                                            for r in part).encode('utf-8'))
            r = push(tmp, 'refs/tags/*:refs/tags/*', remote=url)
            if r.startswith('push failed'):
                return f'{r} (tags batch {i // size})'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return 'pushed'


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
    with PENDING_LOCK, _file_lock(PENDING):  # the file lock: WSL children write it from other processes
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
    Returns the kind, or '' when the rewrite still needs the user's yes.

    Since 2026-11-02 (user: "end force-pushes everywhere") no standing approval applies: published history only grows
    by fast-forward, and any rewrite waits for the user's yes for that repo in REWRITE-APPROVED.txt."""
    return ''
    # Standing yes (user, 2026-10-30 ~06:05 UTC: "Standing yes for verified rebuilds"): any law-history rewrite of a
    # repo this coordinator owns, once every published part has PUBLISH and check.py and audit_push are clean (both
    # already hold when publish() reaches here). The replaced history is archived to world-law-ops first (publish()).
    if slug in owned():
        return 'verified rebuild'
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


# ---------------------------------------------------------------- append onto the remote (2026-11-02)
# The builder regenerates a repo's whole history and ends it with a fresh documentation commit, so a new build is
# never a descendant of the published main. append_onto() re-parents the build's new commits onto the published tip
# instead: same trees, same authors, author dates and messages, committer dates kept rising. The published docs commit
# stays in history; the build's docs commit is appended after it. Anything else (an older commit inserted, a published
# law commit changed or removed) is a rewrite and waits for the user's yes.


def _read_commits(repo: Path, shas: list[str]) -> dict[str, bytes]:
    """Raw commit objects (header + message, exact bytes) through one `git cat-file --batch`."""
    out: dict[str, bytes] = {}
    want = list(dict.fromkeys(shas))
    if not want:
        return out
    data = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo, capture_output=True,
                          input=''.join(f'{s}\n' for s in want).encode()).stdout
    i = 0
    for s in want:
        end = data.index(b'\n', i)
        head = data[i:end].split()
        if len(head) < 3 or head[1] != b'commit':
            raise RuntimeError(f'not a commit: {s}')
        size = int(head[2])
        out[s] = data[end + 1:end + 1 + size]
        i = end + 1 + size + 1
    return out


def _split(raw: bytes) -> tuple[list[bytes], bytes]:
    head, _, msg = raw.partition(b'\n\n')
    return head.split(b'\n'), msg


def _field(raw: bytes, name: bytes) -> bytes:
    for line in _split(raw)[0]:
        if line.startswith(name + b' '):
            return line[len(name) + 1:]
    return b''


def _ident(line: bytes) -> tuple[str, str, int, str]:
    """'Name <email> 1700000000 +0100' -> (name, email, timestamp, tz)."""
    lt, gt = line.rindex(b'<'), line.rindex(b'>')
    ts, tz = line[gt + 1:].split()
    return line[:lt].strip().decode('utf-8', 'replace'), line[lt + 1:gt].decode('utf-8', 'replace'), int(ts), tz.decode()


def _is_law(raw: bytes) -> bool:
    """A law commit: anything not authored by 'Lexifina' (documentation commits, the scaffold, README pauses)."""
    return _ident(_field(raw, b'author'))[0] != 'Lexifina'


def _key(raw: bytes) -> tuple[bytes, bytes, bytes]:
    """What makes two law commits the same law commit, whatever their parents: tree, author line (name, email, date,
    zone) and message."""
    return _field(raw, b'tree'), _field(raw, b'author'), _split(raw)[1]


def _describe(raw: bytes) -> str:
    name, _, ts, _ = _ident(_field(raw, b'author'))
    subj = _split(raw)[1].split(b'\n', 1)[0].decode('utf-8', 'replace')
    return f'"{subj[:70]}" ({dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()})'


def _write_object(repo: Path, kind: str, body: bytes) -> str:
    """A loose object, exactly as `git commit-tree` / `hash-object -w` would store it (one process for thousands)."""
    import zlib
    data = f'{kind} {len(body)}\0'.encode() + body
    sha = hashlib.sha1(data).hexdigest()
    objects = Path(git(repo, 'rev-parse', '--git-path', 'objects'))
    if not objects.is_absolute():
        objects = repo / objects
    path = objects / sha[:2] / sha[2:]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f'.tmp-{sha[2:]}-{os.getpid()}-{threading.get_ident()}')
        tmp.write_bytes(zlib.compress(data, 1))
        try:
            os.replace(tmp, path)
        except OSError:
            if not path.exists():
                raise
            tmp.unlink(missing_ok=True)
    return sha


def _deltas(repo: Path, tip: str) -> tuple[list[str], dict[str, dict[bytes, tuple[bytes, str] | None]]]:
    """First-parent commits of `tip`, oldest first, and each one's file changes against its first parent
    ({path: (mode, blob id) or None when deleted}), from one `git log --raw`."""
    out = subprocess.run(['git', '-c', 'log.showRoot=true', 'log', '-z', '--first-parent', '--no-renames', '--raw',
                          '--no-abbrev', '--format=%x01%H', tip], cwd=repo, capture_output=True).stdout
    order: list[str] = []
    deltas: dict[str, dict] = {}
    cur = None
    toks = out.split(b'\0')
    i = 0
    while i < len(toks):
        t = toks[i].lstrip(b'\n')
        i += 1
        if t.startswith(b'\x01'):
            cur = t[1:].decode()
            order.append(cur)
            deltas[cur] = {}
        elif t.startswith(b':') and cur is not None:
            meta = t[1:].split()
            path = toks[i]
            i += 1
            deltas[cur][path] = None if meta[4].startswith(b'D') else (meta[1], meta[3].decode())
    order.reverse()
    return order, deltas


def _is_law_path(path: bytes) -> bool:
    """A provision file (<act>/<unit>.md): not an act README, the docs commit's data/ and tools/, or top-level docs."""
    top, _, rest = path.partition(b'/')
    return bool(rest) and path.endswith(b'.md') and not path.endswith(b'/README.md') and path != b'README.md' \
        and top not in (b'data', b'tools')


def _law_delta(d: dict) -> dict:
    return {p: v for p, v in d.items() if _is_law_path(p)}


def append_onto(repo: Path, remote: str | None, built: str, base: dict[str, str] | None = None,
                base_tip: str | None = None) -> dict:
    """Grow `remote` (the published tip, or None) towards `built` (the fresh build) by fast-forward only.

    Law commits ('Lexifina'-authored commits are not law) are matched by author line (name, email, in-force date) and
    message, and compared by the provision files each one changes. Act by act (top-level folder), the build must tell
    the published story unchanged: every published law commit is there, changes the same files to the same text, and
    each act's published commits keep their order. The build's other law commits are appended on top of the published
    tip in build order, each changing only its own files (the tip's other files, docs included, are carried until the
    build's documentation commit replaces the whole tree). An appended commit may touch an act only after that act's
    last published commit: a newer version, or an older law found late in an act folder of its own (Alan's D12,
    2026-11-02: appended at the end of history, never inserted). Anything else (a published commit changed, re-dated,
    removed or reordered, an older version slipped into a published act) is a rewrite and waits for the user's yes.
    Committer dates are max(own, previous + 1 s).
    With no `remote` (a branch the remote lacks, e.g. a first `futuro`), `base` maps build SHAs already published
    elsewhere (main's) to their published SHAs, and the build is grafted after the longest such prefix.

    Returns {'kind': 'same'|'append'|'new'|'rewrite', 'new': tip to publish, 'map': {build sha: new sha},
             'added': new commits, 'laws': law commits added, 'docs': docs commits added, 'backfill': any appended law
             commit older than the published laws it follows, 'reason': why a rewrite}."""
    n_list, n_delta = _deltas(repo, built)
    r_list, r_delta = _deltas(repo, remote) if remote else ([], {})
    raws = _read_commits(repo, n_list + r_list)
    n_law = [s for s in n_list if _is_law(raws[s])]
    last_law = n_list.index(n_law[-1]) if n_law else -1
    r_set = set(r_list)
    if any(not _is_law(raws[s]) and s not in r_set for s in n_list[:last_law]):
        return {'kind': 'rewrite', 'reason': 'the build has a non-law commit inside its law history'}
    tail = n_list[last_law + 1:]  # the build's documentation commit(s), after its last law commit
    mapping: dict[str, str] = {}
    name = lambda f: f.decode('utf-8', 'replace')  # noqa: E731
    top = lambda d: {p.partition(b'/')[0] for p in d}  # noqa: E731
    if remote:
        r_law = [s for s in r_list if _is_law(raws[s])]
        # Every build commit up to its last law commit (a build made on top of the published head, as the
        # incremental path makes it, carries the published docs and correction commits too).
        items, corrections, reasons = _plan_by_act(repo, raws, r_list, r_delta, n_list[:last_law + 1], n_delta,
                                                   slug_email(raws))
        if isinstance(items, str):
            return {'kind': 'rewrite', 'reason': items}
        new_law = [it['src'] for it in items if it.get('src')]
        backfill = any(it.get('backfill') for it in items)
        parent = remote
    else:
        backfill = False
        corrections, reasons = 0, []
        base = base or {}
        k = 0
        while k < len(n_law) and n_law[k] in base:
            mapping[n_law[k]] = base[n_law[k]]
            k += 1
        if not k:  # nothing published to graft onto: the build is pushed as it is (a new branch, no history lost)
            return {'kind': 'new', 'new': built, 'map': {s: s for s in n_list}, 'added': list(n_list),
                    'laws': len(n_law), 'docs': len(tail), 'law_tip': n_law[-1] if n_law else None}
        new_law = n_law[k:]
        items = [{'src': s, 'author': _field(raws[s], b'author'), 'committer': raws[s], 'msg': _split(raws[s])[1],
                  'delta': n_delta[s]} for s in new_law]
        # main's published law tip holds every prefix commit (after a back-fill, not the last one in build order)
        parent = base_tip if base_tip and k == sum(1 for s in n_law if s in base) else base[n_law[k - 1]]
    want_tree = _field(raws[built], b'tree').decode()
    if not items and remote and git(repo, 'rev-parse', f'{remote}^{{tree}}') == want_tree:
        return {'kind': 'same', 'new': remote, 'map': mapping, 'added': [], 'laws': 0, 'docs': 0,
                'law_tip': _last_law_change(r_list, r_delta)}
    prev_ct = _ident(_field(_read_commits(repo, [parent])[parent], b'committer'))[2]
    tip = parent

    def committer(raw: bytes | None, cap: bool = False) -> tuple[bytes, int]:
        nonlocal prev_ct
        if raw is None:  # a correction commit: dated now, never before the commit it follows
            prev_ct = max(int(time.time()), prev_ct + 1)
            return f'Lexifina <{slug_email(raws)}> {prev_ct} +0000'.encode(), prev_ct
        c = _field(raw, b'committer')
        gt = c.rindex(b'>')
        ts, tz = c[gt + 1:].split()
        # cap (docs commits): min(build date, now), never before the head, so a docs commit built after midnight UTC
        # (noon local on its docs date) does not leave the next append "future-dated" for hours (2026-11-03).
        prev_ct = max(min(int(ts), int(time.time())) if cap else int(ts), prev_ct + 1)
        return c[:gt + 1] + f' {prev_ct} '.encode() + tz, prev_ct

    def capped_author(line: bytes, ct: int) -> bytes:
        """The docs commit's author line, dated no later than its (capped) committer date."""
        gt = line.rindex(b'>')
        ts, tz = line[gt + 1:].split()
        return line[:gt + 1] + f' {min(int(ts), ct)} '.encode() + tz

    added_items: list[str] = []
    if items:
        # One `git fast-import` for every appended commit: each changes only its own files on top of the tip.
        ref = f'refs/append-tmp/{os.getpid()}-{threading.get_ident()}'
        with tempfile.TemporaryDirectory() as tmp:
            marks = Path(tmp) / 'marks'
            buf = bytearray()
            for i, it in enumerate(items, 1):
                cline = committer(it['committer'])[0]
                buf += f'commit {ref}\nmark :{i}\n'.encode()
                buf += b'author ' + (it['author'] if it['author'] is not None else cline) + b'\n'
                buf += b'committer ' + cline + b'\n'
                buf += f'data {len(it["msg"])}\n'.encode() + it['msg'] + b'\n'
                if i == 1:
                    buf += f'from {tip}\n'.encode()
                for d in it.get('clear', []):
                    buf += b'D ' + d + b'\n'
                for path, v in sorted(it['delta'].items()):
                    if b'\n' in path or path.startswith(b'"'):
                        raise RuntimeError(f'unsupported path {path!r}')
                    buf += (b'D ' + path if v is None else b'M ' + v[0] + b' ' + v[1].encode() + b' ' + path) + b'\n'
                buf += b'\n'
            buf += b'done\n'
            fi = subprocess.run(['git', 'fast-import', '--quiet', '--done', '--date-format=raw',
                                 f'--export-marks={marks}'], cwd=repo, input=bytes(buf), capture_output=True)
            if fi.returncode:
                raise RuntimeError(f'fast-import: {fi.stderr.decode("utf-8", "replace")[-300:]}')
            by_mark = dict(l.split(' ', 1) for l in marks.read_text().split('\n') if l)
        git(repo, 'update-ref', '-d', ref)
        for i, it in enumerate(items, 1):
            sha = by_mark[f':{i}'].strip()
            added_items.append(sha)
            if it.get('src'):
                mapping[it['src']] = sha
        tip = added_items[-1]
    for s in tail:  # the build's documentation commit, with its exact tree, on top
        lines, msg = _split(raws[s])
        body = [l for l in lines if l.startswith(b'tree ')] + [b'parent ' + tip.encode()]
        cline, ct = committer(raws[s], cap=True)
        body += [capped_author(l, ct) for l in lines if l.startswith(b'author ')] + [b'committer ' + cline]
        body += [l for l in lines if not l.startswith((b'tree ', b'parent ', b'author ', b'committer '))]
        tip = _write_object(repo, 'commit', b'\n'.join(body) + b'\n\n' + msg)
        mapping[s] = tip
        added_items.append(tip)
    if not added_items:
        return {'kind': 'same', 'new': remote or parent, 'map': mapping, 'added': [], 'laws': 0, 'docs': 0,
                'law_tip': _last_law_change(r_list, r_delta) if remote else parent}
    if git(repo, 'cat-file', '-t', tip) != 'commit':
        return {'kind': 'rewrite', 'reason': 'internal: the appended tip is not a commit'}
    if tail or remote:
        if git(repo, 'rev-parse', f'{tip}^{{tree}}') != want_tree:
            if tail or _law_files(repo, tip) != _law_files(repo, built):
                return {'kind': 'rewrite', 'reason': 'the appended tip does not have the build\'s final tree'}
    elif _law_files(repo, tip) != _law_files(repo, built):  # a new future branch on main's published law commits
        return {'kind': 'rewrite', 'reason': 'the grafted branch does not have the build\'s law files'}
    if remote and subprocess.run(['git', 'merge-base', '--is-ancestor', remote, tip], cwd=repo).returncode:
        return {'kind': 'rewrite', 'reason': 'internal: the appended tip does not descend from the published tip'}
    law_items = [sha for sha, it in zip(added_items, items) if it.get('src') or it.get('correction')]
    return {'kind': 'append', 'new': tip, 'map': mapping, 'added': added_items,
            'laws': sum(1 for it in items if it.get('src')), 'corrections': corrections, 'correction_reasons': reasons,
            'docs': len(tail), 'backfill': backfill,
            'law_tip': law_items[-1] if law_items else (_last_law_change(r_list, r_delta) if remote else parent)}


def slug_email(raws: dict) -> str:
    """The repo's own address (<slug>-law@lexifina.com), from the committer of any commit the builder made."""
    for raw in raws.values():
        _, email, _, _ = _ident(_field(raw, b'committer'))
        if email.endswith('-law@lexifina.com'):
            return email
    return 'world-law@lexifina.com'


def _last_law_change(seq: list[str], deltas: dict) -> str | None:
    """The last commit of `seq` that changes a provision file (law or correction commit)."""
    for s in reversed(seq):
        if _law_delta(deltas[s]):
            return s
    return None


def _in_force(raw: bytes) -> str | None:
    for line in _split(raw)[1].split(b'\n'):
        if line.startswith(b'In-force:'):
            return line.split(b':', 1)[1].strip().decode()
    return None


CORRECTION_KEYS = ('Kind', 'In-force', 'Corrects', 'Supersedes', 'Reason', 'Act-path', 'Files')


def correction_trailers(act: str, day: str, to: str, supersedes: str | None, reason: str, files: list[bytes]) -> str:
    """The agreed correction trailers (world-law, 2026-11-03), in this order:
        Kind: correction
        In-force: <first day>
        Corrects: <act> <from>..<to>     (open "<from>.." = the newest version)
        Supersedes: <sha|none>           (the published commit that carried the wrong text on that day)
        Reason: <one line>
        Act-path: <corpus-relative folder of the act>
        Files: <path>                    (one line per corrected path, corpus-relative)
    Reading rule: the In-force commit for the day, then each correction whose range covers the day, applied per file; an
    open range ends the day before the act's next ordinary commit touching Act-path."""
    reason = ' '.join(reason.split())
    lines = ['Kind: correction', f'In-force: {day}', f'Corrects: {act} {day}..{to}', f'Supersedes: {supersedes or "none"}',
             f'Reason: {reason}', f'Act-path: {act}']
    lines += [f'Files: {p.decode("utf-8")}' for p in files]
    return '\n'.join(lines) + '\n'


def _plan_by_act(repo: Path, raws: dict, r_list: list[str], r_delta: dict, n_law: list[str], n_delta: dict,
                 email: str) -> tuple:
    """What to append so that every act reads, on every date, as the build says (Alan, 2026-11-02: "bust the held
    work"), without touching published history. Act by act (top-level folder), the published history and the build's
    are both read the way tools/on.py and check.py read them: the newest commit touching the act whose In-force date is
    on or before the day.
    - An act whose published reading already equals the build on every version day, every day before one, and today:
      nothing to append.
    - Versions after everything published (newer versions, or a new act's whole history, older laws found late
      included: D12): the build's own commits are appended, each carrying only its files for such acts.
    - Otherwise (a published version's text, date or order differs): correction commits at the tip, one per build
      version from the first one that reads differently, with the agreed trailers (correction_trailers(): Kind,
      In-force, Corrects, Supersedes, Reason, Act-path, Files), each setting the act to that version's text.
    Returns (items to append in order, number of corrections, reasons) or (reason string, 0, []) to hold."""
    def rows(seq: list[str], deltas: dict) -> tuple[dict, dict]:
        """{act: [(in-force day, state, commit)]} in history order, and each act's final state."""
        out: dict[bytes, list] = {}
        state: dict[bytes, dict] = {}
        for s in seq:
            ld = _law_delta(deltas[s])
            day = _in_force(raws[s])
            if day is None:
                if ld:
                    raise ValueError(f'{_describe(raws[s])} changes provisions but has no In-force trailer')
                continue
            # As check.py and tools/on.py read it: a commit with an In-force trailer belongs to every act folder it
            # touches, even when no provision file changes (a correction that only re-dates a version's text).
            touched = {p.partition(b'/')[0] for p in deltas[s] if b'/' in p} - {b'data', b'tools'}
            for f in touched:
                cur = state.setdefault(f, {})
                for p, v in ld.items():
                    if p.partition(b'/')[0] == f:
                        if v is None:
                            cur.pop(p, None)
                        else:
                            cur[p] = v[1]
                out.setdefault(f, []).append((day, frozenset(cur.items()), s))
        return out, state

    def read(rs: list, day: str):
        for d, st, s in reversed(rs):
            if d <= day:
                return st, s
        return frozenset(), None

    def before(day: str) -> str:
        return (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat() if day > '0001-01-01' else day

    try:
        r_rows, r_state = rows(r_list, r_delta)
        n_rows, n_state = rows(n_law, n_delta)
    except ValueError as e:
        return str(e), 0, []
    r_last_day = max((d for rs in r_rows.values() for d, _, _ in rs), default='')
    keep: dict[str, set[bytes]] = {}  # build commit -> acts whose part of it is appended
    fixes: list[tuple[bytes, int, str]] = []
    for f in sorted(set(r_rows) | set(n_rows)):
        ns, rs = n_rows.get(f, []), r_rows.get(f, [])
        if not rs:  # an act not yet published: its whole history is appended (D12 when it is older)
            for d, st, s in ns:
                keep.setdefault(s, set()).add(f)
            continue
        first = None
        for i, (d, st, s) in enumerate(ns):
            want_prev = read(ns[:i], before(d))[0]
            if read(rs, d)[0] != read(ns, d)[0] or read(rs, before(d))[0] != want_prev:
                first = i
                break
        today = '9999-12-31'
        if first is None:
            if read(rs, today)[0] != read(ns, today)[0]:
                first = len(ns)  # the published act has a later version or text the build no longer has
            else:
                continue
        # Plain append when every published version comes before the first differing one and it reads unchanged
        # until then: the build's versions from `first` on are simply newer.
        rs_last = max(d for d, _, _ in rs)
        if first < len(ns) and ns[first][0] > rs_last and read(rs, today)[0] == read(ns, before(ns[first][0]))[0]:
            for d, st, s in ns[first:]:
                keep.setdefault(s, set()).add(f)
            continue
        fixes.append((f, first, 'published text differs from the corrected build'
                      if first < len(ns) else 'the act was removed or shortened in the corrected build'))
    items = []
    for s in n_law:
        acts = keep.get(s)
        if not acts:
            continue
        delta = {p: v for p, v in n_delta[s].items() if p.partition(b'/')[0] in acts}
        items.append({'src': s, 'author': _field(raws[s], b'author'), 'committer': raws[s],
                      'msg': _split(raws[s])[1], 'delta': delta,
                      'backfill': bool(r_last_day) and (_in_force(raws[s]) or '') < r_last_day})
    reasons = []
    for f, first, why in fixes:
        ns, rs = n_rows.get(f, []), r_rows[f]
        name = f.decode('utf-8', 'replace')
        versions = ns[first:] if first < len(ns) else []
        if not versions:  # removed from the build: one correction that empties the act from its last published day
            versions = [(max(d for d, _, _ in rs), frozenset(), None)]
        tip_state = frozenset(r_state.get(f, {}).items())  # the act's provision files at the published tip
        # Every provision path the act has had (published or built): each correction sets the whole act, so its Files
        # trailer names them all (a path its tree lacks is removed), and a reader applying it file by file gets
        # exactly this version.
        ever = {p for _, sts, _ in rs + ns for p, _ in sts}
        for j, (d, st, s) in enumerate(versions):
            nxt = versions[j + 1][0] if j + 1 < len(versions) else None
            _, sup = read(rs, d)
            to = before(nxt) if nxt else ''
            files = sorted(ever | {p for p, _ in st})
            msg = (f'Correction: {name} as in force from {d}\n\n'
                   f'The published text of {name} differs from the corrected build ({why}). This commit sets it to the '
                   f'build\'s text for {d}..{to}; the published commits stay as they were.\n\n'
                   + correction_trailers(name, d, to, sup, why, files)).encode()
            delta = {p: (b'100644', o) for p, o in st}
            if st == tip_state:
                # Same provision text, another day (an earlier version found, h2 2026-11-03): without a file change
                # the commit would not touch the act, and check.py and tools/on.py, which read an act's history by the
                # commits touching its folder, would never see it (on futuro, which has no act READMEs, it was empty).
                # A note outside the provision files (.txt: not read as law) makes it touch the act; the next docs
                # commit drops it, and history keeps it.
                delta[f + b'/CORRECTIONS.txt'] = (b'100644', _write_object(repo, 'blob', msg))
            tip_state = st
            items.append({'src': None, 'author': None, 'committer': None, 'msg': msg, 'correction': True,
                          'clear': [f], 'delta': delta})
        reasons.append(f'{name}: {why}')
    return items, len(items) - sum(1 for it in items if it.get('src')), reasons

def _law_files(repo: Path, commit: str) -> dict[bytes, bytes]:
    out = subprocess.run(['git', 'ls-tree', '-r', '-z', commit], cwd=repo, capture_output=True).stdout
    files = {}
    for rec in out.split(b'\0'):
        if rec:
            meta, _, path = rec.partition(b'\t')
            if _is_law_path(path):
                files[path] = meta.split()[2]
    return files


# ---------------------------------------------------------------- incremental publishing (2026-11-02)
# A publish builds only what is new: the verified corpus.d parts the published head does not hold yet, as the commits
# the full build would make for them, plus the documentation, on top of the published head. Equivalent to a full build
# followed by append_onto() (same commits, same trees), at a fraction of the CPU. Anything else (a published part,
# corpus.json, the static docs or the shared builder changed; versions in force after the docs date; a law commit
# that spans new and published acts; dates before 1970) falls back to the full build, and a full build still runs
# once a day per repo at a quiet hour as the check gate.

INC_VERSION = 'inc-1'
FULL_EVERY = 24 * 3600
QUIET_HOURS = range(1, 6)  # UTC


def _full_due(state: dict) -> bool:
    """The daily full build (the check gate), at a quiet hour; and always when there is no incremental base."""
    if not state.get('inc'):
        return True
    return time.time() - float(state.get('last_full') or 0) > FULL_EVERY and dt.datetime.now(dt.timezone.utc).hour in QUIET_HOURS


def _shared_digest(folder: Path) -> str:
    """Everything but the corpus.d parts that a build reads or ships."""
    h = hashlib.sha256(INC_VERSION.encode())
    for p in ([COMMON / n for n in ('build.py', 'check.py', 'on.py', 'private.py')] + sorted(COMMON.glob('*.md'))
              + sorted((folder / 'repo').rglob('*')) + [folder / 'corpus.json', folder / 'PUBLISH']):
        if p.is_file() and '__pycache__' not in p.parts:
            h.update(p.as_posix().encode() + b'\0' + p.read_bytes())
        elif p.name == 'PUBLISH':
            h.update(b'no PUBLISH')
    return h.hexdigest()


def _verified_parts(folder: Path) -> dict[str, str]:
    d = folder / 'corpus.d'
    if not d.is_dir():
        return {}
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob('*.json'))
            if p.with_suffix('.PUBLISH').exists()}


def _load_verified(folder: Path) -> tuple[dict, bytes]:
    """build.load() of corpus.json plus the verified parts only (what the main build reads), without touching the
    process environment (several countries build at once in this process): a scratch folder of hard links."""
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / 'corpus.d').mkdir()
        if (folder / 'corpus.json').exists():
            _link(folder / 'corpus.json', t / 'corpus.json')
        for name in _verified_parts(folder):
            _link(folder / 'corpus.d' / name, t / 'corpus.d' / name)
        return B.load(t)


def _link(src: Path, dst: Path) -> None:
    try:
        os.link(src, dst)
    except OSError:
        import shutil
        shutil.copyfile(src, dst)


class _Recorder:
    """build.Writer's interface, recording instead of writing (so write_history() runs without git)."""

    def __init__(self):
        self.mark = 0
        self.heads: dict[str, int] = {}
        self.commits: list[dict] = []

    def commit(self, branch, author, committer, when, message, files, parent=None):
        self.mark += 1
        self.commits.append({'mark': self.mark, 'branch': branch, 'author': author, 'committer': committer,
                             'when': when, 'message': message, 'files': files})
        self.heads[branch] = self.mark
        return self.mark


def _record_history(c: dict, docs_date: str, commits: list[dict]) -> tuple[_Recorder, dict, list[dict]]:
    """build.write_history(), line for line, into a _Recorder (keep the two in step; the equivalence test compares
    the result with a full build)."""
    co = c['country']
    committer = ('Lexifina', f'{co["slug"]}-law@lexifina.com')
    clock = B.Clock(co['tz'])
    w = _Recorder()
    future = co.get('future_branch', 'futuro')
    tags: dict[str, int] = {}
    log = []
    on_future = False
    for x in commits:
        if x['day'] > docs_date and not on_future:
            on_future = True
            if 'main' in w.heads:
                w.heads[future] = w.heads['main']
        branch = future if on_future else 'main'
        if x['kind'] == 'start':
            author, msg, trailers = B.start_message(c, x)
            files = B.act_files(x['act'], x['version']['units'], None)
            touched = [x['act']['slug']]
        else:
            author, msg, trailers = B.change_message(c, x)
            files = {}
            for p in x['parts']:
                files.update(B.act_files(p['act'], p['cur']['units'], p['prev']['units'], p['keys']))
            touched = [p['act']['slug'] for p in x['parts']]
        B.check_trailers(trailers)
        text = '\n'.join(msg).rstrip('\n') + '\n\n' + '\n'.join(trailers) + '\n'
        mark = w.commit(branch, author, committer, clock.stamp(x['day']), text, files)
        for s in touched:
            tags[f'{s}/{x["day"]}'] = mark
        if x['kind'] == 'law':
            tags.setdefault(f'law/{x["law"]}', mark)
        elif x['kind'] == 'start' and x['act'].get('first_law'):
            tags.setdefault(f'law/{x["act"]["first_law"]}', mark)
        log.append({'day': x['day'], 'kind': x['kind'], 'law': x.get('law') or (x['act'].get('first_law') if x['kind'] == 'start' else None),
                    'acts': touched, 'units': len(files), 'branch': branch, 'clamped': x['day'] < '1970-01-01'})
    return w, tags, log


def _fast_import(repo: Path, start: str, commits: list[dict], tz_of=None) -> list[str]:
    """Write `commits` ({author, committer: (name, email), when, message, files, deleteall?, keep?}) on top of
    `start` with one `git fast-import`; committer dates max(own, previous + 1 s). Returns their SHAs."""
    prev_ct = _ident(_field(_read_commits(repo, [start])[start], b'committer'))[2]
    ref = f'refs/inc-tmp/{os.getpid()}-{threading.get_ident()}'
    buf = bytearray()
    for i, x in enumerate(commits, 1):
        ts, tz = x['when'].split()
        # cap (the docs commit): min(build date, now), never before the head, author no later; as append_onto() dates
        # the docs commit, so an incremental publish equals full build + append_onto() and is never future-dated
        # (2026-11-03: São Paulo's head was pushed dated noon local of its docs date, hours ahead).
        prev_ct = max(min(int(ts), int(time.time())) if x.get('cap') else int(ts), prev_ct + 1)
        when = f'{min(int(ts), prev_ct)} {tz}' if x.get('cap') else x['when']
        a, cm = x['author'], x['committer']
        msg = x['message'].encode('utf-8')
        buf += f'commit {ref}\nmark :{i}\n'.encode()
        buf += f'author {a[0]} <{a[1]}> {when}\n'.encode('utf-8')
        buf += f'committer {cm[0]} <{cm[1]}> {prev_ct} {tz}\n'.encode('utf-8')
        buf += f'data {len(msg)}\n'.encode() + msg + b'\n'
        if i == 1:
            buf += f'from {start}\n'.encode()
        if x.get('deleteall'):
            buf += b'deleteall\n'
            for path, oid in sorted(x.get('keep', {}).items()):
                buf += b'M 100644 ' + oid + b' ' + path + b'\n'
        for path in sorted(x['files']):
            text = x['files'][path]
            p = path.encode('utf-8')
            if b'\n' in p or p.startswith(b'"'):
                raise RuntimeError(f'unsupported path {path!r}')
            if text is None:
                buf += b'D ' + p + b'\n'
            else:
                b = text.encode('utf-8')
                buf += b'M 100644 inline ' + p + b'\n' + f'data {len(b)}\n'.encode() + b + b'\n'
        buf += b'\n'
    buf += b'done\n'
    with tempfile.TemporaryDirectory() as tmp:
        marks = Path(tmp) / 'marks'
        fi = subprocess.run(['git', 'fast-import', '--quiet', '--done', '--date-format=raw', f'--export-marks={marks}'],
                            cwd=repo, input=bytes(buf), capture_output=True)
        if fi.returncode:
            raise RuntimeError(f'fast-import: {fi.stderr.decode("utf-8", "replace")[-300:]}')
        by_mark = dict(l.split(' ', 1) for l in marks.read_text().split('\n') if l)
    git(repo, 'update-ref', '-d', ref, check=False)
    return [by_mark[f':{i}'].strip() for i in range(1, len(commits) + 1)]


def _scoped_check(repo: Path, c: dict, raw: bytes, acts: set[str]) -> dict:
    """check.py's record for this corpus on the local main, reading back only `acts` (the new ones); the rest of
    the record (trailers, merges, dates) covers the whole branch, as check.py does. The published acts were read
    back by the full check of the corpus they came from and their commits are unchanged."""
    cat = K.Cat(repo)
    trees: dict = {}
    mismatches, details = 0, []
    sel = [a for a in c['acts'] if a['slug'] in acts]
    by_act = K.all_commits_by_act(repo, 'main', [a['slug'] for a in sel])
    for act in sel:
        slug = act['slug']
        rows = by_act[slug]
        vs = act['versions']
        for i, v in enumerate(vs):
            if i + 1 < len(vs) and vs[i + 1]['from'] == v['from']:
                continue
            before = next((w for w in reversed(vs[:i]) if w['from'] < v['from']), None)
            for day, want in ((v['from'], v), ((dt.date.fromisoformat(v['from']) - dt.timedelta(days=1)).isoformat(), before)):
                h = K.state_on(rows, day)
                if want is None:
                    if h is not None:
                        mismatches += 1
                        details.append(f'{slug}: something is in force on {day}, before the first version')
                    continue
                if h is None:
                    mismatches += 1
                    details.append(f'{slug}: nothing in force on {day}')
                    continue
                files = K.tree_oids(cat, h, slug, trees)
                expect = {f'{slug}/{k}.md': K.blob_oid(u['text']) for k, u in want['units'].items()}
                for f in sorted(set(files) | set(expect)):
                    if files.get(f) != expect.get(f):
                        mismatches += 1
                        if len(details) < 50:
                            details.append(f'{slug} on {day}: {f} differs from version {want["from"]}')
    cat.close()
    trailer_errors, missing_in_force = 0, 0
    out = K.git(repo, 'log', '--no-merges', '--format=%H%x1f%an%x1f%(trailers:only,unfold,separator=%x1e)%x1d', 'main')
    for rec in out.split('\x1d'):
        rec = rec.strip('\n')
        if not rec:
            continue
        h, an, tr = rec.split('\x1f')
        if an == 'Lexifina':
            continue
        keys = [t.split(':', 1)[0] for t in tr.split('\x1e') if t]
        if not keys:
            trailer_errors += 1
        elif 'In-force' not in keys:
            missing_in_force += 1
    merges = int(K.git(repo, 'rev-list', '--merges', '--count', 'main').strip())
    cts = [int(x) for x in K.git(repo, 'log', '--first-parent', '--reverse', '--format=%ct', 'main').split()]
    backwards = sum(1 for a, b in zip(cts, cts[1:]) if b < a)
    now = int(time.time())
    future_dated = sum(1 for x in cts[:-1] if x > now) + (1 if cts and cts[-1] > now + 2 * 86400 else 0)
    return {'acts': len(c['acts']), 'versions': sum(len(a['versions']) for a in c['acts']), 'mismatches': mismatches,
            'trailer_errors': trailer_errors, 'missing_in_force': missing_in_force, 'merges': merges,
            'backwards': backwards, 'future_dated': future_dated, 'details': details,
            'corpus_sha256': hashlib.sha256(raw).hexdigest()}


def incremental(slug: str, folder: Path, repo: Path, state: dict, day: str) -> dict:
    """Prepare the local main as the published head plus only what is new (see the section comment). Returns
    {'ok': True, 'tip': sha, 'parts': ..., 'check': record, 'new_acts': n, 'commits': n}, {'ok': 'same'} when no verified
    part is new, or {'ok': False, 'why': reason} to fall back to the full build. Never pushes."""
    inc = state.get('inc') or {}
    if not inc:
        return {'ok': False, 'why': 'no incremental base yet (first full build)'}
    if inc.get('version') != INC_VERSION:
        return {'ok': False, 'why': 'incremental format changed'}
    if inc.get('shared') != _shared_digest(folder):
        return {'ok': False, 'why': 'corpus.json, PUBLISH, the static docs or the shared builder changed'}
    remote = git(repo, 'rev-parse', '-q', '--verify', 'refs/remotes/origin/main', check=False)
    if not remote or remote != inc.get('head'):
        return {'ok': False, 'why': 'the published main moved since the last publish from here'}
    if (inc.get('check') or {}).get('mismatches') != 0:
        return {'ok': False, 'why': 'the last full check was not clean'}
    parts = _verified_parts(folder)
    old = inc.get('parts') or {}
    changed = [n for n, h in old.items() if parts.get(n) != h]
    if changed:
        return {'ok': False, 'why': f'published part changed or withdrawn: {", ".join(changed[:3])}'}
    new_parts = [n for n in parts if n not in old]
    if not new_parts:
        return {'ok': 'same'}
    future = (json.loads((folder / 'corpus.d' / new_parts[0]).read_text(encoding='utf-8')).get('country') or {}).get(
        'future_branch') or 'futuro'
    if git(repo, 'ls-remote', '--heads', 'origin', future, check=False):
        return {'ok': False, 'why': f'the remote has a {future} branch (kept in step by the full build)'}
    new_acts: set[str] = set()
    for n in new_parts:
        new_acts |= {a['slug'] for a in json.loads((folder / 'corpus.d' / n).read_text(encoding='utf-8')).get('acts', [])}
    c, raw = _load_verified(folder)
    errs = B.validate(c)
    if errs:
        return {'ok': False, 'why': f'corpus has problems ({errs[0][:80]})'}
    c['_docs_date'] = day
    rec, tags, log = _record_history(c, day, B.plan(c))
    new, pub = [], 0
    for x, e in zip(rec.commits, log):
        acts = set(e['acts'])
        if e['branch'] != 'main':
            return {'ok': False, 'why': 'versions in force after the docs date (future branch)'}
        if acts & new_acts and acts - new_acts:
            return {'ok': False, 'why': f'a law commit spans new and published acts ({e.get("law")} on {e["day"]})'}
        if acts <= new_acts:
            if e['clamped']:
                return {'ok': False, 'why': 'a new act dated before 1970 (placeholder dates shift)'}
            new.append(x)
        else:
            pub += 1
    r_law = sum(1 for l in git(repo, 'log', '--first-parent', '--format=%an', remote).split('\n') if l and l != 'Lexifina')
    if pub != r_law:
        return {'ok': False, 'why': f'the published main has {r_law} law commits, the corpus {pub}'}
    if not new:
        return {'ok': 'same'}
    git(repo, 'config', 'gc.auto', '0')
    shas = _fast_import(repo, remote, new)
    law_tip = shas[-1]
    git(repo, 'update-ref', 'refs/heads/main', law_tip)
    future = c['country'].get('future_branch', 'futuro')
    git(repo, 'update-ref', '-d', f'refs/heads/{future}', check=False)
    chk = _scoped_check(repo, c, raw, new_acts)
    if chk['mismatches'] or chk['trailer_errors'] or chk['missing_in_force'] or chk['merges'] or chk['backwards']:
        return {'ok': False, 'why': f'scoped check: {chk["mismatches"]} mismatches {chk["details"][:2]}'}
    record = {k: v for k, v in chk.items() if k != 'details'}
    ver_path = folder / 'verification.json'
    ver = json.loads(ver_path.read_text(encoding='utf-8')) if ver_path.exists() else {}
    ver['check'] = record
    ver_path.write_text(json.dumps(ver, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    # The documentation commit, exactly as the full build makes it: the law files of the last law commit plus the
    # docs files (a whole new tree, so files the old docs had and the new ones do not are gone).
    files = B.docs_files(c, folder, raw, log, tags, day)
    co = c['country']
    committer = ('Lexifina', f'{co["slug"]}-law@lexifina.com')
    docs = {'author': committer, 'committer': committer, 'when': B.Clock(co['tz']).stamp(day),
            'message': f'Documentation, tables, tools and REPRODUCE.md\n\nBuilt from corpus.json '
                       f'(sha256 {hashlib.sha256(raw).hexdigest()}), data retrieved {day}.\n',
            'files': files, 'deleteall': True, 'cap': True,
            'keep': {p: o for p, o in _law_files(repo, law_tip).items() if p.decode('utf-8') not in files}}
    tip = _fast_import(repo, law_tip, [docs])[0]
    git(repo, 'update-ref', 'refs/heads/main', tip)
    # Local tags: exactly the new commits' tags (publish() pushes only tags on commits it adds).
    marks = {x['mark']: s for x, s in zip(new, shas)}
    lines = [f'delete {r}\n' for r in git(repo, 'for-each-ref', '--format=%(refname)', 'refs/tags').split('\n') if r]
    lines += [f'update refs/tags/{t} {marks[m]}\n' for t, m in tags.items() if m in marks]
    if lines:
        git(repo, 'update-ref', '--stdin', data=''.join(lines).encode('utf-8'))
    return {'ok': True, 'tip': tip, 'parts': parts, 'check': record, 'new_acts': len(new_acts), 'commits': len(new)}


def _future_branch(repo: Path) -> str | None:
    """The corpus's future branch name, from the build's data/repo.json on main."""
    try:
        return json.loads(git(repo, 'show', 'refs/heads/main:data/repo.json')).get('future_branch') or None
    except (RuntimeError, ValueError):
        return None


def _build_law_tip(repo: Path, ref: str) -> str | None:
    """The newest first-parent commit of `ref` not authored by 'Lexifina' (the build's last law commit)."""
    for line in git(repo, 'log', '--first-parent', '--format=%H%x1f%an', ref, check=False).splitlines():
        sha, _, author = line.partition('\x1f')
        if author != 'Lexifina':
            return sha
    return None


def publish(slug: str, repo: Path, branches: list[str], dry_run: bool = False, check=None) -> str:
    """Push `branches` (local names, same name on the remote) and the tags to the shared repo, append-only (user,
    2026-11-02: "end force-pushes everywhere"; published history only grows by fast-forward):
    - each branch goes through append_onto(): the build's new law commits and its new documentation commit are written
      on top of the published tip (same trees, authors, author dates and messages), so the push is a fast-forward and
      the published docs commit stays in history; a branch with nothing new is skipped;
    - a build whose law history differs inside the published one (an older commit inserted, a published law commit
      changed, moved or removed) is a rewrite: pushed only if REWRITE-APPROVED.txt names that exact old -> new, with
      --force-with-lease; otherwise recorded with its reason in REWRITE-PENDING.json and nothing is pushed for the repo;
    - `check()` (check.py on the appended branches) must be clean before anything is pushed;
    - tags: only tags on the newly written commits are created, at their new SHAs; a tag the remote already holds is
      never moved or deleted (a name clash at another object is skipped and logged);
    - everything that would be added goes through private.audit_push() first; any finding stops the push."""
    git(repo, 'config', 'gc.auto', '0', check=False)  # no auto-gc mid-publish (each full build re-creates the repo)
    # Only the branches the remote already holds: one missing name (a first `zukunft`/`future`) fails the whole fetch
    # and leaves origin/main stale, which made the first push of such a repo fail.
    have = {l.partition('\t')[2] for l in git(repo, 'ls-remote', '--heads', 'origin', check=False).splitlines()}
    # The future branch the remote holds although this build has none (no version in force after the docs date any
    # more, e.g. the future act was withdrawn): it is published too, as the build's law tip appended onto the remote
    # one, so corrections reach it. Left out, the remote future branch kept the old text while check.py, run here on a
    # repo without that branch, read only main and passed (h2 in test_append_dell.py, 2026-11-03). check.py reads the
    # future branch whenever one exists, so every branch it would read on the remote is now checked before the push.
    future = _future_branch(repo)
    if future and 'main' in branches and future not in branches and f'refs/heads/{future}' in have:
        if not git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{future}', check=False):
            law_tip = _build_law_tip(repo, 'refs/heads/main')
            if not law_tip:
                return f'NOT pushed: the remote has {future} but the build has no law commit to keep it in step'
            git(repo, 'update-ref', f'refs/heads/{future}', law_tip)
        branches = [*branches, future]
    there = [b for b in branches if f'refs/heads/{b}' in have]
    if there:
        git(repo, 'fetch', '-q', '--no-tags', 'origin', *[f'+refs/heads/{b}:refs/remotes/origin/{b}' for b in there],
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
    new_tags: dict[str, str] = {}  # tag ref -> new commit, for commits written by append_onto()
    appended: list[str] = []
    main_map: dict[str, str] = {}
    main_law_tip = None
    for b in branches:
        new = git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{b}', check=False)
        old = git(repo, 'rev-parse', '-q', '--verify', f'refs/remotes/origin/{b}', check=False) if b in there else ''
        if not new:
            plan.append(f'{b} same')
            continue
        g = append_onto(repo, old or None, new, base=main_map if b != 'main' else None,
                        base_tip=main_law_tip if b != 'main' else None)
        if b == 'main':
            main_map = g.get('map', {})
            main_law_tip = g.get('law_tip')
        if g['kind'] == 'rewrite':
            standing = standing_approval(slug, repo, b, old, new, local_tags, remote_tags)  # '' since 2026-11-02
            if (slug, f'refs/heads/{b}', old, new) in approved or standing:
                found = private.audit_push(repo, new, old)
                if found:
                    return f'NOT pushed: privacy audit found {len(found)} in {b}: {"; ".join(found[:5])}'
                leases[f'refs/heads/{b}'] = old
                plan.append(f'{b} approved rewrite {old[:9]}->{new[:9]} ({g["reason"]})')
                refs.append(f'refs/heads/{b}:refs/heads/{b}')
                continue
            replaced = git(repo, 'rev-list', '--count', old, f'^{new}', check=False) if old else 0
            rewrites.append({'ref': f'refs/heads/{b}', 'old': old, 'new': new, 'reason': g['reason'],
                             'replaces_commits': int(replaced or 0),
                             'adds_commits': int(git(repo, 'rev-list', '--count', new, *([f'^{old}'] if old else [])) or 0)})
            continue
        if g['kind'] == 'same':
            plan.append(f'{b} same')
            continue
        tip = g['new']
        found = private.audit_push(repo, tip, old or None)
        if found:
            return f'NOT pushed: privacy audit found {len(found)} in {b}: {"; ".join(found[:5])}'
        git(repo, 'update-ref', f'refs/build/{b}', new)  # the build as made, for comparison
        git(repo, 'update-ref', f'refs/heads/{b}', tip)
        what = (f'+{g["laws"]} law commit{"s" if g["laws"] != 1 else ""}' + (' back-filled at the end' if g.get('backfill')
                else '') + (f', +{g["corrections"]} correction{"s" if g["corrections"] != 1 else ""} '
                            f'({"; ".join(g.get("correction_reasons", [])[:3])})' if g.get('corrections') else '')
                + (f', +{g["docs"]} docs' if g['docs'] else ''))
        plan.append(f'{b} {"append" if old else "new branch"} {old[:9] or "(new)"}->{tip[:9]} ({what}; fast-forward)')
        refs.append(f'refs/heads/{b}:refs/heads/{b}')
        appended.append(b)
        added = set(g['added'])
        for t, s in local_tags.items():
            m = g['map'].get(s)
            if m in added:
                new_tags.setdefault(t, m)
    if rewrites:
        if not dry_run:
            note_pending(slug, {'repo': f'lexifina/{slug}-law', 'at': _now(), 'rewrites': rewrites})
        return ('NOT pushed: needs a rewrite the user has not approved ('
                + ', '.join(f'{r["ref"][11:]} {r["old"][:9]}->{r["new"][:9]}: {r["reason"]}' for r in rewrites) + ')' + ('' if dry_run else '; recorded in world-law/REWRITE-PENDING.json'))
    if not dry_run:
        note_pending(slug, None)
    if appended and check is not None:
        # check.py on what would be published (the local branches now point at the appended tips).
        ok, why = check()
        if not ok:
            return f'NOT pushed: {why}'
    clashes = []
    if leases:
        # An approved rewrite: its tags follow it (a tag moves only with the user's yes for that rewrite).
        moved = [t for t, s in local_tags.items() if t in remote_tags and remote_tags[t] != s]
        for t in moved:
            leases[t] = remote_tags[t]
        refs += [f'{t}:{t}' for t, s in sorted(local_tags.items()) if remote_tags.get(t) != s]
    for t, m in sorted(new_tags.items()):
        if t in remote_tags:  # never moved or deleted; a clash at another object is skipped and logged
            if remote_tags[t] != m:
                clashes.append(t)
            continue
        refs.append(f'{m}:{t}')
    if clashes and not dry_run:
        with open(Path(__file__).resolve().parent / 'logs' / 'tag-clashes.log', 'a', encoding='utf-8') as f:
            f.write(f'{_now()} {slug}-law: {len(clashes)} new tags already on the remote at another commit, '
                    f'not pushed: {" ".join(t[10:] for t in clashes)}\n')
    kept = sum(1 for t in remote_tags if t not in local_tags)
    summary = f'{"; ".join(plan)}; {sum(1 for r in refs if r.partition(":")[2].startswith("refs/tags/"))} tags to push' + \
        (f'; {len(clashes)} new tags skipped (name already on the remote)' if clashes else '') + \
        (f'; {kept} remote-only tags left alone' if kept else '')
    if not refs:
        return f'nothing to push ({summary})'
    bad = push_identities(repo, [r.partition(':')[0] for r in refs])
    if bad:
        return f'NOT pushed: {bad}'
    if dry_run:
        return f'dry run, would push: {summary}'
    # Windows caps a command line at about 32k characters: push the branches first, then the tags in batches.
    heads = [r for r in refs if not r.partition(':')[2].startswith('refs/tags/')]
    tag_refs = [r for r in refs if r.partition(':')[2].startswith('refs/tags/')]
    if len(' '.join(refs)) + len(' '.join(f'{k}:{v}' for k, v in leases.items())) * 2 < 20000:
        return f'{push(repo, *refs, leases=leases)} ({summary})'
    result = push(repo, *heads, leases={k: v for k, v in leases.items() if k.startswith('refs/heads/')}) if heads \
        else 'pushed'
    if not leases and not result.startswith('push failed'):
        # Only new tags (none is on the remote): a throwaway bare repo per batch of 1,000 that borrows this repo's
        # objects and holds only that batch, pushed with one glob refspec (push_clean.fast_push_new_tags' method).
        return f'{push_new_tags(repo, tag_refs)} ({summary}; tags in batches of 1,000)'
    for i in range(0, len(tag_refs), 60):  # each moved tag also carries a --force-with-lease argument
        if result.startswith('push failed'):
            break
        batch = tag_refs[i:i + 60]
        dsts = [t.partition(':')[2] for t in batch]
        result = push(repo, *batch, leases={t: leases[t] for t in dsts if t in leases})
    return f'{result} ({summary}; in batches)'


def push_identities(repo: Path, srcs: list[str]) -> str:
    """The identity check run just before every push (on top of audit_push): `git log <what is pushed> --not
    --remotes=origin --format='%ae %ce'`, i.e. origin/main..HEAD for each pushed ref. Every author and committer must be
    a lexifina.com or .invalid address and never the personal one; in WSL (whose git config deliberately has no
    identity) the personal address must also be known, or nothing is pushed. '' when clean, else why not."""
    personal = private._personal_emails()
    if IN_WSL and not personal:
        return 'personal address unknown in WSL (GITLAW_PERSONAL_GITCONFIG); the identity check cannot run'
    out = subprocess.run(['git', 'log', '--format=%ae %ce', *dict.fromkeys(srcs), '--not', '--remotes=origin', '--'],
                         cwd=repo, capture_output=True, text=True, encoding='utf-8')
    if out.returncode:
        return f'identity check failed: {out.stderr.strip()[:200]}'
    bad = sorted({e for line in out.stdout.splitlines() for e in line.split()
                  if e.lower() in personal or not e.lower().endswith(('lexifina.com', '.invalid'))})
    # The personal address itself is never written into a status or log line.
    return (f'commit identity outside lexifina.com in what would be pushed: '
            f'{", ".join("<personal address>" if e.lower() in personal else e for e in bad)}') if bad else ''


CREDENTIAL = re.compile(r'(code|key|token|sig|apikey)=[A-Za-z0-9_%=-]{20,}')


def wip(slug: str, folder: Path, repo: Path, dry_run: bool = False) -> str:
    """Snapshots scripts/<slug>-law onto branch wip/<slug>-law of the PRIVATE lexifina/world-law-ops (never the public
    country repo), so unfinished work leaves this machine. Each snapshot extends the branch: never forced."""
    files = []
    found = []
    # Skipped folders are pruned while walking (.cache and .tmp* builds can hold tens of thousands of files).
    for top, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.tmp') and d != '.git']
        found += [Path(top, n) for n in names]
    for p in sorted(found):
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
        shas: dict[str, str] = {}
        plain = []
        for rel, p in files:
            data = p.read_bytes()
            text = data.decode('utf-8', 'replace') if p.suffix in ('.py', '.sh', '.md', '.json', '.txt', '.csv') else ''
            if text and (private.HOME.search(text) or CREDENTIAL.search(text)):
                # Even in the private repo: no machine path, and no credential an agent noted down.
                clean = CREDENTIAL.sub(lambda m: f'{m.group(1)}=<redacted>', private.scrub(text))
                shas[rel] = git(repo, 'hash-object', '-w', '--stdin', data=clean.encode('utf-8'))
            else:
                plain.append((rel, p))
        # Two git processes for all the plain files, not two per file.
        if plain:
            out = git(repo, 'hash-object', '-w', '--stdin-paths', data=''.join(f'{p}\n' for _, p in plain).encode('utf-8'))
            shas.update(zip((rel for rel, _ in plain), out.split()))
        if files:
            git(repo, 'update-index', '--add', '--index-info', env=env,
                data=''.join(f'100644 {shas[rel]}\twip/{rel}\n' for rel, _ in files).encode('utf-8'))
        tree = git(repo, 'write-tree', env=env)
    branch = f'wip/{slug}-law'
    # Tracked outside refs/remotes/: a plain `git fetch ops` creates refs/remotes/ops/wip/<slug>-law, and git then
    # cannot create refs/remotes/ops/wip, so the fetch failed, the snapshot had no parent and every push was
    # rejected as non-fast-forward (2026-11-03).
    git(repo, 'fetch', '-q', '--no-tags', 'ops', f'+refs/heads/{branch}:refs/autopush/ops-wip', check=False)
    parent = git(repo, 'rev-parse', '-q', '--verify', 'refs/autopush/ops-wip', check=False)
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
    if not IN_WSL and not dry_run and wsl_migrated(slug, state):
        # Its docs commit names the WSL toolchain: an NTFS build would flip it back (see "WSL ext4").
        return {'main': 'NOT built: this repo builds in WSL only (WSL-MIGRATED.txt / .autopush.json wsl)'}
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
    # This country's rewrite approvals change what may be pushed. private.py is left out on purpose: it only shapes
    # tools/ and the docs commit, and hashing it made one edit rebuild every corpus at once (the next real change
    # brings the docs up to date; audit_push still guards every push).
    h.update(repr(sorted(a for a in approved_rewrites() if a[0] == slug)).encode())
    sha = h.hexdigest()
    # A failed push is retried even when nothing changed (e.g. a first push that lost a race with a new branch).
    if (state.get('built_sha') == sha and not dry_run and not _fail_retry(state)
            and not _retry_due(state)):
        return {'main': f'unchanged since {state.get("built_at")} ({state.get("result")})'}
    if not dry_run:
        state['publish_mode'] = PUBLISH_MODE  # this visit is made under the current rules, whatever it ends in
    day = docs_date(corpus)
    future = corpus['country'].get('future_branch', 'futuro')
    parts = sorted((folder / 'corpus.d').glob('*.json')) if (folder / 'corpus.d').exists() else []
    unverified = [p.name for p in parts if not p.with_suffix('.PUBLISH').exists()]
    published = (folder / 'PUBLISH').exists()

    def build_check(verified_only: bool) -> tuple[bool, dict]:
        env = {**os.environ, 'GITLAW_VERIFIED_PARTS_ONLY': '1' if verified_only else '0',
               'GITLAW_NO_CHECKOUT': '1'}  # pushed from objects; no working tree to write or delete
        py = [sys.executable, '-X', 'utf8']
        # Builds and checks run below normal priority so pushes and fetches are never starved behind them.
        low = {'creationflags': 0x00004000} if os.name == 'nt' else {}  # BELOW_NORMAL_PRIORITY_CLASS
        ver_path = folder / 'verification.json'
        # REPRODUCE.md quotes the check recorded for this exact corpus. When this pass's check is new (first build of
        # this corpus, or the verified-only main build after the full one), build once more so it quotes it.
        for attempt in range(2):
            before = json.loads(ver_path.read_text(encoding='utf-8')).get('check') if ver_path.exists() else None
            b = subprocess.run(py + [str(COMMON / 'build.py'), str(folder), '--repo', str(repo), '--docs-date', day],
                               capture_output=True, text=True, encoding='utf-8', env=env, **low)
            if b.returncode:
                return False, {'stage': 'build', 'error': (b.stderr or b.stdout)[-3000:]}
            c = subprocess.run(py + [str(COMMON / 'check.py'), str(repo), '--corpus', str(corpus_path), '--write'],
                               capture_output=True, text=True, encoding='utf-8', env=env, **low)
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
    preview_key = hashlib.sha256(raw + _shared_digest(folder).encode()).hexdigest()
    if (not published or unverified) and state.get('preview_key') != preview_key:
        ok, info = build_check(False)
        if not ok:
            state.update(built_sha=sha, built_at=_now(), result=f'{info["stage"]} failed, not pushed')
            return {'main': f'{info["stage"]} failed, not pushed', **info}
        out['preview'] = f'built and checked locally at {git(repo, "rev-parse", "--short", "main")} (not published)'
        out['check'] = info['check']
        if not dry_run:
            state['preview_key'] = preview_key
        if not published:
            state.update(built_sha=sha, built_at=_now(), result=out['preview'])
            return {'main': f'{out["preview"]}; main waits for PUBLISH', **out}
    if not published:  # preview inputs unchanged since the last preview build: nothing to do until PUBLISH
        state.update(built_sha=sha, built_at=_now())
        return {'main': f'{state.get("result", "preview unchanged")}; main waits for PUBLISH', **out}
    # 2. main holds only what has been verified against the official text: corpus.json (PUBLISH) and each corpus.d
    #    part whose owner wrote <part>.PUBLISH. Tags are pruned to match, so a part's tags leave with it.
    owner = remote_main_owner(slug, repo)
    if owner != 'ours':
        # Never overwrite a main this pipeline did not make: another session may have built the country with its
        # own builder (Spain, Austria, Italy, ...). The build stays on preview; a person decides.
        state.update(built_sha=sha, built_at=_now(), result=f'main NOT pushed: {owner}')
        return {'main': f'main NOT pushed: remote main is {owner}; build kept on preview only', **out}
    if not _full_due(state):
        t0 = time.process_time()
        try:
            inc = incremental(slug, folder, repo, state, day)
        except Exception as e:  # never fatal: the full build follows
            inc = {'ok': False, 'why': f'incremental error: {str(e)[:150]}'}
        if inc['ok'] == 'same':
            if not dry_run:
                state.update(built_sha=sha, built_at=_now(), result='nothing to push (no new verified part; incremental)')
            return {'main': 'nothing to push (no new verified part; incremental)', **out}
        if inc['ok'] is True:
            def check_inc() -> tuple[bool, str]:
                if git(repo, 'rev-parse', 'refs/heads/main') != inc['tip']:
                    return False, 'check failed: publish would push another tip than the incremental build'
                cts = [int(x) for x in git(repo, 'log', '--first-parent', '--format=%ct', 'main').split()]
                now = time.time()
                if any(x > now for x in cts[1:]) or (cts and cts[0] > now + 2 * 86400):
                    state['retry_after'] = max(x for x in cts if x > now) + 1
                    return False, 'appended commits would be dated ahead of now; waits'
                return True, ''
            state.pop('retry_after', None)
            result = publish(slug, repo, ['main'], dry_run=dry_run, check=check_inc)
            out['incremental'] = (f'{inc["commits"]} commits for {inc["new_acts"]} new acts, '
                                  f'{time.process_time() - t0:.1f} s CPU in this process')
            if not dry_run:
                if result.startswith(('pushed', 'nothing to push')):
                    state['inc'] = {**state['inc'], 'head': inc['tip'], 'parts': inc['parts'], 'check': inc['check']}
                state.update(built_sha=None if result.startswith('push failed') else sha, built_at=_now(),
                             result=f'{result[:200]} {inc["tip"][:8]} (incremental)')
            return {'main': f'{result} {inc["tip"][:8]} (incremental)', **out, 'check': inc['check']}
        out['incremental'] = f'full build: {inc["why"]}'
    ok, info = build_check(True)
    if not ok:
        state.update(built_sha=sha, built_at=_now(), result=f'main {info["stage"]} failed, not pushed')
        return {'main': f'main {info["stage"]} failed, not pushed', **out, **info}
    if not git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{future}', check=False) and             git(repo, 'ls-remote', '--heads', 'origin', future, check=False):
        # No version is in force after the docs date any more, but the remote still has the future branch: keep it in
        # step with main's laws (main's last law commit; the build ends main with the docs commit), so readers of the
        # future branch never see older text than main.
        git(repo, 'update-ref', f'refs/heads/{future}', 'refs/heads/main~1')
    branches = ['main'] + ([future] if git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{future}', check=False) else [])

    def check_appended() -> tuple[bool, str]:
        """check.py (not --write: verification.json keeps the build's own check) on the appended branches. Same trees
        as the build, in the same order, so it must be as clean as the build's check."""
        env = {**os.environ, 'GITLAW_VERIFIED_PARTS_ONLY': '1'}
        low = {'creationflags': 0x00004000} if os.name == 'nt' else {}
        c = subprocess.run([sys.executable, '-X', 'utf8', str(COMMON / 'check.py'), str(repo), '--corpus',
                            str(corpus_path)], capture_output=True, text=True, encoding='utf-8', env=env, **low)
        try:
            chk = json.loads(c.stdout)
        except ValueError:
            return False, f'check failed on the appended history: {(c.stderr or c.stdout)[-300:]}'
        out['check_appended'] = {k: v for k, v in chk.items() if k != 'details'}
        if c.returncode == 0:
            return True, ''
        bad = {k: chk[k] for k in ('mismatches', 'trailer_errors', 'missing_in_force', 'merges', 'backwards',
                                   'future_dated') if chk.get(k)}
        if set(bad) == {'future_dated'}:
            # Appended commits follow the published docs commit (noon local on its docs date), so before that time
            # they would be dated ahead of now: wait for it rather than date anything backwards.
            cts = [int(x) for x in git(repo, 'log', '--first-parent', '--format=%ct', 'main').split()[1:]]
            state['retry_after'] = max([x for x in cts if x > time.time()] or [int(time.time()) + 600]) + 1
            return False, (f'appended commits would be dated ahead of now; waits until '
                           f'{dt.datetime.fromtimestamp(state["retry_after"], dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}')
        return False, f'check failed on the appended history: {bad} {chk.get("details", [])[:3]}'

    state.pop('retry_after', None)
    result = publish(slug, repo, branches, dry_run=dry_run, check=check_appended)
    head = git(repo, 'rev-parse', '--short', 'main')
    # A failed push is retried on the next pass: only a pushed (or unchanged, or waiting-for-approval) build is
    # remembered as done. A new approval changes the hash above, so an approved rewrite is pushed on the next pass.
    # One that waits for its dates (retry_after) is rebuilt once that time has passed.
    if not dry_run:
        state.update(built_sha=None if result.startswith('push failed') else sha,
                     built_at=_now(), result=f'{result[:200]} {head}')
        state['last_full'] = time.time()
        if result.startswith(('pushed', 'nothing to push')) and branches == ['main']:
            tip = git(repo, 'rev-parse', 'refs/heads/main' if result.startswith('pushed') else 'refs/remotes/origin/main')
            state['inc'] = {'version': INC_VERSION, 'head': tip, 'parts': _verified_parts(folder),
                            'shared': _shared_digest(folder), 'check': info.get('check')}
        else:
            state.pop('inc', None)
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


CLAIMS = ROOT / 'scripts' / 'world-law' / 'claims'
SESSION = 'gitlaw-scraper-dell'


def owned() -> set[str]:
    """OWN plus every repo claimed by this session in scripts/world-law/claims/<slug>-law.txt (re-read on each call),
    minus FOREIGN. Claimed Phase 2 countries then stream through this loop as their parts get PUBLISH."""
    out = set(OWN)
    try:
        for c in CLAIMS.glob('*-law.txt'):
            try:
                if c.read_text(encoding='utf-8', errors='replace').strip().startswith(SESSION):
                    out.add(c.name[:-len('-law.txt')])
            except OSError:
                pass
    except OSError:
        pass
    return out - FOREIGN


def _folder_sig(folder: Path, slug: str) -> str:
    """A digest of (path, mtime, size) for every file a visit reads: the country folder (no caches or scratch
    folders), the shared builder, and this country's rewrite approvals. Stat calls only, no file contents."""
    h = hashlib.sha256()
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.tmp') and d != '.git')
        for f in sorted(files):
            if f.startswith('.autopush') or f == 'BUILD_STATUS.json':
                continue
            try:
                st = os.stat(os.path.join(root, f))
            except OSError:
                continue
            h.update(f'{root}/{f}\0{st.st_mtime_ns}\0{st.st_size}\n'.encode('utf-8', 'replace'))
    for n in ('build.py', 'check.py', 'on.py'):
        st = (COMMON / n).stat()
        h.update(f'{n}\0{st.st_mtime_ns}\0{st.st_size}\n'.encode())
    h.update(repr(sorted(a for a in approved_rewrites() if a[0] == slug)).encode())
    return h.hexdigest()


STALL_AFTER = 2 * 3600  # a claimed repo whose folder (cache included) has not changed for this long is reported


def _newest_activity(folder: Path) -> float:
    """Newest change anywhere in a country folder: directory mtimes move whenever a file is added or replaced, so
    walking directories only (not every cached file) is enough to see a fetcher or driver at work."""
    newest = 0.0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        try:
            newest = max(newest, os.stat(root).st_mtime)
        except OSError:
            pass
        if root == str(folder) or root.endswith('corpus.d'):
            for f in files:
                if f in ('.autopush.json', 'BUILD_STATUS.json'):
                    continue
                try:
                    newest = max(newest, os.stat(os.path.join(root, f)).st_mtime)
                except OSError:
                    pass
    return newest


def watchdog() -> None:
    """Every ~10 min: report each claimed repo with no activity for STALL_AFTER as STALLED (once per stall) in
    logs/STALLED.txt, so a dead driver is noticed in hours, not a day (three were dead 14-24 h on 2026-11-01)."""
    out = Path(__file__).resolve().parent / 'logs' / 'STALLED.txt'
    seen_path = Path(__file__).resolve().parent / 'logs' / '.stalled-seen.json'
    try:
        seen = json.loads(seen_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        seen = {}
    now = time.time()
    for slug in sorted(owned()):
        folder = ROOT / 'scripts' / f'{slug}-law'
        if not folder.is_dir():
            continue
        last = _newest_activity(folder)
        if now - last > STALL_AFTER:
            if seen.get(slug) != int(last):
                with open(out, 'a', encoding='utf-8') as f:
                    f.write(f'{_now()} STALLED {slug}-law: no change in its folder for {int((now - last) / 3600)} h '
                            f'(claim still held)\n')
                print(f'STALLED {slug}-law', flush=True)
                seen[slug] = int(last)
        else:
            seen.pop(slug, None)
    seen_path.write_text(json.dumps(seen, indent=1) + '\n', encoding='utf-8')


# Bumped when publish() changes what it would push: every repo is then visited once more under the new rules.
PUBLISH_MODE = 'append-v2-d12'  # v2: D12 end blocks for older laws found late


def _fail_retry(state: dict) -> bool:
    """Whether a visit that ended badly should run again although no input changed. Transient failures (a push or fetch
    that failed: network, races) retry on the next pass. Deterministic refusals (held rewrite, check or build failed,
    NOT pushed) only retry hourly: rebuilding them every pass burned cores for nothing (2026-11-02)."""
    r = str(state.get('result', ''))
    if 'fail' not in r and 'NOT pushed' not in r:
        return False
    if any(k in r for k in ('check failed', 'build failed', 'NOT pushed', 'rewrite')):
        try:
            last = dt.datetime.fromisoformat(str(state.get('built_at', '')).replace('Z', '+00:00')).timestamp()
        except ValueError:
            return True
        return time.time() - last > 3600
    return True


def _retry_due(state: dict) -> bool:
    """True when a repo must be visited again although no file changed: an append that waited for its commit dates
    (state['retry_after']) once that time has passed, or a refusal made under an older PUBLISH_MODE (only those: a
    repo that published cleanly is not rebuilt just because the rules grew)."""
    r = str(state.get('result', ''))
    if state.get('publish_mode') != PUBLISH_MODE and ('NOT pushed' in r or 'fail' in r):
        return True
    return bool(state.get('retry_after')) and time.time() >= state['retry_after']


def unchanged(slug: str) -> bool:
    """True when nothing one() reads has changed since a visit that ended cleanly (stat calls only)."""
    folder = ROOT / 'scripts' / f'{slug}-law'
    state_path = folder / '.autopush.json'
    try:
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
        return (state.get('sig') == _folder_sig(folder, slug) and bool(state.get('built_sha'))
                and bool(state.get('wip_ok')) and not _fail_retry(state) and not _retry_due(state))
    except (OSError, ValueError):
        return False


# ---------------------------------------------------------------- WSL ext4 (2026-11-03)
# A repo's whole build/append/publish path (fetch of the published main, full or incremental build, append_onto,
# check.py, audit_push, the identity check and the push) runs inside WSL with the repository on ext4
# (~/gitlaw-builds/autopush-dell/<slug>-law), the same code in a child process (--wsl-child). Builds there skip the
# NTFS/Defender cost (Japan: 80+ min -> 2.5 min per 500-law batch). Inputs (the country folder, the shared builder)
# are read from /mnt/c; the wip snapshot, the change test and fetching stay on Windows.
#
# REPRODUCE.md names the toolchain that built a repo, so the first WSL build appends one ordinary fast-forward docs
# commit (append_onto re-commits the build's docs commit on the published head). That stays a single change only if
# every later build of the repo, nightly full builds included, also runs in WSL: once a repo has moved it is marked in
# its .autopush.json ('wsl') and in world-law/WSL-MIGRATED.txt (either one is enough), and it never builds on NTFS
# again. If WSL is unavailable the visit fails and retries; it never falls back to NTFS.
#
# Which repos move: world-law/WSL-REPOS.txt, one slug per line, or '*' for every repo this coordinator publishes. A
# selected repo moves at its next visit with real work, one repo at a time.
#
# Identity: the child's git reads its own global config (credential helper only, no user.*, user.useConfigOnly), with
# no system config, and every git process it starts carries GIT_AUTHOR_*/GIT_COMMITTER_* = WIP_AUTHOR (the commits
# themselves carry the builder's explicit identities, as on Windows). Push auth: the Windows Git Credential Manager,
# the helper the Windows clones use (credential.helper=manager), run from /mnt/c; no token is copied or printed.
WSL_REPOS = ROOT / 'scripts' / 'world-law' / 'WSL-REPOS.txt'
WSL_MIGRATED = ROOT / 'scripts' / 'world-law' / 'WSL-MIGRATED.txt'
WSL_DISTRO = os.environ.get('GITLAW_WSL_DISTRO', 'Ubuntu')
WSL_GCM = '/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe'
WSL_BASE = 'gitlaw-builds/autopush-dell'  # under the WSL home
WSL_VENV_PY = 'gitlaw-builds/.venv/bin/python'  # wsl_run.py setup's venv (Python 3.14, tzdata 2026.6)


def _to_wsl(p: Path | str) -> str:
    """C:\\Users\\x -> /mnt/c/Users/x."""
    m = re.match(r'^([A-Za-z]):[\\/](.*)$', str(p))
    if not m:
        raise ValueError(f'not an absolute Windows path: {p}')
    return f'/mnt/{m.group(1).lower()}/' + m.group(2).replace('\\', '/')


def _slug_list(path: Path) -> set[str]:
    try:
        return {l.split('#', 1)[0].strip() for l in path.read_text(encoding='utf-8').splitlines()} - {''}
    except OSError:
        return set()


def wsl_migrated(slug: str, state: dict) -> bool:
    """True once a repo has built in WSL: it must never build on NTFS again."""
    return bool(state.get('wsl')) or slug in _slug_list(WSL_MIGRATED)


def wsl_selected(slug: str, state: dict) -> bool:
    """Whether this repo's build/publish runs in WSL: already moved, or listed in WSL-REPOS.txt ('*' = all)."""
    if wsl_migrated(slug, state):
        return True
    sel = _slug_list(WSL_REPOS)
    return '*' in sel or slug in sel


def _mark_migrated(slug: str, state: dict) -> None:
    """Record the move before the first WSL build (a build that started in WSL may already have published there)."""
    state.setdefault('wsl', {'since': _now(), 'repo': f'~/{WSL_BASE}/{slug}-law'})
    with _file_lock(WSL_MIGRATED):
        if slug not in _slug_list(WSL_MIGRATED):
            with open(WSL_MIGRATED, 'a', encoding='utf-8', newline='\n') as f:
                f.write(f'{slug}  # {_now()}\n')


def _wip_repo(slug: str) -> Path:
    """A Windows repo for the wip snapshot of a moved repo that has no Windows clone (objects and the ops remote only;
    never built or pushed to the public repo)."""
    r = DOCS / '.gitlaw-wip' / f'{slug}-law'
    if not (r / '.git').exists():
        r.mkdir(parents=True, exist_ok=True)
        git(r, 'init', '-q', '-b', 'main')
        git(r, 'config', 'gc.auto', '0')
    return r


def main_build_wsl(slug: str, folder: Path, state: dict, dry_run: bool = False, repo: str | None = None) -> dict:
    """main_build() for `slug` in a WSL child process, on ext4. `state` is updated in place from the child's.
    `repo`: a WSL path for scratch runs (default ~/gitlaw-builds/autopush-dell/<slug>-law)."""
    if not dry_run:
        _mark_migrated(slug, state)
    with tempfile.TemporaryDirectory() as tmp:
        sin, sout = Path(tmp) / 'state.json', Path(tmp) / 'result.json'
        sin.write_text(json.dumps(state), encoding='utf-8')
        args = ['--wsl-child', slug, '--folder', _to_wsl(folder), '--state-in', _to_wsl(sin), '--result-out', _to_wsl(sout)]
        if repo:
            args += ['--repo', repo]
        if dry_run:
            args.append('--dry-run')
        env = {'GITLAW_AUTOPUSH_WSL': '1', 'PYTHONTZPATH': '', 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
               'LC_ALL': 'C.UTF-8', 'GITLAW_PERSONAL_GITCONFIG': _to_wsl(Path.home() / '.gitconfig')}
        if os.environ.get('GITLAW_AUTOPUSH_SCRATCH'):  # tests: side files (pending, approvals, logs) go there
            env['GITLAW_AUTOPUSH_SCRATCH'] = _to_wsl(os.environ['GITLAW_AUTOPUSH_SCRATCH'])
        # --exec: no shell between, arguments arrive as given; nice 10 ~ BelowNormal (and wsl.exe itself BelowNormal).
        cmd = ['wsl.exe', '-d', WSL_DISTRO, '--cd', '~', '--exec', '/usr/bin/env', *[f'{k}={v}' for k, v in env.items()],
               '/usr/bin/nice', '-n', '10', '/bin/sh', '-c', f'exec "$HOME/{WSL_VENV_PY}" -X utf8 "$@"', 'sh',
               _to_wsl(Path(__file__).resolve()), *args]
        low = {'creationflags': 0x00004000} if os.name == 'nt' else {}
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', **low)
        if p.returncode or not sout.exists():
            return {'main': f'WSL build failed (exit {p.returncode}); not built on NTFS, retried next pass',
                    'error': private.scrub((p.stderr or p.stdout)[-1500:])}
        res = json.loads(sout.read_text(encoding='utf-8'))
    wsl_mark = state.get('wsl')
    state.clear()
    state.update(res['state'])
    if wsl_mark and not dry_run:
        state['wsl'] = wsl_mark
    return {**res['status'], 'wsl': f'ext4, {time.time() - t0:.0f} s'}


def _wsl_child_setup() -> None:
    """In the WSL child: git's global config is our own file (credential helper only, no identity), no system config,
    and an explicit identity on every git process."""
    base = Path.home() / WSL_BASE
    base.mkdir(parents=True, exist_ok=True)
    cfg = base / 'gitconfig'
    gcm = WSL_GCM.replace(' ', '\\\\ ')
    want = ('# autopush_dell (WSL child): no user.name/user.email here on purpose; identities are explicit.\n'
            f'[credential]\n\thelper =\n\thelper = {gcm}\n[core]\n\tautocrlf = false\n[gc]\n\tauto = 0\n'
            '[user]\n\tuseConfigOnly = true\n')
    if not cfg.exists() or cfg.read_text(encoding='utf-8') != want:
        tmp = cfg.with_name(f'.gitconfig.{os.getpid()}')
        tmp.write_text(want, encoding='utf-8')
        os.replace(tmp, cfg)
    os.environ.update(GIT_CONFIG_GLOBAL=str(cfg), GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0', **WIP_AUTHOR)
    if not Path(WSL_GCM).exists():
        raise SystemExit(f'Git Credential Manager not found at {WSL_GCM}')


def wsl_child(args) -> int:
    """--wsl-child: main_build() for one repo, here in WSL; state in and (state, status) out as JSON files."""
    _wsl_child_setup()
    scratch = os.environ.get('GITLAW_AUTOPUSH_SCRATCH')
    if scratch:  # tests: pending rewrites, approvals and push/tag logs stay in the scratch folder
        global PENDING, APPROVED, __file__
        s = Path(scratch)
        (s / 'fake' / 'logs').mkdir(parents=True, exist_ok=True)
        PENDING, APPROVED, __file__ = s / 'REWRITE-PENDING.json', s / 'REWRITE-APPROVED.txt', str(s / 'fake' / 'x.py')
    slug = args.wsl_child
    folder = Path(args.folder)
    repo = Path(os.path.expanduser(args.repo)) if args.repo else Path.home() / WSL_BASE / f'{slug}-law'
    if str(repo).startswith('/mnt/'):
        raise SystemExit(f'{repo} is on a Windows drive, not ext4')
    state = json.loads(Path(args.state_in).read_text(encoding='utf-8'))
    if not (repo / '.git').exists():
        # No clone: remote_main_owner() fetches the published main in full, and a full build re-creates the repo.
        repo.mkdir(parents=True, exist_ok=True)
        git(repo, 'init', '-q', '-b', 'main')
        git(repo, 'remote', 'add', 'origin', f'https://github.com/lexifina/{slug}-law.git')
    git(repo, 'config', 'gc.auto', '0')
    try:
        status = main_build(slug, folder, repo, state, dry_run=args.dry_run)
    except Exception as e:
        status = {'error': private.scrub(str(e))[:500]}
    Path(args.result_out).write_text(json.dumps({'state': state, 'status': status}, ensure_ascii=False),
                                     encoding='utf-8')
    return 0


def one(slug: str, dry_run: bool = False, work: Path | None = None, where: str | None = None) -> str:
    """One visit of one repo. `where` ('wsl' or 'ntfs') only for scratch dry runs; otherwise wsl_selected() decides."""
    folder = ROOT / 'scripts' / f'{slug}-law'
    repo = DOCS / f'{slug}-law'
    try:
        live_state = json.loads((folder / '.autopush.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        live_state = {}
    in_wsl = wsl_selected(slug, live_state)
    if where is not None:
        if not (dry_run and work is not None):
            raise ValueError('where= is only for scratch dry runs (--dry-run --work)')
        in_wsl = where == 'wsl'
    wsl_repo = None
    if work is not None:
        # A dry run in a scratch folder: a copy of the country folder (no caches) and a scratch repo, so neither the
        # live clone nor the country folder (verification.json) is touched; no wip snapshot.
        import shutil
        dst = work / f'{slug}-law.folder'
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(folder, dst, ignore=lambda d, names: [n for n in names if n in SKIP_DIRS or n.startswith('.tmp')
                                                               or n in ('.git', 'logs', '.autopush.json')])
        folder, repo = dst, work / f'{slug}-law'
        wsl_repo = f'~/{WSL_BASE}/.scratch/{work.name}/{slug}-law'
        if not in_wsl and not (repo / '.git').exists():
            repo.mkdir(parents=True, exist_ok=True)
            git(repo, 'init', '-q', '-b', 'main')
            git(repo, 'remote', 'add', 'origin', f'https://github.com/lexifina/{slug}-law.git')
    state_path = folder / '.autopush.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    status = {'at': _now()}
    # Cheap change test first: every input file's path, mtime and size. When nothing changed since a visit that ended
    # cleanly, skip the corpus parse, the hashing and the wip snapshot entirely (and write nothing).
    sig = _folder_sig(folder, slug)
    if (not dry_run and state.get('sig') == sig and state.get('built_sha') and state.get('wip_ok')
            and not _retry_due(state)):
        return f'{slug:10} {"no file changed":28} | {str(state.get("result", ""))[:80]}'
    try:
        if in_wsl:
            # Built and published in WSL (main_build_wsl); never on NTFS again once moved. The wip snapshot stays on
            # Windows, always in a small objects-only repo: the old NTFS clone is no longer maintained, and a stale
            # one (Santa Catarina: a local tag to a missing object) failed every wip fetch (2026-11-03).
            if work is None and not (repo / '.git').exists() and subprocess.run(
                    ['git', 'ls-remote', '-h', f'https://github.com/lexifina/{slug}-law.git'], capture_output=True).returncode:
                return f'{slug:10} {"no GitHub repo yet":28} | waiting for its builder to create it'
            status['wip'] = 'skipped (scratch dry run)' if work is not None else wip(
                slug, folder, _wip_repo(slug), dry_run=dry_run)
            status.update(main_build_wsl(slug, folder, state, dry_run=dry_run, repo=wsl_repo))
        else:
            if not (repo / '.git').exists():
                # A claimed repo whose builder has not created it on GitHub yet: skip quietly, no failed clone each pass.
                if subprocess.run(['git', 'ls-remote', '-h', f'https://github.com/lexifina/{slug}-law.git'],
                                  capture_output=True).returncode:
                    return f'{slug:10} {"no GitHub repo yet":28} | waiting for its builder to create it'
                subprocess.run(['git', 'clone', '-q', f'https://github.com/lexifina/{slug}-law.git', str(repo)], check=True)
            status['wip'] = 'skipped (scratch dry run)' if work is not None else wip(slug, folder, repo, dry_run=dry_run)
            status.update(main_build(slug, folder, repo, state, dry_run=dry_run))
    except Exception as e:  # one country's failure never stops the others
        status['error'] = str(e)[:500]
    if dry_run:
        return json.dumps(status, indent=1, ensure_ascii=False)
    state['sig'] = sig
    state['wip_ok'] = 'failed' not in str(status.get('wip', '')) and 'error' not in status
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
    ap.add_argument('--work', help='with --dry-run: build in this scratch folder (copies of the country folders and '
                                   'repos), leaving the live clones and country folders alone')
    ap.add_argument('--where', choices=('wsl', 'ntfs'),
                    help='with --dry-run --work: build there regardless of WSL-REPOS.txt (comparisons)')
    # The WSL child (started by main_build_wsl, never by hand).
    ap.add_argument('--wsl-child', help=argparse.SUPPRESS)
    ap.add_argument('--folder', help=argparse.SUPPRESS)
    ap.add_argument('--repo', help=argparse.SUPPRESS)
    ap.add_argument('--state-in', help=argparse.SUPPRESS)
    ap.add_argument('--result-out', help=argparse.SUPPRESS)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if args.wsl_child:
        if not IN_WSL:
            sys.exit('--wsl-child runs only inside WSL (started by main_build_wsl)')
        sys.exit(wsl_child(args))
    if args.dry_run:
        for s in args.only or []:
            print(one(s, dry_run=True, work=Path(args.work).resolve() if args.work else None, where=args.where),
                  flush=True)
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
                    # The cheap no-change test runs outside the worker slots, so idle repos never queue behind real
                    # builds (119 claimed repos on 6 slots left fresh PUBLISH parts waiting ~50 min).
                    if unchanged(slug):
                        time.sleep(max(5, args.each - (time.time() - t)))
                        continue
                    with builds:
                        line = one(slug)
                except Exception as e:  # one() already catches; this is a last guard so the thread never dies
                    line = f'{slug:10} error {str(e)[:120]}'
                print(line, flush=True)
                time.sleep(max(5, args.each - (time.time() - t)))

        last_site = 0.0
        last_watch = 0.0
        while True:
            # The listed countries, plus any scripts/<slug>-law folder built by the shared builder (it has corpus.json or
            # corpus.d/). Other sessions' corpora (swiss-law, estonia-law, ...) have their own builders and no
            # corpus.json, so they are never touched.
            # Folders still sourcing (PROGRESS.md, no corpus yet) get wip snapshots too, so their work reaches GitHub.
            # On alan-dell many sessions share scripts/: only this coordinator's own countries (OWN) are picked up.
            found = {p.name[:-4] for p in (ROOT / 'scripts').glob('*-law')
                     if p.is_dir() and p.name[:-4] not in FOREIGN and p.name[:-4] in owned()
                     and ((p / 'corpus.json').exists() or (p / 'corpus.d').is_dir() or (p / 'PROGRESS.md').exists())}
            for s in sorted({s for s in COUNTRIES if (ROOT / 'scripts' / f'{s}-law').is_dir() and s not in FOREIGN}
                            | found):
                if s not in running or not running[s].is_alive():
                    running[s] = threading.Thread(target=country_loop, args=(s,), daemon=True, name=s)
                    running[s].start()
            print(f'--- pass at {_now()} (scheduler: {len(running)} country loops alive)', flush=True)
            if time.time() - last_watch > 600:
                watchdog()
                last_watch = time.time()
            if False and time.time() - last_site > 120:
                sd = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve().parent / 'site_data.py')],
                                    capture_output=True, text=True, encoding='utf-8')
                print(f'site data: {"ok" if sd.returncode == 0 else "FAILED " + (sd.stderr or sd.stdout)[-300:]}', flush=True)
                last_site = time.time()
            time.sleep(60)
    if args.only:
        countries = [c for c in countries if c in owned()]
    if not args.only:
        # Same discovery as --each: every started shared-builder country, not only the listed ones.
        countries = sorted(set(countries) | {p.name[:-4] for p in (ROOT / 'scripts').glob('*-law')
                                             if p.is_dir() and p.name[:-4] not in FOREIGN and p.name[:-4] in owned()
                                             and ((p / 'corpus.json').exists() or (p / 'corpus.d').is_dir()
                                                  or (p / 'PROGRESS.md').exists())})
    while True:
        t = time.time()
        with ThreadPoolExecutor(min(args.workers, len(countries)) or 1) as ex:
            lines = list(ex.map(one, countries))
        print(f'--- pass at {_now()} ({time.time() - t:.0f} s)', *lines, sep='\n', flush=True)
        # Keep the /watch/south-america reader's data in step with what main holds (a few seconds; never fatal).
        if not args.loop:
            return
        time.sleep(max(10, args.loop - (time.time() - t)))


if __name__ == '__main__':
    main()
