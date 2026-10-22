#!/usr/bin/env python3
"""Create a private pre-migration backup using the configured database."""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path.cwd().resolve()))
import django
django.setup()
from django.db import connection

root = Path.cwd().resolve()
directory = root.parent / 'reservation-backups'
directory.mkdir(mode=0o700, exist_ok=True)
if directory.is_symlink():
    raise SystemExit('Symlink backup directory refused')
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
settings = connection.settings_dict
engine = settings['ENGINE']
if engine.endswith('postgresql'):
    if not shutil.which('pg_dump'):
        raise SystemExit('pg_dump is required for the automatic database backup. No migration was run.')
    destination = directory / f'v145_before_{stamp}.dump'
    env = os.environ.copy()
    env['PGPASSWORD'] = settings.get('PASSWORD', '')
    args = ['pg_dump', '--format=custom', '--no-owner', '--no-privileges',
            '--host', settings.get('HOST') or 'localhost', '--port', str(settings.get('PORT') or '5432'),
            '--username', settings.get('USER') or os.environ.get('USER', ''), '--dbname', str(settings['NAME'])]
    with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        result = subprocess.run(args, env=env, stdout=output, stderr=subprocess.PIPE)
    if result.returncode:
        destination.unlink(missing_ok=True)
        raise SystemExit('Database backup failed. Check local PostgreSQL access; no migration was run.')
elif engine.endswith('sqlite3'):
    destination = directory / f'v145_before_{stamp}.sqlite3'
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with sqlite3.connect(settings['NAME']) as source, sqlite3.connect(destination) as target:
        source.backup(target)
else:
    raise SystemExit('Unsupported database for automatic backup; no migration was run.')
print('Database backup:', destination)
