from django.conf import settings


def hut(request):
    return {"HUT_NAME": settings.HUT_NAME, "CURRENCY": settings.BOOKING_CURRENCY}
