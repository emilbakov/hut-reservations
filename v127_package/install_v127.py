#!/usr/bin/env python3
"""Install the guest-request review dashboard. Run from the project root.

All changes are validated in memory first. Files are backed up before writing.
No database migrations or data changes are made by this script.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
NEW = {
    'bookings/approval_dashboard_v127.py': 'approval_dashboard_v127.py',
    'bookings/templates/bookings/approval_dashboard_v127.html': 'approval_dashboard_v127.html',
    'bookings/test_approval_dashboard_v127.py': 'test_approval_dashboard_v127.py',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def replace_once(source, old, new, label):
    require(source.count(old) == 1, f'Unexpected {label} structure: expected one match, found {source.count(old)}. No files changed.')
    return source.replace(old, new, 1)


def patch_urls(text):
    text = replace_once(text,
        'from . import public_site_v124\n',
        'from . import public_site_v124\nfrom . import approval_dashboard_v127\n',
        'URL import')
    return replace_once(text,
        '    # Hut manager reservation management\n',
        '    # Guest requests approval dashboard\n'
        '    path("staff/reservations/requests/", approval_dashboard_v127.approval_dashboard, name="approval_dashboard"),\n\n'
        '    # Hut manager reservation management\n',
        'URL route')


def patch_views(text):
    return replace_once(text,
        '    # Fixed destination avoids untrusted redirect parameters.\n'
        '    return redirect("bookings:manager_reservations")\n',
        '    # Only a fixed, known destination is allowed (never a user-supplied URL).\n'
        '    if request.POST.get("source") == "approvals":\n'
        '        return redirect("bookings:approval_dashboard")\n'
        '    return redirect("bookings:manager_reservations")\n',
        'safe redirect from approval queue')


def patch_manager_template(text):
    return replace_once(text,
        '  <nav class="mr-quicklinks" aria-label="Reservation management tools">\n',
        '  <nav class="mr-quicklinks" aria-label="Reservation management tools">\n'
        '    <a href="{% url \'bookings:approval_dashboard\' %}">Guest requests · Review &amp; approve ↗</a>\n',
        'reservations dashboard link')


def patch_email(text):
    return replace_once(text,
        "reverse('bookings:manager_reservations')",
        "reverse('bookings:approval_dashboard')",
        'manager notification destination')


PATCH = {
    'bookings/urls.py': patch_urls,
    'bookings/views.py': patch_views,
    'bookings/templates/bookings/manager_reservations.html': patch_manager_template,
    'bookings/guest_requests_v126.py': patch_email,
}


def target_path(rel):
    relpath = Path(rel)
    require(not relpath.is_absolute() and '..' not in relpath.parts, f'Unsafe path: {rel}')
    target = ROOT / relpath
    require(ROOT in target.parents, f'Path outside project: {rel}')
    require(not target.is_symlink(), f'Refusing symlink: {rel}')
    parent = target.parent
    while parent != ROOT:
        require(not parent.is_symlink(), f'Refusing symlink directory: {parent}')
        parent = parent.parent
    return target


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd127_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the SummitDesk project root.')
    require((ROOT / 'bookings/migrations/0013_reservation_guest_request.py').is_file(), 'Install v126 first.')
    require((ROOT / 'bookings/guest_requests_v126.py').is_file(), 'Missing v126 guest approval service.')
    payload = {}
    for rel, transform in PATCH.items():
        target = target_path(rel)
        require(target.is_file(), f'Missing required source: {rel}')
        original = target.read_text(encoding='utf-8')
        updated = transform(original)
        require(updated != original, f'No change generated for {rel}')
        payload[rel] = updated.encode('utf-8')
    for rel, srcname in NEW.items():
        target = target_path(rel)
        require(not target.exists(), f'Already installed or conflicting file: {rel}')
        src = PKG / srcname
        require(src.is_file() and not src.is_symlink(), f'Missing payload file: {srcname}')
        payload[rel] = src.read_bytes()
    for rel, content in payload.items():
        if rel.endswith('.py'):
            compile(content, rel, 'exec')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'approval_dashboard_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        path = target_path(rel)
        exists = path.is_file()
        manifest.append({'path': rel, 'existed': exists, 'installed_sha256': hashlib.sha256(data).hexdigest()})
        if exists:
            destination = backup / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
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
    print('Guest request review dashboard installed.')
    print('Backup:', backup)
    print('No database migration required. Run Django checks and tests before restarting Gunicorn.')


if __name__ == '__main__':
    main()
