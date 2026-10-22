#!/usr/bin/env python3
"""Safely roll back SummitDesk v137 calendar booking form UI to its pre-installation backup.

List backups:  python3 v137_package/rollback_v137.py --list
Preview:       python3 v137_package/rollback_v137.py --check summitdesk_backups/calendar_form_v137_TIMESTAMP
Restore:       python3 v137_package/rollback_v137.py summitdesk_backups/calendar_form_v137_TIMESTAMP
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()
TARGET = 'bookings/templates/bookings/calendar_booking_form.html'
TEST = 'bookings/test_calendar_form_ui_v137.py'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(target, data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd137_rollback_', delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        os.chmod(tmp, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(tmp, target)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup_dir', nargs='?', help='Exact v137 backup directory printed by installer')
    parser.add_argument('--check', action='store_true', help='Validate rollback only; do not change files')
    parser.add_argument('--list', action='store_true', help='List available v137 backups')
    args = parser.parse_args()
    root = (ROOT / 'summitdesk_backups').resolve()
    if args.list:
        if root.is_dir():
            for path in sorted(root.glob('calendar_form_v137_*')):
                if path.is_dir() and not path.is_symlink():
                    print(path.relative_to(ROOT))
        return
    if not args.backup_dir:
        parser.error('Provide a backup path, or use --list')
    backup = (ROOT / args.backup_dir).resolve()
    if backup.parent != root or not backup.name.startswith('calendar_form_v137_'):
        raise RuntimeError('Backup must be a direct calendar_form_v137_* child of summitdesk_backups.')
    if backup.is_symlink():
        raise RuntimeError('Symlink backup refused.')
    manifest_path = backup / 'manifest.json'
    if manifest_path.is_symlink():
        raise RuntimeError('Symlink manifest refused.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('version') != 'v137' or manifest.get('originals') != {TARGET: manifest.get('originals', {}).get(TARGET)} or set(manifest.get('installed', {})) != {TARGET, TEST} or manifest.get('created') != [TEST]:
        raise RuntimeError('Unexpected v137 manifest.')
    for rel, expected in manifest['installed'].items():
        target = ROOT / rel
        if target.is_symlink() or not target.is_file() or sha(target.read_bytes()) != expected:
            raise RuntimeError(f'Refusing rollback: {rel} changed since installation; manual review required.')
    saved = backup / TARGET
    if saved.is_symlink() or not saved.is_file() or sha(saved.read_bytes()) != manifest['originals'][TARGET]:
        raise RuntimeError('Backup is missing or damaged.')
    if (ROOT / TARGET).parent.is_symlink() or (ROOT / TEST).parent.is_symlink():
        raise RuntimeError('Symlink destination directory refused.')
    print('SummitDesk v137 rollback verification OK')
    print('Restore:', TARGET)
    print('Remove:', TEST)
    if args.check:
        print('Check-only mode: no files changed.')
        return
    atomic_write(ROOT / TARGET, saved.read_bytes())
    (ROOT / TEST).unlink()
    print('Restored pre-v137 calendar booking form and removed v137 test. No database changes.')
    print('Next: run Django check and restart Gunicorn after verification.')


if __name__ == '__main__':
    main()
