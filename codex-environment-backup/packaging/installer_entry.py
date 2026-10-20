import argparse
import hashlib
import json
from pathlib import Path
import sys

from codex_backup.installer import installer_main, install_release
from codex_backup.model import filesystem_path


def main():
    parser = argparse.ArgumentParser(description='安装 Codex 工作环境备份')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--verify-install', type=Path, help='Install into an isolated acceptance directory without shortcuts or launch')
    args = parser.parse_args()
    resources = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    payload = resources / 'payload.zip'
    expected = (resources / 'payload.sha256').read_text(encoding='ascii').strip()
    with payload.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('安装程序内置数据校验失败')
    if args.verify_install:
        report = install_release(payload, args.verify_install)
        (filesystem_path(args.verify_install) / 'INSTALLATION-VERIFIED.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    else:
        installer_main(payload, args.smoke)


if __name__ == '__main__':
    main()
