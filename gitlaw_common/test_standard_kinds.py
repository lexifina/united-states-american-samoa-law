import unittest
import build as B
import corpus_standard as S


class KindsTest(unittest.TestCase):
    def test_all_instruments(self):
        for value in S.LAW_KINDS:
            c = {'laws': {'x': {'label': 'Instrument X', 'kind': value}}}
            trailers = B.law_trailers(c, 'x', '2020-01-01')
            self.assertIn('Kind: law', trailers)
            self.assertIn('Law-kind: ' + value, trailers)

    def test_court_and_treaty(self):
        for value in ('court', 'treaty'):
            self.assertEqual(S.law_commit_kind({'kind': value}), value)

    def test_legacy(self):
        for value in ('decree', 'amendment', 'act', 'amending law', 'lov', 'lbk', 'laki', 'ustawa',
                      'zakon', 'rozporządzenie', 'legal notice', 'ordinance', 'several', 'enacted',
                      'original', 'version', 'repeal', '', 'unknown-local-name'):
            self.assertEqual(S.legacy_kind(value), 'law')
        self.assertEqual(S.legacy_kind('publisher', 'X: oldest version available'), 'baseline')
        self.assertEqual(S.legacy_kind('publisher', words_changed='yes'), 'uncredited')
        self.assertEqual(S.legacy_kind('correction'), 'law')
        self.assertEqual(S.legacy_kind('correction', corrects='x 2020-01-01..'), 'correction')
        self.assertEqual(S.legacy_kind('anything', author='Lexifina'), 'documentation')
        for value in ('editorial note', 'notes only', 'style only change', 'no act named', 'X (not credited)'):
            self.assertEqual(S.legacy_kind(value), 'uncredited')


if __name__ == '__main__':
    unittest.main()
