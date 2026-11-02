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


def append_onto(repo: Path, remote: str | None, built: str, base: dict[str, str] | None = None) -> dict:
    """Grow `remote` (the published tip, or None) towards `built` (the fresh build) by fast-forward only.

    Walks both first-parent histories oldest first and matches law commits by tree, author line and message (not by
    SHA; 'Lexifina'-authored commits are not law). Allowed: the build's law commits start with every published law
    commit, in order; the rest of its law commits, then its trailing documentation commit, are written on top of the
    published tip with their own trees, authors and messages, committer date max(own, previous + 1 s).
    With no `remote` (a branch the remote lacks, e.g. a first `futuro`), `base` maps build SHAs already published
    elsewhere (main's) to their published SHAs, and the build is grafted after the longest such prefix.

    Returns {'kind': 'same'|'append'|'new'|'rewrite', 'new': tip to publish, 'map': {build sha: new sha},
             'laws': law commits added, 'docs': docs commits added, 'reason': why a rewrite}."""
    n_list = git(repo, 'rev-list', '--first-parent', '--reverse', built).split()
    r_list = git(repo, 'rev-list', '--first-parent', '--reverse', remote).split() if remote else []
    raws = _read_commits(repo, n_list + r_list)
    n_law = [s for s in n_list if _is_law(raws[s])]
    last_law = n_list.index(n_law[-1]) if n_law else -1
    if any(not _is_law(raws[s]) for s in n_list[:last_law]):
        return {'kind': 'rewrite', 'reason': 'the build has a non-law commit inside its law history'}
    tail = n_list[last_law + 1:]  # the build's documentation commit(s), after its last law commit
    mapping: dict[str, str] = {}
    if remote:
        r_law = [s for s in r_list if _is_law(raws[s])]
        n_keys = [_key(raws[s]) for s in n_law]
        for i, r in enumerate(r_law):
            rk = _key(raws[r])
            if i < len(n_law) and n_keys[i] == rk:
                mapping[n_law[i]] = r
                continue
            # Diverged at published law commit i: say how, briefly.
            if i >= len(n_law):
                reason = f'removes {len(r_law) - i} published law commits from {_describe(raws[r])} on'
            elif rk[1:] == n_keys[i][1:]:
                # Same commit, other tree. If the build has an extra commit earlier on, every later snapshot carries
                # its text, so this is reported where the first difference is: here.
                reason = f'changes the text (tree) of published {_describe(raws[r])}'
            elif rk[1:] in [k[1:] for k in n_keys[i:]]:
                # The published commit comes later in the build: commits were inserted before it.
                j = [k[1:] for k in n_keys].index(rk[1:], i)
                reason = (f'inserts {j - i} older commit{"s" if j - i != 1 else ""} before {_describe(raws[r])}, '
                          f'first {_describe(raws[n_law[i]])}')
            elif rk[2] == n_keys[i][2]:
                reason = f'changes the author or date of published {_describe(raws[r])}'
            else:
                gone = not any(k[1:] == rk[1:] for k in n_keys)
                reason = (f'{"removes" if gone else "moves"} published {_describe(raws[r])}; the build has '
                          f'{_describe(raws[n_law[i]])} there')
            return {'kind': 'rewrite', 'reason': reason}
        new_law = n_law[len(r_law):]
        parent = remote
    else:
        base = base or {}
        k = 0
        while k < len(n_law) and n_law[k] in base:
            mapping[n_law[k]] = base[n_law[k]]
            k += 1
        if not k:  # nothing published to graft onto: the build is pushed as it is (a new branch, no history lost)
            return {'kind': 'new', 'new': built, 'map': {s: s for s in n_list}, 'added': list(n_list),
                    'laws': len(n_law), 'docs': len(tail)}
        new_law = n_law[k:]
        parent = base[n_law[k - 1]]
    want_tree = _field(raws[built], b'tree')
    todo = list(new_law)
    if not todo and remote and _field(_read_commits(repo, [remote])[remote], b'tree') == want_tree:
        return {'kind': 'same', 'new': remote, 'map': mapping, 'added': [], 'laws': 0, 'docs': 0}
    todo += tail
    prev_ct = _ident(_field(_read_commits(repo, [parent])[parent], b'committer'))[2]
    tip = parent
    for s in todo:
        lines, msg = _split(raws[s])
        out, done_parent = [], False
        for line in lines:
            if line.startswith(b'parent '):
                if not done_parent:
                    out.append(b'parent ' + tip.encode())
                    done_parent = True
                continue
            if line.startswith(b'committer '):
                c = line[len(b'committer '):]
                gt = c.rindex(b'>')
                ts, tz = c[gt + 1:].split()
                ct = max(int(ts), prev_ct + 1)
                prev_ct = ct
                line = b'committer ' + c[:gt + 1] + f' {ct} '.encode() + tz
            out.append(line)
            if line.startswith(b'tree ') and not done_parent:
                out.append(b'parent ' + tip.encode())
                done_parent = True
        tip = _write_object(repo, 'commit', b'\n'.join(out) + b'\n\n' + msg)
        mapping[s] = tip
    if git(repo, 'cat-file', '-t', tip) != 'commit' or git(repo, 'rev-parse', f'{tip}^{{tree}}') != want_tree.decode():
        return {'kind': 'rewrite', 'reason': 'the appended tip does not have the build\'s final tree'}
    if remote and subprocess.run(['git', 'merge-base', '--is-ancestor', remote, tip], cwd=repo).returncode:
        return {'kind': 'rewrite', 'reason': 'internal: the appended tip does not descend from the published tip'}
    docs = sum(1 for s in todo if s in tail)
    return {'kind': 'append', 'new': tip, 'map': mapping, 'added': [mapping[s] for s in todo],
            'laws': len(todo) - docs, 'docs': docs}


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
    # Only the branches the remote already holds: one missing name (a first `zukunft`/`future`) fails the whole fetch
    # and leaves origin/main stale, which made the first push of such a repo fail.
    have = {l.partition('\t')[2] for l in git(repo, 'ls-remote', '--heads', 'origin', check=False).splitlines()}
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
    for b in branches:
        new = git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{b}', check=False)
        old = git(repo, 'rev-parse', '-q', '--verify', f'refs/remotes/origin/{b}', check=False) if b in there else ''
        if not new:
            plan.append(f'{b} same')
            continue
        g = append_onto(repo, old or None, new, base=main_map if b != 'main' else None)
        if b == 'main':
            main_map = g.get('map', {})
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
            replaced = git(repo, 'rev-list', '--count', old, f'^{new}', check=False)
            rewrites.append({'ref': f'refs/heads/{b}', 'old': old, 'new': new, 'reason': g['reason'],
                             'replaces_commits': int(replaced or 0),
                             'adds_commits': int(git(repo, 'rev-list', '--count', new, f'^{old}') or 0)})
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
        what = f'+{g["laws"]} law commit{"s" if g["laws"] != 1 else ""}' + (f', +{g["docs"]} docs' if g['docs'] else '')
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
    if dry_run:
        return f'dry run, would push: {summary}'
    # Windows caps a command line at about 32k characters: push the branches first, then the tags in batches.
    heads = [r for r in refs if not r.partition(':')[2].startswith('refs/tags/')]
    tag_refs = [r for r in refs if r.partition(':')[2].startswith('refs/tags/')]
    if len(' '.join(refs)) + len(' '.join(f'{k}:{v}' for k, v in leases.items())) * 2 < 20000:
        return f'{push(repo, *refs, leases=leases)} ({summary})'
    result = push(repo, *heads, leases={k: v for k, v in leases.items() if k.startswith('refs/heads/')}) if heads \
        else 'pushed'
    for i in range(0, len(tag_refs), 60):  # each moved tag also carries a --force-with-lease argument
        if result.startswith('push failed'):
            break
        batch = tag_refs[i:i + 60]
        dsts = [t.partition(':')[2] for t in batch]
        result = push(repo, *batch, leases={t: leases[t] for t in dsts if t in leases})
    return f'{result} ({summary}; in batches)'


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
    # This country's rewrite approvals change what may be pushed. private.py is left out on purpose: it only shapes
    # tools/ and the docs commit, and hashing it made one edit rebuild every corpus at once (the next real change
    # brings the docs up to date; audit_push still guards every push).
    h.update(repr(sorted(a for a in approved_rewrites() if a[0] == slug)).encode())
    sha = h.hexdigest()
    # A failed push is retried even when nothing changed (e.g. a first push that lost a race with a new branch).
    if (state.get('built_sha') == sha and not dry_run and 'fail' not in str(state.get('result', ''))
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
PUBLISH_MODE = 'append-v1'


def _retry_due(state: dict) -> bool:
    """True when a repo must be visited again although no file changed: an append that waited for its commit dates
    (state['retry_after']) once that time has passed, or a last visit made under an older PUBLISH_MODE."""
    if state.get('publish_mode') != PUBLISH_MODE:
        return True
    return bool(state.get('retry_after')) and time.time() >= state['retry_after']


def unchanged(slug: str) -> bool:
    """True when nothing one() reads has changed since a visit that ended cleanly (stat calls only)."""
    folder = ROOT / 'scripts' / f'{slug}-law'
    state_path = folder / '.autopush.json'
    try:
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
        return (state.get('sig') == _folder_sig(folder, slug) and bool(state.get('built_sha'))
                and bool(state.get('wip_ok')) and 'fail' not in str(state.get('result', '')) and not _retry_due(state))
    except (OSError, ValueError):
        return False


def one(slug: str, dry_run: bool = False, work: Path | None = None) -> str:
    folder = ROOT / 'scripts' / f'{slug}-law'
    repo = DOCS / f'{slug}-law'
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
        if not (repo / '.git').exists():
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
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if args.dry_run:
        for s in args.only or []:
            print(one(s, dry_run=True, work=Path(args.work).resolve() if args.work else None), flush=True)
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
