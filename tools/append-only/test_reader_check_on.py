"""After test_corrections.py <work>: gitlaw_common check.py and on.py read the corrected repos by the reading rule.

    python -X utf8 test_reader_check_on.py <work> <gitlaw_common>
- each case (newest, middle, backfill, newer): check.py with the fixed corpus finds 0 mismatches and counts the
  corrections; on.py prints, for each probe day, exactly the fixed corpus's text of that day;
- shared folder: on.py reads the one-file act title-11/362,1.md as Old / Fixed / Fixed / New on 2005/2012/2016/2021
  (the open range holds across the sibling's commit and ends at the act's own), and the sibling as itself.
"""
import json
import subprocess
import sys
from pathlib import Path

work, common = Path(sys.argv[1]), Path(sys.argv[2])
fail = []


def run(*args, cwd=None):
    return subprocess.run([sys.executable, '-X', 'utf8', *map(str, args)], capture_output=True, text=True,
                          encoding='utf-8', cwd=cwd)


for name in ('newest', 'middle', 'backfill', 'newer'):
    repo, fixed = work / f'{name}-repo', work / f'{name}-fixed' / 'corpus.json'
    r = run(common / 'check.py', repo, '--corpus', fixed)
    res = json.loads(r.stdout)
    ok = r.returncode == 0 and res['mismatches'] == 0 and res.get('corrections', 0) >= 1
    print(f'{"PASS" if ok else "FAIL"} {name}: check.py rc {r.returncode}, mismatches {res["mismatches"]}, '
          f'corrections {res.get("corrections")}', res['details'][:3])
    fail += [] if ok else [f'{name} check']
    c = json.loads(fixed.read_text(encoding='utf-8'))
    for day in ('2005-06-01', '2015-06-01', '2022-06-01', '2025-06-01'):
        for act in c['acts']:
            v = [w for w in act['versions'] if w['from'] <= day][-1] if act['versions'][0]['from'] <= day else None
            want = ''.join(v['units'][k]['text'] + '\n' for k in sorted(v['units'])) if v else None
            o = run(common / 'on.py', day, act['slug'], cwd=repo)
            got = o.stdout if o.returncode == 0 else None
            if got != want:
                fail.append(f'{name} on.py {day} {act["slug"]}')
                print(f'FAIL {name}: on.py {day} {act["slug"]}: {got!r} != {want!r} {o.stderr[-200:]}')
    print(f'{name}: on.py reads checked')

repo = work / 'shared-repo'
for day, want in (('2005-06-01', 'Old.\n'), ('2012-06-01', 'Fixed.\n'), ('2016-06-01', 'Fixed.\n'), ('2021-06-01', 'New.\n')):
    o = run(common / 'on.py', day, 'title-11/362,1.md', cwd=repo)
    ok = o.returncode == 0 and o.stdout == want
    print(f'{"PASS" if ok else "FAIL"} shared folder on {day}: {o.stdout!r} {o.stderr[-200:]}')
    fail += [] if ok else [f'shared {day}']
o = run(common / 'on.py', '2016-06-01', 'title-11/363.md', cwd=repo)
print(f'{"PASS" if o.stdout == "Sibling, amended.\n" else "FAIL"} shared folder sibling: {o.stdout!r}')
fail += [] if o.stdout == 'Sibling, amended.\n' else ['sibling']
# The all-acts listing marks the shared folder while the one-file act's correction holds (2010-01-01 until the day
# before the act's own 2020 commit), and only then.
fix = subprocess.run(['git', 'log', '--format=%H', '--grep=^Kind: correction'], cwd=repo, capture_output=True,
                     text=True).stdout.split()[0][:10]
for day, marked in (('2005-06-01', False), ('2012-06-01', True), ('2016-06-01', True), ('2021-06-01', False)):
    o = run(common / 'on.py', day, cwd=repo)
    line = next((l for l in o.stdout.splitlines() if l.startswith('title-11\t')), '')
    ok = o.returncode == 0 and line and (f'corrected by {fix}' in line) == marked
    print(f'{"PASS" if ok else "FAIL"} listing on {day}: {line!r} (marked expected: {marked}) {o.stderr[-200:]}')
    fail += [] if ok else [f'listing {day}']
print('ALL OK' if not fail else f'FAILED: {fail}')
sys.exit(1 if fail else 0)
