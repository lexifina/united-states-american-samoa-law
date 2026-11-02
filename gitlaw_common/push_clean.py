"""Push a cleaned, fully checked law build (private; never published).

    python -X utf8 scripts/gitlaw_common/push_clean.py <build folder> <slug> [--main] [--branch future]

1. audit_push must be clean for every ref pushed.
2. Private snapshot: world-law-ops refs/heads/wip/<slug>[-<branch>] (plain push; a rejection is reported, never forced).
3. With --main (Alan's blanket yes, 2026-10-29: a fully checked build may replace a placeholder, scaffold or thin
   main): the public lexifina/<slug> main (and --branch refs) as a plain fast-forward push only (Alan, 2026-11-02:
   no force-pushes anywhere); a build that is not a fast-forward of the remote is held and logged in HELD_LOG,
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


def fast_push_new_tags(build: Path, pub: str, slug: str, names: list[str], tags: dict[str, str],
                       size: int = 1000, parallel: int = 4) -> None:
    import shutil
    import tempfile
    from concurrent.futures import ThreadPoolExecutor
    objects = (build / '.git' / 'objects') if (build / '.git').is_dir() else (build / 'objects')

    def one(part: list[str]) -> None:
        tmp = Path(tempfile.mkdtemp(prefix='tagpush-'))
        try:
            run('git', 'init', '-q', '--bare', str(tmp))
            # bytes, not text: a text-mode write on Windows ends the line with \r, and git can't read that path
            (tmp / 'objects' / 'info' / 'alternates').write_bytes((str(objects.resolve()).replace('\\', '/') + '\n').encode())
            stdin = ''.join(f'create {t} {tags[t]}\n' for t in part).encode()
            subprocess.run(['git', 'update-ref', '--stdin'], cwd=tmp, input=stdin, capture_output=True, check=True)
            for attempt in range(3):
                r = run('git', 'push', '-q', pub, 'refs/tags/*:refs/tags/*', cwd=tmp)
                if not r.returncode:
                    return
                time.sleep(15 * (attempt + 1))
            print(f'{slug}: fast tag batch of {len(part)} from {part[0]} failed: {r.stderr.strip()[-200:]}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    parts = [names[i:i + size] for i in range(0, len(names), size)]
    with ThreadPoolExecutor(parallel) as ex:
        list(ex.map(one, parts))


HELD_LOG = Path(__file__).parents[1] / 'world-law' / 'logs' / 'HELD-REWRITES.txt'


def held(slug: str, what: str) -> None:
    HELD_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HELD_LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())} HELD-REWRITE {slug}: {what}\n")
    print(f'{slug}: HELD-REWRITE {what}')


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
    # 3. public main (+ branches): a plain push, so git itself refuses anything that is not a fast-forward. Published
    # history is never rewritten (Alan, 2026-11-02); a build that would need it is held for his yes on that repo.
    for b in branches:
        ref = f'refs/heads/{b}'
        old = remote.get(ref)
        r = run('git', 'push', pub, f'{local[b]}:{ref}', cwd=build)
        got = remote_refs(pub, ref).get(ref)
        if got != local[b] and ('non-fast-forward' in r.stderr or 'fetch first' in r.stderr or 'rejected' in r.stderr):
            held(slug, f'{b} {(old or "")[:9]} -> {local[b][:9]} is not a fast-forward')
            sys.exit(3)
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

    # New tags (absent on the remote) go up fast: each batch of 1,000 from a throwaway bare repo that borrows the
    # build's objects and holds only that batch, one glob refspec, 4 batches at once (bench/TAGS-AND-REBUILDS-2026-10-29:
    # ~13x faster). A plain non-forced push can only create, never overwrite. Tags that already exist with another
    # target (moved) keep the per-tag-lease path above.
    # Old remote-only tags that block a new tag by name (a ref can't be a file and a folder): Alan's standing yes
    # (2026-10-30, via global-law-main-composer) lets exactly those be deleted, each leased on its current value, and
    # logged in the corpus's private notes. No other remote tag is ever deleted.
    clash = sorted(t for t in remote if t.startswith('refs/tags/') and t not in tags
                   and any(n.startswith(t + '/') for n in tags))
    if clash:  # published tags are never deleted now (Alan, 2026-11-02): hold the build's clashing names instead
        held(slug, f'{len(clash)} published tags would need deleting: ' + ', '.join(t[10:] for t in clash[:10]))
        clash = []
    if clash:
        leases = [f'--force-with-lease={t}:{remote[t]}' for t in clash]
        r = run('git', 'push', *leases, pub, *[f':{t}' for t in clash], cwd=build)
        gone = [t for t in clash if t not in remote_refs(pub, t)]
        notes = Path(__file__).parents[1] / slug / 'NOTES.md'
        with open(notes, 'a', encoding='utf-8', newline='\n') as f:
            f.write(f"\n## Tag-clash deletions ({time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC, standing yes)\n"
                    + ''.join(f'- {t[10:]} {remote[t]}\n' for t in gone))
        print(f'{slug}: deleted {len(gone)} of {len(clash)} clashing old tags' + ('' if not r.returncode else
              f' ({r.stderr.strip()[-150:]})'))
        for t in gone:
            remote.pop(t, None)
    # a new tag whose name is a folder of a published tag (or the reverse) can't be created without deleting one: skip it
    folders = {r.rsplit('/', i)[0] for r in remote if r.startswith('refs/tags/') for i in range(1, r.count('/') - 1)}
    new = [t for t in todo if t not in remote and t not in folders
           and not any(t.rsplit('/', i)[0] in remote for i in range(1, t.count('/') - 1))]
    old = [t for t in todo if t in remote]
    if old:  # a published tag is never moved (Alan, 2026-11-02)
        held(slug, f'{len(old)} published tags would move: ' + ', '.join(t[10:] for t in old[:10]))
        old = []
    fast_push_new_tags(build, pub, slug, new, tags, size=100 if len(remote) > 15000 else 1000, parallel=1 if len(remote) > 15000 else 4)
    for i in range(0, len(old), BATCH):
        push_tags(old[i:i + BATCH])
    after = remote_refs(pub, 'refs/tags/*')
    bad = [t for t, sha in tags.items() if after.get(t) != sha]
    print(f'{slug}: tags {len(tags)} in build, {len(todo)} pushed ({moved} moved), {len(bad)} not matching after')


if __name__ == '__main__':
    main()
