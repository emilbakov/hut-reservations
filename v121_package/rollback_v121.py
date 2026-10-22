#!/usr/bin/env python3
"""Restore a single v121 installation backup. Run from Django project root.

Usage: python3 v121_package/rollback_v121.py summitdesk_backups/booking_ui_<timestamp>
"""
import json
import shutil
import sys
from pathlib import Path

root = Path.cwd().resolve()
if len(sys.argv) != 2:
    raise SystemExit('Specify the backup directory printed by the installer.')
backup = (root / sys.argv[1]).resolve()
if backup.parent != root / 'summitdesk_backups' or not backup.name.startswith('booking_ui_'):
    raise SystemExit('Backup must be a booking_ui_* folder in summitdesk_backups.')
manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
for entry in manifest:
    rel = Path(entry['path'])
    if rel.is_absolute() or '..' in rel.parts:
        raise SystemExit('Unsafe backup manifest path.')
    dest = root / rel
    if entry['existed']:
        shutil.copy2(backup / rel, dest)
    else:
        dest.unlink(missing_ok=True)
print('Restored original booking views and removed added files.')
