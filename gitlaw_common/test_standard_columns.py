import csv
import io
import unittest
import build as B
import corpus_tables as T


class ColumnsTest(unittest.TestCase):
    def test_additional_columns(self):
        c = {'country': {'code': 'XX'}, '_docs_date': '2026-11-03',
             'laws': {'x': {'label': 'Decree X', 'kind': 'decree', 'enacted': '2020-01-01'}},
             'acts': [{'slug': 'a', 'title': 'Act A', 'short': 'A', 'versions': [
                 {'from': '2020-01-01', 'text_as_of': '2020-01-01', 'units': {'s': {'text': 'A\n', 'label': 'S'}}},
                 {'from': '2021-01-01', 'units': {}}]}]}
        tables = B.tables(c, [])
        laws = list(csv.DictReader(io.StringIO(tables['data/laws.csv'])))
        self.assertEqual((laws[0]['kind'], laws[0]['law_kind']), ('law', 'decree'))
        versions = T.versions_document(c, '2026-11-03')['acts'][0]['versions']
        self.assertEqual((versions[0]['to'], versions[0]['status'], versions[0]['text_as_of']),
                         ('2020-12-31', 'replaced', '2020-01-01'))
        self.assertEqual(versions[1]['status'], 'repealed')

    def test_old_ledger_kinds(self):
        self.assertEqual(T.ledger_kind({'acts': []}, {'kind': 'unexplained'}), 'uncredited')
        self.assertEqual(T.ledger_kind({'acts': []}, {'kind': 'start', 'law': None}), 'baseline')
        self.assertEqual(T.ledger_kind({'acts': []}, {'kind': 'start', 'law': 'x'}), 'law')


if __name__ == '__main__':
    unittest.main()
