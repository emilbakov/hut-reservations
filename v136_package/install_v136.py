#!/usr/bin/env python3
"""Install SummitDesk v136 availability calendar UI; --check is read-only.

From project root: python3 v136_package/install_v136.py --check
Then:             python3 v136_package/install_v136.py
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
TARGET = 'bookings/templates/bookings/availability_calendar.html'
TEST = 'bookings/test_availability_ui_v136.py'
EXPECTED_SHA = '9a40d17e88757d9832c93abcb30809088edb739434bb9bf623b24e7fcc40ca02'


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
    require(target.is_file(), f'Missing calendar: {TARGET}')
    require(not test.exists(), f'{TEST} already exists; refusing overwrite.')
    original = target.read_bytes()
    require(sha(original) == EXPECTED_SHA,
            'Calendar differs from uploaded production snapshot; refusing overwrite. '
            f'Current SHA256: {sha(original)}. Send the current calendar template for a compatible update.')
    updated = (PKG / 'availability_calendar_v136.html').read_bytes()
    test_data = (PKG / 'test_availability_ui_v136.py').read_bytes()
    require(b'SummitDesk v136' in updated and b"bookings:calendar_edit" in updated
            and b"bookings:calendar_create" in updated, 'v136 template is incomplete.')
    compile(test_data, TEST, 'exec')
    return original, {TARGET: updated, TEST: test_data}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Preflight only; do not modify files.')
    args = parser.parse_args()
    original, updates = preflight()
    print('SummitDesk v136 preflight OK')
    print('Availability calendar baseline SHA256:', sha(original))
    if args.check:
        print('Check-only mode: no files changed.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'availability_v136_{stamp}'
    require(not backup.exists(), 'Backup directory already exists.')
    backup.mkdir(parents=True)
    saved = backup / TARGET
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(safe_path(TARGET), saved)
    require(saved.read_bytes() == original, 'Backup verification failed; no changes made.')
    manifest = {
        'version': 'v136',
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
    print('Installed SummitDesk v136 monthly availability UI.')
    print('Backup:', backup)
    print('Rollback preview: python3 v136_package/rollback_v136.py --check ' + str(backup.relative_to(ROOT)))
    print('Rollback command: python3 v136_package/rollback_v136.py ' + str(backup.relative_to(ROOT)))
    print('No migrations, database changes, view logic, permissions or staff navigation changed.')
    print('Next: python manage.py test bookings.test_availability_ui_v136 bookings.test_availability_calendar --settings=config.settings')


if __name__ == '__main__':
    main()
