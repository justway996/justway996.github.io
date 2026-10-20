import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        project = self.base / 'project'
        (project / 'packaging').mkdir(parents=True)
        (project / 'src/codex_backup').mkdir(parents=True)
        (project / 'src/codex_backup/__init__.py').write_text("__version__ = '0.3.0'", encoding='utf-8')
        (project / 'README.md').write_bytes(b'public readme')
        (project / 'personal-config.json').write_bytes(b'private credential fixture')
        (project / 'skills').mkdir()
        (project / 'dist/CodexEnvironmentBackup/docs').mkdir(parents=True)
        (project / 'dist/CodexEnvironmentBackup/docs/progress.md').write_bytes(b'private progress fixture')
        (project / 'dist/CodexEnvironmentBackup/app.exe').write_bytes(b'application')
        self.whitelist = project / 'packaging/release-files.txt'
        self.whitelist.write_text('README.md\nsrc/codex_backup/__init__.py\npackaging/release-files.txt\n', encoding='utf-8')
        entry = Path(__file__).resolve().parents[1] / 'packaging/package_release.py'
        spec = importlib.util.spec_from_file_location('test_release_builder', entry)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.__file__ = str(project / 'packaging/package_release.py')

    def test_dotted_version_keeps_full_zip_name_and_private_files_out(self):
        destination = self.base / 'CodexEnvironmentBackup-v0.3.0-candidate1'
        result = self.module.package_release(destination, 'source-commit', 133)
        self.assertEqual(Path(result['archive']), destination.with_name(destination.name + '.zip').resolve())
        with zipfile.ZipFile(result['archive']) as archive:
            names = archive.namelist()
        self.assertFalse(any('personal-config' in name or 'progress.md' in name for name in names))
        metadata = json.loads((destination / 'release.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['minimum_mapped_manifest_reader'], '0.2.0')
        self.assertFalse(metadata['source_published'])

    def test_unsafe_or_private_whitelist_fails_before_output_is_created(self):
        for name in ['../personal-config.json', '/absolute', 'C:/drive', 'docs/progress.md']:
            self.whitelist.write_text(name + '\n', encoding='utf-8')
            destination = self.base / 'release'
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.module.package_release(destination, 'commit', 133)
            self.assertFalse(destination.exists())

    def test_duplicate_whitelist_cannot_be_packaged(self):
        self.whitelist.write_text('README.md\nREADME.md\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.module.package_release(self.base / 'release', 'commit', 133)
