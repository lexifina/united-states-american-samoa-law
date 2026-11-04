"""Gates the pointer loop runs on a corpus's new commits before pinning them (repoint_fast.py, from 2026-11-04).

For each corpus whose pin would move (or that would be added), in parallel and time-boxed:
  - global-law's own tools/check_corpus.py checks (taken from global-law main, the commit the pass builds on), run at
    the new commit on a blob-less bare clone kept between passes in <gl-repoint>/.git/gate-clones/<repo>.git;
  - the stale-HEAD check ("check 11" in the queue briefs: HEAD must still equal the text in force; check_corpus's
    stale_at_head, which held romania, spain-madrid and minnesota by hand on 2026-11-04).
A corpus is held when the new commit has a fatal problem or more stale files than the commit pinned now (what got
worse, not what was already true at the pin). Held corpora are logged to repoint-held.log for that pass only; nothing
is written to repoint-hold.txt, which people curate.
"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

HERE = Path(__file__).resolve().parent
FETCH_CAP = 240     # s for one corpus's fetch; a first clone that runs longer goes on in the background
CHECK_CAP = 180     # s for check_corpus at the new commit (and the old pin, if needed)
DEADLINE = 540      # s for all gates of one pass; a corpus not reached by then is held for that pass
WORKERS = 8
ENV = {**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'}


def _git(cwd, *a, timeout=60):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          timeout=timeout, env=ENV)


def tools_dir(w, base):
    """check_corpus.py and law.py (which it imports for Kind words) from global-law at `base`; None if absent."""
    d = w / '.gate-tools' / base[:12] / 'tools'
    if (d / 'check_corpus.py').exists():
        return d
    d.mkdir(parents=True, exist_ok=True)
    for name in ('check_corpus.py', 'law.py'):
        r = _git(w, 'show', f'{base}:tools/{name}')
        if r.returncode:
            if name == 'check_corpus.py':
                return None
            continue
        (d / name).write_bytes(r.stdout.encode('utf-8'))
    return d


def _norm(problem):
    import re
    return re.sub(r'[0-9a-f]{7,40}|\d+', '#', problem)


def _alive(pid):
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return True


def _one(w, tools, repo, url, checks, until):
    """checks: [(new, old|None, wip)] for one repo. Returns {(new, old): (ok, reason)}."""
    out = {}
    clone = w / '.git' / 'gate-clones' / f'{repo}.git'
    if not (clone / 'HEAD').exists():
        clone.mkdir(parents=True, exist_ok=True)
        _git(clone, 'init', '-q', '--bare')
        _git(clone, 'config', 'remote.origin.url', url)
        _git(clone, 'config', 'remote.origin.promisor', 'true')
        _git(clone, 'config', 'remote.origin.partialclonefilter', 'blob:none')
    missing = [n for n, _, _ in checks if _git(clone, 'cat-file', '-e', f'{n}^{{commit}}').returncode]
    if missing:
        mark = clone / 'gate-fetching'
        if mark.exists():
            try:
                pid, at = mark.read_text().split()
                if _alive(int(pid)) and time.time() - float(at) < 3600:
                    return {(n, o): (False, f'an earlier fetch (pid {pid}) is still running') for n, o, _ in checks}
            except ValueError:
                pass
        refs = ['+refs/heads/main:refs/heads/main']
        if any(w_ for _, _, w_ in checks):
            refs.append('+refs/heads/preview:refs/heads/preview')
        # Not killed at the cap: a first blob-less clone of a large corpus may take longer than one pass allows, and
        # a killed fetch keeps nothing. It finishes in the background and the next pass reads it.
        p = subprocess.Popen(['git', 'fetch', '-q', '--filter=blob:none', 'origin', *refs], cwd=clone, env=ENV,
                             stdout=subprocess.DEVNULL, stderr=open(clone / 'gate-fetch.err', 'w'))
        mark.write_text(f'{p.pid} {time.time()}')
        try:
            rc = p.wait(timeout=FETCH_CAP)
        except subprocess.TimeoutExpired:
            return {(n, o): (False, f'fetch still running after {FETCH_CAP} s (left to finish; checked next pass)')
                    for n, o, _ in checks}
        mark.unlink(missing_ok=True)
        if rc:
            err = (clone / 'gate-fetch.err').read_text(encoding='utf-8', errors='replace').strip()[-160:]
            return {(n, o): (False, f'fetch failed: {err}') for n, o, _ in checks}
    for new, old, wip in checks:
        if _git(clone, 'cat-file', '-e', f'{new}^{{commit}}').returncode:
            out[(new, old)] = (False, f'{new[:9]} not on the fetched branches')
            continue
        try:
            r = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'gate_check.py'), str(tools), str(clone), new,
                                old or '-', '1' if wip else '0', until], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=CHECK_CAP, env=ENV)
        except subprocess.TimeoutExpired:
            out[(new, old)] = (False, f'check_corpus ran past {CHECK_CAP} s')
            continue
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            out[(new, old)] = (False, f'check_corpus failed: {r.stderr.strip()[-160:]}')
            continue
        was = {_norm(p) for p in (res['fatal_old'] or [])}
        worse = [p for p in res['fatal_new'] if _norm(p) not in was]
        if worse:
            out[(new, old)] = (False, f'check_corpus: {worse[0][:200]}' + (f' (+{len(worse) - 1} more)' if len(worse) > 1 else ''))
        elif res['stale_new'] and res['stale_new'] > (res['stale_old'] or 0):
            out[(new, old)] = (False, f"stale HEAD (check 11): {res['stale_new']} file(s) show older law at HEAD"
                                      f" (pin has {res['stale_old'] or 0}); {res['stale_eg'][-160:]}")
        else:
            note = []
            if res['fatal_new']:
                note.append(f"{len(res['fatal_new'])} fatal already at the pin")
            if res['stale_new']:
                note.append(f"{res['stale_new']} stale already at the pin")
            out[(new, old)] = (True, '; '.join(note) or 'pass')
    return out


_DONE: dict = {}  # (repo, new, old) -> (ok, reason), kept across the retries of one process


def gate(w, base, items, until=None):
    """items: {(repo, new, old): {'url': ..., 'wip': bool}}. Returns {(repo, new, old): (ok, reason)}, and None when
    global-law main has no tools/check_corpus.py (gates off, logged by the caller)."""
    tools = tools_dir(w, base)
    if tools is None:
        return None
    until = until or time.strftime('%Y-%m-%d', time.gmtime())
    todo: dict = {}
    for (repo, new, old), meta in items.items():
        if (repo, new, old) in _DONE:
            continue
        todo.setdefault(repo, {'url': meta['url'], 'checks': []})['checks'].append((new, old, meta.get('wip', False)))
    ex = ThreadPoolExecutor(WORKERS)
    futs = {ex.submit(_one, w, tools, repo, d['url'], d['checks'], until): repo for repo, d in todo.items()}
    done, _ = wait(futs, timeout=DEADLINE)
    for f, repo in futs.items():
        if f in done:
            try:
                for (new, old), v in f.result().items():
                    _DONE[(repo, new, old)] = v
            except Exception as e:
                for new, old, _ in todo[repo]['checks']:
                    _DONE[(repo, new, old)] = (False, f'gate error: {str(e)[:160]}')
        else:  # not cached: asked again next pass
            for new, old, _ in todo[repo]['checks']:
                _DONE.setdefault(('~' + repo, new, old), (False, f'gate deadline ({DEADLINE} s) reached first'))
    ex.shutdown(wait=False, cancel_futures=True)  # running gates end by their own caps
    return {k: _DONE.get(k) or _DONE.get(('~' + k[0], k[1], k[2])) for k in items}
