from django.conf import settings


def hut(request):
    from .ui_locale_v147 import browser_messages
    context = {"HUT_NAME": settings.HUT_NAME, "CURRENCY": settings.BOOKING_CURRENCY,
               "UI147": browser_messages()}
    if not request.path.startswith(("/staff/", "/admin/")):
        from .public_profile_v149 import public_context
        context.update(public_context(request))
    return context
