"""Public request emails. Never email a guest's private link to staff."""
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string

from .models import Hut


def _hut(reservation):
    item = reservation.items.select_related('room__hut').first()
    return item.room.hut if item and item.room.hut_id else None


def _guest_context(request, reservation):
    hut = _hut(reservation)
    from .self_service import issue_guest_link
    try:
        link = request.build_absolute_uri(issue_guest_link(reservation))
    except PermissionDenied:
        link = request.build_absolute_uri(reservation.get_absolute_url())
    return {
        'reservation': reservation,
        'hut_name': hut.name if hut else settings.HUT_NAME,
        'link': link,
        'currency': settings.BOOKING_CURRENCY,
    }


def send_guest_request_received(request, reservation):
    from .notifications_v145 import queue_request_received
    queue_request_received(request, reservation)


def send_guest_request_declined(request, reservation):
    from .notifications_v145 import supersede_request_notifications
    supersede_request_notifications(reservation)
    if not reservation.email:
        return
    context = _guest_context(request, reservation)
    body = render_to_string('bookings/email_request_declined_v126.txt', context)
    from .notifications_v145 import queue_notification
    queue_notification(reservation, 'declined_guest', 'Reservation request declined or cancelled', body, reservation.email)
