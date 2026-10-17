import json
import os
from pathlib import Path
import tempfile
import unittest

from codex_backup.archive import seal, verify_snapshot
from codex_backup.collect import collect
from codex_backup.model import load_config


class TimestampTests(unittest.TestCase):
    def test_pre_1980_file_timestamp_does_not_prevent_backup(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as tmp:
            base = Path(tmp).resolve()
            source = base / 'source'
            source.mkdir()
            file = source / 'legacy.dat'
            file.write_bytes(b'legacy asset')
            os.utime(file, (0, 0))
            config = base / 'config.json'
            config.write_text(json.dumps(dict(format_version=1, codex_home=str(base / 'codex'),
                data_dir=str(base / 'data'), roots=[dict(id='p', path=str(source), kind='source')])), encoding='utf-8')
            stage = base / 'stage'
            manifest = collect(load_config(config), stage)
            snapshot = seal(stage, base / 'outbox', b'k' * 32)
            self.assertEqual(verify_snapshot(snapshot, b'k' * 32)['files'], manifest['files'])
