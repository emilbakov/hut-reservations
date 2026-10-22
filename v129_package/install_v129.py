#!/usr/bin/env python3
"""Safe, idempotence-checked installer for SummitDesk v129.

Run from the project root: python3 v129_package/install_v129.py
No Django imports or DB connections: production environment is loaded later.
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
    'bookings/manager_digest_v129.py': 'manager_digest_v129.py',
    'bookings/management/commands/send_manager_request_digest.py': 'send_manager_request_digest.py',
    'bookings/migrations/0014_managerrequestdigestlog.py': '0014_managerrequestdigestlog.py',
    'bookings/test_manager_digest_v129.py': 'test_manager_digest_v129.py',
}

MODEL_ADDENDUM = '''\n\nclass ManagerRequestDigestLog(models.Model):
    """At most one successfully submitted manager digest per local day."""
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='request_digest_logs',
    )
    digest_date = models.DateField()
    recipient = models.EmailField()
    hut_count = models.PositiveIntegerField(default=0)
    request_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-digest_date', '-sent_at']
        constraints = [models.UniqueConstraint(
            fields=['manager', 'digest_date'],
            name='unique_manager_request_digest_day',
        )]
'''

SMTP_SETTINGS = '''\n\n# v129: optional SMTP configuration via the production environment.
# Existing email settings are unchanged unless these variables are provided.
if os.environ.get('DJANGO_EMAIL_HOST'):
    EMAIL_HOST = os.environ['DJANGO_EMAIL_HOST']
if os.environ.get('DJANGO_EMAIL_PORT'):
    EMAIL_PORT = int(os.environ['DJANGO_EMAIL_PORT'])
if os.environ.get('DJANGO_EMAIL_HOST_USER'):
    EMAIL_HOST_USER = os.environ['DJANGO_EMAIL_HOST_USER']
if os.environ.get('DJANGO_EMAIL_HOST_PASSWORD'):
    EMAIL_HOST_PASSWORD = os.environ['DJANGO_EMAIL_HOST_PASSWORD']
if os.environ.get('DJANGO_EMAIL_USE_TLS') is not None:
    EMAIL_USE_TLS = os.environ['DJANGO_EMAIL_USE_TLS'] == '1'
if os.environ.get('DJANGO_EMAIL_USE_SSL') is not None:
    EMAIL_USE_SSL = os.environ['DJANGO_EMAIL_USE_SSL'] == '1'
if os.environ.get('DJANGO_EMAIL_TIMEOUT'):
    EMAIL_TIMEOUT = int(os.environ['DJANGO_EMAIL_TIMEOUT'])
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


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd129_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run in your Django project root beside manage.py.')
    require((ROOT / 'bookings/request_operations_v128.py').is_file(), 'v128 must be installed first.')
    require((ROOT / 'bookings/migrations/0013_reservation_guest_request.py').is_file(), 'v126 migration is missing.')
    model_path = target_path('bookings/models.py')
    settings_path = target_path('config/settings.py')
    require(model_path.is_file() and settings_path.is_file(), 'Django models/settings not found.')
    original_model = model_path.read_text(encoding='utf-8')
    original_settings = settings_path.read_text(encoding='utf-8')
    require('class GuestChangeRequest(models.Model)' in original_model, 'Unexpected reservation model layout.')
    require('class ManagerRequestDigestLog' not in original_model, 'v129 appears installed already; refusing overwrite.')
    require('DJANGO_EMAIL_HOST' not in original_settings, 'SMTP configuration already customized; review before installing.')
    require('import os' in original_settings, 'Expected os import missing from settings.py.')
    payload = {
        'bookings/models.py': (original_model.rstrip() + '\n' + MODEL_ADDENDUM).encode('utf-8'),
        'config/settings.py': (original_settings.rstrip() + '\n' + SMTP_SETTINGS).encode('utf-8'),
    }
    for rel, source in NEW_FILES.items():
        target = target_path(rel)
        require(not target.exists(), f'Already exists (installation refused): {rel}')
        src = PKG / source
        require(src.is_file() and not src.is_symlink(), f'Payload missing: {source}')
        payload[rel] = src.read_bytes()
    for rel, data in payload.items():
        if rel.endswith('.py'):
            compile(data, rel, 'exec')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'manager_digest_{stamp}'
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
    print('SummitDesk v129 source files installed successfully.')
    print('Backup:', backup)
    print('NEXT: activate your production environment and run python manage.py migrate --noinput.')
    print('The daily timer is NOT enabled automatically. See v129_package/README.txt.')


if __name__ == '__main__':
    main()
