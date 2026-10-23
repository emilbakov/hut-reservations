from .settings import *

# Test-only settings. Never use these for production.
SECURE_SSL_REDIRECT = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
