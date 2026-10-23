"""Database-backed submission budgets shared by Gunicorn workers.

Never trust client-supplied forwarding headers. Unix/loopback proxy peers do
not share an IP bucket; browser and email budgets still apply in that setup.
"""
import ipaddress
import math
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import PublicBookingRateBucket
from .reliability_v145 import browser_secret


class BookingRateLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, retry_after)


def _budget(kind, value, limit, window, now):
    period = int(now.timestamp()) // window
    key = salted_hmac("summitdesk.booking-budget.v150", f"{kind}:{value}:{period}", algorithm="sha256").hexdigest()
    expires = datetime.fromtimestamp((period + 1) * window, tz=datetime_timezone.utc)
    return key, limit, expires


def reserve_budget(request, email):
    now = timezone.now()
    budgets = [
        _budget("browser", browser_secret(request), getattr(settings, "BOOKING_BROWSER_LIMIT", 12), 600, now),
        _budget("email", email.strip().casefold(), getattr(settings, "BOOKING_EMAIL_LIMIT", 6), 3600, now),
    ]
    try:
        peer = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
    except ValueError:
        peer = None
    if peer and not peer.is_loopback:
        budgets.append(_budget("peer", str(peer), getattr(settings, "BOOKING_IP_LIMIT", 60), 600, now))
    # Stable lock order prevents requests sharing several buckets from deadlocking.
    with transaction.atomic():
        locked = []
        for key, limit, expires in sorted(budgets):
            PublicBookingRateBucket.objects.get_or_create(key=key, defaults={"expires_at": expires})
            bucket = PublicBookingRateBucket.objects.select_for_update().get(key=key)
            if bucket.attempts >= limit:
                raise BookingRateLimited(math.ceil((expires - now).total_seconds()))
            locked.append(bucket)
        for bucket in locked:
            bucket.attempts += 1
            bucket.save(update_fields=["attempts"])
        stale = list(PublicBookingRateBucket.objects.filter(expires_at__lte=now).values_list("pk", flat=True)[:100])
        if stale:
            PublicBookingRateBucket.objects.filter(pk__in=stale).delete()
