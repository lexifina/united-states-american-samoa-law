"""Tests for credits.py (CORPUS-STANDARD.md §5b). Run: python -X utf8 gitlaw_common/test_credits.py"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import append as A  # noqa: E402
import build as B  # noqa: E402
import credits as C  # noqa: E402

CORPUS = {
    'country': {'code': 'XX', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                'future_branch': 'future', 'publisher': {'name': 'Gazette', 'email': 'g@gazette.invalid'}},
    'sources': [{'name': 'Gazette', 'url': 'https://laws.example.gov/', 'retrieved': '2026-11-01'}],
    'laws': {'act-1-2010': {'label': 'Act 1 of 2010', 'kind': 'law', 'enacted': '2010-01-01', 'published': '2010-01-02'},
             'act-7-2015': {'label': 'Act 7 of 2015', 'kind': 'law', 'enacted': '2015-05-01', 'published': '2015-05-02',
                            'in_force': '2015-06-01', 'url': 'https://laws.example.gov/a7-2015'},
             'act-8-2015': {'label': 'Act 8 of 2015', 'kind': 'law', 'published': '2015-05-02'},  # no in_force
             'act-9-2020': {'label': 'Act 9 of 2020', 'kind': 'law', 'published': '2020-01-01', 'in_force': '2020-03-01'},
             'act-3-2018': {'label': 'Act 3 of 2018', 'kind': 'law', 'published': '2018-02-01', 'in_force': '2018-03-01'},
             'act-5-2014': {'label': 'Act 5 of 2014', 'kind': 'law', 'published': '2014-01-01', 'in_force': '2014-07-01'}},
    'acts': [],
}
PART = {'acts': [{
    'slug': 'fees-act', 'short': 'Fees Act', 'title': 'Fees Act 2010', 'url': 'https://laws.example.gov/fees',
    'first_law': 'act-1-2010', 'earlier_laws': [],
    'versions': [
        {'from': '2010-02-01', 'units': {'s-001': {'label': 's. 1', 'text': 'The fee is 10.\n'},
                                         's-002': {'label': 's. 2', 'text': 'Rule two.\n'}}, 'credits': {}},
        {'from': '2015-06-01', 'units': {'s-001': {'label': 's. 1', 'text': 'The fee is 20.\n'},
                                         's-002': {'label': 's. 2', 'text': 'Rule two.\n'}}, 'credits': {}},
        {'from': '2018-03-01', 'units': {'s-001': {'label': 's. 1', 'text': 'The fee is 30.\n'},
                                         's-002': {'label': 's. 2', 'text': 'Rule 2, amended.\n'}},
         'credits': {'s-002': ['act-3-2018']}},
    ]}]}
GOOD = {'path': 'fees-act/s-001.md', 'version_from': '2015-06-01', 'proposed_law': 'act-7-2015',
        'evidence': 'Section 1 substituted by Act No. 7 of 2015, s. 4, with effect from 1 June 2015.', 'evidence_url': 'https://laws.example.gov/fees#notes',
        'model': 'test-model', 'confidence': '0.9', 'checked': ''}


def folder_with(rows):
    d = Path(tempfile.mkdtemp())
    (d / 'corpus.json').write_text(json.dumps(CORPUS), encoding='utf-8')
    (d / 'corpus.d').mkdir()
    (d / 'corpus.d' / '20-fees.json').write_text(json.dumps(PART), encoding='utf-8')
    C.write_tsv(d / 'credits-proposed.tsv', rows)
    return d


class Check(unittest.TestCase):
    def verdict(self, **change):
        r = {**GOOD, **change}
        rows, _ = C.check(folder_with([r]), folder_with([r]) / 'credits-proposed.tsv')
        return rows[0]['checked']

    def test_good_row_passes(self):
        self.assertEqual(self.verdict(), 'yes')

    def test_unchanged_provision(self):
        self.assertIn('did not change', self.verdict(path='fees-act/s-002.md'))

    def test_already_credited(self):
        self.assertIn('already credited', self.verdict(path='fees-act/s-002.md', version_from='2018-03-01',
                                                       proposed_law='act-3-2018',
                                                       evidence='s. 2 amended by Act 3 of 2018 from 1 March 2018'))

    def test_first_version_has_first_law(self):
        self.assertIn('first_law', self.verdict(version_from='2010-02-01', proposed_law='act-1-2010'))

    def test_law_after_the_version(self):
        self.assertIn('not on or before', self.verdict(proposed_law='act-9-2020', evidence='s. 1 by Act 9 of 2020 on 1 June 2015'))

    def test_stated_in_force_day_must_match(self):
        self.assertIn('in force from 2014-07-01, not 2015-06-01',
                      self.verdict(proposed_law='act-5-2014', evidence='s. 1 substituted by Act 5 of 2014'))
        self.assertEqual(self.verdict(version_from='2018-03-01', proposed_law='act-3-2018',
                                      evidence='s. 1 substituted by Act 3 of 2018, commencing 1 March 2018'), 'yes')

    def test_unknown_law(self):
        self.assertIn('unknown law', self.verdict(proposed_law='act-99'))

    def test_evidence_must_name_the_provision_and_the_law(self):
        self.assertIn('name the provision', self.verdict(evidence='Amended by Act 7 of 2015 from 1 June 2015.'))
        self.assertIn('name the law', self.verdict(evidence='Section 1 was amended from 1 June 2015.'))

    def test_the_same_numbers_elsewhere_are_not_a_match(self):  # review of b191625: numbers alone matched
        self.assertIn('name the provision', self.verdict(
            evidence='Section 99 amended by Act 7 of 2015 from 1 June 2015; see note 1.'))
        self.assertIn('name the provision', self.verdict(evidence='Section 10 substituted by Act 7 of 2015 from 1 June 2015.'))
        self.assertIn('name the provision', self.verdict(evidence='Section 1A substituted by Act 7 of 2015 from 1 June 2015.'))
        self.assertIn('name the law', self.verdict(evidence='Section 1 substituted by Act 17 of 2015 from 1 June 2015.'))
        self.assertIn('name the law', self.verdict(evidence='Section 1 substituted by Act 7 of 2016 from 1 June 2015.'))
        self.assertEqual(self.verdict(evidence='s 1 subst. by Act No 7 of 2015 (in force 01/06/2015)'), 'yes')

    def test_a_commencement_day_is_required(self):  # review of b191625: commencement was optional
        # from the corpus's own data for the law only (re-review 3 of 2923c82: the evidence's wording cannot be trusted)
        self.assertEqual(self.verdict(evidence='Section 1 substituted by Act No. 7 of 2015.'), 'yes')
        self.assertIn('no commencement day', self.verdict(
            proposed_law='act-8-2015', evidence='Section 1 substituted by Act 8 of 2015, in force from 1 June 2015.'))

    def test_evidence_alone_never_establishes_commencement(self):  # re-review 3 of 2923c82, finding 1
        for ev in ('Section 1 substituted by Act 8 of 2015 (zverejnené 1. júna 2015; abgerufen am 01.06.2015).',
                   'Section 1 substituted by Act 8 of 2015 from 1 June 2015, the day it was published.',
                   'Section 1 substituted by Act 8 of 2015, not in force until a later order; signed 1 June 2015.',
                   'Section 1 substituted by Act 8 of 2015 (in force on a day to be appointed); 1 June 2015',
                   'Section 1 substituted by Act 8 of 2015, with effect from 1 June 2015.'):
            self.assertIn('no commencement day', self.verdict(proposed_law='act-8-2015', evidence=ev), ev)

    def with_law(self, law: dict, extra_part_law: dict | None = None, raw_corpus: str | None = None, **row):
        d = folder_with([{**GOOD, 'proposed_law': 'act-x', 'evidence': 'Section 1 substituted by Act X of 2015.', **row}])
        cj = json.loads((d / 'corpus.json').read_text(encoding='utf-8'))
        cj['laws']['act-x'] = {'label': 'Act X of 2015', 'kind': 'law', 'published': '2015-05-02', **law}
        (d / 'corpus.json').write_text(raw_corpus(cj) if raw_corpus else json.dumps(cj), encoding='utf-8')
        if extra_part_law is not None:
            (d / 'corpus.d' / '30-laws.json').write_text(json.dumps(
                {'acts': [], 'laws': {'act-x': {'label': 'Act X of 2015', 'kind': 'law', **extra_part_law}}}), encoding='utf-8')
        rows, _ = C.check(d, d / 'credits-proposed.tsv')
        return rows[0]['checked']

    def test_days_must_be_calendar_days(self):  # re-review 4 of 7d8ac2a, finding 1
        for bad in ('2017-02-29', '2020-02-30', '2017-04-31', '2017-13-01', '2017-04-01T00:00:00Z', '1900-02-29'):
            self.assertIn('not a calendar day', self.with_law({'in_force': bad}, version_from=bad), bad)
        self.assertEqual(self.with_law({'in_force': '2015-06-01'}), 'yes')
        self.assertIn('calendar day', C.check_row({}, {}, set(), {**GOOD, 'version_from': '2015-6-1'}))
        d = folder_with([GOOD])
        with self.assertRaises(B.CorpusError):
            C.emit(d, d / 'credits-proposed.tsv', date='2026-02-30')

    def test_re_review_5_holes_fail_closed(self):  # re-review 5 of 185bd76
        twice = lambda cj: json.dumps(cj)[:-1] + ', "laws": ' + json.dumps({'act-x': {'label': 'Act X of 2015', 'kind': 'law', 'published': '2015-05-02', 'in_force': '2015-06-01'}}) + '}'  # noqa: E731
        self.assertIn('twice', self.with_law({'in_force': '2015-07-01'}, raw_corpus=twice))
        for empty in (None, ''):
            self.assertIn('not a calendar day', self.with_law({'in_force': '2015-06-01', 'commenced': empty}), repr(empty))
            self.assertIn('not a calendar day', self.with_law({'in_force': '2015-06-01', 'published': empty}), repr(empty))
        self.assertIn('not a calendar day', self.with_law({'in_force': '2015-06-01', 'enacted': '2015-02-30'}))
        self.assertIn('not a calendar day', self.with_law({'in_force': '2015-06-01'}, extra_part_law={'published': '2015-13-01'}))
        d = folder_with([GOOD])
        for bad in ('', ' '):
            with self.assertRaises(B.CorpusError):
                C.emit(d, d / 'credits-proposed.tsv', date=bad)
        self.assertFalse(list((d / 'corpus.d').glob('95-*')))

    def test_any_duplicate_key_refuses_every_row(self):  # re-review 6 of b579062
        def with_part(text):
            d = folder_with([GOOD])
            (d / 'corpus.d' / '30-laws.json').write_text(text, encoding='utf-8')
            rows, _ = C.check(d, d / 'credits-proposed.tsv')
            return rows[0]['checked']
        for text in ('{"laws": {"act-7-2015": {"in_force": "2017-04-02"}}, "laws": {}}',
                     '{"laws": {"other": {}}, "laws": {"act-7-2015": {"in_force": "2015-07-01"}}, "laws": {"other": {}}}',
                     '{"laws": {"act-7-2015": {"in_force": "2015-07-01"}}, "\\u006caws": {}}',
                     '{"acts": [], "provenance": {"laws": 1, "laws": 2}}',
                     '{"acts": [], "provenance": [{"note": 1, "note": 2}]}'):
            self.assertIn('gives a key twice', with_part(text), text)
        self.assertEqual(with_part('{"acts": [], "provenance": [{"note": 1}, {"note": 2}]}'), 'yes')

    def test_an_ambiguous_commencement_fails_closed(self):  # re-review 4 of 7d8ac2a, finding 3
        self.assertIn('different commencement days', self.with_law({'in_force': '2015-06-01', 'commenced': '2015-06-02'}))
        self.assertIn('different commencement days', self.with_law({'in_force': '2015-06-02', 'commenced': '2015-06-01'}))
        self.assertIn('not a calendar day', self.with_law({'in_force': '2015-06-01', 'commenced': ['2015-06-01']}))
        for falsy in (False, [], {}):
            self.assertIn('not a calendar day', self.with_law({'in_force': falsy, 'commenced': '2015-06-01'}), falsy)
        dup = lambda cj: json.dumps(cj).replace('"in_force": "2015-06-01"', '"in_force": "2015-07-01", "in_force": "2015-06-01"')  # noqa: E731
        self.assertIn('gives a key twice', self.with_law({'in_force': '2015-06-01'}, raw_corpus=dup))
        self.assertIn('different commencement days', self.with_law({'in_force': '2015-06-01'}, extra_part_law={'in_force': '2015-07-01'}))
        self.assertEqual(self.with_law({'in_force': '2015-06-01', 'commenced': '2015-06-01'}), 'yes')

    def test_the_evidence_can_only_disqualify(self):  # review of 918f755, P1
        self.assertIn('commencement 2015-07-01, not 2015-06-01', self.verdict(
            evidence='Section 1 amended by Act 7 of 2015, published 1 June 2015; commences 1 July 2015.'))
        self.assertIn('commencement 2015-06-02, not 2015-06-01', self.verdict(
            evidence='Section 1 substituted by Act No. 7 of 2015 from 2 June 2015.'))
        self.assertEqual(self.verdict(evidence='Section 1 amended by Act 7 of 2015 (retrieved 1 June 2015).'), 'yes')

    def test_a_stated_commencement_must_agree_with_the_law(self):
        self.assertIn('commencement 2018-04-01, not 2018-03-01', self.verdict(
            version_from='2018-03-01', proposed_law='act-3-2018',
            evidence='s. 1 substituted by Act 3 of 2018 (published 1 March 2018), in force 1 April 2018'))

    def test_evidence_host(self):
        self.assertIn('host', self.verdict(evidence_url='https://blog.example.com/fees'))

    def test_confidence_and_model(self):
        self.assertIn('confidence', self.verdict(confidence='1.5'))
        self.assertIn('model', self.verdict(model=''))

    def test_duplicate_proposal(self):
        d = folder_with([GOOD, dict(GOOD)])
        rows, counts = C.check(d, d / 'credits-proposed.tsv')
        self.assertEqual([r['checked'] for r in rows][1][:2], 'no')
        self.assertEqual(counts, {'proposed': 2, 'checked': 1, 'rejected': 1})


class Emit(unittest.TestCase):
    def test_emit_writes_a_correction_part_the_builder_loads(self):
        d = folder_with([GOOD, {**GOOD, 'path': 'fees-act/s-002.md'}])  # the second is rejected (unchanged)
        out = C.emit(d, d / 'credits-proposed.tsv', date='2026-11-03')
        self.assertEqual([p.name for p in out], ['95-credits-2026-11-03-01-ai-use.json', '95-credits-2026-11-03-01-20-fees.json'])
        ai = json.loads(out[0].read_text(encoding='utf-8'))
        self.assertEqual(ai['acts'], [])
        self.assertIn('proposed 2 credits', ai['ai_use'][0])
        self.assertIn('test-model: 1 checked, 1 rejected', ai['ai_use'][0])
        part = json.loads(out[1].read_text(encoding='utf-8'))
        self.assertEqual(part['corrects'], '20-fees.json')
        for p in out:  # a review request each, never the sign-off itself
            self.assertTrue(p.with_suffix('.PUBLISH.pending').exists())
            self.assertFalse(p.with_suffix('.PUBLISH').exists())
        c, _ = B.load(d)
        act = c['acts'][0]
        v = act['versions'][1]
        self.assertEqual(v['credits'], {'s-001': ['act-7-2015']})
        self.assertEqual(v['units'], PART['acts'][0]['versions'][1]['units'])  # law text unchanged
        meta = A.correction_metadata(act, v)  # the appender's own validation of correction metadata
        self.assertTrue(meta['metadata_only'])
        self.assertIn('Act 7 of 2015', meta['reason'])
        self.assertIn('https://laws.example.gov/fees#notes', meta['reason'])
        self.assertNotIn('\n', meta['reason'])
        self.assertEqual(act['versions'][2]['credits'], {'s-002': ['act-3-2018']})  # other versions untouched
        self.assertNotIn('correction', act['versions'][2])

    def test_nothing_checked_is_still_disclosed(self):  # review of b191625: all-rejected runs left no record
        d = folder_with([{**GOOD, 'proposed_law': 'act-99'}])
        out = C.emit(d, d / 'credits-proposed.tsv', date='2026-11-03')
        self.assertEqual([p.name for p in out], ['95-credits-2026-11-03-01-ai-use.json'])
        text = json.loads(out[0].read_text(encoding='utf-8'))['ai_use'][0]
        self.assertIn('0 passed', text)
        self.assertIn('1 were rejected', text)
        c, _ = B.load(d)
        self.assertEqual(c['acts'][0]['versions'][1]['credits'], {})

    def test_no_proposals_writes_nothing(self):
        d = folder_with([])
        self.assertEqual(C.emit(d, d / 'credits-proposed.tsv'), [])
        self.assertFalse(list((d / 'corpus.d').glob('95-*')))

    def test_a_second_emission_never_replaces_the_first(self):  # review of b191625: emit overwrote its part
        d = folder_with([GOOD])
        first = C.emit(d, d / 'credits-proposed.tsv', date='2026-11-03')
        before = {p.name: p.read_bytes() for p in first}
        C.write_tsv(d / 'credits-proposed.tsv', [{**GOOD, 'version_from': '2018-03-01', 'proposed_law': 'act-3-2018',
                                                  'evidence': 's. 1 substituted by Act 3 of 2018 from 1 March 2018'}])
        second = C.emit(d, d / 'credits-proposed.tsv', date='2026-11-03')
        for name, data in before.items():
            self.assertEqual((d / 'corpus.d' / name).read_bytes(), data)
        self.assertEqual([p.name for p in second], ['95-credits-2026-11-03-02-ai-use.json', '95-credits-2026-11-03-02-20-fees.json'])
        self.assertEqual(json.loads(second[1].read_text(encoding='utf-8'))['corrects'], '95-credits-2026-11-03-01-20-fees.json')
        c, _ = B.load(d)
        vs = c['acts'][0]['versions']
        self.assertEqual(vs[1]['credits'], {'s-001': ['act-7-2015']})  # the first emission's credit carries forward
        self.assertEqual(vs[2]['credits'], {'s-001': ['act-3-2018'], 's-002': ['act-3-2018']})

    def refused_and_untouched(self, d, **kw):
        before = sorted(p.name for p in (d / 'corpus.d').iterdir())
        with self.assertRaises(B.CorpusError) as e:
            C.emit(d, d / 'credits-proposed.tsv', **kw)
        self.assertEqual(sorted(p.name for p in (d / 'corpus.d').iterdir()), before)  # nothing written
        return str(e.exception)

    def test_a_source_part_that_sorts_later_is_refused_before_writing(self):  # review of 918f755, P2
        for name in ('99-sample.json', 'zz-sample.json'):
            d = folder_with([GOOD])
            (d / 'corpus.d' / '20-fees.json').rename(d / 'corpus.d' / name)
            self.assertIn('--prefix', self.refused_and_untouched(d, date='2026-11-04'))
        out = C.emit(d, d / 'credits-proposed.tsv', prefix='zzz', date='2026-11-04')  # a later prefix works
        self.assertEqual(json.loads(out[1].read_text(encoding='utf-8'))['corrects'], 'zz-sample.json')
        self.assertEqual(B.load(d)[0]['acts'][0]['versions'][1]['credits'], {'s-001': ['act-7-2015']})

    def test_a_backdated_emission_is_refused_before_writing(self):  # review of 918f755, P2
        d = folder_with([GOOD])
        C.emit(d, d / 'credits-proposed.tsv', date='2026-11-05')
        C.write_tsv(d / 'credits-proposed.tsv', [{**GOOD, 'version_from': '2018-03-01', 'proposed_law': 'act-3-2018',
                                                  'evidence': 's. 1 substituted by Act 3 of 2018 from 1 March 2018'}])
        self.assertIn('--date', self.refused_and_untouched(d, date='2026-11-04'))

    def test_owners_with_one_stem_get_distinct_parts(self):  # review of 918f755, P2: mixed current owners
        d = folder_with([GOOD])
        other = copy.deepcopy(PART['acts'][0])
        other.update(slug='other-act', short='Other Act', title='Other Act 2010')
        part = json.loads((d / 'corpus.d' / '20-fees.json').read_text(encoding='utf-8'))
        part['acts'].append(other)
        (d / 'corpus.d' / '20-fees.json').write_text(json.dumps(part), encoding='utf-8')
        C.emit(d, d / 'credits-proposed.tsv', date='2026-11-04')  # fees-act now owned by the correction part
        C.write_tsv(d / 'credits-proposed.tsv', [
            {**GOOD, 'version_from': '2018-03-01', 'proposed_law': 'act-3-2018',
             'evidence': 's. 1 substituted by Act 3 of 2018 from 1 March 2018'},
            {**GOOD, 'path': 'other-act/s-001.md'}])
        out = C.emit(d, d / 'credits-proposed.tsv', date='2026-11-04')
        self.assertEqual(len(out), 3)
        self.assertEqual(sorted(json.loads(p.read_text(encoding='utf-8'))['corrects'] for p in out[1:]),
                         ['20-fees.json', '95-credits-2026-11-04-01-20-fees.json'])
        acts = {a['slug']: a for a in B.load(d)[0]['acts']}
        self.assertEqual(acts['fees-act']['versions'][1]['credits'], {'s-001': ['act-7-2015']})
        self.assertEqual(acts['fees-act']['versions'][2]['credits'], {'s-001': ['act-3-2018'], 's-002': ['act-3-2018']})
        self.assertEqual(acts['other-act']['versions'][1]['credits'], {'s-001': ['act-7-2015']})

    def test_unicode_normalisation_variants_are_refused(self):  # re-review 4 of 7d8ac2a, finding 2
        import unicodedata
        d = folder_with([GOOD, {**GOOD, 'path': 'other-act/s-001.md'}])
        nfc = '20-École.json'
        nfd = unicodedata.normalize('NFD', nfc)
        other = copy.deepcopy(PART)
        other['acts'][0].update(slug='other-act', short='Other Act', title='Other Act 2010')
        (d / 'corpus.d' / '20-fees.json').rename(d / 'corpus.d' / nfc)
        (d / 'corpus.d' / nfd).write_text(json.dumps(other), encoding='utf-8')
        if len(list((d / 'corpus.d').glob('*.json'))) < 2:
            self.skipTest('this file system stores the two names as one')
        self.assertIn('Unicode normalisation', self.refused_and_untouched(d, date='2026-11-04'))

    def test_check_write_fills_the_column(self):
        d = folder_with([GOOD])
        C.check(d, d / 'credits-proposed.tsv', write=True)
        self.assertEqual(C.read_tsv(d / 'credits-proposed.tsv')[0]['checked'], 'yes')


if __name__ == '__main__':
    unittest.main()
