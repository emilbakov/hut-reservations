#!/usr/bin/env python3
"""Safe source-only installer for SummitDesk v130.

Run from the project root: python3 v130_package/install_v130.py
Does not import Django or connect to the production database.
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
    'bookings/manager_digest_preferences_v130.py': 'manager_digest_preferences_v130.py',
    'bookings/templates/bookings/manager_digest_preferences_v130.html': 'manager_digest_preferences_v130.html',
    'bookings/migrations/0015_managerdigestpreference.py': '0015_managerdigestpreference.py',
    'bookings/test_manager_digest_preferences_v130.py': 'test_manager_digest_preferences_v130.py',
}

MODEL_ADDENDUM = '''\n\nclass ManagerDigestPreference(models.Model):
    """Manager's personal daily email reminder preferences (v130)."""
    manager = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='digest_preference',
    )
    enabled = models.BooleanField(default=True)
    urgent_only = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
'''


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
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd130_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from Django project root beside manage.py.')
    require((ROOT / 'bookings/migrations/0014_managerrequestdigestlog.py').is_file(),
            'v129 must be installed first (migration 0014 is missing).')
    require((ROOT / 'bookings/manager_digest_v129.py').is_file(), 'v129 digest module is missing.')
    require((ROOT / 'bookings/management/commands/send_manager_request_digest.py').is_file(),
            'v129 digest command is missing.')

    paths = {
        'model': 'bookings/models.py',
        'digest': 'bookings/manager_digest_v129.py',
        'command': 'bookings/management/commands/send_manager_request_digest.py',
        'urls': 'bookings/urls.py',
        'dashboard': 'bookings/templates/bookings/approval_dashboard_v127.html',
    }
    original = {}
    for name, rel in paths.items():
        path = target_path(rel)
        require(path.is_file(), f'Expected file not found: {rel}')
        original[name] = path.read_text(encoding='utf-8')

    require('class ManagerRequestDigestLog(models.Model)' in original['model'], 'Unexpected v129 model layout.')
    require('class ManagerDigestPreference' not in original['model'],
            'v130 already installed or partially installed; refusing to overwrite.')
    require('manager_digest_preferences' not in original['urls'],
            'v130 URL appears installed; refusing overwrite.')

    digest = replace_once(
        original['digest'],
        'from .models import Hut, ManagerRequestDigestLog, Reservation',
        'from .models import Hut, ManagerDigestPreference, ManagerRequestDigestLog, Reservation',
        'digest model import',
    )
    digest = replace_once(
        digest,
        "        if ManagerRequestDigestLog.objects.filter(manager=manager, digest_date=today).exists():\n"
        "            return 'duplicate', 0\n"
        "        summaries = collect_pending_summaries(manager, now=now, today=today)\n"
        "        return ('preview', sum(item['pending'] for item in summaries)) if summaries else ('empty', 0)",
        "        preference = ManagerDigestPreference.objects.filter(manager=manager).first()\n"
        "        if preference and not preference.enabled:\n"
        "            return 'disabled', 0\n"
        "        if ManagerRequestDigestLog.objects.filter(manager=manager, digest_date=today).exists():\n"
        "            return 'duplicate', 0\n"
        "        summaries = collect_pending_summaries(manager, now=now, today=today)\n"
        "        if not summaries:\n"
        "            return 'empty', 0\n"
        "        total = sum(item['pending'] for item in summaries)\n"
        "        if preference and preference.urgent_only and not any(\n"
        "                item['waiting24'] or item['arrival48'] for item in summaries):\n"
        "            return 'not_urgent', total\n"
        "        return 'preview', total",
        'preview preference handling',
    )
    digest = replace_once(
        digest,
        "        if ManagerRequestDigestLog.objects.filter(manager=manager, digest_date=today).exists():\n"
        "            return 'duplicate', 0\n"
        "        summaries = collect_pending_summaries(manager, now=now, today=today)\n"
        "        if not summaries:\n"
        "            return 'empty', 0\n"
        "        total = sum(item['pending'] for item in summaries)\n"
        "        subject, body = render_digest(summaries, base_url=base_url, today=today)",
        "        preference = ManagerDigestPreference.objects.filter(manager=manager).first()\n"
        "        if preference and not preference.enabled:\n"
        "            return 'disabled', 0\n"
        "        if ManagerRequestDigestLog.objects.filter(manager=manager, digest_date=today).exists():\n"
        "            return 'duplicate', 0\n"
        "        summaries = collect_pending_summaries(manager, now=now, today=today)\n"
        "        if not summaries:\n"
        "            return 'empty', 0\n"
        "        total = sum(item['pending'] for item in summaries)\n"
        "        if preference and preference.urgent_only and not any(\n"
        "                item['waiting24'] or item['arrival48'] for item in summaries):\n"
        "            return 'not_urgent', total\n"
        "        subject, body = render_digest(summaries, base_url=base_url, today=today)",
        'send preference handling',
    )
    digest = replace_once(
        digest,
        "        'You are receiving this summary because you are assigned as a hut manager.',",
        "        'Manage reminder preferences:',\n"
        "        f'{base_url}{reverse(\"bookings:manager_digest_preferences\")}',\n"
        "        '',\n"
        "        'You are receiving this summary because you are assigned as a hut manager.',",
        'email preferences link',
    )

    command = replace_once(
        original['command'],
        "counts = {'sent': 0, 'preview': 0, 'duplicate': 0, 'empty': 0, 'ineligible': 0, 'failed': 0}",
        "counts = {'sent': 0, 'preview': 0, 'duplicate': 0, 'empty': 0, 'disabled': 0, 'not_urgent': 0, 'ineligible': 0, 'failed': 0}",
        'digest command counters',
    )
    urls = replace_once(
        original['urls'],
        'from . import approval_dashboard_v127\n',
        'from . import approval_dashboard_v127\nfrom . import manager_digest_preferences_v130\n',
        'URL imports',
    )
    urls = replace_once(
        urls,
        '    path("staff/reservations/requests/", approval_dashboard_v127.approval_dashboard, name="approval_dashboard"),',
        '    path("staff/reservations/requests/", approval_dashboard_v127.approval_dashboard, name="approval_dashboard"),\n'
        '    path("staff/settings/reminders/", manager_digest_preferences_v130.manager_digest_preferences, name="manager_digest_preferences"),',
        'URL route',
    )
    dashboard = replace_once(
        original['dashboard'],
        '    <a class="aq-back" href="{% url \'bookings:manager_reservations\' %}">← All reservations</a>',
        '    <div style="display:flex;gap:10px;flex-wrap:wrap">\n'
        '      <a class="aq-back" href="{% url \'bookings:manager_digest_preferences\' %}">Email reminders</a>\n'
        '      <a class="aq-back" href="{% url \'bookings:manager_reservations\' %}">← All reservations</a>\n'
        '    </div>',
        'approval dashboard navigation',
    )

    payload = {
        paths['model']: (original['model'].rstrip() + '\n' + MODEL_ADDENDUM).encode('utf-8'),
        paths['digest']: digest.encode('utf-8'),
        paths['command']: command.encode('utf-8'),
        paths['urls']: urls.encode('utf-8'),
        paths['dashboard']: dashboard.encode('utf-8'),
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
    backup = ROOT / 'summitdesk_backups' / f'manager_preferences_{stamp}'
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
    print('SummitDesk v130 source files installed successfully.')
    print('Backup:', backup)
    print('NEXT: activate production environment and run python manage.py migrate --noinput.')
    print('No email timer or SMTP settings were changed.')


if __name__ == '__main__':
    main()
