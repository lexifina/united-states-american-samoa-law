import unittest
import corpus_tables as T


class ActsTest(unittest.TestCase):
    def make(self, **act):
        return {'country': {}, 'laws': {'a': {'label': 'Act A', 'kind': 'code', 'enacted': '2000-01-01',
                                              'published': '2000-02-01'}},
                'acts': [{'slug': 'a', 'title': 'Act A', 'short': 'A', 'first_law': 'a',
                          'versions': [{'from': '2000-03-01', 'units': {'s-1': {}}}], **act}]}

    def row(self, **act):
        return T.acts_document(self.make(**act), '2026-11-03')['acts'][0]

    def test_static_dates_are_original_dates(self):
        row = self.row()
        self.assertEqual((row['enacted'], row['published'], row['in_force']), ('2000-01-01', '2000-02-01', '2000-03-01'))
        self.assertEqual(row['law_kind'], 'code')
        self.assertEqual(row['status'], 'in force')

    def test_baseline_has_no_invented_commencement(self):
        row = self.row(first_law=None)
        self.assertIsNone(row['in_force'])
        self.assertEqual(row['status'], 'as captured')

    def test_statuses(self):
        self.assertEqual(self.row(repealed='2020-01-01', repealed_by='Act B')['status'], 'repealed')
        self.assertEqual(self.row(expired='2020-01-01')['status'], 'expired')
        self.assertEqual(self.row(versions=[{'from': '2099-01-01', 'units': {}}])['status'], 'not yet in force')
        self.assertEqual(self.row(versions=[{'from': '2000-03-01', 'units': {'s-1': {}}},
                                            {'from': '2020-01-01', 'units': {}}])['repealed'], '2020-01-01')

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            self.row(status='unknown')


if __name__ == '__main__':
    unittest.main()
