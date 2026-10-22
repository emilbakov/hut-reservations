#!/usr/bin/env python3
"""Install the SummitDesk visual bed redesign; backup before changing files.

Run from the Django project root: python3 v120_package/install_v120.py
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
FILES = {
    'floorplans/templates/floorplans/visual_beds.html': 'visual_beds.html',
    'floorplans/static/floorplans/visual_beds_v120.css': 'visual_beds_v120.css',
}


def require(condition, message):
    if not condition:
        raise SystemExit('Preflight failed: ' + message)


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.sd120_', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    require((ROOT / 'manage.py').is_file() and (ROOT / 'floorplans').is_dir(),
            'Run from the Django project root (folder containing manage.py).')
    original = ROOT / 'floorplans/templates/floorplans/visual_beds.html'
    require(original.is_file() and not original.is_symlink(), 'Existing visual_beds.html not found or is a symlink.')
    existing = original.read_text(encoding='utf-8')
    require('sd120-workspace' not in existing, 'Redesign already installed; refusing to overwrite it.')
    require(all(marker in existing for marker in ['v7-room', 'v7-grid', 'v9-item', 'v10-csv']),
            'Current visual bed template is not the expected layout. No files changed.')
    require((ROOT / 'floorplans/templatetags/summitdesk_nav.py').is_file(),
            'The shared SummitDesk navigation is missing; install the navigation release first.')
    contents = {relative: (PACKAGE / name).read_bytes() for relative, name in FILES.items()}
    require(all(contents.values()), 'A package file is empty.')
    for relative in FILES:
        target = ROOT / relative
        require(not target.is_symlink(), f'Refusing symlink target: {relative}')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('visual_beds_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for relative in FILES:
        target = ROOT / relative
        exists = target.is_file()
        manifest.append({'path': relative, 'existed': exists,
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest() if exists else None})
        if exists:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for relative, content in contents.items():
            atomic_write(ROOT / relative, content)
    except Exception:
        for entry in manifest:
            target = ROOT / entry['path']
            if entry['existed']:
                shutil.copy2(backup / entry['path'], target)
            else:
                target.unlink(missing_ok=True)
        raise
    print('SummitDesk visual bed redesign installed.')
    print('Backup:', backup)
    print('Next: python manage.py check && python manage.py collectstatic --noinput')


if __name__ == '__main__':
    main()
