import json
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from codex_backup.collect import collect
from codex_backup.model import load_config


class CollectTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.cfgpath = self.base / 'config.json'
        self.cfgpath.write_text(json.dumps(dict(format_version=1, codex_home=str(self.base / 'codex'),
            data_dir=str(self.base / 'data'), roots=[dict(id='p', path=str(self.source), kind='project')])), encoding='utf-8')

    def test_live_wal_is_captured(self):
        db = sqlite3.connect(self.source / 'chat.sqlite')
        self.addCleanup(db.close)
        db.execute('pragma journal_mode=wal')
        db.execute('create table chats(body text)')
        db.execute("insert into chats values ('not-checkpointed')")
        db.commit()
        dest = self.base / 'stage'
        result = collect(load_config(self.cfgpath), dest)
        with closing(sqlite3.connect(dest / 'roots/p/chat.sqlite')) as copy:
            self.assertEqual(copy.execute('select body from chats').fetchone()[0], 'not-checkpointed')
        self.assertFalse(any(f['path'].endswith(('-wal', '-shm')) for f in result['files']))

    def test_git_changes_and_ignored_business_files_are_saved(self):
        def git(*args):
            return subprocess.run(['git', '-c', f'safe.directory={self.source.as_posix()}', '-C', str(self.source), *args], check=True, capture_output=True).stdout
        git('init', '-b', 'work')
        (self.source / 'main.py').write_text('print(1)', encoding='utf-8')
        git('add', '.')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'base')
        (self.source / 'main.py').write_text('print(2)', encoding='utf-8')
        git('add', 'main.py')
        (self.source / 'main.py').write_text('print(3)', encoding='utf-8')
        (self.source / 'untracked.txt').write_text('unfinished', encoding='utf-8')
        (self.source / '.gitignore').write_text('business.dat', encoding='utf-8')
        (self.source / 'business.dat').write_bytes(b'important')
        before = git('status', '--porcelain=v1', '-uall')
        dest = self.base / 'stage'
        collect(load_config(self.cfgpath), dest)
        copied = dest / 'roots/p'
        after = subprocess.run(['git', '-c', f'safe.directory={copied.as_posix()}', '-C', str(copied), 'status', '--porcelain=v1', '-uall'], check=True, capture_output=True).stdout
        self.assertEqual(before, after)
        self.assertEqual((copied / 'business.dat').read_bytes(), b'important')

    def test_credentials_excluded_and_missing_dependency_reported(self):
        (self.source / 'auth.json').write_text('secret', encoding='utf-8')
        (self.source / '.env').write_text('API_KEY=encrypted-only', encoding='utf-8')
        (self.source / '.git').write_text('gitdir: ../absent-git', encoding='utf-8')
        result = collect(load_config(self.cfgpath), self.base / 'stage')
        paths = [x['path'] for x in result['files']]
        self.assertNotIn('roots/p/auth.json', paths)
        self.assertIn('roots/p/.env', paths)
        self.assertTrue(any(x['state'] == 'unsupported' for x in result['coverage']))

    def test_missing_root_is_not_complete(self):
        cfg = load_config(self.cfgpath)
        cfg['roots'].append(dict(id='missing', path=str(self.base / 'absent'), kind='source'))
        result = collect(cfg, self.base / 'stage')
        self.assertFalse(result['complete'])

    def test_codex_worktree_dependency_locks_are_preserved_and_runtime_locks_reported(self):
        project = self.source / 'worktrees/fixture/project'
        project.mkdir(parents=True)
        for name in ['poetry.lock', 'yarn.lock', 'package-lock.json']:
            (project / name).write_text('exact dependency versions', encoding='utf-8')
        (self.source / '.sqlite-maintenance.lock').write_bytes(b'process lock')
        cfg = load_config(self.cfgpath)
        cfg['roots'][0]['kind'] = 'codex'
        result = collect(cfg, self.base / 'stage')
        self.assertEqual(len(result['files']), 3)
        self.assertTrue(any(x.get('path') == '.sqlite-maintenance.lock' and x['state'] == 'rebuildable' for x in result['coverage']))

    def test_explicit_file_exclusion_is_reported_without_reading(self):
        (self.source / 'installer.bin').write_bytes(b'generated installer')
        (self.source / 'business.txt').write_text('keep', encoding='utf-8')
        cfg = load_config(self.cfgpath)
        cfg['roots'][0]['exclude'] = ['installer.bin']
        result = collect(cfg, self.base / 'stage')
        self.assertEqual([f['path'] for f in result['files']], ['roots/p/business.txt'])
        self.assertTrue(any(x.get('path') == 'installer.bin' and x['reason'] == 'Explicit exclusion' for x in result['coverage']))

    def test_codex_provisioning_guard_is_transient_but_project_file_is_kept(self):
        name = '.codex-provisioning-fixture.guard'
        (self.source / name).write_bytes(b'process lock')
        cfg = load_config(self.cfgpath)
        cfg['roots'][0]['kind'] = 'codex'
        result = collect(cfg, self.base / 'codex-stage')
        self.assertFalse(result['files'])
        self.assertTrue(any(x.get('path') == name and x['state'] == 'rebuildable' for x in result['coverage']))
        cfg['roots'][0]['kind'] = 'project'
        result = collect(cfg, self.base / 'project-stage')
        self.assertEqual([x['path'] for x in result['files']], ['roots/p/' + name])

    def test_codex_browser_login_profile_excluded_but_project_browser_assets_preserved(self):
        profile = self.source / 'browser' / 'profile'
        profile.mkdir(parents=True)
        (profile / 'Cookies').write_bytes(b'private browser session')
        cfg = load_config(self.cfgpath)
        cfg['roots'][0]['kind'] = 'codex'
        result = collect(cfg, self.base / 'codex-stage')
        self.assertNotIn('roots/p/browser/profile/Cookies', {x['path'] for x in result['files']})
        self.assertTrue(any(x.get('path') == 'browser' and x['state'] == 'reauthorize' for x in result['coverage']))
        cfg['roots'][0]['kind'] = 'project'
        result = collect(cfg, self.base / 'project-stage')
        self.assertIn('roots/p/browser/profile/Cookies', {x['path'] for x in result['files']})

    def test_readonly_sqlite_uses_stable_wal_copy_when_api_cannot_open_source(self):
        dbpath = self.source / 'chat.sqlite'
        db = sqlite3.connect(dbpath)
        self.addCleanup(db.close)
        db.execute('pragma journal_mode=wal')
        db.execute('create table chats(body text)')
        db.execute("insert into chats values ('wal-survives')")
        db.commit()
        connect = sqlite3.connect
        def guarded(path, *args, **kwargs):
            if isinstance(path, str) and path == dbpath.as_uri() + '?mode=ro':
                raise sqlite3.OperationalError('unable to open database file')
            return connect(path, *args, **kwargs)
        with patch('codex_backup.collect.sqlite3.connect', side_effect=guarded):
            collect(load_config(self.cfgpath), self.base / 'stage')
        with closing(connect(self.base / 'stage/roots/p/chat.sqlite')) as copied:
            self.assertEqual(copied.execute('select body from chats').fetchone()[0], 'wal-survives')

    def test_readonly_failure_can_happen_during_backup_not_connect(self):
        dbpath = self.source / 'chat.sqlite'
        with closing(sqlite3.connect(dbpath)) as db:
            db.execute('create table chats(body text)')
            db.commit()
        connect = sqlite3.connect
        class DelayedFailure:
            def backup(self, *args, **kwargs):
                raise sqlite3.OperationalError('unable to open database file')
            def close(self):
                pass
        def guarded(path, *args, **kwargs):
            return DelayedFailure() if path == dbpath.as_uri() + '?mode=ro' else connect(path, *args, **kwargs)
        with patch('codex_backup.collect.sqlite3.connect', side_effect=guarded):
            result = collect(load_config(self.cfgpath), self.base / 'stage')
        self.assertTrue(result['complete'])

    def test_fallback_rejects_active_rollback_journal(self):
        dbpath = self.source / 'rollback.sqlite'
        db = sqlite3.connect(dbpath)
        self.addCleanup(db.close)
        db.execute('pragma journal_mode=delete')
        db.execute('pragma cache_size=10')
        db.execute('create table rows(body text)')
        db.executemany('insert into rows values (?)', [('old' * 400,)] * 1000)
        db.commit()
        db.execute("update rows set body=?", ('NEW' * 400,))
        connect = sqlite3.connect
        def guarded(path, *args, **kwargs):
            if path == dbpath.as_uri() + '?mode=ro':
                raise sqlite3.OperationalError('unable to open database file')
            return connect(path, *args, **kwargs)
        with patch('codex_backup.collect.sqlite3.connect', side_effect=guarded):
            with self.assertRaisesRegex(RuntimeError, 'journal'):
                collect(load_config(self.cfgpath), self.base / 'stage')
        db.rollback()
