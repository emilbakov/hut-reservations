#!/usr/bin/env python3
"""Restore v140 backed-up originals; refuse to overwrite unrelated edits."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()
BACKUPS = ROOT / 'summitdesk_backups'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('backup', nargs='?')
    p.add_argument('--list', action='store_true')
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    if args.list:
        for path in sorted(BACKUPS.glob('quickstay_v140_*/manifest.json')):
            print(path.parent.relative_to(ROOT))
        return
    if not args.backup:
        p.error('Pass the backup directory shown by the installer, or --list.')
    backup = (ROOT / args.backup).resolve()
    if BACKUPS.resolve() not in backup.parents or not backup.name.startswith('quickstay_v140_'):
        p.error('Backup path must be a v140 backup under summitdesk_backups.')
    manifest = json.loads((backup / 'manifest.json').read_text())
    if manifest.get('version') != 'v140':
        p.error('Invalid backup manifest.')
    for rel, expected in manifest['installed'].items():
        path = ROOT / rel
        if not path.is_file() or path.is_symlink() or sha(path.read_bytes()) != expected:
            p.error('File modified since install; refusing rollback: ' + rel)
    for rel, expected in manifest['original'].items():
        if sha((backup / rel).read_bytes()) != expected:
            p.error('Backup hash mismatch: ' + rel)
    print('Rollback preflight OK.')
    if args.check:
        return
    for rel in manifest['original']:
        target = ROOT / rel
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.sd140_restore_', delete=False) as f:
            temp = Path(f.name)
            f.write((backup / rel).read_bytes())
        os.chmod(temp, target.stat().st_mode & 0o777)
        os.replace(temp, target)
    for rel in manifest['created']:
        (ROOT / rel).unlink()
    print('v140 rollback complete. Restart Gunicorn after verifying checks.')

if __name__ == '__main__':
    main()
