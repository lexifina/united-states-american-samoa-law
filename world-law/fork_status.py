"""Status of the fork's countries (L–Z, worked Z to A): local folder, corpus, PUBLISH, remote main and wip, last push.

    python -X utf8 scripts/world-law/fork_status.py [--remote]
"""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIST = Path(__file__).resolve().parent / 'fork_countries.json'


def remote(slug: str) -> dict:
    try:
        out = subprocess.run(['git', 'ls-remote', f'https://github.com/lexifina/{slug}-law.git', 'refs/heads/*'],
                             capture_output=True, text=True, timeout=60).stdout
    except subprocess.TimeoutExpired:
        return {'error': 'timeout'}
    return {l.split()[1].rsplit('/', 1)[1]: l.split()[0][:7] for l in out.splitlines() if l.strip()}


def row(slug: str, with_remote: bool) -> str:
    f = ROOT / 'scripts' / f'{slug}-law'
    if not f.is_dir():
        return f'{slug:26} not started'
    corpus = (f / 'corpus.json').exists() or (f / 'corpus.d').is_dir()
    pub = (f / 'PUBLISH').exists()
    prog = f / 'PROGRESS.md'
    age = f'{(time.time() - prog.stat().st_mtime) / 60:.0f}m' if prog.exists() else '-'
    newest = max((p.stat().st_mtime for p in f.rglob('*') if p.is_file() and '.cache' not in p.parts), default=0)
    act = f'{(time.time() - newest) / 60:.0f}m' if newest else '-'
    st = {}
    if (f / 'BUILD_STATUS.json').exists():
        try:
            st = json.loads((f / 'BUILD_STATUS.json').read_text(encoding='utf-8'))
        except ValueError:
            pass
    r = remote(slug) if with_remote else {}
    return (f'{slug:26} corpus={int(corpus)} pub={int(pub)} last-file={act:>4} progress={age:>4} | '
            f'main={r.get("main", "-"):7} wip={r.get("wip", "-"):7} preview={r.get("preview", "-"):7} | '
            f'{str(st.get("main", ""))[:60]}')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    slugs = json.loads(LIST.read_text(encoding='utf-8'))
    with ThreadPoolExecutor(8) as ex:
        for line in ex.map(lambda s: row(s, '--remote' in sys.argv), slugs):
            print(line)


if __name__ == '__main__':
    main()
