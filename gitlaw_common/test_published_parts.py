"""A previously published input cannot become an implicit withdrawal."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import append_gate as gate
import build
import published_parts
import publish_marker
from test_build import corpus

D = '2026-10-28'
NAME = '20-civil-code.json'


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, check=True,
                          encoding='utf-8', timeout=120).stdout.strip()


class PublishedPartsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.root = Path(cls.work.name)
        data = corpus()  # unchanged, existing Testland fixture; no real law authored
        cls.part_data = {'acts': [data['acts'].pop(1)]}
        cls.part_bytes = json.dumps(cls.part_data, ensure_ascii=False).encode('utf-8')
        cls.base_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        source = cls.root / 'original'
        source.mkdir()
        (source / 'corpus.d').mkdir()
        (source / 'corpus.json').write_bytes(cls.base_bytes)
        part = source / 'corpus.d' / NAME
        part.write_bytes(cls.part_bytes)
        publish_marker.write(part, 'original-review')
        cls.repo = cls.root / 'published'
        with patch.dict(os.environ, {'GITLAW_VERIFIED_PARTS_ONLY': '1'}):
            build.build(source, cls.repo, D)
        cls.head = git(cls.repo, 'rev-parse', 'main')
        # Model an older main with no part manifest, preserving its law history.
        cls.legacy = cls.root / 'legacy'
        git(cls.root, 'clone', '-q', str(cls.repo), str(cls.legacy))
        git(cls.legacy, 'rm', '-q', 'data/parts.json')
        git(cls.legacy, '-c', 'user.name=Lexifina', '-c', 'user.email=world-law@lexifina.com',
            'commit', '-q', '-m', 'Legacy fixture without part provenance')

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / 'corpus.d').mkdir()
        (self.folder / 'corpus.json').write_bytes(self.base_bytes)
        self.part = self.folder / 'corpus.d' / NAME
        self.part.write_bytes(self.part_bytes)
        publish_marker.write(self.part, 'promoted-review')
        env = patch.dict(os.environ, {'GITLAW_VERIFIED_PARTS_ONLY': '1'})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(setattr, gate.Frozen, 'snap', None)

    def test_manifest_names_and_hashes_are_from_the_consumed_inputs(self):
        saved = json.loads(git(self.repo, 'show', 'main:data/parts.json'))
        self.assertEqual(saved, {'schema': 1, 'parts': {NAME: {
            'sha256': hashlib.sha256(self.part_bytes).hexdigest(), 'acts': ['codigo-civil']}}})

    def assert_stops_before_planning(self, reason, repo=None):
        repo = repo or self.repo
        head = git(repo, 'rev-parse', 'main')
        tags = git(repo, 'show-ref', '--tags')
        for frozen in (False, True):
            for corrections in (False, True):
                with self.subTest(frozen=frozen, corrections=corrections):
                    folder = gate.freeze(self.folder) if frozen else self.folder
                    with patch.object(gate, 'sync', return_value=head), \
                         patch.object(gate.AP, 'append') as append, \
                         patch.object(build, 'plan') as plan, \
                         patch.object(gate.AP, 'plan_corrections') as withdraw:
                        result = gate.run(folder, repo, 'unused', D, None, incremental=True,
                                          corrections=corrections, repair=True)
                    self.assertEqual(result['result'], 'error', result)
                    self.assertIn(NAME, result['reason'])
                    self.assertIn(reason, result['reason'])
                    append.assert_not_called()
                    plan.assert_not_called()
                    withdraw.assert_not_called()
        self.assertEqual(git(repo, 'rev-parse', 'main'), head)
        self.assertEqual(git(repo, 'show-ref', '--tags'), tags)

    def test_published_part_edited_after_promotion_stops_before_any_plan(self):
        self.part.write_bytes(b'{"acts": []}')  # even deleting every act cannot hide ownership
        self.assert_stops_before_planning('mismatch')

    def test_published_part_marker_deleted_stops_before_any_plan(self):
        self.part.with_suffix('.PUBLISH').unlink()
        self.assert_stops_before_planning('absent')

    def test_published_part_file_deleted_stops_before_any_plan(self):
        self.part.unlink()
        self.assert_stops_before_planning('absent part file')

    def test_never_published_unverified_part_excluded_and_gate_passes(self):
        new = copy.deepcopy(self.part_data)
        new['acts'][0]['slug'] = 'never-published'
        extra = self.folder / 'corpus.d' / '90-new.json'
        extra.write_text(json.dumps(new), encoding='utf-8')
        publish_marker.write(extra, 'new-review')
        extra.write_bytes(extra.read_bytes() + b' ')  # mismatch, but never published
        repo = self.root / ('positive-' + self.folder.name)
        git(self.root, 'clone', '-q', str(self.repo), str(repo))
        frozen = gate.freeze(self.folder)
        with patch.object(gate, 'sync', return_value=self.head), patch.object(build, 'plan') as plan:
            result = gate.run(frozen, repo, 'unused', D, None, incremental=True)
        self.assertIn(result['result'], ('same', 'docs'), result)
        plan.assert_not_called()
        self.assertNotIn('90-new.json', json.loads(git(repo, 'show', 'main:data/parts.json'))['parts'])
        self.assertNotIn('never-published', git(repo, 'show', 'main:data/versions.json'))

    def test_legacy_main_edited_part_is_not_lost_by_freeze(self):
        self.part.write_bytes(self.part_bytes + b' ')
        self.assert_stops_before_planning('mismatch', self.legacy)

    def test_legacy_main_deleted_marker_is_not_lost_by_freeze(self):
        self.part.with_suffix('.PUBLISH').unlink()
        self.assert_stops_before_planning('absent', self.legacy)

    def test_legacy_main_unmapped_published_act_stops_with_candidate_name(self):
        self.part.write_bytes(b'{"acts": []}')
        self.assert_stops_before_planning('lost input ownership', self.legacy)

    def test_required_part_marker_cannot_disappear_during_load_selection(self):
        verified = publish_marker.verified

        def remove_after_check(part):
            ok = verified(part)
            part.with_suffix('.PUBLISH').unlink()
            return ok

        with patch.object(publish_marker, 'verified', remove_after_check), \
             self.assertRaisesRegex(build.CorpusError, NAME):
            build.load(self.folder, required_parts={NAME})

    def test_nightly_and_direct_append_also_stop(self):
        self.part.with_suffix('.PUBLISH').unlink()
        with patch.object(gate, 'sync', return_value=self.head), patch.object(gate, 'check_main') as check:
            result = gate.full_check(gate.freeze(self.folder), self.repo, 'unused', D, None)
        self.assertEqual(result['result'], 'error')
        self.assertIn(NAME, result['reason'])
        check.assert_not_called()
        with patch.object(build, 'plan') as plan, self.assertRaisesRegex(build.CorpusError, NAME):
            gate.AP.append(self.folder, self.repo, D, corrections=True)
        plan.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
