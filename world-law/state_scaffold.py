"""Create lexifina/united-states-<state>-law (public) and push the scaffold first commit if it does not exist.

    python -X utf8 scripts/world-law/state_scaffold.py <state-slug> "<State name>" "<source name>" "<source url>" "<what is planned>"
"""
import subprocess
import sys
import tempfile
from pathlib import Path

state, name, src, url, plan = sys.argv[1:6]
repo = f'united-states-{state}-law'
remote = f'https://github.com/lexifina/{repo}.git'


def run(*a, cwd=None, check=True):
    p = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise SystemExit(f'{a[:3]} failed: {p.stderr[:400]}')
    return p


ls = run('git', 'ls-remote', remote, check=False)
if ls.returncode == 0 and ls.stdout.strip():
    print('EXISTS', repo, ls.stdout.splitlines()[0][:60])
    raise SystemExit(0)
exists = run('gh', 'api', f'repos/lexifina/{repo}', check=False).returncode == 0
if not exists:
    run('gh', 'api', 'orgs/lexifina/repos', '-f', f'name={repo}', '-F', 'private=false', '-f', f'description={name} law as git history')
    print('CREATED', repo)
d = Path(tempfile.mkdtemp(prefix='scaffold-'))
run('git', 'init', '-q', '-b', 'main', cwd=d)
(d / 'README.md').write_text(f"""# {name}: law as git history

Work in progress. This repository will hold the law of {name} as a git history: one file per provision, one commit per
change, `git blame` and `git log` working line by line.

Planned first build: {plan}

Source: [{src}]({url}).
""", encoding='utf-8', newline='\n')
(d / 'SOURCES.md').write_text(f"""# Sources

- {src}: <{url}>

Statute text is not copyrightable (Georgia v. Public.Resource.Org, 2020). Annotations published under a state copyright
claim are not used. The terms and licence will be recorded in LICENSE with the first build.
""", encoding='utf-8', newline='\n')
run('git', 'add', '-A', cwd=d)
run('git', '-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m',
    f'United States ({name}): sources, before any law', cwd=d)
run('git', 'remote', 'add', 'origin', remote, cwd=d)
p = run('git', 'push', '-q', 'origin', 'main', cwd=d, check=False)
print(p.stdout, p.stderr[-300:])
print(run('git', 'ls-remote', remote).stdout)
