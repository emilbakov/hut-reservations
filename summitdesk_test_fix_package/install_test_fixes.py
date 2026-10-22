#!/usr/bin/env python3
"""Safely update four legacy Django test assertions for the current UI and permissions.

Only modifies bookings/tests.py and bookings/test_manual_booking.py.
No models, views, migrations, settings, or database operations.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path.cwd().resolve()
BACKUP_ROOT = ROOT / 'summitdesk_backups'

# Each assertion is scoped to its named test method to prevent unintended edits.
CHANGES = {
    'bookings/tests.py': [
        ('test_search_shows_rooms',
         '        self.assertContains(response, "4 of 4")',
         '        self.assertContains(response, "4 available for your stay")'),
        ('test_staff_dashboard_shows_occupancy',
         '        self.assertContains(response, "Occupancy calendar")',
         '        self.assertContains(response, "Beds occupied today")'),
        ('test_dashboard_displays_month_for_staff',
         '        self.assertContains(response, "Occupancy calendar")',
         '        self.assertContains(response, "October 2026 at a glance")'),
    ],
    'bookings/test_manual_booking.py': [
        ('test_nonstaff_denied',
         '        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)',
         '        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)\n'
         '        self.assertEqual(Reservation.objects.count(), 0)'),
    ],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def scoped_replace(source, method, old, new):
    # Match an indented TestCase method; stop at the next class or method.
    start = re.search(r'(?m)^    def ' + re.escape(method) + r'\(self\):\s*$', source)
    require(start is not None, f'Missing test method: {method}')
    end = re.search(r'(?m)^(?:    def |class |@)', source[start.end():])
    stop = start.end() + end.start() if end else len(source)
    block = source[start.end():stop]
    if old in block:
        require(block.count(old) == 1, f'Ambiguous assertion in {method}')
        return source[:start.end()] + block.replace(old, new, 1) + source[stop:], True
    if new in block:
        require(block.count(new) == 1, f'Ambiguous already-fixed assertion in {method}')
        return source, False
    raise RuntimeError(f'Unexpected test contents in {method}; refusing to overwrite custom changes')


def safe_path(rel):
    p = ROOT / rel
    require(ROOT in p.parents and not p.is_symlink(), f'Unsafe target: {rel}')
    require(not (ROOT / 'bookings').is_symlink(), 'Symlinked bookings directory not supported')
    require(p.is_file(), f'Missing test file: {rel}')
    return p


def atomic_write(path, data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.summitdesk_testfix_', dir=path.parent, delete=False) as fh:
            tmp = Path(fh.name)
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the Django project root')
    require((ROOT / 'bookings/test_guest_approval_v126.py').is_file(),
            'Guest approval test file is missing; this patch targets the current installation')
    require((ROOT / 'bookings/migrations/0013_reservation_guest_request.py').is_file(),
            'Guest approval migration file is missing')
    pending = {}
    counts = {}
    originals = {}
    # Validate all changes before modifying any file.
    for rel, changes in CHANGES.items():
        path = safe_path(rel)
        original = path.read_bytes()
        require(b'\r\n' not in original, f'Unexpected CRLF file: {rel}')
        text = original.decode('utf-8')
        changed = 0
        for method, old, new in changes:
            text, did_change = scoped_replace(text, method, old, new)
            changed += int(did_change)
        compiled = text.encode('utf-8')
        compile(compiled, rel, 'exec')
        pending[rel] = compiled
        originals[rel] = original
        counts[rel] = changed
    total = sum(counts.values())
    if total == 0:
        print('Already fixed: all four assertions match the current behavior. No files changed.')
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        backup = BACKUP_ROOT / f'test_fixes_{stamp}'
        require(not backup.exists(), f'Backup already exists: {backup}')
        backup.mkdir(parents=True)
        manifest = []
        for rel, data in pending.items():
            if counts[rel] == 0:
                continue
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_path(rel), dst)
            manifest.append({'path': rel, 'before_sha256': sha(originals[rel]),
                             'after_sha256': sha(data)})
        (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        for entry in manifest:
            rel = entry['path']
            atomic_write(safe_path(rel), pending[rel])
            print(f'Updated {rel}: {counts[rel]} assertion(s)')
        print(f'Original files backed up to: {backup}')
    # The old import error may have been from a folder already moved/removed.
    old_backup = ROOT / 'floorplans/backup'
    if old_backup.exists() or old_backup.is_symlink():
        print('NOTE: floorplans/backup still exists. It may cause unittest discovery import errors.')
        print('      Inspect this folder; the installer deliberately did not touch it.')
    else:
        print('floorplans/backup is absent; no backup-folder action required.')
    print('No application code, database tables, or migrations were changed.')
    print('Next: python manage.py test bookings.test_manual_booking bookings.tests')
    print('Then: python manage.py test')


if __name__ == '__main__':
    main()
