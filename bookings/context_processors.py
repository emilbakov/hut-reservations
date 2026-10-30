from django.conf import settings


def hut(request):
    from .ui_locale_v147 import browser_messages
    from .branding_v153 import brand_name
    from .public_profile_v149 import profile_for
    brand = brand_name() if getattr(request, '_skip_brand_profile_v153', False) else brand_name(profile_for(request))
    context = {"HUT_NAME": brand, "BRAND_NAME": brand, "CURRENCY": settings.BOOKING_CURRENCY,
               "UI147": browser_messages()}
    if not request.path.startswith(("/staff/", "/admin/")):
        from .public_profile_v149 import public_context
        context.update(public_context(request))
    from .whole_units_v183 import whole_units
    context.update(WHOLE_UNITS=whole_units(), BOOKING_UNIT="room" if whole_units() else "bed")
    return context
