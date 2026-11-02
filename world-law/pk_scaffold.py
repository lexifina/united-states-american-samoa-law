"""Create lexifina/pakistan-<unit>-law (public, via the API) and push the scaffold first commit if it does not exist.

    python -X utf8 scripts/world-law/pk_scaffold.py <state-slug> "<Unit name>" "<sources line>" "<tz offset e.g. -0500>"

Skips when the repo already exists with refs. The token comes from the stored git credential and is never printed.
Private (never published).
"""
import json, os, subprocess, sys, tempfile, urllib.request, urllib.error
from pathlib import Path

slug, name, sources, tz = sys.argv[1:5]
repo = f"pakistan-{slug}-law"
url = f'https://github.com/lexifina/{repo}.git'
ls = subprocess.run(['git', 'ls-remote', url], capture_output=True, text=True)
if ls.returncode == 0 and ls.stdout.strip():
    print('EXISTS with refs:\n' + ls.stdout); sys.exit(0)
cred = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n', capture_output=True, text=True).stdout
tok = dict(l.split('=', 1) for l in cred.splitlines() if '=' in l).get('password')
if ls.returncode != 0:
    req = urllib.request.Request('https://api.github.com/orgs/lexifina/repos', method='POST',
        data=json.dumps({'name': repo, 'private': False, 'description': f'{name} law as git history'}).encode(),
        headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json', 'User-Agent': 'lexifina-gitlaw'})
    try:
        print('created', json.load(urllib.request.urlopen(req))['html_url'])
    except urllib.error.HTTPError as e:
        print('create failed', e.code, e.read()[:300]); sys.exit(1)
d = Path(tempfile.mkdtemp(prefix='scaffold-'))
(d / 'README.md').write_text(f'# {name}: law history in git\n\nThe law of {name} as a git history, one commit per change on the day it took effect.\n\nThis repository is a scaffold: sources are being checked and no law has been added yet.\n', encoding='utf-8', newline='\n')
(d / 'SOURCES.md').write_text(f'# Sources\n\n{sources}\n\nNothing has been copied yet.\n', encoding='utf-8', newline='\n')
e = {**os.environ, 'GIT_AUTHOR_DATE': f'2026-10-30T12:00:00{tz}', 'GIT_COMMITTER_DATE': f'2026-10-30T12:00:00{tz}'}
def g(*a): return subprocess.run(['git', *a], cwd=d, env=e, capture_output=True, text=True)
g('init', '-q', '-b', 'main'); g('config', 'core.autocrlf', 'false'); g('add', '.')
print(g('-c', 'user.name=Lexifina', '-c', f'user.email={repo}@lexifina.com', 'commit', '-q', '-m', f'Pakistan ({name}): sources, before any law').stderr)
g('remote', 'add', 'origin', url)
p = g('push', '-q', 'origin', 'main'); print(p.returncode, p.stderr[-300:])
print(subprocess.run(['git', 'ls-remote', url], capture_output=True, text=True).stdout)
