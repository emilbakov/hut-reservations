"""Read-only source snapshot for PostgreSQL migration trial."""
from .settings import *
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/home/deploy/reservation-backups/db-before-postgresql.sqlite3"}}
