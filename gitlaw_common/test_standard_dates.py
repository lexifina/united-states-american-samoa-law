import unittest
import corpus_standard as S
import build as B
import append as A


class DatesTest(unittest.TestCase):
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
