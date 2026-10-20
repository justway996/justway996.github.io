import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_backup.bootstrap_windows import prepare_environment, request_restart_resume, authorize_cloud, _system_info


class WindowsSetupTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.cfg = dict(data_dir=str(self.base / 'data'), cloud=dict(distribution='', script='', path='/CodexWorkspace'))
        self.system = dict(supported=True, system_ready=True, wsl_installed=True, boot_id='boot-1')

    def test_verified_existing_environment_never_installs_or_terminates(self):
        ready = dict(state='ready', distribution='existing', script='/opt/cli/scripts/quark-drive.cjs')
        with patch('codex_backup.bootstrap_windows.inspect_environment', return_value=ready), patch('codex_backup.bootstrap_windows.download_component') as download, patch('codex_backup.bootstrap_windows._elevated_system') as elevated:
            self.assertEqual(prepare_environment(self.cfg, self.base / 'setup'), ready)
        download.assert_not_called()
        elevated.assert_not_called()

    def test_foreign_distribution_is_never_modified(self):
        observed = dict(state='needs_setup', distribution='occupied', exists=True, owned=False, system=self.system)
        with patch('codex_backup.bootstrap_windows.inspect_environment', return_value=observed), patch('codex_backup.bootstrap_windows._run') as run:
            with self.assertRaisesRegex(RuntimeError, '已有'):
                prepare_environment(self.cfg, self.base / 'setup')
        run.assert_not_called()

    def test_permission_denial_preserves_retry_state(self):
        system = dict(self.system, system_ready=False)
        observed = dict(state='needs_setup', distribution='new', exists=False, owned=False, system=system)
        with patch('codex_backup.bootstrap_windows.inspect_environment', return_value=observed), patch('codex_backup.bootstrap_windows._elevated_system', return_value=dict(state='failed', error_code='ADMIN_DENIED')):
            result = prepare_environment(self.cfg, self.base / 'setup')
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['error_code'], 'ADMIN_DENIED')
        self.assertTrue((self.base / 'setup/setup-state.json').exists())

    def test_reboot_required_does_not_repeat_elevation_until_boot_changes(self):
        system = dict(self.system, system_ready=False)
        observed = dict(state='needs_setup', distribution='new', exists=False, owned=False, system=system)
        with patch('codex_backup.bootstrap_windows.inspect_environment', return_value=observed), patch('codex_backup.bootstrap_windows._elevated_system', return_value=dict(state='restart_required')) as elevated:
            first = prepare_environment(self.cfg, self.base / 'setup')
            second = prepare_environment(self.cfg, self.base / 'setup')
        self.assertEqual(first['state'], 'restart_required')
        self.assertEqual(second['state'], 'restart_required')
        self.assertEqual(elevated.call_count, 1)

    def test_active_backup_prevents_environment_changes(self):
        from codex_backup.scheduler import lock
        observed = dict(state='needs_setup', distribution='new', exists=False, owned=False, system=self.system)
        with lock(Path(self.cfg['data_dir'])), patch('codex_backup.bootstrap_windows.inspect_environment', return_value=observed), patch('codex_backup.bootstrap_windows.download_component') as download:
            with self.assertRaises(RuntimeError):
                prepare_environment(self.cfg, self.base / 'setup')
        download.assert_not_called()

    def test_resume_registry_command_quotes_paths_without_restarting(self):
        import winreg
        exe = self.base / "程序 space ' & app.exe"
        exe.write_bytes(b'executable')
        with patch.object(winreg, 'CreateKey') as key, patch.object(winreg, 'SetValueEx') as write, patch('codex_backup.bootstrap_windows._run') as run:
            request_restart_resume(exe, self.base / 'setup')
        run.assert_not_called()
        command = write.call_args.args[-1]
        self.assertIn('"' + str(exe.resolve()) + '"', command)
        self.assertIn('--setup-state', command)
        self.assertIn('setup', command)

    def test_completed_setup_removes_only_its_own_resume_entry(self):
        import winreg
        from codex_backup.bootstrap_windows import clear_restart_resume
        with patch.object(winreg, 'OpenKey'), patch.object(winreg, 'DeleteValue') as delete:
            clear_restart_resume(self.base / 'setup')
        self.assertEqual(delete.call_count, 1)
        self.assertTrue(delete.call_args.args[1].startswith('CodexWorkspaceBackupSetup-'))

    def test_authorization_checks_then_creates_directory_without_exporting_login_data(self):
        with patch('codex_backup.bootstrap_windows.QuarkClient') as client:
            client.return_value.check.side_effect = [RuntimeError('expired'), dict(state='connected')]
            client.return_value.run.return_value = ({'data': {'token': 'not-to-return'}}, [])
            client.return_value.create_folder.return_value = 'opaque-id'
            result = authorize_cloud(self.cfg)
        self.assertEqual(result['state'], 'connected')
        self.assertNotIn('token', json.dumps(result))
        client.return_value.run.assert_called_once_with('login')

    def test_elevated_helper_only_handles_system_components(self):
        script = (Path(__file__).resolve().parents[1] / 'src/codex_backup/setup-wsl.ps1').read_text(encoding='utf-8')
        self.assertIn('Get-AuthenticodeSignature', script)
        self.assertIn('Microsoft Corporation', script)
        self.assertNotIn('import-key', script)
        self.assertNotIn('quark-drive', script)
        self.assertNotIn('--install', script)
        self.assertNotIn('Restart-Computer', script)

    def test_unsigned_installer_is_rejected_by_native_signature_check(self):
        from codex_backup.bootstrap_windows import _powershell, _ps_literal, RESOURCES
        msi = self.base / "unsigned space ' & test.msi"
        msi.write_bytes(b'not a Microsoft installer')
        result = self.base / 'system-result.json'
        command = '& ' + _ps_literal(RESOURCES / 'setup-wsl.ps1') + ' -Action Enable -Msi ' + _ps_literal(msi) + ' -ResultFile ' + _ps_literal(result)
        process = _powershell(command)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(json.loads(result.read_text(encoding='utf-8'))['error_code'], 'SIGNATURE_INVALID')

    def test_root_or_writable_cli_cannot_be_considered_ready(self):
        from codex_backup.bootstrap_windows import inspect_environment
        from types import SimpleNamespace
        cfg = dict(self.cfg, cloud=dict(distribution='fixture', script='/opt/codex-quark/1.0.24/scripts/quark-drive.cjs'))
        for uid, writable in [(b'0', 1), (b'1000', 0)]:
            def run(args, timeout=60):
                if '--quiet' in args: return SimpleNamespace(returncode=0, stdout=b'fixture\n')
                if 'cat' in args: return SimpleNamespace(returncode=1, stdout=b'')
                if 'id' in args: return SimpleNamespace(returncode=0, stdout=uid)
                if 'test' in args: return SimpleNamespace(returncode=writable, stdout=b'')
                return SimpleNamespace(returncode=0, stdout=b'1.0.24' if '/opt/codex-quark/1.0.24/scripts/quark-drive.cjs' in args else b'v24.22.0')
            with self.subTest(uid=uid, writable=writable), patch('codex_backup.bootstrap_windows._system_info', return_value=self.system), patch('codex_backup.bootstrap_windows._run', side_effect=run), patch('codex_backup.bootstrap_windows._registered_id', return_value=''):
                self.assertNotEqual(inspect_environment(cfg)['state'], 'ready')

    def test_automatically_named_foreign_environment_is_not_reused(self):
        from codex_backup.bootstrap_windows import inspect_environment, _owner
        from types import SimpleNamespace
        name = 'CodexWorkspaceBackup-' + _owner(self.cfg).split(':')[-1][:8]
        def run(args, timeout=60):
            if '--quiet' in args: return SimpleNamespace(returncode=0, stdout=name.encode())
            if 'cat' in args: return SimpleNamespace(returncode=1, stdout=b'')
            if 'id' in args: return SimpleNamespace(returncode=0, stdout=b'1000')
            if 'test' in args: return SimpleNamespace(returncode=1, stdout=b'')
            return SimpleNamespace(returncode=0, stdout=b'1.0.24' if '/opt/codex-quark/1.0.24/scripts/quark-drive.cjs' in args else b'v24.22.0')
        with patch('codex_backup.bootstrap_windows._system_info', return_value=self.system), patch('codex_backup.bootstrap_windows._run', side_effect=run), patch('codex_backup.bootstrap_windows._registered_id', return_value=''):
            self.assertNotEqual(inspect_environment(self.cfg)['state'], 'ready')
