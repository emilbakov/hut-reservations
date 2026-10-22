#!/usr/bin/env python3
"""Restore the property hub from a specific installer backup directory.

Usage: python3 v119_package/rollback_v119.py summitdesk_backups/property_dashboard_YYYYMMDD_...
"""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path.cwd().resolve()
ALLOWED = {
    'floorplans/templates/floorplans/staff_hub.html',
    'floorplans/templates/floorplans/includes/hub_advanced_v119.html',
    'floorplans/static/floorplans/property_dashboard_v119.css',
    'floorplans/test_property_dashboard_v119.py',
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v119_package/rollback_v119.py summitdesk_backups/property_dashboard_<timestamp>')
    backup = (ROOT / sys.argv[1]).resolve()
    backups_root = (ROOT / 'summitdesk_backups').resolve()
    if backup.parent != backups_root or not backup.name.startswith('property_dashboard_'):
        raise SystemExit('Backup path must be a property_dashboard_* folder under summitdesk_backups.')
    manifest_path = backup / 'manifest.json'
    if not manifest_path.is_file():
        raise SystemExit('Backup manifest not found.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if {item['path'] for item in manifest} != ALLOWED:
        raise SystemExit('Unexpected backup contents; refusing rollback.')
    for entry in manifest:
        target = ROOT / entry['path']
        if target.is_symlink():
            raise SystemExit(f'Refusing to restore through symlink: {entry["path"]}')
        if entry['existed'] and not (backup / entry['path']).is_file():
            raise SystemExit(f'Missing backup: {entry["path"]}')
    for entry in manifest:
        target = ROOT / entry['path']
        if entry['existed']:
            shutil.copy2(backup / entry['path'], target)
        else:
            target.unlink(missing_ok=True)
    print('Property dashboard restored from', backup)


if __name__ == '__main__':
    main()
