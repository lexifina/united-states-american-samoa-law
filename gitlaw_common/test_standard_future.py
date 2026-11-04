import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import build as B
import append as A
import corpus_standard as S
from test_build import corpus


class FutureTest(unittest.TestCase):
    def test_unchanged_future_history_never_reaches_planning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, repo = root / 'source', root / 'repo'
            source.mkdir()
            c = corpus()
            (source / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            try:
                B.build(source, repo, '2026-10-28')
                refs = B.git(repo, 'show-ref')
                with patch.object(B, 'plan') as plan:
                    self.assertEqual(A.append_future(repo, c, '2026-10-28'), 0)
                plan.assert_not_called()
                self.assertEqual(B.git(repo, 'show-ref'), refs)
            finally:
                for p in repo.rglob('*'):
                    p.chmod(0o700)

    def test_invalid_branch(self):
        for value in ('main', '../bad', 'future.lock', 'x//y', 'HEAD'):
            with self.assertRaises(ValueError):
                S.future_branch({'future_branch': value})

    def test_only_future_law_never_on_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = corpus()
            c['acts'] = [c['acts'][0]]
            c['acts'][0]['versions'] = [c['acts'][0]['versions'][-1]]
            source = root / 'source'
            source.mkdir()
            (source / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            target = root / 'repo'
            try:
                B.build(source, target, '2026-10-28')
                self.assertEqual(B.git(target, 'log', '--format=%(trailers:key=In-force,valueonly)', 'main').strip(), '')
                self.assertIn('2099-02-01', B.git(target, 'log', '--format=%B', 'futuro'))
                self.assertNotIn('constitucion/art-001.md', B.git(target, 'ls-tree', '-r', '--name-only', 'main'))
            finally:
                for p in target.rglob('*'):
                    p.chmod(0o700)


if __name__ == '__main__':
    unittest.main()
