#!/usr/bin/env python3
"""SummitDesk v141 style-only rollback with hash verification."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()
BACKUPS = ROOT / 'summitdesk_backups'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('backup', nargs='?')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        for manifest in sorted(BACKUPS.glob('reservation_style_v141_*/manifest.json')):
            print(manifest.parent.relative_to(ROOT))
        return
    if not args.backup:
        parser.error('Pass backup path or --list.')
    backup = (ROOT / args.backup).resolve()
    if BACKUPS.resolve() not in backup.parents or not backup.name.startswith('reservation_style_v141_'):
        parser.error('Invalid backup path.')
    manifest = json.loads((backup / 'manifest.json').read_text())
    if manifest.get('version') != 'v141':
        parser.error('Invalid manifest.')
    rel = Path(manifest['file'])
    target = ROOT / rel
    if not target.is_file() or target.is_symlink() or sha(target.read_bytes()) != manifest['installed']:
        parser.error('Current template differs from installed v141; refusing overwrite.')
    original = (backup / rel).read_bytes()
    if sha(original) != manifest['original']:
        parser.error('Backup checksum mismatch.')
    print('v141 rollback preflight OK.')
    if args.check:
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd141_rollback_', delete=False) as f:
        temp = Path(f.name)
        f.write(original)
    try:
        os.chmod(temp, target.stat().st_mode & 0o777)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    print('v141 style rolled back; v140 booking functionality remains installed.')

if __name__ == '__main__':
    main()
