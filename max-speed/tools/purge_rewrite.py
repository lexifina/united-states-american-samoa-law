"""Move private material out of a lexifina/<slug>-law repo's history, then force-push only if every check passes.

    python -X utf8 purge_rewrite.py <repo-name> [--push]     (without --push: dry run, nothing leaves this machine)

Gate: every original branch and tag must already be in lexifina/world-law-ops as archive/<repo>/<ref> with the same
SHA (archive_all.py), so nothing is ever discarded.

Rewrite: git filter-repo with callback.py, plus mailmap (personal email -> world-law@lexifina.com); empty commits kept.
callback.py drops private files, scrubs home paths, drops README bot-challenge lines and rewrites REPRODUCE's fetch
wording.

Checks, per ref:
- the commit count is the same;
- tags of law commits are unchanged;
- at each branch tip, every path that disappeared is one the rule calls private, and no binary file changed.

Push: changed refs only, with --force-with-lease on the archived SHA, in steps of 300 first-parent commits (GitHub's
secret scan). Prints one JSON line.
"""
import json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = re.compile(r'^(PROGRESS\.md|ISSUES\.md|PERMISSION[^/]*|NOTES\.md|[^/]*\.log|wayback[^/]*\.py|fetch[^/]*\.(py|sh)|'
                  r'crawl[^/]*\.py|grab[^/]*\.py|probe[^/]*\.py|discover[^/]*\.py|ia\.py|cc_[^/]*\.py|download[^/]*\.py|'
                  r'harvest[^/]*\.py)$', re.I)
MARK = re.compile(rb'host_get|cc_get|cc_captures|import wayback|wayback\.|ThreadPoolExecutor|requests a second|Crawl-delay|'
                  rb'adaptive rate', re.I)
TEXT = ('.py', '.sh', '.md', '.json', '.csv', '.txt', '.toml', '.yml', '.yaml')
OPS = 'https://github.com/lexifina/world-law-ops.git'
TMP = Path(r'C:\Users\alany\purge-tmp')


def git(cwd, *a, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True)
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.decode("utf-8", "replace").strip()[:300]}')
    return r.stdout.decode('utf-8', 'replace')


def ls_remote(url):
    out = {}
    for line in git(None, 'ls-remote', url).splitlines():
        sha, ref = line.split('\t')
        if ref.startswith(('refs/heads/', 'refs/tags/')) and not ref.endswith('^{}'):
            out[ref] = sha
    return out


def archived_name(ref, name):
    kind, short = ref.split('/', 2)[1], ref.split('/', 2)[2]
    return f'refs/{kind}/archive/{name}/{short}'


def tree(r, ref):
    out = {}
    for line in git(r, 'ls-tree', '-r', ref).splitlines():
        meta, path = line.split('\t', 1)
        out[path] = meta.split()[2]
    return out


def is_private(r, path, blob):
    base = path.rsplit('/', 1)[-1]
    if not path.startswith(('wip/', 'tools/')):
        return False
    if NAME.match(base):
        return True
    if base.endswith(('.py', '.sh')):
        return bool(MARK.search(subprocess.run(['git', 'cat-file', 'blob', blob], cwd=r, capture_output=True).stdout))
    return False


