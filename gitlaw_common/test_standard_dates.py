import unittest
import json
import tempfile
from pathlib import Path
from unittest import mock
import corpus_standard as S
import build as B
import append as A
import check as K


class DatesTest(unittest.TestCase):
    def test_full_checker_reports_future_commit_sha_date_and_now(self):
        now = 1700000000
        future = now + 2 * 86400 + 1
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            c = {'country': {'code': 'XX', 'slug': 'testland'}, 'laws': {}, 'acts': [
                {'slug': 'a', 'versions': [{'from': '2020-01-01', 'units': {'s-1': {'text': '# Fixture\n'}}}]}]}
            source = root / 'corpus.json'
            source.write_text(json.dumps(c), encoding='utf-8')
            B.prepare(repo)
            writer = B.Writer(repo)
            publisher = ('Fixture publisher', 'fixture@example.invalid')
            writer.commit('main', publisher, publisher, '1577836800 +0000',
                          'Fixture\n\nKind: baseline\nIn-force: 2020-01-01\n', {'a/s-1.md': '# Fixture\n'})
            lexifina = ('Lexifina', 'testland-law@lexifina.com')
            writer.commit('main', lexifina, lexifina, f'{future} +0000',
                          'Invalid future fixture\n\nKind: documentation\n', {})
            writer.finish()
            sha = B.git(repo, 'rev-parse', 'main').strip()
            date = B.git(repo, 'show', '-s', '--format=%cI', 'main').strip()
            with mock.patch.object(K.time, 'time', return_value=now):
                checked = K.check(repo, source, '2023-11-14')
            self.assertEqual(checked['future_dated'], 1)
            self.assertEqual(checked['mismatches'], 0)
            self.assertTrue(any(sha in line and date in line and f'now ' in line and f'({now})' in line
                                for line in checked['details']), checked)

    def test_future_date_diagnostics_preserve_the_safety_thresholds(self):
        now = 1700000000
        bad_sha = 'a' * 40
        date = '2023-11-14T22:13:21+00:00'
        commits = [('0' * 40, now - 1, 'past'), (bad_sha, now + 1, date),
                   ('b' * 40, now + 2 * 86400, 'allowed last docs boundary')]
        details = K.future_date_details(commits, now)
        self.assertEqual(len(details), 1)
        for value in (bad_sha, date, str(now + 1), 'now', str(now)):
            self.assertIn(value, details[0])
        # Moving that same allowed docs commit inside the history must still fail.
        self.assertEqual(len(K.future_date_details(commits + [('c' * 40, now, 'new docs')], now)), 2)
        self.assertEqual(len(K.future_date_details([('d' * 40, now + 2 * 86400 + 1, 'too late')], now)), 1)
        self.assertEqual(K.future_date_details([('e' * 40, now, 'boundary')], now), [])

    def setUp(self):
        self.c = {'country': {}, 'sources': [{'retrieved': '2026-10-30'}]}
        self.act = {'slug': 'example'}

    def trailers(self, **version):
        return S.date_trailers(self.c, self.act, {'from': '2020-01-01', **version})

    def test_capture_requires_basis(self):
        with self.assertRaisesRegex(ValueError, 'in_force_basis'):
            self.trailers(**{'from': '2026-10-30'})
        values = self.trailers(**{'from': '2026-10-30', 'in_force_unknown': True,
                                  'in_force_basis': 'source gives no date'})
        self.assertIn('Text-as-of: 2026-10-30', values)
        self.assertIn('In-force-basis: source gives no date', values)

    def test_does_not_infer_capture_from_sentence(self):
        self.assertFalse(any(t.startswith('Text-as-of:') for t in self.trailers(
            in_force_basis='Retrieval day retained because exact commencement is unknown.')))
        act = {'slug': 'example', 'editorial_date_correction': {
            'metadata_only': True, 'in_force_basis': 'Retrieval day retained because exact commencement is unknown.'}}
        self.assertNotIn('text_as_of', A.correction_metadata(act, {'from': '2020-01-01'}))

    def test_known_date_wins(self):
        self.assertEqual(self.trailers(in_force_basis='Gazette commencement clause'),
                         ['In-force-basis: Gazette commencement clause'])
        self.assertEqual(S.date_trailers(self.c, self.act, {'from': '2026-10-30'},
                                         {'enacted': '2026-10-30'}), [])

    def test_retroactive_provision(self):
        self.assertIn('Retroactive: yes; section 7', self.trailers(retroactive='section 7'))
        with self.assertRaises(ValueError):
            self.trailers(retroactive=True)

    def test_consolidated_date_only_and_legacy_url(self):
        with self.assertRaises(ValueError):
            self.trailers(consolidated='https://example.invalid/version')
        self.assertEqual(S.legacy_text_source({'Consolidated': 'https://example.invalid/v'}), 'https://example.invalid/v')
        self.assertIsNone(S.legacy_text_source({'Consolidated': '2020-01-01'}))

    def test_early_date_requires_record_note(self):
        with self.assertRaises(ValueError):
            self.trailers(**{'from': '0881-01-01'})
        self.c['country']['record_note'] = 'Dated historical record from the official source.'
        self.trailers(**{'from': '1400-01-01'})

    def test_date_format_and_duplicate_keys(self):
        with self.assertRaises(ValueError):
            self.trailers(text_as_of='2020-02-30')
        with self.assertRaises(B.CorpusError):
            B.check_trailers(['Kind: law', 'Kind: law'])


if __name__ == '__main__':
    unittest.main()
