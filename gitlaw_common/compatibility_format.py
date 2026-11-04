"""Independent v1 expectations for the compatibility test; never used by the builder."""
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

from test_correction_compatibility import HERE, git, invoke, objects, sha

DOC_REASONS = {
    '.gitattributes': 'Section 5a marks retained assets as binary.',
    'corpus.json': 'Section 2 adds the root descriptor and its required fields.',
    'jurisdiction.json': 'Section 2 derives jurisdiction path, level, code and parent.',
    'data/acts.json': 'Section 4 adds static act facts, lifecycle status and image counts.',
    'data/assets.tsv': 'Section 5a adds the image asset inventory.',
    'data/provisions.tsv': 'Section 5 adds provision intervals with commit provenance.',
    'data/laws.csv': 'Section 5 adds law_kind and canonical kind values.',
    'data/versions.json': 'Section 5 adds validity, status and capture metadata.',
    'data/commits.csv': 'The ledger records canonical kinds and the generated commit IDs.',
    'data/repo.json': 'Section 1 replaces the deprecated descriptor with root corpus.json.',
    'data/parts.json': 'The documentation refresh records unchanged input ownership.',
    'README.md': 'The generated corpus summary describes the standard record.',
    'REPRODUCE.md': 'The reproduction record identifies the new tools, kinds and checks.',
}
TOOLS = {'build.py', 'check.py', 'check_repo.py', 'on.py', 'append.py', 'append_gate.py', 'publish_marker.py', 'published_parts.py',
         'corpus_standard.py', 'corpus_paths.py', 'corpus_tables.py', 'corpus_images.py', 'corpus_jurisdiction.py',
         'provision_index.py', 'current_text.py', 'SCHEMA.md', 'REPRODUCE.template.md'}
ERRORS = ('mismatches', 'trailer_errors', 'missing_in_force', 'merges', 'backwards', 'future_dated',
          'image_errors', 'tip_errors')


def tree(repo, ref='main'):
    return dict(line.split('\t', 1)[::-1] for line in git(repo, 'ls-tree', '-r', ref).decode().splitlines())


def differences(before, after):
    a, b = tree(before), tree(after)
    rows = []
    for path in sorted(set(a) | set(b)):
        if a.get(path) == b.get(path):
            continue
        reason = DOC_REASONS.get(path)
        if path.startswith('tools/') and path.removeprefix('tools/') in TOOLS:
            reason = 'Ship the reviewed v1 builder/reader/schema used for this documentation refresh.'
        if path.endswith('/README.md'):
            reason = 'Generated act metadata and history links reflect canonical kinds and commit IDs.'
        assert reason, f'unexpected changed path: {path}'
        rows.append({'path': path, 'before': a.get(path), 'after': b.get(path), 'reason': reason})
    return rows


def history(repo, ref):
    records = []
    fmt = '%x00%H%x1f%T%x1f%an%x1f%ae%x1f%at%x1f%cn%x1f%ce%x1f%ct%x1f%B%x1e'
    output = git(repo, 'log', '--reverse', '--no-renames', '--name-only', '--format=' + fmt, ref).decode()
    for raw in output.split('\0')[1:]:
        header, names = raw.split('\x1e', 1)
        commit, *parts = header.split('\x1f', 8)
        message = parts.pop().rstrip('\n')
        if 'Kind: documentation' in message.splitlines() or not re.search(r'^In-force: ', message, re.M):
            continue
        metadata = '\x1f'.join(parts)
        files = [p for p in names.splitlines() if p]
        records.append({'commit': commit, 'tree_author_committer': metadata, 'message': message, 'files': files})
    return records


