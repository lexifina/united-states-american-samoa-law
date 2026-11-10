"""Grow a published future branch (futuro / futur / fremtidig) by fast-forward, after main has been appended.

    GITLAW_VERIFIED_PARTS_ONLY=1 python -X utf8 append_future.py <scripts/<slug>-law> --repo <publish clone> \
        --url https://github.com/lexifina/<slug>-law.git --docs-date D [--build <clone>] [--append-main] [--corrections]

append.py grows main only. The future branch holds the laws passed but not yet in force; the full builder forks it
from main's last law commit, so every rebuild of it is a rewrite of the published one. grow() grows it instead, in the
publish clone, append-only, in three steps:

1. Replay. main's commits newer than the future branch's fork point (git merge-base), oldest first, that the branch
   does not hold yet (a commit is held when one with the same author line and message is on the branch after the
   fork): law commits and correction commits; main's documentation commits are left out (the future branch keeps only
   law). Each is written on top of the branch as a new commit with the exact author line and message bytes, so every
   trailer (In-force, and a correction's Kind, In-force, Corrects, Supersedes, Reason, Act-path, Files) is kept as
   main has it, and the committer of main's commit at max(its own date, previous + 1 s). Its tree sets each act the
   commit touches (an act by its corpus slug; a correction's Act-path too) to the act's files in main's commit, so a
   replayed commit reads, for its acts, as it reads on main.
2. Corrections, in append.py's own format and code (append.plan_corrections(), correction_message()), read on the
   future branch with corrections applied (append.Reader) against the whole corpus, future versions included: ONE
   correction commit per act version the branch reads wrongly, plus, where the act at the tip no longer holds its
   newest version on the branch, those files restored in that version's correction. A replayed main commit for an act
   that has a published future version is the usual case: from the future version's day the branch would read main's
   newer text, so a correction sets that day on back to the future version. Only with corrections=True (the loop's
   --corrections); without it, any such need refuses and the hold stays, with the acts and days.
3. New future laws: the versions after the newest one the branch holds (append.to_append() with no date cut), planned
   and worded exactly as build.py and append.py plan them, each act's first version as a start commit; a commit whose
   author line and message the branch already holds is not written again.

Committer dates never go backwards and nothing reads the clock, so the same published branch, main and corpus always
give the same SHAs; a second run adds nothing. Tags: the new future laws' `<act>/<day>` and `law/<key>`, only names the
remote does not hold (never moved).

grow() writes objects and refs in the publish clone only (refs/heads/<future>), then runs check.py over the future
branch against the whole corpus (no docs-date cut; check.py reads correction commits by on.py's rule),
private.audit_push() over just the new commits, and refuses any author or committer address outside lexifina.com and
.invalid. It never pushes: autopush.publish_future() pushes with a plain push (never forced) and clears the held entry
once the push has landed.

The CLI is the dry run: --append-main runs append_gate.run() first (main appended in the publish clone, not pushed;
with --corrections, append_gate's --corrections too). Use scratch clones, never a loop's own.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import append as AP  # noqa: E402
import private  # noqa: E402

B, K = AP.B, AP.K
LOW = {'creationflags': 0x00004000} if os.name == 'nt' else {}  # BELOW_NORMAL_PRIORITY_CLASS, as builds
FAIL_KEYS = ('mismatches', 'trailer_errors', 'missing_in_force', 'merges', 'backwards', 'future_dated')
CORRECTION = re.compile(rb'^Kind:\s*correction\s*$', re.M)
# append.plan_corrections() reads `main` through append.Reader; the future branch is read by passing its tip as the
# ref (see _plan_corrections). The loop runs countries in threads of one process: one at a time.
_READER_LOCK = threading.Lock()


def git(repo: Path, *args: str, env: dict | None = None, data: bytes | None = None, check: bool = True) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if check and out.returncode:
        raise RuntimeError(f'git {" ".join(args[:3])}: {out.stderr.decode("utf-8", "replace").strip()[:300]}')
    return out.stdout.decode('utf-8', 'replace').strip()


def bot_env(email: str) -> dict[str, str]:
    return {'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': email,
            'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': email}


# ---------------------------------------------------------------- raw commits

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


def _key(raw: bytes) -> tuple[bytes, bytes]:
    """The same commit, whatever its parent and committer: author line (name, email, date, zone) and message."""
    return _field(raw, b'author'), _split(raw)[1]


def _is_correction(raw: bytes) -> bool:
    return bool(CORRECTION.search(_split(raw)[1]))


def _replayable(raw: bytes) -> bool:
    """A law commit (not authored by Lexifina) or a correction commit; not a documentation commit."""
    return _ident(_field(raw, b'author'))[0] != 'Lexifina' or _is_correction(raw)


def _in_force(raw: bytes) -> str | None:
    for line in _split(raw)[1].split(b'\n'):
        if line.startswith(b'In-force:'):
            return line.split(b':', 1)[1].strip().decode()
    return None


def _trailer_values(raw: bytes, key: bytes) -> list[str]:
    return [line.split(b':', 1)[1].strip().decode('utf-8', 'replace') for line in _split(raw)[1].split(b'\n')
            if line.startswith(key + b':')]


def _first_parent(repo: Path, rng: list[str]) -> list[str]:
    out = git(repo, 'rev-list', '--reverse', '--first-parent', *rng)
    return out.split() if out else []


def _act_of(path: str, slugs: set[str]) -> str | None:
    """The corpus act a path lies in (the longest slug at or above it), else its top-level folder; None for the
    documentation (top-level files, data/, tools/)."""
    parts = path.split('/')
    for i in range(len(parts), 0, -1):
        p = '/'.join(parts[:i])
        if p in slugs:
            return p
    if len(parts) < 2 or parts[0] in ('data', 'tools'):
        return None
    return parts[0]


def _fast_import(repo: Path, buf: bytes, email: str) -> dict[str, str]:
    """One `git fast-import` of `buf` (commits on a temporary ref, marks :1..); {':n': sha}."""
    with tempfile.TemporaryDirectory() as tmp:
        marks = Path(tmp) / 'marks'
        fi = subprocess.run(['git', 'fast-import', '--quiet', '--done', '--date-format=raw', f'--export-marks={marks}'],
                            cwd=repo, input=buf + b'done\n', capture_output=True, env={**os.environ, **bot_env(email)})
        if fi.returncode:
            raise RuntimeError(f'fast-import: {fi.stderr.decode("utf-8", "replace")[-300:]}')
        return dict(line.split(' ', 1) for line in marks.read_text().split('\n') if line)


def _path_ok(p: str) -> str:
    if '\n' in p or p.startswith('"'):
        raise RuntimeError(f'unsupported path {p!r}')
    return p


# ---------------------------------------------------------------- the three steps

def _ls_all(repo: Path, commit: str) -> dict[str, tuple[str, str]]:
    out = subprocess.run(['git', '-c', 'core.quotePath=false', 'ls-tree', '-r', '-z', '--full-tree', commit], cwd=repo,
                         capture_output=True).stdout
    files = {}
    for rec in out.split(b'\0'):
        if rec:
            meta, _, p = rec.partition(b'\t')
            mode, kind, oid = meta.decode().split()
            if kind == 'blob':
                files[p.decode('utf-8', 'surrogateescape')] = (mode, oid)
    return files


def _deltas(repo: Path, rng: list[str]) -> dict[str, dict[str, tuple[str, str] | None]]:
    """Each first-parent commit's file changes against its first parent ({path: (mode, blob id), or None when
    deleted}), from one `git log --raw`."""
    out = subprocess.run(['git', '-c', 'core.quotePath=false', '-c', 'log.showRoot=true', 'log', '-z', '--first-parent',
                          '--no-renames', '--raw', '--no-abbrev', '--format=%x01%H', *rng], cwd=repo,
                         capture_output=True).stdout
    deltas: dict[str, dict] = {}
    cur = None
    toks = out.split(b'\0')
    i = 0
    while i < len(toks):
        t = toks[i].lstrip(b'\n')
        i += 1
        if t.startswith(b'\x01'):
            cur = t[1:].decode()
            deltas[cur] = {}
        elif t.startswith(b':') and cur is not None:
            meta = t[1:].split()
            path = toks[i].decode('utf-8', 'surrogateescape')
            i += 1
            deltas[cur][path] = None if meta[4].startswith(b'D') else (meta[1].decode(), meta[3].decode())
    return deltas


class _Acts:
    """A tree's files grouped by act (_act_of), kept up to date path by path."""

    def __init__(self, files: dict[str, tuple[str, str]], units: set[str]):
        self.units, self.by = units, {}
        for p, v in files.items():
            self.set(p, v)

    def set(self, path: str, v: tuple[str, str] | None):
        a = _act_of(path, self.units)
        if a is None:
            return
        d = self.by.setdefault(a, {})
        if v is None:
            d.pop(path, None)
        else:
            d[path] = v

    def get(self, act: str) -> dict[str, tuple[str, str]]:
        return dict(self.by.get(act, {}))


