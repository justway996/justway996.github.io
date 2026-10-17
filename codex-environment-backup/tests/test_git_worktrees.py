import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from codex_backup.archive import seal
from codex_backup.collect import collect
from codex_backup.model import filesystem_path, load_config, logical_path
from codex_backup.restore import restore


class GitWorktreeTests(unittest.TestCase):
    def setUp(self):
        work = filesystem_path('.test-work')
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.main = self.source / 'main'
        self.linked = self.source / 'linked'
        self.main.mkdir(parents=True)
        self.git(self.main, 'init', '-b', 'main')
        (self.main / 'code.py').write_text('print(1)', encoding='utf-8')
        self.git(self.main, 'add', '.')
        self.git(self.main, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'base')
        self.git(self.main, 'worktree', 'add', '-b', 'unfinished', str(logical_path(self.linked)))
        (self.linked / 'code.py').write_text('print(2)', encoding='utf-8')
        self.git(self.linked, 'add', 'code.py')
        (self.linked / 'code.py').write_text('print(3)', encoding='utf-8')
        (self.linked / 'untracked.txt').write_text('ongoing', encoding='utf-8')
        self.config = self.base / 'config.json'
        self.config.write_text(json.dumps(dict(format_version=1, codex_home=str(logical_path(self.base / 'codex')),
            data_dir=str(logical_path(self.base / 'data')), roots=[dict(id='p', path=str(logical_path(self.source)), kind='project')])), encoding='utf-8')

    def git(self, directory, *args):
        path = logical_path(directory)
        return subprocess.run(['git', '-c', 'safe.directory=' + path.as_posix(), '-C', str(path), *args],
            check=True, capture_output=True).stdout

    def test_worktree_and_index_survive_with_original_directory_unavailable(self):
        before = self.git(self.linked, 'status', '--porcelain=v1', '-uall')
        stage = self.base / 'stage'
        manifest = collect(load_config(self.config), stage)
        self.assertTrue(manifest['complete'])
        self.assertEqual(len(manifest['git_worktrees']), 1)
        snapshot = seal(stage, self.base / 'outbox', b'k' * 32)
        self.source.rename(self.base / 'original-offline')
        destination = self.base / 'restored'
        report = restore(snapshot, destination, b'k' * 32)
        linked = destination / 'roots/p/linked'
        self.assertEqual(self.git(linked, 'status', '--porcelain=v1', '-uall'), before)
        self.assertEqual(self.git(linked, 'branch', '--show-current').strip(), b'unfinished')
        common = self.git(linked, 'rev-parse', '--git-common-dir').decode('utf-8').strip()
        self.assertEqual(logical_path(Path(common).resolve()), logical_path((destination / 'roots/p/main/.git').resolve()))
        self.assertEqual(report['git_worktrees']['restored'], 1)
        self.assertFalse(report['git_worktrees']['pending'])

    def test_common_git_directory_outside_scope_remains_an_explicit_gap(self):
        cfg = load_config(self.config)
        cfg['roots'][0]['path'] = str(logical_path(self.linked))
        manifest = collect(cfg, self.base / 'stage')
        self.assertFalse(manifest['complete'])
        self.assertEqual(manifest.get('git_worktrees', []), [])

    def test_worktree_pointer_cannot_be_rewritten_outside_restored_roots(self):
        stage = self.base / 'stage'
        manifest = collect(load_config(self.config), stage)
        manifest['git_worktrees'] = [dict(path='roots/p/linked/.git', target='../outside', common='roots/p/main/.git')]
        (stage / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        snapshot = seal(stage, self.base / 'outbox', b'k' * 32)
        destination = self.base / 'never'
        with self.assertRaises(ValueError):
            restore(snapshot, destination, b'k' * 32)
        self.assertFalse(destination.exists())
