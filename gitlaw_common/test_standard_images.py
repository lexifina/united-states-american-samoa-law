import base64
import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
import build as B
import append as A
import check as K
import corpus_images as M
import corpus_tables as T

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4V8AAAAASUVORK5CYII=')
DIGEST = hashlib.sha256(PNG).hexdigest()


def fixture():
    version = {'from': '2020-01-01', 'source_url': 'https://official.invalid/law', 'source_images': 1,
               'units': {'schedule': {'label': 'Schedule', 'text': '# Schedule\n![Table 1](assets/' + DIGEST + '.png)\n'}},
               'images': [{'sha256': DIGEST, 'file': 'official.png', 'caption': 'Table 1',
                           'source_url': 'https://official.invalid/table.png', 'media_type': 'image/png'}]}
    return {'country': {'code': 'XX', 'name': 'Testland', 'slug': 'testland', 'lang': 'en', 'tz': 'UTC',
                        'publisher': {'name': 'Official publisher', 'email': 'source@example.invalid'}},
            'laws': {}, 'acts': [{'slug': 'a', 'short': 'A', 'title': 'Fixture A',
                                   'url': 'https://official.invalid/law', 'versions': [version]}]}


class ImagesTest(unittest.TestCase):
    def test_image_counts_do_not_assert_whole_text_completeness(self):
        c = fixture()
        row = T.acts_document(c, '2026-11-03')['acts'][0]
        self.assertTrue(row['images_complete'])
        self.assertFalse(row['complete'])
        c['acts'][0]['complete'] = True
        self.assertTrue(T.acts_document(c, '2026-11-03')['acts'][0]['complete'])
        import append_gate as G
        self.assertIn('image_errors', G.FAIL_KEYS)

    def test_missing_inventory_and_silent_drop_fail(self):
        act = fixture()['acts'][0]
        v = copy.deepcopy(act['versions'][0])
        del v['source_images']
        with self.assertRaisesRegex(ValueError, 'inventory'):
            M.require(act, v, required=True)
        v['source_images'] = 2
        with self.assertRaisesRegex(ValueError, 'source images 2'):
            M.require(act, v)

    def test_unsurveyed_legacy_version_warns_even_on_a_new_correction(self):
        c = fixture()
        act, version = c['acts'][0], c['acts'][0]['versions'][0]
        del version['source_images']
        with self.assertWarnsRegex(UserWarning, 'not surveyed'):
            M.require(act, version)
        records = [{'day': version['from'], 'files': ['a/schedule.md'], 'standard': '1'}]
        check = M.check(c, records)
        self.assertEqual(check['errors'], [])
        self.assertIn('not surveyed', check['warnings'][0])
        self.assertIsNone(M.counts(version)['source'])
        self.assertFalse(T.acts_document(c, '2026-11-03')['acts'][0]['images_complete'])
        c['country']['image_inventory_required'] = True
        self.assertTrue(M.check(c, records)['errors'])
        with self.assertRaisesRegex(B.CorpusError, 'inventory'):
            B.start_message(c, {'act': act, 'version': version})

    def test_new_corpus_without_survey_fails_before_creating_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = fixture()
            version = c['acts'][0]['versions'][0]
            del version['source_images']
            version['images'] = []
            version['units']['schedule']['text'] = '# Schedule\n'
            (root / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            with self.assertRaisesRegex(B.CorpusError, 'inventory'):
                B.build(root, root / 'new-repo', '2026-11-03')
            self.assertFalse((root / 'new-repo/.git').exists())

    def test_invalid_survey_is_not_treated_as_missing(self):
        act = fixture()['acts'][0]
        for count in (None, -1, True, '1'):
            with self.subTest(count=count):
                version = {**act['versions'][0], 'source_images': count}
                with self.assertRaisesRegex(ValueError, 'invalid'):
                    M.require(act, version)

    def test_normative_omission_counts_but_is_incomplete(self):
        c = fixture()
        act, v = c['acts'][0], c['acts'][0]['versions'][0]
        v['images'] = []
        v['units']['schedule']['text'] = '[Image omitted: official PDF p. 12; tariff table; reason: not extractable]\n'
        v['images_omitted'] = [{'source_ref': 'official PDF p. 12', 'description': 'tariff table', 'reason': 'not extractable'}]
        M.require(act, v)
        row = T.acts_document(c, '2026-11-03')['acts'][0]
        self.assertEqual((row['images'], row['images_omitted'], row['complete']), (0, 1, False))
        v['units']['schedule']['text'] = '[Image omitted: table missing]\n'
        with self.assertRaises(ValueError):
            M.require(act, v)

    def test_new_history_errors_old_history_warns(self):
        c = fixture()
        c['acts'][0]['versions'][0]['source_images'] = 2
        records = [{'day': '2020-01-01', 'files': ['a/schedule.md'], 'standard': ''}]
        self.assertTrue(M.check(c, records)['warnings'])
        self.assertFalse(M.check(c, records)['errors'])
        records[0]['standard'] = '1'
        self.assertTrue(M.check(c, records)['errors'])

    def test_end_to_end_uses_exact_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, repo = root / 'source', root / 'repo'
            source.mkdir()
            c = fixture()
            (source / 'official.png').write_bytes(PNG)
            (source / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            try:
                B.build(source, repo, '2026-11-03')
                self.assertEqual((repo / 'a/assets' / (DIGEST + '.png')).read_bytes(), PNG)
                self.assertIn('**/assets/* binary', (repo / '.gitattributes').read_text())
                assets = list(csv.DictReader(io.StringIO((repo / 'data/assets.tsv').read_text()), delimiter='\t'))
                self.assertEqual(len(assets), 1)
                self.assertEqual(int(assets[0]['bytes']), len(PNG))
                source_text = c['acts'][0]['versions'][0]['units']['schedule']['text']
                self.assertEqual((repo / 'a/schedule.md').read_text(), source_text)
                self.assertEqual(K.check(repo, source / 'corpus.json')['image_errors'], 0)
                wrong = fixture()
                wrong['acts'][0]['versions'][0]['images'][0]['source_url'] = 'https://another.invalid/image.png'
                with self.assertRaisesRegex(ValueError, 'same official source'):
                    M.load(wrong, source)
                wrong = fixture()
                wrong['acts'][0]['versions'][0]['images'][0]['sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'sha256 differs'):
                    M.load(wrong, source)
                from unittest.mock import patch
                with patch.object(M, 'LIMIT', len(PNG) - 1), self.assertRaisesRegex(ValueError, 'over 25 MB'):
                    M.load(fixture(), source)
            finally:
                if repo.exists():
                    for p in repo.rglob('*'):
                        p.chmod(0o700)

    def test_restoration_is_a_correction_and_preserves_prior_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, repo = root / 'source', root / 'repo'
            source.mkdir()
            original = fixture()
            old = original['acts'][0]['versions'][0]
            old.update(source_images=0, images=[])
            old['units']['schedule']['text'] = '# Schedule\n'
            input_file = source / 'corpus.json'
            input_file.write_text(json.dumps(original), encoding='utf-8')
            try:
                B.build(source, repo, '2026-11-03')
                head = B.git(repo, 'rev-parse', 'main').strip()
                old_tags = B.git(repo, 'show-ref', '--tags')
                (source / 'official.png').write_bytes(PNG)
                input_file.write_text(json.dumps(fixture()), encoding='utf-8')
                result = A.append(source, repo, '2026-11-03', corrections=True)
                self.assertEqual(result['corrections'], 1)
                self.assertEqual(B.git(repo, 'show-ref', '--tags'), old_tags)
                self.assertEqual(B.git(repo, 'show', head + ':a/schedule.md'), '# Schedule\n')
                correction = B.git(repo, 'log', '-1', '--format=%B', '--grep=^Kind: correction')
                self.assertIn('Reason: image restored', correction)
                self.assertIn('Corrects: a 2020-01-01..', correction)
                self.assertEqual((repo / 'a/assets' / (DIGEST + '.png')).read_bytes(), PNG)
                self.assertEqual(K.check(repo, input_file)['image_errors'], 0)
                self.assertEqual(A.check_corrected(repo, B.load(source)[0], '2026-11-03')['mismatches'], 0)
            finally:
                if repo.exists():
                    for p in repo.rglob('*'):
                        p.chmod(0o700)


if __name__ == '__main__':
    unittest.main()
