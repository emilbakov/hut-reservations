#!/usr/bin/env python3
"""Restore the v133 backup if the installed files have not been edited since."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
BACKUPS = (ROOT / 'summitdesk_backups').resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v133_package/rollback_v133.py summitdesk_backups/mobile_v133_TIMESTAMP')
    backup = Path(sys.argv[1]).resolve()
    if backup.parent != BACKUPS or not backup.name.startswith('mobile_v133_'):
        raise SystemExit('Refusing a backup outside summitdesk_backups/mobile_v133_*')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        rel = Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit('Unsafe path in backup manifest')
        target = ROOT / rel
        if target.is_symlink() or not target.is_file():
            raise SystemExit(f'File missing or symlink: {rel}')
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != item['installed_sha256']:
            raise SystemExit(f'File edited since install; refusing rollback: {rel}')
        if item['existed'] and not (backup / rel).is_file():
            raise SystemExit(f'Backup missing: {rel}')
    for item in manifest:
        rel = Path(item['path'])
        target = ROOT / rel
        if item['existed']:
            shutil.copy2(backup / rel, target)
        else:
            target.unlink()
    print('v133 rollback completed. Run collectstatic and restart your Django service.')


if __name__ == '__main__':
    main()
