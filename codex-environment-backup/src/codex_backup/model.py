"""Validated user-selected scope and read-only discovery."""
import json
import os
from pathlib import Path
import re
import tomllib


def logical_path(path):
    value = str(path)
    if os.name == 'nt':
        if value.startswith('\\\\?\\UNC\\'):
            value = '\\\\' + value[8:]
        elif value.startswith('\\\\?\\') and re.match(r'[A-Za-z]:[\\/]', value[4:]):
            value = value[4:]
    return Path(value)


def filesystem_path(path):
    path = logical_path(path).absolute()
    value = str(path)
    if os.name == 'nt':
        value = '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return Path(value)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value):
        raise ValueError('Invalid root identifier')
    if value.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}:
        raise ValueError('Reserved root identifier')
    return value


def load_config(path: Path) -> dict:
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    if cfg.get('format_version') != 1:
        raise ValueError('Unsupported config format')
    base = path.parent
    def absolute(value):
        p = Path(os.path.expandvars(value)).expanduser()
        return str(logical_path((p if p.is_absolute() else base / p).resolve()))
    cfg['codex_home'] = absolute(cfg.get('codex_home', os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    cfg['data_dir'] = absolute(cfg['data_dir'])
    ids = set()
    for entry in cfg.get('roots', []):
        rid = safe_id(entry['id'])
        if rid in ids:
            raise ValueError('Duplicate root identifier')
        ids.add(rid)
        entry['path'] = absolute(entry['path'])
        if entry.get('kind') not in {'project', 'vault', 'skill', 'codex', 'source'}:
            raise ValueError('Unknown root kind')
        if Path(cfg['data_dir']).is_relative_to(Path(entry['path'])):
            raise ValueError('Backup output must be outside all source roots')
    if Path(cfg['data_dir']).is_relative_to(Path(cfg['codex_home'])):
        raise ValueError('Backup output must be outside CODEX_HOME')
    cfg['_base'] = str(base)
    cfg['_path'] = str(path)
    return cfg


def discover(config: dict) -> dict:
    home = Path(config['codex_home'])
    setting = {}
    if (home / 'config.toml').is_file():
        setting = tomllib.loads((home / 'config.toml').read_text(encoding='utf-8-sig'))
    db = Path(setting.get('sqlite_home') or os.environ.get('CODEX_SQLITE_HOME') or home).expanduser()
    if not db.is_absolute():
        db = Path(config['_base']) / db
    roots, aliases, seen = [], {}, {}
    for raw in config.get('roots', []):
        entry = dict(raw)
        source = str(Path(entry['path']).resolve())
        key = os.path.normcase(source)
        if key in seen:
            aliases[entry['id']] = seen[key]
            continue
        seen[key] = entry['id']
        entry['state'] = 'available' if Path(source).is_dir() else 'missing'
        roots.append(entry)
    if any(r['kind'] == 'codex' and home.resolve().is_relative_to(Path(r['path'])) for r in roots) and not any(db.resolve().is_relative_to(Path(r['path'])) for r in roots):
        rid = 'sqlite-state'
        if any(r['id'] == rid for r in roots):
            raise ValueError('Reserved sqlite-state ID conflicts with a selected root')
        roots.append(dict(id=rid, path=str(db.resolve()), kind='codex', state='available' if db.is_dir() else 'missing'))
    return dict(format_version=1, codex_home=str(home), sqlite_home=str(db.resolve()),
                roots=roots, aliases=aliases)
