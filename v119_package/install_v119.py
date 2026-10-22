#!/usr/bin/env python3
"""Install the SummitDesk property hub redesign (templates + CSS only).

Run from the Django project root. Existing files are backed up before any
write, changes are atomic, and a failed install restores the original state.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
FILES = {
    'floorplans/templates/floorplans/staff_hub.html': 'staff_hub.html',
    'floorplans/templates/floorplans/includes/hub_advanced_v119.html': 'hub_advanced_v119.html',
    'floorplans/static/floorplans/property_dashboard_v119.css': 'property_dashboard_v119.css',
    'floorplans/test_property_dashboard_v119.py': 'test_property_dashboard_v119.py',
}


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def atomic_write(destination, content):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.sd119_', dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        mode = (destination.stat().st_mode & 0o777) if destination.exists() else 0o644
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main():
    require((ROOT / 'manage.py').is_file() and (ROOT / 'floorplans/urls.py').is_file(),
            'Run this installer from /home/deploy/hut-reservations (the Django project root).')
    require((ROOT / 'floorplans/static/floorplans/summitdesk_shell_v116.css').is_file(),
            'Install the unified SummitDesk navigation first (v116).')
    require((ROOT / 'bookings/test_booking_access_v118.py').is_file(),
            'Install the New Booking permission fix first (v118).')
    current = ROOT / 'floorplans/templates/floorplans/staff_hub.html'
    require(current.is_file() and not current.is_symlink(), 'The property hub template is missing or unsafe.')
    old = current.read_text(encoding='utf-8')
    require('V38_FORECAST_START' in old and 'summitdesk_nav' in old,
            'Unexpected property hub template. No files changed; inspect before upgrading.')
    require('sd119-page' not in old,
            'This redesign appears to be installed already. Refusing a second installation.')
    for relative, filename in FILES.items():
        src = PACKAGE / filename
        dst = ROOT / relative
        require(src.is_file(), f'Missing package file: {filename}')
        require(not dst.is_symlink(), f'Refusing to overwrite symlink: {relative}')
        if relative != 'floorplans/templates/floorplans/staff_hub.html':
            require(not dst.exists(), f'File already exists: {relative}; refusing to overwrite.')
    template = (PACKAGE / 'staff_hub.html').read_text(encoding='utf-8')
    legacy = (PACKAGE / 'hub_advanced_v119.html').read_text(encoding='utf-8')
    require('summitdesk_nav' in template and 'staff_new_booking' in template,
            'The shared navigation or authorized booking link is missing.')
    require('{% include \'floorplans/includes/hub_advanced_v119.html\' %}' in template,
            'The advanced report include is missing.')
    require('V38_FORECAST_START' in legacy and 'V39_ALERTS_END' in legacy,
            'The existing management reports were not preserved.')
    # Verify every source before making a backup or changing any file.
    contents = {relative: (PACKAGE / filename).read_bytes() for relative, filename in FILES.items()}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('property_dashboard_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for relative in FILES:
        dest = ROOT / relative
        existed = dest.is_file()
        manifest.append({'path': relative, 'existed': existed})
        if existed:
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, target)
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
    print('SummitDesk property dashboard installed successfully.')
    print('Backup:', backup)
    print('No migrations. Run: python manage.py check')
    print('Tests: python manage.py test floorplans.test_property_dashboard_v119')


if __name__ == '__main__':
    main()
