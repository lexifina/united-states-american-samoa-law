import unittest
import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import corpus_jurisdiction as J


class JurisdictionTest(unittest.TestCase):
    def test_yogyakarta_template(self):
        got = J.document({'code': 'ID-YO', 'jurisdiction_level': 'province'}, 'indonesia/yogyakarta/acts', {'level': 'country', 'code': 'ID-YO', 'build': 'built'})
        self.assertEqual((got['level'], got['code'], got['parent']), ('province', 'ID-YO', 'indonesia'))
        self.assertEqual(got['build'], 'built')

    def test_country_and_whole_level(self):
        self.assertEqual(J.document({'code': 'US'}, 'united-states/acts')['level'], 'country')
        got = J.document({'code': 'US'}, 'united-states/federal/acts')
        self.assertEqual((got['level'], got['parent'], got['code']), ('federal', 'united-states', 'US'))

    def test_state_prefix_and_place_name_level(self):
        got = J.document({'code': 'US'}, 'united-states/colorado/acts', {'code': 'CO', 'level': 'colorado'})
        self.assertEqual((got['code'], got['level']), ('US-CO', 'subdivision'))

    def test_municipality_and_regency_parent(self):
        got = J.document({'code': 'AR-B-ALBERTI'}, 'argentina/buenos-aires/alberti/acts')
        self.assertEqual((got['level'], got['code'], got['parent']),
                         ('municipality', 'AR-B-ALBERTI', 'argentina/buenos-aires'))
        got = J.document({'code': 'ID-JI-BOJONEGORO'}, 'indonesia/east-java/bojonegoro-regency/acts')
        self.assertEqual(got['code'], 'ID-JI-BOJONEGORO-REGENCY')
        self.assertEqual(got['level'], 'regency')

    def test_unknown_type_and_eu(self):
        self.assertEqual(J.document({'code': 'XX-1'}, 'testland/example/acts', {'level': 'example'})['level'], 'subdivision')
        self.assertEqual(J.document({'code': 'EU'}, 'european-union/acts')['level'], 'supranational')
        with self.assertRaises(ValueError):
            J.document({'code': 'US-WRONG'}, 'united-states/example/acts')

    def test_preserves_recorded_types_from_the_closed_vocabulary(self):
        for level in ('community', 'federal entity', 'autonomous territorial unit', 'autonomous region',
                      'emirate', 'metropolitan municipality with regional functions'):
            with self.subTest(level=level):
                got = J.document({'code': 'XX-1'}, 'testland/example/acts', {'level': level, 'code': 'XX-1'})
                self.assertEqual(got['level'], level)
                self.assertEqual(got['parent'], 'testland')

    def test_nested_canton_preserves_its_source_type_and_iso_code(self):
        got = J.document({'code': 'XX-05', 'parent_code': 'XX-A'}, 'testland/entity/river-canton/acts',
                         {'code': 'XX-05', 'level': 'canton'})
        self.assertEqual((got['level'], got['code'], got['parent']), ('canton', 'XX-05', 'testland/entity'))
        with self.assertRaisesRegex(ValueError, 'canton code'):
            J.document({'code': 'XX-05', 'parent_code': 'XX-A'}, 'testland/entity/river-canton/acts',
                       {'code': 'XX-NOTISO', 'level': 'canton'})

    def test_matches_unchanged_global_describe(self):
        source = Path(__file__).parent / 'fixtures/corpus-standard/describe-95b8164.py'
        spec = importlib.util.spec_from_file_location('pinned_global_describe', source)
        upstream = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upstream)
        samples = {
            'indonesia/yogyakarta/acts': ({'code': 'ID-YO'}, {'level': 'country', 'code': 'ID-YO'}),
            'united-states/colorado/acts': ({'code': 'US-CO'}, {'level': 'state', 'code': 'CO'}),
            'united-states/american-samoa/acts': ({'code': 'US-AS'}, {'level': 'territory', 'code': 'AS'}),
            'united-states/federal/cfr': ({'code': 'US'}, {'level': 'federal', 'code': 'US'}),
            'european-union/acts': ({'code': 'EU'}, {'level': 'supranational', 'code': 'EU'}),
            'argentina/buenos-aires/alberti/acts': ({'code': 'AR-B-ALBERTI'}, {'level': 'municipality', 'code': 'AR-B-ALBERTI'}),
            'testland/example/acts': ({'code': 'XX-1'}, {'level': 'community', 'code': 'XX-1'}),
            'testland/entity/river-canton/acts': ({'code': 'XX-05', 'parent_code': 'XX-A'}, {'level': 'canton', 'code': 'XX-05'}),
        }
        documents = {'manifest.json': {'corpora': []}, 'jurisdiction.json': {}}
        for name, code in [('indonesia', 'ID'), ('united-states', 'US'), ('argentina', 'AR'), ('testland', 'XX')]:
            documents[name + '/jurisdiction.json'] = {'code': code, 'level': 'country'}
        documents['argentina/buenos-aires/jurisdiction.json'] = {'code': 'AR-B', 'level': 'province'}
        for path, (_, old) in samples.items():
            documents[path.rsplit('/', 1)[0] + '/jurisdiction.json'] = {**old, 'name': path}

        def read_git(*args):
            if args == ('ls-tree', '-r', '--name-only', 'HEAD'):
                return '\n'.join(documents)
            if args[0] == 'show':
                name = args[1].split(':', 1)[1]
                if name == 'data/moved-paths.tsv':
                    return ''
                return json.dumps(documents[name])
            raise AssertionError(args)

        with tempfile.TemporaryDirectory() as tmp, patch.object(upstream, 'ROOT', Path(tmp)), \
                patch.object(upstream, 'git', read_git), patch.object(upstream, '_token', return_value=''), \
                patch.object(upstream, 'pins', return_value={p: ('fixture', 'fixture') for p in samples}), \
                patch.object(upstream, 'describe', side_effect=lambda p, *_: ({'path': p}, samples[p][1])):
            self.assertEqual(upstream.main([]), 0)
            for path, (country, old) in samples.items():
                expected = json.loads((Path(tmp) / path.rsplit('/', 1)[0] / 'jurisdiction.json').read_text())
                actual = J.document(country, path, old)
                self.assertEqual({k: actual[k] for k in ('level', 'code', 'path')},
                                 {k: expected[k] for k in ('level', 'code', 'path')}, path)


if __name__ == '__main__':
    unittest.main()
