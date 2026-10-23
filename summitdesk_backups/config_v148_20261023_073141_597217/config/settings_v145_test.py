"""Isolated regression-test settings. Never use as production settings."""
import os
os.environ.setdefault('DJANGO_SECRET_KEY', 'v145-isolated-tests-only-not-a-production-secret-key')
from .settings_test import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:',
                       'OPTIONS': {'transaction_mode': 'IMMEDIATE', 'timeout': 20}}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
