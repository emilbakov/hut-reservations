#!/usr/bin/env python3
"""Restore the previous cleaning-team UI/handlers, retaining new DB schema.

The offline-cleaner model and migration are deliberately kept, to avoid
losing any saved name-only cleaners and task assignments. This is a UI/code
rollback, not a destructive database rollback.
"""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path.cwd().resolve()
KEEP = {
    'floorplans/hut_staff.py',
    'floorplans/housekeeping_tasks.py',
    'floorplans/models.py',
    'floorplans/migrations/0012_offline_cleaners.py',
    'floorplans/test_cleaning_team_v123.py',
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 v123_package/rollback_v123.py summitdesk_backups/cleaning_team_TIMESTAMP')
    backup = Path(sys.argv[1]).resolve()
    allowed_root = (ROOT / 'summitdesk_backups').resolve()
    if backup.parent != allowed_root or not backup.name.startswith('cleaning_team_'):
        raise SystemExit('Invalid backup location')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest:
        rel = entry['path']
        if rel in KEEP:
            continue
        target = ROOT / rel
        if entry['existed']:
            original = backup / rel
            if not original.is_file() or target.is_symlink():
                raise RuntimeError('Missing original or unsafe target: ' + rel)
            shutil.copy2(original, target)
        else:
            target.unlink(missing_ok=True)
    print('Previous team UI and handlers restored.')
    print('New schema/model files were intentionally retained to preserve cleaner assignments.')
    print('Run python manage.py check and restart gunicorn.')


if __name__ == '__main__':
    main()
