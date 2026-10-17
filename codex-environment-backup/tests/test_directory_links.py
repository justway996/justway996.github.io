import json
import os
from pathlib import Path
import tempfile
import unittest

from codex_backup.archive import seal
from codex_backup.collect import collect
from codex_backup.credentials import new_key
from codex_backup.model import filesystem_path, load_config, logical_path
from codex_backup.restore import restore
from codex_backup.scheduler import run_once


@unittest.skipUnless(os.name == 'nt', 'Windows junction restoration')
class DirectoryLinkTests(unittest.TestCase):
    def setUp(self):
        work = filesystem_path('.test-work')
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.app = self.base / 'app'
        self.deps = self.base / 'deps'
        (self.app / 'node_modules').mkdir(parents=True)
        (self.deps / 'lib').mkdir(parents=True)
        (self.deps / 'lib/code.txt').write_bytes(b'captured dependency')
        self.link = self.app / 'node_modules/lib'
        self.junction(self.deps / 'lib')
        self.config = self.base / 'config.json'
        self.config.write_text(json.dumps(dict(format_version=1,
            codex_home=str(logical_path(self.base / 'codex')), data_dir=str(logical_path(self.base / 'data')),
            roots=[dict(id='app', path=str(logical_path(self.app)), kind='project'),
                   dict(id='deps', path=str(logical_path(self.deps)), kind='source')])), encoding='utf-8')

    def junction(self, target):
        import _winapi
        _winapi.CreateJunction(str(logical_path(target)), str(self.link))

    def test_selected_dependency_link_is_restored_to_captured_target(self):
        stage = self.base / 'stage'
        manifest = collect(load_config(self.config), stage)
        self.assertTrue(manifest['complete'])
        self.assertEqual(manifest['format_version'], 2)
        self.assertEqual(manifest['directory_links'], [dict(path='roots/app/node_modules/lib', target='roots/deps/lib')])
        snapshot = seal(stage, self.base / 'outbox', b'k' * 32)
        (self.deps / 'lib/code.txt').write_bytes(b'changed original')
        destination = self.base / 'restored'
        report = restore(snapshot, destination, b'k' * 32)
        link = destination / 'roots/app/node_modules/lib'
        self.assertTrue(link.is_junction())
        self.assertEqual((link / 'code.txt').read_bytes(), b'captured dependency')
        self.assertEqual(logical_path(link.resolve()), logical_path((destination / 'roots/deps/lib').resolve()))
        self.assertEqual(report['directory_links']['restored'], 1)
        self.assertEqual(report['directory_links']['pending'], [])

    def test_outside_or_excluded_link_target_stays_an_explicit_gap(self):
        for mode in ['outside', 'excluded']:
            with self.subTest(mode=mode):
                cfg = load_config(self.config)
                if mode == 'outside':
                    cfg['roots'] = cfg['roots'][:1]
                else:
                    cfg['roots'][1]['exclude'] = ['lib']
                manifest = collect(cfg, self.base / ('stage-' + mode))
                self.assertFalse(manifest['complete'])
                self.assertEqual(manifest.get('directory_links', []), [])
                self.assertTrue(any(x['state'] == 'unsupported' for x in manifest['coverage']))

    def test_directory_link_can_be_restored_under_a_long_destination(self):
        stage = self.base / 'stage'
        collect(load_config(self.config), stage)
        snapshot = seal(stage, self.base / 'outbox', b'k' * 32)
        destination = self.base / ('a' * 70) / ('b' * 70) / 'restored'
        report = restore(snapshot, destination, b'k' * 32)
        self.assertEqual(report['directory_links']['pending'], [])
        self.assertEqual((destination / 'roots/app/node_modules/lib/code.txt').read_bytes(), b'captured dependency')

    def test_invalid_link_plan_is_rejected_before_destination_is_published(self):
        stage = self.base / 'stage'
        manifest = collect(load_config(self.config), stage)
        for row in [dict(path='roots/app/node_modules/lib', target='../outside'),
                    dict(path='../outside', target='roots/deps/lib'),
                    dict(path='roots/deps/lib/code.txt', target='roots/deps/lib'),
                    dict(path='roots/app/node_modules/lib', target='roots/missing/lib')]:
            with self.subTest(row=row):
                manifest['directory_links'] = [row]
                (stage / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
                snapshot = seal(stage, self.base / 'outbox', b'k' * 32)
                destination = self.base / snapshot.name
                with self.assertRaises(ValueError):
                    restore(snapshot, destination, b'k' * 32)
                self.assertFalse(destination.exists())

    def test_changed_link_target_creates_a_new_version_even_with_same_files(self):
        (self.deps / 'other').mkdir()
        (self.deps / 'other/code.txt').write_bytes(b'other dependency')
        new_key(self.base / 'data', self.base / 'offline.key')
        first = run_once(self.config)
        self.link.rmdir()
        self.junction(self.deps / 'other')
        second = run_once(self.config)
        self.assertFalse(second['unchanged'])
        self.assertNotEqual(first['snapshot_id'], second['snapshot_id'])
