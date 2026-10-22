#!/usr/bin/env python3
"""Validate the uploaded baseline, back up source, then install v145 atomically."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PKG = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise RuntimeError('Unsafe path in release manifest')
    path = root / rel
    current = path
    while current != root:
        if current.is_symlink():
            raise RuntimeError(f'Symlink refused: {relative}')
        current = current.parent
    return path


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sd145_', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def preflight(root):
    if not (root / 'manage.py').is_file():
        raise RuntimeError('Run from the project directory beside manage.py.')
    if not (root / 'config/settings_v145_test.py').is_file():
        raise RuntimeError('Install the v145 reliability package first.')
    manifest = json.loads((PKG / 'manifest.json').read_text())
    payload = []
    all_installed = True
    for item in manifest['files']:
        target = safe_path(root, item['path'])
        source = safe_path(PKG / 'files', item['path'])
        data = source.read_bytes()
        if digest(data) != item['after_sha256']:
            raise RuntimeError(f'Damaged package payload: {item["path"]}')
        current = digest(target.read_bytes()) if target.is_file() else None
        if current not in (item['before_sha256'], item['after_sha256']):
            raise RuntimeError(f'Unexpected/customized file: {item["path"]}. No source files changed.')
        if current != item['after_sha256']:
            all_installed = False
        if item['path'].endswith('.py'):
            compile(data, item['path'], 'exec')
        payload.append((item, target, data))
    return payload, all_installed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Validate without changing files')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    payload, all_installed = preflight(root)
    if args.check:
        print('v145.1 preflight passed; no files changed.')
        return
    import fcntl
    with (root / '.summitdesk_v145_1_csv_install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        payload, all_installed = preflight(root)
        if all_installed:
            print('v145.1 test correction is already installed. Run deploy_v145.sh to verify migrations/services.')
            return
        parent = root / 'summitdesk_backups'
        if parent.is_symlink():
            raise RuntimeError('Symlink backup directory refused')
        parent.mkdir(exist_ok=True)
        backup = parent / ('csv_test_v145_1_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(mode=0o700)
        saved = []
        for item, target, data in payload:
            existed = target.is_file()
            entry = {**item, 'existed':existed, 'mode':target.stat().st_mode & 0o777 if existed else 0o644,
                     'backup_sha256':digest(target.read_bytes()) if existed else None}
            saved.append(entry)
            if existed:
                destination = backup / item['path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, destination)
        (backup / 'manifest.json').write_text(json.dumps(saved, indent=2))
        try:
            for (item, target, data), entry in zip(payload, saved):
                atomic_write(target, data, entry['mode'])
        except BaseException:
            for entry in saved:
                target = safe_path(root, entry['path'])
                if entry['existed']:
                    atomic_write(target, (backup / entry['path']).read_bytes(), entry['mode'])
                elif target.exists():
                    target.unlink()
            raise
        print('CSV test correction installed. Resume the v145 deployment with the command below.')
        print('Source backup:', backup)
        print('Next: bash v145_reliability_package/deploy_v145.sh')
        print('Rollback: python3 v145_1_csv_test_fix_package/rollback_v145_1.py ' + str(backup.relative_to(root)))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
