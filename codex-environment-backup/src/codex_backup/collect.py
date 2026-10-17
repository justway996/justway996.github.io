"""Stable file copies and SQLite online backups; originals are never changed."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

from .model import discover, write_json


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
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)) as src:
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


def collect(config: dict, staging: Path) -> dict:
    staging = Path(staging).resolve()
    if staging.exists():
        raise FileExistsError('Staging directory must not exist')
    discovery = discover(config)
    for root in discovery['roots']:
        if staging.is_relative_to(Path(root['path'])):
            raise ValueError('Staging must be outside source roots')
    staging.mkdir(parents=True)
    files, coverage, roots = [], [], []
    secrets = {'auth.json', '.env.bak', 'credentials.json', 'token.json', 'tokens.json'}
    transient = {'.sandbox', '.sandbox-secrets', '.tmp', 'thread-writer-locks', '__pycache__', '.pytest_cache', '.superpowers'}
    for root in discovery['roots']:
        entry = dict(root)
        roots.append(entry)
        source = Path(root['path'])
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
                if linked(child) or name in transient or excluded:
                    dirs.remove(name)
                    coverage.append(dict(root=root['id'], path=child.relative_to(source).as_posix(),
                        state='unsupported' if linked(child) else 'rebuildable', reason='External link' if linked(child) else 'Explicit exclusion' if excluded else 'Transient runtime cache'))
            # Preserve empty directories, too.
            (staging / 'roots' / root['id'] / parent.relative_to(source)).mkdir(parents=True, exist_ok=True)
            for name in names:
                original = parent / name
                relative = original.relative_to(source).as_posix()
                if linked(original):
                    coverage.append(dict(root=root['id'], path=relative, state='unsupported', reason='External file link'))
                    continue
                if name.lower() in secrets or name.startswith('.env.bak-') or name.startswith('auth.json.'):
                    coverage.append(dict(root=root['id'], path=relative, state='reauthorize', reason='Login credentials excluded'))
                    continue
                if name.endswith(('-wal', '-shm', '.lock')):
                    main = original.with_name(name.rsplit('-', 1)[0])
                    if name.endswith(('-wal', '-shm')) and main.is_file():
                        with main.open('rb') as stream:
                            if stream.read(16) == b'SQLite format 3\x00':
                                continue
                    if name.endswith('.lock') and root['kind'] == 'codex':
                        continue
                target_rel = f"roots/{root['id']}/{relative}"
                target = staging / target_rel
                copy_stable(original, target)
                files.append(dict(path=target_rel, size=target.stat().st_size, sha256=sha256(target)))
                if name == '.git' and original.is_file():
                    coverage.append(dict(root=root['id'], path=relative, state='unsupported', reason='External Git worktree common-dir requires separate scope'))
                if name in {'.gitmodules', 'docker-compose.yml', 'compose.yaml', 'compose.yml'}:
                    coverage.append(dict(root=root['id'], path=relative, state='unsupported', reason='Check external submodule/service data separately'))
        coverage.append(dict(root=root['id'], state='saved', reason='Files copied and hashes recorded'))
    manifest = dict(format_version=1, created_at=utcnow(), roots=roots, aliases=discovery['aliases'],
        coverage_scope=dict(selected_roots_only=True, note=config.get('scope_note', 'File coverage of selected roots only; full environment requires dependency and runtime checks')),
        files=files, directories=sorted(p.relative_to(staging).as_posix() for p in staging.rglob('*') if p.is_dir()),
        coverage=coverage, complete=not any(x['state'] in {'missing', 'unsupported'} for x in coverage),
        environment=dict(os=platform.platform(), architecture=platform.machine(), python=sys.version,
                         python_executable=sys.executable, sqlite=sqlite3.sqlite_version),
        handoff=dict(project_status=config.get('project_status', 'unknown'),
                     project_card=config.get('project_card'), source_hashes={f['path']: f['sha256'] for f in files if Path(f['path']).name in {'AGENTS.md', 'CONTINUE.md'}},
                     validation_results=[], unknowns=['Runtime and project commands have not been executed by backup']),
        warnings=['Multiple files/databases are collected over an interval, not an atomic machine image'])
    write_json(staging / 'manifest.json', manifest)
    return manifest
