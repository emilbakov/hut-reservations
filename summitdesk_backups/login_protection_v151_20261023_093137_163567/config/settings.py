"""Settings for the hut reservations site.

DEBUG is off unless DJANGO_DEBUG=1 is explicitly set for development.
Production requires DJANGO_SECRET_KEY. Set DJANGO_ALLOWED_HOSTS to a
comma-separated list of hostnames/IPs and use PostgreSQL. Uploaded photos
use DJANGO_MEDIA_ROOT, defaulting to /var/www/hut-media in production.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Shared database submission budgets; forwarded IP headers are never trusted.
BOOKING_BROWSER_LIMIT = int(os.environ.get("DJANGO_BOOKING_BROWSER_LIMIT", "12"))
BOOKING_EMAIL_LIMIT = int(os.environ.get("DJANGO_BOOKING_EMAIL_LIMIT", "6"))
BOOKING_IP_LIMIT = int(os.environ.get("DJANGO_BOOKING_IP_LIMIT", "60"))
if min(BOOKING_BROWSER_LIMIT, BOOKING_EMAIL_LIMIT, BOOKING_IP_LIMIT) < 1:
    raise RuntimeError("Booking request limits must be positive")

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
if not DEBUG and (not SECRET_KEY.strip() or SECRET_KEY == "dev-only-change-me"):
    raise RuntimeError("Set DJANGO_SECRET_KEY before running in production")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "167.233.96.3,127.0.0.1,localhost"
).split(",") if host.strip()]
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS to the hostnames/IPs this site serves")

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
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bookings.staff_auth_v117.StaffLoginRedirectMiddleware",
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
LANGUAGES = [("en", "English"), ("bg", "Български")]
TIME_ZONE = "Europe/Sofia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = "/var/www/hut-static"

# nginx serves public hut photos in production; Django serves them only in DEBUG.
MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("DJANGO_MEDIA_ROOT") or (
    str(BASE_DIR / "media") if DEBUG else "/var/www/hut-media"
)
if not DEBUG and not Path(MEDIA_ROOT).is_absolute():
    raise RuntimeError("DJANGO_MEDIA_ROOT must be an absolute directory in production")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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

# Staff and cleaner authentication entry point.
LOGIN_URL = "/staff/login/"


# v129: optional SMTP configuration via the production environment.
# Existing email settings are unchanged unless these variables are provided.
# Gmail SMTP configuration
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_APP_PASSWORD", "")

EMAIL_TIMEOUT = 20
