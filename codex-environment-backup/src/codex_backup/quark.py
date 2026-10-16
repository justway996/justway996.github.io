"""Official CLI protocol adapter. Actual account compatibility requires a live probe."""
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess


def parse_output(stdout: str, returncode: int):
    try:
        records = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        results = [x for x in records if x.get('type') == 'result']
        result = results[-1] if results else {}
        data = result.get('data') or {}
        if returncode or result.get('code') != 0 or data.get('failedCount', 0) or data.get('failCount', 0):
            # Raw command output can contain identity information: do not dump it.
            raise RuntimeError(f"Quark command failed (code={result.get('code', 'missing')}); check official authorization or task status")
        if any(x.get('code', 0) != 0 for x in records if x.get('type') == 'list'):
            raise RuntimeError('Partial Quark transfer failed')
        return result, records
    except (json.JSONDecodeError, AttributeError) as exc:
        raise RuntimeError('Quark protocol changed or unavailable') from exc


class QuarkClient:
    def __init__(self, config: dict, workdir: Path):
        self.distribution = config.get('distribution', '')
        self.script = config.get('script', '')
        if not self.distribution or not self.script.startswith('/'):
            raise ValueError('Configure WSL distribution and absolute official CLI script path first')
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.notices = []

    def wsl(self, *args, timeout=60):
        return subprocess.run(['wsl.exe', '-d', self.distribution, '--exec', *args],
            capture_output=True, timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def linux_path(self, path):
        p = self.wsl('wslpath', '-a', str(Path(path).resolve()))
        if p.returncode:
            raise RuntimeError('WSL path conversion unavailable')
        return p.stdout.decode('utf-8').strip()

    def windows_path(self, path):
        p = self.wsl('wslpath', '-w', path)
        if p.returncode:
            raise RuntimeError('WSL path conversion unavailable')
        return Path(p.stdout.decode('utf-8').strip())

    def run(self, *args):
        runtime = self.linux_path(self.workdir)
        p = self.wsl('env', f'OPENCLAW_RUNTIME_DIR={runtime}', 'node', self.script, *args, timeout=3600)
        result, records = parse_output(p.stdout.decode('utf-8', errors='replace'), p.returncode)
        if result.get('notice', {}).get('text'):
            self.notices.append(result['notice']['text'])
        return result, records

    def check(self):
        # Listing is read-only and also tests whether authorization is valid.
        self.list_children('0')
        return dict(state='connected', live_transfer_verified=False, distribution=self.distribution)

    def list_children(self, fid):
        result, records = self.run('browse', '--parent-fid', fid, '--all', '--task-dir', self.linux_path(self.workdir))
        data = result['data']
        if data.get('hasMore') is not False or not data.get('file_path'):
            raise RuntimeError('Incomplete browse listing')
        artifact = PurePosixPath(data['file_path'])
        if not artifact.is_relative_to(PurePosixPath(self.linux_path(self.workdir))):
            raise RuntimeError('Unexpected artifact location')
        lines = self.windows_path(str(artifact)).read_text(encoding='utf-8').splitlines()
        raw = [json.loads(line) for line in lines if line.strip()]
        return [dict(fid=x['fid'], file_name=x['filename'], dir=x.get('file_type') == '0' or x.get('category') == 0,
                     size=x.get('size')) for x in raw]

    def resolve_path(self, path):
        if not path.startswith('/') or '..' in PurePosixPath(path).parts:
            raise ValueError('Use an absolute cloud path')
        fid = '0'
        for part in PurePosixPath(path).parts[1:]:
            matches = [x for x in self.list_children(fid) if x['dir'] and x['file_name'] == part]
            if len(matches) != 1:
                raise ValueError('Cloud path missing or ambiguous; select/create it explicitly')
            fid = matches[0]['fid']
        return fid

    def create_folder(self, name, parent):
        result, _ = self.run('create-folder', '--dir-path', name, '--parent-fid', parent)
        return result['data']['fid']

    def upload(self, local, parent):
        result, records = self.run('upload', self.linux_path(local), '--parent-fid', parent)
        fids = result['data'].get('fids', [])
        if len(fids) != 1:
            raise RuntimeError('Expected one uploaded file')
        return dict(fid=fids[0])

    def download(self, fid, destination):
        result, records = self.run('read-file', '--fid', fid)
        files = result['data'].get('files', [])
        if len(files) != 1 or not files[0].get('success'):
            raise RuntimeError('Incomplete download')
        local = PurePosixPath(files[0]['filePath'])
        runtime = PurePosixPath(self.linux_path(self.workdir)) / '.quarkclouddrive'
        if '..' in local.parts or not local.is_relative_to(runtime):
            raise RuntimeError('Unexpected download output location')
        shutil.copyfile(self.windows_path(str(local)), destination)
        return Path(destination)
