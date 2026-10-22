#!/usr/bin/env python3
"""Safely roll back v132 using its install backup.

Usage: python3 v132_package/rollback_v132.py summitdesk_backups/manager_digest_history_<timestamp>
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v132_package/rollback_v132.py <backup-folder>')
    backup = (ROOT / sys.argv[1]).resolve()
    if ROOT not in backup.parents or not backup.is_dir() or not backup.name.startswith('manager_digest_history_'):
        raise RuntimeError('Expected a v132 backup folder inside this project.')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest:
        rel = Path(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('Unsafe manifest path.')
        target = ROOT / rel
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f'Missing or symlinked installed file: {target}')
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry['installed_sha256']:
            raise RuntimeError(f'File changed since installation: {target}; rollback refused.')
        if entry['existed'] and not (backup / rel).is_file():
            raise RuntimeError(f'Backup missing: {rel}')
    for entry in manifest:
        rel = Path(entry['path'])
        target = ROOT / rel
        if entry['existed']:
            shutil.copy2(backup / rel, target)
        else:
            target.unlink()
    print('v132 source files restored. No database migration reversal is necessary.')


if __name__ == '__main__':
    main()
