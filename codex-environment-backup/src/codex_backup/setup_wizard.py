"""First-use workflow with explicit scope and original-key recovery."""
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .app import action, validate_key_location
from .archive import signature, verify_snapshot
from .bootstrap import load_setup_state, save_setup_state
from .bootstrap_windows import prepare_environment, authorize_cloud, request_restart_resume, clear_restart_resume
from .credentials import import_key, read_key
from .model import load_config, write_json
from .quark import QuarkClient
from .restore import restore
from .scheduler import install_schedule, lock
from .transfer import checked_envelope, fetch, list_snapshots, remote_files


def _make_config(config_path, roots, data_dir):
    config_path = Path(config_path)
    cfg = dict(format_version=1, codex_home=os.environ.get('CODEX_HOME', str(Path.home() / '.codex')),
        roots=roots, data_dir=str(Path(data_dir).resolve()), project_status='unknown',
        cloud=dict(enabled=False, distribution='', script='', path='/CodexWorkspace'),
        schedule=dict(interval_minutes=240))
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open('x', encoding='utf-8') as stream:
        json.dump(cfg, stream, ensure_ascii=False, indent=2)
    try:
        return load_config(config_path)
    except Exception:
        config_path.unlink()
        raise


def make_backup_config(config_path: Path, roots: list[dict], data_dir: Path) -> dict:
    if not roots:
        raise ValueError('请至少选择一个要备份的目录')
    def failed(error):
        raise ValueError('无法检查备份范围，请选择可读取的具体工程目录：' + str(error.filename)) from error
    for root in roots:
        for directory, folders, files in os.walk(Path(root['path']).expanduser(), followlinks=False, onerror=failed):
            names = set(files)
            if ('key.dpapi' in names and ('outbox' in folders or 'worker.lock' in names or 'status.json' in names)) or {'envelope.json', 'COMPLETE.json'} <= names:
                raise ValueError('所选范围包含旧备份仓库：' + directory + '。请改选工程、聊天或知识库的具体目录，不要选择包含备份仓库的上级目录。')
            folders[:] = [name for name in folders if not (Path(directory) / name).is_junction()]
    return _make_config(config_path, roots, data_dir)


def make_restore_config(config_path: Path, data_dir: Path) -> dict:
    return _make_config(config_path, [], data_dir)


def connect_cloud(config_path, state_dir, progress=None):
    cfg = load_config(config_path)
    prepared = prepare_environment(cfg, state_dir, progress)
    if prepared['state'] != 'ready':
        return prepared
    with lock(Path(cfg['data_dir'])):
        raw = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        raw['cloud'] = dict(raw.get('cloud', {}), enabled=False,
            distribution=prepared['distribution'], script=prepared['script'])
        write_json(Path(config_path), raw)
        authorize_cloud(load_config(config_path), progress)
        raw['cloud']['enabled'] = bool(raw['roots'])
        write_json(Path(config_path), raw)
    clear_restart_resume(state_dir)
    return dict(state='connected', backup_upload_enabled=raw['cloud']['enabled'])


def _empty_destination(destination):
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError('恢复目标必须为空目录，未覆盖任何文件')