def _replay(repo: Path, tip: str, main: str, slugs: set[str], email: str) -> tuple[str, list[str], list[str]]:
    """Step 1. Returns (new tip, main commits replayed, their new SHAs)."""
    fork = git(repo, 'merge-base', tip, main, check=False)
    if not fork:
        raise RuntimeError('the future branch and main share no history')
    m_list = _first_parent(repo, [main, f'^{fork}'])
    f_list = _first_parent(repo, [tip, f'^{fork}'])
    raws = _read_commits(repo, m_list + f_list + [tip])
    held = {_key(raws[s]) for s in f_list}
    todo = [s for s in m_list if _replayable(raws[s]) and _key(raws[s]) not in held]
    if not todo:
        return tip, [], []
    # Act units: the corpus slugs, and every Act-path a replayed correction names (an act may be one file).
    units = set(slugs) | {p.strip().rstrip('/') for s in todo for p in _trailer_values(raws[s], b'Act-path')
                          if p.strip()}
    deltas = _deltas(repo, [main, f'^{fork}'])
    on_main = _Acts(_ls_all(repo, fork), units)  # main's files, moved commit by commit
    on_branch = _Acts(_ls_all(repo, tip), units)  # the branch's files, moved by what is written here
    want_set = set(todo)
    prev_ct = _ident(_field(raws[tip], b'committer'))[2]
    ref = f'refs/append-future-tmp/{os.getpid()}-{threading.get_ident()}'
    buf = bytearray()
    i = 0
    for s in m_list:
        d = deltas.get(s, {})
        for p, v in d.items():
            on_main.set(p, v)
        if s not in want_set:
            continue
        i += 1
        raw = raws[s]
        acts = {a for p in d if (a := _act_of(p, units))}
        acts |= {p.strip().rstrip('/') for p in _trailer_values(raw, b'Act-path') if p.strip()}
        acts |= {a for p in _trailer_values(raw, b'Files') if (a := _act_of(p, units))}
        ops: list[bytes] = []
        for a in sorted(acts):
            have, want = on_branch.get(a), on_main.get(a)
            for p in sorted(set(have) | set(want)):
                if want.get(p) == have.get(p):
                    continue
                ops.append((f'D {_path_ok(p)}' if p not in want else
                            f'M {want[p][0]} {want[p][1]} {_path_ok(p)}').encode('utf-8', 'surrogateescape'))
                on_branch.set(p, want.get(p))
        c = _field(raw, b'committer')
        gt = c.rindex(b'>')
        ts, tz = c[gt + 1:].split()
        prev_ct = max(int(ts), prev_ct + 1)
        msg = _split(raw)[1]
        buf += f'commit {ref}\nmark :{i}\n'.encode()
        buf += b'author ' + _field(raw, b'author') + b'\n'
        buf += b'committer ' + c[:gt + 1] + f' {prev_ct} '.encode() + tz + b'\n'
        buf += f'data {len(msg)}\n'.encode() + msg + b'\n'
        if i == 1:
            buf += f'from {tip}\n'.encode()
        buf += b''.join(op + b'\n' for op in ops) + b'\n'
    marks = _fast_import(repo, bytes(buf), email)
    git(repo, 'update-ref', '-d', ref, check=False)
    new = [marks[f':{k}'].strip() for k in range(1, len(todo) + 1)]
    return new[-1], todo, new


