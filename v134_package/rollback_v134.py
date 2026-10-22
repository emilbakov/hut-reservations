#!/usr/bin/env python3
"""Restore v134 source files from a backup if they have not been edited."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
BACKUPS = (ROOT / 'summitdesk_backups').resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v134_package/rollback_v134.py summitdesk_backups/communications_v134_TIMESTAMP')
    backup = Path(sys.argv[1]).resolve()
    if backup.parent != BACKUPS or not backup.name.startswith('communications_v134_'):
        raise SystemExit('Refusing a backup outside summitdesk_backups/communications_v134_*')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        rel = Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit('Unsafe path in manifest')
        target = ROOT / rel
        if target.is_symlink() or not target.is_file():
            raise SystemExit(f'File missing or symlink: {rel}')
        if hashlib.sha256(target.read_bytes()).hexdigest() != item['installed_sha256']:
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
    print('v134 source rollback complete. Database tables were NOT removed.')
    print('Restart Django. Leave the 0016 tables in place unless performing a separate reviewed DB rollback.')


if __name__ == '__main__':
    main()
