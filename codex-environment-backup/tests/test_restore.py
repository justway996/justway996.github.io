from pathlib import Path
import unittest

from test_archive import ArchiveTests
from codex_backup.restore import restore, safe_member, export_chats


class RestoreTests(ArchiveTests):
    def test_directly_selected_sessions_root_exports_messages(self):
        import json
        target = self.base / 'export'
        sessions = target / 'roots/sessions'
        sessions.mkdir(parents=True)
        (sessions / 'one.jsonl').write_text(json.dumps(dict(type='response_item', payload=dict(type='message', role='user', content=[dict(text='resume')]))))
        report = export_chats(target, dict(roots=[dict(id='sessions', path='C:/old/.codex/sessions/2026/10/16', kind='codex')]))
        self.assertEqual(report['exported_messages'], 1)

    def test_restore_to_empty_directory(self):
        target = self.base / 'new-computer'
        report = restore(self.snapshot(), target, self.key)
        self.assertEqual((target / 'roots/p/秘密.txt').read_bytes(), self.file.read_bytes())
        self.assertTrue(report['files_verified'])
        self.assertFalse(report['project_verified'])
        self.assertNotEqual(report['state'], 'ready_to_continue')
        self.assertTrue((target / 'CONTINUE.md').is_file())

    def test_existing_files_preserved(self):
        target = self.base / 'existing'
        target.mkdir()
        (target / 'important.txt').write_text('keep')
        with self.assertRaises(FileExistsError):
            restore(self.snapshot(), target, self.key)
        self.assertEqual((target / 'important.txt').read_text(), 'keep')

    def test_wrong_key_leaves_no_published_destination(self):
        with self.assertRaises(ValueError):
            restore(self.snapshot(), self.base / 'never', b'x' * 32)
        self.assertFalse((self.base / 'never').exists())

    def test_windows_unsafe_names(self):
        for value in ['../escape', '/abs', 'C:/abs', 'a\\b', 'a:stream', 'a/../b',
                      'a/./b', 'NUL.txt', 'foo.', 'foo ', 'a\x00b']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_member(value)
