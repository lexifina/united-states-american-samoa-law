"""Publish steps of a Windows loop, run inside WSL with the repo on ext4 (see README-wsl.md, "Publish loops").

A loop that fetches keeps running on Windows (fetch_scheduler's leases and host state live under %LOCALAPPDATA%), and
sends only its publish side here: the clone of the published main, the append, check.py, the audit and the push.

    import wsl_exec as W
    repo = W.fresh('taiwan-law')                          # ~/gitlaw-builds/taiwan-law at origin/main (a WSL path)
    W.run([sys.executable, '-X', 'utf8', 'ly_block.py', '--repo', repo, ...], cwd=HERE, env=BOT)
    W.run(['git', 'rev-parse', 'main'], cwd=repo)
    W.push('taiwan-law', repo, env=BOT)                    # identity + date gate, then push_clean.py --main

- args[0] = 'git' runs WSL git; python (sys.executable, 'python', 'py') runs ~/gitlaw-builds/.venv/bin/python; anything
  else runs as given. Windows paths in arguments and cwd (C:\\..., C:/...) become /mnt/c/... paths.
- Every process runs under nice -n 10, with GIT_CONFIG_GLOBAL=~/gitlaw-builds/gitconfig (Windows credential manager;
  the Windows user.email, which private.audit_push keeps out of pushes), PYTHONTZPATH='' (the tzdata package, as on
  Windows), PYTHONDONTWRITEBYTECODE=1 and GITLAW_FETCH_DRY=1: nothing in WSL ever fetches from a publisher; a page that
  is not cached raises fetch_scheduler.DryMiss instead.
- GIT_AUTHOR_*/GIT_COMMITTER_* (and GITLAW_*) are passed on from `env`, so the bot identity is explicit.
- A slug whose scripts folder holds `.wsl-only` must never be published from NTFS again: `require_wsl_only(folder)`.
Standard library only.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISTRO = os.environ.get('GITLAW_WSL_DISTRO', 'Ubuntu')
WIN_ABS = re.compile(r'^([A-Za-z]):[\\/](.*)$', re.S)
PASS = re.compile(r'^(GIT_(AUTHOR|COMMITTER)_(NAME|EMAIL|DATE)|GITLAW_\w+)$')
OK_MAIL = re.compile(r'(lexifina\.com|\.invalid)$', re.I)
_home: str | None = None
IN_WSL = os.name != 'nt'   # the same calls work from a loop that itself runs in WSL


def wsl_exe() -> str:
    w = shutil.which('wsl.exe') or shutil.which('wsl')
    if not w:
        raise RuntimeError('wsl.exe not found')
    return w


def home() -> str:
    """The WSL home (/home/alany), asked once."""
    global _home
    if _home is None and IN_WSL:
        _home = os.environ.get('HOME') or '/home/alany'
    if _home is None:
        r = subprocess.run([wsl_exe(), '-d', DISTRO, '--exec', '/usr/bin/printenv', 'HOME'], capture_output=True,
                           text=True, timeout=120)
        _home = r.stdout.strip() or '/home/alany'
    return _home


def root() -> str:
    return f'{home()}/gitlaw-builds'


def to_wsl(p) -> str:
    """C:\\x\\y or C:/x/y -> /mnt/c/x/y; ~/x -> /home/<user>/x; anything else unchanged."""
    s = str(p)
    m = WIN_ABS.match(s)
    if m:
        return f'/mnt/{m.group(1).lower()}/' + m.group(2).replace('\\', '/')
    if s == '~' or s.startswith('~/'):
        return home() + s[1:]
    return s


def unc(p: str) -> str:
    """A WSL path as Windows sees it (\\\\wsl.localhost\\Ubuntu\\home\\...): slow, fine for a few reads."""
    return f'\\\\wsl.localhost\\{DISTRO}' + to_wsl(p).replace('/', '\\')


def repo_path(slug: str) -> str:
    return f'{root()}/{slug}'


def _prog(a: str) -> str:
    low = os.path.basename(str(a)).lower()
    if str(a) == sys.executable or low in ('python', 'python.exe', 'python3', 'py', 'py.exe', 'pythonw.exe'):
        return f'{root()}/.venv/bin/python'
    return to_wsl(a)


def command(args: list, cwd=None, env: dict | None = None) -> list[str]:
    """The wsl.exe command line for args (see module doc)."""
    e = {'GIT_CONFIG_GLOBAL': f'{root()}/gitconfig', 'PYTHONTZPATH': '', 'PYTHONUTF8': '1',
         'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C.UTF-8', 'GIT_TERMINAL_PROMPT': '0'}
    # the shared WSL gitconfig carries no identity; the push audit reads the personal address from the Windows one
    e['GITLAW_PERSONAL_GITCONFIG'] = to_wsl(Path.home() / '.gitconfig')
    e.update({k: v for k, v in (env or os.environ).items() if PASS.match(k) and k != 'GITLAW_WSL_DISTRO'})
    lad = (env or {}).get('LOCALAPPDATA') or os.environ.get('LOCALAPPDATA')
    if lad:   # the CPU-load pause log (%LOCALAPPDATA%\gitlaw-cpu.log) is read from the Windows side
        e['LOCALAPPDATA'] = to_wsl(lad)
    e['GITLAW_FETCH_DRY'] = '1'   # never fetch from a publisher in WSL: the leases live on Windows
    e['GITLAW_IN_WSL'] = '1'
    args = [str(a) for a in args]
    if IN_WSL:
        return ['/usr/bin/env', *[f'{k}={v}' for k, v in e.items()], 'nice', '-n', '10', _prog(args[0]),
                *[to_wsl(a) for a in args[1:]]]
    full = [wsl_exe(), '-d', DISTRO, '--cd', to_wsl(cwd) if cwd else '~', '--exec', '/usr/bin/env',
            *[f'{k}={v}' for k, v in e.items()], 'nice', '-n', '10', _prog(args[0]), *[to_wsl(a) for a in args[1:]]]
    return full


def run(args: list, cwd=None, env: dict | None = None, timeout=None, input=None, text=True,
        check=False) -> subprocess.CompletedProcess:
    kw = dict(encoding='utf-8', errors='replace') if text else {}
    if IN_WSL and cwd:
        kw['cwd'] = to_wsl(cwd)
    return subprocess.run(command(args, cwd, env), capture_output=True, text=text, timeout=timeout, input=input,
                          check=check, **kw)


def popen(args: list, cwd=None, env: dict | None = None, **kw) -> subprocess.Popen:
    if IN_WSL and cwd:
        kw.setdefault('cwd', to_wsl(cwd))
    return subprocess.Popen(command(args, cwd, env), **kw)


def detach(args: list, cwd, log, pidfile=None, env: dict | None = None) -> int:
    """Start a whole loop in WSL, detached from this console (Windows side only): nice 10, the env of command(),
    stdout+stderr appended to `log` (a Windows path). Returns the PID of its wsl.exe, which is also written to
    `pidfile`; stopping that process stops the loop."""
    flags = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    with open(log, 'ab') as out:
        p = subprocess.Popen(command(args, cwd, env), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             creationflags=flags, close_fds=True)
    if pidfile:
        Path(pidfile).write_text(str(p.pid), encoding='ascii')
    return p.pid


def git(repo: str, *a: str, env: dict | None = None, timeout=None) -> str:
    return run(['git', *a], cwd=repo, env=env, timeout=timeout).stdout.strip()


def fresh(slug: str, url: str | None = None, name: str | None = None, env: dict | None = None) -> str:
    """~/gitlaw-builds/<name or slug> at the published main (clone once, then fetch + hard reset + clean).
    Returns the WSL path; raises RuntimeError with git's message."""
    url = url or f'https://github.com/lexifina/{slug}.git'
    repo = f'{root()}/{name or slug}'
    r = run(['test', '-d', f'{repo}/.git'])
    steps = ([['git', '-C', repo, 'fetch', '-q', '--prune', 'origin', '+refs/heads/main:refs/remotes/origin/main',
               '+refs/tags/*:refs/tags/*'],   # exactly the remote's tags, as append_gate.sync
              ['git', '-C', repo, 'checkout', '-q', '-f', '-B', 'main', 'origin/main'],
              ['git', '-C', repo, 'reset', '-q', '--hard', 'origin/main'], ['git', '-C', repo, 'clean', '-q', '-fdx']]
             if r.returncode == 0 else
             [['mkdir', '-p', root()], ['git', 'clone', '-q', url, repo]])
    for s in steps + [['git', '-C', repo, 'config', 'gc.auto', '0'],
                      ['git', '-C', repo, 'config', 'core.autocrlf', 'false']]:
        r = run(s, env=env, timeout=3600)
        if r.returncode:
            raise RuntimeError(f'{" ".join(s[:4])}: {(r.stderr or r.stdout).strip()[-300:]}')
    return repo


