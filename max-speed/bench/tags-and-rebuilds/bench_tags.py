"""Tag push speed for huge tag sets, against the throwaway private repo lexifina/tagpush-bench.

Source: a bare copy of hong-kong-law-build (main + 19,682 lightweight tags). main is pushed first (as push_clean.py
does), so every tag push is a ref-only update, as in a real publish. Each config pushes copies of real tags under its
own prefix (refs/tags/<cfg>/<original name>), so no config sees another's refs as already there.

    python -X utf8 bench_tags.py <config> ...   (results appended to tags.jsonl)
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'hk.git'
URL = 'https://github.com/lexifina/tagpush-bench.git'
OUT = HERE / 'tags.jsonl'


import base64
import os
ENV = None   # set by the _h flag: auth header via environment config, no credential helper, no 401 round trip


def header_env(schannel=False):
    tok = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()
    b = base64.b64encode(f'x-access-token:{tok}'.encode()).decode()
    kv = [('credential.helper', ''), ('http.https://github.com/.extraheader', f'Authorization: Basic {b}')]
    if schannel:
        kv.append(('http.sslBackend', 'schannel'))
    env = {**os.environ, 'GIT_CONFIG_COUNT': str(len(kv))}
    for i, (k, v) in enumerate(kv):
        env[f'GIT_CONFIG_KEY_{i}'], env[f'GIT_CONFIG_VALUE_{i}'] = k, v
    return env


def run(args, cwd=SRC, inp=None):
    t = time.perf_counter()
    env = ENV if args[:2] == ['git', 'push'] or args[:2] == ['git', 'ls-remote'] else None
    if inp is not None:   # bytes: a text-mode pipe on Windows turns LF into CRLF, which update-ref --stdin refuses
        r = subprocess.run(args, cwd=cwd, capture_output=True, input=inp.encode('utf-8'), env=env)
        if r.returncode:
            raise SystemExit(f'{args[:3]} failed: {r.stderr.decode(errors="replace")[-300:]}')
        return r, time.perf_counter() - t
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    return r, time.perf_counter() - t


TAGS = [l for l in run(['git', 'for-each-ref', '--format=%(refname)', 'refs/tags'])[0].stdout.splitlines()
        if l.count('/') >= 3 and not l.startswith('refs/tags/b')]   # originals only (cap-*/date)
SHA = dict(l.split(' ')[::-1] for l in run(['git', 'for-each-ref', '--format=%(objectname) %(refname)', 'refs/tags'])[0].stdout.splitlines())


def remote_count():
    r, dt = run(['git', 'ls-remote', URL])
    return len(r.stdout.splitlines()), round(dt, 2)


def classify(r):
    e = r.stderr
    return {'rc': r.returncode, 'gh013': 'GH013' in e, 'failed': '(failed)' in e,
            'timeout': 'timed out' in e.lower() or 'timeout' in e.lower(),
            'err': e.strip()[-300:] if r.returncode else ''}


def push_cli(prefix, part, i=0):
    specs = [f'{t}:refs/tags/{prefix}/{t[len("refs/tags/"):]}' for t in part]
    cmdlen = sum(len(s) + 1 for s in specs) + len(URL) + 20
    r, dt = run(['git', 'push', '-q', URL, *specs])
    return r, dt, cmdlen


def push_glob(prefix, part, i=0):
    """Stage the batch as refs/stage/<prefix>/* in the source repo (update-ref --stdin: no command-line limit),
    push it with one glob refspec, then drop the staging refs."""
    stage = f'refs/stage/{prefix}/{i}'
    run(['git', 'update-ref', '--stdin'], inp=''.join(f'create {stage}/{t[10:]} {SHA[t]}\n' for t in part))
    r, dt = run(['git', 'push', '-q', URL, f'{stage}/*:refs/tags/{prefix}/*'])
    run(['git', 'update-ref', '--stdin'], inp=''.join(f'delete {stage}/{t[10:]}\n' for t in part))
    return r, dt, len(URL) + 60


def push_bare(prefix, part, i=0):
    d = HERE / 'bare' / f'{prefix}-{i}'
    if d.exists():
        import shutil
        shutil.rmtree(d)
    subprocess.run(['git', 'init', '-q', '--bare', str(d)], check=True)
    (d / 'objects' / 'info' / 'alternates').write_text((SRC / 'objects').as_posix() + '\n', newline='\n')
    run(['git', 'update-ref', '--stdin'], cwd=d, inp=''.join(f'create {t} {SHA[t]}\n' for t in part))
    r, dt = run(['git', 'push', '-q', URL, f'refs/tags/*:refs/tags/{prefix}/*'], cwd=d)
    return r, dt, len(URL) + 60


def batches(prefix, tags, size, mode, parallel=1):
    parts = [tags[i:i + size] for i in range(0, len(tags), size)]
    fn = {'cli': push_cli, 'glob': push_glob, 'bare': push_bare}[mode]
    res = []
    lock = threading.Lock()
    queue = list(enumerate(parts))

    def worker(w):
        while True:
            with lock:
                if not queue:
                    return
                i, part = queue.pop(0)
            # parallel workers use distinct sub-prefixes for staging so they never share a staging ref
            r, dt, cl = fn(prefix, part, i)
            rec = {'batch': i, 'n': len(part), 'secs': round(dt, 2), 'cmdlen': cl, **classify(r)}
            if r.returncode:   # one retry, recorded
                r2, dt2, _ = fn(prefix, part, i)
                rec['retry'] = {'secs': round(dt2, 2), **classify(r2)}
            with lock:
                res.append(rec)
    t0 = time.perf_counter()
    ths = [threading.Thread(target=worker, args=(w,)) for w in range(parallel)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    return res, time.perf_counter() - t0


def record(cfg, **kw):
    kw['config'] = cfg
    kw['at'] = time.strftime('%H:%M:%S')
    with open(OUT, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(kw) + '\n')
    print(json.dumps({k: v for k, v in kw.items() if k != 'batches'}), flush=True)


def verify(prefix, tags):
    r, _ = run(['git', 'ls-remote', URL, f'refs/tags/{prefix}/*'])
    got = {ref: sha for sha, ref in (l.split('\t') for l in r.stdout.splitlines())}
    return sum(1 for t in tags if got.get(f'refs/tags/{prefix}/{t[10:]}') == SHA[t])


def main():
    for cfg in sys.argv[1:]:
        global ENV
        ENV = None
        before = remote_count()
        if cfg == 'main':
            r, dt = run(['git', 'push', '-q', URL, 'main:refs/heads/main'])
            record(cfg, secs=round(dt, 1), **classify(r), remote_refs_before=before)
            continue
        # cfg forms: cli80 / cli300 / glob300 / glob1000 / glob3000 [ _pN ] [ _nCOUNT ] [ _oOFFSET ]
        bits = cfg.split('_')
        ENV = header_env('hs' in bits[1:]) if ('h' in bits[1:] or 'hs' in bits[1:]) else None
        mode = next(m for m in ('cli', 'glob', 'bare') if bits[0].startswith(m))
        size = int(bits[0][len(mode):])
        par = next((int(b[1:]) for b in bits[1:] if b.startswith('p')), 1)
        n = next((int(b[1:]) for b in bits[1:] if b.startswith('n')), 3000)
        off = next((int(b[1:]) for b in bits[1:] if b.startswith('o')), 0)
        tags = TAGS[off:off + n]
        res, wall = batches(cfg, tags, size, mode, par)
        ok = verify(cfg, tags)
        record(cfg, mode=mode, batch=size, parallel=par, tags=len(tags), wall=round(wall, 1),
               secs_per_1000=round(wall / len(tags) * 1000, 1), on_remote=ok,
               pushes=len(res), failed_pushes=sum(1 for b in res if b['rc']),
               gh013=sum(1 for b in res if b['gh013'] or b.get('retry', {}).get('gh013')),
               failed_marker=sum(1 for b in res if b['failed'] or b.get('retry', {}).get('failed')),
               median_push=sorted(b['secs'] for b in res)[len(res) // 2], remote_refs_before=before,
               batches=res)


if __name__ == '__main__':
    main()
