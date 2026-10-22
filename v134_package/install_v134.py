#!/usr/bin/env python3
"""Install SummitDesk v134 in the Django root (beside manage.py).

All patch anchors and target paths are checked before writing anything.
No database migrations or email sends are run by the installer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
PATCHES = json.loads((PKG / 'patches.json').read_text(encoding='utf-8'))
ADDITIONS = [
    'bookings/conversations_v134.py',
    'bookings/migrations/0016_guest_conversation_v134.py',
    'bookings/templates/bookings/conversation_inbox_v134.html',
    'bookings/templates/bookings/conversation_thread_v134.html',
    'bookings/templates/bookings/quick_replies_v134.html',
    'bookings/test_conversations_v134.py',
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def target_path(relative):
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts, f'Unsafe path: {relative}')
    target = ROOT / path
    require(ROOT in target.parents and not target.is_symlink(), f'Unsafe target: {relative}')
    current = target.parent
    while current != ROOT:
        require(not current.is_symlink(), f'Symlink directory refused: {current}')
        current = current.parent
    return target


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd134_', delete=False) as fh:
            temporary = Path(fh.name)
            fh.write(data)
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def preflight():
    require((ROOT / 'manage.py').is_file(), 'Run from the Django project root beside manage.py.')
    require((ROOT / 'bookings/test_mobile_v133.py').is_file(), 'Install v133 first.')
    require((ROOT / 'bookings/migrations/0015_managerdigestpreference.py').is_file(), 'Install v130 first.')
    require(not (ROOT / 'bookings/conversations_v134.py').exists(), 'v134 appears installed. Refusing to overwrite.')
    payload = {}
    for rel, ops in PATCHES.items():
        target = target_path(rel)
        require(target.is_file(), f'Required v133 file missing: {rel}')
        source = target.read_text(encoding='utf-8')
        for op in ops:
            count = source.count(op['before'])
            require(count == 1, f'Unexpected or customized {rel}: expected one patch anchor, found {count}. No files changed.')
            source = source.replace(op['before'], op['after'], 1)
        payload[rel] = source.encode('utf-8')
    for rel in ADDITIONS:
        target = target_path(rel)
        require(not target.exists(), f'File already exists: {rel}. Refusing to overwrite.')
        payload[rel] = (PKG / 'files' / rel).read_bytes()
    for rel, data in payload.items():
        if rel.endswith('.py'):
            compile(data, rel, 'exec')
    return payload


def main():
    payload = preflight()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'communications_v134_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        target = target_path(rel)
        existed = target.is_file()
        manifest.append({'path': rel, 'existed': existed, 'installed_sha256': hashlib.sha256(data).hexdigest()})
        if existed:
            saved = backup / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for rel, data in payload.items():
            atomic_write(target_path(rel), data)
    except Exception:
        for entry in manifest:
            target = target_path(entry['path'])
            if entry['existed']:
                shutil.copy2(backup / entry['path'], target)
            elif target.exists():
                target.unlink()
        raise
    print('SummitDesk v134 installed: direct guest messages, email copies, quick replies, conversation timeline.')
    print('Backup:', backup)
    print('NEXT: activate venv, load PostgreSQL env, run migrate, check and targeted tests.')
    print('IMPORTANT: do not enable public messaging until database migration succeeds.')


if __name__ == '__main__':
    main()
