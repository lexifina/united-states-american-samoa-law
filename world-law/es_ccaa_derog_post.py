"""After the autopush: for each unit whose derogadas PUBLISH is older than its BUILD_STATUS, fetch the live main (and
futuro) into the private mirror, diff it against the main it replaced (BUILD_STATUS "old->new"), and require that only
the new repealed acts' folders and the docs changed. Prints one line per unit."""
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import es_ccaa as e  # noqa: E402

DOCS_PATHS = {'README.md', 'LICENSE', 'REPRODUCE.md', 'jurisdiction.json', 'data', 'tools', '.gitattributes', 'AGENTS.md',
              'CLAUDE.md', '.mcp.json', 'MCP.md', 'CHANGELOG.md'}


def git(d, *a):
    return subprocess.run(['git', *a], cwd=d, capture_output=True, text=True, encoding='utf-8').stdout


for u in sys.argv[1:] or [x for x in e.UNITS if x not in e.CITY]:
    f = e.folder(u)
    pubs = sorted((f / 'corpus.d').glob('6*-derogadas-*.PUBLISH'))
    st = f / 'BUILD_STATUS.json'
    if not pubs:
        continue
    if not st.exists() or st.stat().st_mtime < max(p.stat().st_mtime for p in pubs):
        print(u, 'WAIT autopush has not run since PUBLISH')
        continue
    s = json.loads(st.read_text(encoding='utf-8'))
    m = re.search(r'main verified rebuild ([0-9a-f]+)->([0-9a-f]+)', s.get('main', ''))
    if not m:
        print(u, 'WAIT', s.get('main', '')[:160])
        continue
    old, new = m.groups()
    mirror = e.HERE / '.cache' / 'es-derogcheck' / f'{e.repo_name(u)}.git'
    remote = f'https://github.com/lexifina/{e.repo_name(u)}.git'
    if not mirror.exists():
        mirror.mkdir(parents=True)
        git(mirror, 'init', '-q', '--bare')
    live = dict(reversed(l.split('\t')) for l in git(mirror, 'ls-remote', remote, 'refs/heads/main', 'refs/heads/futuro').splitlines())
    git(mirror, 'fetch', '-q', remote, '+refs/heads/main:refs/post/main', *(['+refs/heads/futuro:refs/post/futuro'] if 'refs/heads/futuro' in live else []))
    if not git(mirror, 'cat-file', '-t', old).strip():
        # the replaced tip is archived on world-law-ops (archive3/<repo>/main/<sha12>)
        ops = git(e.DOCS / e.repo_name(u), 'remote', 'get-url', 'ops').strip() or 'https://github.com/lexifina/world-law-ops.git'
        refs = [l.split('	')[1] for l in git(mirror, 'ls-remote', ops, f'refs/heads/archive3/{e.repo_name(u)}/main/*').splitlines()]
        refs = [r for r in refs if r.rsplit('/', 1)[-1].startswith(old[:9])]
        if refs:
            git(mirror, 'fetch', '-q', ops, f'+{refs[0]}:refs/post/old')
    if not git(mirror, 'cat-file', '-t', old).strip():
        print(u, f'old tip {old} not available')
        continue
    newacts = {a['slug'] for p in pubs for a in json.loads(p.with_suffix('.json').read_text(encoding='utf-8'))['acts']}
    if not live.get('refs/heads/main', '').startswith(new):
        print(u, f'live main {live.get("refs/heads/main", "")[:9]} is not the rebuild {new}')
        continue
    changed = {x.split('/')[0] for x in git(mirror, 'diff', '--name-only', old, 'refs/post/main').split()}
    bad = changed - newacts - DOCS_PATHS
    missing = newacts - {x for x in git(mirror, 'ls-tree', '--name-only', 'refs/post/main').split()}
    print(u, 'OK' if not bad and not missing else 'PROBLEM', f'main {old[:9]}->{live["refs/heads/main"][:9]}',
          f'{len(newacts)} new act folders; other changed paths: {sorted(changed - newacts)}',
          f'unexpected: {sorted(bad)[:5]}' if bad else '', f'missing: {sorted(missing)[:5]}' if missing else '')
