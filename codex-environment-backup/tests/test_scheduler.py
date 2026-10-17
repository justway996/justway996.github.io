import json
import os
from pathlib import Path
import tempfile
import unittest
import sqlite3
from unittest.mock import patch

from codex_backup.scheduler import run_once, lock, schedule_xml
from codex_backup.credentials import protect, unprotect, new_key, read_key
from test_transfer import LocalDrive


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / 'source').mkdir()
        (self.base / 'source/a.txt').write_text('work')
        self.config = self.base / 'config.json'
        self.config.write_text(json.dumps(dict(format_version=1, codex_home=str(self.base / 'codex'),
            data_dir=str(self.base / 'data'), roots=[dict(id='p', path=str(self.base / 'source'), kind='project')])) )

    def test_dpapi_roundtrip_and_key_export(self):
        key = os.urandom(32)
        self.assertEqual(unprotect(protect(key)), key)
        new_key(self.base / 'data', self.base / 'offline.key')
        self.assertEqual(read_key(self.base / 'data'), bytes.fromhex((self.base / 'offline.key').read_text().strip()))

    def test_wrong_export_location_rejected(self):
        with self.assertRaises(ValueError):
            new_key(self.base / 'data', self.base / 'data/outbox/key.txt')

    def test_no_change_no_new_snapshot_and_key_not_in_backup(self):
        new_key(self.base / 'data', self.base / 'offline.key')
        first = run_once(self.config)
        second = run_once(self.config)
        self.assertEqual(first['snapshot_id'], second['snapshot_id'])
        self.assertTrue(second['unchanged'])
        self.assertEqual(first['state'], 'local_ready')

    def test_missing_key_does_not_mark_success(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            run_once(self.config)
        status = self.base / 'data/status.json'
        self.assertNotEqual(json.loads(status.read_text()).get('state'), 'local_ready')

    def test_unchanged_snapshot_is_reverified(self):
        new_key(self.base / 'data', self.base / 'offline.key')
        first = run_once(self.config)
        next(Path(first['snapshot']).glob('*.aes')).write_bytes(b'corrupted')
        with self.assertRaises(ValueError):
            run_once(self.config)
        status = json.loads((self.base / 'data/status.json').read_text())
        self.assertNotEqual(status['state'], 'local_ready')

    def test_lock_prevents_second_worker_and_releases(self):
        with lock(self.base):
            with self.assertRaises(RuntimeError):
                with lock(self.base):
                    pass
        with lock(self.base):
            pass

    def test_schedule_quotes_paths_and_30_minute_interval(self):
        xml = schedule_xml(Path('C:/Program Files/备份/app.exe'), Path('C:/Users/测试/config.json'))
        self.assertIn('PT30M', xml)
        self.assertIn('InteractiveToken', xml)
        self.assertIn('worker', xml)

    def test_schedule_uses_selected_interval_and_rejects_invalid_values(self):
        self.assertIn('PT240M', schedule_xml(Path('C:/backup/worker.exe'), Path('C:/backup/config.json'), 240))
        for minutes in [0, -1, True, 1.5, 1441]:
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                schedule_xml(Path('worker.exe'), Path('config.json'), minutes)

    def test_cloud_target_change_is_reverified(self):
        cfg = json.loads(self.config.read_text())
        one, two = self.base / 'remote-one', self.base / 'remote-two'
        one.mkdir()
        two.mkdir()
        cfg['cloud'] = dict(enabled=True, path=str(one))
        self.config.write_text(json.dumps(cfg))
        new_key(self.base / 'data', self.base / 'offline.key')
        class Client(LocalDrive):
            notices = []
            fail = False
            def __init__(self, *args):
                pass
            def resolve_path(self, path):
                return path
        with patch('codex_backup.scheduler.QuarkClient', Client):
            first = run_once(self.config)
            cfg['cloud']['path'] = str(two)
            self.config.write_text(json.dumps(cfg))
            second = run_once(self.config)
        self.assertEqual(second['state'], 'cloud_verified')
        self.assertTrue(list(two.glob('*/COMPLETE.json')))

    def test_verified_old_versions_check_metadata_without_downloading_all_volumes_again(self):
        cfg = json.loads(self.config.read_text())
        remote = self.base / 'remote'
        remote.mkdir()
        cfg['cloud'] = dict(enabled=True, path=str(remote))
        self.config.write_text(json.dumps(cfg))
        new_key(self.base / 'data', self.base / 'offline.key')
        downloads = []
        class Client(LocalDrive):
            notices = []
            fail = False
            def __init__(self, *args):
                pass
            def resolve_path(self, path):
                return path
            def download(self, fid, destination):
                downloads.append(Path(fid).name)
                return super().download(fid, destination)
        with patch('codex_backup.scheduler.QuarkClient', Client):
            first = run_once(self.config)
            downloads.clear()
            second = run_once(self.config)
            self.assertFalse(any(name.endswith('.aes') for name in downloads))
            self.assertIn('envelope.json', downloads)
            self.assertEqual(second['cloud_verified_at'], first['cloud_verified_at'])
            self.assertEqual(second['cloud_check_scope'], 'previous_full_bytes_and_current_metadata')
            next((remote / first['snapshot_id']).glob('*.aes')).unlink()
            downloads.clear()
            run_once(self.config)
            self.assertTrue(any(name.endswith('.aes') for name in downloads))

    def test_new_empty_directory_creates_a_version(self):
        new_key(self.base / 'data', self.base / 'offline.key')
        first = run_once(self.config)
        (self.base / 'source/new-empty').mkdir()
        second = run_once(self.config)
        self.assertFalse(second['unchanged'])
        self.assertNotEqual(first['snapshot_id'], second['snapshot_id'])

    def test_sqlite_maintenance_only_does_not_create_a_version(self):
        db = sqlite3.connect(self.base / 'source/state.sqlite')
        self.addCleanup(db.close)
        db.execute('create table work(id integer primary key, body text)')
        db.execute("insert into work values(1,'ongoing')")
        db.commit()
        new_key(self.base / 'data', self.base / 'offline.key')
        first = run_once(self.config)
        db.execute('vacuum')
        second = run_once(self.config)
        self.assertTrue(second['unchanged'])
        self.assertEqual(first['snapshot_id'], second['snapshot_id'])
