"""private.py on WSL paths: scrub(), the audit's home-path marker and audit_push() catch this machine's home however
Windows, Git Bash or WSL writes it, and the personal address is found from GITLAW_PERSONAL_GITCONFIG when the global
git config has no identity (autopush_dell in WSL).

    python -X utf8 scripts/gitlaw_common/test_private_wsl.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import private  # noqa: E402

FAIL = []
HOME_WIN = 'C:' + '\\' + 'Users' + '\\' + 'alany'
WSL_UNC = '\\\\wsl.localhost\\Ubuntu\\home\\alany'
WSL_DOLLAR = '\\\\wsl$\\Ubuntu\\home\\alany'


def ok(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra else ''), flush=True)
    if not cond:
        FAIL.append(name)


paths = {
    'windows': (HOME_WIN + '\\Documents\\x', '~\\Documents\\x'),
    'windows forward': ('C:/Users/alany/Documents/x', '~/Documents/x'),
    'git bash': ('/c/Users/alany/Documents/x', '~/Documents/x'),
    'wsl drvfs c': ('/mnt/c/Users/alany/Documents/x', '~/Documents/x'),
    'wsl drvfs d': ('/mnt/d/Users/alany/x', '~/x'),
    'wsl home': ('/home/alany/gitlaw-builds/autopush-dell/x-law', '~/gitlaw-builds/autopush-dell/x-law'),
    'wsl unc': (WSL_UNC + '\\gitlaw-builds\\x', '~\\gitlaw-builds\\x'),
    'wsl dollar unc': (WSL_DOLLAR + '\\gitlaw-builds\\x', '~\\gitlaw-builds\\x'),
}
for name, (raw, want) in paths.items():
    text = f'built in {raw} on the day'
    got = private.scrub(text)
    ok(f'scrub {name}', got == f'built in {want} on the day', got)
    ok(f'audit marker {name}', bool(private.AUDIT_MARKS['home path'].search(text.encode())))
    ok(f'scrubbed text clean {name}', not private.AUDIT_MARKS['home path'].search(got.encode())
       and not private.HOME.search(got))
for text in ('/home/bob/x', 'the homepage of alany', '/homestead/alany', 'Users/alanyx'):
    ok(f'no false hit: {text}', private.scrub(text) == text and not private.AUDIT_MARKS['home path'].search(text.encode()))

with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    # The personal address from a named gitconfig, with an empty global config (as autopush runs in WSL).
    personal = t / 'win.gitconfig'
    personal.write_text('[user]\n\tname = someone\n\temail = someone@example.org\n', encoding='utf-8')
    empty = t / 'empty.gitconfig'
    empty.write_text('', encoding='utf-8')
    saved = {k: os.environ.get(k) for k in ('GIT_CONFIG_GLOBAL', 'GITLAW_PERSONAL_GITCONFIG')}
    os.environ['GIT_CONFIG_GLOBAL'] = str(empty)
    os.environ.pop('GITLAW_PERSONAL_GITCONFIG', None)
    ok('no identity, no personal config: nothing known', private._personal_emails() == set())
    os.environ['GITLAW_PERSONAL_GITCONFIG'] = str(personal)
    ok('personal address from GITLAW_PERSONAL_GITCONFIG', private._personal_emails() == {'someone@example.org'})

    # audit_push over a repo whose added blobs name the WSL home, and one with the personal address in a commit.
    repo = t / 'r'
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': 'x-law@lexifina.com',
           'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': 'x-law@lexifina.com'}

    def g(*a, e=None):
        return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, env=e or env, check=True).stdout.strip()
    repo.mkdir()
    g('init', '-q', '-b', 'main')
    (repo / 'README.md').write_text('clean\n', encoding='utf-8')
    g('add', '.')
    g('commit', '-q', '-m', 'base')
    base = g('rev-parse', 'HEAD')
    ok('clean commit: no findings', private.audit_push(repo, base) == [])
    for i, (name, (raw, _)) in enumerate(paths.items()):
        (repo / 'README.md').write_text(f'built in {raw}\n', encoding='utf-8')
        g('commit', '-q', '-am', f'path {i}')
        found = private.audit_push(repo, g('rev-parse', 'HEAD'), base)
        ok(f'audit_push finds {name}', any(f.startswith('home path') for f in found), '; '.join(found))
        g('reset', '-q', '--hard', base)
    (repo / 'README.md').write_text('contact someone@example.org\n', encoding='utf-8')
    g('commit', '-q', '-am', 'mail in blob')
    ok('audit_push finds the personal address in a blob',
       any(f.startswith('personal email') for f in private.audit_push(repo, g('rev-parse', 'HEAD'), base)))
    g('reset', '-q', '--hard', base)
    (repo / 'x.md').write_text('x\n', encoding='utf-8')
    g('add', '.')
    g('commit', '-q', '-m', 'personal identity', e={**env, 'GIT_COMMITTER_EMAIL': 'someone@example.org'})
    ok('audit_push finds a personal committer',
       any('someone@example.org' in f for f in private.audit_push(repo, g('rev-parse', 'HEAD'), base)))
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print(f'{"FAILED: " + ", ".join(FAIL) if FAIL else "all passed"}')
sys.exit(1 if FAIL else 0)