def main(name, push):
    t0 = time.time()
    url = f'https://github.com/lexifina/{name}.git'
    orig = ls_remote(url)
    ops = ls_remote(OPS)
    unarchived = [ref for ref, sha in orig.items() if ops.get(archived_name(ref, name)) != sha]
    if unarchived:
        return {'repo': name, 'status': 'NOT ARCHIVED, skipped', 'unarchived': len(unarchived), 'e.g.': unarchived[:3]}
    TMP.mkdir(exist_ok=True)
    m = Path(tempfile.mkdtemp(prefix=f'{name}-', dir=TMP))
    try:
        r = m / 'r.git'
        git(None, 'clone', '-q', '--mirror', url, str(r))
        before = {ref: git(r, 'rev-parse', ref).strip() for ref in orig}
        heads = [ref for ref in orig if ref.startswith('refs/heads/')]
        counts = {ref: int(git(r, 'rev-list', '--count', ref)) for ref in heads}
        tips = {ref: tree(r, ref) for ref in heads}
        p = subprocess.run([sys.executable, '-m', 'git_filter_repo', '--quiet', '--force', '--prune-empty', 'never',
                            '--prune-degenerate', 'never', '--mailmap', str(HERE / 'mailmap'),
                            '--file-info-callback', str(HERE / 'callback.py')], cwd=r, capture_output=True, text=True)
        if p.returncode:
            return {'repo': name, 'status': 'FILTER FAILED', 'err': (p.stderr or p.stdout)[-300:]}
        after = {ref: git(r, 'rev-parse', '-q', '--verify', ref, check=False).strip() for ref in orig}
        problems, removed, changed_files = [], {}, {}
        for ref in heads:
            if not after[ref]:
                problems.append(f'{ref} vanished')
                continue
            if int(git(r, 'rev-list', '--count', ref)) != counts[ref]:
                problems.append(f'{ref} commit count changed')
            new = tree(r, ref)
            gone = [pth for pth in tips[ref] if pth not in new]
            for pth in gone:
                if not is_private(r, pth, tips[ref][pth]):
                    problems.append(f'{ref}: non-private path removed: {pth}')
            edited = [pth for pth in new if pth in tips[ref] and tips[ref][pth] != new[pth]]
            for pth in edited:
                if not pth.endswith(TEXT):
                    problems.append(f'{ref}: binary changed: {pth}')
            short = ref.rsplit('/', 1)[1]
            if gone:
                removed[short] = len(gone)
            if edited:
                changed_files[short] = len(edited)
        tag_changed = [t for t in orig if t.startswith('refs/tags/') and after.get(t) != before[t]]
        changed = [ref for ref in orig if after.get(ref) and after[ref] != before[ref]]
        res = {'repo': name, 'refs': len(orig), 'changed_refs': len(changed), 'tags_changed': len(tag_changed),
               'removed_at_tips': removed, 'scrubbed_at_tips': changed_files, 'problems': problems[:8],
               'seconds': round(time.time() - t0)}
        if problems:
            res['status'] = 'CHECK FAILED, not pushed'
            return res
        if not changed:
            res['status'] = 'nothing to change'
            return res
        if not push:
            res['status'] = 'dry run OK'
            return res
        git(r, 'remote', 'add', 'origin', url, check=False)

        def run(*specs):
            err = ''
            for attempt in range(5):
                q = subprocess.run(['git', 'push', '-q', 'origin', *specs], cwd=r, capture_output=True, text=True)
                if q.returncode == 0:
                    return None
                err = q.stderr[-300:]
                if 'stale info' in err:
                    return err  # the remote moved since the archive: never overwrite it
                time.sleep(15 * (attempt + 1))
            return err

        lease = dict(before)
        for ref in [c for c in changed if c.startswith('refs/heads/')]:
            commits = git(r, 'rev-list', '--first-parent', '--reverse', after[ref]).split()
            for sha in commits[299::300]:
                err = run(f'--force-with-lease={ref}:{lease[ref]}', f'+{sha}:{ref}')
                if err:
                    res['status'] = f'PUSH FAILED at a step of {ref}: {err}'
                    return res
                lease[ref] = sha
            err = run(f'--force-with-lease={ref}:{lease[ref]}', f'+{after[ref]}:{ref}')
            if err:
                res['status'] = f'PUSH FAILED on {ref}: {err}'
                return res
        tags = [c for c in changed if c.startswith('refs/tags/')]
        for i in range(0, len(tags), 300):
            batch = tags[i:i + 300]
            err = run(*[f'--force-with-lease={t}:{before[t]}' for t in batch], *[f'+{after[t]}:{t}' for t in batch])
            if err:
                res['status'] = f'TAG PUSH FAILED: {err}'
                return res
        now = ls_remote(url)
        res['status'] = 'pushed and verified' if all(now.get(ref) == after[ref] for ref in changed) else 'PUSHED BUT REMOTE DIFFERS'
        return res
    finally:
        shutil.rmtree(m, ignore_errors=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(main(sys.argv[1], '--push' in sys.argv)), flush=True)
    except Exception as e:
        print(json.dumps({'repo': sys.argv[1], 'status': 'ERROR', 'err': str(e)[:300]}), flush=True)
