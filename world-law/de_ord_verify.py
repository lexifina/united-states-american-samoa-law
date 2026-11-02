"""Verify new Verordnungen parts of a German Land folder (gitlaw-scraper-dell, ordinances wave 2026-10-30).

    python -X utf8 scripts/world-law/de_ord_verify.py germany-saxony-law 40-verordnungen-01 40-verordnungen-02 ...

1. The folder's own independent letters-and-digits check (check_letters.py, regex reader, no HTML/XML parser) on
   each new part: must report 0 mismatches.
2. Act slugs unique across every part.
3. A scratch build of every published part plus the new parts (scripts/gitlaw_common/build.py into an empty repo)
   and check.py on it: 0 mismatches, trailer errors, merges, backwards, future-dated, missing in-force.
Prints one JSON line; writes nothing in the folder. Private.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent.parent
LOW = 0x4000 if os.name == 'nt' else 0


def rm(d: Path):
    def onerr(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if d.exists():
        shutil.rmtree(d, onexc=onerr)


def main(slug: str, parts: list[str], day: str = '2026-10-30') -> dict:
    f = ROOT / slug
    out = {'slug': slug, 'parts': parts}
    lc = subprocess.run([sys.executable, '-X', 'utf8', 'check_letters.py'] + [str(f / 'corpus.d' / f'{p}.json') for p in parts],
                        cwd=f, capture_output=True, text=True, encoding='utf-8', creationflags=LOW)
    out['letters'] = (lc.stdout.strip().splitlines() or [''])[-1]
    out['letters_ok'] = lc.returncode == 0
    if not out['letters_ok']:
        out['letters_detail'] = lc.stdout[-1500:] + lc.stderr[-500:]
    names = sorted({p.stem for p in (f / 'corpus.d').glob('*.json') if p.with_suffix('.PUBLISH').exists()} | set(parts))
    slugs, dup = {}, []
    nacts = nvers = 0
    for n in names:
        for a in json.loads((f / 'corpus.d' / f'{n}.json').read_text(encoding='utf-8'))['acts']:
            if a['slug'] in slugs:
                dup.append(f'{a["slug"]} in {slugs[a["slug"]]} and {n}')
            slugs[a['slug']] = n
            if n in parts:
                nacts += 1
                nvers += len(a['versions'])
    out['new_acts'], out['new_versions'] = nacts, nvers
    out['dup_slugs'] = dup
    tmp, build = DOCS / f'{slug}-ordverify', DOCS / f'{slug}-ordverifybuild'
    for d in (tmp, build):
        rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    for n in names:
        shutil.copy2(f / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    if (f / 'repo').exists():
        shutil.copytree(f / 'repo', tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo',
                        str(build), '--docs-date', day], capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=env, creationflags=LOW)
    res = None
    if b.returncode:
        out['build_error'] = (b.stderr or b.stdout)[-800:]
    else:
        c = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build),
                            '--corpus', str(tmp / 'corpus.json')], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', creationflags=LOW)
        try:
            res = json.loads(c.stdout[c.stdout.index('{'):])
        except Exception:
            out['check_error'] = (c.stderr or c.stdout)[-800:]
    if res is not None:
        out['check'] = {k: v for k, v in res.items() if k != 'details'}
        if res.get('details'):
            out['check_details'] = res['details'][:5]
    out['check_ok'] = res is not None and not any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges',
                                                                       'backwards', 'future_dated', 'missing_in_force'))
    out['ok'] = out['letters_ok'] and out['check_ok'] and not dup
    for d in (tmp, build):
        rm(d)
    return out


if __name__ == '__main__':
    print(json.dumps(main(sys.argv[1], sys.argv[2:]), ensure_ascii=False))
