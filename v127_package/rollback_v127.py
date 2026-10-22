#!/usr/bin/env python3
"""Restore files from a v127 installer backup after checking their hashes."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path.cwd().resolve()

def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v127_package/rollback_v127.py summitdesk_backups/approval_dashboard_TIMESTAMP')
    backup = Path(sys.argv[1]).resolve()
    backups_root = (ROOT / 'summitdesk_backups').resolve()
    if backups_root not in backup.parents or not backup.name.startswith('approval_dashboard_'):
        raise SystemExit('Refusing unexpected backup directory.')
    entries = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in entries:
        rel = Path(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit('Unsafe backup entry.')
        target = ROOT / rel
        if target.is_symlink() or not target.is_file():
            raise SystemExit(f'Missing or unsafe installed file: {rel}')
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry['installed_sha256']:
            raise SystemExit(f'File changed since installation; refusing to overwrite: {rel}')
        if entry['existed'] and not (backup / rel).is_file():
            raise SystemExit(f'Missing backup file: {rel}')
    for entry in entries:
        rel = Path(entry['path'])
        target = ROOT / rel
        if entry['existed']:
            shutil.copy2(backup / rel, target)
        else:
            target.unlink()
    print('Restored v127 files. Run checks and restart Gunicorn if rolling back a live deployment.')

if __name__ == '__main__':
    main()
