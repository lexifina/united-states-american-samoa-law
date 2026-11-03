"""End-to-end preservation check against a separately retained pre-append repository."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import append as A
import append_gate as G
import build as B
from test_build import corpus


class AppendDocsTest(unittest.TestCase):
    def test_one_documentation_commit_keeps_all_law_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'corpus.json').write_text(json.dumps(corpus()), encoding='utf-8')
            previous = root / 'previous'
            B.build(source, previous, '2026-10-28')
            target = root / 'target'
            B.git(root, 'clone', '--no-hardlinks', str(previous), str(target))
            try:
                result = A.append(source, target, '2026-10-28', refresh_docs=True)
                self.assertEqual(result['commits'], 0)
                proof = B.compare_preserved(target, previous)
                self.assertTrue(proof['identical'], proof)
                self.assertEqual(proof['documentation_commits'], 1)
                self.assertFalse(G.docs_only(source, target, '2026-10-28'), 'repeat refresh must not add another docs commit')
                for change in proof['changed_files']:
                    path = change.split('\t')[-1]
                    self.assertFalse(path.startswith(('constitucion/art-', 'codigo-civil/art-')), path)
            finally:
                # Git object files on Windows are read-only.
                for repo in (target, previous):
                    for p in repo.rglob('*'):
                        p.chmod(0o700)


if __name__ == '__main__':
    unittest.main()
