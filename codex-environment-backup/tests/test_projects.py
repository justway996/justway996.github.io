import json
from pathlib import Path
import tempfile
import unittest

from codex_backup.archive import seal
from codex_backup.collect import collect, sha256
from codex_backup.restore import restore


class ProjectIndexTests(unittest.TestCase):
    def test_project_commands_requirements_and_handoff_hashes_survive_restore(self):
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            base = Path(temp).resolve()
            source = base / 'source'
            (source / 'web/node_modules/dependency').mkdir(parents=True)
            (source / 'web/package.json').write_text(json.dumps(dict(name='fixture', packageManager='pnpm@10.1.0',
                engines=dict(node='>=22'), scripts=dict(dev='vite', test='vitest run'))), encoding='utf-8')
            (source / 'web/pnpm-lock.yaml').write_text('lockfileVersion: 9', encoding='utf-8')
            (source / 'web/AGENTS.md').write_text('Fixture rules', encoding='utf-8')
            (source / 'web/node_modules/dependency/package.json').write_text('{}', encoding='utf-8')
            (source / 'python').mkdir()
            (source / 'python/pyproject.toml').write_text('[project]\nname="fixture-python"\nrequires-python=">=3.12"\n', encoding='utf-8')
            (source / 'python/requirements.txt').write_text('example==1.0', encoding='utf-8')
            (source / 'project-card.md').write_text('Paused; confirm next task', encoding='utf-8')
            cfg = dict(codex_home=str(base / 'codex'), data_dir=str(base / 'data'), _base=str(base),
                roots=[dict(id='p', path=str(source), kind='project')],
                project_card='p/project-card.md', project_status='paused')
            stage = base / 'stage'
            manifest = collect(cfg, stage)
            projects = {p['path']: p for p in manifest['projects']}
            self.assertEqual(set(projects), {'roots/p/web', 'roots/p/python'})
            self.assertEqual(projects['roots/p/web']['declared']['packageManager'], 'pnpm@10.1.0')
            self.assertEqual(projects['roots/p/web']['declared']['scripts']['test'], 'vitest run')
            self.assertEqual(projects['roots/p/python']['declared']['requires-python'], '>=3.12')
            self.assertIn('roots/p/web/pnpm-lock.yaml', projects['roots/p/web']['source_hashes'])
            self.assertEqual(manifest['handoff']['source_hashes']['roots/p/project-card.md'], sha256(source / 'project-card.md'))
            snapshot = seal(stage, base / 'outbox', b'k' * 32)
            destination = base / 'restored'
            report = restore(snapshot, destination, b'k' * 32)
            index = json.loads((destination / 'PROJECTS.json').read_text(encoding='utf-8'))
            self.assertEqual(len(index), 2)
            self.assertEqual(Path(index[0]['restored_path']).parent.parent, destination / 'roots')
            self.assertIn('vitest run', (destination / 'PROJECTS.md').read_text(encoding='utf-8'))
            self.assertFalse(report['project_verified'])
            self.assertEqual(report['project_status'], 'paused')

    def test_invalid_manifest_is_preserved_with_an_explicit_unknown(self):
        with tempfile.TemporaryDirectory(dir='.test-work') as temp:
            base = Path(temp).resolve()
            source = base / 'source'
            source.mkdir()
            (source / 'package.json').write_text('{broken', encoding='utf-8')
            cfg = dict(codex_home=str(base / 'codex'), _base=str(base),
                roots=[dict(id='p', path=str(source), kind='project')])
            manifest = collect(cfg, base / 'stage')
            self.assertTrue(manifest['projects'][0]['unknowns'])
            self.assertEqual((base / 'stage/roots/p/package.json').read_text(), '{broken')
