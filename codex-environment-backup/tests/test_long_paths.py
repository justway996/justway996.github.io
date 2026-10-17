import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from codex_backup.archive import seal
from codex_backup.collect import collect
from codex_backup.model import load_config
from codex_backup.restore import restore


@unittest.skipUnless(os.name == 'nt', 'Windows filesystem paths')
class LongPathTests(unittest.TestCase):
    def test_nested_long_paths_and_sqlite_survive_collection_encryption_and_restore(self):
        work = Path('.test-work').resolve()
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='\\\\?\\' + str(work)) as tmp:
            base = Path(tmp)
            ordinary = Path(tmp[4:])
            source = base / 'source'
            nested = source / ('a' * 70) / ('b' * 70) / ('c' * 70)
            nested.mkdir(parents=True)
            (nested / 'code.txt').write_bytes(b'long path work in progress')
            (nested / 'empty').mkdir()
            dbpath = nested / 'state.sqlite'
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('create table state(body text)')
                db.execute("insert into state values ('preserve sqlite')")
                db.commit()
            config = base / 'config.json'
            config.write_text(json.dumps(dict(format_version=1, codex_home=str(ordinary / 'codex'),
                data_dir=str(ordinary / 'data'), roots=[dict(id='p', path=str(ordinary / 'source'), kind='project')])), encoding='utf-8')
            stage = ordinary / 'stage'
            manifest = collect(load_config(config), stage)
            self.assertTrue(manifest['complete'])
            self.assertEqual(len(manifest['files']), 2)
            snapshot = seal(stage, ordinary / 'outbox', b'k' * 32)
            destination = ordinary / 'restore'
            report = restore(snapshot, destination, b'k' * 32)
            restored = base / 'restore/roots/p' / nested.relative_to(source)
            self.assertEqual((restored / 'code.txt').read_bytes(), b'long path work in progress')
            self.assertTrue((restored / 'empty').is_dir())
            self.assertTrue(report['files_verified'])

    def test_extended_prefix_cannot_hide_output_inside_selected_root(self):
        work = Path('.test-work').resolve()
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='\\\\?\\' + str(work)) as tmp:
            base = Path(tmp)
            ordinary = Path(tmp[4:])
            cfg = base / 'config.json'
            cfg.write_text(json.dumps(dict(format_version=1, codex_home=str(ordinary / 'codex'),
                data_dir=str(base / 'source/data'), roots=[dict(id='p', path=str(ordinary / 'source'), kind='project')])), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'outside'):
                load_config(cfg)
