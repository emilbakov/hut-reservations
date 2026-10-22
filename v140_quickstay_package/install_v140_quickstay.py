#!/usr/bin/env python3
"""SummitDesk v140: preflight, backup, atomic install of quick-stay planner."""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
TEMPLATE = Path('floorplans/templates/floorplans/property_calendar_v138.html')
HELPER = Path('floorplans/property_calendar_v138.py')
URLS = Path('floorplans/urls.py')
VIEW = Path('floorplans/property_quickstay_v140.py')
TEST = Path('floorplans/test_quickstay_v140.py')
EXPECTED = {
    TEMPLATE: {'5dd0a0b89b3eeba1cb941962b7a9dceef38634fe99f8e47e0e6738c36981f090',
               '9e4ac571f101765970c40a003b3192024a9e8992635ab0f8a9e53c4abde2a50f'},
    HELPER: {'ded23956be73a88d7e3286523ee5586bef0958328be55e80576bcd482e1f92bb'},
}
MARKER = 'app_name = "floorplans"'
INSERT = 'from . import property_quickstay_v140 as quickstay140\n'
ROUTE = '    path("<int:hut_id>/quickstay/", quickstay140.quickstay_create, name="quickstay_create"),\n'

def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sd140_', delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true', help='Verify without changes')
    args = p.parse_args()
    if not (ROOT / 'manage.py').is_file():
        p.error('Run from the Django project root.')
    originals = {}
    for rel in (TEMPLATE, HELPER, URLS):
        path = ROOT / rel
        if not path.is_file() or path.is_symlink():
            p.error('Missing or symlinked target: ' + str(rel))
        originals[rel] = path.read_bytes()
    for rel, hashes in EXPECTED.items():
        if sha(originals[rel]) not in hashes:
            p.error(f'{rel} differs from known v138/v139 baseline; no files changed. Found SHA256: {sha(originals[rel])}')
    urls = originals[URLS].decode('utf-8')
    if urls.count(MARKER) != 1 or 'quickstay_create' in urls or 'property_quickstay_v140' in urls:
        p.error('Unexpected floorplans URL configuration; no files changed.')
    for rel in (VIEW, TEST):
        if (ROOT / rel).exists():
            p.error('Target already exists: ' + str(rel))
    new_urls = urls.replace(MARKER, INSERT + '\n' + MARKER, 1).replace('urlpatterns = [', 'urlpatterns = [\n' + ROUTE, 1).encode()
    new = {TEMPLATE: (PACKAGE / 'property_calendar_v140.html').read_bytes(),
           HELPER: (PACKAGE / 'property_calendar_v140.py').read_bytes(),
           URLS: new_urls,
           VIEW: (PACKAGE / 'property_quickstay_v140.py').read_bytes(),
           TEST: (PACKAGE / 'test_quickstay_v140.py').read_bytes()}
    if b'csrf_token' not in new[TEMPLATE] or b'create_reservation(' not in new[VIEW] or b'permitted_hut(' not in new[VIEW]:
        p.error('Package verification failed.')
    print('v140 preflight OK: v138/v139 Property Calendar supported; 3 files updated, 2 new files.')
    if args.check:
        print('Read-only check: no changes made.')
        return
    backup = ROOT / 'summitdesk_backups' / ('quickstay_v140_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(parents=True)
    for rel, content in originals.items():
        dest = backup / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        if dest.read_bytes() != content:
            p.error('Backup verification failed before installation.')
    manifest = {'version':'v140', 'original': {str(k):sha(v) for k,v in originals.items()},
                'installed': {str(k):sha(v) for k,v in new.items()},
                'created':[str(VIEW), str(TEST)]}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    done = []
    try:
        for rel, content in new.items():
            path = ROOT / rel
            if rel in (VIEW, TEST):
                with path.open('xb') as f:
                    f.write(content)
            else:
                write_atomic(path, content)
            done.append(rel)
            if sha(path.read_bytes()) != sha(content):
                raise RuntimeError('Post-install SHA mismatch: ' + str(rel))
    except Exception:
        for rel in reversed(done):
            if rel in originals:
                write_atomic(ROOT / rel, originals[rel])
            else:
                (ROOT / rel).unlink(missing_ok=True)
        raise
    print('v140 installed. Backup:', backup.relative_to(ROOT))
    print('Rollback: python3 v140_quickstay_package/rollback_v140_quickstay.py ' + str(backup.relative_to(ROOT)))
    print('No database migrations. Run tests before production restart.')

if __name__ == '__main__':
    main()
