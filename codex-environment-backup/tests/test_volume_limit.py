import json
import os
from pathlib import Path
import tempfile
import unittest

from codex_backup.archive import seal, verify_snapshot
from codex_backup.collect import sha256


class VolumeLimitTests(unittest.TestCase):
    def test_default_volumes_fit_observed_download_limit_and_old_large_parts_still_read(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            base = Path(temp)
            stage = base / 'stage'
            file = stage / 'roots/p/data.bin'
            file.parent.mkdir(parents=True)
            file.write_bytes(os.urandom(52 * 1024 * 1024))
            manifest = dict(format_version=1, roots=[dict(id='p', path='C:/old', kind='project')],
                files=[dict(path='roots/p/data.bin', size=file.stat().st_size, sha256=sha256(file))],
                coverage=[], complete=True)
            (stage / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            key = os.urandom(32)
            snapshot = seal(stage, base / 'out', key)
            self.assertTrue(all(p.stat().st_size <= 50 * 1024 * 1024 for p in snapshot.glob('*.aes')))
            self.assertGreater(len(list(snapshot.glob('*.aes'))), 1)
            self.assertEqual(verify_snapshot(snapshot, key)['files'], manifest['files'])
            legacy = seal(stage, base / 'legacy', key, part_size=64 * 1024 * 1024)
            self.assertEqual(verify_snapshot(legacy, key)['files'], manifest['files'])
