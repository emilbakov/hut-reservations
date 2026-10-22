#!/usr/bin/env python3
"""Install revised SummitDesk v138 Property Calendar. Run --check first."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
CHANGES = {
    'floorplans/staff_calendar.py': 'staff_calendar_v138.py',
    'floorplans/templates/floorplans/staff_calendar.html': 'staff_calendar_timeline_v138.html',
}
ADDED = {
    'floorplans/property_calendar_v138.py': 'property_calendar_v138.py',
    'floorplans/templates/floorplans/property_calendar_v138.html': 'property_calendar_v138.html',
    'floorplans/test_property_calendar_v138.py': 'test_property_calendar_v138.py',
}
EXPECTED = {
    'floorplans/staff_calendar.py': 'ee3247d9b8072f07131e305ed9b0a7fcfdb9e3012f1cc1f90512e3d3478de9fd',
    'floorplans/templates/floorplans/staff_calendar.html': '327822394874ddd6f945b564f4c290045f6e87ce473c70455c851950a74ba690',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def target_path(relative):
    rel = Path(relative)
    check(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe path: ' + relative)
    p = ROOT / rel
    check(ROOT in p.parents and not p.is_symlink(), 'Unsafe target: ' + relative)
    parent = p.parent
    while parent != ROOT:
        check(not parent.is_symlink(), 'Symlink parent refused: ' + str(parent))
        parent = parent.parent
    return p


def atomic_write(target, data):
    tmp = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd138_property_', delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        os.chmod(tmp, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(tmp, target)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def preflight():
    check((ROOT / 'manage.py').is_file(), 'Run from Django project root (next to manage.py).')
    check((ROOT / 'floorplans/urls.py').is_file(), 'Floorplans URLs not found.')
    for relative, expected in EXPECTED.items():
        path = target_path(relative)
        check(path.is_file(), 'Missing expected file: ' + relative)
        current = sha(path.read_bytes())
        check(current == expected, f'{relative} differs from uploaded baseline. Expected {expected}, found {current}. Refusing to overwrite live edits.')
    for relative in ADDED:
        check(not target_path(relative).exists(), 'Already exists; refusing overwrite: ' + relative)
    # Previous all-hut v138 package is incompatible with this revised property-only package.
    old_multi = ROOT / 'bookings/availability_calendar.py'
    if old_multi.is_file():
        check(b'v138: unified all-permitted-huts' not in old_multi.read_bytes(),
              'Previous all-hut v138 detected. Roll it back first, then retry.')
    payload = {}
    for rel, source in {**CHANGES, **ADDED}.items():
        data = (PKG / source).read_bytes()
        if rel.endswith('.py'):
            compile(data, rel, 'exec')
        check(bool(data), 'Empty payload: ' + source)
        payload[rel] = data
    check(b'view=timeline' in payload['floorplans/templates/floorplans/staff_calendar.html'], 'Timeline fallback missing.')
    check(b'permitted_hut' in payload['floorplans/staff_calendar.py'], 'Property permission guard missing.')
    check(b'bookings:calendar_create' in payload['floorplans/templates/floorplans/property_calendar_v138.html'], 'Booking link missing.')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only preflight, no changes')
    args = parser.parse_args()
    payload = preflight()
    print('SummitDesk v138 Property Calendar preflight OK')
    for rel, expected in EXPECTED.items():
        print(f'Baseline SHA256 {rel}: {expected}')
    if args.check:
        print('Check-only mode: no files changed.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('property_calendar_v138_' + stamp)
    check(not backup.exists(), 'Backup directory already exists.')
    backup.mkdir(parents=True)
    originals = {}
    for rel in CHANGES:
        original = target_path(rel).read_bytes()
        saved = backup / rel
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_path(rel), saved)
        check(saved.read_bytes() == original, 'Backup verification failed: ' + rel)
        originals[rel] = original
    manifest = {
        'version': 'v138-property',
        'originals': {rel: sha(data) for rel, data in originals.items()},
        'installed': {rel: sha(data) for rel, data in payload.items()},
        'created': sorted(ADDED),
    }
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    written = []
    try:
        for rel, data in payload.items():
            atomic_write(target_path(rel), data)
            written.append(rel)
            check(target_path(rel).read_bytes() == data, 'Verification failed: ' + rel)
    except Exception:
        for rel in reversed(written):
            if rel in originals:
                atomic_write(target_path(rel), originals[rel])
            else:
                target_path(rel).unlink(missing_ok=True)
        raise
    print('Installed SummitDesk v138 Property Calendar (one hut, all rooms).')
    print('Backup:', backup)
    relative = backup.relative_to(ROOT)
    print('Rollback check: python3 v138_property_package/rollback_v138_property.py --check ' + str(relative))
    print('Rollback: python3 v138_property_package/rollback_v138_property.py ' + str(relative))
    print('No migrations or reservation write logic changed.')
    print('Next: python manage.py test floorplans.test_property_calendar_v138 --settings=config.settings')


if __name__ == '__main__':
    main()
