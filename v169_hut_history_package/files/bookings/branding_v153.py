"""Shared display branding; hut identities and permissions remain separate."""
from django.conf import settings

DEFAULT_BRAND = 'Карлък'
PLACEHOLDERS = {'', 'mountain hut', 'summitdesk'}


def brand_name(profile=None):
    configured = getattr(profile, 'brand_name', '').strip()
    if configured.casefold() not in PLACEHOLDERS:
        return configured
    configured = settings.HUT_NAME.strip()
    return DEFAULT_BRAND if configured.casefold() in PLACEHOLDERS else configured
