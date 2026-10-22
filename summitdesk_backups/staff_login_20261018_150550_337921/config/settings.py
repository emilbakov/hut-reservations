"""Settings for the hut reservations site.

Development defaults work out of the box. For production set the
environment variables DJANGO_SECRET_KEY, DJANGO_DEBUG=0 and
DJANGO_ALLOWED_HOSTS, and switch the database to PostgreSQL.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
if not DEBUG and SECRET_KEY == "dev-only-change-me":
    raise RuntimeError("Set DJANGO_SECRET_KEY before running in production")
ALLOWED_HOSTS = ['167.233.96.3','127.0.0.1']

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "bookings",
    
    "floorplans.reservation_audit_apps.FloorplansV31Config",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "floorplans.audit_actor.ReservationAuditActorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "bookings.context_processors.hut",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            # Take the write lock when a transaction starts, so two bookings
            # made at the same moment queue up instead of racing each other.
            # (SQLite ignores select_for_update; PostgreSQL honours it.)
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Sofia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = "/var/www/hut-static"
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG and os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
if os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS"):
    CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.environ["DJANGO_CSRF_TRUSTED_ORIGINS"].split(",") if x.strip()]

# Emails are printed to the terminal in development.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_FROM_EMAIL", "bookings@example.com")

# --- Hut settings -----------------------------------------------------------
HUT_NAME = os.environ.get("HUT_NAME", "Mountain Hut")
BOOKING_CURRENCY = "€"
BOOKING_MAX_NIGHTS = 14           # longest stay a guest can book online
BOOKING_MAX_DAYS_AHEAD = 365      # how far in advance bookings open
BOOKING_INITIAL_STATUS = "confirmed"  # use "pending" once you add payments
BOOKING_PENDING_MINUTES = 15      # unpaid holds older than this are released
BOOKING_NOTIFY_EMAIL = os.environ.get("BOOKING_NOTIFY_EMAIL", "")         # the hut keeper's address, optional
