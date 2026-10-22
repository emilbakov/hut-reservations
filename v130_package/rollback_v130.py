#!/usr/bin/env python3
"""Rollback v130 code only; first reverse migration 0015 when safe.

Usage: python3 v130_package/rollback_v130.py summitdesk_backups/manager_preferences_<timestamp>
Refuses to overwrite code modified since installation.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v130_package/rollback_v130.py <backup-folder>')
    backup = (ROOT / sys.argv[1]).resolve()
    if ROOT not in backup.parents or not backup.is_dir():
        raise RuntimeError('Backup folder must be inside project.')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest:
        target = ROOT / entry['path']
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f'Missing or symlinked installed file: {target}')
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry['installed_sha256']:
            raise RuntimeError(f'File changed since v130 installation: {target}; rollback refused.')
        if entry['existed'] and not (backup / entry['path']).is_file():
            raise RuntimeError(f'Backup missing for: {target}')
    for entry in manifest:
        target = ROOT / entry['path']
        if entry['existed']:
            shutil.copy2(backup / entry['path'], target)
        else:
            target.unlink()
    print('v130 source code restored. Verify migration state and restart your service.')


if __name__ == '__main__':
    main()
