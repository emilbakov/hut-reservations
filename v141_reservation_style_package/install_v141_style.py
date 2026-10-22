#!/usr/bin/env python3
"""SummitDesk v141: install CSS/heading-only Property Calendar restyle, safely."""
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
BASELINE_SHA = 'f8ab9d7733c18c088b74b59e42025bde069499a446b0fff914edb1cc978f96f8'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sd141_', delete=False) as f:
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
    if sha(original) != BASELINE_SHA:
        parser.error('Expected the unmodified v140 Property Calendar template; no files changed. Actual SHA256: ' + sha(original))
    update = (PACKAGE / 'property_calendar_v141.html').read_bytes()
    if not all(marker in update for marker in (b'csrf_token', b'sd140-pick', b'quickstay_create', b'SummitDesk / Property management')):
        parser.error('Invalid update template.')
    # All scripts, template logic and booking form stay byte-identical.
    import re
    strip_css = lambda b: re.sub(rb'<style>.*?</style>', b'<style>CSS</style>', b, count=1, flags=re.S)
    strip_visual_heading = lambda b: b.replace(b'<p class="sd141-eyebrow">SummitDesk / Property management</p>', b'').replace(b' sd141-primary', b'')
    if strip_css(original) != strip_visual_heading(strip_css(update)):
        parser.error('Nonvisual template content changed; refusing install.')
    print('v141 preflight OK: exact v140 baseline; template-only restyle; booking logic unchanged.')
    if args.check:
        print('Read-only check: no changes made.')
        return
    backup = ROOT / 'summitdesk_backups' / ('reservation_style_v141_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    backup_target = backup / TARGET
    backup_target.parent.mkdir(parents=True)
    backup_target.write_bytes(original)
    if sha(backup_target.read_bytes()) != sha(original):
        parser.error('Backup failed; no files changed.')
    manifest = {'version': 'v141', 'file': str(TARGET), 'original': sha(original), 'installed': sha(update)}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    try:
        atomic_write(target, update)
        if sha(target.read_bytes()) != sha(update):
            raise RuntimeError('Post-install hash mismatch.')
    except Exception:
        atomic_write(target, original)
        raise
    print('v141 installed. Backup:', backup.relative_to(ROOT))
    print('Rollback: python3 v141_reservation_style_package/rollback_v141_style.py ' + str(backup.relative_to(ROOT)))
    print('No migrations, backend changes, or static collection required.')

if __name__ == '__main__':
    main()
