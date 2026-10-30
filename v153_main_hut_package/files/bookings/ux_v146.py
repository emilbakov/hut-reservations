"""Read-only booking presentation helpers. Inventory rules stay in services."""
from django.utils.translation import gettext as _
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from .services import free_beds


def party_size(params):
    raw = params.get('beds', '')
    if raw in ('', None):
        return None, ''
    try:
        value = int(raw)
        if not 1 <= value <= 30:
            raise ValueError
    except (ValueError, TypeError):
        return None, _('Choose between 1 and 30 guests.')
    return value, ''


def selected_summary(booking, rooms, nights):
    rows, count, total = [], 0, Decimal('0')
    for room in rooms:
        name = f'room_{room.pk}'
        value = booking[name].value() if name in booking.fields else 0
        try:
            quantity = max(0, int(value or 0))
        except (ValueError, TypeError):
            quantity = 0
        if quantity:
            subtotal = room.price_per_night * quantity * nights
            rows.append({'room': room, 'beds': quantity, 'subtotal': subtotal})
            count += quantity
            total += subtotal
    return rows, count, total


def nearby_stays(hut, rooms, start, end, guests):
    if not hut or not rooms or not guests:
        return []
    today, results = timezone.localdate(), []
    for shift in (1, -1, 2, -2, 3, -3):
        arrival, departure = start + timedelta(days=shift), end + timedelta(days=shift)
        if not today <= arrival <= today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD):
            continue
        free = free_beds(rooms, arrival, departure)
        if sum(free.values()) < guests:
            continue
        results.append({'check_in': arrival, 'check_out': departure, 'free': sum(free.values()),
                        'url': reverse('bookings:hut_detail', args=[hut.slug]) + '?' + urlencode({
                            'check_in': arrival.isoformat(), 'check_out': departure.isoformat(), 'beds': guests})})
        if len(results) == 2:
            break
    return results
