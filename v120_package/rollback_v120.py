#!/usr/bin/env python3
"""Restore the visual bed template and CSS from a specified installer backup.

Usage: python3 v120_package/rollback_v120.py summitdesk_backups/visual_beds_<timestamp>
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path.cwd().resolve()
ALLOWED = {
    'floorplans/templates/floorplans/visual_beds.html',
    'floorplans/static/floorplans/visual_beds_v120.css',
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v120_package/rollback_v120.py summitdesk_backups/visual_beds_<timestamp>')
    backup = (ROOT / sys.argv[1]).resolve()
    if backup.parent != (ROOT / 'summitdesk_backups').resolve() or not backup.name.startswith('visual_beds_'):
        raise SystemExit('Specify a visual_beds_* backup folder under summitdesk_backups.')
    manifest_path = backup / 'manifest.json'
    if not manifest_path.is_file():
        raise SystemExit('Backup manifest not found.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if {entry['path'] for entry in manifest} != ALLOWED or len(manifest) != len(ALLOWED):
        raise SystemExit('Unexpected manifest paths. Refusing rollback.')
    for entry in manifest:
        target = ROOT / entry['path']
        if target.is_symlink():
            raise SystemExit('Refusing symlink target: ' + entry['path'])
        if entry['existed']:
            source = backup / entry['path']
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
                raise SystemExit('Missing or altered backup: ' + entry['path'])
    for entry in manifest:
        target = ROOT / entry['path']
        if entry['existed']:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / entry['path'], target)
        else:
            target.unlink(missing_ok=True)
    print('Visual bed page restored from', backup)


if __name__ == '__main__':
    main()
