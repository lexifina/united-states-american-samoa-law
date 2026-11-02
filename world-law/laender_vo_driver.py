"""Publish Brandenburg and Bremen Verordnungen parts as their fetches complete (private, gitlaw-scraper-dell).

    python -X utf8 scripts/world-law/laender_vo_driver.py            # loop: a pass every 10 minutes
    python -X utf8 scripts/world-law/laender_vo_driver.py --once     # one pass

For each Land, a pass does what was done by hand for the Gesetze, and writes nothing to corpus.d unless every step
passes:
1. waits while cpu5 > 92 or RAM > 85 (last line of %LOCALAPPDATA%/gitlaw-cpu.log); runs everything at BelowNormal;
2. parses the not yet published 30-verordnungen-NN parts into a fresh staging copy (<land>/.tmp/vo-stage-<time>, a new
   directory every time, so every verify build is new; old ones are removed with read-only bits cleared) - parse.py
   writes only parts whose every act is fully fetched;
3. publishes only a batch of 2-4 new parts (fewer only for the last parts once the fetch has finished);
4. letters-and-digits check of every new part; a version whose parsed text differs from its page is added to
   <land>/letters-differ.json (left out, with that reason, in the part's decisions) and the batch is parsed again;
5. local build of all parts with check.py and audit_push (verify_parts_local.py) must be clean;
6. every published part must be byte-identical in the staging copy;
7. copies the new parts into corpus.d, then writes each <part>.PUBLISH (autopush_dell then publishes main: a verified
   rebuild with lease, old tip archived).
It stops a Land (records why in <land>/VO-DRIVER.json) on any failure, on a fetch that stopped with an error, or when
autopush reports a refused push. When every part of a Land is published and its fetch has finished, it deletes that
Land's claim (only if gitlaw-scraper-dell holds it). Log: <land>/vo-driver.log.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

SCRIPTS = Path(__file__).resolve().parents[1]
CPU_LOG = Path(os.environ['LOCALAPPDATA']) / 'gitlaw-cpu.log'
LANDS = {
    'germany-brandenburg-law': {'list': '.cache/verordnungen.txt', 'index': 'BRAVORS subject index'},
    'germany-bremen-law': {'list': None, 'index': 'Transparenzportal Bremen list (searched for "Verordnung")'},
}
BATCH_MIN, BATCH_MAX = 2, 4  # Alan: frequent main changes (coordinator, 2026-11-01)
PY = [sys.executable, '-X', 'utf8']
LOW = {'creationflags': 0x00004000} if os.name == 'nt' else {}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log(folder: Path, msg: str) -> None:
    with open(folder / 'vo-driver.log', 'a', encoding='utf-8') as f:
        f.write(f'{now()} {msg}\n')


def gate() -> None:
    while True:
        line = CPU_LOG.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-1]
        c = re.search(r'cpu5=(\d+)', line)
        r = re.search(r'ram=(\d+)', line)
        if c and r and int(c.group(1)) <= 92 and int(r.group(1)) <= 85:
            return
        time.sleep(30)


def run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 7200) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env={**os.environ, **(env or {})}, timeout=timeout, **LOW)


def total_parts(folder: Path) -> int | None:
    if folder.name == 'germany-brandenburg-law':
        f = folder / '.cache' / 'verordnungen.txt'
        return math.ceil(len(f.read_text(encoding='utf-8').split()) / 50) if f.exists() else None
    p = run(PY + ['-c', 'import fetch; print(len(fetch.verordnung_entries()))'], folder)
    return math.ceil(int(p.stdout.strip()) / 50) if p.returncode == 0 and p.stdout.strip().isdigit() else None


def fetch_state(folder: Path) -> str:
    """running / finished / stopped: <why>, from the newest fetch.py verordnungen PID in my-pids.txt and its logs."""
    pids = [l for l in (folder / 'my-pids.txt').read_text(encoding='utf-8').splitlines() if 'fetch.py verordnungen' in l]
    pid = int(pids[-1].split()[0]) if pids else None
    if pid and psutil.pid_exists(pid):
        try:
            if 'fetch.py' in ' '.join(psutil.Process(pid).cmdline()):
                return 'running'
        except psutil.Error:
            pass
    err = (folder / 'fetch-verordnungen.err').read_text(encoding='utf-8', errors='replace') \
        if (folder / 'fetch-verordnungen.err').exists() else ''
    if 'stop:' in err or 'Traceback' in err:
        return 'stopped: ' + err.strip().splitlines()[-1][:300]
    return 'finished'


def published(folder: Path) -> list[str]:
    return sorted(p.stem for p in (folder / 'corpus.d').glob('30-verordnungen-*.PUBLISH'))


def rmtree(path: Path) -> None:
    """shutil.rmtree that clears the read-only bit git sets on pack files (Windows refuses to delete those)."""
    import stat

    def again(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=again)
    else:
        shutil.rmtree(path, onerror=again)


def stage(folder: Path) -> Path:
    for old in (folder / '.tmp').glob('vo-stage*'):
        try:
            rmtree(old)
        except OSError as e:  # a lock held elsewhere: leave it, the new stage has its own name
            log(folder, f'could not remove {old.name}: {e}')
    st = folder / '.tmp' / f'vo-stage-{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")}'
    (st / 'corpus.d').mkdir(parents=True)
    for p in (folder / 'corpus.d').iterdir():
        if p.suffix in ('.json', '.PUBLISH'):
            shutil.copy2(p, st / 'corpus.d' / p.name)
    shutil.copytree(folder / 'repo', st / 'repo')
    shutil.copy2(folder / 'PUBLISH', st / 'PUBLISH')
    return st


def parse(folder: Path, st: Path, names: list[str]) -> subprocess.CompletedProcess:
    return run(PY + ['parse.py', *names], folder, env={'PARSE_OUT': str(st / 'corpus.d')})


def letters(folder: Path, parts: list[Path]) -> tuple[int, list[str]]:
    p = run(PY + ['check_letters.py', *map(str, parts)], folder)
    urls = re.findall(r'^MISMATCH .*?; url=(\S+)$', p.stdout, re.M)
    m = re.search(r'(\d+) mismatches', p.stdout)
    return (int(m.group(1)) if m else -1), urls


def one_land(folder: Path, status: dict) -> None:
    if status.get('done') or status.get('stopped'):
        return
    fs = fetch_state(folder)
    status['fetch'] = fs
    if fs.startswith('stopped'):
        status['stopped'] = f'fetch {fs}'
        return
    total = total_parts(folder)
    pub = published(folder)
    status.update({'total_parts': total, 'published': len(pub)})
    if total is not None and len(pub) >= total and fs == 'finished':
        status['done'] = now()
        claim = SCRIPTS / 'world-law' / 'claims' / f'{folder.name}.txt'
        if claim.exists() and claim.read_text(encoding='utf-8').startswith('gitlaw-scraper-dell'):
            claim.unlink()
            log(folder, 'all Verordnungen parts published and fetch finished: claim deleted')
        return
    if total is None:
        return
    todo = [f'30-verordnungen-{n:02d}' for n in range(1, total + 1) if f'30-verordnungen-{n:02d}' not in pub]
    gate()
    st = stage(folder)
    p = parse(folder, st, todo[:BATCH_MAX])  # only the next batch: parse.py stops at the first part not ready
    if p.returncode:
        status['stopped'] = 'parse failed: ' + (p.stderr or p.stdout)[-400:]
        return
    new = [n for n in todo if (st / 'corpus.d' / f'{n}.json').exists()]
    last = fs == 'finished' and len(pub) + len(new) >= total
    if len(new) < BATCH_MIN and not (new and last):
        status['waiting'] = f'{len(new)} new parts ready; batch needs {BATCH_MIN}'
        return
    batch = new[:BATCH_MAX]
    for attempt in range(4):
        if attempt or len(new) > len(batch):
            st = stage(folder)
            p = parse(folder, st, batch)
            if p.returncode:
                status['stopped'] = 'parse failed: ' + (p.stderr or p.stdout)[-400:]
                return
        gate()
        bad, urls = letters(folder, [st / 'corpus.d' / f'{n}.json' for n in batch])
        if bad == 0:
            break
        if bad < 0 or not urls or attempt == 3:
            status['stopped'] = f'letters check: {bad} mismatches after {attempt + 1} passes'
            return
        ld_path = folder / 'letters-differ.json'
        ld = json.loads(ld_path.read_text(encoding='utf-8')) if ld_path.exists() else {}
        for u in urls:
            key = u.split('brandenburg.de', 1)[1] if 'bravors.brandenburg.de' in u else u
            ld[key] = 'the parsed text differs from the page (letters check)'
        ld_path.write_text(json.dumps(ld, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        log(folder, f'letters check: {len(urls)} versions added to letters-differ.json')
    gate()
    v = run(PY + [str(SCRIPTS / 'world-law' / 'verify_parts_local.py'), str(st)], folder)
    try:
        ver = json.loads(v.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        status['stopped'] = 'verify failed: ' + (v.stderr or v.stdout)[-400:]
        return
    if v.returncode or not ver.get('ok'):
        status['stopped'] = 'verify not clean: ' + json.dumps(ver)[:600]
        return
    for p_ in (folder / 'corpus.d').glob('*.json'):
        if (st / 'corpus.d' / p_.name).read_bytes() != p_.read_bytes():
            status['stopped'] = f'published part {p_.name} would change'
            return
    chk = ver['check']
    for n in batch:
        part = json.loads((st / 'corpus.d' / f'{n}.json').read_text(encoding='utf-8'))
        acts = len(part['acts'])
        nv = sum(len(a['versions']) for a in part['acts'])
        left = sum(1 for d in part['decisions'] if d.startswith('Left out:'))
        k = int(n.rsplit('-', 1)[1])
        tmp = folder / 'corpus.d' / f'{n}.json.tmp'
        shutil.copy2(st / 'corpus.d' / f'{n}.json', tmp)
        tmp.replace(folder / 'corpus.d' / f'{n}.json')
        status.setdefault('parts', {})[n] = {'acts': acts, 'versions': nv, 'left_out': left}
    day = dt.date.today().isoformat()
    for n in batch:
        s = status['parts'][n]
        k = int(n.rsplit('-', 1)[1])
        (folder / 'corpus.d' / f'{n}.PUBLISH').write_text(
            f'Verified {day} (gitlaw-scraper-dell, Verordnungen part driver): Verordnungen {50 * k - 49}-{50 * k} of the '
            f'{LANDS[folder.name]["index"]}; {s["acts"]} acts, {s["versions"]} versions; {s["left_out"]} decisions '
            f'"Left out" (listed in the part); independent letters-and-digits check of every version against its raw '
            f'page: 0 differences; local build of all parts into an empty repo: check.py 0 mismatches / 0 trailer '
            f'errors / 0 future-dated ({chk["acts"]} acts, {chk["versions"]} versions); audit_push clean.\n',
            encoding='utf-8', newline='\n')
    status['last_batch'] = {'at': now(), 'parts': batch, 'check': chk}
    status.pop('waiting', None)
    log(folder, f'published {batch[0]}..{batch[-1]} ({len(batch)} parts): {chk["acts"]} acts, {chk["versions"]} versions in all')


def autopush_refused(folder: Path) -> str | None:
    b = folder / 'BUILD_STATUS.json'
    if not b.exists():
        return None
    s = json.loads(b.read_text(encoding='utf-8'))
    m = s.get('main', '')
    return m if re.search(r'NOT pushed|refus|rejected|error', m, re.I) else None


def main() -> None:
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    once = '--once' in sys.argv
    started = now()
    while True:
        for name in LANDS:
            folder = SCRIPTS / name
            sp = folder / 'VO-DRIVER.json'
            status = json.loads(sp.read_text(encoding='utf-8')) if sp.exists() else {}
            was_stopped = bool(status.get('stopped'))
            r = autopush_refused(folder)
            if r:
                # autopush refused the last build: publish nothing more for this Land; re-checked every pass, so it
                # resumes by itself once autopush pushes again (e.g. after a restart that loads a fixed rule).
                status['autopush_refused'] = r[:400]
            else:
                status.pop('autopush_refused', None)
            try:
                if not r:
                    one_land(folder, status)
            except Exception as e:  # recorded, never retried blindly
                status['stopped'] = f'{type(e).__name__}: {e}'[:400]
            status['at'] = now()
            sp.write_text(json.dumps(status, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            if status.get('stopped') and not was_stopped:
                log(folder, 'STOPPED: ' + status['stopped'])
        states = [json.loads((SCRIPTS / n / 'VO-DRIVER.json').read_text(encoding='utf-8')) for n in LANDS]
        if once or all(s.get('done') or s.get('stopped') for s in states):
            return
        # Right away while a Land just published (more parts may be ready), else every 10 minutes.
        if not any(s.get('last_batch', {}).get('at', '') > started for s in states):
            time.sleep(600)
        started = now()


if __name__ == '__main__':
    main()
