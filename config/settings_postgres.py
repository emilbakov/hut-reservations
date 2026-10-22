"""Isolated PostgreSQL destination for migration trial. Never used by Gunicorn."""
import os
from .settings import *
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "hut_reservations",
    "USER": "hut_app",
    "PASSWORD": os.environ["HUT_PG_PASSWORD"],
    "HOST": "127.0.0.1",
    "PORT": "5432",
    "CONN_MAX_AGE": 0,
}}
