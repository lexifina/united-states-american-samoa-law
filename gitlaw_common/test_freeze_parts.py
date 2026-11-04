"""Test append_gate --freeze-parts: a part whose .PUBLISH lands between append and check must not fail the run.

    python -X utf8 scripts/gitlaw_common/test_freeze_parts.py [<work dir>]

A Testland corpus with verified parts in corpus.d is built and "published" to a local bare repository. A new verified
part (20-b) is then to be appended; while the gate runs, right after append.append() returns, another part (30-c) and
its .PUBLISH are written, as an agent might. Without the freeze the check reads 30-c and reports its act missing from
the tip (the netherlands failure of 2026-11-03 06:08); with it the run appends 20-b and passes, and the next run
appends 30-c.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ['GITLAW_VERIFIED_PARTS_ONLY'] = '1'
import append_gate as AG  # noqa: E402

work = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else \
    Path.home() / 'Documents' / '.gitlaw-append' / 'work' / 'test-freeze'
D = '2026-01-01'


def u(text):
    return {'label': text[:6], 'text': text}


def act(slug, day, text):
    return {'slug': slug, 'short': slug[:5], 'title': slug.title(), 'first_law': 'act-1',
            # This synthetic source has one text unit and no images; the initial
            # repository is a new build, which requires an explicit survey.
            'versions': [{'from': day, 'source_images': 0, 'units': {'s-1': u(text)}}]}


BASE = {'country': {'code': 'XT', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                    'publisher': {'name': 'Testland Gazette', 'email': 'gazette@testland.invalid'}},
        'laws': {'act-1': {'label': 'Act 1', 'enacted': '1999-12-01'}},
        'acts': [act('constitution', '2000-01-01', 'One.\n')],
        'sources': [{'name': 'Testland Gazette', 'url': 'https://testland.invalid/', 'retrieved': D}]}


def part(folder: Path, name: str, acts: list[dict]):
    (folder / 'corpus.d').mkdir(exist_ok=True)
    (folder / 'corpus.d' / f'{name}.json').write_text(json.dumps({'acts': acts}), encoding='utf-8', newline='\n')
    (folder / 'corpus.d' / f'{name}.PUBLISH').write_text('verified\n', encoding='utf-8')


def g(repo: Path, *args) -> str:
    r = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        raise SystemExit(f'git {args}: {r.stderr}')
    return r.stdout.strip()


def scenario(name: str, frozen: bool) -> tuple[dict, dict]:
    root = work / name
    if root.exists():
        shutil.rmtree(root, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    folder = root / 'corpus'
    folder.mkdir(parents=True)
    (folder / 'corpus.json').write_text(json.dumps(BASE), encoding='utf-8', newline='\n')
    part(folder, '10-a', [act('statute', '2010-01-01', 'Statute.\n')])
    build = root / 'build'
    r = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'build.py'), str(folder), '--repo', str(build),
                        '--docs-date', D], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr[-1500:]
    origin = root / 'origin.git'
    g(root, 'clone', '-q', '--bare', str(build), str(origin))
    part(folder, '20-b', [act('decree', '2015-01-01', 'Decree.\n')])  # verified before the run: to be appended

    real = AG.AP.append

    def append_then_publish(*a, **k):  # an agent's PUBLISH lands between append and check
        res = real(*a, **k)
        part(folder, '30-c', [act('order', '2020-01-01', 'Order.\n')])
        return res

    AG.AP.append = append_then_publish
    try:
        pub = root / 'pub'
        first = AG.run(AG.freeze(folder) if frozen else folder, pub, str(origin), D, None, incremental=True)
    finally:
        AG.AP.append = real
    second = {}
    if first.get('result') == 'appended':
        g(pub, 'push', '-q', str(origin), 'refs/heads/main:refs/heads/main', '--tags')  # "publish" it
        second = AG.run(AG.freeze(folder) if frozen else folder, pub, str(origin), D, None, incremental=True)
    AG.Frozen.snap = None
    return first, second


results = []


def expect(name, ok, info=''):
    results.append(ok)
    print(f'{"PASS" if ok else "FAIL"}  {name}  {info}')


first, _ = scenario('unfrozen', frozen=False)
expect('without --freeze-parts the mid-run PUBLISH fails the check (the bug reproduced)',
       first.get('result') == 'check failed', f"{first.get('result')}: {str(first.get('details', ''))[:160]}")
first, second = scenario('frozen', frozen=True)
expect('with --freeze-parts the run appends the part verified at its start and passes',
       first.get('result') == 'appended' and first.get('new_acts') == ['decree'],
       f"{first.get('result')} new_acts={first.get('new_acts')} check={first.get('check')}")
expect('the part that landed mid-run goes out on the next run', second.get('result') == 'appended'
       and second.get('new_acts') == ['order'], f"{second.get('result')} new_acts={second.get('new_acts')}")
print(f'{sum(results)}/{len(results)} passed')
if not all(results):
    raise SystemExit(1)
print('ALL OK')
