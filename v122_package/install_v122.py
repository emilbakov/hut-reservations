#!/usr/bin/env python3
"""Install the small staff booking calendar with a backup and rollback support.

Run from the SummitDesk Django root after v121. No migrations or new URLs.
Preflight all inputs and patch anchors before modifying the project.
"""
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
MANUAL = 'bookings/manual_bookings.py'
PROPERTY = 'floorplans/staff_new_booking.py'
TEMPLATE = 'bookings/templates/bookings/staff_booking_v121.html'
HELPER = 'bookings/booking_calendar_v122.py'
TEST = 'bookings/test_booking_calendar_v122.py'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def once(source, old, new, rel):
    n = source.count(old)
    require(n == 1, f'{rel}: expected one v121 anchor, found {n}. Nothing installed.')
    return source.replace(old, new)


def patch_manual(src):
    src = once(src,
        'from .staff_booking_ui_v121 import availability_summary',
        'from .staff_booking_ui_v121 import availability_summary\nfrom .booking_calendar_v122 import booking_month', MANUAL)
    src = once(src,
        '        "availability": availability_summary(rooms, free, start, end),',
        '''        "availability": availability_summary(rooms, free, start, end),
        "booking_calendar": booking_month(rooms, start, end, today=today,
            month_value=request.POST.get("cal_month") if request.method == "POST" else request.GET.get("cal_month")),''', MANUAL)
    return src


def patch_property(src):
    src = once(src,
        'from bookings.staff_booking_ui_v121 import availability_summary',
        'from bookings.staff_booking_ui_v121 import availability_summary\nfrom bookings.booking_calendar_v122 import booking_month', PROPERTY)
    src = once(src,
        '        "availability": availability_summary(rooms, free, start if valid_dates else None, end if valid_dates else None),',
        '''        "availability": availability_summary(rooms, free, start if valid_dates else None, end if valid_dates else None),
        "booking_calendar": booking_month(rooms, start if valid_dates else None,
            end if valid_dates else None, today=today,
            month_value=request.POST.get("cal_month") if request.method == "POST" else request.GET.get("cal_month")),''', PROPERTY)
    return src


def atomic_write(path, data):
    temp = None
    try:
        with tempfile.NamedTemporaryFile('wb', prefix='.sd122_', dir=path.parent, delete=False) as f:
            temp = Path(f.name)
            f.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from Django project root.')
    require((ROOT / 'bookings/staff_booking_ui_v121.py').is_file(), 'Install v121 first.')
    require((ROOT / 'floorplans/templatetags/summitdesk_nav.py').is_file(), 'Shared navigation is missing.')
    changes = {}
    for rel, patch in ((MANUAL, patch_manual), (PROPERTY, patch_property)):
        path = ROOT / rel
        require(path.is_file() and not path.is_symlink(), f'Missing or unsafe: {rel}')
        changes[rel] = patch(path.read_text(encoding='utf-8')).encode('utf-8')
    path = ROOT / TEMPLATE
    require(path.is_file() and not path.is_symlink(), f'Missing or unsafe: {TEMPLATE}')
    existing = path.read_text(encoding='utf-8')
    require('id="sd-booking-form"' in existing and 'id="sd-rooms-heading"' in existing,
            'Expected v121 booking template not found.')
    require('sd-cal-grid' not in existing, 'Calendar already present. Refusing to overwrite.')
    for rel, filename in ((TEMPLATE, 'staff_booking_v121.html'),
                          (HELPER, 'booking_calendar_v122.py'),
                          (TEST, 'test_booking_calendar_v122.py')):
        if rel != TEMPLATE:
            require(not (ROOT / rel).exists(), f'{rel} already exists. Refusing to overwrite.')
        source = PKG / filename
        require(source.is_file() and not source.is_symlink(), f'Missing package file: {filename}')
        changes[rel] = source.read_bytes()
    for rel, data in changes.items():
        if rel.endswith('.py'):
            ast.parse(data.decode('utf-8'), filename=rel)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('booking_calendar_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel in changes:
        path = ROOT / rel
        require(not path.is_symlink(), f'Symlink not allowed: {rel}')
        existed = path.is_file()
        manifest.append({'path': rel, 'existed': existed})
        if existed:
            target = backup / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for rel, data in changes.items():
            path = ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, data)
    except Exception:
        for entry in manifest:
            path = ROOT / entry['path']
            if entry['existed']:
                shutil.copy2(backup / entry['path'], path)
            else:
                path.unlink(missing_ok=True)
        raise
    print('Installed small monthly availability calendar on both staff booking pages.')
    print('Backup:', backup)
    print('No migrations. Run Django check and bookings.test_booking_calendar_v122.')


if __name__ == '__main__':
    main()
