#!/usr/bin/env python3
"""Restore v129 code only, after safely reversing the 0014 migration.

Usage: python3 v129_package/rollback_v129.py summitdesk_backups/manager_digest_<timestamp>
Refuses to overwrite files modified after the v129 installation.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v129_package/rollback_v129.py <backup-folder>')
    backup = (ROOT / sys.argv[1]).resolve()
    if ROOT not in backup.parents or not backup.is_dir():
        raise RuntimeError('Backup folder must be inside project.')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        target = ROOT / item['path']
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f'Missing or symlinked installed file: {target}')
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != item['installed_sha256']:
            raise RuntimeError(f'File changed since installation: {target}; rollback refused.')
        if item['existed'] and not (backup / item['path']).is_file():
            raise RuntimeError(f'Backup missing for {target}')
    for item in manifest:
        target = ROOT / item['path']
        if item['existed']:
            shutil.copy2(backup / item['path'], target)
        else:
            target.unlink()
    print('v129 code restored. Check migration state and restart your service.')


if __name__ == '__main__':
    main()
