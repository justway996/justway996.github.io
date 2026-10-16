"""Immutable remote versions; COMPLETE is always written and verified last."""
import json
from pathlib import Path
import re
import tempfile

from .collect import sha256


def remote_files(client, fid):
    result = {}
    for item in client.list_children(fid):
        name = item['file_name']
        if name in result:
            raise ValueError('Ambiguous same-name cloud item')
        result[name] = item
    return result


def checked_envelope(snapshot):
    marker = json.loads((snapshot / 'COMPLETE.json').read_text(encoding='utf-8'))
    envelope = json.loads((snapshot / 'envelope.json').read_text(encoding='utf-8'))
    if marker.get('format_version') != 1 or envelope.get('format_version') != 1 or marker.get('snapshot_id') != envelope.get('snapshot_id'):
        raise ValueError('Unsupported or inconsistent remote version')
    if marker.get('envelope_sha256') != sha256(snapshot / 'envelope.json'):
        raise ValueError('Corrupt envelope')
    if not re.fullmatch('[a-f0-9]{32}', envelope.get('snapshot_id', '')):
        raise ValueError('Unsafe snapshot ID')
    for index, part in enumerate(envelope['parts']):
        if part['name'] != f'{index:08d}.aes' or not 0 < part['size'] <= 64 * 1024 * 1024 + 28:
            raise ValueError('Unsafe volume')
    if not envelope['parts']:
        raise ValueError('Empty version')
    return envelope


def publish(snapshot: Path, client, remote_root_fid: str) -> dict:
    snapshot = Path(snapshot)
    envelope = checked_envelope(snapshot)
    for part in envelope['parts']:
        local = snapshot / part['name']
        if local.stat().st_size != part['size'] or sha256(local) != part['sha256']:
            raise ValueError('Local volume changed after sealing; publication stopped')
    sid = envelope['snapshot_id']
    fid = client.create_folder(sid, remote_root_fid)
    current = remote_files(client, fid)
    entries = [(snapshot / p['name'], p['size'], p['sha256']) for p in envelope['parts']]
    entries += [(snapshot / name, (snapshot / name).stat().st_size, sha256(snapshot / name)) for name in ['envelope.json', 'COMPLETE.json']]
    with tempfile.TemporaryDirectory(prefix='.cloud-check-', dir=snapshot.parent) as temp:
        for local, expected_size, expected_hash in entries:
            if local.stat().st_size != expected_size or sha256(local) != expected_hash:
                raise ValueError('Local file changed during upload')
            # Reusing a same-name part requires downloading and comparing its bytes.
            existing = current.get(local.name)
            remote = existing['fid'] if existing else client.upload(local, fid)['fid']
            copy = client.download(remote, Path(temp) / local.name)
            if copy.stat().st_size != expected_size or sha256(copy) != expected_hash:
                raise ValueError('Remote bytes differ; no complete version published')
    return dict(state='cloud_verified', snapshot_id=sid, fid=fid)


def list_snapshots(client, remote_root_fid: str) -> list[dict]:
    refs = []
    for folder in client.list_children(remote_root_fid):
        if not folder['dir'] or not re.fullmatch('[a-f0-9]{32}', folder['file_name']):
            continue
        children = remote_files(client, folder['fid'])
        if 'COMPLETE.json' in children and 'envelope.json' in children:
            refs.append(dict(snapshot_id=folder['file_name'], fid=folder['fid'], state='candidate_requires_key_verification'))
    return refs


def fetch(snapshot_ref: dict, client, inbox: Path) -> Path:
    sid = snapshot_ref['snapshot_id']
    if not re.fullmatch('[a-f0-9]{32}', sid):
        raise ValueError('Unsafe snapshot ID')
    inbox = Path(inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / sid
    if target.exists():
        raise FileExistsError('Inbox version already exists')
    with tempfile.TemporaryDirectory(prefix='.fetch-', dir=inbox) as temp:
        stage = Path(temp) / 'version'
        stage.mkdir()
        items = remote_files(client, snapshot_ref['fid'])
        for name in ['COMPLETE.json', 'envelope.json']:
            if name not in items or (items[name].get('size') or 0) > 16 * 1024 * 1024:
                raise ValueError('Missing or oversized cloud metadata')
            client.download(items[name]['fid'], stage / name)
        envelope = checked_envelope(stage)
        if envelope['snapshot_id'] != sid:
            raise ValueError('Wrong remote snapshot')
        for part in envelope['parts']:
            if part['name'] not in items:
                raise ValueError('Missing cloud volume')
            local = client.download(items[part['name']]['fid'], stage / part['name'])
            if local.stat().st_size != part['size'] or sha256(local) != part['sha256']:
                raise ValueError('Damaged cloud volume')
        stage.rename(target)
    return target
