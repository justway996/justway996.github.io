import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_backup.bootstrap import download_component, load_setup_state, save_setup_state, setup_lock


class BootstrapDownloadTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = b'verified official component'
        self.spec = dict(name='component.zip', version='1', url='https://example.invalid/component.zip',
            sha256=hashlib.sha256(self.data).hexdigest(), size_bytes=len(self.data))

    def test_download_is_hashed_and_valid_cache_is_reused(self):
        progress = []
        with patch('codex_backup.bootstrap.urllib.request.urlopen', return_value=io.BytesIO(self.data)) as opened:
            first = download_component(self.spec, self.base, lambda done, total: progress.append((done, total)))
            second = download_component(self.spec, self.base)
        self.assertEqual(first, second)
        self.assertEqual(first.read_bytes(), self.data)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(progress[-1], (len(self.data), len(self.data)))

    def test_corruption_and_truncation_never_become_a_component(self):
        for bad in [b'wrong', self.data[:-1], self.data + b'extra']:
            with self.subTest(bad=bad), patch('codex_backup.bootstrap.urllib.request.urlopen', return_value=io.BytesIO(bad)):
                with self.assertRaises(ValueError):
                    download_component(self.spec, self.base)
                self.assertFalse((self.base / self.spec['name']).exists())

    def test_stale_partial_and_bad_cache_are_not_trusted(self):
        (self.base / 'component.zip.part').write_bytes(b'old download')
        (self.base / 'component.zip').write_bytes(b'corrupt cached file')
        with patch('codex_backup.bootstrap.urllib.request.urlopen', return_value=io.BytesIO(self.data)):
            self.assertEqual(download_component(self.spec, self.base).read_bytes(), self.data)

    def test_network_failure_keeps_valid_retry_possible(self):
        with patch('codex_backup.bootstrap.urllib.request.urlopen', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                download_component(self.spec, self.base)
        self.assertFalse((self.base / self.spec['name']).exists())
        with patch('codex_backup.bootstrap.urllib.request.urlopen', return_value=io.BytesIO(self.data)):
            self.assertTrue(download_component(self.spec, self.base).is_file())

    def test_paths_http_and_invalid_digest_are_rejected_before_network(self):
        for changes in [dict(name='../outside'), dict(name='C:stream'), dict(url='http://example.invalid/a'), dict(sha256='unchecked')]:
            with self.subTest(changes=changes), patch('codex_backup.bootstrap.urllib.request.urlopen') as opened:
                with self.assertRaises(ValueError):
                    download_component(dict(self.spec, **changes), self.base)
                opened.assert_not_called()

    def test_state_roundtrip_and_credentials_are_rejected(self):
        path = self.base / 'state.json'
        self.assertEqual(load_setup_state(path), {})
        state = dict(state='restart_required', stage='system', completed=['wsl'])
        save_setup_state(path, state)
        self.assertEqual(load_setup_state(path), state)
        for secret in [dict(token='private'), dict(state='ready', password='private'), dict(completed=[{'key': 'secret'}])]:
            with self.subTest(secret=secret), self.assertRaises(ValueError):
                save_setup_state(path, secret)
        self.assertEqual(load_setup_state(path), state)

    def test_second_setup_is_blocked_and_lock_releases(self):
        with setup_lock(self.base):
            with self.assertRaises(RuntimeError):
                with setup_lock(self.base):
                    pass
        with setup_lock(self.base):
            pass
