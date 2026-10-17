"""Independent authenticated encrypted volumes, published only after verification."""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import uuid
import zipfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .collect import sha256, utcnow
from .model import write_json

PART_SIZE = 64 * 1024 * 1024
DEFAULT_PART_SIZE = 32 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def signature(value, key):
    return hmac.new(key, b'codex-backup-envelope-v1\x00' + canonical(value), hashlib.sha256).hexdigest()


def aad(sid, index, count):
    return canonical([1, sid, index, count])


def check_key(key):
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError('A 32-byte recovery key is required')


def seal(staging: Path, outbox: Path, recovery_key: bytes, *, part_size=DEFAULT_PART_SIZE) -> Path:
    check_key(recovery_key)
    if not 128 <= part_size <= PART_SIZE:
        raise ValueError('Invalid volume size')
    staging, outbox = Path(staging).resolve(), Path(outbox).resolve()
    if outbox.is_relative_to(staging):
        raise ValueError('Outbox must be outside staging')
    manifest = json.loads((staging / 'manifest.json').read_text(encoding='utf-8'))
    # A collection must not change between its manifest and encryption.
    for item in manifest['files']:
        file = staging / item['path']
        if not file.resolve().is_relative_to(staging) or file.stat().st_size != item['size'] or sha256(file) != item['sha256']:
            raise ValueError('Staging does not match manifest')
        if item['size'] in {32, 64, 65, 66}:
            content = file.read_bytes()
            if content == recovery_key or content.strip() == recovery_key.hex().encode('ascii'):
                raise ValueError('Recovery key is inside selected source scope; move it offline before backing up')
    outbox.mkdir(parents=True, exist_ok=True)
    sid = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='.packing-', dir=outbox) as temp_name:
        temp = Path(temp_name)
        archive = temp / 'payload.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for file in sorted(staging.rglob('*')):
                if file.is_symlink():
                    raise ValueError('Staging contains a link')
                zf.write(file, file.relative_to(staging).as_posix())
        count = (archive.stat().st_size + part_size - 1) // part_size
        payload = temp / 'snapshot'
        payload.mkdir()
        envelope = dict(format_version=1, snapshot_id=sid, created_at=utcnow(), cipher='AES-256-GCM', parts=[])
        with archive.open('rb') as stream:
            for index in range(count):
                data = stream.read(part_size)
                nonce = os.urandom(12)
                encrypted = nonce + AESGCM(recovery_key).encrypt(nonce, data, aad(sid, index, count))
                part = payload / f'{index:08d}.aes'
                part.write_bytes(encrypted)
                envelope['parts'].append(dict(name=part.name, size=len(encrypted), sha256=sha256(part)))
        envelope['tag'] = signature(envelope, recovery_key)
        write_json(payload / 'envelope.json', envelope)
        write_json(payload / 'COMPLETE.json', dict(format_version=1, snapshot_id=sid, envelope_sha256=sha256(payload / 'envelope.json')))
        verify_snapshot(payload, recovery_key)
        target = outbox / sid
        payload.rename(target)
    return target


@contextmanager
def opened_snapshot(snapshot: Path, recovery_key: bytes):
    check_key(recovery_key)
    snapshot = Path(snapshot).resolve()
    if (snapshot / 'envelope.json').stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Envelope too large')
    envelope = json.loads((snapshot / 'envelope.json').read_text(encoding='utf-8'))
    complete = json.loads((snapshot / 'COMPLETE.json').read_text(encoding='utf-8'))
    if envelope.get('format_version') != 1 or complete.get('format_version') != 1:
        raise ValueError('Unsupported snapshot format')
    tag = envelope.pop('tag', '')
    if not hmac.compare_digest(tag, signature(envelope, recovery_key)):
        raise ValueError('Wrong key or damaged envelope')
    sid, parts = envelope['snapshot_id'], envelope['parts']
    if complete.get('snapshot_id') != sid or complete.get('envelope_sha256') != sha256(snapshot / 'envelope.json') or not parts:
        raise ValueError('Incomplete snapshot')
    # Temporary plaintext exists only locally while verification/restoration runs.
    with tempfile.TemporaryFile(dir=snapshot.parent) as stream:
        for index, part in enumerate(parts):
            if part['name'] != f'{index:08d}.aes' or not 28 <= part['size'] <= PART_SIZE + 28:
                raise ValueError('Invalid volume metadata')
            path = snapshot / part['name']
            if path.is_symlink() or path.stat().st_size != part['size'] or sha256(path) != part['sha256']:
                raise ValueError('Missing or damaged volume')
            data = path.read_bytes()
            try:
                stream.write(AESGCM(recovery_key).decrypt(data[:12], data[12:], aad(sid, index, len(parts))))
            except InvalidTag as exc:
                raise ValueError('Wrong key or damaged volume') from exc
        stream.seek(0)
        with zipfile.ZipFile(stream) as zf:
            if zf.getinfo('manifest.json').file_size > 64 * 1024 * 1024:
                raise ValueError('Manifest too large')
            manifest = json.loads(zf.read('manifest.json'))
            if manifest.get('format_version') != 1:
                raise ValueError('Unsupported manifest')
            for item in manifest['files']:
                info = zf.getinfo(item['path'])
                if info.file_size != item['size']:
                    raise ValueError('File size mismatch')
                with zf.open(info) as file:
                    if hashlib.file_digest(file, 'sha256').hexdigest() != item['sha256']:
                        raise ValueError('File hash mismatch')
            yield zf, manifest


def verify_snapshot(snapshot: Path, recovery_key: bytes) -> dict:
    with opened_snapshot(snapshot, recovery_key) as (_, manifest):
        return manifest
