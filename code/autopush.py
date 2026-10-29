"""Keeps every South American law repository current, so country agents never wait on a push.

    python -X utf8 scripts/south-america-law/autopush.py            # one pass over all 12 countries, in parallel
    python -X utf8 scripts/south-america-law/autopush.py --loop 180 # a pass every 180 seconds

For each country, in parallel:
1. wip: snapshots scripts/<slug>-law (no .cache, temporary builds or files over 50 MB) onto the branch `wip` of
   lexifina/<slug>-law, without touching the clone's checkout (a private index and plumbing), and pushes it if it
   changed.
2. main: when corpus.json changed since the last pass, rebuilds the clone with scripts/gitlaw_common/build.py, runs
   check.py, and pushes main, the future branch and the tags only if the check is clean.
The result of each pass is written to scripts/<slug>-law/BUILD_STATUS.json, which the country agent reads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT.parent
COMMON = ROOT / 'scripts' / 'gitlaw_common'
sys.path.insert(0, str(COMMON))
from build import load  # noqa: E402
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
SKIP_DIRS = {'.cache', '__pycache__', '.tmp-build', '.tmp', 'tmp'}
MAX_FILE = 50 * 1024 * 1024
WIP_AUTHOR = {'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': 'world-law@lexifina.com',
              'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': 'world-law@lexifina.com'}


def git(repo: Path, *args: str, env: dict | None = None, data: bytes | None = None, check: bool = True) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, input=data, env={**os.environ, **(env or {})})
    if check and out.returncode:
        raise RuntimeError(f'git {" ".join(args[:3])}: {out.stderr.decode("utf-8", "replace").strip()[:300]}')
    return out.stdout.decode('utf-8', 'replace').strip()


def push(repo: Path, *refs: str) -> str:
    """Force-push with retries: GitHub sometimes answers 'Repository not found' when many pushes run at once."""
    last = ''
    for attempt in range(4):
        out = subprocess.run(['git', 'push', '-q', '-f', 'origin', *refs], cwd=repo, capture_output=True, text=True)
        if out.returncode == 0:
            return 'pushed'
        last = out.stderr.strip()
        if 'did not run because of a timeout' in last:
            # GitHub's secret scan gives up on a very large push (a rebuilt history of thousands of commits). Push the
            # same refs in steps it can scan, then the whole set once more.
            return push_in_steps(repo, *refs)
        if 'GH013' in last:
            break  # a repository rule (secret scanning, file size): retrying cannot help
        time.sleep(15 * (attempt + 1))
    # The whole message goes to its own log: GitHub names the file and line only near the end of it.
    with open(Path(__file__).resolve().parent / 'logs' / 'push-errors.log', 'a', encoding='utf-8') as f:
        f.write(f'=== {repo.name} {" ".join(refs)} at {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}\n{last}\n')
    return f'push failed: {last[:300]}'


def push_in_steps(repo: Path, *refs: str, step: int = 300) -> str:
    """Push each branch in `refs` a few hundred first-parent commits at a time, then the tags in batches, then all the
    refs together (with --prune if asked), so each push is small enough for GitHub's secret scan to finish."""
    log = Path(__file__).resolve().parent / 'logs' / 'push-errors.log'

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(['git', 'push', '-q', '-f', 'origin', *args], cwd=repo, capture_output=True, text=True)

    for ref in refs:
        if not ref.startswith('refs/heads/'):
            continue
        src, _, dst = ref.partition(':')
        commits = git(repo, 'rev-list', '--first-parent', '--reverse', src).split()
        for sha in commits[step - 1::step]:
            r = run(f'{sha}:{dst}')
            if r.returncode:
                with open(log, 'a', encoding='utf-8') as f:
                    f.write(f'=== {repo.name} step {sha[:8]}:{dst}\n{r.stderr.strip()}\n')
                return f'push failed: step {sha[:8]} of {dst}: {r.stderr.strip()[:200]}'
    if any(r.startswith('refs/tags/') for r in refs):
        tags = git(repo, 'tag', '--list').split()
        for i in range(0, len(tags), step):
            r = run(*[f'refs/tags/{t}:refs/tags/{t}' for t in tags[i:i + step]])
            if r.returncode:
                return f'push failed: tags batch {i // step}: {r.stderr.strip()[:200]}'
    r = run(*refs)
    if r.returncode:
        with open(log, 'a', encoding='utf-8') as f:
            f.write(f'=== {repo.name} final {" ".join(refs)}\n{r.stderr.strip()}\n')
        return f'push failed: {r.stderr.strip()[:300]}'
    return 'pushed (in steps)'


