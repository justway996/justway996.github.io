import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from codex_backup.model import load_config
from codex_backup.scheduler import run_once
from codex_backup.credentials import new_key, read_key
from codex_backup.restore import restore


class EndToEndTests(unittest.TestCase):
    def test_unfinished_project_chat_skill_and_vault_recover(self):
        (Path.cwd() / '.test-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.test-work') as temp:
            base = Path(temp)
            project = base / 'project'
            codex = base / 'codex'
            vault = base / '工作知识库'
            for p in [project, codex / 'sessions', codex / 'skills/custom/scripts', vault / '10_项目']:
                p.mkdir(parents=True)
            (project / 'main.py').write_text('print("resume-ok")', encoding='utf-8')
            (project / 'CONTINUE.md').write_text('接口未完成。先运行 main.py，再接测试 API。', encoding='utf-8')
            (codex / 'sessions/one.jsonl').write_text(json.dumps(dict(type='response_item', payload=dict(type='message', role='user', content=[dict(type='input_text', text='还没做完')]))), encoding='utf-8')
            db = sqlite3.connect(codex / 'thread_history_1.sqlite')
            db.execute('create table thread_items(thread_id text, rollout_ordinal integer, item_json text, primary key(thread_id, rollout_ordinal)) without rowid')
            db.execute('insert into thread_items values (?,?,?)', ('thread', 1, json.dumps(dict(type='userMessage', content=[dict(text='数据库对话')]))))
            db.commit()
            db.close()
            (codex / 'skills/custom/scripts/run.py').write_text('print("skill")', encoding='utf-8')
            (vault / '10_项目/project.md').write_text('---\nstatus: paused\n---\n下一步：补接口\n[[missing-note]]', encoding='utf-8')
            cfg = base / 'config.json'
            cfg.write_text(json.dumps(dict(format_version=1, codex_home=str(codex), data_dir=str(base / 'data'),
                project_status='paused', project_card='vault:10_项目/project.md',
                roots=[dict(id='project', path=str(project), kind='project'), dict(id='codex', path=str(codex), kind='codex'),
                       dict(id='vault', path=str(vault), kind='vault')])) )
            new_key(base / 'data', base / 'offline.key')
            status = run_once(cfg)
            report = restore(Path(status['snapshot']), base / 'new-disk', read_key(base / 'data'))
            run = subprocess.run([__import__('sys').executable, str(base / 'new-disk/roots/project/main.py')], capture_output=True)
            self.assertIn(b'resume-ok', run.stdout)
            self.assertEqual(report['project_status'], 'paused')
            self.assertTrue((base / 'new-disk/roots/codex/skills/custom/scripts/run.py').is_file())
            self.assertTrue(any(x['state'] == 'unresolved' for x in report['links']))
            self.assertTrue(list((base / 'new-disk/chats').glob('*.md')))
            self.assertIn('还没做完', next((base / 'new-disk/chats').glob('*.md')).read_text(encoding='utf-8'))
