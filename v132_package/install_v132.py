#!/usr/bin/env python3
"""Install SummitDesk v132 read-only reminder history.

Run from the Django project root: python3 v132_package/install_v132.py
Preflight, backup, atomic file writes; no Django imports, DB or SMTP calls.
"""
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent

NEW_FILES = {
    'bookings/manager_digest_history_v132.py': 'manager_digest_history_v132.py',
    'bookings/templates/bookings/manager_digest_history_v132.html': 'manager_digest_history_v132.html',
    'bookings/test_manager_digest_history_v132.py': 'test_manager_digest_history_v132.py',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def target_path(rel):
    path = Path(rel)
    require(not path.is_absolute() and '..' not in path.parts, f'Unsafe path: {rel}')
    target = ROOT / path
    require(ROOT in target.parents, f'Outside project: {rel}')
    require(not target.is_symlink(), f'Symlink target refused: {rel}')
    current = target.parent
    while current != ROOT:
        require(not current.is_symlink(), f'Symlink directory refused: {current}')
        current = current.parent
    return target


def replace_once(source, before, after, label):
    count = source.count(before)
    require(count == 1, f'Unexpected {label} layout: expected one anchor, found {count}. No files changed.')
    return source.replace(before, after, 1)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd132_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from Django project root beside manage.py.')
    require((ROOT / 'bookings/manager_digest_preview_v131.py').is_file(), 'v131 must be installed first.')
    require((ROOT / 'bookings/manager_digest_preferences_v130.py').is_file(), 'v130 must be installed first.')
    require((ROOT / 'bookings/migrations/0015_managerdigestpreference.py').is_file(), 'v130 migration is missing.')

    urls_rel = 'bookings/urls.py'
    prefs_rel = 'bookings/templates/bookings/manager_digest_preferences_v130.html'
    preview_rel = 'bookings/templates/bookings/manager_digest_preview_v131.html'
    urls = target_path(urls_rel).read_text(encoding='utf-8')
    prefs = target_path(prefs_rel).read_text(encoding='utf-8')
    preview = target_path(preview_rel).read_text(encoding='utf-8')
    require('manager_digest_history_v132' not in urls, 'v132 already installed; refusing overwrite.')
    require('manager_digest_history' not in prefs, 'v132 settings link already exists; refusing overwrite.')
    require('manager_digest_history' not in preview, 'v132 preview link already exists; refusing overwrite.')

    urls = replace_once(
        urls,
        'from . import manager_digest_preview_v131\n',
        'from . import manager_digest_preview_v131\nfrom . import manager_digest_history_v132\n',
        'URL imports',
    )
    urls = replace_once(
        urls,
        '    path("staff/settings/reminders/preview/", manager_digest_preview_v131.manager_digest_preview, name="manager_digest_preview"),',
        '    path("staff/settings/reminders/preview/", manager_digest_preview_v131.manager_digest_preview, name="manager_digest_preview"),\n'
        '    path("staff/settings/reminders/history/", manager_digest_history_v132.manager_digest_history, name="manager_digest_history"),',
        'URL route',
    )
    prefs = replace_once(
        prefs,
        '    <h2>Recent email history</h2>\n',
        '    <h2>Recent email history</h2>\n'
        '    <p><a href="{% url \'bookings:manager_digest_history\' %}" '
        'style="color:#1c503b;font-weight:800;text-underline-offset:3px">'
        'View full history and download CSV →</a></p>\n',
        'settings history link',
    )
    preview = replace_once(
        preview,
        '    <a href="{% url \'bookings:manager_digest_preferences\' %}">← Back to reminder settings</a>\n',
        '    <a href="{% url \'bookings:manager_digest_preferences\' %}">← Back to reminder settings</a>\n'
        '    <a href="{% url \'bookings:manager_digest_history\' %}" style="margin-left:20px">Email history →</a>\n',
        'preview history link',
    )

    payload = {
        urls_rel: urls.encode('utf-8'),
        prefs_rel: prefs.encode('utf-8'),
        preview_rel: preview.encode('utf-8'),
    }
    for rel, source in NEW_FILES.items():
        target = target_path(rel)
        require(not target.exists(), f'New file already exists (installation refused): {rel}')
        src = PKG / source
        require(src.is_file() and not src.is_symlink(), f'Package file missing: {source}')
        payload[rel] = src.read_bytes()
    for rel, data in payload.items():
        if rel.endswith('.py'):
            compile(data, rel, 'exec')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'manager_digest_history_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        target = target_path(rel)
        existed = target.is_file()
        manifest.append({'path': rel, 'existed': existed,
                         'installed_sha256': hashlib.sha256(data).hexdigest()})
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

    print('SummitDesk v132 installed: manager-only email reminder history and CSV export.')
    print('Backup:', backup)
    print('No migrations, SMTP, or timer changes are required.')
    print('NEXT: activate your production environment and run the targeted tests.')


if __name__ == '__main__':
    main()
