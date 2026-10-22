#!/usr/bin/env python3
"""Backup-first SummitDesk cleaning-team update. Run from project root.

This copies code only; run the database migration separately after install.
A failure during copying restores all originals automatically.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
FILES = {
    'floorplans/staff_tasks.py': 'staff_tasks.py',
    'floorplans/hut_staff.py': 'hut_staff.py',
    'floorplans/housekeeping_tasks.py': 'housekeeping_tasks.py',
    'floorplans/models.py': 'models.py',
    'floorplans/templates/floorplans/cleaner_team.html': 'cleaner_team.html',
    'floorplans/templates/floorplans/staff_tasks.html': 'staff_tasks.html',
    'floorplans/migrations/0012_offline_cleaners.py': '0012_offline_cleaners.py',
    'floorplans/test_cleaning_team_v123.py': 'test_cleaning_team_v123.py',
}
NEW = {'floorplans/migrations/0012_offline_cleaners.py', 'floorplans/test_cleaning_team_v123.py'}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def atomic_write(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=target.parent, prefix='.sd123_', delete=False) as out:
            temp = Path(out.name)
            out.write(data)
        os.chmod(temp, (target.stat().st_mode & 0o777) if target.exists() else 0o644)
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file() and (ROOT / 'floorplans/urls.py').is_file(),
            'Run from the SummitDesk Django project root.')
    require((ROOT / 'floorplans/static/floorplans/summitdesk_shell_v116.css').is_file(),
            'The unified SummitDesk navigation is required (v116).')
    for rel, filename in FILES.items():
        src, dst = PACKAGE / filename, ROOT / rel
        require(src.is_file() and not src.is_symlink(), f'Package file missing or unsafe: {filename}')
        require(not dst.is_symlink(), f'Refusing to overwrite symlink: {rel}')
        require(all(not parent.is_symlink() for parent in [dst.parent, *dst.parents] if parent != ROOT and ROOT in parent.parents),
                f'Unsafe directory: {rel}')
        if rel in NEW:
            require(not dst.exists(), f'Already present: {rel}. Installation may already be complete.')
        else:
            require(dst.is_file(), f'Expected existing project file missing: {rel}')
    existing_view = (ROOT / 'floorplans/staff_tasks.py').read_text(encoding='utf-8')
    require('def cleaner_team(' in existing_view and 'class OfflineCleaner' not in existing_view
            and 'add_offline' not in existing_view, 'Unexpected cleaning team code. No changes made.')
    existing_models = (ROOT / 'floorplans/models.py').read_text(encoding='utf-8')
    require('from .hut_staff import HutCleaner' in existing_models and 'OfflineCleaner' not in existing_models,
            'Unexpected floorplans model imports. No changes made.')
    current_migrations = list((ROOT / 'floorplans/migrations').glob('0012_*.py'))
    require(not current_migrations,
            'Another floorplans migration 0012 already exists. Do not overwrite migration history; inspect manually.')
    require('offline_assignee' in (PACKAGE / 'housekeeping_tasks.py').read_text(encoding='utf-8'),
            'Package model is incomplete.')
    contents = {rel: (PACKAGE / filename).read_bytes() for rel, filename in FILES.items()}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('cleaning_team_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel in FILES:
        target = ROOT / rel
        existed = target.is_file()
        manifest.append({'path': rel, 'existed': existed})
        if existed:
            backup_file = backup / rel
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_file)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for rel, data in contents.items():
            atomic_write(ROOT / rel, data)
    except Exception:
        for item in manifest:
            dst = ROOT / item['path']
            if item['existed']:
                shutil.copy2(backup / item['path'], dst)
            else:
                dst.unlink(missing_ok=True)
        raise
    print('SummitDesk cleaning team update installed.')
    print('Original files backed up at:', backup)
    print('NEXT: activate the virtual environment and load the PostgreSQL settings.')
    print('Then run: python manage.py check')
    print('Then run: python manage.py migrate floorplans')
    print('Then run: python manage.py test floorplans.test_cleaning_team_v123')
    print('Restart gunicorn only after all checks pass.')


if __name__ == '__main__':
    main()
