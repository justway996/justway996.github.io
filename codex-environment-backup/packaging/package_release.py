"""Create an application payload from an explicit public-file whitelist."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


def package_release(destination, source_commit, tests_passed, source_published=False):
    project = Path(__file__).resolve().parents[1]
    destination = Path(destination).resolve()
    archive = destination.with_name(destination.name + '.zip')
    if destination.exists() or archive.exists():
        raise FileExistsError('Release output already exists')
    files = (project / 'packaging/release-files.txt').read_text(encoding='utf-8').splitlines()
    for name in files:
        path = PurePosixPath(name)
        if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or name == 'docs/progress.md':
            raise ValueError('Invalid public source whitelist')
        if not (project / name).is_file():
            raise FileNotFoundError(name)
    if len(files) != len(set(files)):
        raise ValueError('Duplicate public source file')
    shutil.copytree(project / 'dist/CodexEnvironmentBackup', destination, ignore=shutil.ignore_patterns('progress.md'))
    for name in files:
        target = destination / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((project / name).read_bytes().replace(b'\r\n', b'\n'))
    shutil.copytree(project / 'skills', destination / 'skills')
    (destination / 'launch.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0CodexEnvironmentBackupWorker.exe" setup\r\n')
    from_version = (project / 'src/codex_backup/__init__.py').read_text(encoding='utf-8')
    version = next(line.split("'")[1] for line in from_version.splitlines() if line.startswith('__version__'))
    metadata = dict(version=version, stage='installer_core_verified_clean_machine_pending', tests_passed=tests_passed,
        minimum_mapped_manifest_reader='0.2.0', source_commit=source_commit, source_published=source_published,
        source_url='https://github.com/justway996/justway996.github.io/tree/main/codex-environment-backup',
        full_environment_verified=False, cross_machine_verified=False, scheduled_backup_enabled=False,
        default_volume_mib=32, observed_download_limit_mib=50, overall_task_time_limit='PT0S', overlapping_runs='IgnoreNew',
        clean_machine_installer_verified=False, existing_environment_readonly_probe_verified=True)
    (destination / 'release.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    sums = []
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            sums.append(digest + '  ' + path.relative_to(destination).as_posix())
    (destination / 'SHA256SUMS.txt').write_bytes(('\n'.join(sums) + '\n').encode('utf-8'))
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in destination.rglob('*'):
            if path.is_file():
                output.write(path, str(Path(destination.name) / path.relative_to(destination)))
    return dict(archive=str(archive), bytes=archive.stat().st_size, version=version, files_hashed=len(sums), public_source_files=len(files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--tests-passed', required=True, type=int)
    parser.add_argument('--source-published', action='store_true')
    args = parser.parse_args()
    print(json.dumps(package_release(args.destination, args.source_commit, args.tests_passed, args.source_published)))
