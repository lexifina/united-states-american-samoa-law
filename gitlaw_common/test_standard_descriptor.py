import unittest
import json
import tempfile
from pathlib import Path
import build as B
import corpus_paths as P


class DescriptorTest(unittest.TestCase):
    def test_named_path(self):
        for code, slug, wanted in (
                ('US-CO', 'united-states-colorado', 'united-states/colorado/acts'),
                ('ID-JI-BOJONEGORO', 'indonesia-bojonegoro-regency', 'indonesia/east-java/bojonegoro-regency/acts'),
                ('AR-B-ALBERTI', 'argentina-alberti-city', 'argentina/buenos-aires/alberti/acts'),
                ('BR-DF', 'brazil-federal-district', 'brazil/federal-district/acts')):
            self.assertEqual(P.descriptor_path({'code': code, 'slug': slug}), wanted)

    def test_metadata_only(self):
        c = {'country': {'code': 'XX', 'slug': 'testland', 'name': 'Testland', 'lang': 'en',
                         'history': 'metadata-only', 'publisher': {'name': 'Official Gazette'}},
             'acts': [{'slug': 'record', 'versions': []}], 'laws': {}}
        d = B.corpus_descriptor(c, [], '2026-11-03')
        self.assertEqual(d['history'], 'metadata-only')
        self.assertEqual(d['acts'], 1)
        for field in ('path', 'scope', 'future_branch', 'publisher', 'record_to'):
            self.assertIn(field, d)

    def test_unknown_parent_is_not_guessed(self):
        with self.assertRaises(ValueError):
            P.descriptor_path({'code': 'ID-ZZ-EXAMPLE', 'slug': 'indonesia-example'})

    def test_metadata_only_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            c = {'country': {'code': 'XX', 'slug': 'testland', 'name': 'Testland', 'lang': 'en', 'tz': 'UTC',
                             'history': 'metadata-only', 'publisher': {'name': 'Gazette', 'email': 'g@example.invalid'}},
                 'laws': {}, 'acts': [{'slug': 'entry', 'short': 'Entry', 'title': 'Catalogue entry'}]}
            (source / 'corpus.json').write_text(json.dumps(c), encoding='utf-8')
            repo = root / 'repo'
            try:
                B.build(source, repo, '2026-11-03')
                self.assertEqual(B.git(repo, 'rev-list', '--count', 'main').strip(), '1')
                self.assertEqual(B.hashes(repo)[1], {})
                descriptor = json.loads((repo / 'corpus.json').read_text())
                self.assertEqual(descriptor['history'], 'metadata-only')
                self.assertEqual(descriptor['acts'], 1)
                self.assertIsNone(descriptor['history_from'])
            finally:
                if repo.exists():
                    for p in repo.rglob('*'):
                        p.chmod(0o700)


if __name__ == '__main__':
    unittest.main()
