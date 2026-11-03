"""Regression checks against pinned delivery metadata and unchanged published rows."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import append as A

F = Path(__file__).resolve().parent / 'fixtures' / 'correction-gaps'
IDENTITY = ('Lexifina', 'world-law@lexifina.com')
FORMULA = '[Formula image on page 15 of the official PDF not reproduced]'
FINANCING = 'garissa-county-financing-of-cities-and-urban-areas-act-2026'


def read(name):
    return json.loads((F / name).read_text(encoding='utf-8'))


class CorrectionGaps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        A.git(self.repo, 'init', '-q', '-b', 'main')

    def fixture(self, name):
        data = read(name + '.json')
        writer = A.B.Writer(self.repo)
        rows = sorted((r['day'], s, r) for s, rs in data['published_rows'].items() for r in reversed(rs))
        previous = {}
        for i, (day, slug, row) in enumerate(rows):
            files = dict.fromkeys(set(previous.get(slug, {})) - set(row['files'])) | row['files']
            writer.commit('main', IDENTITY, IDENTITY, f'{1600000000 + i} +0000',
                          f'Published row {row["commit"]}\n\nIn-force: {day}\n', files)
            previous[slug] = row['files']
        writer.finish()
        new = A.git(self.repo, 'rev-list', '--reverse', 'main').split()
        self.commit_map = {row['commit']: h for (_, _, row), h in zip(rows, new)}
        self.c = {'acts': copy.deepcopy(data['acts']), 'laws': {},
                  'country': {'code': 'XT', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                              'publisher': {'name': 'Test Gazette', 'email': 'gazette@testland.invalid'}}}
        for act in self.c['acts']:
            meta = act.get('editorial_date_correction')
            if meta:
                meta['supersedes'] = self.commit_map[meta['supersedes']]
        self.data = data
        return self.c

    def plan(self):
        head = A.git(self.repo, 'rev-parse', 'main').strip()
        state = A.published_state(self.repo, self.c, verify=False)
        return A.plan_corrections(self.repo, self.c, head, state, A.DEFAULT_REASON)

    def emit(self, plans):
        head = A.git(self.repo, 'rev-parse', 'main').strip()
        writer = A.Appender(self.repo, head, 1700000000, '+0000')
        for x in plans:
            msg, trailers = A.correction_message(self.c, x)
            A.B.check_trailers(trailers)
            writer.commit(IDENTITY, '1700000000 +0000', IDENTITY,
                          '\n'.join(msg).rstrip() + '\n\n' + '\n'.join(trailers) + '\n', x['files'])
        writer.finish()

    def test_pinned_fixture_bytes(self):
        for name, record in read('manifest.json').items():
            self.assertEqual(hashlib.sha256((F / name).read_bytes()).hexdigest(), record['sha256'])

    def test_micronesia_27_in_27_out_and_metadata_idempotent(self):
        self.fixture('micronesia-law')
        plans = self.plan()
        supplied = {a['slug']: a for a in self.data['acts']}
        self.assertEqual(len(supplied), 27)
        self.assertEqual({x['act']['slug'] for x in plans}, set(supplied))
        metadata = [x for x in plans if x.get('metadata_changed')]
        self.assertEqual(len(metadata), 12)
        for x in plans:
            original = supplied[x['act']['slug']]['editorial_date_correction']
            _, trailers = A.correction_message(self.c, x)
            self.assertIn('In-force-basis: ' + original['in_force_basis'], trailers)
            self.assertIn('Reason: ' + original['reason'], trailers)
            self.assertIn('Supersedes: ' + self.commit_map[original['supersedes']], trailers)
        for x in metadata:
            s = x['act']['slug']
            _, trailers = A.correction_message(self.c, x)
            self.assertIn('Text-as-of: 2026-11-03', trailers)
            self.assertEqual(x['bad'], [])
            # Independent oracle: immutable published row, not new corpus rendering.
            self.assertEqual(x['files'], self.data['published_rows'][s][0]['files'])
            self.assertTrue(x['files'])
            for path in x['files']:
                self.assertIn('Files: ' + path, trailers)
        self.emit(plans)
        self.assertEqual(self.plan(), [])
        for fix in A.corrections_on(self.repo):
            if next(iter(fix['ranges'])) in {x['act']['slug'] for x in metadata}:
                self.assertEqual(A.git(self.repo, 'diff-tree', '--no-commit-id', '-r', '--name-only', fix['commit']).strip(), '')

    def test_garissa_gate_dates_and_genuine_later_amendment(self):
        self.fixture('kenya-garissa-law')
        plans = self.plan()
        financing = [x for x in plans if x['act']['slug'] == FINANCING]
        self.assertEqual([(x['range_from'], x['to']) for x in financing],
                         [('2026-07-24', '2026-11-02'), ('2026-11-03', None)])
        for x in financing:
            self.assertEqual(x['version']['from'], '2026-07-24')
            self.assertIn('In-force: 2026-07-24', A.correction_message(self.c, x)[1])
        self.emit(plans)
        self.assertEqual(self.plan(), [])
        rd = A.Reader(self.repo, list(self.data['published_rows']))
        try:
            for case in self.data['reader_boundaries']:
                s, day = case['act'], case['day']
                supplied = next(a for a in self.data['acts'] if a['slug'] == s)
                have = rd.files(s, day)
                if day < supplied['versions'][0]['from']:
                    self.assertIsNone(have, (s, day))
                    continue
                original = self.data['published_rows'][s][0]['files']
                texts = {p: rd.cat.read(oid).decode('utf-8') for p, oid in have.items()}
                if s == FINANCING:
                    self.assertTrue(all(FORMULA in t for t in texts.values()), day)
                    texts = {p: t.replace('\n' + FORMULA + '\n\n', '', 1) for p, t in texts.items()}
                self.assertEqual(texts, original, (s, day))
        finally:
            rd.close()
        path = next(iter(self.data['published_rows'][FINANCING][0]['files']))
        # Synthetic future event tests clipping only; no invented text is asserted as law.
        head = A.git(self.repo, 'rev-parse', 'main').strip()
        w = A.Appender(self.repo, head, 1700000100, '+0000')
        w.commit(IDENTITY, '1700000101 +0000', IDENTITY, 'Test amendment\n\nIn-force: 2027-01-01\n',
                 {path: 'SYNTHETIC AMENDMENT TEST\n'})
        w.finish()
        rd = A.Reader(self.repo, [FINANCING])
        try:
            self.assertIn(FORMULA, rd.cat.read(rd.files(FINANCING, '2026-12-31')[path]).decode())
            self.assertEqual(rd.cat.read(rd.files(FINANCING, '2027-01-01')[path]), b'SYNTHETIC AMENDMENT TEST\n')
        finally:
            rd.close()

    def test_explicit_capture_metadata_and_changed_assertion(self):
        self.fixture('micronesia-law')
        act = next(a for a in self.c['acts'] if a['editorial_date_correction']['metadata_only'])
        self.c['acts'] = [act]
        act['correction'] = {'text_as_of': '2026-11-02', 'reason': '  Explicit provenance correction  '}
        plans = self.plan()
        self.assertEqual(len(plans), 1)
        self.assertIn('Text-as-of: 2026-11-02', A.correction_message(self.c, plans[0])[1])
        self.assertIn('Reason: Explicit provenance correction', A.correction_message(self.c, plans[0])[1])
        self.emit(plans)
        self.assertEqual(self.plan(), [])
        act['correction']['reason'] = 'Revised provenance correction'
        self.assertEqual(len(self.plan()), 1)

    def test_checker_detects_stale_row_even_when_tip_is_correct(self):
        self.fixture('kenya-garissa-law')
        plans = self.plan()
        # Reproduce the old output: one open correction from commencement, whose
        # physical tip is correct but which the historical row clips on November 3.
        plans = [x for x in plans if not (x['act']['slug'] == FINANCING and x['range_from'] == '2026-11-03')]
        for x in plans:
            if x['act']['slug'] == FINANCING:
                x['to'] = None
        self.emit(plans)
        result = A.check_corrected(self.repo, self.c, '2026-11-03')
        self.assertEqual(result['tip_mismatches'], 0)
        self.assertGreater(result['mismatches'], 0)
        self.assertTrue(any(FINANCING + ' on 2026-11-03' in line for line in result['details']))

    def test_metadata_only_does_not_imply_unknown_commencement(self):
        act = {'slug': 'sample', 'correction': {'metadata_only': True, 'reason': 'Source corrected'}}
        meta = A.correction_metadata(act, {'from': '2020-01-01'})
        self.assertNotIn('text_as_of', meta)

    def test_supersedes_must_belong_to_act(self):
        self.fixture('micronesia-law')
        self.c['acts'][0]['editorial_date_correction']['supersedes'] = '0' * 40
        with self.assertRaisesRegex(A.B.CorpusError, 'published history'):
            self.plan()

    def test_invalid_trailer_metadata_rejected(self):
        for values in ({'reason': 'one\nReason: two'}, {'text_as_of': 'yesterday', 'in_force_basis': 'No date'},
                       {'text_as_of': '2026-11-03'}, {'metadata_only': 'yes'}):
            with self.subTest(values=values), self.assertRaises(A.B.CorpusError):
                A.correction_metadata({'slug': 'sample', 'correction': values}, {'from': '2026-11-03'})

    def test_withdrawal_reason_uses_supplied_explanation(self):
        withdrawal = json.loads((F.parent / 'correction-parts' / 'withdrawals.json').read_text(encoding='utf-8'))['acts'][0]
        meta = A.correction_metadata(withdrawal, withdrawal['versions'][0])
        self.assertEqual(meta['reason'], 'corpus withdrawal, not legislative repeal: ' + withdrawal['corpus_withdrawal']['reason'])
        withdrawal['correction'] = {'reason': 'corpus withdrawal, not legislative repeal: incomplete source record'}
        self.assertEqual(A.correction_metadata(withdrawal, withdrawal['versions'][0])['reason'], withdrawal['correction']['reason'])
        originals = [a for name in ('30-ordenanzas-01.json', '80-sibom-c-recovery.json')
                     for a in json.loads((F.parent / 'correction-parts' / name).read_text(encoding='utf-8'))['acts']]
        old = next(a for a in originals if a['slug'] == withdrawal['slug'])
        version = old['versions'][0]
        w = A.B.Writer(self.repo)
        w.commit('main', IDENTITY, IDENTITY, '1700000000 +0000', 'Published SIBOM fixture\n\nIn-force: ' + version['from'],
                 {f'{old["slug"]}/{k}.md': u['text'] for k, u in version['units'].items()})
        w.finish()
        self.c = {'acts': [withdrawal], 'laws': {}}
        plans = self.plan()
        self.assertEqual(len(plans), 1)
        self.assertIn('Reason: ' + withdrawal['correction']['reason'], A.correction_message(self.c, plans[0])[1])
        self.assertTrue(all(t is None for t in plans[0]['files'].values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
