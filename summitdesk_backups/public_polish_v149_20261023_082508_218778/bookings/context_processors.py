from django.conf import settings


def hut(request):
    from .ui_locale_v147 import browser_messages
    return {"HUT_NAME": settings.HUT_NAME, "CURRENCY": settings.BOOKING_CURRENCY,
            "UI147": browser_messages()}
