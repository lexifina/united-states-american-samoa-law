"""Pushes a `wip` snapshot of every fork country folder (L–Z) to its own repo, every N seconds, until each has a corpus.

    python -X utf8 scripts/world-law/fork_wip.py --loop 90

The original session's autopush loop picks a folder up only once it has corpus.json or corpus.d/. Until then this
loop makes sure the agents' scripts, PROGRESS.md and sources reach GitHub, so nothing lives only on this machine. It
uses autopush.wip() unchanged: snapshot via a private index and plumbing, push only if the tree changed. It never
touches main, preview or tags, and it skips any folder autopush already handles (one with a corpus).
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'south-america-law'))
import autopush  # noqa: E402

SLUGS = json.loads((Path(__file__).resolve().parent / 'fork_countries.json').read_text(encoding='utf-8'))
DOCS = ROOT.parent


def one(slug: str) -> str:
    folder = ROOT / 'scripts' / f'{slug}-law'
    if not folder.is_dir():
        return f'{slug:24} not started'
    if (folder / 'corpus.json').exists() or (folder / 'corpus.d').is_dir():
        return f'{slug:24} has a corpus: autopush handles it'
    repo = DOCS / f'{slug}-law'
    try:
        if not (repo / '.git').exists():
            subprocess.run(['git', 'clone', '-q', f'https://github.com/lexifina/{slug}-law.git', str(repo)],
                           check=True, capture_output=True, timeout=180)
        return f'{slug:24} {autopush.wip(slug, folder, repo)}'
    except Exception as e:  # one country never stops the others
        return f'{slug:24} error {str(e)[:100]}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loop', type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    while True:
        t = time.time()
        with ThreadPoolExecutor(8) as ex:
            lines = list(ex.map(one, SLUGS))
        stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        print(f'--- fork wip pass at {stamp} ({time.time() - t:.0f} s)', *[l for l in lines if 'not started' not in l],
              sep='\n', flush=True)
        if not args.loop:
            return
        time.sleep(max(10, args.loop - (time.time() - t)))


if __name__ == '__main__':
    main()