def _portable_key(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 128:
        raise ValueError('请选择原离线恢复密钥文件')
    try:
        key = bytes.fromhex(path.read_text(encoding='ascii').strip())
    except (ValueError, UnicodeError) as exc:
        raise ValueError('恢复密钥文件格式不正确') from exc
    if len(key) != 32:
        raise ValueError('恢复密钥文件格式不正确')
    return key


def _authenticate_envelope(snapshot, key):
    envelope = checked_envelope(Path(snapshot))
    tag = envelope.pop('tag', '')
    if not hmac.compare_digest(tag, signature(envelope, key)):
        raise ValueError('恢复密钥与这个版本不匹配，或版本清单已损坏；未开始恢复')
    return envelope


def _import_verified_key(cfg, key_file, key):
    validate_key_location(cfg, key_file)
    data = Path(cfg['data_dir'])
    if (data / 'key.dpapi').exists():
        if not hmac.compare_digest(read_key(data), key):
            raise ValueError('此配置已有另一把密钥，未替换；请建立独立的恢复配置')
    else:
        import_key(data, key_file)


def restore_saved_snapshot(config_path, snapshot, destination, key_file):
    _empty_destination(destination)
    cfg = load_config(config_path)
    key = _portable_key(key_file)
    _authenticate_envelope(snapshot, key)
    _import_verified_key(cfg, key_file, key)
    return restore(Path(snapshot), Path(destination), key)


def _client(cfg):
    client = QuarkClient(cfg['cloud'], Path(cfg['data_dir']) / 'quark-runtime')
    return client, client.resolve_path(cfg['cloud']['path'])


def _metadata(client, reference, directory):
    items = remote_files(client, reference['fid'])
    for name in ['envelope.json', 'COMPLETE.json']:
        item = items.get(name, {})
        if item.get('dir') or not item.get('fid') or not 0 < item.get('size', 0) <= 16 * 1024 * 1024:
            raise ValueError('云端版本清单缺失或大小异常')
        result = client.download(item['fid'], Path(directory) / name)
        if Path(result).stat().st_size > 16 * 1024 * 1024:
            raise ValueError('云端版本清单过大')
    envelope = checked_envelope(Path(directory))
    if envelope['snapshot_id'] != reference['snapshot_id']:
        raise ValueError('云端版本身份不一致')
    return envelope


def cloud_versions(config_path):
    cfg = load_config(config_path)
    client, root = _client(cfg)
    rows, invalid = [], 0
    for reference in list_snapshots(client, root):
        with tempfile.TemporaryDirectory() as temp:
            try:
                envelope = _metadata(client, reference, Path(temp))
            except ValueError:
                invalid += 1
                continue
        rows.append(dict(snapshot_id=reference['snapshot_id'], created_at=envelope.get('created_at', '未知时间'),
            parts=len(envelope['parts']), cloud_fetch_supported=all(part['size'] <= 50 * 1024 * 1024 for part in envelope['parts']),
            state='密钥认证后才可恢复，覆盖范围待恢复报告确认'))
    return dict(versions=sorted(rows, key=lambda row: row['created_at'], reverse=True), skipped_invalid=invalid)


def restore_cloud_version(config_path, snapshot_id, destination, key_file):
    _empty_destination(destination)
    cfg = load_config(config_path)
    client, root = _client(cfg)
    refs = [row for row in list_snapshots(client, root) if row['snapshot_id'] == snapshot_id]
    if len(refs) != 1:
        raise ValueError('版本不存在或有重名，请刷新后重选')
    key = _portable_key(key_file)
    with tempfile.TemporaryDirectory() as temp:
        envelope = _metadata(client, refs[0], Path(temp))
        _authenticate_envelope(Path(temp), key)
    if any(part['size'] > 50 * 1024 * 1024 for part in envelope['parts']):
        raise ValueError('这个旧版本含超出网盘接口限制的分卷，请手动下载后使用本地恢复')
    _import_verified_key(cfg, key_file, key)
    target = Path(cfg['data_dir']) / 'inbox' / snapshot_id
    if target.exists():
        verify_snapshot(target, key)
    else:
        target = fetch(refs[0], client, Path(cfg['data_dir']) / 'inbox')
    return restore(target, Path(destination), key)


def launch_backup(config_path, schedule=False):
    cfg = load_config(config_path)
    if not cfg['roots']:
        raise ValueError('这是恢复配置，请先创建明确的备份范围')
    if not cfg['cloud'].get('enabled'):
        raise ValueError('请先完成网盘连接，避免仅在本机保存而误认为已上云')
    read_key(Path(cfg['data_dir']))
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('请使用已安装的程序启动后台备份')
    worker = Path(sys.executable).with_name('CodexEnvironmentBackupWorker.exe')
    if not worker.is_file():
        raise RuntimeError('后台程序缺失，请重新取得完整安装包')
    with lock(Path(cfg['data_dir'])):
        if schedule:
            write_json(Path(cfg['data_dir']) / 'schedule-request.json', dict(config_path=str(Path(config_path).resolve())))
    return subprocess.Popen([str(worker), 'worker', '--config', str(Path(config_path).resolve())],
        cwd=worker.parent, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def enable_schedule_after_backup(config_path, status):
    cfg = load_config(config_path)
    if not cfg['roots'] or status.get('state') != 'cloud_verified':
        raise ValueError('完整云端往返校验尚未通过，未启用定时备份')
    return install_schedule(Path(config_path))


def setup_gui(smoke=False, state_dir=None):
    import queue
    import threading
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import uuid

    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'CodexWorkspaceBackupData'
    state_dir = Path(state_dir) if state_dir else base / 'setup'
    window = tk.Tk()
    window.title('Codex 工作环境备份')
    window.geometry('920x780')
    window.minsize(820, 700)
    ttk.Label(window, text='备份与换机恢复', font=('Microsoft YaHei UI', 20)).pack(anchor='w', padx=24, pady=(20, 5))
    ttk.Label(window, text='按向导操作，无需输入命令。恢复后仍需检查工程依赖，旧聊天不会自动写入当前账号。').pack(anchor='w', padx=24)
    menu = ttk.Frame(window)
    menu.pack(fill='x', padx=24, pady=12)
    page = ttk.Frame(window)
    page.pack(fill='both', expand=True, padx=24)
    status = tk.StringVar(value='请选择备份这台电脑，或恢复到新电脑。')
    ttk.Label(window, textvariable=status, wraplength=860, justify='left').pack(fill='x', padx=24, pady=18)
    events = queue.Queue()
    current = dict(path=None, mode='backup', busy=False, versions=[])
    data = tk.StringVar()
    recovery_file = tk.StringVar()
    destination = tk.StringVar()
    timed = tk.BooleanVar(value=True)
    scope, versions = None, None
    editors = []
    roots = []

    def progress(message):
        events.put(('progress', message))

    def job(operation, completed):
        if current['busy']:
            return messagebox.showinfo('正在执行', '请等待当前操作完成')
        current['busy'] = True
        status.set('正在执行，请稍候……')
        def worker():
            try:
                value, error = operation(), None
            except Exception as exc:
                value, error = None, exc
            events.put(('done', completed, value, error))
        threading.Thread(target=worker, daemon=True).start()

    def consume():
        try:
            while True:
                item = events.get_nowait()
                if item[0] == 'progress':
                    status.set(item[1])
                else:
                    current['busy'] = False
                    if item[3]:
                        error = item[3]
                        message = str(error)
                        if isinstance(error, OSError):
                            message = '文件或网络操作未完成，请检查目录权限、磁盘空间和网络后重试。'
                        elif message.isascii():
                            message = '操作未完成，请检查连接、恢复密钥与版本完整性后重试。'
                        status.set('未完成：' + message)
                    else:
                        item[1](item[2])
        except queue.Empty:
            pass
        window.after(100, consume)

    def ensure_config():
        path = Path(current['path']) if current['path'] else base / (current['mode'] + '-config.json')
        if path.exists():
            load_config(path)
        elif current['mode'] == 'backup':
            selected = [roots[index] for index in scope.curselection()]
            make_backup_config(path, selected, Path(data.get()))
        else:
            make_restore_config(path, Path(data.get()))
        current['path'] = path
        for editor in editors:
            editor.configure(state='readonly' if isinstance(editor, ttk.Entry) else 'disabled')
        remembered = load_setup_state(state_dir / 'setup-state.json')
        remembered.update(config_path=str(path.resolve()), mode=current['mode'])
        save_setup_state(state_dir / 'setup-state.json', remembered)
        return path

    def guarded(callback):
        def call():
            if current['busy']:
                return messagebox.showinfo('正在执行', '请等待当前操作完成')
            try:
                callback()
            except Exception as exc:
                messagebox.showerror('操作尚未完成', str(exc))
        return call

    def choose_data():
        value = filedialog.askdirectory(title='选择本地备份数据位置，必须在采集范围外')
        if value:
            data.set(value)

    def key(importing=False):
        path = ensure_config()
        cfg = load_config(path)
        if current['mode'] == 'restore':
            value = filedialog.askopenfilename(title='选择原离线恢复密钥', filetypes=[('恢复密钥', '*.key'), ('所有文件', '*.*')])
            if value:
                _portable_key(value)
                recovery_file.set(value)
                status.set('已选择密钥；会先验证它是否匹配备份，再开始大文件下载和恢复。')
            return
        if (Path(cfg['data_dir']) / 'key.dpapi').exists():
            read_key(Path(cfg['data_dir']))
            status.set('此设置已保存本机密钥。请确认原离线副本在另一设备上，不会重新生成或替换。')
            return
        value = filedialog.askopenfilename(title='选择已有离线密钥') if importing else filedialog.asksaveasfilename(
            title='将恢复密钥另存到U盘等独立位置，不能与备份放在一起', initialfile='Codex-recovery.key', defaultextension='.key')
        if value:
            action('import-key' if importing else 'new-key', path, key_file=value)
            status.set('密钥已保存。请将离线副本另存到可信的独立设备，然后连接网盘。')

    def connected(result):
        if result['state'] == 'restart_required':
            if getattr(sys, 'frozen', False):
                request_restart_resume(Path(sys.executable), state_dir)
            status.set('系统组件需要重启，已保存进度。重新登录后可继续，也可从桌面入口打开。')
            if messagebox.askyesno('需要重启才能继续', '请先保存其他工作。现在重启电脑吗？'):
                subprocess.Popen(['shutdown.exe', '/r', '/t', '0'], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return
        if result['state'] != 'connected':
            status.set('准备尚未完成：系统权限未批准或组件安装失败。可以稍后点击连接重试。')
            return
        if current['mode'] == 'restore':
            path = Path(current['path'])
            job(lambda: cloud_versions(path), listed)
        else:
            status.set('网盘连接已验证。确认所选目录和离线密钥后，点击“开始备份”。')

    def connect():
        path = ensure_config()
        job(lambda: connect_cloud(path, state_dir, progress), connected)

    def listed(result):
        current['versions'] = result['versions']
        labels = [f"{row['created_at']} · {row['snapshot_id'][:8]} · {row['parts']}卷" + (' · 需手动下载' if not row['cloud_fetch_supported'] else '') for row in result['versions']]
        versions.configure(values=labels)
        if labels:
            versions.current(0)
            status.set('请选择版本及空恢复目录。版本须用原密钥认证，覆盖缺项会在恢复报告中列出。')
        else:
            status.set('尚未找到有效完成标记的版本。首次全量可能仍在上传，请稍后刷新。')

    def choose_destination():
        value = filedialog.askdirectory(title='选择空恢复目录，不会覆盖原工程')
        if value:
            _empty_destination(value)
            destination.set(value)

    def restored(result):
        location = Path(destination.get())
        status.set('文件已认证并恢复。请打开恢复目录，让新Codex读取CONTINUE.md和项目卡；业务工程运行与换机接续仍须验证。'
            + (' 部分路径仍需修复，请查看恢复报告。' if result['directory_links']['pending'] or result['git_worktrees']['pending'] else ''))
        if messagebox.askyesno('文件恢复完成，仍需验证工程', '现在打开恢复目录，查看接续文件和恢复报告吗？'):
            os.startfile(location)

    def recover(local=False):
        path = ensure_config()
        if not recovery_file.get():
            raise ValueError('请先选择原离线恢复密钥')
        if not destination.get():
            raise ValueError('请先选择空恢复目录')
        key_file, target = Path(recovery_file.get()), Path(destination.get())
        _empty_destination(target)
        if local:
            value = filedialog.askdirectory(title='选择含COMPLETE.json的完整快照目录')
            if value:
                job(lambda: restore_saved_snapshot(path, Path(value), target, key_file), restored)
        else:
            selected = versions.current()
            if selected < 0 or selected >= len(current['versions']):
                raise ValueError('请先连接网盘并选择可恢复版本')
            sid = current['versions'][selected]['snapshot_id']
            job(lambda: restore_cloud_version(path, sid, target, key_file), restored)

    def watch_backup(process, path):
        status_path = Path(load_config(path)['data_dir']) / 'status.json'
        if process.poll() is None:
            status.set('后台备份正在运行并校验云端回读。定时保护须等云端验证通过；关闭窗口后后台仍会完成已请求的设置。请保持联网和Windows登录。')
            window.after(1000, lambda: watch_backup(process, path))
            return
        current['busy'] = False
        result = json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
        if process.returncode != 0 or result.get('state') != 'cloud_verified':
            status.set('本次备份未完成云端验证。请稍后重试或检查已有后台任务；没有将它标记为已保护。')
            return
        status.set('此版本已完成云端往返校验。' + (' 原始位置有缺项，不能视为所有内容齐全。' if not result.get('complete') else '') + ' 项目运行仍需恢复验收。')
        if result.get('schedule_status') == 'preserved':
            status.set(status.get() + ' 原定时任务及程序绑定已保留。')
        elif result.get('schedule_status') == 'enabled':
            status.set(status.get() + ' 已启用此配置的定时备份，需保持Windows用户登录。')
        elif result.get('schedule_status') == 'pending':
            status.set(status.get() + ' 定时保护仍待设置，请重试备份或从高级操作检查。')

    def backup():
        path = ensure_config()
        cfg = load_config(path)
        if not messagebox.askyesno('确认开始备份', '将备份界面列出的目录，上传加密快照并回下载验证。确认已保存独立恢复密钥并开始吗？'):
            return
        process = launch_backup(path, schedule=timed.get())
        current['busy'] = True
        watch_backup(process, path)

    def select_mode(mode, existing=None, fresh=False):
        nonlocal scope, versions, roots
        for child in page.winfo_children():
            child.destroy()
        editors.clear()
        current.update(mode=mode, versions=[], path=existing)
        recovery_file.set('')
        profile = base / 'profiles' / uuid.uuid4().hex if fresh else base
        cfg_path = Path(existing) if existing else profile / (mode + '-config.json')
        cfg = load_config(cfg_path) if cfg_path.exists() else None
        timed.set(cfg is None)
        if cfg:
            current['path'] = cfg_path
        elif fresh:
            current['path'] = cfg_path
        data.set(cfg['data_dir'] if cfg else str(profile / (mode + '-data')))
        ttk.Label(page, text='备份这台电脑' if mode == 'backup' else '恢复到新电脑', font=('Microsoft YaHei UI', 15)).pack(anchor='w', pady=8)
        location = ttk.Frame(page)
        location.pack(fill='x', pady=4)
        ttk.Label(location, text='本地数据位置：').pack(side='left')
        data_entry = ttk.Entry(location, textvariable=data, state='readonly' if cfg else 'normal')
        data_entry.pack(side='left', fill='x', expand=True)
        data_button = ttk.Button(location, text='选择', command=guarded(choose_data), state='disabled' if cfg else 'normal')
        data_button.pack(side='right')
        editors.extend([data_entry, data_button])
        if mode == 'backup':
            ttk.Label(page, text='确认要采集的目录；可多选。程序不会自动找到所有外部服务数据。').pack(anchor='w', pady=5)
            scope = tk.Listbox(page, selectmode='extended', height=8, exportselection=False)
            scope.pack(fill='both', expand=True)
            roots = list(cfg['roots']) if cfg else []
            if not cfg:
                for candidate, kind in [(Path.home() / '.codex', 'codex'), (Path.home() / 'Documents/Codex', 'project'),
                    (Path.home() / '.cache/codex-runtimes', 'source'), (Path('E:/工作知识库'), 'vault'), (Path('E:/自生长'), 'vault')]:
                    if candidate.is_dir():
                        roots.append(dict(id=f'source-{len(roots)+1}', path=str(candidate), kind=kind))
            for root in roots:
                scope.insert('end', root['path'])
            scope.selection_set(0, 'end')
            def add_root():
                value = filedialog.askdirectory(title='选择工程、知识库或其他需要备份的目录')
                if value and not any(Path(root['path']).resolve() == Path(value).resolve() for root in roots):
                    roots.append(dict(id=f'added-{len(roots)+1}', path=value, kind='project'))
                    scope.insert('end', value)
                    scope.selection_set(len(roots)-1)
            add_button = ttk.Button(page, text='添加目录', command=guarded(add_root), state='disabled' if cfg else 'normal')
            add_button.pack(anchor='w', pady=5)
            editors.extend([scope, add_button])
            if cfg:
                scope.configure(state='disabled')
            actions = ttk.Frame(page)
            actions.pack(fill='x', pady=8)
            for text, callback in [('1 保存离线密钥', lambda: key(False)), ('使用已有密钥', lambda: key(True)),
                ('2 连接夸克', connect), ('3 开始备份', backup)]:
                ttk.Button(actions, text=text, command=guarded(callback)).pack(side='left', padx=(0, 8))
            ttk.Checkbutton(page, text='云端往返校验通过后，启用此配置的定时备份（新配置每4小时）', variable=timed).pack(anchor='w', pady=6)
        else:
            key_row = ttk.Frame(page)
            key_row.pack(fill='x', pady=8)
            ttk.Button(key_row, text='1 选择原恢复密钥', command=guarded(key)).pack(side='left')
            ttk.Label(key_row, textvariable=recovery_file, wraplength=600).pack(side='left', padx=8)
            ttk.Button(page, text='2 自动准备连接并读取网盘版本', command=guarded(connect)).pack(anchor='w', pady=8)
            versions = ttk.Combobox(page, state='readonly')
            versions.pack(fill='x', pady=8)
            ttk.Button(page, text='3 选择空恢复目录', command=guarded(choose_destination)).pack(anchor='w', pady=6)
            ttk.Label(page, textvariable=destination, wraplength=840).pack(anchor='w')
            ttk.Button(page, text='4 下载并恢复所选版本', command=guarded(recover)).pack(anchor='w', pady=12)
            ttk.Button(page, text='已有完整快照：直接本地恢复', command=guarded(lambda: recover(True))).pack(anchor='w', pady=4)
        status.set('已加载已有设置，未改写范围；需要不同范围可新建另一份设置。' if cfg else '确认本地数据位置后按编号操作。首次准备系统组件可能要求管理员权限和重启。')
        if cfg and (Path(cfg['data_dir']) / 'schedule-request.json').exists():
            status.set(status.get() + ' 定时保护请求仍待完成；后台成功验证后会启用，也可重试备份。')

    def open_existing():
        value = filedialog.askopenfilename(title='选择已有备份或恢复设置', filetypes=[('设置', '*.json')])
        if value:
            cfg = load_config(value)
            select_mode('backup' if cfg['roots'] else 'restore', value)

    for text, callback in [('备份这台电脑', lambda: select_mode('backup')), ('恢复到新电脑', lambda: select_mode('restore')),
        ('打开已有设置', open_existing), ('新建另一份设置', lambda: select_mode(current['mode'], fresh=True))]:
        ttk.Button(menu, text=text, command=guarded(callback)).pack(side='left', padx=(0, 8))

    def advanced():
        from .app import gui
        if not current['busy']:
            window.destroy()
            gui()
    ttk.Button(menu, text='高级操作', command=advanced).pack(side='right')
    def close():
        if current['busy'] and not messagebox.askyesno('操作尚未完成', '关闭会中断准备或恢复；已经启动的后台备份会继续。确定关闭窗口吗？', default='no'):
            return
        window.destroy()
    window.protocol('WM_DELETE_WINDOW', close)
    remembered = {} if smoke else load_setup_state(state_dir / 'setup-state.json')
    previous = remembered.get('config_path')
    select_mode(remembered.get('mode', 'backup'), previous if previous and Path(previous).is_file() else None)
    if smoke:
        window.withdraw()
        window.after(100, window.destroy)
    else:
        window.after(100, consume)
        if remembered.get('state') == 'restart_required' and current['path']:
            window.after(500, guarded(connect))
    window.mainloop()
