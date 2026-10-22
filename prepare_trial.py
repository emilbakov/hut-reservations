#!/usr/bin/env python3
"""Create isolated settings modules for a SQLite -> PostgreSQL trial.

Run from the Django project root (directory containing manage.py).
Does not modify existing settings.py or production DATABASES.
"""
import ast
import os
from pathlib import Path

root = Path.cwd()
manage = root / 'manage.py'
if not manage.is_file():
    raise SystemExit('Run this from the directory containing manage.py')
module = None
for node in ast.walk(ast.parse(manage.read_text())):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'setdefault' and len(node.args) >= 2:
        if isinstance(node.args[0], ast.Constant) and node.args[0].value == 'DJANGO_SETTINGS_MODULE' and isinstance(node.args[1], ast.Constant):
            module = node.args[1].value
            break
if not module or not module.endswith('.settings'):
    raise SystemExit('Could not identify standard Django settings module; no files changed.')
settings_path = root / Path(*module.split('.')).with_suffix('.py')
if not settings_path.exists():
    raise SystemExit(f'Could not find settings file {settings_path}')
settings_dir = settings_path.parent
base = module.rsplit('.', 1)[0]
backup = Path('/home/deploy/reservation-backups/db-before-postgresql.sqlite3')
if not backup.is_file():
    raise SystemExit(f'Missing SQLite backup: {backup}')
modules = {
    'settings_sqlite_trial.py': '''"""Read-only source snapshot for PostgreSQL migration trial."""\nfrom .settings import *\nDATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/home/deploy/reservation-backups/db-before-postgresql.sqlite3"}}\n''',
    'settings_postgres_trial.py': '''"""Isolated PostgreSQL destination for migration trial. Never used by Gunicorn."""\nimport os\nfrom .settings import *\nDATABASES = {"default": {\n    "ENGINE": "django.db.backends.postgresql",\n    "NAME": "hut_reservations",\n    "USER": "hut_app",\n    "PASSWORD": os.environ["HUT_PG_PASSWORD"],\n    "HOST": "127.0.0.1",\n    "PORT": "5432",\n    "CONN_MAX_AGE": 0,\n}}\n''',
}
for name, content in modules.items():
    dest = settings_dir / name
    if dest.exists() and dest.read_text() != content:
        raise SystemExit(f'Refusing to overwrite custom settings: {dest}')
    dest.write_text(content)
    os.chmod(dest, 0o600)
print('SQLite trial module:', base + '.settings_sqlite_trial')
print('PostgreSQL trial module:', base + '.settings_postgres_trial')
print('Source snapshot:', backup)
