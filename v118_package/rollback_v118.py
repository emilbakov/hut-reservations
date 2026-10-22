#!/usr/bin/env python3
"""Restore files from the exact backup directory printed by install_v118.py."""
import json
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit('Usage: python3 v118_package/rollback_v118.py summitdesk_backups/booking_403_<timestamp>')
root = Path.cwd().resolve()
backup = Path(sys.argv[1]).resolve()
if not backup.is_relative_to(root / 'summitdesk_backups') or not backup.name.startswith('booking_403_'):
    raise SystemExit('Refusing backup path outside SummitDesk booking_403 backups.')
manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
for entry in manifest:
    relative = Path(entry['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise SystemExit('Invalid backup manifest path')
    target = root / relative
    if entry['existed']:
        shutil.copy2(backup / relative, target)
    else:
        target.unlink(missing_ok=True)
print('Restored original files from:', backup)