def _state(repo: Path, c: dict, tip: str) -> dict[str, str]:
    """{act: newest In-force day the branch holds}, as append.published_state() reads main (without its check)."""
    rows = K.all_commits_by_act(repo, tip, [a['slug'] for a in c['acts']])
    listed: dict[str, str] = {}
    try:  # credit-only commits (no file changed) on main, from main's data/commits.csv
        for e in AP.published_log(repo):
            if e['branch'] == 'main':
                for s in e['acts']:
                    listed[s] = max(listed.get(s, ''), e['day'])
    except Exception:
        pass
    return {a['slug']: max([d for _, d in rows[a['slug']]] + [listed.get(a['slug'], '')])
            for a in c['acts'] if rows[a['slug']]}


def _plan_corrections(repo: Path, c: dict, tip: str, state: dict[str, str], reason: str) -> list[dict]:
    """append.plan_corrections() read on the future branch: its Reader is given the branch tip as the ref."""
    with _READER_LOCK:
        orig = AP.Reader

        def reader(repo_, acts, ref='main', **kw):
            return orig(repo_, acts, ref=tip, **kw)
        AP.Reader = reader
        try:
            return AP.plan_corrections(repo, c, tip, state, reason)
        finally:
            AP.Reader = orig


def grow(folder: Path, pub: Path, build: Path | None = None, future: str | None = None, docs_date: str | None = None,
         corrections: bool = False, reason: str = AP.DEFAULT_REASON) -> dict:
    """The published future branch grown by fast-forward in the publish clone `pub`, after main has been appended
    there (pushed or not). `build` is not read (kept for the callers; the plan comes from main and the corpus).
    Returns {'result': 'same'|'appended'|'refused'|'check failed'|'audit failed'|'skipped'|'error', 'branch', 'old',
    'new', 'added', 'replayed' (main's commits), 'replayed_corrections', 'corrections' (written for the branch),
    'future_laws', 'refs' (to push: the branch, then new tags only), 'new_tags', 'check', 'audit', 'reason'}."""
    c, _ = B.load(folder)
    co = c['country']
    future = future or co.get('future_branch', 'futuro')
    day = docs_date or max((s.get('retrieved', '') for s in c.get('sources', []) if s.get('retrieved')), default='')
    c['_docs_date'] = day or '9999-12-31'
    email = f'{co["slug"]}-law@lexifina.com'
    out: dict = {'branch': future}
    if not git(pub, 'ls-remote', '--heads', 'origin', future):
        # A first future branch has no published history to grow: the full builder's push makes it (a new branch).
        return {**out, 'result': 'skipped', 'reason': f'the remote has no {future} branch yet'}
    git(pub, 'fetch', '-q', '--no-tags', 'origin', f'+refs/heads/{future}:refs/remotes/origin/{future}')
    old = git(pub, 'rev-parse', f'refs/remotes/origin/{future}')
    main = git(pub, 'rev-parse', 'refs/heads/main')
    out['old'] = old
    slugs = {a['slug'] for a in c['acts']}
    try:
        t1, src, replayed = _replay(pub, old, main, slugs, email)
        rraws = _read_commits(pub, replayed)
        out['replayed'] = len(replayed)
        out['replayed_corrections'] = sum(1 for s in replayed if _is_correction(rraws[s]))
        # Steps 2 and 3, read on the replayed tip against the whole corpus.
        state = _state(pub, c, t1)
        fixes = _plan_corrections(pub, c, t1, state, reason)
        if fixes and not corrections:
            acts = sorted({x['act']['slug'] for x in fixes})
            return {**out, 'result': 'refused', 'corrections_needed': len(fixes),
                    'reason': f'the future branch needs {len(fixes)} correction(s) in {len(acts)} act(s) after '
                              f'replaying main (e.g. ' + '; '.join(f'{x["act"]["slug"]} {x["version"]["from"]}'
                                                                   for x in fixes[:6]) + '): run with --corrections'}
        sub, based = AP.to_append(c, state, '9999-12-31')
        planned = [x for x in (B.plan(sub) if sub['acts'] else [])
                   if not (x['kind'] == 'start' and x['act']['slug'] in based)]
    except Exception as e:
        return {**out, 'result': 'error', 'reason': f'{type(e).__name__}: {str(e)[:500]}'}
    clock = B.Clock(co['tz'])
    committer = f'Lexifina <{email}>'
    f_raws = _read_commits(pub, _first_parent(pub, [t1, f'^{git(pub, "merge-base", t1, main)}']) + [t1])
    held = {_key(r) for r in f_raws.values()}
    prev_ct, tz = _ident(_field(f_raws[t1], b'committer'))[2:]
    items = []  # (author line, message, files {path: text or None}, tags)
    for x in fixes:
        msg, trailers = AP.correction_message(c, x)
        B.check_trailers(trailers)
        text = '\n'.join(msg).rstrip('\n') + '\n\n' + '\n'.join(trailers) + '\n'
        items.append((f'{committer} {clock.stamp(x["version"]["from"])}', text, x['files'], []))
    n_law = 0
    for x in planned:
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
        aline = f'{author[0]} <{author[1]}> {clock.stamp(x["day"])}'
        if (aline.encode('utf-8'), text.encode('utf-8')) in held:
            continue  # already on the branch (a credit-only commit changes no file, so no reading shows it)
        tags = [f'{s}/{x["day"]}' for s in touched]
        if x['kind'] == 'law':
            tags.append(f'law/{x["law"]}')
        elif x['kind'] == 'start' and x['act'].get('first_law'):
            tags.append(f'law/{x["act"]["first_law"]}')
        items.append((aline, text, files, tags))
        n_law += 1
    tip, written, tag_at = t1, [], {}
    if items:
        ref = f'refs/append-future-tmp/{os.getpid()}-{threading.get_ident()}'
        buf = bytearray()
        for i, (aline, text, files, tags) in enumerate(items, 1):
            prev_ct += 1
            data = text.encode('utf-8')
            buf += f'commit {ref}\nmark :{i}\nauthor {aline}\ncommitter {committer} {prev_ct} {tz}\n'.encode('utf-8')
            buf += f'data {len(data)}\n'.encode() + data + b'\n'
            if i == 1:
                buf += f'from {t1}\n'.encode()
            for p in sorted(files):
                if files[p] is None:
                    buf += f'D {_path_ok(p)}\n'.encode('utf-8')
                else:
                    blob = files[p].encode('utf-8')
                    buf += f'M 100644 inline {_path_ok(p)}\n'.encode('utf-8') + f'data {len(blob)}\n'.encode() + blob + b'\n'
            buf += b'\n'
        marks = _fast_import(pub, bytes(buf), email)
        git(pub, 'update-ref', '-d', ref, check=False)
        written = [marks[f':{i}'].strip() for i in range(1, len(items) + 1)]
        tip = written[-1]
        for sha, (_, _, _, tags) in zip(written, items):
            for t in tags:
                tag_at.setdefault(f'refs/tags/{t}', sha)
    added = replayed + written
    if not added:
        git(pub, 'update-ref', f'refs/heads/{future}', old)
        return {**out, 'result': 'same', 'new': old, 'added': 0, 'replayed': 0, 'corrections': 0, 'future_laws': 0,
                'new_tags': 0, 'refs': []}
    if subprocess.run(['git', 'merge-base', '--is-ancestor', old, tip], cwd=pub).returncode:
        return {**out, 'result': 'error', 'reason': f'internal: {tip[:12]} is not a fast-forward of {old[:12]}'}
    git(pub, 'update-ref', f'refs/heads/{future}', tip)
    remote = remote_tags(pub)
    new_tags = {t: s for t, s in tag_at.items() if t not in remote}
    out.update(new=tip, added=len(added), corrections=len(fixes), future_laws=n_law, new_tags=len(new_tags),
               refs=[f'refs/heads/{future}:refs/heads/{future}'] + [f'{s}:{t}' for t, s in sorted(new_tags.items())])
    chk = check_all(folder, pub)
    out['check'] = {k: v for k, v in chk.items() if k != 'details'}
    if 'error' not in chk:
        out['check']['mismatch_days'] = _split_days(chk.get('details') or [], day)
    if 'error' in chk or any(chk.get(k) for k in FAIL_KEYS):
        return {**out, 'result': 'check failed', 'details': (chk.get('details') or [chk.get('error')])[:10]}
    found = private.audit_push(pub, tip, old)
    bad = foreign_emails(pub, tip, old)
    out['audit'] = {'findings': len(found), 'foreign_emails': bad}
    if found or bad:
        return {**out, 'result': 'audit failed', 'details': found[:5] + [f'address: {e}' for e in bad[:5]]}
    out['result'] = 'appended'
    return out


