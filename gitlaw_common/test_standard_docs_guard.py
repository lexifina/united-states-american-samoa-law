import unittest
import tempfile
from pathlib import Path
import build as B
import append as A
import json
import rollout


class DocumentationGuardTest(unittest.TestCase):
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
