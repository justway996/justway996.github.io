"""Chinese desktop entry and matching command-line operations."""
import argparse
import json
import os
from pathlib import Path
import sys

from .archive import verify_snapshot
from .credentials import new_key, import_key, read_key
from .model import discover, load_config, write_json
from .quark import QuarkClient
from .restore import restore
from .scheduler import install_schedule, run_once
from .transfer import list_snapshots, fetch


def create_config(path, projects, data_dir, *, include_codex=True, include_vaults=True):
    path = Path(path)
    if path.exists():
        raise FileExistsError('Config already exists')
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    roots = [dict(id=f'project-{i+1}', path=str(Path(p).resolve()), kind='project') for i, p in enumerate(projects)]
    if include_codex:
        roots.append(dict(id='codex', path=str(home), kind='codex'))
    if include_vaults:
        roots.extend([dict(id='work-vault', name='工作知识库', path='E:/工作知识库', kind='vault'),
                      dict(id='design-vault', name='自生长', path='E:/自生长', kind='vault')])
    cfg = dict(format_version=1, codex_home=str(home), data_dir=str(Path(data_dir).resolve()), roots=roots,
               project_status='unknown', project_card=None,
               cloud=dict(enabled=False, distribution='', script='', path='/CodexWorkspace'))
    write_json(path, cfg)
    try:
        load_config(path)
    except Exception:
        path.unlink()
        raise
    return cfg


def validate_key_location(cfg, path):
    path = Path(path).resolve()
    roots = [Path(cfg['data_dir']), Path(cfg['codex_home']), *(Path(r['path']) for r in discover(cfg)['roots'])]
    if any(path.is_relative_to(root.resolve()) for root in roots):
        raise ValueError('恢复密钥必须保存在所有采集目录和备份数据目录之外，例如离线 U 盘')


def action(command, config_path, **kwargs):
    cfg = load_config(config_path)
    data = Path(cfg['data_dir'])
    if command == 'inspect':
        return discover(cfg)
    if command == 'status':
        path = data / 'status.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(state='not_started')
    if command in {'backup', 'worker'}:
        return run_once(config_path)
    if command == 'new-key':
        validate_key_location(cfg, kwargs['key_file'])
        new_key(data, Path(kwargs['key_file']))
        return dict(state='key_created', note='请将恢复密钥另存离线；不要上传到同一个网盘目录')
    if command == 'import-key':
        validate_key_location(cfg, kwargs['key_file'])
        import_key(data, Path(kwargs['key_file']))
        return dict(state='key_imported')
    if command == 'restore':
        return restore(Path(kwargs['snapshot']), Path(kwargs['destination']), read_key(data))
    if command == 'verify':
        manifest = verify_snapshot(Path(kwargs['snapshot']), read_key(data))
        return dict(state='local_verified', file_count=len(manifest['files']), complete=manifest['complete'])
    if command == 'install-schedule':
        return install_schedule(Path(config_path))
    client = QuarkClient(cfg['cloud'], data / 'quark-runtime')
    if command == 'cloud-check':
        return client.check()
    fid = client.resolve_path(cfg['cloud']['path'])
    if command == 'versions':
        return dict(versions=list_snapshots(client, fid), notices=client.notices)
    if command == 'fetch':
        versions = list_snapshots(client, fid)
        matches = [v for v in versions if v['snapshot_id'] == kwargs['snapshot_id']]
        if len(matches) != 1:
            raise ValueError('Version not found or ambiguous')
        target = fetch(matches[0], client, data / 'inbox')
        verify_snapshot(target, read_key(data))
        return dict(state='download_verified', snapshot=str(target), notices=client.notices)
    raise ValueError('Unknown operation')