def expected_message(old, corpus):
    """The written standard's explicit changes; legal wording and all other message text stay exact."""
    body, trailers = old['message'].rsplit('\n\n', 1)
    lines = trailers.splitlines()
    fields = dict(line.split(': ', 1) for line in lines if ': ' in line)
    original_kind = fields.get('Kind', 'law')
    kind = original_kind
    if original_kind == 'publisher':
        kind = 'baseline' if 'oldest version available' in body.splitlines()[0] else 'uncredited'
    elif original_kind not in {'law', 'baseline', 'uncredited', 'correction', 'court', 'treaty', 'printing'}:
        kind = 'law'
    expected = [f'Kind: {kind}' if line.startswith('Kind: ') else
                'Text-source: ' + line.split(': ', 1)[1] if line.startswith('Consolidated: http') else line
                for line in lines]
    if kind == 'law':
        instrument = original_kind if original_kind in {'constitution', 'constitutional-amendment', 'act', 'code',
            'decree', 'decree-law', 'regulation', 'ordinance', 'legal-notice', 'referendum', 'other'} else 'act'
        expected.append('Law-kind: ' + instrument)
    if 'Source' not in fields:
        acts = [a for a in corpus['acts'] if any(p.startswith(a['slug'] + '/') for p in old['files'])
                or a.get('short', '\0') in body.splitlines()[0]]
        urls = sorted({a['url'] for a in acts if a.get('url')})
        urls = urls or [s['url'] for s in corpus.get('sources', []) if s.get('url')]
        if urls:
            expected.append('Source: ' + urls[0])
    expected.append('Corpus-standard: 1')
    return body, Counter(expected)


def tag_equivalence(before, after, mapping):
    def refs(repo):
        return dict(line.split('\t', 1) for line in git(repo, 'for-each-ref',
            '--format=%(refname)%09%(objecttype)%09%(objectname)', 'refs/tags').decode().splitlines())
    old, new = refs(before), refs(after)
    assert old.keys() == new.keys(), 'tag names differ'
    for name, entry in old.items():
        kind, oid = entry.split('\t')
        new_kind, new_oid = new[name].split('\t')
        assert kind == new_kind
        if kind == 'commit':
            assert mapping[oid] == new_oid, name
        else:
            a = git(before, 'cat-file', '-p', oid)
            target, rest = a.split(b'\n', 1)
            expected = b'object ' + mapping[target.split()[1].decode()].encode() + b'\n' + rest
            assert git(after, 'cat-file', '-p', new_oid) == expected, name
        # Every mapping pair has already passed exact Git tree/attribution/date equality.
    return {'names_types_payloads_and_target_trees_equal': True, 'count': len(old), 'raw_refs_equal': old == new,
            'reason_for_new_targets': 'Required v1 law trailers change fresh commit IDs; exact old tags are tested in the published upgrade.'}


