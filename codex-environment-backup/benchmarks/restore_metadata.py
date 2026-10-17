import contextlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

workspace = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace/'src'))
from codex_backup.restore import restore

results = []
temporary_root = workspace / '.test-work'
temporary_root.mkdir(exist_ok=True)
for count in [4000, 16000]:
    files = [dict(path=f'roots/r/file-{i}.txt') for i in range(count)]
    infos = [SimpleNamespace(filename=item['path'],external_attr=0,is_dir=lambda:False) for item in files]
    infos.append(SimpleNamespace(filename='roots/unknown/stop.txt',external_attr=0,is_dir=lambda:False))
    manifest = dict(roots=[dict(id='r')],files=files)
    @contextlib.contextmanager
    def opened(*args):
        yield SimpleNamespace(infolist=lambda:infos), manifest
    with tempfile.TemporaryDirectory(dir=temporary_root) as temp:
        start=time.perf_counter()
        with patch('codex_backup.restore.opened_snapshot',opened):
            try:
                restore(Path(temp)/'unused',Path(temp)/'restore',b'0'*32)
            except ValueError as error:
                assert str(error)=='Unexpected archive root'
            else:
                raise AssertionError('Validation did not reject the final unknown root')
        results.append(dict(files=count,seconds=time.perf_counter()-start))
print(json.dumps(results))
assert results[1]['seconds'] / results[0]['seconds'] < 12, 'Metadata validation grows superlinearly'
