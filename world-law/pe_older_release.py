"""Release the claims of the Peru units whose older-ordinance run (pe_regions.py older) has ended, once the autopush has
pushed their verified build, and keep a per-repo summary (gitlaw-scraper-dell, 2026-10-31). No requests to El Peruano.

    python -X utf8 scripts/world-law/pe_older_release.py <fetcher pid> [--every 300]

A unit is released when its PROGRESS.md says `older: stopped with ...` (or STOPPED), nothing is staged, and the remote
main (git ls-remote) equals the local clone's main built from every PUBLISH part. When the fetcher has exited and every
claimed unit is released, the summary goes to logs/pe-older-summary.json and the script exits.
"""
from __future__ import annotations

import calendar
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pe_regions as P  # noqa: E402

OUT = HERE / 'logs' / 'pe-older-summary.json'


def alive(pid: int) -> bool:
    r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True)
    return str(pid) in r.stdout


def ended(u: str) -> bool:
    p = P.folder(u) / 'PROGRESS.md'
    if not p.exists():
        return False
    lines = p.read_text(encoding='utf-8').splitlines()
    starts = [i for i, l in enumerate(lines) if 'older: catalogue' in l]
    if not starts:
        return False
    return any('older: stopped with' in l or 'STOPPED' in l for l in lines[starts[0]:])


def summary(u: str) -> dict:
    d = P.folder(u) / 'corpus.d'
    parts = sorted(p.stem for p in d.glob(f'{P.OLDER_PREFIX}-*.PUBLISH'))
    added = sum(len(json.loads((d / f'{n}.json').read_text(encoding='utf-8'))['acts']) for n in parts)
    total = sum(len(json.loads(p.read_text(encoding='utf-8'))['acts']) for p in d.glob('*.json')
                if p.with_suffix('.PUBLISH').exists())
    return {'repo': P.repo_name(u), 'ordinances_added': added, 'parts': parts, 'ordinances_total': total}


def main():
    pid = int(sys.argv[1])
    every = int(sys.argv[sys.argv.index('--every') + 1]) if '--every' in sys.argv else 300
    res = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    while True:
        running = alive(pid)
        pending = []
        for u in P.UNITS:
            claim = P.CLAIMS / f'{P.repo_name(u)}.txt'
            if not claim.exists() or not claim.read_text(encoding='utf-8', errors='replace').startswith(P.SESSION):
                continue
            if 'older' not in claim.read_text(encoding='utf-8', errors='replace'):
                continue  # not a claim of this round
            if not (ended(u) or not running) or list(P.stage_dir(u).glob('*.json')):
                pending.append(u)
                continue
            heads = P.remote_heads(u)
            local = subprocess.run(['git', 'rev-parse', 'main'], cwd=P.DOCS / P.repo_name(u), capture_output=True,
                                   text=True).stdout.strip()
            st = json.loads((P.folder(u) / 'BUILD_STATUS.json').read_text(encoding='utf-8')) \
                if (P.folder(u) / 'BUILD_STATUS.json').exists() else {}
            newest = max((p.stat().st_mtime for p in (P.folder(u) / 'corpus.d').glob('*.PUBLISH')), default=0)
            at = calendar.timegm(time.strptime(st['at'], '%Y-%m-%dT%H:%M:%SZ')) if st.get('at') else 0
            if heads.get('main') != local or at < newest or 'fail' in str(st.get('main', '')):
                pending.append(u)
                continue
            res[u] = {**summary(u), 'main': local[:7], 'released': P.now()}
            claim.unlink()
            P.progress(u, f'older: claim released; main {local[:7]}')
            OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
            print(time.strftime('%H:%M:%S'), 'released', u, res[u], flush=True)
        if not running and not pending:
            print(time.strftime('%H:%M:%S'), 'all released; fetcher gone', flush=True)
            return
        time.sleep(every)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
