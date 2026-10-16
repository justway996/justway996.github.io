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
from .model import load_config, write_json
from .quark import QuarkClient
from .transfer import publish


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
            with tempfile.TemporaryDirectory(prefix='.collect-', dir=data) as temp:
                stage = Path(temp) / 'payload'
                manifest = collect(cfg, stage)
                fingerprint = hashlib.sha256(json.dumps(dict(files=manifest['files'], directories=manifest.get('directories', []), coverage=manifest['coverage'],
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
                # Flush older immutable pending versions before the newest one.
                for pending in sorted((data / 'outbox').iterdir()):
                    if pending.is_dir() and (pending / 'COMPLETE.json').exists():
                        report = publish(pending, client, fid)
                        write_json(pending / 'CLOUD-VERIFIED.json', report)
                status.update(state='cloud_verified', cloud_verified_at=utcnow(), notices=client.notices)
        except Exception as exc:
            status.update(state='pending_upload' if status.get('snapshot_id') else 'failed',
                          error=f'{type(exc).__name__}: {exc}')
            write_json(status_path, status)
            raise
        write_json(status_path, status)
        return status


def schedule_xml(executable: Path, config_path: Path):
    arguments = subprocess.list2cmdline(['worker', '--config', str(config_path)])
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<Triggers><LogonTrigger><Enabled>true</Enabled><Repetition><Interval>PT30M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></LogonTrigger></Triggers>
<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT6H</ExecutionTimeLimit></Settings>
<Actions Context="Author"><Exec><Command>{escape(str(executable))}</Command><Arguments>{escape(arguments)}</Arguments></Exec></Actions>
</Task>'''


def install_schedule(config_path: Path):
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Use the packaged exe to register a stable scheduled task')
    cfg = load_config(config_path)
    read_key(Path(cfg['data_dir']))
    path = Path(cfg['data_dir']) / 'schedule.xml'
    path.write_text(schedule_xml(Path(sys.executable), Path(config_path).resolve()), encoding='utf-16')
    name = 'CodexEnvironmentBackup-' + hashlib.sha256(str(Path(config_path).resolve()).encode()).hexdigest()[:12]
    p = subprocess.run(['schtasks.exe', '/Create', '/TN', name, '/XML', str(path), '/F'], capture_output=True)
    if p.returncode:
        raise RuntimeError('Windows rejected scheduled task registration')
    return dict(task_name=name, interval_minutes=30, requires_logged_in_user=True)
