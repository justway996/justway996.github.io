"""Install a verified application bundle without moving user data."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

from .model import filesystem_path, logical_path


def _relative(name):
    path = PurePosixPath(name)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}
    if not name or path.is_absolute() or '\\' in name or ':' in name or str(path) != name:
        raise ValueError('安装包包含无效路径')
    if any(part in {'.', '..'} or part.rstrip(' .') != part or part.split('.')[0].upper() in reserved for part in path.parts):
        raise ValueError('安装包包含无效路径')
    return path


def _digest(stream):
    return hashlib.file_digest(stream, 'sha256').hexdigest()


def _inspect(archive):
    members, root, names = {}, None, set()
    if sum(info.file_size for info in archive.infolist()) > 512 * 1024 * 1024:
        raise ValueError('安装包展开大小超出限制')
    for info in archive.infolist():
        name = info.filename.rstrip('/') if info.is_dir() else info.filename
        path = _relative(name)
        folded = name.casefold()
        if folded in names or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError('安装包包含重复路径或符号链接')
        names.add(folded)
        if root is None:
            root = path.parts[0]
        if path.parts[0] != root or (not info.is_dir() and len(path.parts) < 2):
            raise ValueError('安装包根目录无效')
        if not info.is_dir():
            members[str(PurePosixPath(*path.parts[1:]))] = info
    if 'SHA256SUMS.txt' not in members or 'release.json' not in members:
        raise ValueError('安装包缺少校验清单或版本信息')
    sums = {}
    for line in archive.read(members['SHA256SUMS.txt']).decode('utf-8').splitlines():
        digest, separator, name = line.partition('  ')
        _relative(name)
        if not separator or not re.fullmatch('[a-f0-9]{64}', digest) or name.casefold() in {n.casefold() for n in sums}:
            raise ValueError('安装包校验清单无效')
        sums[name] = digest
    if set(members) != set(sums) | {'SHA256SUMS.txt'}:
        raise ValueError('安装包存在未列入清单或缺失的文件')
    required = {'CodexEnvironmentBackup.exe', 'CodexEnvironmentBackupWorker.exe', 'release.json'}
    if not required.issubset(sums) or not any(name.startswith('_internal/') for name in sums):
        raise ValueError('安装包缺少程序或运行库')
    for name, digest in sums.items():
        with archive.open(members[name]) as stream:
            if _digest(stream) != digest:
                raise ValueError('安装包校验失败，请重新取得安装包')
    release = json.loads(archive.read(members['release.json']))
    version = release.get('version', '')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('安装包版本无效')
    return members, sums, version


def install_release(payload: Path, destination: Path) -> dict:
    destination = filesystem_path(Path(destination).resolve())
    with zipfile.ZipFile(payload) as archive:
        members, sums, version = _inspect(archive)
        target = destination / version
        if target.exists():
            for name, digest in sums.items():
                path = target / name
                if not path.resolve().is_relative_to(target.resolve()) or not path.is_file():
                    raise ValueError('已有安装不完整，请选择其他安装位置')
                with path.open('rb') as stream:
                    if _digest(stream) != digest:
                        raise ValueError('已有安装被修改，未覆盖；请选择其他安装位置')
            return dict(version=version, installed=str(logical_path(target)), reused=True)
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.install-', dir=destination) as temp:
            stage = Path(temp) / version
            stage.mkdir()
            for name, info in members.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
            for name, digest in sums.items():
                with (stage / name).open('rb') as stream:
                    if _digest(stream) != digest:
                        raise ValueError('安装文件写入后校验失败')
            stage.rename(target)
    return dict(version=version, installed=str(logical_path(target)), reused=False)


def _ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def create_shortcuts(executable: Path) -> list[Path]:
    # Use encoded PowerShell and quoted literals so user paths cannot become code.
    code = f"""[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference='Stop'; $shell=New-Object -ComObject WScript.Shell
$locations=@([Environment]::GetFolderPath('DesktopDirectory'), [IO.Path]::Combine([Environment]::GetFolderPath('Programs'),'Codex 工作环境备份'))
$created=@(); foreach($folder in $locations) {{
  [IO.Directory]::CreateDirectory($folder) | Out-Null
  $path=[IO.Path]::Combine($folder,'Codex 工作环境备份.lnk')
  if(Test-Path -LiteralPath $path) {{
    $existing=$shell.CreateShortcut($path)
    if($existing.TargetPath -ne {_ps_literal(executable)}) {{ throw 'Existing shortcut belongs to another installation' }}
  }}
  $shortcut=$shell.CreateShortcut($path)
  $shortcut.TargetPath={_ps_literal(executable)}
  $shortcut.Arguments = 'setup'
  $shortcut.WorkingDirectory={_ps_literal(Path(executable).parent)}
  $shortcut.Save(); $created+=$path
}}
ConvertTo-Json -InputObject @($created) -Compress"""
    encoded = base64.b64encode(code.encode('utf-16le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
        capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('程序已安装，但快捷方式未创建；请从安装目录启动或选择其他安装位置')
    return [Path(value) for value in json.loads(result.stdout.decode('utf-8-sig'))]


def installer_main(payload: Path, smoke: bool = False):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import threading
    window = tk.Tk()
    window.title('安装 Codex 工作环境备份')
    window.geometry('640x320')
    selected = tk.StringVar(value=str(Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'CodexWorkspaceBackup/app'))
    ttk.Label(window, text='安装工作环境备份', font=('Microsoft YaHei UI', 18)).pack(anchor='w', padx=24, pady=(24, 12))
    ttk.Label(window, text='安装后打开中文向导。网盘组件将按需自动准备，账号和密钥由你选择。').pack(anchor='w', padx=24)
    ttk.Entry(window, textvariable=selected).pack(fill='x', padx=24, pady=12)
    status = tk.StringVar(value='程序与个人备份数据分开保存，现有工程不会被覆盖。')
    ttk.Label(window, textvariable=status, wraplength=590).pack(anchor='w', padx=24, pady=8)
    controls = ttk.Frame(window)
    controls.pack(fill='x', padx=24, pady=12)
    def choose():
        path = filedialog.askdirectory(title='选择程序安装位置')
        if path:
            selected.set(path)
    def complete(result, error):
        if error:
            status.set(error)
            install_button.configure(state='normal')
            return
        status.set('安装完成，正在打开首次使用向导。')
        executable = Path(result['installed']) / 'CodexEnvironmentBackupWorker.exe'
        try:
            create_shortcuts(executable)
        except Exception as exc:
            messagebox.showwarning('快捷方式未完成', str(exc))
        subprocess.Popen([str(executable), 'setup'], cwd=executable.parent,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        window.destroy()
    def install():
        target = Path(selected.get())
        install_button.configure(state='disabled')
        status.set('正在校验和安装，请稍候……')
        def worker():
            try:
                result, error = install_release(payload, target), None
            except Exception as exc:
                result, error = None, str(exc)
            window.after(0, lambda: complete(result, error))
        threading.Thread(target=worker, daemon=True).start()
    ttk.Button(controls, text='更改位置', command=choose).pack(side='left')
    install_button = ttk.Button(controls, text='安装并开始使用', command=install)
    install_button.pack(side='right')
    if smoke:
        window.withdraw()
        window.after(100, window.destroy)
    window.mainloop()
