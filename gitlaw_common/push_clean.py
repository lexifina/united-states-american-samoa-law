"""Push a cleaned, fully checked law build (private; never published).

    python -X utf8 scripts/gitlaw_common/push_clean.py <build folder> <slug> [--main] [--branch future]

1. audit_push must be clean for every ref pushed.
2. Private snapshot: world-law-ops refs/heads/wip/<slug>[-<branch>] (plain push; a rejection is reported, never forced).
3. With --main (Alan's blanket yes, 2026-10-29: a fully checked build may replace a placeholder, scaffold or thin
   main): the public lexifina/<slug> main (and --branch refs) with --force-with-lease on the remote's current sha,
   then the build's own tags in batches of 300; a tag already on the remote is moved with a per-tag lease; remote-only
   tags are left alone. Every ref is verified with ls-remote afterwards.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import private  # noqa: E402

OPS = 'https://github.com/lexifina/world-law-ops.git'
BATCH = 80  # Windows caps a command line at 32,767 chars; ~80 tag refspecs plus leases fit


def run(*a: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')


LEDGER = Path(__file__).parent / 'pushed-wip.json'   # private: every world-law-ops wip tip this machine pushed


def load_ledger() -> dict[str, str]:
    import json
    try:
        return json.loads(LEDGER.read_text('utf-8'))
    except (OSError, ValueError):
        return {}


def save_ledger(ref: str, sha: str) -> None:
    import json
    d = load_ledger()
    d[ref] = sha
    LEDGER.write_text(json.dumps(d, indent=1, sort_keys=True) + '\n', 'utf-8')


def remote_refs(url: str, *patterns: str) -> dict[str, str]:
    out = run('git', 'ls-remote', url, *patterns).stdout
    return {ref: sha for sha, ref in (l.split('\t') for l in out.splitlines() if '\t' in l)}


def main() -> None:
    build, slug = Path(sys.argv[1]), sys.argv[2]
    to_main = '--main' in sys.argv
    branches = ['main'] + [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--branch']
    pub = f'https://github.com/lexifina/{slug}.git'
    local = {b: run('git', 'rev-parse', b, cwd=build).stdout.strip() for b in branches}
    remote = remote_refs(pub, 'refs/heads/*', 'refs/tags/*')
    for b in branches:
        old = remote.get(f'refs/heads/{b}')
        findings = private.audit_push(build, local[b], old)
        if findings:
            sys.exit(f'{slug} {b}: audit refused:\n  ' + '\n  '.join(findings[:20]))
    # 2. private snapshot: one branch per corpus. A branch whose tip is in our ledger (we pushed it) is replaced with
    # a lease on that exact tip (approved by Alan via global-law-main-composer, 2026-10-29); anyone else's tip is
    # never overwritten and gets a sha-named sibling instead.
    ledger = load_ledger()
    for b in branches:
        dst = f'refs/heads/wip/{slug}' + ('' if b == 'main' else f'-{b}')
        got, err = None, ''
        for attempt in range(5):  # parallel pushes to the one private repo race on its refs: retry with back-off
            tip = remote_refs(OPS, dst).get(dst)
            lease = [f'--force-with-lease={dst}:{tip}'] if tip and ledger.get(dst) == tip else []
            r = run('git', 'push', *lease, OPS, f'{local[b]}:{dst}', cwd=build)
            got, err = remote_refs(OPS, dst).get(dst), r.stderr.strip()[-200:]
            if got == local[b]:
                save_ledger(dst, got)
                break
            if got and ('non-fast-forward' in r.stderr or 'fetch first' in r.stderr):
                # the name holds another snapshot (never forced over): use one sibling named by this build's sha
                base = f'refs/heads/wip/{slug}' + ('' if b == 'main' else f'-{b}')
                dst = f'{base}-{local[b][:9]}'
                continue
            time.sleep(5 * (attempt + 1))
        print(f'{slug}: private {dst} = {(got or "")[:9]}', 'ok' if got == local[b] else f'REJECTED {err}')
    if not to_main:
        return
    # 3. public main (+ branches), leased
    for b in branches:
        ref = f'refs/heads/{b}'
        old = remote.get(ref)
        lease = f'--force-with-lease={ref}:{old}' if old else f'--force-with-lease={ref}:'
        r = run('git', 'push', lease, pub, f'{local[b]}:{ref}', cwd=build)
        got = remote_refs(pub, ref).get(ref)
        print(f'{slug}: public {b} {(old or "none")[:9]} -> {(got or "")[:9]}',
              'ok' if got == local[b] else f'FAILED {r.stderr.strip()[-300:]}')
        if got != local[b]:
            sys.exit(1)
    # tags in batches
    tags = {l.split(' ')[1]: l.split(' ')[0] for l in
            run('git', 'for-each-ref', '--format=%(objectname) %(refname)', 'refs/tags', cwd=build).stdout.splitlines()}
    todo = [t for t, sha in tags.items() if remote.get(t) != sha]
    moved = sum(1 for t in todo if t in remote)
    def push_tags(part: list[str], depth: int = 0) -> None:
        # GitHub sometimes rejects a whole batch with a bare "(failed)": retry with back-off, then split in halves.
        for attempt in range(3):
            leases = [f'--force-with-lease={t}:{remote[t]}' for t in part if t in remote]
            r = run('git', 'push', *leases, pub, *[f'{t}:{t}' for t in part], cwd=build)
            if not r.returncode:
                return
            time.sleep(10 * (attempt + 1))
        if len(part) > 1 and depth < 6:
            half = len(part) // 2
            push_tags(part[:half], depth + 1)
            push_tags(part[half:], depth + 1)
        else:
            print(f'{slug}: tag {part[0]} failed: {r.stderr.strip()[-200:]}')

    for i in range(0, len(todo), BATCH):
        push_tags(todo[i:i + BATCH])
    after = remote_refs(pub, 'refs/tags/*')
    bad = [t for t, sha in tags.items() if after.get(t) != sha]
    print(f'{slug}: tags {len(tags)} in build, {len(todo)} pushed ({moved} moved), {len(bad)} not matching after')


if __name__ == '__main__':
    main()
