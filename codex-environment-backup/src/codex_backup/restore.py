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
from .model import filesystem_path, logical_path, safe_id, write_json
from .projects import write_project_index


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


def validate_directory_links(rows, root_ids, members):
    if not isinstance(rows, list):
        raise ValueError('Invalid directory link plan')
    directories = {str(safe_member(info.filename)).casefold() for info in members if info.is_dir()}
    occupied = {str(safe_member(info.filename)).casefold() for info in members}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'target'} or not all(isinstance(value, str) for value in row.values()):
            raise ValueError('Invalid directory link entry')
        path, target = safe_member(row['path']), safe_member(row['target'])
        for value in [path, target]:
            if len(value.parts) < 2 or value.parts[0] != 'roots' or value.parts[1] not in root_ids:
                raise ValueError('Unexpected directory link root')
        key = str(path).casefold()
        if key in seen or key in occupied or str(target).casefold() not in directories or str(path.parent).casefold() not in directories:
            raise ValueError('Directory link conflicts with archive or lacks a captured target')
        seen.add(key)


def restore_directory_links(destination, rows):
    restored, pending = 0, []
    for row in rows:
        path, target = destination / row['path'], destination / row['target']
        try:
            import os
            if os.name == 'nt':
                create_junction(path, target)
                if not path.is_dir() or logical_path(path.resolve()) != logical_path(target.resolve()):
                    raise OSError('Restored directory junction does not resolve to captured target')
            else:
                path.symlink_to(os.path.relpath(target, path.parent), target_is_directory=True)
            restored += 1
        except OSError as exc:
            pending.append(dict(**row, error=f'{type(exc).__name__}: {exc}'))
    return dict(restored=restored, pending=pending)


def create_junction(path, target):
    # Native substitute names avoid _winapi.CreateJunction's MAX_PATH check and
    # its incorrect prefix when passed an already extended target path.
    import ctypes
    from ctypes import wintypes
    import struct
    name = str(logical_path(target))
    substitute = ('\\??\\UNC\\' + name[2:] if name.startswith('\\\\') else '\\??\\' + name).encode('utf-16le')
    display = name.encode('utf-16le')
    names = substitute + b'\0\0' + display + b'\0\0'
    if len(names) + 16 > 16384:
        raise OSError('Directory junction target exceeds Windows reparse buffer limit')
    payload = struct.pack('<IHHHHHH', 0xA0000003, len(names) + 8, 0,
                          0, len(substitute), len(substitute) + 2, len(display)) + names
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    control = kernel.DeviceIoControl
    control.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    control.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    path.mkdir()
    try:
        handle = create(str(path), 0x40000000, 0, None, 3, 0x02200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            buffer = ctypes.create_string_buffer(payload)
            returned = wintypes.DWORD()
            if not control(handle, 0x000900A4, buffer, len(payload), None, 0, ctypes.byref(returned), None):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            close(handle)
    except OSError:
        path.rmdir()
        raise


def validate_git_worktrees(rows, root_ids, members):
    if not isinstance(rows, list):
        raise ValueError('Invalid Git worktree plan')
    files = {str(safe_member(info.filename)) for info in members if not info.is_dir()}
    directories = {str(safe_member(info.filename)) for info in members if info.is_dir()}
    seen_paths, seen_targets = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'target', 'common'} or not all(isinstance(value, str) for value in row.values()):
            raise ValueError('Invalid Git worktree entry')
        path, target, common = (safe_member(row[key]) for key in ['path', 'target', 'common'])
        for value in [path, target, common]:
            if len(value.parts) < 2 or value.parts[0] != 'roots' or value.parts[1] not in root_ids:
                raise ValueError('Unexpected Git worktree root')
        required = {str(path), str(target / 'gitdir'), str(target / 'commondir'), str(common / 'HEAD'), str(common / 'config')}
        if path.name != '.git' or target.parent != common / 'worktrees' or not required <= files or not {str(target), str(common / 'objects')} <= directories:
            raise ValueError('Git worktree administration was not captured')
        if str(path).casefold() in seen_paths or str(target).casefold() in seen_targets:
            raise ValueError('Duplicate Git worktree mapping')
        seen_paths.add(str(path).casefold())
        seen_targets.add(str(target).casefold())


def restore_git_worktrees(destination, rows):
    restored, pending, changes = 0, [], []
    for row in rows:
        path, target, common = (destination / row[key] for key in ['path', 'target', 'common'])
        try:
            for file, value in [(target / 'commondir', logical_path(common).as_posix() + '\n'),
                                (target / 'gitdir', logical_path(path).as_posix() + '\n'),
                                (path, 'gitdir: ' + logical_path(target).as_posix() + '\n')]:
                before = hashlib.sha256(file.read_bytes()).hexdigest()
                file.write_text(value, encoding='utf-8')
                changes.append(dict(path=file.relative_to(destination).as_posix(), original_sha256=before,
                    restored_sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
            restored += 1
        except OSError as exc:
            pending.append(dict(**row, error=f'{type(exc).__name__}: {exc}'))
    return dict(restored=restored, pending=pending, rewritten_files=changes)


def restore(snapshot: Path, destination: Path, recovery_key: bytes) -> dict:
    destination = filesystem_path(destination)
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
            allowed = expected | {'manifest.json'}
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
                if not info.is_dir() and str(path) not in allowed:
                    raise ValueError('Unlisted archive content')
            directory_links = manifest.get('directory_links', [])
            validate_directory_links(directory_links, root_ids, zf.infolist())
            git_worktrees = manifest.get('git_worktrees', [])
            validate_git_worktrees(git_worktrees, root_ids, zf.infolist())
            # Validation above finishes before the first archive file is written.
            for info in zf.infolist():
                output = target / safe_member(info.filename)
                if info.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, output.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
            for row in directory_links:
                if (target / row['path']).exists():
                    raise ValueError('Directory link conflicts with extracted content')
            mapping = {r['id']: dict(source=r['path'], restored=str(logical_path(destination / 'roots' / r['id'])),
                                    vault_name=r.get('name')) for r in manifest['roots']}
            write_json(target / 'PATH-MAPPING.json', mapping)
            write_project_index(target, destination, manifest)
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
                '3. 读取 PROJECTS.md/PROJECTS.json 核对依赖、锁文件、启动/验证命令；检查数据库/素材与授权；未知不得当成已通过。\n'
                '4. 让用户确认接续任务，执行已授权验证后再继续开发。\n\n'
                '活动账号数据库未被覆盖；自动任务、插件、规则未被激活。代码运行及跨机接续尚未验证。\n', encoding='utf-8')
            (target / 'START-HERE.md').write_text('先读 CONTINUE.md。原始工程和知识库在 roots/<id>。恢复结果尚需环境与项目运行验证。\n', encoding='utf-8')
        if destination.exists():
            # Empty destination only; no recursive deletion.
            destination.rmdir()
        target.rename(destination)
        report['git_worktrees'] = restore_git_worktrees(destination, git_worktrees)
        report['directory_links'] = restore_directory_links(destination, directory_links)
        report['file_verification_scope'] = 'Snapshot bytes verified before recorded Git pointer rewrites; immutable snapshot retains originals'
        if report['directory_links']['pending'] or report['git_worktrees']['pending']:
            report['state'] = 'restored_needs_path_repairs'
        write_json(destination / 'RESTORE-REPORT.json', report)
    return report