def _split_days(details: list[str], day: str) -> dict:
    """check.py's mismatch details ('<act> on <day>: ...') counted as past (on or before the data date) or future."""
    past = fut = 0
    for d in details:
        m = re.search(r' on (\d{4}-\d{2}-\d{2}):', d)
        if m:
            if day and m.group(1) > day:
                fut += 1
            else:
                past += 1
    return {'past': past, 'future': fut, 'of_details': len(details)}


# ---------------------------------------------------------------- gates

def foreign_emails(repo: Path, new: str, old: str | None) -> list[str]:
    """Author and committer addresses of old..new outside lexifina.com and the .invalid placeholders."""
    out = git(repo, 'log', '--format=%ae %ce', new, *([f'^{old}'] if old else []))
    return sorted({e for line in out.splitlines() for e in line.split()
                   if not (e.endswith('@lexifina.com') or e.endswith('.invalid'))})


def check_all(folder: Path, repo: Path) -> dict:
    """check.py on the publish clone's future branch (and main's trailers and health) against the whole corpus (no
    docs-date cut), verified parts only as autopush publishes them. Below normal priority, in its own process."""
    env = {**os.environ, 'GITLAW_VERIFIED_PARTS_ONLY': os.environ.get('GITLAW_VERIFIED_PARTS_ONLY', '1')}
    r = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'check.py'), str(repo), '--corpus',
                        str(folder / 'corpus.json')], capture_output=True, text=True, encoding='utf-8', env=env, **LOW)
    try:
        res = json.loads(r.stdout)
    except ValueError:
        return {'error': (r.stderr or r.stdout)[-1000:]}
    res.pop('corpus_sha256', None)
    return res


