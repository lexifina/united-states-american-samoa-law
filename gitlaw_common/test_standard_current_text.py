"""Fictional source fixtures reproduce an older ordinary write after the current version."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import append as A
import append_gate as G
import build as B
import check as K
import current_text as H
from test_standard_images import fixture


def source_fixture():
    c = fixture()
    c['acts'][0]['versions'] = [
        {'from': day, 'source_url': 'https://official.invalid/law', 'source_images': 0,
         'units': {'article': {'label': 'Article', 'text': text}}}
        for day, text in [('2016-01-01', '# Article\nFictional old source text.\n'),
                          ('2023-01-06', '# Article\nFictional current source text.\n')]]
    return c


class CurrentTextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source, self.repo = self.root / 'source', self.root / 'repo'
        self.source.mkdir()
        self.c = source_fixture()
        self.input = self.source / 'corpus.json'
        self.input.write_text(json.dumps(self.c), encoding='utf-8')
        B.build(self.source, self.repo, '2026-11-03')
        self.head = B.git(self.repo, 'rev-parse', 'main').strip()
        self.tags = B.git(self.repo, 'show-ref', '--tags')

    def tearDown(self):
        for p in self.repo.rglob('*'):
            p.chmod(0o700)
        self.tmp.cleanup()

    def test_older_existing_file_refused_new_file_allowed(self):
        for value in ('old text', None):
            with self.assertRaisesRegex(ValueError, 'older ordinary append'):
                H.ordinary_order(self.repo, [{'day': '2016-01-01', 'files': {'a/article.md': value}}])
        H.ordinary_order(self.repo, [{'day': '1900-01-01', 'files': {'new-act/article.md': 'new file'}}])
        H.ordinary_order(self.repo, [{'day': '2023-01-06', 'files': {'a/article.md': 'same-day text'}}])
        self.assertEqual(B.git(self.repo, 'rev-parse', 'main').strip(), self.head)
        self.assertEqual(B.git(self.repo, 'show-ref', '--tags'), self.tags)

    def test_backfill_requires_correction_before_any_ref_changes(self):
        older = copy.deepcopy(self.c['acts'][0]['versions'][0])
        older['from'] = '2020-01-01'
        older['units']['article']['text'] = '# Article\nFictional intervening source text.\n'
        self.c['acts'][0]['versions'].insert(1, older)
        self.input.write_text(json.dumps(self.c), encoding='utf-8')
        with self.assertRaisesRegex(B.CorpusError, 'correction or a back-filled form'):
            A.append(self.source, self.repo, '2026-11-03')
        self.assertEqual(B.git(self.repo, 'rev-parse', 'main').strip(), self.head)
        self.assertEqual(B.git(self.repo, 'show-ref', '--tags'), self.tags)
        result = A.append(self.source, self.repo, '2026-11-03', corrections=True)
        self.assertGreater(result['corrections'], 0)
        self.assertEqual((self.repo / 'a/article.md').read_text(), self.c['acts'][0]['versions'][-1]['units']['article']['text'])
        self.assertEqual(K.check(self.repo, self.input)['tip_errors'], 0)

    def write_external_stale_commit(self, standard):
        stamp, zone = B.git(self.repo, 'log', '-1', '--format=%ct %ci', 'main').split()[0::3]
        writer = A.Appender(self.repo, self.head, int(stamp), zone)
        identity = ('Fictional source law', 'law@example.invalid')
        writer.commit(identity, B.Clock('UTC').stamp('2016-01-01'), ('Lexifina', 'test@lexifina.com'),
                      'Fictional external builder appends an older text\n\nKind: law\nLaw-kind: act\n'
                      'In-force: 2016-01-01\nSource: https://official.invalid/law\n' +
                      ('Corpus-standard: 1\n' if standard else ''),
                      {'a/article.md': self.c['acts'][0]['versions'][0]['units']['article']['text']})
        writer.finish()
        return B.git(self.repo, 'rev-parse', 'main').strip()

    def test_new_stale_tip_fails_against_current_source(self):
        new = self.write_external_stale_commit(True)
        result = K.check(self.repo, self.input)
        self.assertEqual(result['mismatches'], 1, 'the existing history check also detects this invalid ordinary append')
        self.assertEqual((result['tip_errors'], result['tip_warnings']), (1, 0))
        self.assertEqual(G.check_main(self.source, self.repo, '2026-11-03')['tip_errors'], 1)
        self.assertEqual(G.check_appended(self.source, self.repo, '2026-11-03', self.head, new)['tip_errors'], 1)
        self.assertIn('tip_errors', G.FAIL_KEYS)

    def test_pinned_stale_tip_warns_and_preflight_catches_it(self):
        self.write_external_stale_commit(False)
        result = H.check(self.repo, self.c, '2026-11-03')
        self.assertEqual((result['tip_errors'], result['tip_warnings']), (0, 1))
        self.assertEqual(H.check(self.repo, self.c, '2026-11-03', {})['tip_errors'], 1)
        current = self.c['acts'][0]['versions'][-1]['units']['article']['text']
        self.assertEqual(H.check(self.repo, self.c, '2026-11-03', {'a/article.md': current})['tip_errors'], 0)


if __name__ == '__main__':
    unittest.main()
