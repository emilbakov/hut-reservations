#!/usr/bin/env python3
"""Restore a specific backup created by install_v116.py."""
import json
from pathlib import Path
import shutil
import sys

root = Path.cwd().resolve()
if len(sys.argv) != 2:
    sys.exit('Usage: python3 v116_package/rollback_v116.py summitdesk_backups/shared_shell_TIMESTAMP')
backup = Path(sys.argv[1]).resolve()
backups_root = (root / 'summitdesk_backups').resolve()
if backups_root not in backup.parents or not backup.name.startswith('shared_shell_'):
    sys.exit('ERROR: Backup must be a shared_shell_* folder inside summitdesk_backups.')
manifest_file = backup / 'manifest.json'
if not manifest_file.is_file():
    sys.exit('ERROR: Backup manifest not found.')
manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
for item in manifest:
    path = Path(item['path'])
    if path.is_absolute() or '..' in path.parts or not path.parts:
        sys.exit('ERROR: Unsafe backup manifest path.')
    if item['existed'] and not (backup / path).is_file():
        sys.exit('ERROR: Backup incomplete: ' + str(path))
for item in manifest:
    target = root / item['path']
    if item['existed']:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup / item['path'], target)
    else:
        target.unlink(missing_ok=True)
print('Restored files from:', backup)
print('Run collectstatic, manage.py check and restart Gunicorn.')
