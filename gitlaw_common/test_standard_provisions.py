import unittest
import provision_index as I


class ProvisionsTest(unittest.TestCase):
    def fixture(self):
        c = {'country': {}, 'laws': {}, 'acts': [{'slug': 'a', 'first_law': None, 'versions': [
            {'from': '2020-01-01', 'text_as_of': '2020-01-01', 'units': {'s': {'text': 'A\n'}, 't': {'text': 'X\n'}}},
            {'from': '2021-01-01', 'units': {'s': {'text': 'B\n'}, 't': {'text': 'X\n'}}},
            {'from': '2022-01-01', 'units': {'t': {'text': 'X\n'}}}]}]}
        records = [{'commit': 'one', 'day': '2020-01-01', 'kind': 'baseline', 'law': '', 'files': ['a/s.md', 'a/t.md'], 'ranges': []},
                   {'commit': 'two', 'day': '2021-01-01', 'kind': 'uncredited', 'law': '', 'files': ['a/s.md'], 'ranges': []},
                   {'commit': 'three', 'day': '2022-01-01', 'kind': 'uncredited', 'law': '', 'files': ['a/s.md'], 'ranges': []}]
        return c, records

    def test_independent_boundaries(self):
        c, records = self.fixture()
        rows = I.provision_rows(c, records)
        s = [r for r in rows if r['path'] == 'a/s.md']
        self.assertEqual([(r['from'], r['to'], r['commit']) for r in s],
                         [('2020-01-01', '2020-12-31', 'one'), ('2021-01-01', '2021-12-31', 'two'),
                          ('2022-01-01', '', 'three')])
        self.assertEqual(s[-1]['status'], 'repealed')
        self.assertEqual(len([r for r in rows if r['path'] == 'a/t.md']), 1)

    def test_correction_splits_only_its_range(self):
        c, records = self.fixture()
        records.append({'commit': 'fix', 'day': '2020-03-01', 'kind': 'correction', 'law': '',
                        'files': ['a/s.md'], 'ranges': [('a', '2020-03-01', '2020-04-30')]})
        rows = [r for r in I.provision_rows(c, records) if r['path'] == 'a/s.md']
        self.assertEqual([(r['from'], r['to'], r['commit']) for r in rows[:3]],
                         [('2020-01-01', '2020-02-29', 'one'), ('2020-03-01', '2020-04-30', 'fix'),
                          ('2020-05-01', '2020-12-31', 'one')])

    def test_missing_commit_is_not_invented(self):
        c, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, 'no published commit'):
            I.provision_rows(c, [])


if __name__ == '__main__':
    unittest.main()