def gate(repo: str, ref: str = 'main', env: dict | None = None) -> list[str]:
    """Problems in what a push of `ref` would add over the published main: an author or committer outside
    lexifina.com / .invalid, or a commit dated after now. Fetches origin main first. Empty = ok."""
    run(['git', 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main'], cwd=repo, env=env, timeout=1800)
    has = run(['git', 'rev-parse', '-q', '--verify', 'refs/remotes/origin/main'], cwd=repo).returncode == 0
    span = f'origin/main..{ref}' if has else ref
    out = run(['git', 'log', span, '--format=%H %ae %ce %ct %at'], cwd=repo, env=env, timeout=1800).stdout.split('\n')
    bad, now = [], time.time() + 300
    for line in filter(None, out):
        sha, ae, ce, ct, at = line.split(' ')
        for m in (ae, ce):
            if not OK_MAIL.search(m):
                bad.append(f'{sha[:9]}: identity {m}')
        if int(ct) > now:
            bad.append(f'{sha[:9]}: committer date in the future ({ct})')
    return bad


def push(slug: str, repo: str, env: dict | None = None, extra: list[str] | None = None,
         timeout=3 * 3600) -> subprocess.CompletedProcess:
    """gate(), then push_clean.py <repo> <slug> --main inside WSL (fast-forward only, audit_push included).
    A failed gate returns a CompletedProcess with returncode 4 and the findings in stdout."""
    bad = gate(repo, env=env)
    if bad:
        return subprocess.CompletedProcess([], 4, 'wsl_exec gate refused:\n  ' + '\n  '.join(bad[:20]), '')
    return run([sys.executable, '-X', 'utf8', str(HERE / 'push_clean.py'), repo, slug, '--main', *(extra or [])],
               cwd=repo, env=env, timeout=timeout)


def require_wsl_only(folder) -> None:
    """Raise when a .wsl-only corpus is about to be published from Windows/NTFS."""
    if (Path(folder) / '.wsl-only').exists() and os.name == 'nt' and not os.environ.get('GITLAW_IN_WSL'):
        raise SystemExit(f'{folder} is WSL-only (.wsl-only): publish through gitlaw_common/wsl_exec.py, not NTFS')


def is_wsl_only(slug_or_folder) -> bool:
    p = Path(slug_or_folder)
    if not p.is_absolute():
        p = HERE.parent / str(slug_or_folder)
    return (p / '.wsl-only').exists()
