import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from codex_backup.installer import install_release, create_shortcuts
from codex_backup.model import filesystem_path


class InstallerTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def payload(self, extra=None, bad_hash=False):
        files = {'release.json': json.dumps({'version': '0.3.0'}).encode(),
            'CodexEnvironmentBackup.exe': b'app', 'CodexEnvironmentBackupWorker.exe': b'worker',
            '_internal/runtime.dat': b'runtime'}
        sums = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in files.items())
        if bad_hash:
            sums = '0' * 64 + sums[64:]
        files['SHA256SUMS.txt'] = sums.encode()
        path = self.base / 'payload.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, data in files.items():
                z.writestr('bundle/' + name, data)
            if extra:
                for name, data in extra:
                    z.writestr(name, data)
        return path

    def test_install_and_repeat_keep_existing_user_configuration(self):
        target = self.base / "应用 space ' & folder"
        target.mkdir()
        (target / 'config.json').write_bytes(b'user configuration')
        payload = self.payload()
        first = install_release(payload, target)
        second = install_release(payload, target)
        self.assertEqual(first['installed'], second['installed'])
        self.assertEqual(Path(first['installed']).name, '0.3.0')
        self.assertEqual((Path(first['installed']) / 'CodexEnvironmentBackup.exe').read_bytes(), b'app')
        self.assertEqual((target / 'config.json').read_bytes(), b'user configuration')
        self.assertTrue(second['reused'])

    def test_bad_hash_rejected_before_any_installation(self):
        target = self.base / 'apps'
        with self.assertRaises(ValueError):
            install_release(self.payload(bad_hash=True), target)
        self.assertFalse(target.exists())

    def test_long_destination_installs_repeats_and_preserves_modified_files(self):
        with tempfile.TemporaryDirectory(dir=filesystem_path(self.base)) as temp:
            target = Path(temp) / ('a' * 80) / ('b' * 80)
            self.assertGreater(len(str(target.resolve() / '0.3.0/_internal/runtime.dat')), 260)
            payload = self.payload()
            first = install_release(payload, target)
            self.assertFalse(first['installed'].startswith('\\\\?\\'))
            self.assertTrue(install_release(payload, target)['reused'])
            runtime = filesystem_path(Path(first['installed']) / '_internal/runtime.dat')
            self.assertEqual(runtime.read_bytes(), b'runtime')
            runtime.write_bytes(b'user modified')
            with self.assertRaises(ValueError):
                install_release(payload, target)
            self.assertEqual(runtime.read_bytes(), b'user modified')

    def test_paths_and_unlisted_files_are_rejected_before_writes(self):
        names = ['../escaped', '/absolute', 'C:/drive', '//host/share', 'bundle/../escape',
            'bundle/C:stream', 'bundle/back\\slash', 'bundle/unlisted.txt', 'other/release.json']
        for name in names:
            with self.subTest(name=name):
                target = self.base / 'apps'
                with self.assertRaises(ValueError):
                    install_release(self.payload([(name, b'bad')]), target)
                self.assertFalse(target.exists())

    def test_duplicate_members_and_symlinks_are_rejected(self):
        for link in [False, True]:
            payload = self.payload()
            with zipfile.ZipFile(payload, 'a') as z:
                if link:
                    info = zipfile.ZipInfo('bundle/link')
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(info, 'elsewhere')
                else:
                    z.writestr('bundle/release.json', b'{}')
            with self.assertRaises(ValueError):
                install_release(payload, self.base / 'apps')

    def test_existing_modified_version_is_not_overwritten(self):
        payload = self.payload()
        installed = Path(install_release(payload, self.base / 'apps')['installed'])
        exe = installed / 'CodexEnvironmentBackup.exe'
        exe.write_bytes(b'user modified')
        with self.assertRaises(ValueError):
            install_release(payload, self.base / 'apps')
        self.assertEqual(exe.read_bytes(), b'user modified')

    def test_shortcut_paths_are_data_in_encoded_powershell(self):
        exe = self.base / "应用 space ' & directory" / 'app.exe'
        with patch('codex_backup.installer.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps([str(self.base / 'desktop.lnk')]).encode()
            created = create_shortcuts(exe)
        import base64
        args = run.call_args.args[0]
        self.assertIn('-EncodedCommand', args)
        decoded = base64.b64decode(args[-1]).decode('utf-16le')
        self.assertIn(str(exe).replace("'", "''"), decoded)
        self.assertIn("$shortcut.Arguments = 'setup'", decoded)
        self.assertEqual(created, [self.base / 'desktop.lnk'])

    def test_native_shortcut_creation_in_isolated_unicode_directory(self):
        import base64
        import subprocess
        original_run = subprocess.run
        folder = self.base / "中文 shortcut ' & space"
        exe = self.base / "程序 ' & space" / 'app.exe'
        def isolated_run(args, **kwargs):
            code = base64.b64decode(args[-1]).decode('utf-16le')
            start = code.index('$locations=@(')
            end = code.index('\n$created=', start)
            code = code[:start] + "$locations=@('" + str(folder).replace("'", "''") + "')" + code[end:]
            return original_run([*args[:-1], base64.b64encode(code.encode('utf-16le')).decode('ascii')], **kwargs)
        with patch('codex_backup.installer.subprocess.run', side_effect=isolated_run):
            links = create_shortcuts(exe)
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0].is_file())
        self.assertTrue(links[0].is_relative_to(folder))
