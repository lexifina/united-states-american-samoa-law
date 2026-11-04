import unittest
import tempfile
from pathlib import Path
import build as B
import append as A


class DocumentationGuardTest(unittest.TestCase):
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
