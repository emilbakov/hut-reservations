#!/usr/bin/env python3
"""SummitDesk v139: safe today-focus patch for installed v138 Property Calendar."""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
REL = Path('floorplans/templates/floorplans/property_calendar_v138.html')
BASELINE_SHA = '5dd0a0b89b3eeba1cb941962b7a9dceef38634fe99f8e47e0e6738c36981f090'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write_atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sd139_', delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true', help='Read-only verification')
    args = p.parse_args()
    target = ROOT / REL
    if not (ROOT / 'manage.py').is_file() or not target.is_file():
        p.error('Run from project root after installing v138.')
    if target.is_symlink() or any(x.is_symlink() for x in target.parents if x != ROOT and ROOT in x.parents):
        p.error('Refusing to edit a symlinked path.')
    current = target.read_bytes()
    if sha(current) != BASELINE_SHA:
        p.error('v138 template does not match expected SHA256; no changes made. Found: ' + sha(current))
    updated = (PACKAGE / 'property_calendar_v139.html').read_bytes()
    if b'data-calendar-today' not in updated or b'bookings:calendar_create' not in updated:
        p.error('Invalid patch contents.')
    print('v139 preflight OK. Only Property Calendar template will change.')
    if args.check:
        print('No files changed.')
        return
    backup = ROOT / 'summitdesk_backups' / ('property_today_v139_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    original_backup = backup / REL
    original_backup.parent.mkdir(parents=True)
    original_backup.write_bytes(current)
    if original_backup.read_bytes() != current:
        p.error('Backup verification failed; no live changes.')
    (backup / 'manifest.json').write_text(json.dumps({'version':'v139','path':str(REL),'original_sha':sha(current),'installed_sha':sha(updated)},indent=2))
    try:
        write_atomic(target, updated)
        if sha(target.read_bytes()) != sha(updated):
            raise RuntimeError('Post-install hash mismatch')
    except Exception:
        write_atomic(target, current)
        raise
    print('v139 installed. Backup:', backup.relative_to(ROOT))
    print('Rollback: python3 v139_today_package/rollback_v139_today.py ' + str(backup.relative_to(ROOT)))
    print('No migrations or reservation logic changes.')

if __name__ == '__main__':
    main()
