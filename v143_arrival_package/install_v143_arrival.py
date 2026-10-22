#!/usr/bin/env python3
"""Install SummitDesk v143 Property Calendar arrival-date highlight, with verified backup."""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
TARGET = Path('floorplans/templates/floorplans/property_calendar_v138.html')
BASELINES = {
    '20d430e3d53bdcfffb8ca6f76763d027751cd8c789a061aa6755fec7bdf51e99': 'v142',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sd142_', delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Read-only preflight')
    args = parser.parse_args()
    if not (ROOT / 'manage.py').is_file():
        parser.error('Run from Django project root.')
    target = ROOT / TARGET
    if not target.is_file() or target.is_symlink():
        parser.error('Missing or symlinked Property Calendar template.')
    original = target.read_bytes()
    baseline = BASELINES.get(sha(original))
    if not baseline:
        parser.error('Expected unmodified v142 template. No files changed. Actual SHA256: ' + sha(original))
    update = (PACKAGE / 'property_calendar_v143.html').read_bytes()
    required = (b'csrf_token', b'quickstay_create', b'data-room=', b'sd142-grid', b'sd142-booking', b'Confirm reservation')
    if not all(marker in update for marker in required):
        parser.error('Invalid v143 template; no files changed.')
    print('v143 preflight OK: verified ' + baseline + ' template; existing booking backend unchanged.')
    if args.check:
        print('Read-only check: no changes made.')
        return
    backup = ROOT / 'summitdesk_backups' / ('property_arrival_v143_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    saved = backup / TARGET
    saved.parent.mkdir(parents=True)
    saved.write_bytes(original)
    if sha(saved.read_bytes()) != sha(original):
        parser.error('Backup verification failed; no files changed.')
    manifest = {'version': 'v143', 'baseline': baseline, 'file': str(TARGET), 'original': sha(original), 'installed': sha(update)}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    try:
        atomic_write(target, update)
        if sha(target.read_bytes()) != sha(update):
            raise RuntimeError('Post-install hash mismatch')
    except Exception:
        atomic_write(target, original)
        raise
    print('v143 installed. Backup:', backup.relative_to(ROOT))
    print('Rollback: python3 v143_arrival_package/rollback_v143_arrival.py ' + str(backup.relative_to(ROOT)))
    print('No migrations or backend changes required.')

if __name__ == '__main__':
    main()
