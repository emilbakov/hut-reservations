#!/usr/bin/env python3
"""Restore the original test files from an installer-created backup.

Usage: python3 summitdesk_test_fix_package/rollback_test_fixes.py summitdesk_backups/test_fixes_TIMESTAMP
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path.cwd().resolve()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 summitdesk_test_fix_package/rollback_test_fixes.py summitdesk_backups/test_fixes_TIMESTAMP')
    backup = Path(sys.argv[1]).resolve()
    allowed = (ROOT / 'summitdesk_backups').resolve()
    if backup.parent != allowed or not backup.name.startswith('test_fixes_'):
        raise SystemExit('Refusing backup outside project test-fix backup directory')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest:
        rel = entry['path']
        if rel not in {'bookings/tests.py', 'bookings/test_manual_booking.py'}:
            raise SystemExit(f'Unexpected file in manifest: {rel}')
        target = ROOT / rel
        saved = backup / rel
        if target.is_symlink() or saved.is_symlink() or not target.is_file() or not saved.is_file():
            raise SystemExit(f'Unsafe or missing file: {rel}')
        if sha(target.read_bytes()) != entry['after_sha256']:
            raise SystemExit(f'{rel} changed since installation; refusing to overwrite')
        if sha(saved.read_bytes()) != entry['before_sha256']:
            raise SystemExit(f'Backup checksum mismatch: {rel}')
    for entry in manifest:
        rel = entry['path']
        shutil.copy2(backup / rel, ROOT / rel)
        print(f'Restored {rel}')
    print('Original test files restored. No application code or database changes.')


if __name__ == '__main__':
    main()
