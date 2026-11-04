import unittest
import tempfile
from pathlib import Path
import build as B
import append as A
import json
import copy
import rollout
from unittest.mock import patch


class DocumentationGuardTest(unittest.TestCase):
    def native_history(self, root, texts=('First native text.\n', 'Middle native text.\n', 'Last native text.\n'), unit='s-1'):
        folder, repo = root / 'input', root / 'repo'
        folder.mkdir()
        c = {'country': {'slug': 'testland', 'code': 'XX', 'name': 'Testland', 'tz': 'UTC', 'lang': 'en',
                         'publisher': {'name': 'Native fixture', 'email': 'fixture@example.invalid'}},
             'laws': {}, 'acts': [{'slug': 'a', 'short': 'A', 'title': 'Native act', 'versions': []}]}
        B.prepare(repo)
        writer = B.Writer(repo)
        identity = ('Native fixture', 'fixture@example.invalid')
        for index, text in enumerate(texts):
            day = f'{2020 + index}-01-01'
            files = {'a/' + unit + '.md': text}
            if index == 0:
                files.update({'corpus.json': '{"acts": 1}\n',
                              'jurisdiction.json': '{"code":"XX","level":"country"}\n'})
            mark = writer.commit('main', identity, identity, f'{1600000000 + index} +0000',
                                 f'Independent native event\n\nKind: law\nIn-force: {day}\n', files)
            writer.tag('a/' + day, mark)
            c['acts'][0]['versions'].append({'from': day, 'source_images': 0,
                                            'units': {unit: {'label': '1', 'text': text}}})
        writer.finish()
        return folder, repo, c

    def refused_inventory(self, folder, repo, c, message):
        (folder / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
        before = B.git(repo, 'for-each-ref', '--format=%(refname) %(objectname)')
        head = B.git(repo, 'rev-parse', 'main').strip()
        with self.assertRaisesRegex(B.CorpusError, message):
            rollout.refresh(folder, repo, '2026-11-04', head)
        self.assertEqual(B.git(repo, 'for-each-ref', '--format=%(refname) %(objectname)'), before)
        self.assertEqual(B.git(repo, 'rev-parse', 'main').strip(), head)

    def test_rollout_refuses_omitted_middle_transition_and_preserves_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, repo, c = self.native_history(Path(tmp))
            c['acts'][0]['versions'].pop(1)
            self.refused_inventory(folder, repo, c, '2021-01-01.*published text transition')

    def test_rollout_keeps_nested_provisions_with_their_act(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, repo, c = self.native_history(Path(tmp), unit='schedule/s-1')
            (folder / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            head = B.git(repo, 'rev-parse', 'main').strip()
            result = rollout.refresh(folder, repo, '2026-11-04', head)
            self.assertEqual(result['documentation_commits'], 1)
            self.assertEqual(B.git(repo, 'rev-parse', 'main^').strip(), head)
            c['acts'][0]['versions'].pop(1)
            self.refused_inventory(folder, repo, c, '2021-01-01.*published text transition')

    def test_rollout_refuses_equal_count_with_missing_act_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, repo, c = self.native_history(Path(tmp))
            # Count and empty current text alone cannot identify an unheld act.
            c['acts'][0]['slug'] = 'unpublished'
            c['acts'][0]['versions'] = []
            self.refused_inventory(folder, repo, c, 'act identity coverage')

    def test_rollout_accepts_omitted_redundant_text_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, repo, c = self.native_history(Path(tmp), ('Same native text.\n', 'Same native text.\n', 'Last native text.\n'))
            c['acts'][0]['versions'].pop(1)
            (folder / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            head = B.git(repo, 'rev-parse', 'main').strip()
            tags = B.git(repo, 'show-ref', '--tags')
            result = rollout.refresh(folder, repo, '2026-11-04', head)
            self.assertEqual(result['documentation_commits'], 1)
            self.assertEqual(B.git(repo, 'rev-parse', 'main^').strip(), head)
            self.assertEqual(B.git(repo, 'show-ref', '--tags'), tags)

    def test_rollout_checks_correction_start_and_return_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, repo, c = self.native_history(Path(tmp), ('Original native text.\n', 'Original native text.\n', 'Last native text.\n'))
            c['acts'][0]['versions'].pop(1)
            head = B.git(repo, 'rev-parse', 'main').strip()
            writer = A.Appender(repo, head, 1600000002, '+0000')
            identity = ('Native fixture', 'fixture@example.invalid')
            writer.commit(identity, '1700000000 +0000', identity,
                'Independent correction\n\nKind: correction\nIn-force: 2021-02-01\n'
                'Corrects: a 2021-02-01..2021-06-30\nAct-path: a\nFiles: a/s-1.md\n',
                {'a/s-1.md': 'Corrected native text.\n'})
            writer.commit(identity, '1700000001 +0000', identity,
                'Native tip restored\n\nKind: correction\nIn-force: 2022-01-01\n'
                'Corrects: a 2022-01-01..\nAct-path: a\nFiles: a/s-1.md\n',
                {'a/s-1.md': 'Last native text.\n'})
            writer.finish()
            self.refused_inventory(folder, repo, c, '2021-02-01.*published text transition')
            supplied = copy.deepcopy(c)
            supplied['acts'][0]['versions'].insert(1, {'from': '2021-02-01', 'source_images': 0,
                'units': {'s-1': {'label': '1', 'text': 'Corrected native text.\n'}}})
            self.refused_inventory(folder, repo, supplied, '2021-07-01.*published text transition')

    def test_bare_worktree_and_detached_history_refused_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / 'native'
            B.prepare(native)
            writer = B.Writer(native)
            identity = ('Independent fixture', 'fixture@example.invalid')
            mark = writer.commit('main', identity, identity, '1600000000 +0000',
                                 'Native root\n\nIn-force: 2020-01-01\n', {'a/s-1.md': 'Native fixture.\n'})
            writer.tag('a/2020-01-01', mark)
            writer.finish()
            bare, linked, detached = (root / name for name in ('bare.git', 'linked', 'detached'))
            B.git(root, 'clone', '--bare', '--no-hardlinks', str(native), str(bare))
            B.git(native, 'worktree', 'add', '--detach', str(linked), 'main')
            B.git(root, 'clone', '--no-hardlinks', str(native), str(detached))
            B.git(detached, 'checkout', '--detach', 'main')
            for line in B.git(detached, 'for-each-ref', '--format=%(refname)').splitlines():
                B.git(detached, 'update-ref', '-d', line)
            for repo in (native, bare, linked, detached):
                before = B.git(repo, 'for-each-ref', '--format=%(refname) %(objectname)')
                head = B.git(repo, 'rev-parse', 'HEAD')
                # Constructor refusal occurs before any import can replay the
                # native root and move its tag to a fast-forward descendant.
                with patch.object(B.subprocess, 'Popen', wraps=B.subprocess.Popen) as processes:
                    with self.assertRaisesRegex(B.CorpusError, 'append-only'):
                        B.Writer(repo)
                    self.assertFalse(any('fast-import' in call.args[0] for call in processes.call_args_list))
                self.assertEqual(B.git(repo, 'for-each-ref', '--format=%(refname) %(objectname)'), before)
                self.assertEqual(B.git(repo, 'rev-parse', 'HEAD'), head)

    def test_writer_never_discovers_enclosing_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / 'outer'
            B.prepare(outer)
            nested = outer / 'uninitialized'
            nested.mkdir()
            self.assertIsNone(B.target_git_dir(nested))
            with self.assertRaisesRegex(B.CorpusError, 'initialized target'):
                B.Writer(nested)
            self.assertEqual(B.git(outer, 'for-each-ref'), '')

    def test_writer_tag_refuses_published_and_queued_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            B.prepare(repo)
            writer = B.Writer(repo)
            identity = ('Independent fixture', 'fixture@example.invalid')
            mark = writer.commit('main', identity, identity, '1600000000 +0000',
                                 'Native root\n', {'a/s-1.md': 'Native fixture.\n'})
            writer.tag('queued', mark)
            with self.assertRaisesRegex(B.CorpusError, 'existing tag'):
                writer.tag('queued', mark)
            writer.checkpoint()
            root = B.git(repo, 'rev-parse', 'main').strip()
            B.git(repo, 'update-ref', 'refs/tags/published', root)
            before = B.git(repo, 'rev-parse', 'refs/tags/published')
            newer = writer.commit('main', identity, identity, '1700000000 +0000',
                                  'Documentation\n', {'README.md': 'Fixture documentation.\n'})
            with self.assertRaisesRegex(B.CorpusError, 'existing tag'):
                writer.tag('published', newer)
            writer.finish()
            self.assertEqual(B.git(repo, 'rev-parse', 'refs/tags/published'), before)

    def test_own_builder_rollout_is_one_docs_commit_and_preserves_native_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, repo = Path(tmp) / 'input', Path(tmp) / 'published'
            folder.mkdir()
            c = {'country': {'slug': 'testland', 'code': 'XX', 'name': 'Testland', 'tz': 'UTC',
                             'lang': 'en', 'publisher': {'name': 'Gazette', 'email': 'gazette@example.invalid'}},
                 'laws': {}, 'acts': [{'slug': 'a', 'title': 'Fixture', 'short': 'Fixture',
                     'versions': [{'from': '2020-01-01', 'units': {'s-1': {'label': 's 1', 'text': '# Fixture\n'}}}]}]}
            source = folder / 'corpus.json'
            source.write_text(json.dumps(c), encoding='utf-8')
            B.prepare(repo)
            writer = B.Writer(repo)
            identity = ('Fixture publisher', 'fixture@example.invalid')
            original = {'a/s-1.md': '# Fixture\n', 'tools/build.py': '# native builder\n',
                        'data/native.json': '{"native": true}\n', 'README.md': '# Native repository\n',
                        'corpus.json': '{"acts": 1, "coverage": "One native fixture"}\n',
                        'jurisdiction.json': '{"name": "Testland", "code": "XX", "level": "country"}\n'}
            mark = writer.commit('main', identity, identity, '1700000000 +0000',
                                 'Oldest version available\n\nKind: publisher\nIn-force: 2020-01-01\n', original)
            writer.tag('a/2020-01-01', mark)
            writer.finish()
            before = B.git(repo, 'rev-parse', 'main').strip()
            old_tags = B.git(repo, 'show-ref', '--tags')
            with self.assertRaisesRegex(B.CorpusError, 'head changed'):
                rollout.refresh(folder, repo, '2026-11-04', '0' * 40)
            result = rollout.refresh(folder, repo, '2026-11-04', before)
            after = result['main']
            self.assertEqual(result['documentation_commits'], 1)
            self.assertEqual(B.git(repo, 'rev-parse', after + '^').strip(), before)
            self.assertEqual(B.git(repo, 'show-ref', '--tags'), old_tags)
            for path in ('a/s-1.md', 'tools/build.py', 'data/native.json', 'README.md'):
                self.assertEqual(B.git(repo, 'show', after + ':' + path), original[path])
            self.assertEqual(json.loads(B.git(repo, 'show', after + ':corpus.json'))['coverage'], 'One native fixture')
            self.assertEqual(rollout.refresh(folder, repo, '2026-11-04', after)['documentation_commits'], 0)
            source.write_text(json.dumps({**c, 'acts': []}), encoding='utf-8')
            with self.assertRaisesRegex(B.CorpusError, 'complete published act inventory'):
                rollout.refresh(folder, repo, '2026-11-04', after)
            c['acts'][0]['versions'].append({'from': '2025-01-01', 'units': {}})
            source.write_text(json.dumps(c), encoding='utf-8')
            with self.assertRaisesRegex(B.CorpusError, 'only indexes published versions'):
                rollout.refresh(folder, repo, '2026-11-04', after)
            c['acts'][0]['versions'].pop()
            c['acts'][0]['versions'][0]['units']['s-1']['text'] = '# Changed\n'
            source.write_text(json.dumps(c), encoding='utf-8')
            with self.assertRaisesRegex(B.CorpusError, 'main differs'):
                rollout.refresh(folder, repo, '2026-11-04', after)
            self.assertEqual(B.git(repo, 'rev-parse', 'main').strip(), after)

    def test_docs_cannot_write_law(self):
        for path in ('a/s-1.md', 'a/assets/anything.png'):
            with self.assertRaises(B.CorpusError):
                B.check_documentation_paths({'acts': [{'slug': 'a'}]}, {path: 'text'})
        B.check_documentation_paths({'acts': [{'slug': 'a'}]}, {'a/README.md': 'index', 'data/acts.json': '{}'})

    def test_full_build_and_writer_refuse_existing_history_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'published'
            B.prepare(repo)
            w = B.Writer(repo)
            identity = ('Fixture publisher', 'fixture@example.invalid')
            mark = w.commit('main', identity, identity, '1700000000 +0000',
                            'Fixture\n\nKind: law\nIn-force: 2020-01-01\n', {'a/s-1.md': '# Fixture\n'})
            w.tag('a/2020-01-01', mark)
            w.finish()
            before = B.hashes(repo)
            tree = B.git(repo, 'rev-parse', 'main^{tree}')
            for operation in (lambda: B.prepare(repo), lambda: B.Writer(repo),
                              lambda: B.build(Path(tmp) / 'missing-input', repo, '2026-11-04')):
                with self.assertRaisesRegex(B.CorpusError, 'append-only'):
                    operation()
                self.assertEqual(B.hashes(repo), before)
                self.assertEqual(B.git(repo, 'rev-parse', 'main^{tree}'), tree)
            head = B.git(repo, 'rev-parse', 'main').strip()
            writer = A.Appender(repo, head, 1700000000, '+0000')
            try:
                with self.assertRaisesRegex(B.CorpusError, 'existing tag'):
                    writer.tag('a/2020-01-01', 1)
            finally:
                writer.finish()
            self.assertEqual(B.hashes(repo), before)


if __name__ == '__main__':
    unittest.main()
