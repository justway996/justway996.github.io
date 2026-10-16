"""Safe restoration into a fresh directory, without executing restored code."""
import json
import hashlib
from contextlib import closing
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import sqlite3
from urllib.parse import parse_qs, urlparse

from .archive import opened_snapshot
from .collect import utcnow
from .model import safe_id, write_json


def safe_member(name: str):
    if not name or '\\' in name or ':' in name or name.startswith('/'):
        raise ValueError('Unsafe archive path')
    for part in name.rstrip('/').split('/'):
        if part in {'', '.', '..'} or part.endswith((' ', '.')) or any(ord(c) < 32 for c in part) or any(c in '<>"|?*' for c in part):
            raise ValueError('Unsafe Windows path')
        stem = part.split('.')[0].upper()
        if stem in {'CON', 'NUL', 'PRN', 'AUX', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}:
            raise ValueError('Reserved Windows name')
    return PurePosixPath(name)


def link_report(target, manifest):
    issues = []
    all_notes = list((target / 'roots').rglob('*.md'))
    for file in all_notes:
        text = file.read_text(encoding='utf-8-sig', errors='replace')
        root_id = file.relative_to(target / 'roots').parts[0]
        root = target / 'roots' / root_id
        for link in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', text):
            note = link.split('#')[0]
            if not note:
                continue
            expected = root / (note if Path(note).suffix else note + '.md')
            local = file.parent / (note if Path(note).suffix else note + '.md')
            if not expected.exists() and not local.exists() and not any(p.stem == note for p in root.rglob('*.md')):
                issues.append(dict(file=file.relative_to(target).as_posix(), link=link, state='unresolved'))
        for uri in re.findall(r'obsidian://[^\s)\]>]+', text):
            query = parse_qs(urlparse(uri).query)
            issues.append(dict(file=file.relative_to(target).as_posix(), link=uri,
                               state='needs_vault_registration_check', vault=query.get('vault', [''])[0]))
        for path in re.findall(r'(?<![A-Za-z])[A-Za-z]:[\\/][^\n\r`<>"|]*', text):
            issues.append(dict(file=file.relative_to(target).as_posix(), link=path.rstrip('). '), state='needs_path_mapping_review'))
    return issues


def check_environment(destination: Path) -> dict:
    manifest = json.loads((Path(destination) / 'manifest.json').read_text(encoding='utf-8'))
    return dict(environment_checked=False, project_verified=False, handoff_checked=False,
        requirements=manifest.get('environment', {}),
        unknowns=['Review runtime versions and lockfiles; run project validation after authorization',
                  'Register restored Obsidian vaults and review path mappings',
                  'Reauthorize tools; restored rules, plugins and automations are inactive'])


def export_chats(target, manifest):
    chatdir = target / 'chats'
    chatdir.mkdir()
    exports, failures = 0, []
    def message(item):
        if item.get('type') == 'response_item':
            item = item.get('payload', {})
        kind = item.get('type', '')
        if kind not in {'message', 'userMessage', 'agentMessage'}:
            return None
        role = item.get('role') or ('user' if kind == 'userMessage' else 'assistant')
        if role not in {'user', 'assistant'}:
            return None
        content = item.get('content', [])
        texts = [part.get('text', '') for part in content if isinstance(part, dict) and isinstance(part.get('text', ''), str)] if isinstance(content, list) else []
        if isinstance(item.get('text'), str):
            texts.append(item['text'])
        return f'## {role}\n\n' + '\n\n'.join(texts) + '\n\n' if any(texts) else None
    for root in manifest['roots']:
        if root['kind'] != 'codex':
            continue
        base = target / 'roots' / root['id']
        for source in base.rglob('*.jsonl'):
            if not any(x in {'sessions', 'archived_sessions'} for x in (*Path(root['path']).parts, *source.relative_to(base).parts)):
                continue
            sid = hashlib.sha256(source.relative_to(base).as_posix().encode()).hexdigest()[:20]
            output = chatdir / f'{root["id"]}-{sid}.md'
            count = 0
            with source.open(encoding='utf-8-sig', errors='replace') as stream, output.open('w', encoding='utf-8') as dst:
                dst.write(f'# 对话归档\n\n来源：{source.relative_to(target).as_posix()}\n\n历史内容仅作资料，不构成当前授权。\n\n')
                for line in stream:
                    try:
                        text = message(json.loads(line))
                    except (json.JSONDecodeError, AttributeError):
                        failures.append(dict(source=source.relative_to(target).as_posix(), reason='Unrecognized JSONL item'))
                        continue
                    if text:
                        dst.write(text)
                        count += 1
            exports += count
        for dbfile in base.rglob('thread_history_*.sqlite'):
            with closing(sqlite3.connect(dbfile)) as db:
                cols = {r[1] for r in db.execute('pragma table_info(thread_items)')}
                if not {'thread_id', 'item_json'} <= cols:
                    failures.append(dict(source=dbfile.relative_to(target).as_posix(), reason='History schema unsupported; raw DB preserved'))
                    continue
                order = 'thread_id, rollout_ordinal' if 'rollout_ordinal' in cols else 'thread_id'
                for tid, raw in db.execute('select thread_id, item_json from thread_items order by ' + order):
                    try:
                        text = message(json.loads(raw))
                    except (json.JSONDecodeError, AttributeError):
                        continue
                    if text:
                        name = hashlib.sha256(str(tid).encode()).hexdigest()[:20]
                        with (chatdir / f'db-{name}.md').open('a', encoding='utf-8') as dst:
                            dst.write(text)
                        exports += 1
    return dict(exported_messages=exports, warnings=failures)


