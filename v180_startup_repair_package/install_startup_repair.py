#!/usr/bin/env python3
"""Correct v180 socket startup order without stopping services or changing the database."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

PKG = Path(__file__).resolve().parent
PREFIX = 'startup_repair_v180_'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise RuntimeError('Unsafe repair path.')
    path = root / rel
    current = path
    while current != root:
        if current.is_symlink():
            raise RuntimeError('Symlink refused: ' + relative)
        current = current.parent
    return path


def atomic_write(path, data, mode):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.startup-repair-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def preflight(root):
    if not (root / 'manage.py').is_file():
        raise RuntimeError('Run beside manage.py in /home/deploy/hut-reservations.')
    manifest = json.loads((PKG / 'startup_manifest.json').read_text())
    for item in manifest['guards']:
        path = safe_path(root, item['path'])
        if not path.is_file() or digest(path.read_bytes()) != item['sha256']:
            raise RuntimeError('Unrecognized v180 deployment helper: ' + item['path'])
    rows = []
    for item in manifest['files']:
        target = safe_path(root, item['path'])
        if not target.is_file():
            raise RuntimeError('Missing deployment file: ' + item['path'])
        current = target.read_bytes()
        current_sha = digest(current)
        if current_sha not in item['accepted_sha256']:
            raise RuntimeError('Unrecognized/customized deployment file: ' + item['path'])
        data = current.replace(manifest['old_start_block'].encode(), manifest['new_start_block'].encode())
        expected = item['transform_sha256'][current_sha]
        if digest(data) != expected:
            raise RuntimeError('Startup transformation did not match the verified result: ' + item['path'])
        item = {**item, 'sha256': expected}
        if target.suffix == '.sh':
            result = subprocess.run(['bash', '-n'], input=data, capture_output=True)
            if result.returncode:
                raise RuntimeError('Invalid shell payload: ' + item['path'])
        if target.suffix == '.py':
            compile(data, item['path'], 'exec')
        rows.append((item, target, data))
    return manifest, rows


def restore(root, supplied):
    parent = root / 'summitdesk_backups'
    backup = (root / supplied).resolve()
    if parent.is_symlink() or backup.parent != parent or not backup.name.startswith(PREFIX):
        raise RuntimeError('Use the repair backup path printed by this installer.')
    entries = json.loads(safe_path(backup, 'repair_backup.json').read_text())
    allowed = {item['path'] for item in json.loads((PKG / 'startup_manifest.json').read_text())['files']}
    if {entry['path'] for entry in entries} != allowed:
        raise RuntimeError('Unexpected paths in repair backup.')
    changes = []
    for entry in entries:
        target = safe_path(root, entry['path'])
        original = safe_path(backup, entry['path'])
        if not target.is_file() or digest(target.read_bytes()) != entry['after_sha256']:
            raise RuntimeError('Deployment file changed after repair: ' + entry['path'])
        data = original.read_bytes()
        if digest(data) != entry['before_sha256']:
            raise RuntimeError('Repair backup changed: ' + entry['path'])
        changes.append((target, data, entry['mode'], target.read_bytes()))
    try:
        for target, data, mode, current in changes:
            atomic_write(target, data, mode)
    except BaseException:
        for target, data, mode, current in changes:
            atomic_write(target, current, mode)
        raise
    print('Previous staged v180 deployment files restored. Live application source and database were not changed.')


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true')
    group.add_argument('--verify-staged', action='store_true')
    group.add_argument('--verify-installed', action='store_true')
    group.add_argument('--restore', metavar='BACKUP')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.restore:
        if not (root / 'manage.py').is_file():
            raise RuntimeError('Run beside manage.py.')
        with (root / '.summitdesk_v180_deploy.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            restore(root, args.restore)
        return
    manifest, rows = preflight(root)
    staged = all(digest(target.read_bytes()) == item['sha256'] for item, target, data in rows)
    if args.verify_installed or args.verify_staged:
        if not staged:
            raise RuntimeError('Run install_startup_repair.py before deployment.')
        print('Startup order verified: socket before Gunicorn. No services restarted.')
        return
    if args.check:
        print('Repair preflight passed; no deployment files changed.')
        return
    with (root / '.summitdesk_v180_deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest, rows = preflight(root)
        if all(digest(target.read_bytes()) == item['sha256'] for item, target, data in rows):
            print('Startup order already corrected. No services restarted.')
            return
        parent = root / 'summitdesk_backups'
        if parent.is_symlink():
            raise RuntimeError('Symlink backup directory refused.')
        parent.mkdir(exist_ok=True)
        backup = parent / (PREFIX + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(mode=0o700)
        saved = []
        for item, target, data in rows:
            destination = safe_path(backup, item['path'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
            saved.append({'path': item['path'], 'before_sha256': digest(target.read_bytes()),
                          'after_sha256': item['sha256'], 'mode': target.stat().st_mode & 0o777})
        (backup / 'repair_backup.json').write_text(json.dumps(saved, indent=2)+'\n')
        try:
            for (item, target, data), entry in zip(rows, saved):
                atomic_write(target, data, entry['mode'])
        except BaseException:
            for entry in saved:
                atomic_write(safe_path(root, entry['path']), (backup / entry['path']).read_bytes(), entry['mode'])
            raise
        print('Deployment and rollback startup order corrected. No services restarted; database unchanged.')
        print('Staging backup:', backup.relative_to(root))
        print('Verify: python3 v180_startup_repair_package/install_startup_repair.py --verify-staged')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        raise SystemExit(str(exc))
