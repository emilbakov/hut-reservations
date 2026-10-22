#!/usr/bin/env python3
"""Restore source without deleting bookings or the additive v145 database tables."""
import argparse
import json
from pathlib import Path
from install_v147 import atomic_write, digest, safe_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('backup', nargs='?')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    parent = root / 'summitdesk_backups'
    if args.list:
        for path in sorted(parent.glob('performance_locale_v147_*/manifest.json')):
            print(path.parent.relative_to(root))
        return
    if not args.backup:
        parser.error('Specify the backup printed by the installer, or use --list.')
    supplied = Path(args.backup)
    backup = (root / supplied).resolve() if not supplied.is_absolute() else supplied.resolve()
    if backup.parent != parent or not backup.name.startswith('performance_locale_v147_'):
        raise RuntimeError('Use a performance_locale_v147 backup inside this project.')
    entries = json.loads((backup / 'manifest.json').read_text())
    for entry in entries:
        target = safe_path(root, entry['path'])
        if not target.is_file() or digest(target.read_bytes()) != entry['after_sha256']:
            raise RuntimeError('File edited since installation; rollback refused: ' + entry['path'])
        if entry['existed']:
            original = safe_path(backup, entry['path'])
            if not original.is_file():
                raise RuntimeError('Backup file missing: ' + entry['path'])
            if digest(original.read_bytes()) != entry['backup_sha256']:
                raise RuntimeError('Backup file changed: ' + entry['path'])
    if args.check:
        print('Rollback preflight passed; no files changed.')
        return
    for entry in entries:
        target = safe_path(root, entry['path'])
        if entry['existed']:
            atomic_write(target, (backup / entry['path']).read_bytes(), entry['mode'])
        elif entry['path'].startswith('bookings/migrations/'):
            # Keep migration history consistent with the intentionally retained tables.
            continue
        else:
            target.unlink()
    print('Source restored. Reservation and notification data were not deleted.')
    print('Run the rollback wrapper to collect static assets and restart Gunicorn.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
