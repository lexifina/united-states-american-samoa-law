"""Compare this builder with unmodified code and three or more unchanged corpora.

    python -X utf8 gitlaw_common/test_correction_compatibility.py --before BASELINE_COMMON \
        --corpus COPY1 --corpus COPY2 --corpus COPY3 --scratch EMPTY_JOB_SCRATCH

No network. Inputs must be job-local copies: build --compare writes verification.json.
Full stdout identity is reported separately from the existing law-history comparison.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def invoke(common, script, args, output):
    saved_path, saved_argv = sys.path[:], sys.argv[:]
    saved_stdout, saved_stderr = sys.stdout, sys.stderr
    # check.py imports build/on by name; each run must use its own unchanged/candidate code.
    modules = {key: sys.modules.pop(key, None) for key in ('build', 'on', 'private')}
    try:
        sys.path.insert(0, str(common))
        sys.argv = [str(common / script), *map(str, args)]
        with output.open('w', encoding='utf-8') as stdout, output.with_suffix('.stderr').open('w', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            try:
                runpy.run_path(str(common / script), run_name='__main__')
                code = 0
            except SystemExit as exc:
                code = exc.code or 0
    finally:
        sys.path[:], sys.argv[:] = saved_path, saved_argv
        sys.stdout, sys.stderr = saved_stdout, saved_stderr
        for key, value in modules.items():
            sys.modules.pop(key, None)
            if value is not None:
                sys.modules[key] = value
    if code:
        raise AssertionError(f'{script} exited {code}: {output.read_text(encoding="utf-8")}')
    return output.read_bytes()


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, check=True, timeout=120).stdout


def objects(output):
    text = output.decode('utf-8')
    decoder, result = json.JSONDecoder(), []
    while text.strip():
        value, end = decoder.raw_decode(text.lstrip())
        result.append(value)
        text = text.lstrip()[end:]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, action='append', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--strict-stdout', action='store_true', help='also fail on any full stdout difference')
    parser.add_argument('--verified-parts-only', action='store_true', help='exercise the main-branch part filter')
    args = parser.parse_args()
    if len(args.corpus) < 3:
        parser.error('at least three unchanged corpus copies are required')
    root = args.scratch.resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.environ['GITLAW_NO_CHECKOUT'] = '1'
    os.environ['GITLAW_VERIFIED_PARTS_ONLY'] = '1' if args.verified_parts_only else '0'
    results = []
    for folder in map(Path.resolve, args.corpus):
        work = root / folder.name
        work.mkdir()
        inputs = ([folder / 'corpus.json'] if (folder / 'corpus.json').exists() else []) + sorted((folder / 'corpus.d').glob('*.json'))
        supplied = [json.loads(p.read_text(encoding='utf-8')) for p in inputs]
        assert all('corrects' not in part for part in supplied)
        docs_date = max(s['retrieved'] for part in supplied for s in part.get('sources', []) if s.get('retrieved'))
        input_hashes = {p.name: sha(p.read_bytes()) for p in inputs}
        verification = folder / 'verification.json'
        saved = verification.read_bytes() if verification.exists() else None
        outputs, loaded, snapshots = {}, {}, {}
        try:
            for phase, common in [('before', args.before.resolve()), ('after', HERE)]:
                if saved is None:
                    verification.unlink(missing_ok=True)
                else:
                    verification.write_bytes(saved)
                spec = importlib.util.spec_from_file_location(f'{phase}_build', common / 'build.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                corpus, raw = module.load(folder)
                assert module.validate(corpus) == []
                loaded[phase] = (corpus, raw)
                repo = work / phase
                outputs[phase] = invoke(common, 'build.py', [folder, '--repo', repo, '--docs-date', docs_date,
                    *(['--compare', work / 'before'] if phase == 'after' else [])], work / f'{phase}-build.stdout')
                outputs[phase + '-check'] = invoke(common, 'check.py', [repo, '--corpus', folder / 'corpus.json'],
                                                  work / f'{phase}-check.stdout')
                snapshots[phase] = {
                    'history': git(repo, 'log', '--format=%H', 'main^'),
                    'tags': git(repo, 'show-ref', '--tags'),
                    'tree': git(repo, 'ls-tree', '-r', 'main'),
                }
            # Exercise baseline --compare too, restoring the same verification input first.
            if saved is None:
                verification.unlink(missing_ok=True)
            else:
                verification.write_bytes(saved)
            outputs['before-compare'] = invoke(args.before.resolve(), 'build.py', [folder, '--repo', work / 'before-again',
                '--docs-date', docs_date, '--compare', work / 'before'], work / 'before-compare.stdout')
        finally:
            if saved is None:
                verification.unlink(missing_ok=True)
            else:
                verification.write_bytes(saved)
        assert input_hashes == {p.name: sha(p.read_bytes()) for p in inputs}
        assert loaded['before'] == loaded['after']
        assert snapshots['before']['history'] == snapshots['after']['history']
        assert snapshots['before']['tags'] == snapshots['after']['tags']
        assert outputs['before-check'] == outputs['after-check']
        # Updated shipped tools change the docs SHA and --compare's main_identical.
        # Keep those differences visible; require all law comparison fields equal.
        comparison_tails = []
        for output in (outputs['before-compare'], outputs['after']):
            text = output.decode('utf-8')
            _, end = json.JSONDecoder().raw_decode(text)
            comparison_tails.append(text[end:].encode('utf-8'))
        records = [objects(output) for output in (outputs['before-compare'], outputs['after'])]
        assert {k: v for k, v in records[0][0].items() if k != 'main'} == {
            k: v for k, v in records[1][0].items() if k != 'main'}
        assert {k: v for k, v in records[0][1].items() if k != 'main_identical'} == {
            k: v for k, v in records[1][1].items() if k != 'main_identical'}
        before_files, after_files = {}, {}
        for phase, files in [('before', before_files), ('after', after_files)]:
            for line in snapshots[phase]['tree'].decode('utf-8').splitlines():
                meta, path = line.split('\t', 1)
                files[path] = meta
        differences = sorted(p for p in set(before_files) | set(after_files) if before_files.get(p) != after_files.get(p))
        assert set(differences) <= {'tools/build.py', 'tools/publish_marker.py', 'tools/SCHEMA.md', 'REPRODUCE.md'}, differences
        check = json.loads(outputs['after-check'])
        for field in ('mismatches', 'trailer_errors', 'missing_in_force', 'merges', 'backwards', 'future_dated'):
            assert check[field] == 0, check
        entry = {
            'corpus': folder.name, 'docs_date': docs_date, 'check': check,
            'input_hashes': input_hashes, 'merged_corpus_and_raw_bytes_identical': True,
            'history_bytes_identical': True, 'history_sha256': sha(snapshots['before']['history']),
            'tag_bytes_identical': True, 'tags_sha256': sha(snapshots['before']['tags']),
            'check_stdout_bytes_identical': True, 'check_stdout_sha256': sha(outputs['before-check']),
            'before_compare_stdout_sha256': sha(outputs['before-compare']),
            'after_compare_stdout_sha256': sha(outputs['after']),
            'build_compare_stdout_bytes_identical': outputs['before-compare'] == outputs['after'],
            'compare_result_identical': objects(outputs['before-compare'])[1:] == objects(outputs['after'])[1:],
            'compare_stdout_bytes_identical': comparison_tails[0] == comparison_tails[1],
            'compare_stdout_sha256': sha(comparison_tails[0]),
            'before_compare': objects(outputs['before-compare']), 'after_compare': objects(outputs['after']),
            'changed_tip_files': differences,
        }
        results.append(entry)
        (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(entry), flush=True)
    if args.strict_stdout:
        assert all(r['build_compare_stdout_bytes_identical'] for r in results), 'full build --compare stdout differs; see results.json'


if __name__ == '__main__':
    main()