def remote_tags(repo: Path) -> dict[str, str]:
    out = {}
    for line in git(repo, 'ls-remote', '--tags', 'origin', check=False).splitlines():
        sha, _, ref = line.partition('\t')
        if not ref.endswith('^{}'):
            out[ref] = sha
    return out


# ---------------------------------------------------------------- dry run (CLI)

def wait_cpu(limit: int = 92, log: Path | None = None) -> None:
    """Wait while the 5-minute CPU average in %LOCALAPPDATA%/gitlaw-cpu.log is over `limit` (never WMI)."""
    log = log or Path(os.environ.get('LOCALAPPDATA', '')) / 'gitlaw-cpu.log'
    while True:
        try:
            last = log.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-1]
            cpu5 = int(next(f for f in last.split() if f.startswith('cpu5=')).split('=')[1])
        except (OSError, IndexError, StopIteration, ValueError):
            return
        if cpu5 <= limit:
            return
        time.sleep(60)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--repo', required=True, help='the publish clone (a scratch one for a dry run)')
    ap.add_argument('--build', help='(not read; accepted for older callers)')
    ap.add_argument('--url', required=True)
    ap.add_argument('--docs-date', required=True)
    ap.add_argument('--seed', help='a clone holding the published main, to copy objects from (only read)')
    ap.add_argument('--append-main', action='store_true', help='append main first with append_gate.run() (no push)')
    ap.add_argument('--corrections', action='store_true', help='write correction commits instead of refusing')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    folder, pub = Path(a.folder).resolve(), Path(a.repo).resolve()
    res: dict = {}
    try:
        if a.append_main:
            import append_gate as AG
            wait_cpu()
            m = AG.run(folder, pub, a.url, a.docs_date, Path(a.seed).resolve() if a.seed else None,
                       corrections=a.corrections)
            res['main'] = {k: (len(v) if isinstance(v, list) else v) for k, v in m.items()}
            if m.get('result') not in ('same', 'appended', 'docs'):
                raise RuntimeError(f'main: {m.get("result")}: {str(m.get("reason") or m.get("details"))[:500]}')
        else:
            # The publish clone's main must be the published one (or appended on it): sync only the refs.
            git(pub, 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main')
        wait_cpu()
        res['future'] = grow(folder, pub, docs_date=a.docs_date, corrections=a.corrections)
        res['future'].pop('refs', None)
    except Exception as e:
        res['error'] = f'{type(e).__name__}: {str(e)[:800]}'
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
