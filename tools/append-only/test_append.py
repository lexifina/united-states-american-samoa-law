"""Test append.py: a partial build plus an append must read back exactly like the full corpus, with no SHA changed.

Usage: python -X utf8 test_append.py <work dir>
Uses the laptop's 7-part Phase 1+2 corpus (scripts/romania-law/corpus.d) as test data.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE / 'tools'
SRC = Path(r'C:\Users\alany\Documents\lexifina\scripts\romania-law')
work = Path(sys.argv[1])
if work.exists():
    shutil.rmtree(work)
part_dir, full_dir, repo, ref = work / 'partial', work / 'full', work / 'repo', work / 'ref'
for d in (part_dir, full_dir):
    (d / 'corpus.d').mkdir(parents=True)
    shutil.copytree(SRC / 'repo', d / 'repo')
parts = sorted((SRC / 'corpus.d').glob('*.json'))
for p in parts:
    shutil.copy(p, full_dir / 'corpus.d' / p.name)
    if p.name.startswith(('10-', '20-', '30-', '40-', '50-')):
        shutil.copy(p, part_dir / 'corpus.d' / p.name)
    elif p.name.startswith('60-'):
        c = json.loads(p.read_text(encoding='utf-8'))
        for a in c['acts']:
            a['versions'] = a['versions'][:30]
        (part_dir / 'corpus.d' / p.name).write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')
D = '2026-10-29'


def run(*args, cwd=None):
    out = subprocess.run([sys.executable, '-X', 'utf8', *map(str, args)], capture_output=True, text=True,
                         encoding='utf-8', cwd=cwd)
    print(out.stdout[-1500:], out.stderr[-1500:])
    if out.returncode:
        raise SystemExit(f'failed: {args}')
    return out.stdout


def g(*args, cwd=repo):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8').stdout


run(TOOLS / 'build.py', part_dir, '--repo', repo, '--docs-date', D)
before = g('rev-list', 'main').split()
tags_before = {t: g('rev-parse', t).strip() for t in g('tag', '--list').split()}
print('partial build:', len(before), 'commits,', len(tags_before), 'tags')
run(TOOLS / 'append.py', full_dir, '--repo', repo, '--docs-date', D)
after = g('rev-list', 'main').split()
print('after append:', len(after), 'commits')
assert set(before) <= set(after), 'a published commit vanished'
assert after[-len(before):] == before, 'published history changed'
moved = [t for t, s in tags_before.items() if g('rev-parse', t).strip() != s]
assert not moved, f'tags moved: {moved[:5]}'
print(run(TOOLS / 'check_repo.py', repo, '--corpus', full_dir / 'corpus.json'))
# Idempotent: a second append with the same corpus adds nothing.
run(TOOLS / 'append.py', full_dir, '--repo', repo, '--docs-date', D)
assert g('rev-list', 'main').split() == after, 'second append changed main'
# Deterministic: the same partial build + append in a fresh folder gives the same head.
run(TOOLS / 'build.py', part_dir, '--repo', ref, '--docs-date', D)
run(TOOLS / 'append.py', full_dir, '--repo', ref, '--docs-date', D)
assert g('rev-parse', 'main', cwd=ref) == g('rev-parse', 'main'), 'append is not deterministic'
print('ALL OK; head', g('rev-parse', 'main').strip())
