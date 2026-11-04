"""End-to-end preservation check against a separately retained pre-append repository."""
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import append as A
import append_gate as G
import build as B
import check as K
from test_build import corpus


class AppendDocsTest(unittest.TestCase):
    def test_same_morning_docs_are_capped_and_identical_refreshes_are_skipped(self):
        day = '2026-11-04'
        morning = int(B.dt.datetime(2026, 11, 4, 8, tzinfo=B.dt.timezone.utc).timestamp())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, repo = root / 'source', root / 'repo'
            source.mkdir()
            c = corpus()
            c['country']['tz'] = 'UTC'
            path = source / 'corpus.json'
            path.write_text(json.dumps(c), encoding='utf-8')
            with mock.patch.object(B.time, 'time', return_value=morning):
                B.build(source, repo, day)
                self.assertEqual(B.git(repo, 'show', '-s', '--format=%at %ct', 'main').strip(),
                                 f'{morning} {morning}')
                A.append(source, repo, day, refresh_docs=True)
                head = B.git(repo, 'rev-parse', 'main').strip()
                repeat = A.append(source, repo, day, refresh_docs=True)
                self.assertTrue(repeat['no_change'])
                self.assertEqual(repeat['main'], head)
                self.assertFalse(G.docs_only(source, repo, day))
            c.setdefault('decisions', []).append('Additional fixture documentation; law text is unchanged.')
            path.write_text(json.dumps(c), encoding='utf-8')
            with mock.patch.object(B.time, 'time', return_value=morning + 2):
                A.append(source, repo, day, refresh_docs=True)
                self.assertEqual(B.git(repo, 'show', '-s', '--format=%at %ct', 'main').strip(),
                                 f'{morning + 2} {morning + 2}')
                checked = K.check(repo, path, day)
                self.assertEqual((checked['mismatches'], checked['trailer_errors'], checked['backwards'],
                                  checked['future_dated']), (0, 0, 0, 0), checked)
            # Noon remains the ceiling once that day's noon is in the past.
            with mock.patch.object(B.time, 'time', return_value=morning + 10 * 3600):
                self.assertEqual(int(B.Clock('UTC').docs_stamp(day).split()[0]), morning + 4 * 3600)
            for p in repo.rglob('*'):
                p.chmod(0o700)

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