def wip(slug: str, folder: Path, repo: Path) -> str:
    files = []
    for p in sorted(folder.rglob('*')):
        rel = p.relative_to(folder)
        if (not p.is_file() or set(rel.parts) & SKIP_DIRS or any(x.startswith('.tmp') or x == '.git' for x in rel.parts[:-1])
                or p.name.startswith('.autopush')
                or p.name == 'BUILD_STATUS.json' or p.stat().st_size > MAX_FILE):
            continue
        files.append((rel.as_posix(), p))
    with tempfile.TemporaryDirectory() as tmp:
        env = {'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        for rel, p in files:
            sha = git(repo, 'hash-object', '-w', '--', str(p))
            git(repo, 'update-index', '--add', '--cacheinfo', f'100644,{sha},wip/{rel}', env=env)
        tree = git(repo, 'write-tree', env=env)
    git(repo, 'fetch', '-q', 'origin', '+refs/heads/wip:refs/remotes/origin/wip', check=False)
    parent = git(repo, 'rev-parse', '-q', '--verify', 'refs/remotes/origin/wip', check=False)
    branch = 'wip'
    if parent:
        # Only extend a wip branch this pipeline made (or the country agents' own wip pushes under scripts/<slug>-law):
        # another session may keep a real build on its repo's wip (Costa Rica's wip held 2188 commits of one).
        who = git(repo, 'log', '-1', '--format=%ae%x1f%s', parent, check=False)
        email, _, subj = who.partition('\x1f')
        ours = email == 'world-law@lexifina.com' or subj.startswith(('Work in progress', 'wip')) or \
            git(repo, 'cat-file', '-t', f'{parent}:wip', check=False) == 'tree'
        if not ours:
            # Leave that wip alone (a person decides whose wins) but keep this folder's work off the machine anyway,
            # on its own branch: `wip-local` only ever holds snapshots of scripts/<slug>-law.
            branch = 'wip-local'
            git(repo, 'fetch', '-q', 'origin', f'+refs/heads/{branch}:refs/remotes/origin/{branch}', check=False)
            parent = git(repo, 'rev-parse', '-q', '--verify', f'refs/remotes/origin/{branch}', check=False)
    if parent and git(repo, 'rev-parse', f'{parent}^{{tree}}') == tree:
        return f'{branch} unchanged'
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    msg = f'Work in progress: scripts/{slug}-law at {now}\n'.encode()
    commit = git(repo, 'commit-tree', tree, *(['-p', parent] if parent else []), env={**WIP_AUTHOR, 'GIT_AUTHOR_DATE': now,
                                                                                     'GIT_COMMITTER_DATE': now}, data=msg)
    git(repo, 'update-ref', f'refs/heads/{branch}', commit)
    return f'{branch} ' + push(repo, f'refs/heads/{branch}:refs/heads/{branch}')


def docs_date(corpus: dict) -> str:
    days = sorted(s.get('retrieved', '') for s in corpus.get('sources', []) if s.get('retrieved'))
    return days[-1] if days else dt.date.today().isoformat()


def main_build(slug: str, folder: Path, repo: Path, state: dict) -> dict:
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
    sha = h.hexdigest()
    if state.get('built_sha') == sha:
        return {'main': f'unchanged since {state.get("built_at")} ({state.get("result")})'}
    day = docs_date(corpus)
    future = corpus['country'].get('future_branch', 'futuro')
    parts = sorted((folder / 'corpus.d').glob('*.json')) if (folder / 'corpus.d').exists() else []
    unverified = [p.name for p in parts if not p.with_suffix('.PUBLISH').exists()]
    published = (folder / 'PUBLISH').exists()

    def build_check(verified_only: bool) -> tuple[bool, dict]:
        env = {**os.environ, 'GITLAW_VERIFIED_PARTS_ONLY': '1' if verified_only else '0'}
        py = [sys.executable, '-X', 'utf8']
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
        return c.returncode == 0, {'stage': 'check', 'check': chk}

    out = {'docs_date': day}
    # 1. Everything, verified or not, streams to `preview`: the whole country as the agents have it now.
    if not published or unverified:
        ok, info = build_check(False)
        if not ok:
            state.update(built_sha=sha, built_at=_now(), result=f'{info["stage"]} failed, not pushed')
            return {'main': f'{info["stage"]} failed, not pushed', **info}
        head = git(repo, 'rev-parse', '--short', 'main')
        out['preview'] = f'{push(repo, "refs/heads/main:refs/heads/preview")} {head}'
        out['check'] = info['check']
        if not published:
            state.update(built_sha=sha, built_at=_now(), result=f'preview {out["preview"]}')
            return {'main': f'preview {out["preview"]} (main waits for PUBLISH)', **out}
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
    refs = ['refs/heads/main:refs/heads/main', 'refs/tags/*:refs/tags/*']
    if git(repo, 'rev-parse', '-q', '--verify', f'refs/heads/{future}', check=False):
        refs.insert(1, f'refs/heads/{future}:refs/heads/{future}')
    result = push(repo, '--prune', *refs)
    head = git(repo, 'rev-parse', '--short', 'main')
    # A failed push is retried on the next pass: only a pushed build is remembered as done.
    state.update(built_sha=sha if not result.startswith('push failed') else None, built_at=_now(), result=f'{result} {head}')
    return {'main': f'{result} {head}' + (f' (left out until verified: {", ".join(unverified)})' if unverified else ''),
            **out, 'check': info['check'], 'commits': git(repo, 'rev-list', '--count', 'main')}


def remote_main_owner(slug: str, repo: Path) -> str:
    """'ours' when the remote main is the scaffold ("<Name>: sources, before any law", by world-law@lexifina.com) or a
    build by the shared builder (its head is the documentation commit by <slug>-law@lexifina.com, or it holds
    data/repo.json). Anything else is another builder's work and is described instead."""
    out = subprocess.run(['git', 'fetch', '-q', '--depth', '1', 'origin', '+refs/heads/main:refs/remotes/origin/main'],
                         cwd=repo, capture_output=True, text=True, timeout=180)
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


def one(slug: str) -> str:
    folder = ROOT / 'scripts' / f'{slug}-law'
    repo = DOCS / f'{slug}-law'
    state_path = folder / '.autopush.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    status = {'at': _now()}
    try:
        if not (repo / '.git').exists():
            subprocess.run(['git', 'clone', '-q', f'https://github.com/lexifina/{slug}-law.git', str(repo)], check=True)
        status['wip'] = wip(slug, folder, repo)
        status.update(main_build(slug, folder, repo, state))
    except Exception as e:  # one country's failure never stops the others
        status['error'] = str(e)[:500]
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
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
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
