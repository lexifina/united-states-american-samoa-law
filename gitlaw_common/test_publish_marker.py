"""Raw-byte sign-offs and all shared-builder consumers, using temporary fixtures."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import append_gate
import build
import publish_marker as marker


class PublishMarkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / 'corpus.json').write_bytes(b'{"acts": []}')
        (self.folder / 'corpus.d').mkdir()
        self.part = self.folder / 'corpus.d' / '10-part.json'
        self.original = b'{\r\n "acts": [{"slug": "sample", "versions": []}]\r\n}\r\n'
        self.part.write_bytes(self.original)
        self.signoff = self.part.with_suffix('.PUBLISH')
        self.env = patch.dict(os.environ, {'GITLAW_VERIFIED_PARTS_ONLY': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(setattr, append_gate.Frozen, 'snap', None)

    def marked(self):
        # Independent expected digest: hash the original fixture, not writer output.
        self.signoff.write_bytes(b'sha256:' + hashlib.sha256(self.original).hexdigest().encode() + b'\n')

    def test_absent_and_pending_rejected(self):
        self.part.with_suffix('.PUBLISH.pending').write_bytes(b'review requested\n')
        self.assertEqual(marker.status(self.part)[0], 'absent')
        self.assertFalse(marker.verified(self.part))

    def test_legacy_including_empty_marker_accepted(self):
        for data in (b'', b'verified against source\r\n'):
            self.signoff.write_bytes(data)
            self.assertEqual(marker.status(self.part)[0], 'legacy')
            self.assertTrue(marker.verified(self.part))
            self.assertEqual(len(build.load(self.folder)[0]['acts']), 1)

    def test_matching_hash_accepted(self):
        self.marked()
        self.assertEqual(marker.status(self.part)[0], 'match')
        self.assertTrue(marker.verified(self.part))
        self.assertEqual(len(build.load(self.folder)[0]['acts']), 1)

    def test_edited_part_rejected_by_build_and_freeze(self):
        self.marked()
        self.part.write_bytes(self.original.replace(b'sample', b'edited'))
        self.assertEqual(marker.status(self.part)[0], 'mismatch')
        self.assertIn('reviewed', marker.status(self.part)[1])
        self.assertFalse(marker.verified(self.part))
        self.assertEqual(build.load(self.folder)[0]['acts'], [])
        frozen = append_gate.freeze(self.folder)
        self.assertEqual(build.load(frozen)[0]['acts'], [])
        self.assertFalse((frozen / 'corpus.d' / self.signoff.name).exists())

    def test_exact_crlf_bytes_not_normalized(self):
        self.marked()
        self.part.write_bytes(self.original.replace(b'\r\n', b'\n'))
        self.assertEqual(json.loads(self.original), json.loads(self.part.read_bytes()))
        self.assertFalse(marker.verified(self.part))

    def test_malformed_or_duplicate_digest_fails_closed(self):
        digest = hashlib.sha256(self.original).hexdigest()
        for text in ('sha256:bad', 'sha256:' + digest.upper(), 'SHA256:' + digest,
                     f'sha256:{digest}\nsha256:{digest}'):
            with self.subTest(text=text):
                self.signoff.write_text(text, encoding='utf-8')
                self.assertEqual(marker.status(self.part)[0], 'mismatch')

    def test_hash_after_metadata_or_bom_is_not_legacy(self):
        for prefix in (b'reviewer: sample\n', b'\xef\xbb\xbf'):
            self.signoff.write_bytes(prefix + b'sha256:' + b'0' * 64 + b'\n')
            self.assertEqual(marker.status(self.part)[0], 'mismatch')

    def test_missing_part_with_hash_fails_closed(self):
        self.marked()
        self.part.unlink()
        self.assertEqual(marker.status(self.part)[0], 'mismatch')

    def test_unreadable_marker_fails_closed(self):
        self.signoff.mkdir()
        self.assertEqual(marker.status(self.part)[0], 'mismatch')

    def test_writer_format_and_atomic_replacement(self):
        self.signoff.write_bytes(b'previous review\n')
        replace = os.replace
        observed = []

        def capture(src, dest):
            self.assertEqual(Path(src).parent, self.signoff.parent)
            self.assertEqual(self.signoff.read_bytes(), b'previous review\n')
            observed.append(Path(src).read_bytes())
            replace(src, dest)

        with patch.object(marker.os, 'replace', capture):
            marker.write(self.part, 'marker-review')
        lines = self.signoff.read_bytes().splitlines()
        self.assertEqual(lines[0], b'sha256:' + hashlib.sha256(self.original).hexdigest().encode())
        self.assertEqual(lines[1], b'reviewer: marker-review')
        self.assertRegex(lines[2].decode(), r'^at: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertEqual(observed, [self.signoff.read_bytes()])
        self.assertNotIn(b'\r', self.signoff.read_bytes())
        self.assertEqual(sorted(p.name for p in self.part.parent.iterdir()), [self.signoff.name, self.part.name])

    def test_failed_replace_preserves_previous_marker_and_cleans_temp(self):
        self.signoff.write_bytes(b'previous\n')
        with patch.object(marker.os, 'replace', side_effect=OSError('locked')):
            with self.assertRaises(OSError):
                marker.write(self.part, 'reviewer')
        self.assertEqual(self.signoff.read_bytes(), b'previous\n')
        self.assertEqual(len(list(self.part.parent.iterdir())), 2)

    def test_reviewer_cannot_inject_lines(self):
        with self.assertRaises(ValueError):
            marker.write(self.part, 'job\nsha256:bad')
        self.assertFalse(self.signoff.exists())

    def test_freeze_keeps_reviewed_part_and_marker_after_live_changes(self):
        self.marked()
        frozen = append_gate.freeze(self.folder)
        frozen_part = frozen / 'corpus.d' / self.part.name
        self.part.write_bytes(self.original.replace(b'sample', b'edited'))
        self.signoff.write_bytes(b'sha256:' + b'0' * 64 + b'\n')
        self.assertTrue(marker.verified(frozen_part))
        self.assertEqual(frozen_part.read_bytes(), self.original)
        self.assertEqual(build.load(frozen)[0]['acts'][0]['slug'], 'sample')
        self.assertEqual(build.load(append_gate.freeze(self.folder))[0]['acts'], [])

    def test_unverified_snapshot_does_not_invent_a_marker(self):
        with patch.dict(os.environ, {'GITLAW_VERIFIED_PARTS_ONLY': '0'}):
            frozen = append_gate.freeze(self.folder)
        frozen_part = frozen / 'corpus.d' / self.part.name
        self.marked()  # arrives after snapshot
        self.assertFalse(frozen_part.with_suffix('.PUBLISH').exists())
        self.assertEqual(marker.status(frozen_part)[0], 'absent')
        self.assertEqual(build.load(frozen)[0]['acts'], [])

    def test_freeze_checks_captured_bytes_if_live_part_changes_during_capture(self):
        self.marked()
        read = Path.read_bytes

        def changing_read(path):
            data = read(path)
            if path == self.signoff:
                self.part.write_bytes(self.original.replace(b'sample', b'edited'))
                marker.write(self.part, 'new-review')
            return data

        # Read the old marker followed by a new part: the mixed snapshot must fail.
        def one_change(path):
            if path == self.signoff:
                with patch.object(Path, 'read_bytes', read):
                    return changing_read(path)
            return read(path)

        with patch.object(Path, 'read_bytes', one_change):
            frozen = append_gate.freeze(self.folder)
        self.assertEqual(build.load(frozen)[0]['acts'], [])

    def test_build_rechecks_bytes_read_after_selection(self):
        self.marked()
        real = marker.verified

        def edited_after_check(part):
            result = real(part)
            part.write_bytes(self.original.replace(b'sample', b'edited'))
            return result

        with patch.object(marker, 'verified', edited_after_check):
            self.assertEqual(build.load(self.folder)[0]['acts'], [])


if __name__ == '__main__':
    unittest.main()
