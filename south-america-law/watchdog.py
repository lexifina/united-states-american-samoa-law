"""Stall watchdog for this machine's country producers (hp-omen, 2026-11-01).

For each repo listed in ACTIVE.txt (repos with a running agent or driver), report STALLED when no PUBLISH file has
changed for more than LIMIT and no other file in the folder has changed either. Writes STALLED lines to the
autopush log and prints them; exits 1 when any repo is stalled so a waiting shell loop can wake the coordinator.
A STALLED line is a prompt to ask the agent, never a reason to stop it: agents also work in scratch folders, so the
watch includes ~/Documents/.gitlaw-scratch/<slug>* as well.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = Path(__file__).with_name('ACTIVE.txt')
LOG = Path(__file__).with_name('logs') / 'autopush.log'
SCRATCH = ROOT.parents[1] / '.gitlaw-scratch'
LIMIT = 2 * 3600
QUIET = {'BUILD_STATUS.json', 'verification.json'}


def newest(folder: Path, publish: bool) -> float:
    best = 0.0
    for p in folder.rglob('*'):
        if '.git' in p.parts or p.name in QUIET or p.name.startswith('.autopush'):
            continue
        if publish != p.name.endswith('PUBLISH'):
            continue
        try:  # agents delete scratch files while the walk runs
            if p.is_file():
                best = max(best, p.stat().st_mtime)
        except OSError:
            continue
    return best


def main() -> int:
    now = time.time()
    slugs = [s.strip() for s in ACTIVE.read_text(encoding='utf-8').split() if s.strip() and not s.startswith('#')]
    stalled = []
    for slug in slugs:
        folder = ROOT / f'{slug}-law'
        if not folder.is_dir():
            continue
        pub, other = newest(folder, True), newest(folder, False)
        for scratch in SCRATCH.glob(f'{slug}*'):
            if scratch.is_dir():
                other = max(other, newest(scratch, False))
        if now - pub > LIMIT and now - other > LIMIT:
            stalled.append(f'STALLED {slug}-law: last PUBLISH {(now - pub) / 3600:.1f} h ago, '
                           f'last file change {(now - other) / 3600:.1f} h ago')
    if stalled:
        stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))
        with LOG.open('a', encoding='utf-8') as f:
            f.writelines(f'{stamp} {line}\n' for line in stalled)
        print('\n'.join(stalled))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
