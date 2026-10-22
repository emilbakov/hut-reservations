#!/usr/bin/env python3
"""Install SummitDesk v137 calendar booking form UI; --check is read-only.

From project root: python3 v137_package/install_v137.py --check
Then:             python3 v137_package/install_v137.py
"""
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
TARGET = 'bookings/templates/bookings/calendar_booking_form.html'
TEST = 'bookings/test_calendar_form_ui_v137.py'
EXPECTED_SHA = 'a1308b00d8251e650b21b5320f4a1a65da8f08b74feda05b899a1283cd0d48db'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def safe_path(relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts, f'Unsafe path: {relative}')
    target = ROOT / p
    require(ROOT in target.parents and not target.is_symlink(), f'Unsafe target: {relative}')
    parent = target.parent
    while parent != ROOT:
        require(not parent.is_symlink(), f'Symlink directory refused: {parent}')
        parent = parent.parent
    return target


def atomic_write(target, data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd136_', delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        os.chmod(tmp, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(tmp, target)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def preflight():
    require((ROOT / 'manage.py').is_file(), 'Run from the Django project root beside manage.py.')
    target = safe_path(TARGET)
    test = safe_path(TEST)
    require(target.is_file(), f'Missing booking form: {TARGET}')
    require(not test.exists(), f'{TEST} already exists; refusing overwrite.')
    original = target.read_bytes()
    require(sha(original) == EXPECTED_SHA,
            'Booking form differs from uploaded production snapshot; refusing overwrite. '
            f'Current SHA256: {sha(original)}. Send the current calendar template for a compatible update.')
    updated = (PKG / 'calendar_booking_form_v137.html').read_bytes()
    test_data = (PKG / 'test_calendar_form_ui_v137.py').read_bytes()
    require(b'SummitDesk v137' in updated and b"Booking overview" in updated
            and b"bookings:availability_calendar" in updated, 'v137 template is incomplete.')
    compile(test_data, TEST, 'exec')
    return original, {TARGET: updated, TEST: test_data}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Preflight only; do not modify files.')
    args = parser.parse_args()
    original, updates = preflight()
    print('SummitDesk v137 preflight OK')
    print('Calendar booking form baseline SHA256:', sha(original))
    if args.check:
        print('Check-only mode: no files changed.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'calendar_form_v137_{stamp}'
    require(not backup.exists(), 'Backup directory already exists.')
    backup.mkdir(parents=True)
    saved = backup / TARGET
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(safe_path(TARGET), saved)
    require(saved.read_bytes() == original, 'Backup verification failed; no changes made.')
    manifest = {
        'version': 'v137',
        'originals': {TARGET: sha(original)},
        'installed': {rel: sha(data) for rel, data in updates.items()},
        'created': [TEST],
    }
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    written = []
    try:
        for rel, data in updates.items():
            atomic_write(safe_path(rel), data)
            written.append(rel)
            require(safe_path(rel).read_bytes() == data, f'Install verification failed: {rel}')
    except Exception:
        for rel in reversed(written):
            if rel == TARGET:
                atomic_write(safe_path(TARGET), original)
            else:
                safe_path(rel).unlink(missing_ok=True)
        raise
    print('Installed SummitDesk v137 calendar booking form UI.')
    print('Backup:', backup)
    print('Rollback preview: python3 v137_package/rollback_v137.py --check ' + str(backup.relative_to(ROOT)))
    print('Rollback command: python3 v137_package/rollback_v137.py ' + str(backup.relative_to(ROOT)))
    print('No migrations, database changes, view logic, permissions or staff navigation changed.')
    print('Next: python manage.py test bookings.test_calendar_form_ui_v137 bookings.test_calendar_actions --settings=config.settings')


if __name__ == '__main__':
    main()
