#!/usr/bin/env python3
"""Safe, source-only installer for SummitDesk v131 email digest preview.

Run from the Django project root:
    python3 v131_package/install_v131.py

Preflights all expected anchors and Python syntax before writing anything.
Creates a timestamped code backup and writes files atomically.
No database or SMTP connection, migrations, or scheduled-task changes.
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
    'bookings/manager_digest_preview_v131.py': 'manager_digest_preview_v131.py',
    'bookings/templates/bookings/manager_digest_preview_v131.html': 'manager_digest_preview_v131.html',
    'bookings/test_manager_digest_preview_v131.py': 'test_manager_digest_preview_v131.py',
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
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd131_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the Django project root beside manage.py.')
    require((ROOT / 'bookings/manager_digest_preferences_v130.py').is_file(),
            'v130 must be installed before v131 (preferences view missing).')
    require((ROOT / 'bookings/manager_digest_v129.py').is_file(),
            'v129 digest module is missing.')
    require((ROOT / 'bookings/migrations/0015_managerdigestpreference.py').is_file(),
            'v130 migration is missing; install v130 first.')

    urls_rel = 'bookings/urls.py'
    prefs_rel = 'bookings/templates/bookings/manager_digest_preferences_v130.html'
    urls = target_path(urls_rel).read_text(encoding='utf-8')
    prefs = target_path(prefs_rel).read_text(encoding='utf-8')
    require('manager_digest_preview_v131' not in urls, 'v131 already installed; refusing overwrite.')
    require('manager_digest_preview' not in prefs, 'v131 template link already exists; refusing overwrite.')

    urls = replace_once(
        urls,
        'from . import manager_digest_preferences_v130\n',
        'from . import manager_digest_preferences_v130\nfrom . import manager_digest_preview_v131\n',
        'URL imports',
    )
    urls = replace_once(
        urls,
        '    path("staff/settings/reminders/", manager_digest_preferences_v130.manager_digest_preferences, name="manager_digest_preferences"),',
        '    path("staff/settings/reminders/", manager_digest_preferences_v130.manager_digest_preferences, name="manager_digest_preferences"),\n'
        '    path("staff/settings/reminders/preview/", manager_digest_preview_v131.manager_digest_preview, name="manager_digest_preview"),',
        'URL route',
    )
    prefs = replace_once(
        prefs,
        '  <section class="dr-panel" aria-label="Email delivery history">',
        '''  <section class="dr-panel" aria-label="Preview next reminder">
    <h2>Preview your next reminder</h2>
    <p>See which pending requests would appear in your next daily summary, and check why a reminder might not be sent. No email is sent by the preview.</p>
    <a href="{% url 'bookings:manager_digest_preview' %}" style="display:inline-flex;align-items:center;min-height:44px;padding:10px 16px;background:#1c503b;color:#fff;border-radius:10px;font-weight:800;text-decoration:none">Preview daily email →</a>
  </section>
  <section class="dr-panel" aria-label="Email delivery history">''',
        'preferences preview link',
    )

    payload = {
        urls_rel: urls.encode('utf-8'),
        prefs_rel: prefs.encode('utf-8'),
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
    backup = ROOT / 'summitdesk_backups' / f'manager_digest_preview_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        target = target_path(rel)
        existed = target.is_file()
        manifest.append({
            'path': rel, 'existed': existed,
            'installed_sha256': hashlib.sha256(data).hexdigest(),
        })
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

    print('SummitDesk v131 installed: read-only manager email digest preview.')
    print('Backup:', backup)
    print('No migrations, SMTP changes, or timer changes are required.')
    print('NEXT: activate your production environment and run the targeted tests.')


if __name__ == '__main__':
    main()
