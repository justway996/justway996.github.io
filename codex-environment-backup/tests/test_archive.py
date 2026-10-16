import json
import os
from pathlib import Path
import tempfile
import unittest

from codex_backup.archive import seal, verify_snapshot
from codex_backup.collect import sha256


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.stage = self.base / 'stage'
        (self.stage / 'roots/p').mkdir(parents=True)
        self.file = self.stage / 'roots/p/秘密.txt'
        self.file.write_bytes(os.urandom(2048))
        self.manifest = dict(format_version=1, roots=[dict(id='p', path='C:/old', kind='project')],
            files=[dict(path='roots/p/秘密.txt', size=2048, sha256=sha256(self.file))],
            coverage=[], environment={}, handoff={}, complete=True)
        (self.stage / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        self.key = os.urandom(32)

    def snapshot(self):
        return seal(self.stage, self.base / 'out', self.key, part_size=512)

    def test_roundtrip_multi_part(self):
        snapshot = self.snapshot()
        self.assertGreater(len(list(snapshot.glob('*.aes'))), 1)
        self.assertEqual(verify_snapshot(snapshot, self.key)['files'], self.manifest['files'])
        envelope = (snapshot / 'envelope.json').read_text(encoding='utf-8')
        self.assertNotIn('秘密', envelope)
        self.assertNotIn('C:/old', envelope)

    def test_wrong_key_rejected(self):
        with self.assertRaises(ValueError):
            verify_snapshot(self.snapshot(), os.urandom(32))

    def test_corruption_missing_part_and_envelope_tamper(self):
        for kind in ['corrupt', 'missing', 'envelope', 'marker']:
            with self.subTest(kind=kind):
                snap = self.snapshot()
                part = next(snap.glob('*.aes'))
                if kind == 'corrupt':
                    data = bytearray(part.read_bytes())
                    data[-1] ^= 1
                    part.write_bytes(data)
                elif kind == 'missing':
                    part.unlink()
                elif kind == 'envelope':
                    envelope = json.loads((snap / 'envelope.json').read_text())
                    envelope['parts'].reverse()
                    (snap / 'envelope.json').write_text(json.dumps(envelope))
                else:
                    (snap / 'COMPLETE.json').unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    verify_snapshot(snap, self.key)

    def test_changed_staging_rejected_without_publishing(self):
        self.file.write_bytes(b'changed after collection')
        with self.assertRaises(ValueError):
            self.snapshot()
        self.assertFalse(list((self.base / 'out').glob('*/COMPLETE.json')))

    def test_recovery_key_in_source_is_blocked_even_after_scope_changes(self):
        self.file.write_text(self.key.hex() + '\n', encoding='ascii')
        self.manifest['files'][0].update(size=self.file.stat().st_size, sha256=sha256(self.file))
        (self.stage / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Recovery key'):
            self.snapshot()
