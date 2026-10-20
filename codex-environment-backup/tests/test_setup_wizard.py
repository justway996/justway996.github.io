import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from codex_backup.credentials import new_key
from codex_backup.scheduler import run_once
from codex_backup.setup_wizard import (make_backup_config, make_restore_config, connect_cloud,
    restore_saved_snapshot, restore_cloud_version, cloud_versions, enable_schedule_after_backup, launch_backup)
from test_transfer import LocalDrive


class SetupWizardTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'unfinished.txt').write_bytes(b'uncommitted work')
        self.cfg = self.base / 'backup.json'
        self.roots = [dict(id='project', path=str(self.source), kind='project')]
        make_backup_config(self.cfg, self.roots, self.base / 'backup-data')

    def snapshot(self):
        key = self.base / 'offline.key'
        new_key(self.base / 'backup-data', key)
        return Path(run_once(self.cfg)['snapshot']), key

    def restore_config(self):
        config = self.base / 'restore.json'
        make_restore_config(config, self.base / 'restore-data')
        return config

    def test_backup_configuration_is_explicit_four_hours_and_cloud_disabled(self):
        cfg = json.loads(self.cfg.read_text(encoding='utf-8'))
        self.assertEqual(cfg['schedule']['interval_minutes'], 240)
        self.assertFalse(cfg['cloud']['enabled'])
        self.assertEqual(cfg['roots'], self.roots)

    def test_existing_configuration_and_invalid_output_location_are_preserved(self):
        before = self.cfg.read_bytes()
        with self.assertRaises(FileExistsError):
            make_backup_config(self.cfg, self.roots, self.base / 'other')
        self.assertEqual(self.cfg.read_bytes(), before)
        bad = self.base / 'bad.json'
        with self.assertRaises(ValueError):
            make_backup_config(bad, self.roots, self.source / 'data')
        self.assertFalse(bad.exists())

    def test_broad_scope_containing_an_old_backup_store_is_blocked_before_save(self):
        old = self.source / 'old-backup/data'
        (old / 'outbox').mkdir(parents=True)
        (old / 'key.dpapi').write_bytes(b'not a real key')
        config = self.base / 'broad.json'
        with self.assertRaisesRegex(ValueError, 'old-backup'):
            make_backup_config(config, self.roots, self.base / 'new-data')
        self.assertFalse(config.exists())

    def test_launch_persists_schedule_request_before_detached_worker_starts(self):
        import sys
        self.snapshot()
        cfg = json.loads(self.cfg.read_text(encoding='utf-8'))
        cfg['cloud']['enabled'] = True
        self.cfg.write_text(json.dumps(cfg), encoding='utf-8')
        exe = self.base / 'app.exe'
        exe.with_name('CodexEnvironmentBackupWorker.exe').write_bytes(b'fixture')
        def started(*args, **kwargs):
            request = json.loads((self.base / 'backup-data/schedule-request.json').read_text(encoding='utf-8'))
            self.assertEqual(Path(request['config_path']), self.cfg.resolve())
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)), patch(
                'codex_backup.setup_wizard.subprocess.Popen', side_effect=started):
            launch_backup(self.cfg, schedule=True)

    def test_restore_profile_cannot_launch_backup_or_enable_schedule(self):
        cfg = self.restore_config()
        self.assertEqual(json.loads(cfg.read_text(encoding='utf-8'))['roots'], [])
        with self.assertRaises(ValueError):
            launch_backup(cfg)
        with self.assertRaises(ValueError):
            enable_schedule_after_backup(cfg, dict(state='cloud_verified'))

    def test_cloud_is_not_enabled_when_login_or_restart_is_pending(self):
        original = self.cfg.read_bytes()
        with patch('codex_backup.setup_wizard.prepare_environment', return_value=dict(state='restart_required')):
            self.assertEqual(connect_cloud(self.cfg, self.base / 'setup')['state'], 'restart_required')
        self.assertEqual(self.cfg.read_bytes(), original)
        ready = dict(state='ready', distribution='dedicated', script='/opt/quark/scripts/quark-drive.cjs')
        with patch('codex_backup.setup_wizard.prepare_environment', return_value=ready), patch('codex_backup.setup_wizard.authorize_cloud', side_effect=RuntimeError('not authorized')):
            with self.assertRaises(RuntimeError):
                connect_cloud(self.cfg, self.base / 'setup')
        self.assertFalse(json.loads(self.cfg.read_text(encoding='utf-8'))['cloud']['enabled'])

    def test_connected_backup_enables_cloud_but_restore_never_does(self):
        restore = self.restore_config()
        ready = dict(state='ready', distribution='dedicated', script='/opt/quark/scripts/quark-drive.cjs')
        for cfg, enabled in [(self.cfg, True), (restore, False)]:
            with patch('codex_backup.setup_wizard.prepare_environment', return_value=ready), patch('codex_backup.setup_wizard.authorize_cloud', return_value=dict(state='connected')):
                connect_cloud(cfg, self.base / 'setup')
            self.assertEqual(json.loads(cfg.read_text(encoding='utf-8'))['cloud']['enabled'], enabled)

    def test_local_restore_generates_real_continuation_files(self):
        snapshot, key = self.snapshot()
        destination = self.base / 'restored'
        report = restore_saved_snapshot(self.restore_config(), snapshot, destination, key)
        self.assertTrue(report['files_verified'])
        self.assertEqual((destination / 'roots/project/unfinished.txt').read_bytes(), b'uncommitted work')
        self.assertTrue((destination / 'CONTINUE.md').is_file())

    def test_wrong_key_and_nonempty_target_fail_before_key_import(self):
        snapshot, key = self.snapshot()
        cfg = self.restore_config()
        wrong = self.base / 'wrong.key'
        wrong.write_text('00' * 32, encoding='ascii')
        with self.assertRaises(ValueError):
            restore_saved_snapshot(cfg, snapshot, self.base / 'wrong-restore', wrong)
        self.assertFalse((self.base / 'restore-data/key.dpapi').exists())
        target = self.base / 'occupied'
        target.mkdir()
        (target / 'work.txt').write_bytes(b'keep')
        with self.assertRaises(ValueError):
            restore_saved_snapshot(cfg, snapshot, target, key)
        self.assertEqual((target / 'work.txt').read_bytes(), b'keep')

    def test_cloud_metadata_is_listed_and_wrong_key_stops_before_bulk_fetch(self):
        snapshot, key = self.snapshot()
        remote = self.base / 'remote'
        remote.mkdir()
        shutil.copytree(snapshot, remote / snapshot.name)
        drive = LocalDrive(remote)
        drive.resolve_path = lambda path: str(remote)
        cfg = self.restore_config()
        wrong = self.base / 'wrong.key'
        wrong.write_text('00' * 32, encoding='ascii')
        with patch('codex_backup.setup_wizard.QuarkClient', return_value=drive):
            versions = cloud_versions(cfg)
            self.assertEqual(versions['versions'][0]['snapshot_id'], snapshot.name)
            self.assertIn('created_at', versions['versions'][0])
            with patch('codex_backup.setup_wizard.fetch') as fetch_mock:
                with self.assertRaises(ValueError):
                    restore_cloud_version(cfg, snapshot.name, self.base / 'restore', wrong)
                fetch_mock.assert_not_called()

    def test_failed_download_cannot_report_a_restored_version(self):
        snapshot, key = self.snapshot()
        remote = self.base / 'remote'
        remote.mkdir()
        shutil.copytree(snapshot, remote / snapshot.name)
        drive = LocalDrive(remote)
        drive.resolve_path = lambda path: str(remote)
        cfg = self.restore_config()
        with patch('codex_backup.setup_wizard.QuarkClient', return_value=drive), patch('codex_backup.setup_wizard.fetch', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                restore_cloud_version(cfg, snapshot.name, self.base / 'restored', key)
        self.assertFalse((self.base / 'restored').exists())

    def test_cloud_restore_fetches_and_restores_the_authenticated_version(self):
        snapshot, key = self.snapshot()
        remote = self.base / 'remote'
        remote.mkdir()
        shutil.copytree(snapshot, remote / snapshot.name)
        drive = LocalDrive(remote)
        drive.resolve_path = lambda path: str(remote)
        cfg = self.restore_config()
        with patch('codex_backup.setup_wizard.QuarkClient', return_value=drive):
            result = restore_cloud_version(cfg, snapshot.name, self.base / 'restored', key)
        self.assertTrue(result['files_verified'])
        self.assertEqual((self.base / 'restored/roots/project/unfinished.txt').read_bytes(), b'uncommitted work')

    def test_launch_uses_fixed_background_worker_with_explicit_configuration(self):
        import sys
        snapshot, key = self.snapshot()
        cfg = json.loads(self.cfg.read_text(encoding='utf-8'))
        cfg['cloud']['enabled'] = True
        self.cfg.write_text(json.dumps(cfg), encoding='utf-8')
        exe = self.base / 'app.exe'
        worker = self.base / 'CodexEnvironmentBackupWorker.exe'
        worker.write_bytes(b'fixture')
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)), patch('codex_backup.setup_wizard.subprocess.Popen') as popen:
            launch_backup(self.cfg)
        args = popen.call_args.args[0]
        self.assertEqual(Path(args[0]), worker)
        self.assertEqual(args[1:3], ['worker', '--config'])
        self.assertEqual(Path(args[3]), self.cfg.resolve())
        self.assertFalse(popen.call_args.kwargs.get('shell', False))

    def test_empty_cloud_and_incomplete_backup_do_not_enable_schedule(self):
        cfg = self.restore_config()
        drive = LocalDrive(self.base)
        drive.resolve_path = lambda path: str(self.base)
        with patch('codex_backup.setup_wizard.QuarkClient', return_value=drive):
            self.assertEqual(cloud_versions(cfg)['versions'], [])
        with patch('codex_backup.setup_wizard.install_schedule') as install:
            with self.assertRaises(ValueError):
                enable_schedule_after_backup(self.cfg, dict(state='pending_upload'))
            install.assert_not_called()

    def test_setup_entry_dispatches_without_starting_system_installation(self):
        from codex_backup.app import main
        with patch('sys.argv', ['app.exe', 'setup-smoke']), patch('codex_backup.setup_wizard.setup_gui', create=True) as gui:
            main()
        gui.assert_called_once_with(True, state_dir=None)

    def test_packaged_setup_diagnostic_is_read_only(self):
        from codex_backup.app import action
        with patch('codex_backup.bootstrap_windows.inspect_environment', return_value=dict(state='ready')) as inspect, patch('codex_backup.setup_wizard.prepare_environment') as prepare:
            self.assertEqual(action('setup-check', self.cfg)['state'], 'ready')
        inspect.assert_called_once()
        prepare.assert_not_called()

    def test_worker_publishes_working_before_collecting(self):
        from codex_backup.collect import collect
        new_key(self.base / 'backup-data', self.base / 'offline.key')
        observed = []
        def check(cfg, stage):
            observed.append(json.loads((self.base / 'backup-data/status.json').read_text(encoding='utf-8'))['state'])
            return collect(cfg, stage)
        with patch('codex_backup.scheduler.collect', side_effect=check):
            run_once(self.cfg)
        self.assertEqual(observed, ['working'])
