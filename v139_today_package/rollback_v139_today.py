#!/usr/bin/env python3
"""Restore the original v138 template from a v139 backup, verifying hashes."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
ROOT=Path.cwd().resolve()
def sha(data): return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('backup',help='Path printed by v139 installer')
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    folder=(ROOT/args.backup).resolve()
    allowed=(ROOT/'summitdesk_backups').resolve()
    if allowed not in folder.parents or not folder.name.startswith('property_today_v139_'):
        p.error('Invalid backup path')
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest.get('version')!='v139' or manifest.get('path')!='floorplans/templates/floorplans/property_calendar_v138.html':
        p.error('Invalid backup manifest')
    target=ROOT/manifest['path']
    if target.is_symlink(): p.error('Symlink target refused')
    original=(folder/manifest['path']).read_bytes()
    if sha(original)!=manifest['original_sha']: p.error('Backup checksum mismatch')
    if sha(target.read_bytes())!=manifest['installed_sha']: p.error('Installed file modified; refusing overwrite')
    print('Rollback preflight OK')
    if args.check: return
    with tempfile.NamedTemporaryFile(dir=target.parent,delete=False,prefix='.sd139_rollback_') as f:
        temp=Path(f.name);f.write(original)
    try:
        os.chmod(temp,target.stat().st_mode & 0o777)
        os.replace(temp,target)
    finally:
        temp.unlink(missing_ok=True)
    print('Restored v138 Property Calendar template')
if __name__=='__main__': main()
