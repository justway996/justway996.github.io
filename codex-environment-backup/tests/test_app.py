import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_backup.app import create_config, validate_key_location, action, main
from codex_backup.model import load_config


class AppTests(unittest.TestCase):
    def test_background_entry_works_without_a_console_stream(self):
        with patch('sys.argv', ['worker.exe', 'worker', '--config', 'fixture.json']), patch('sys.stdout', None), patch('codex_backup.app.action', return_value={'state': 'cloud_verified'}):
            main()

    def test_key_rejected_in_automatically_discovered_sqlite_root(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work') as temp:
            root = Path(temp)
            home = root / 'codex'
            db = root / 'external-db'
            home.mkdir()
            db.mkdir()
            (home / 'config.toml').write_text(f'sqlite_home="{db.as_posix()}"')
            cfgfile = root / 'config.json'
            cfgfile.write_text(json.dumps(dict(format_version=1, codex_home=str(home), data_dir=str(root / 'data'),
                roots=[dict(id='codex', path=str(home), kind='codex')])))
            for command in ['new-key', 'import-key']:
                with self.subTest(command=command), self.assertRaises(ValueError):
                    action(command, cfgfile, key_file=db / 'offline.key')

    def test_help_runs_without_global_install(self):
        p = subprocess.run([sys.executable, '-m', 'codex_backup', '--help'], capture_output=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn(b'inspect', p.stdout)

    def test_config_has_explicit_scope_and_does_not_enable_cloud(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work') as temp:
            root = Path(temp)
            cfgfile = root / 'config.json'
            create_config(cfgfile, [root / 'project'], root / 'data', include_codex=False, include_vaults=True)
            cfg = load_config(cfgfile)
            self.assertFalse(cfg['cloud']['enabled'])
            self.assertEqual(len([r for r in cfg['roots'] if r['kind'] == 'vault']), 2)
            with self.assertRaises(ValueError):
                validate_key_location(cfg, root / 'project/key.txt')
            with self.assertRaises(ValueError):
                action('import-key', cfgfile, key_file=root / 'project/key.txt')
