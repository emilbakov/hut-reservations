import os

# Test-only fallback; never import this module from production settings.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-production-secret")

from .settings import *

# Test-only settings. Never use these for production.
SECURE_SSL_REDIRECT = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
