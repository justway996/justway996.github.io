"""Local Windows DPAPI wrapping plus a separately retained portable recovery key."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, decrypt: bool):
    if os.name != 'nt':
        raise RuntimeError('Local key protection requires Windows')
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    if decrypt:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        ok = crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel32.LocalFree(output.data)


def protect(data):
    return _dpapi(data, False)


def unprotect(data):
    return _dpapi(data, True)


def new_key(data_dir: Path, export_path: Path):
    data_dir, export_path = Path(data_dir).resolve(), Path(export_path).resolve()
    if export_path.is_relative_to(data_dir):
        raise ValueError('Recovery key must be stored separately from backup data')
    if (data_dir / 'key.dpapi').exists():
        raise FileExistsError('A key already exists; do not silently rotate it')
    data_dir.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    with export_path.open('x', encoding='ascii') as file:
        file.write(key.hex() + '\n')
    (data_dir / 'key.dpapi').write_bytes(protect(key))


def import_key(data_dir: Path, recovery_file: Path):
    key = bytes.fromhex(Path(recovery_file).read_text(encoding='ascii').strip())
    if len(key) != 32:
        raise ValueError('Invalid recovery key file')
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    if (data_dir / 'key.dpapi').exists():
        raise FileExistsError('Local key already exists')
    (data_dir / 'key.dpapi').write_bytes(protect(key))


def read_key(data_dir: Path):
    key = unprotect((Path(data_dir) / 'key.dpapi').read_bytes())
    if len(key) != 32:
        raise ValueError('Invalid local key')
    return key
