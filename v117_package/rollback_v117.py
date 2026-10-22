#!/usr/bin/env python3
"""Restore the latest staff-login backup created by install_v117.py."""
import json
from pathlib import Path
import shutil

ROOT = Path.cwd().resolve()
BACKUPS = ROOT / 'summitdesk_backups'


def main():
    if not (ROOT / 'manage.py').is_file():
        raise SystemExit('Run from the Django project root.')
    backups = sorted(BACKUPS.glob('staff_login_*/manifest.json'))
    if not backups:
        raise SystemExit('No v117 backup found.')
    backup = backups[-1].parent
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise SystemExit('Invalid backup manifest path.')
        target = ROOT / relative
        if item['existed']:
            source = backup / relative
            if not source.is_file():
                raise SystemExit('Missing backup file: ' + str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            target.unlink(missing_ok=True)
    print('Restored original files from:', backup)
    print('Run collectstatic and restart Gunicorn after checking Django.')


if __name__ == '__main__':
    main()
