#!/usr/bin/env python3
"""Pre-migration file rollback only. Refuses if bookings 0013 is applied.

After migration, keep schema and expiry protection until guest requests are
resolved; reverting requires a coordinated database and application plan.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v126_package/rollback_v126.py summitdesk_backups/guest_approval_TIMESTAMP')
    backup_root = (ROOT / 'summitdesk_backups').resolve()
    backup = (ROOT / sys.argv[1]).resolve()
    if backup.parent != backup_root or not backup.name.startswith('guest_approval_'):
        raise RuntimeError('Specify the exact guest_approval_ backup folder.')

    # Refuse rollback when the schema has already been migrated.
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_postgres')
        import django
        django.setup()
        from django.db import connection
        from django.db.migrations.recorder import MigrationRecorder
        applied = MigrationRecorder(connection).applied_migrations()
    except Exception as exc:
        raise RuntimeError('Cannot verify migration state. Set Django env/venv first; refusing rollback.') from exc
    if ('bookings', '0013_reservation_guest_request') in applied:
        raise RuntimeError(
            'Migration 0013 is already applied. Do not revert these files alone: '
            'pending guest requests could be auto-cancelled. Coordinate a database-safe rollback.'
        )

    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest:
        rel = Path(entry['path'])
        target = ROOT / rel
        if rel.is_absolute() or '..' in rel.parts or target.is_symlink():
            raise RuntimeError(f'Unsafe path: {rel}')
        if entry['existed'] and not (backup / rel).is_file():
            raise RuntimeError(f'Missing backup file: {rel}')
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != entry['installed_sha256']:
            raise RuntimeError(f'File changed since install; refusing to overwrite: {rel}')

    for entry in manifest:
        rel = Path(entry['path'])
        target = ROOT / rel
        if entry['existed']:
            shutil.copy2(backup / rel, target)
        else:
            target.unlink()
    print('Restored original files before migration from:', backup)


if __name__ == '__main__':
    main()
