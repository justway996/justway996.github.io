import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_backup.model import load_config, discover


class ConfigTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / '.test-work'
        work.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def config(self, **kwargs):
        data = dict(format_version=1, codex_home=str(self.root / 'codex'),
                    roots=[dict(id='project', path=str(self.root / '项目 空格'), kind='project')],
                    data_dir=str(self.root / 'backup'))
        data.update(kwargs)
        path = self.root / 'config.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            load_config(self.config(format_version=99))

    def test_output_inside_source_rejected(self):
        with self.assertRaises(ValueError):
            load_config(self.config(data_dir=str(self.root / '项目 空格' / 'backup')))

    def test_duplicate_and_unsafe_ids_rejected(self):
        for ids in [('a', 'a'), ('../escape', 'b'), ('CON', 'b')]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                load_config(self.config(roots=[dict(id=i, path=str(self.root / i), kind='project') for i in ids]))

    def test_missing_source_is_visible(self):
        result = discover(load_config(self.config()))
        self.assertEqual(result['roots'][0]['state'], 'missing')

    def test_config_sqlite_overrides_environment(self):
        home = self.root / 'codex'
        home.mkdir()
        (home / 'config.toml').write_text('sqlite_home = "other-db"', encoding='utf-8')
        with patch.dict(os.environ, {'CODEX_SQLITE_HOME': str(self.root / 'env-db')}):
            result = discover(load_config(self.config()))
        self.assertEqual(Path(result['sqlite_home']), (self.root / 'other-db').resolve())

    def test_chinese_vaults_and_same_source_deduplicated(self):
        source = self.root / '项目 空格'
        source.mkdir()
        cfg = load_config(self.config(roots=[dict(id='project', path=str(source), kind='project'),
                                             dict(id='vault', path=str(source), kind='vault')]))
        result = discover(cfg)
        self.assertEqual(len(result['roots']), 1)
        self.assertEqual(result['aliases']['vault'], 'project')

    def test_external_sqlite_root_is_included_with_codex_scope(self):
        home = self.root / 'codex'
        home.mkdir()
        external = self.root / 'external'
        external.mkdir()
        (home / 'config.toml').write_text(f'sqlite_home = "{external.as_posix()}"', encoding='utf-8')
        cfg = load_config(self.config(roots=[dict(id='codex', path=str(home), kind='codex')]))
        paths = [Path(r['path']) for r in discover(cfg)['roots']]
        self.assertIn(external.resolve(), paths)

    def test_partial_sessions_selection_does_not_expand_to_entire_codex(self):
        home = self.root / 'codex'
        (home / 'sessions').mkdir(parents=True)
        cfg = load_config(self.config(roots=[dict(id='sessions', path=str(home / 'sessions'), kind='codex')]))
        self.assertEqual(len(discover(cfg)['roots']), 1)