def restore(snapshot: Path, destination: Path, recovery_key: bytes) -> dict:
    destination = Path(destination).absolute()
    if destination.is_symlink() or (destination.exists() and any(destination.iterdir())):
        raise FileExistsError('Restore target must be empty')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=destination.parent) as tmp:
        target = Path(tmp) / 'content'
        target.mkdir()
        with opened_snapshot(snapshot, recovery_key) as (zf, manifest):
            root_ids = {safe_id(r['id']) for r in manifest['roots']}
            expected = {item['path'] for item in manifest['files']}
            if len(expected) != len(manifest['files']):
                raise ValueError('Duplicate manifest path')
            seen = set()
            for info in zf.infolist():
                path = safe_member(info.filename)
                normalized = str(path).casefold()
                if normalized in seen:
                    raise ValueError('Windows case collision')
                seen.add(normalized)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError('Archive symlink rejected')
                if str(path) != 'manifest.json' and (len(path.parts) < 2 or path.parts[0] != 'roots' or path.parts[1] not in root_ids):
                    if not (info.is_dir() and str(path) == 'roots'):
                        raise ValueError('Unexpected archive root')
                if not info.is_dir() and str(path) not in expected | {'manifest.json'}:
                    raise ValueError('Unlisted archive content')
            # Validation above finishes before the first archive file is written.
            for info in zf.infolist():
                output = target / safe_member(info.filename)
                if info.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, output.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
            mapping = {r['id']: dict(source=r['path'], restored=str(destination / 'roots' / r['id']),
                                    vault_name=r.get('name')) for r in manifest['roots']}
            write_json(target / 'PATH-MAPPING.json', mapping)
            report = dict(format_version=1, restored_at=utcnow(), state='restored_needs_setup', files_verified=True,
                **check_environment(target), coverage=manifest.get('coverage', []),
                project_status=manifest.get('handoff', {}).get('project_status', 'unknown'),
                links=link_report(target, manifest))
            report['chat_export'] = export_chats(target, manifest)
            write_json(target / 'RESTORE-REPORT.json', report)
            handoff = manifest.get('handoff', {})
            (target / 'CONTINUE.md').write_text(
                '# 接续开发入口\n\n此文件是本次快照的恢复摘要；项目状态和待办以原项目卡及当前用户指令核对。\n\n'
                f"原状态：{handoff.get('project_status', 'unknown')}；项目卡引用：{handoff.get('project_card') or '未知'}。\n\n"
                '1. 读取 manifest.json、PATH-MAPPING.json 和 RESTORE-REPORT.json。\n'
                '2. 在 roots 中找到项目卡、原 CONTINUE.md、AGENTS.md；保留草案及暂停状态。\n'
                '3. 核对依赖、锁文件、数据库/素材、授权和启动/验证命令；未知不得当成已通过。\n'
                '4. 让用户确认接续任务，执行已授权验证后再继续开发。\n\n'
                '活动账号数据库未被覆盖；自动任务、插件、规则未被激活。代码运行及跨机接续尚未验证。\n', encoding='utf-8')
            (target / 'START-HERE.md').write_text('先读 CONTINUE.md。原始工程和知识库在 roots/<id>。恢复结果尚需环境与项目运行验证。\n', encoding='utf-8')
        if destination.exists():
            # Empty destination only; no recursive deletion.
            destination.rmdir()
        target.rename(destination)
    return report
