#!/usr/bin/env python3
"""Rollback v128 if files have not been changed since installation.

Usage: python v128_package/rollback_v128.py summitdesk_backups/request_operations_<stamp>
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python v128_package/rollback_v128.py summitdesk_backups/request_operations_<timestamp>')
    backup = Path(sys.argv[1]).resolve()
    expected_parent = (ROOT / 'summitdesk_backups').resolve()
    if backup.parent != expected_parent or not backup.name.startswith('request_operations_'):
        raise SystemExit('Backup must be a v128 folder directly under summitdesk_backups/.')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest:
        rel = Path(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit('Unsafe manifest path.')
        path = ROOT / rel
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != ROOT):
            raise SystemExit(f'Symlink detected: {rel}')
        if not path.is_file():
            raise SystemExit(f'File missing; manual restore required: {rel}')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry['installed_sha256']:
            raise SystemExit(f'File modified after installation; manual restore required: {rel}')
        if entry['existed'] and not (backup / rel).is_file():
            raise SystemExit(f'Missing backup file: {rel}')
    for entry in manifest:
        rel = Path(entry['path'])
        path = ROOT / rel
        if entry['existed']:
            shutil.copy2(backup / rel, path)
        else:
            path.unlink()
    print('v128 source files restored. Restart your service only after checks pass.')


if __name__ == '__main__':
    main()
