"""Stable file copies and SQLite online backups; originals are never changed."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

from .model import discover, filesystem_path, logical_path, write_json
from .projects import project_index


def sha256(path: Path) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def linked(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def backup_sqlite(source, target):
    started = time.monotonic()
    def progress(status, remaining, total):
        if time.monotonic() - started > 30:
            raise TimeoutError('SQLite backup busy for more than 30 seconds')
    def copy_from(src):
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst, pages=512, progress=progress, sleep=0.05)
            if dst.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite integrity check failed')
    try:
        with closing(sqlite3.connect(logical_path(source).as_uri() + '?mode=ro', uri=True, timeout=5)) as src:
            copy_from(src)
    except sqlite3.OperationalError as exc:
        if 'unable to open' not in str(exc).lower() and 'readonly' not in str(exc).lower():
            raise
        # Read-only sandboxes may forbid SQLite opening/creating SHM. Never use
        # immutable=1 against a live original: take an unchanged main+WAL copy.
        with tempfile.TemporaryDirectory(prefix='.sqlite-read-', dir=target.parent) as temp:
            main = Path(temp) / 'copy.sqlite'
            wal = source.with_name(source.name + '-wal')
            journal = source.with_name(source.name + '-journal')
            def stamp():
                return [(p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in [source, wal]]
            for _ in range(3):
                if journal.exists():
                    raise RuntimeError('Active rollback journal; SQLite backup must retry when idle')
                before = stamp()
                shutil.copyfile(source, main)
                copied_wal = main.with_name(main.name + '-wal')
                if before[1] is not None:
                    shutil.copyfile(wal, copied_wal)
                elif copied_wal.exists():
                    copied_wal.unlink()
                if journal.exists():
                    raise RuntimeError('Rollback journal appeared during copy; retry when idle')
                if before == stamp():
                    break
            else:
                raise RuntimeError('SQLite source kept changing; retry when idle')
            with closing(sqlite3.connect(main)) as copied:
                copy_from(copied)
        return


def copy_stable(source, target):
    source, target = filesystem_path(source), filesystem_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        before = source.stat()
        with source.open('rb') as stream:
            header = stream.read(16)
        if header == b'SQLite format 3\x00':
            backup_sqlite(source, target)
            return
        shutil.copy2(source, target)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and sha256(source) == sha256(target):
            return
    raise RuntimeError(f'Source kept changing: {source}')


def git_evidence(source):
    result = {}
    for name, args in [('status', ['status', '--porcelain=v1', '-uall']),
                       ('branch', ['branch', '--show-current']), ('head', ['rev-parse', 'HEAD'])]:
        try:
            p = subprocess.run(['git', '-C', str(source), *args], capture_output=True, timeout=15)
            result[name] = p.stdout.decode('utf-8', errors='replace').strip() if p.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            result[name] = None
    return result


def captured_path(original, roots, staging):
    real = logical_path(filesystem_path(original).resolve(strict=True))
    for root in roots:
        base = logical_path(Path(root['path']).resolve())
        if real.is_relative_to(base):
            candidate = (Path('roots') / root['id'] / real.relative_to(base)).as_posix()
            if (staging / candidate).exists():
                return candidate
    return None


def collect(config: dict, staging: Path) -> dict:
    staging = filesystem_path(Path(staging).resolve())
    if staging.exists():
        raise FileExistsError('Staging directory must not exist')
    discovery = discover(config)
    for root in discovery['roots']:
        if logical_path(staging).is_relative_to(Path(root['path'])):
            raise ValueError('Staging must be outside source roots')
    staging.mkdir(parents=True)
    files, coverage, roots, pending_links, pending_git = [], [], [], [], []
    secrets = {'auth.json', '.env.bak', 'credentials.json', 'token.json', 'tokens.json'}
    transient = {'.sandbox', '.sandbox-secrets', '.tmp', 'thread-writer-locks', '__pycache__', '.pytest_cache', '.superpowers'}
    for root in discovery['roots']:
        entry = dict(root)
        roots.append(entry)
        source = filesystem_path(root['path'])
        if not source.is_dir():
            coverage.append(dict(root=root['id'], state='missing', reason='Source directory not found'))
            continue
        if linked(source):
            coverage.append(dict(root=root['id'], state='unsupported', reason='Root is a symlink/junction; select its real target'))
            continue
        entry['git'] = git_evidence(source) if (source / '.git').exists() else None
        for parent, dirs, names in os.walk(source, followlinks=False, onerror=lambda error: (_ for _ in ()).throw(error)):
            parent = Path(parent)
            for name in list(dirs):
                child = parent / name
                if root['kind'] == 'codex' and child.relative_to(source).as_posix() == 'browser':
                    dirs.remove(name)
                    coverage.append(dict(root=root['id'], path='browser', state='reauthorize', reason='Browser login profile excluded'))
                    continue
                excluded = child.relative_to(source).as_posix() in root.get('exclude', [])
                is_link = linked(child)
                if is_link or name in transient or excluded:
                    dirs.remove(name)
                    relative = child.relative_to(source).as_posix()
                    if is_link and child.is_junction() and not excluded and name not in transient:
                        pending_links.append((root['id'], relative, child))
                    else:
                        unsupported = is_link and not excluded and name not in transient
                        coverage.append(dict(root=root['id'], path=relative, state='unsupported' if unsupported else 'rebuildable',
                            reason='Unsupported directory reparse point' if unsupported else 'Explicit exclusion' if excluded else 'Transient runtime cache'))
            # Preserve empty directories, too.
            (staging / 'roots' / root['id'] / parent.relative_to(source)).mkdir(parents=True, exist_ok=True)
            for name in names:
                original = parent / name
                relative = original.relative_to(source).as_posix()
                excluded = relative in root.get('exclude', [])
                guard = root['kind'] == 'codex' and name.startswith('.codex-provisioning-') and name.endswith('.guard')
                parts = Path(relative).parts
                runtime_lock = root['kind'] == 'codex' and (relative == '.sqlite-maintenance.lock' or
                    (name == '.lock' and len(parts) >= 3 and parts[0] == 'tmp' and parts[1] in {'arg0', 'arg0-windows'}))
                if excluded or guard or runtime_lock:
                    coverage.append(dict(root=root['id'], path=relative, state='rebuildable',
                        reason='Explicit exclusion' if excluded else 'Transient provisioning lock' if guard else 'Transient Codex runtime lock'))
                    continue
                if linked(original):
                    coverage.append(dict(root=root['id'], path=relative, state='unsupported', reason='External file link'))
                    continue
                if name.lower() in secrets or name.startswith('.env.bak-') or name.startswith('auth.json.'):
                    coverage.append(dict(root=root['id'], path=relative, state='reauthorize', reason='Login credentials excluded'))
                    continue
                if name.endswith(('-wal', '-shm')):
                    main = original.with_name(name.rsplit('-', 1)[0])
                    if name.endswith(('-wal', '-shm')) and main.is_file():
                        with main.open('rb') as stream:
                            if stream.read(16) == b'SQLite format 3\x00':
                                continue
                target_rel = f"roots/{root['id']}/{relative}"
                target = staging / target_rel
                copy_stable(original, target)
                files.append(dict(path=target_rel, size=target.stat().st_size, sha256=sha256(target)))
                if name == '.git' and original.is_file():
                    pending_git.append((root['id'], relative, original))
                if Path(relative).parts[-3:] == ('objects', 'info', 'alternates'):
                    coverage.append(dict(root=root['id'], path=relative, state='unsupported', reason='Git object alternates require separate recovery validation'))
                if name in {'.gitmodules', 'docker-compose.yml', 'compose.yaml', 'compose.yml'}:
                    coverage.append(dict(root=root['id'], path=relative, state='unsupported', reason='Check external submodule/service data separately'))
        coverage.append(dict(root=root['id'], state='saved', reason='Files copied and hashes recorded'))
    directory_links = []
    for rid, relative, original in pending_links:
        mapped = None
        try:
            candidate = captured_path(original, roots, staging)
            if candidate and (staging / candidate).is_dir() and not linked(staging / candidate):
                mapped = candidate
        except (OSError, RuntimeError):
            pass
        if mapped:
            directory_links.append(dict(path=f'roots/{rid}/{relative}', target=mapped))
        coverage.append(dict(root=rid, path=relative, state='saved_link' if mapped else 'unsupported',
            reason='Captured directory target' if mapped else 'Directory link target is missing, excluded or outside captured roots'))
    git_worktrees = []
    for rid, relative, original in pending_git:
        row = None
        try:
            copied = staging / 'roots' / rid / relative
            pointer = copied.read_text(encoding='utf-8-sig').strip() if copied.stat().st_size <= 4096 else ''
            if pointer.startswith('gitdir: '):
                admin = Path(pointer[8:])
                admin = filesystem_path(admin if admin.is_absolute() else original.parent / admin)
                target = captured_path(admin, roots, staging)
                if target and (staging / target / 'commondir').is_file() and (staging / target / 'gitdir').is_file():
                    common = Path((staging / target / 'commondir').read_text(encoding='utf-8-sig').strip())
                    common = common if common.is_absolute() else admin / common
                    mapped_common = captured_path(common, roots, staging)
                    backlink = Path((staging / target / 'gitdir').read_text(encoding='utf-8-sig').strip())
                    backlink = backlink if backlink.is_absolute() else admin / backlink
                    if mapped_common and Path(target).parent == Path(mapped_common) / 'worktrees' and logical_path(backlink.resolve()) == logical_path(original.resolve()):
                        common_copy = staging / mapped_common
                        custom = (staging / target / 'config.worktree').exists() or re.search(r'(?im)^\s*worktree\s*=', (common_copy / 'config').read_text(encoding='utf-8-sig'))
                        if not custom and (common_copy / 'objects').is_dir() and (common_copy / 'HEAD').is_file():
                            row = dict(path=f'roots/{rid}/{relative}', target=target, common=mapped_common)
        except (OSError, UnicodeError, ValueError, RuntimeError):
            pass
        if row:
            git_worktrees.append(row)
        coverage.append(dict(root=rid, path=relative, state='saved_git_worktree' if row else 'unsupported',
            reason='Captured worktree administration and common Git directory' if row else 'Git pointer target is external, missing or requires custom recovery'))
    card = config.get('project_card') or ''
    card_path = card if card.startswith('roots/') else 'roots/' + card
    manifest = dict(format_version=2 if directory_links or git_worktrees else 1, created_at=utcnow(), roots=roots, aliases=discovery['aliases'],
        coverage_scope=dict(selected_roots_only=True, note=config.get('scope_note', 'File coverage of selected roots only; full environment requires dependency and runtime checks')),
        files=files, directories=sorted(p.relative_to(staging).as_posix() for p in staging.rglob('*') if p.is_dir()),
        directory_links=directory_links,
        git_worktrees=git_worktrees,
        projects=project_index(staging, files, roots),
        coverage=coverage, complete=not any(x['state'] in {'missing', 'unsupported'} for x in coverage),
        environment=dict(os=platform.platform(), architecture=platform.machine(), python=sys.version,
                         python_executable=sys.executable, sqlite=sqlite3.sqlite_version),
        handoff=dict(project_status=config.get('project_status', 'unknown'),
                     project_card=config.get('project_card'), source_hashes={f['path']: f['sha256'] for f in files if Path(f['path']).name in {'AGENTS.md', 'CONTINUE.md'} or f['path'] == card_path},
                     validation_results=[], unknowns=['Runtime and project commands have not been executed by backup']),
        warnings=['Multiple files/databases are collected over an interval, not an atomic machine image'])
    write_json(staging / 'manifest.json', manifest)
    return manifest
