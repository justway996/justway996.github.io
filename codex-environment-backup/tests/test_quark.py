import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from codex_backup.quark import QuarkClient, parse_output


class QuarkTests(unittest.TestCase):
    def test_existing_version_folder_is_reused_without_create_command(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            with patch.object(client, 'list_children', return_value=[dict(file_name='version', dir=True, fid='existing')]), \
                    patch.object(client, 'run', return_value=({'data': {'fid': 'replacement'}}, [])) as run:
                self.assertEqual(client.create_folder('version', 'parent'), 'existing')
                run.assert_not_called()

    def test_conflicting_or_ambiguous_version_folder_is_rejected(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            for items in [[dict(file_name='version', dir=False, fid='file')],
                          [dict(file_name='version', dir=True, fid='one'), dict(file_name='version', dir=True, fid='two')]]:
                with self.subTest(items=items), patch.object(client, 'list_children', return_value=items), \
                        patch.object(client, 'run', return_value=({'data': {'fid': 'replacement'}}, [])) as run:
                    with self.assertRaisesRegex(ValueError, 'ambiguous|conflict'):
                        client.create_folder('version', 'parent')
                    run.assert_not_called()

    def test_missing_version_folder_is_created(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            with patch.object(client, 'list_children', return_value=[]), \
                    patch.object(client, 'run', return_value=({'data': {'fid': 'created'}}, [])) as run:
                self.assertEqual(client.create_folder('version', 'parent'), 'created')
                run.assert_called_once_with('create-folder', '--dir-path', 'version', '--parent-fid', 'parent')

    def test_partial_failure_is_failure_even_with_zero_exit(self):
        lines = [dict(type='list', code=0, data={'fileId': 'one'}),
                 dict(type='result', code=31003, data={'successCount': 1, 'failedCount': 1})]
        with self.assertRaises(RuntimeError):
            parse_output('\n'.join(json.dumps(x) for x in lines), 0)

    def test_exit_failure_overrides_success_result(self):
        with self.assertRaises(RuntimeError):
            parse_output('{"type":"result","code":0,"data":{}}', 1)

    def test_missing_result_and_noise_rejected(self):
        for text in ['', 'not-json', '{"type":"progress"}']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                parse_output(text, 0)

    def test_valid_artifact_and_notice_preserved(self):
        output = '\n'.join(json.dumps(x) for x in [dict(type='result', code=0, data={'hasMore': False}, notice={'text': 'real notice'}),
                          dict(type='artifact', data={'file_path': '/tmp/list.jsonl'})])
        result, records = parse_output(output, 0)
        self.assertEqual(result['notice']['text'], 'real notice')
        self.assertEqual(records[-1]['type'], 'artifact')

    def test_official_download_result_copies_file_in_private_download_directory(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            base = Path(temp)
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, base)
            downloads = []
            def linux(path):
                return '/runtime' + ('/' + Path(path).resolve().relative_to(base.resolve()).as_posix() if Path(path).resolve() != base.resolve() else '')
            def windows(path):
                return base / Path(path).relative_to('/runtime')
            def response(*args):
                self.assertEqual(args[:4], ('download', '--fid', 'fid', '--output-dir'))
                file = windows(args[4]) / 'part.aes'
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b'ciphertext')
                downloads.append(file)
                return {'data': {'fileName': 'part.aes', 'filePath': linux(file)}}, []
            with patch.object(client, 'linux_path', side_effect=linux), \
                    patch.object(client, 'windows_path', side_effect=windows), \
                    patch.object(client, 'run', side_effect=response):
                destination = base / 'copied.aes'
                client.download('fid', destination)
                self.assertEqual(destination.read_bytes(), b'ciphertext')
                self.assertTrue(all(not file.exists() for file in downloads))

    def test_official_download_rejects_output_outside_private_directory(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            with patch.object(client, 'linux_path', return_value='/runtime'), \
                    patch.object(client, 'run', return_value=({'data': {'filePath': '/runtime/../../config.json'}}, [])):
                with self.assertRaisesRegex(RuntimeError, 'Unexpected download output location'):
                    client.download('fid', Path(temp) / 'copied')

    def test_official_cli_receives_codex_channel_and_private_working_directory(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            output = subprocess.CompletedProcess([], 0, b'{"type":"result","code":0,"data":{}}', b'')
            with patch.object(client, 'linux_path', return_value='/runtime with spaces'), \
                    patch.object(client, 'wsl', side_effect=lambda *args, **kwargs: subprocess.CompletedProcess([], 1, b'', b'') if args[0] == 'test' else output) as wsl:
                client.run('browse', '--parent-fid', '0')
                args = wsl.call_args.args
                self.assertIn('CODEX_ENV=1', args)
                self.assertIn('--chdir=/runtime with spaces', args)
                self.assertIn('HOME=/runtime with spaces', args)

    def test_writable_cli_install_rejected_before_using_shared_authorization(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            with patch.object(client, 'linux_path', return_value='/runtime'), \
                    patch.object(client, 'wsl', return_value=subprocess.CompletedProcess([], 0, b'', b'')):
                with self.assertRaisesRegex(RuntimeError, 'read-only'):
                    client.run('browse', '--parent-fid', '0')

    def test_oversize_volume_stopped_before_uploading_unrestorable_data(self):
        Path('.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            file = Path(temp) / 'oversize.aes'
            with file.open('wb') as stream:
                stream.truncate(50 * 1024 * 1024 + 1)
            client = QuarkClient({'distribution': 'CodexBackup', 'script': '/opt/quark/scripts/quark-drive.cjs'}, Path(temp))
            with patch.object(client, 'linux_path', return_value='/runtime/file'), \
                    patch.object(client, 'run', return_value=({'data': {'fids': ['uploaded']}}, [])) as run:
                with self.assertRaisesRegex(ValueError, '32 MiB'):
                    client.upload(file, 'parent')
                run.assert_not_called()
