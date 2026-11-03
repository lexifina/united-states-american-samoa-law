"""Correction-part selection against unchanged SIBOM delivery/published fixtures.

    python -X utf8 gitlaw_common/test_correction_parts.py
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from build import CorpusError, load, validate

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'correction-parts'
ORIGINALS = ('30-ordenanzas-01.json', '80-sibom-c-recovery.json')
SHA256 = {
    '30-ordenanzas-01.json': '1409aed13b28d430b0950524b4b6db06f2b3a58f5f919ccec20f303debd4ff57',
    '80-sibom-c-recovery.json': 'd391bfac3b714a39ff45c8cc239025cb9a257cefff714a677cacfd159114a36d',
    'withdrawals.json': 'd831153c38bcf168a1e7ad1690b7904e1c6122d9891d50f40cd7f7075be2604a',
}


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


class CorrectionParts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / 'corpus.d').mkdir()
        for name in ORIGINALS:
            shutil.copyfile(FIXTURES / name, self.folder / 'corpus.d' / name)
        self.originals = [act for name in ORIGINALS for act in read(name)['acts']]
        self.withdrawals = read('withdrawals.json')['acts']
        self.owner = {act['slug']: name for name in ORIGINALS for act in read(name)['acts']}
        self.env = patch.dict(os.environ, {'GITLAW_VERIFIED_PARTS_ONLY': '0'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def part(self, name, value):
        path = self.folder / 'corpus.d' / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def correction(self, act=None, target=None, name='zz-correction.json'):
        act = copy.deepcopy(act if act is not None else self.withdrawals[0])
        return self.part(name, {'corrects': target if target is not None else self.owner[act['slug']], 'acts': [act]})

    def test_fixture_bytes_match_unchanged_published_parts_and_delivery(self):
        for name, expected in SHA256.items():
            self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), expected)

    def test_pilar_70_withdrawals_and_43_untouched_acts(self):
        for i, name in enumerate(ORIGINALS):
            acts = [a for a in self.withdrawals if self.owner[a['slug']] == name]
            self.part(f'zz-{i}-withdrawals.json', {'corrects': name, 'acts': acts})
        result, raw = load(self.folder)
        self.assertEqual(validate(result), [])
        self.assertEqual(len(result['acts']), 113)
        self.assertEqual(len(self.withdrawals), 70)
        expected = {a['slug']: a for a in self.withdrawals}
        self.assertEqual([a['slug'] for a in result['acts']], [a['slug'] for a in self.originals])
        for old, actual in zip(self.originals, result['acts']):
            # The independent oracle is either an unchanged published act or the supplied delivery act.
            self.assertEqual(actual, expected.get(old['slug'], old))
            self.assertEqual([v['from'] for v in actual['versions']], [v['from'] for v in old['versions']])
            if actual['slug'] in expected:
                self.assertIn('not repeal', actual['corpus_withdrawal']['scope'])
                for version in actual['versions']:
                    self.assertEqual(version['units'], {})
                    self.assertEqual(version['credits'], {})
        self.assertEqual(raw, b''.join(b'\n' + p.name.encode() + b'\n' + p.read_bytes()
                                      for p in sorted((self.folder / 'corpus.d').glob('*.json'))))

    def test_one_identity_correction_keeps_historical_slug_and_text(self):
        supplied = self.withdrawals[0]
        old = next(a for a in self.originals if a['slug'] == supplied['slug'])
        correction = copy.deepcopy(old)
        # Use the source identity/title already recorded by sibom-fix; no new law text.
        correction['short'] = supplied['short']
        correction['title'] = supplied['title']
        self.assertEqual(old['slug'], 'ordenanza-392-2019')
        self.assertEqual(supplied['corpus_withdrawal']['source_identity'], 'ordenanza-392-2018')
        self.correction(correction)
        result, _ = load(self.folder)
        self.assertEqual(validate(result), [])
        actual = next(a for a in result['acts'] if a['slug'] == old['slug'])
        self.assertEqual(actual, correction)
        self.assertEqual(actual['versions'], old['versions'])

    def test_undeclared_duplicate_remains_validation_error(self):
        self.part('zz-duplicate.json', {'acts': [self.withdrawals[0]]})
        self.assertTrue(any('must be unique' in e for e in validate(load(self.folder)[0])))

    def test_target_without_slug_fails(self):
        wrong = next(name for name in ORIGINALS if name != self.owner[self.withdrawals[0]['slug']])
        self.correction(target=wrong)
        with self.assertRaisesRegex(CorpusError, 'must occur exactly once'):
            load(self.folder)

    def test_invalid_missing_self_and_forward_targets_fail(self):
        for target in (None, '', [], {}, 12, 'missing.json', 'corpus.json', 'zz-correction.json',
                       '../30-ordenanzas-01.json', 'zzz-later.json'):
            with self.subTest(target=target):
                self.part('zz-correction.json', {'corrects': target, 'acts': [self.withdrawals[0]]})
                self.part('zzz-later.json', {'acts': []})
                with self.assertRaisesRegex(CorpusError, 'earlier loaded part'):
                    load(self.folder)

    def test_duplicate_inside_correction_fails(self):
        act = self.withdrawals[0]
        self.part('zz-correction.json', {'corrects': self.owner[act['slug']], 'acts': [act, act]})
        with self.assertRaisesRegex(CorpusError, 'must occur exactly once'):
            load(self.folder)

    def test_correction_cannot_hide_preexisting_duplicate(self):
        self.part('90-duplicate.json', {'acts': [self.withdrawals[0]]})
        self.correction()
        with self.assertRaisesRegex(CorpusError, 'must occur exactly once'):
            load(self.folder)

    def test_duplicate_after_correction_still_fails_validation(self):
        self.correction()
        self.part('zzz-duplicate.json', {'acts': [self.withdrawals[0]]})
        self.assertTrue(any('must be unique' in e for e in validate(load(self.folder)[0])))

    def test_latest_correction_must_be_named_for_a_chain(self):
        self.correction(name='zz-first.json')
        self.correction(name='zz-second.json')
        with self.assertRaisesRegex(CorpusError, 'still belong to that part'):
            load(self.folder)
        self.correction(target='zz-first.json', name='zz-second.json')
        self.assertEqual(validate(load(self.folder)[0]), [])

    def test_main_corpus_duplicate_cannot_be_hidden(self):
        (self.folder / 'corpus.json').write_text(json.dumps({'acts': [self.withdrawals[0]]}), encoding='utf-8')
        self.correction()
        with self.assertRaisesRegex(CorpusError, 'must occur exactly once'):
            load(self.folder)

    def test_verified_filter_excludes_correction_and_requires_target(self):
        self.correction()
        # Model marker presence without writing any publication marker.
        exists = Path.exists
        verified = {Path(n).with_suffix('.PUBLISH').name for n in ORIGINALS}

        def marker_exists(path):
            return path.name in verified if path.suffix == '.PUBLISH' else exists(path)

        with patch.dict(os.environ, {'GITLAW_VERIFIED_PARTS_ONLY': '1'}), patch.object(Path, 'exists', marker_exists):
            self.assertEqual(load(self.folder)[0]['acts'], self.originals)
            verified.add('zz-correction.PUBLISH')
            self.assertEqual(validate(load(self.folder)[0]), [])
            verified.remove(Path(self.owner[self.withdrawals[0]['slug']]).with_suffix('.PUBLISH').name)
            with self.assertRaisesRegex(CorpusError, 'earlier loaded part'):
                load(self.folder)

    def test_replacement_delta_versions_expand_after_selection(self):
        old = copy.deepcopy(self.originals[0])
        version = copy.deepcopy(old['versions'][0])
        version.pop('units')
        version['same_day'] = True
        version['changes'] = {}
        old['versions'].append(version)
        self.correction(old)
        result, _ = load(self.folder)
        actual = next(a for a in result['acts'] if a['slug'] == old['slug'])
        self.assertEqual(actual['versions'][-1]['units'], self.originals[0]['versions'][0]['units'])
        self.assertEqual(validate(result), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
