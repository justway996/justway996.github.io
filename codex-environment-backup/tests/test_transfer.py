import json
from pathlib import Path
import shutil
import tempfile
import unittest
from codex_backup.transfer import publish, list_snapshots, fetch
from codex_backup.collect import sha256


class LocalDrive:
    """Filesystem fake ONLY for transport contract tests; never a real cloud claim."""
    def __init__(self, base):
        self.base = base
        self.fail = False
    def create_folder(self, name, parent):
        target = Path(parent) / name
        target.mkdir(exist_ok=True)
        return str(target)
    def list_children(self, fid):
        return [dict(fid=str(p), file_name=p.name, dir=p.is_dir(), size=p.stat().st_size) for p in Path(fid).iterdir()]
    def upload(self, local, parent):
        if self.fail and local.suffix == '.aes':
            raise OSError('offline')
        p = Path(parent) / local.name
        shutil.copyfile(local, p)
        return dict(fid=str(p))
    def download(self, fid, destination):
        shutil.copyfile(fid, destination)
        return destination


class TransferTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote'
        self.remote.mkdir()
        self.snapshot = self.base / ('a' * 32)
        self.snapshot.mkdir()
        part = self.snapshot / '00000000.aes'
        part.write_bytes(b'encrypted-fixture')
        (self.snapshot / 'envelope.json').write_text(json.dumps(dict(format_version=1, snapshot_id=self.snapshot.name,
            parts=[dict(name=part.name, size=part.stat().st_size, sha256=sha256(part))])))
        (self.snapshot / 'COMPLETE.json').write_text(json.dumps(dict(format_version=1, snapshot_id=self.snapshot.name,
            envelope_sha256=sha256(self.snapshot / 'envelope.json'))))
        self.client = LocalDrive(self.remote)

    def test_publish_discover_fetch_without_catalog(self):
        report = publish(self.snapshot, self.client, str(self.remote))
        self.assertEqual(report['state'], 'cloud_verified')
        refs = list_snapshots(self.client, str(self.remote))
        self.assertEqual(len(refs), 1)
        target = fetch(refs[0], self.client, self.base / 'inbox')
        self.assertEqual(sha256(target / '00000000.aes'), sha256(self.snapshot / '00000000.aes'))

    def test_interruption_does_not_publish_complete(self):
        self.client.fail = True
        with self.assertRaises(OSError):
            publish(self.snapshot, self.client, str(self.remote))
        self.assertEqual(list_snapshots(self.client, str(self.remote)), [])

    def test_corrupted_cloud_volume_not_restorable(self):
        publish(self.snapshot, self.client, str(self.remote))
        (self.remote / self.snapshot.name / '00000000.aes').write_bytes(b'bad')
        refs = list_snapshots(self.client, str(self.remote))
        with self.assertRaises(ValueError):
            fetch(refs[0], self.client, self.base / 'inbox')

    def test_local_corruption_blocks_complete_publication(self):
        (self.snapshot / '00000000.aes').write_bytes(b'changed-after-seal')
        with self.assertRaises(ValueError):
            publish(self.snapshot, self.client, str(self.remote))
        self.assertFalse(list(self.remote.glob('*/COMPLETE.json')))

    def test_mutation_during_upload_uses_fixed_manifest_hash(self):
        client = self.client
        original = client.upload
        def changing_upload(local, parent):
            if local.suffix == '.aes':
                local.write_bytes(b'mutated while uploading')
            return original(local, parent)
        client.upload = changing_upload
        with self.assertRaises(ValueError):
            publish(self.snapshot, client, str(self.remote))
        self.assertFalse(list(self.remote.glob('*/COMPLETE.json')))