def gui(smoke=False):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    import threading
    window = tk.Tk()
    window.title('Codex 工作环境备份 · 0.2.4 迁移验证版')
    window.geometry('900x620')
    selected = tk.StringVar()
    ttk.Label(window, text='完整备份与恢复', font=('Microsoft YaHei UI', 19)).pack(anchor='w', padx=20, pady=(18, 4))
    ttk.Label(window, text='先配置采集范围并保存离线恢复密钥。网盘尚需 WSL 与官方授权；恢复不会覆盖当前账号。').pack(anchor='w', padx=20)
    ttk.Entry(window, textvariable=selected).pack(fill='x', padx=20, pady=12)
    rows = ttk.Frame(window)
    rows.pack(fill='x', padx=20)
    output = tk.Text(window, wrap='word', font=('Microsoft YaHei UI', 10))
    output.pack(fill='both', expand=True, padx=20, pady=14)
    busy = [False]
    def show(value):
        output.delete('1.0', 'end')
        output.insert('end', json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)
    def choose():
        value = filedialog.askopenfilename(title='选择备份配置 JSON', filetypes=[('配置', '*.json')])
        if value:
            selected.set(value)
            show(action('inspect', value))
    def setup():
        project = filedialog.askdirectory(title='选择正在开发的工程目录；可在配置中增加更多工程')
        if not project:
            return
        cfgfile = filedialog.asksaveasfilename(title='将新配置保存到工程目录外', initialfile='backup-config.json', defaultextension='.json')
        if not cfgfile:
            return
        data_dir = filedialog.askdirectory(title='选择本地备份数据目录，必须位于所有采集根之外')
        if not data_dir:
            return
        include = messagebox.askyesno('采集范围', '同时纳入 Codex 本地数据和 E 盘两个知识库？\n可能占用较大空间；备份前请检查范围。')
        try:
            create_config(Path(cfgfile), [Path(project)], Path(data_dir), include_codex=include, include_vaults=include)
            selected.set(cfgfile)
            show(action('inspect', cfgfile))
        except Exception as exc:
            messagebox.showerror('配置未完成', str(exc))
    def perform(command, **kwargs):
        if busy[0]:
            messagebox.showinfo('正在执行', '请等待当前操作结束')
            return
        if not selected.get():
            return messagebox.showinfo('需要配置', '请先新建或打开配置')
        busy[0] = True
        show('正在执行，请等待；未显示云端验证通过前不代表已经上传。')
        def worker():
            try:
                result = action(command, Path(selected.get()), **kwargs)
            except Exception as exc:
                result = dict(state='failed', error=f'{type(exc).__name__}: {exc}')
            window.after(0, lambda: (show(result), busy.__setitem__(0, False)))
        threading.Thread(target=worker, daemon=True).start()
    def key(importing=False):
        if not selected.get():
            return messagebox.showinfo('需要配置', '请先打开配置')
        path = filedialog.askopenfilename(title='导入原离线恢复密钥') if importing else filedialog.asksaveasfilename(title='保存恢复密钥到采集范围之外，随后离线保管', initialfile='Codex-recovery.key')
        if path:
            perform('import-key' if importing else 'new-key', key_file=path)
    def restore_dialog():
        snap = filedialog.askdirectory(title='选择含 COMPLETE.json 的完整版本目录')
        if not snap:
            return
        destination = filedialog.askdirectory(title='选择空目录；恢复后需要核对环境和项目卡')
        if destination:
            perform('restore', snapshot=snap, destination=destination)
    def cloud_setup():
        if not selected.get():
            return
        try:
            path = Path(selected.get())
            cfg = json.loads(path.read_text(encoding='utf-8'))
            dist = simpledialog.askstring('WSL', '已安装的 WSL 发行版名称：')
            script = simpledialog.askstring('官方 CLI', 'WSL 内官方 quark-drive.cjs 绝对路径：')
            remote = simpledialog.askstring('目标目录', '已存在、已授权的网盘路径：', initialvalue='/CodexWorkspace')
            if not all([dist, script, remote]):
                return
            cfg['cloud'] = dict(enabled=False, distribution=dist, script=script, path=remote)
            write_json(path, cfg)
            show('已保存连接参数，自动上传尚未启用。点击连接检查，通过后可在配置中将 cloud.enabled 改为 true。首次 OAuth 请用官方工具完成。')
        except Exception as exc:
            messagebox.showerror('设置失败', str(exc))
    def install():
        if not selected.get():
            return messagebox.showinfo('需要配置', '请先打开配置')
        interval = load_config(Path(selected.get())).get('schedule', {}).get('interval_minutes', 30)
        if messagebox.askyesno('启用本机定时备份', f'每 {interval} 分钟检查，需当前用户保持登录。确认范围和恢复密钥均已设置？'):
            perform('install-schedule')
    buttons = [('新建配置', setup), ('打开配置', choose), ('创建恢复密钥', key), ('导入密钥', lambda: key(True)),
               ('检查范围', lambda: perform('inspect')), ('立即备份', lambda: perform('backup')),
               ('状态', lambda: perform('status')), ('恢复本地版本', restore_dialog), ('网盘参数', cloud_setup),
               ('连接检查', lambda: perform('cloud-check')), ('云端版本', lambda: perform('versions')), ('启用定时', install)]
    for i, (label, callback) in enumerate(buttons):
        ttk.Button(rows, text=label, command=callback).grid(row=i // 6, column=i % 6, padx=3, pady=4, sticky='ew')
    for col in range(6):
        rows.columnconfigure(col, weight=1)
    show('尚未开始备份。使用“新建配置”选择工程；检查完整范围后，再创建离线恢复密钥并备份。\n文件恢复与项目运行验证分别报告。')
    if smoke:
        window.withdraw()
        window.after(100, window.destroy)
    window.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Codex environment backup / 工作环境备份')
    parser.add_argument('command', nargs='?', default='gui', choices=['gui', 'gui-smoke', 'inspect', 'status', 'backup', 'worker',
        'new-key', 'import-key', 'restore', 'verify', 'cloud-check', 'versions', 'fetch', 'install-schedule'])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--key-file', type=Path)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--snapshot-id')
    args = parser.parse_args()
    if args.command in {'gui', 'gui-smoke'}:
        return gui(args.command == 'gui-smoke')
    if not args.config:
        parser.error('--config is required')
    for command, fields in {'new-key': ['key_file'], 'import-key': ['key_file'], 'restore': ['snapshot', 'destination'],
                             'verify': ['snapshot'], 'fetch': ['snapshot_id']}.items():
        if args.command == command and any(getattr(args, field) is None for field in fields):
            parser.error('Missing required operation arguments: ' + ', '.join(fields))
    try:
        result = action(args.command, args.config, key_file=args.key_file, snapshot=args.snapshot,
                        destination=args.destination, snapshot_id=args.snapshot_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps(dict(state='failed', error=f'{type(exc).__name__}: {exc}'), ensure_ascii=False))
        raise SystemExit(1)
