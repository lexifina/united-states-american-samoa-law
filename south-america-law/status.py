"""One line per South American country: corpus, local build, pushed head, open issues.

    python -X utf8 scripts/south-america-law/status.py [--remote]
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT.parent
COUNTRIES = ['chile', 'uruguay', 'brazil', 'colombia', 'argentina', 'peru', 'paraguay', 'ecuador', 'bolivia',
             'venezuela', 'guyana', 'suriname']


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8')
    return out.stdout.strip() if out.returncode == 0 else ''


def row(slug: str, remote: bool) -> str:
    folder = ROOT / 'scripts' / f'{slug}-law'
    repo = DOCS / f'{slug}-law'
    corpus = folder / 'corpus.json'
    acts = versions = laws = 0
    if corpus.exists():
        try:
            c = json.loads(corpus.read_text(encoding='utf-8'))
            acts, laws = len(c.get('acts', [])), len(c.get('laws', {}))
            versions = sum(len(a.get('versions', [])) for a in c.get('acts', []))
        except Exception:
            acts = -1
    cache = folder / '.cache'
    cache_n = sum(1 for _ in cache.glob('*')) if cache.exists() else 0
    commits = git(repo, 'rev-list', '--count', 'main') if (repo / '.git').exists() else ''
    head = git(repo, 'rev-parse', '--short', 'main') if commits else ''
    pushed = ''
    if remote:
        out = subprocess.run(['git', 'ls-remote', f'https://github.com/lexifina/{slug}-law.git', 'refs/heads/main'],
                             capture_output=True, text=True, timeout=30).stdout
        pushed = out[:7]
    ver = folder / 'verification.json'
    chk = ''
    if ver.exists():
        v = json.loads(ver.read_text(encoding='utf-8'))
        if 'check' in v:
            chk = f'chk {v["check"]["mismatches"]}mm'
        if 'rebuild' in v:
            chk += ' det ' + ('ok' if v['rebuild'].get('identical') else 'DIFF')
    issues = (folder / 'ISSUES.md').exists()
    return (f'{slug:10} cache {cache_n:5} | corpus acts {acts:2} versions {versions:4} laws {laws:4} | '
            f'repo {commits or "-":>5} {head:8} | pushed {pushed or "-":7} | {chk:16} | {"ISSUES" if issues else ""}')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    remote = '--remote' in sys.argv
    with ThreadPoolExecutor(12) as ex:
        for line in ex.map(lambda s: row(s, remote), COUNTRIES):
            print(line)


if __name__ == '__main__':
    main()