def verify(args):
    root = args.scratch.resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.environ['GITLAW_NO_CHECKOUT'] = '1'
    os.environ['GITLAW_VERIFIED_PARTS_ONLY'] = '1' if args.verified_parts_only else '0'
    results = []
    for folder in map(Path.resolve, args.corpus):
        work = root / folder.name
        work.mkdir()
        inputs = ([folder / 'corpus.json'] if (folder / 'corpus.json').exists() else []) + sorted((folder / 'corpus.d').glob('*.json'))
        input_hashes = {p.name: sha(p.read_bytes()) for p in inputs}
        verification = folder / 'verification.json'
        saved_verification = verification.read_bytes() if verification.exists() else None
        supplied = [json.loads(p.read_text(encoding='utf-8')) for p in inputs]
        assert all('corrects' not in part for part in supplied)
        date = max(s['retrieved'] for part in supplied for s in part.get('sources', []) if s.get('retrieved'))
        spec = importlib.util.spec_from_file_location('unchanged_corpus_loader', args.before / 'build.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        corpus, _ = module.load(folder)
        assert module.validate(corpus) == []
        before, after, upgraded = work / 'before', work / 'after', work / 'upgraded'
        invoke(args.before, 'build.py', [folder, '--repo', before, '--docs-date', date], work / 'before-build.stdout')
        invoke(HERE, 'build.py', [folder, '--repo', after, '--docs-date', date], work / 'after-build.stdout')
        checks = {}
        for phase, common, repo in [('before', args.before, before), ('after', HERE, after)]:
            checks[phase] = json.loads(invoke(common, 'check.py', [repo, '--corpus', folder / 'corpus.json'], work / (phase + '-check.stdout')))
            assert all(checks[phase].get(k, 0) == 0 for k in ERRORS), checks[phase]
        for key in ('acts', 'versions', *ERRORS[:6]):
            assert checks['before'][key] == checks['after'][key], key
        refs = git(before, 'for-each-ref', '--format=%(refname)', 'refs/heads').decode().splitlines()
        assert refs == git(after, 'for-each-ref', '--format=%(refname)', 'refs/heads').decode().splitlines()
        mapping, changes = {}, []
        for ref in refs:
            old, new = history(before, ref), history(after, ref)
            assert len(old) == len(new), ref
            for a, b in zip(old, new):
                assert a['tree_author_committer'] == b['tree_author_committer'], (ref, a, b)
                body, trailers = expected_message(a, corpus)
                new_body, new_trailers = b['message'].rsplit('\n\n', 1)
                assert body == new_body and trailers == Counter(new_trailers.splitlines()), (a, b, trailers)
                mapping[a['commit']] = b['commit']
                changes.append({'ref': ref, 'before': a['commit'], 'after': b['commit'],
                                'tree_author_committer_equal': True,
                                'before_message': a['message'], 'after_message': b['message'],
                                'reason': 'Only the explicitly asserted Kind, Law-kind, Source, Text-source and Corpus-standard trailer changes.'})
        tags = tag_equivalence(before, after, mapping)
        fresh_paths = differences(before, after)
        descriptor = json.loads(git(after, 'show', 'main:corpus.json'))
        assert descriptor['acts'] == len(corpus['acts'])
        assert descriptor['scope'] == 'selected-acts'
        assert descriptor['history'] == 'in-force'
        assert descriptor['future_branch'] == corpus['country'].get('future_branch', 'futuro')
        assert descriptor['publisher'] == corpus['country']['publisher']['name']
        indexed = json.loads(git(after, 'show', 'main:data/acts.json'))['acts']
        assert {a['slug'] for a in indexed} == {a['slug'] for a in corpus['acts']}
        for act in indexed:
            source_act = next(a for a in corpus['acts'] if a['slug'] == act['slug'])
            assert act['title'] == source_act['title']
            assert act['images'] == act['images_omitted'] == act['images_source'] == 0
        # The independent old build is now the published input. Every byte of its
        # old commits, trees and tags must survive the actual v1 append/docs path.
        subprocess.run(['git', 'clone', '--no-hardlinks', str(before), str(upgraded)], check=True, capture_output=True, timeout=120)
        upgrade = objects(invoke(HERE, 'build.py', [folder, '--repo', upgraded, '--docs-date', date,
            '--append', '--refresh-docs', '--compare', before], work / 'upgrade.stdout'))
        assert upgrade[-1]['identical'] and upgrade[-1]['documentation_commits'] == 1, upgrade
        assert git(before, 'rev-list', 'main') == git(upgraded, 'rev-list', 'main^')
        assert git(before, 'show-ref', '--tags') == git(upgraded, 'show-ref', '--tags')
        old_trees = git(before, 'log', '--format=%H %T', 'main')
        assert old_trees == git(upgraded, 'log', '--format=%H %T', 'main^')
        upgrade_paths = differences(before, upgraded)
        assert input_hashes == {p.name: sha(p.read_bytes()) for p in inputs}
        if saved_verification is None:
            verification.unlink(missing_ok=True)
        else:
            verification.write_bytes(saved_verification)
        results.append({'corpus': folder.name, 'input_hashes': input_hashes, 'source_checks': checks,
            'fresh_law_trees_attribution_and_dates_identical': True, 'fresh_commits': changes, 'fresh_tags': tags,
            'fresh_changed_paths': fresh_paths, 'published_history_commits_and_trees_identical': True,
            'published_tag_objects_identical': True, 'published_history_tree_sha256': sha(old_trees),
            'published_upgrade': upgrade[-1], 'published_changed_paths': upgrade_paths, 'passed': True})
        (root / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        if args.format_evidence:
            args.format_evidence.write_text(json.dumps({'resolution': 'A(2)', 'results': results,
                'success': len(results) == len(args.corpus)}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'corpus': folder.name, 'passed': True, 'published_history_and_tags_identical': True}), flush=True)
