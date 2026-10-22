#!/usr/bin/env python3
"""Restore the exact Property Calendar template backed up before v143."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()
BACKUPS = ROOT / 'summitdesk_backups'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('backup', nargs='?')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        for manifest in sorted(BACKUPS.glob('property_arrival_v143_*/manifest.json')):
            print(manifest.parent.relative_to(ROOT))
        return
    if not args.backup:
        parser.error('Pass backup path or --list.')
    backup = (ROOT / args.backup).resolve()
    if BACKUPS.resolve() not in backup.parents or not backup.name.startswith('property_arrival_v143_'):
        parser.error('Invalid backup path.')
    manifest = json.loads((backup / 'manifest.json').read_text())
    if manifest.get('version') != 'v143' or manifest.get('file') != 'floorplans/templates/floorplans/property_calendar_v138.html':
        parser.error('Invalid backup manifest.')
    target = ROOT / manifest['file']
    if not target.is_file() or target.is_symlink() or sha(target.read_bytes()) != manifest['installed']:
        parser.error('Current template differs from installed v143; refusing overwrite.')
    original = (backup / manifest['file']).read_bytes()
    if sha(original) != manifest['original']:
        parser.error('Backup checksum mismatch.')
    print('v143 rollback preflight OK.')
    if args.check:
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd142_rollback_', delete=False) as f:
        temp = Path(f.name)
        f.write(original)
    try:
        os.chmod(temp, target.stat().st_mode & 0o777)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    print('v143 rolled back to ' + manifest['baseline'] + ' template.')

if __name__ == '__main__':
    main()
