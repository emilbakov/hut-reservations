#!/usr/bin/env python3
"""Restore SummitDesk pre-v138 property calendar and remove added v138 files."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()
BACKUP_ROOT = ROOT / 'summitdesk_backups'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(target, data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd138_restore_', delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        os.chmod(tmp, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(tmp, target)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', nargs='?', help='Backup path printed by installer')
    parser.add_argument('--check', action='store_true', help='Preview rollback; do not change files')
    parser.add_argument('--list', action='store_true', help='List property-calendar v138 backups')
    args = parser.parse_args()
    if args.list:
        if BACKUP_ROOT.is_dir():
            for p in sorted(BACKUP_ROOT.glob('property_calendar_v138_*')):
                if p.is_dir() and not p.is_symlink():
                    print(p.relative_to(ROOT))
        return
    if not args.backup:
        parser.error('Supply exact backup path, or use --list')
    backup = (ROOT / args.backup).resolve()
    if backup.parent != BACKUP_ROOT.resolve() or not backup.name.startswith('property_calendar_v138_') or backup.is_symlink():
        raise RuntimeError('Backup must be a direct property_calendar_v138_* child of summitdesk_backups.')
    manifest_file = backup / 'manifest.json'
    if manifest_file.is_symlink():
        raise RuntimeError('Symlink manifest refused.')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    from install_v138_property import CHANGES, ADDED
    if (manifest.get('version') != 'v138-property' or set(manifest.get('originals', {})) != set(CHANGES)
            or set(manifest.get('installed', {})) != set(CHANGES) | set(ADDED)
            or set(manifest.get('created', [])) != set(ADDED)):
        raise RuntimeError('Invalid backup manifest.')
    originals = {}
    for rel, expected in manifest['originals'].items():
        saved = backup / rel
        if saved.is_symlink() or not saved.is_file() or sha(saved.read_bytes()) != expected:
            raise RuntimeError('Missing or damaged backup: ' + rel)
        originals[rel] = saved.read_bytes()
    for rel, expected in manifest['installed'].items():
        p = ROOT / rel
        if p.is_symlink() or not p.is_file() or sha(p.read_bytes()) != expected:
            raise RuntimeError('Refusing rollback: installed file changed since v138: ' + rel)
        parent = p.parent
        while parent != ROOT:
            if parent.is_symlink():
                raise RuntimeError('Symlink directory refused: ' + str(parent))
            parent = parent.parent
    print('SummitDesk v138 Property Calendar rollback preflight OK')
    print('Restore:', ', '.join(CHANGES))
    print('Remove:', ', '.join(ADDED))
    if args.check:
        print('Check-only mode: no files changed.')
        return
    for rel, data in originals.items():
        atomic_write(ROOT / rel, data)
    for rel in ADDED:
        (ROOT / rel).unlink()
    print('Restored original Property Calendar and removed v138 additions.')
    print('No database changes. Run Django check and restart Gunicorn after verification.')


if __name__ == '__main__':
    main()
