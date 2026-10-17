"""One-shot worker and opt-in current-user task. No task is installed on import."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

from .archive import seal, verify_snapshot
from .collect import collect, utcnow
from .credentials import read_key
from .model import filesystem_path, load_config, write_json
from .quark import QuarkClient
from .transfer import publish, receipt_metadata_matches


@contextmanager
def lock(data_dir: Path):
    import msvcrt
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    file = (data_dir / 'worker.lock').open('a+b')
    try:
        if (data_dir / 'worker.lock').stat().st_size == 0:
            file.write(b'0')
            file.flush()
        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError('Another backup is already running') from exc
        try:
            yield
        finally:
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        file.close()


def run_once(config_path: Path) -> dict:
    cfg = load_config(config_path)
    data = Path(cfg['data_dir'])
    with lock(data):
        status_path = data / 'status.json'
        previous = json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
        status = dict(previous, last_attempt=utcnow(), state='working')
        try:
            key = read_key(data)
            with tempfile.TemporaryDirectory(prefix='.collect-', dir=filesystem_path(data)) as temp:
                stage = Path(temp) / 'payload'
                manifest = collect(cfg, stage)
                fingerprint = hashlib.sha256(json.dumps(dict(files=manifest['files'], directories=manifest.get('directories', []), directory_links=manifest.get('directory_links', []), git_worktrees=manifest.get('git_worktrees', []), coverage=manifest['coverage'],
                    roots=cfg['roots'], project_status=cfg.get('project_status'), project_card=cfg.get('project_card')),
                    sort_keys=True).encode()).hexdigest()
                old = previous.get('snapshot_id')
                unchanged = fingerprint == previous.get('fingerprint') and old and (data / 'outbox' / old / 'COMPLETE.json').exists()
                snapshot = data / 'outbox' / old if unchanged else seal(stage, data / 'outbox', key)
                if unchanged:
                    verify_snapshot(snapshot, key)
            status.update(state='local_ready', snapshot_id=snapshot.name, snapshot=str(snapshot),
                fingerprint=fingerprint, unchanged=bool(unchanged), local_verified_at=utcnow(),
                complete=manifest['complete'], file_count=len(manifest['files']))
            status.pop('error', None)
            if cfg.get('cloud', {}).get('enabled'):
                client = QuarkClient(cfg['cloud'], data / 'quark-runtime')
                fid = client.resolve_path(cfg['cloud']['path'])
                latest_receipt, latest_reused = None, False
                # Flush older immutable pending versions before the newest one.
                for pending in sorted((data / 'outbox').iterdir()):
                    if pending.is_dir() and (pending / 'COMPLETE.json').exists():
                        receipt_path = pending / 'CLOUD-VERIFIED.json'
                        receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else {}
                        binding = {key: cfg['cloud'].get(key) for key in ['distribution', 'script', 'path']}
                        reused = receipt.get('target') == binding and receipt_metadata_matches(pending, client, fid, receipt)
                        if not reused:
                            receipt = dict(publish(pending, client, fid), target=binding)
                            write_json(receipt_path, receipt)
                        if pending.name == snapshot.name:
                            latest_receipt, latest_reused = receipt, reused
                status.update(state='cloud_verified', cloud_verified_at=latest_receipt['verified_at'],
                    cloud_metadata_checked_at=utcnow(),
                    cloud_check_scope='previous_full_bytes_and_current_metadata' if latest_reused else 'full_bytes', notices=client.notices)
        except Exception as exc:
            status.update(state='pending_upload' if status.get('snapshot_id') else 'failed',
                          error=f'{type(exc).__name__}: {exc}')
            write_json(status_path, status)
            raise
        write_json(status_path, status)
        return status


def schedule_xml(executable: Path, config_path: Path, interval_minutes=30):
    if type(interval_minutes) is not int or not 1 <= interval_minutes <= 1440:
        raise ValueError('Schedule interval must be 1 to 1440 whole minutes')
    arguments = subprocess.list2cmdline(['worker', '--config', str(config_path)])
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<Triggers><LogonTrigger><Enabled>true</Enabled><Repetition><Interval>PT{interval_minutes}M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></LogonTrigger></Triggers>
<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT6H</ExecutionTimeLimit></Settings>
<Actions Context="Author"><Exec><Command>{escape(str(executable))}</Command><Arguments>{escape(arguments)}</Arguments></Exec></Actions>
</Task>'''


def install_schedule(config_path: Path):
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Use the packaged exe to register a stable scheduled task')
    cfg = load_config(config_path)
    read_key(Path(cfg['data_dir']))
    executable = Path(sys.executable).with_name('CodexEnvironmentBackupWorker.exe')
    if not executable.is_file():
        raise RuntimeError('Background worker is missing; extract the complete release directory')
    interval = cfg.get('schedule', {}).get('interval_minutes', 30)
    path = Path(cfg['data_dir']) / 'schedule.xml'
    path.write_text(schedule_xml(executable, Path(config_path).resolve(), interval), encoding='utf-16')
    name = 'CodexEnvironmentBackup-' + hashlib.sha256(str(Path(config_path).resolve()).encode()).hexdigest()[:12]
    p = subprocess.run(['schtasks.exe', '/Create', '/TN', name, '/XML', str(path), '/F'], capture_output=True)
    if p.returncode:
        raise RuntimeError('Windows rejected scheduled task registration')
    return dict(task_name=name, interval_minutes=interval, requires_logged_in_user=True,
        note='Runs at next logon and repeats; use backup now for the first run')
