"""Verified component downloads and resumable, credential-free setup state."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request

from .model import write_json


@contextmanager
def setup_lock(directory: Path):
    import msvcrt
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'setup.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError('另一个安装准备流程正在运行，请等待其完成') from exc
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _file_matches(path, spec):
    if not path.is_file() or path.stat().st_size != spec['size_bytes']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == spec['sha256']


def download_component(spec: dict, cache: Path, progress=None) -> Path:
    name, digest, size = spec.get('name', ''), spec.get('sha256', ''), spec.get('size_bytes')
    url = urllib.parse.urlsplit(spec.get('url', ''))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) or name.endswith('.'):
        raise ValueError('组件文件名无效')
    if url.scheme != 'https' or not url.netloc or url.username or url.password:
        raise ValueError('组件必须使用官方HTTPS下载地址')
    if not re.fullmatch('[a-f0-9]{64}', digest) or type(size) is not int or not 0 < size <= 2 * 1024 ** 3:
        raise ValueError('组件缺少有效的大小与SHA256校验信息')
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if not target.resolve().is_relative_to(cache):
        raise ValueError('组件缓存路径超出指定目录')
    with setup_lock(cache):
        if _file_matches(target, spec):
            if progress:
                progress(size, size)
            return target
        descriptor, temporary = tempfile.mkstemp(prefix=name + '.', suffix='.part', dir=cache)
        temporary = Path(temporary)
        try:
            copied, hashed = 0, hashlib.sha256()
            with os.fdopen(descriptor, 'wb') as output:
                with urllib.request.urlopen(spec['url'], timeout=60) as response:
                    if hasattr(response, 'geturl') and urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                        raise ValueError('组件下载被重定向到非HTTPS地址')
                    while block := response.read(1024 * 1024):
                        copied += len(block)
                        if copied > size:
                            raise ValueError('组件下载大小不符，请重试')
                        output.write(block)
                        hashed.update(block)
                        if progress:
                            progress(copied, size)
            if copied != size or hashed.hexdigest() != digest:
                raise ValueError('组件校验失败，未执行；请重试下载')
            temporary.replace(target)
            return target
        finally:
            if temporary.exists():
                temporary.unlink()


def _validate_state(state):
    fields = {'state', 'stage', 'distribution', 'distribution_id', 'script', 'config_path', 'mode', 'restart_boot', 'error_code', 'completed'}
    if not isinstance(state, dict) or set(state) - fields:
        raise ValueError('安装进度包含不支持的字段，不能保存凭据')
    for key, value in state.items():
        if key == 'completed':
            if not isinstance(value, list) or any(not isinstance(item, str) or item not in {'wsl', 'ubuntu', 'node', 'quark', 'system', 'distribution'} for item in value):
                raise ValueError('安装进度组件列表无效')
        elif not isinstance(value, str):
            raise ValueError('安装进度字段无效')


def load_setup_state(path: Path) -> dict:
    if not Path(path).exists():
        return {}
    state = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    _validate_state(state)
    return state


def save_setup_state(path: Path, state: dict):
    _validate_state(state)
    write_json(Path(path), state)
