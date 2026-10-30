#!/usr/bin/env python3
"""Validate the uploaded v167 baseline, back up source, then install v153_1 atomically."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PKG = Path(__file__).resolve().parent
PRODUCTION_ROOT = Path('/home/deploy/hut-reservations')
ENV_FILE = Path('/etc/hut-reservations/postgres.env')


def production_preflight(root):
    if root != PRODUCTION_ROOT:
        return
    if not ENV_FILE.is_file():
        raise RuntimeError('Missing production environment file. No source files changed.')
    script = 'set -e; set -a; source "$1"; set +a; exec python3 "$2" "$3"'
    result = subprocess.run(['bash', '-c', script, 'summitdesk-v153_1', str(ENV_FILE),
        str(PKG / 'check_environment_v153_1.py'), str(root)], capture_output=True, text=True)
    if result.returncode:
        # The controlled helper prints only setting names and error explanations.
        raise RuntimeError('Production environment check failed; no source files changed.\n' + result.stderr.strip())



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
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sd153_', delete=False) as stream:
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
    manifest = json.loads((PKG / 'manifest.json').read_text())
    payload = []
    unexpected = []
    for item in manifest.get('prerequisites', []):
        target = safe_path(root, item['path'])
        if target.exists() and not target.is_file():
            raise RuntimeError('Non-file prerequisite refused: ' + item['path'])
        current = digest(target.read_bytes()) if target.is_file() else None
        if current != item['sha256']:
            unexpected.append(item['path'])
    all_installed = True
    for item in manifest['files']:
        target = safe_path(root, item['path'])
        if target.exists() and not target.is_file():
            raise RuntimeError('Non-file target refused: ' + item['path'])
        source = safe_path(PKG / 'files', item['path'])
        data = source.read_bytes() if item['after_sha256'] is not None else None
        if data is not None and digest(data) != item['after_sha256']:
            raise RuntimeError(f'Damaged package payload: {item["path"]}')
        current = digest(target.read_bytes()) if target.is_file() else None
        if current not in [item['before_sha256'], item['after_sha256'], *item.get('compatible_sha256', [])]:
            unexpected.append(item['path'])
        if current != item['after_sha256']:
            all_installed = False
        if data is not None and item['path'].endswith('.py'):
            compile(data, item['path'], 'exec')
        payload.append((item, target, data))
    if unexpected:
        raise RuntimeError('Unexpected/customized files or incompatible baseline:\n  ' +
                           '\n  '.join(unexpected) + '\nNo source files changed. Do not force-overwrite these files.')
    return payload, all_installed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-installed', action='store_true', help='Require every release file to be installed')
    parser.add_argument('--check', action='store_true', help='Validate without changing files')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    payload, all_installed = preflight(root)
    production_preflight(root)
    if args.verify_installed:
        if not all_installed:
            raise RuntimeError('v153_1 source is not fully installed. Run install_v153_1.py first.')
        print('v153_1 installed source hashes verified.')
        return
    if args.check:
        print('v153_1 preflight passed; no files changed.')
        return
    import fcntl
    with (root / '.summitdesk_v153_1_install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        payload, all_installed = preflight(root)
        if all_installed:
            print('v153_1 source is already installed. Run deploy_v153_1.sh to verify migrations/services.')
            return
        parent = root / 'summitdesk_backups'
        if parent.is_symlink():
            raise RuntimeError('Symlink backup directory refused')
        parent.mkdir(exist_ok=True)
        backup = parent / ('main_hut_v153_1_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
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
                if data is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, data, entry['mode'])
        except BaseException:
            for entry in saved:
                target = safe_path(root, entry['path'])
                if entry['existed']:
                    atomic_write(target, (backup / entry['path']).read_bytes(), entry['mode'])
                elif target.exists():
                    target.unlink()
            raise
        print('v153_1 source installed. Run the deployment step to apply required migrations, checks and static assets.')
        print('Source backup:', backup)
        print('Next: bash v153_1_main_hut_package/deploy_v153_1.sh')
        print('Rollback: bash v153_1_main_hut_package/rollback_v153_1.sh ' + str(backup.relative_to(root)))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
