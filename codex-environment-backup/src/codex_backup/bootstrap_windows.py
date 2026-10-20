"""Original-user Windows orchestration; only system setup is elevated."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import winreg
import zipfile

from .bootstrap import download_component, load_setup_state, save_setup_state, setup_lock
from .installer import _ps_literal, _relative
from .quark import QuarkClient
from .scheduler import lock

RESOURCES = Path(__file__).resolve().parent
SCRIPT = '/opt/codex-quark/1.0.24/scripts/quark-drive.cjs'


def _run(args, timeout=60):
    return subprocess.run([str(arg) for arg in args], capture_output=True, timeout=timeout,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _text(value):
    return value.decode('utf-16le' if b'\x00' in value else 'utf-8-sig', errors='replace').strip().lstrip('\ufeff')


def _powershell(code, timeout=60):
    code = '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); $ErrorActionPreference="Stop"; ' + code
    encoded = base64.b64encode(code.encode('utf-16le')).decode('ascii')
    return _run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded], timeout)


def _system_info():
    result = _powershell('& ' + _ps_literal(RESOURCES / 'setup-wsl.ps1') + ' -Action Inspect')
    if result.returncode:
        raise RuntimeError('无法检测Windows组件，请确认系统允许使用WSL')
    info = json.loads(_text(result.stdout))
    try:
        version = _run(['wsl.exe', '--version'])
        info['wsl_installed'] = version.returncode == 0
    except FileNotFoundError:
        info['wsl_installed'] = False
    return info


def _owner(config):
    return 'codex-workspace-backup-v1:' + hashlib.sha256(str(Path(config['data_dir']).resolve()).casefold().encode()).hexdigest()[:16]


def _registered_id(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Lxss') as root:
            index = 0
            while True:
                try:
                    value = winreg.EnumKey(root, index)
                except OSError:
                    return ''
                index += 1
                with winreg.OpenKey(root, value) as child:
                    if winreg.QueryValueEx(child, 'DistributionName')[0] == name:
                        return value
    except OSError:
        return ''


def inspect_environment(config: dict) -> dict:
    system = _system_info()
    name = config.get('cloud', {}).get('distribution') or 'CodexWorkspaceBackup-' + _owner(config).split(':')[-1][:8]
    script = config.get('cloud', {}).get('script') or SCRIPT
    observed = dict(state='needs_setup', distribution=name, script=script, exists=False, owned=False, system=system)
    if not system['wsl_installed'] or not system['system_ready']:
        return observed
    listing = _run(['wsl.exe', '--list', '--quiet'])
    if listing.returncode or name not in _text(listing.stdout).splitlines():
        return observed
    observed['exists'] = True
    command = ['wsl.exe', '-d', name, '--exec']
    marker = _run([*command, 'cat', '/opt/codex-quark/INSTALLER-OWNER'])
    observed['owned'] = marker.returncode == 0 and _text(marker.stdout) == _owner(config)
    state_dir = Path(config.get('_setup_state_dir', Path(config['data_dir']) / 'setup'))
    state = load_setup_state(state_dir / 'setup-state.json')
    registered = _registered_id(name)
    if registered and state.get('distribution') == name and state.get('distribution_id') == registered:
        observed['owned'] = True
    if not observed['owned'] and not config.get('cloud', {}).get('distribution'):
        return observed
    uid = _run([*command, 'id', '-u'])
    readonly = _run([*command, 'test', '-w', str(Path(script).parent.parent).replace('\\', '/')])
    node = _run([*command, 'node', '--version'])
    cli = _run([*command, 'node', script, '--version'])
    if uid.returncode == 0 and _text(uid.stdout).isdigit() and int(_text(uid.stdout)) != 0 and readonly.returncode == 1 and node.returncode == 0 and _text(node.stdout).startswith('v24.') and cli.returncode == 0 and _text(cli.stdout).startswith('1.0.24'):
        observed['state'] = 'ready'
    return observed


def _elevated_system(msi, state_dir):
    result_path = Path(state_dir) / 'system-result.json'
    if result_path.exists():
        result_path.unlink()
    child = '& ' + _ps_literal(RESOURCES / 'setup-wsl.ps1') + ' -Action Enable -ResultFile ' + _ps_literal(result_path)
    if msi:
        child += ' -Msi ' + _ps_literal(msi)
    encoded = base64.b64encode(child.encode('utf-16le')).decode('ascii')
    outer = "$p=Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand'," + _ps_literal(encoded) + ') -Wait -PassThru -WindowStyle Hidden; exit $p.ExitCode'
    result = _powershell(outer, timeout=1800)
    if result_path.is_file():
        value = json.loads(result_path.read_text(encoding='utf-8-sig'))
        return {key: str(value[key]) for key in ['state', 'error_code'] if key in value}
    return dict(state='failed', error_code='ADMIN_DENIED' if result.returncode else 'SYSTEM_RESULT_MISSING')


def _component(name, state_dir, progress):
    spec = json.loads((RESOURCES / 'setup-dependencies.json').read_text(encoding='utf-8'))['components'][name]
    callback = (lambda done, total: progress(f'正在下载组件 {name}：{done * 100 // total}%')) if progress else None
    return download_component(spec, Path(state_dir) / 'downloads', callback)


def _wsl_path(name, path):
    result = _run(['wsl.exe', '-d', name, '--exec', 'wslpath', '-a', str(Path(path).resolve())])
    if result.returncode:
        raise RuntimeError('无法访问组件下载位置，请检查磁盘和WSL状态')
    return _text(result.stdout)


def prepare_environment(config: dict, state_dir: Path, progress=None) -> dict:
    state_dir = Path(state_dir).resolve()
    config = dict(config, _setup_state_dir=str(state_dir))
    with setup_lock(state_dir):
        observed = inspect_environment(config)
        if observed['state'] == 'ready':
            return observed
        if not observed['system']['supported']:
            raise RuntimeError('此版本需要Windows 11 x64及可用的虚拟化支持；仍可使用本地恢复')
        if observed['exists'] and not observed['owned']:
            raise RuntimeError('已有同名WSL环境不属于本安装器，未修改；请选择新的数据位置或已有配置')
        with lock(Path(config['data_dir'])):
            state_path = state_dir / 'setup-state.json'
            state = load_setup_state(state_path)
            boot = observed['system']['boot_id']
            if state.get('state') == 'restart_required' and state.get('restart_boot') == boot:
                return state
            state.update(state='preparing', stage='system', distribution=observed['distribution'])
            save_setup_state(state_path, state)
            if not observed['system']['system_ready'] or not observed['system']['wsl_installed']:
                msi = None if observed['system']['wsl_installed'] else _component('wsl', state_dir, progress)
                result = _elevated_system(msi, state_dir)
                if result['state'] != 'ready':
                    state.update(result, restart_boot=boot)
                    save_setup_state(state_path, state)
                    return state
                observed = inspect_environment(config)
                if not observed['system']['system_ready'] or not observed['system']['wsl_installed']:
                    state.update(state='restart_required', restart_boot=boot)
                    save_setup_state(state_path, state)
                    return state
            components = {name: _component(name, state_dir, progress) for name in ['ubuntu', 'node', 'quark']}
            name = observed['distribution']
            if not observed['exists']:
                location = Path(config['data_dir']).resolve() / 'environment/wsl'
                result = _run(['wsl.exe', '--install', '--from-file', components['ubuntu'], '--name', name,
                    '--location', location, '--no-launch'], timeout=1800)
                if result.returncode:
                    raise RuntimeError('专用环境未建立，请检查虚拟化是否启用、系统是否需要重启')
                registered = _registered_id(name)
                if not registered:
                    raise RuntimeError('专用环境注册未确认，未继续配置')
                state.update(distribution_id=registered, stage='distribution')
                save_setup_state(state_path, state)
            with tempfile.TemporaryDirectory(prefix='quark-', dir=state_dir) as temp:
                with zipfile.ZipFile(components['quark']) as archive:
                    for info in archive.infolist():
                        _relative(info.filename.rstrip('/'))
                        if (info.external_attr >> 16) & 0o170000 == 0o120000:
                            raise ValueError('官方组件包包含不支持的符号链接')
                    archive.extractall(temp)
                paths = [_wsl_path(name, path) for path in [RESOURCES / 'setup-quark.sh', components['node'], Path(temp), Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/rundll32.exe']]
                if progress:
                    progress('正在配置网盘连接组件……')
                result = _run(['wsl.exe', '-d', name, '-u', 'root', '--exec', 'bash', paths[0], *paths[1:3], _owner(config), paths[3]], timeout=600)
                if result.returncode:
                    raise RuntimeError('网盘组件未配置完成，请重试；现有其他环境未修改')
            # Only our positively identified distribution is restarted, never global WSL.
            result = _run(['wsl.exe', '--terminate', name])
            if result.returncode:
                raise RuntimeError('专用环境尚未就绪，请稍后重试')
            updated = dict(config, cloud=dict(config.get('cloud', {}), distribution=name, script=SCRIPT))
            verified = inspect_environment(updated)
            if verified['state'] != 'ready':
                raise RuntimeError('组件已写入但运行检查未通过，未启用网盘备份')
            state.update(state='ready', stage='complete', script=SCRIPT)
            save_setup_state(state_path, state)
            return verified


def request_restart_resume(executable: Path, state_dir: Path):
    executable, state_dir = Path(executable).resolve(), Path(state_dir).resolve()
    if not executable.is_file():
        raise ValueError('续跑程序不存在，请从已安装的程序启动')
    name = 'CodexWorkspaceBackupSetup-' + hashlib.sha256(str(state_dir).encode()).hexdigest()[:12]
    command = subprocess.list2cmdline([str(executable), 'setup', '--setup-state', str(state_dir)])
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\RunOnce') as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)


def clear_restart_resume(state_dir: Path):
    name = 'CodexWorkspaceBackupSetup-' + hashlib.sha256(str(Path(state_dir).resolve()).encode()).hexdigest()[:12]
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\RunOnce', 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass


def authorize_cloud(config: dict, progress=None) -> dict:
    client = QuarkClient(config['cloud'], Path(config['data_dir']) / 'quark-runtime')
    try:
        client.check()
    except RuntimeError:
        if progress:
            progress('请在打开的夸克官方页面完成登录和授权……')
        client.run('login')
        client.check()
    path = config['cloud'].get('path', '/CodexWorkspace')
    if not path.startswith('/') or '..' in path.split('/'):
        raise ValueError('网盘目录无效')
    parent = '0'
    for part in path.split('/')[1:]:
        if part:
            parent = client.create_folder(part, parent)
    return dict(state='connected', path=path)
