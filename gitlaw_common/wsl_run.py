"""Run a git-for-law build, check or push inside WSL, with the output repository on ext4 (see README-wsl.md).

    python wsl_run.py setup                                   # once: venv + tzdata, git credential helper
    python wsl_run.py build <slug|folder> --docs-date D [--compare DIR] [--site-data FILE] [--repo DIR]
    python wsl_run.py check <slug|folder> [--write] [--repo DIR]
    python wsl_run.py push  <slug|folder> [--main] [--branch B] [--repo DIR]
    python wsl_run.py git   <slug|folder> <git args...>       # git inside the WSL build repo
    python wsl_run.py py    <slug|folder> <script> [--repo DIR] <args...>  # a builder script (append_gate.py, ...)
    python wsl_run.py path  <slug|folder>                     # where the build repo is (also as a \\wsl.localhost path)

<slug> is a folder name under scripts/ (e.g. chile-law); a folder path works too. The build repo is
~/gitlaw-builds/<slug> inside WSL. build/check/push take the same options as build.py/check.py/push_clean.py and give
the same output and exit code; Windows paths in the arguments (C:\\..., or relative paths that exist) are passed as
/mnt/c/... paths. GITLAW_* environment variables (GITLAW_VERIFIED_PARTS_ONLY, GITLAW_NO_CHECKOUT, ...) are passed on.
--time prints wall and CPU time of the WSL side to stderr. Standard library only.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISTRO = os.environ.get('GITLAW_WSL_DISTRO', 'Ubuntu')
WIN_ABS = re.compile(r'^([A-Za-z]):[\\/](.*)$')
TZDATA_VERSION = '2026.6'


def to_wsl(p: str | Path) -> str:
    """C:\\Users\\x -> /mnt/c/Users/x (drvfs mounts at /mnt/<drive>)."""
    m = WIN_ABS.match(str(p))
    if not m:
        raise ValueError(f'not an absolute Windows path: {p}')
    return f'/mnt/{m.group(1).lower()}/' + m.group(2).replace('\\', '/')


def convert(arg: str) -> str:
    """A Windows path argument (absolute, or relative and existing) as a WSL path; anything else unchanged."""
    if arg.startswith('--') and '=' in arg:
        opt, _, val = arg.partition('=')
        return f'{opt}={convert(val)}'
    if WIN_ABS.match(arg):
        return to_wsl(arg)
    if arg.startswith(('/', '~')):  # already a WSL path
        return arg
    if not arg.startswith('-') and ('/' in arg or '\\' in arg or arg in ('.', '..')) and Path(arg).exists():
        return to_wsl(Path(arg).resolve())
    return arg


def wheels() -> Path:
    """pip and tzdata wheels for the WSL venv (Ubuntu's python3 has no ensurepip), downloaded with Windows pip."""
    d = Path(tempfile.gettempdir()) / 'gitlaw-wsl-wheels'
    d.mkdir(exist_ok=True)
    if not list(d.glob('pip-*.whl')) or not list(d.glob(f'tzdata-{TZDATA_VERSION}-*.whl')):
        subprocess.run([sys.executable, '-m', 'pip', 'download', '-q', '--no-deps', '--only-binary=:all:', 'pip',
                        f'tzdata=={TZDATA_VERSION}', '-d', str(d)], check=True)
    return d


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv else 2
    timing = '--time' in argv
    argv = [a for a in argv if a != '--time']
    cmd, rest = argv[0], argv[1:]
    env = {k: v for k, v in os.environ.items() if k.startswith('GITLAW_') and k != 'GITLAW_WSL_DISTRO'}
    env.update(GITLAW_COMMON=to_wsl(HERE), GITLAW_SCRIPTS=to_wsl(HERE.parent), GITLAW_WIN_HOME=to_wsl(Path.home()))
    if timing:
        env['GITLAW_WSL_TIME'] = '1'
    if cmd == 'setup':
        d = wheels()
        env['GITLAW_WHEEL_DIR'] = to_wsl(d)
        env['GITLAW_PIP_WHEEL'] = to_wsl(sorted(d.glob('pip-*.whl'))[-1])
        env['GITLAW_TZDATA_VERSION'] = TZDATA_VERSION
    elif cmd != 'git':
        rest = [convert(a) for a in rest]
    elif rest:
        rest = [convert(rest[0])] + rest[1:]
    wsl = shutil.which('wsl.exe') or shutil.which('wsl')
    if not wsl:
        sys.exit('wsl_run: wsl.exe not found')
    # --exec: no shell in between, so arguments arrive exactly as given. --cd ~: start on ext4, not in /mnt/c.
    full = [wsl, '-d', DISTRO, '--cd', '~', '--exec', '/usr/bin/env', *[f'{k}={v}' for k, v in env.items()],
            '/bin/bash', to_wsl(HERE / 'wsl_build.sh'), cmd, *rest]
    try:
        return subprocess.run(full).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
