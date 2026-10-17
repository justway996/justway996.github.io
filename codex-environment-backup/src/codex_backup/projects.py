"""Recorded project declarations; commands are never executed by indexing."""
import json
from pathlib import PurePosixPath
import tomllib

from .model import logical_path, write_json


MARKERS = {'package.json', 'pyproject.toml', 'requirements.txt'}
EVIDENCE = MARKERS | {'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'poetry.lock',
    'uv.lock', 'Pipfile.lock', 'AGENTS.md', 'CONTINUE.md', 'README.md', '.python-version', '.node-version', '.nvmrc'}
CACHES = {'node_modules', '.pnpm-store', '.git', '.venv', 'venv', '__pycache__', '.pytest_cache'}


def project_index(staging, files, roots):
    eligible = {root['id'] for root in roots if root['kind'] in {'project', 'codex'}}
    candidates = {}
    for file in files:
        path = PurePosixPath(file['path'])
        if path.parts[1] not in eligible or any(part in CACHES for part in path.parts[2:]):
            continue
        if path.name in EVIDENCE:
            candidates.setdefault(str(path.parent), []).append(file)
    projects = []
    for path, evidence in sorted(candidates.items()):
        if not any(PurePosixPath(f['path']).name in MARKERS for f in evidence):
            continue
        declared, unknowns = {}, ['Runtime, install, start and test commands have not been verified']
        for file in evidence:
            name = PurePosixPath(file['path']).name
            if name not in {'package.json', 'pyproject.toml'}:
                continue
            try:
                if file['size'] > 2 * 1024 * 1024:
                    raise ValueError('Declaration exceeds indexing limit; raw file preserved')
                text = (staging / file['path']).read_text(encoding='utf-8-sig')
                if name == 'package.json':
                    package = json.loads(text)
                    if not isinstance(package, dict):
                        raise ValueError('Expected object')
                    declared.update({key: package[key] for key in ['name', 'packageManager', 'engines', 'scripts'] if key in package})
                else:
                    package = tomllib.loads(text)
                    declared.update({key: package.get('project', {})[key] for key in ['name', 'requires-python', 'scripts'] if key in package.get('project', {})})
                    if 'build-system' in package:
                        declared['build-system'] = package['build-system']
            except (ValueError, TypeError, UnicodeError) as exc:
                unknowns.append(f'{name}: {type(exc).__name__}; inspect preserved source')
        projects.append(dict(path=path, declared=declared,
            source_hashes={f['path']: f['sha256'] for f in evidence}, unknowns=unknowns))
    return projects


def write_project_index(target, destination, manifest):
    projects = [dict(row, restored_path=str(logical_path(destination / row['path']))) for row in manifest.get('projects', [])]
    write_json(target / 'PROJECTS.json', projects)
    lines = ['# 恢复后的工程索引', '', '以下命令来自原工程声明，仅供核对，尚未执行。先读项目卡、AGENTS.md 和 CONTINUE.md。', '']
    if not projects:
        lines += ['此快照没有工程声明索引。请按 PATH-MAPPING.json 检查 roots，不能据此认定没有工程。', '']
    for row in projects:
        lines += [f"## {row['path']}", '', f"恢复位置：{row['restored_path']}", '',
            '声明的环境与命令：', '', '```json', json.dumps(row['declared'], ensure_ascii=False, indent=2), '```', '',
            '依赖、锁文件与交接来源（哈希见 PROJECTS.json）：', '']
        lines += ['- ' + path for path in row['source_hashes']]
        lines += ['', '待验证：' + '；'.join(row['unknowns']), '']
    (target / 'PROJECTS.md').write_text('\n'.join(lines), encoding='utf-8')
