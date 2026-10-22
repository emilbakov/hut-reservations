"""Public request emails. Never email a guest's private link to staff."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Hut

logger = logging.getLogger(__name__)


def _hut(reservation):
    item = reservation.items.select_related('room__hut').first()
    return item.room.hut if item and item.room.hut_id else None


def _guest_context(request, reservation):
    hut = _hut(reservation)
    return {
        'reservation': reservation,
        'hut_name': hut.name if hut else settings.HUT_NAME,
        'link': request.build_absolute_uri(reservation.get_absolute_url()),
        'currency': settings.BOOKING_CURRENCY,
    }


def _send(subject, body, recipients, code):
    if not recipients:
        return
    try:
        send_mail(subject, body, None, recipients, fail_silently=False)
    except Exception:
        logger.exception('Could not deliver reservation request email for %s', code)


def send_guest_request_received(request, reservation):
    """Tell guest the request is NOT confirmed, then notify assigned managers."""
    context = _guest_context(request, reservation)
    if reservation.email:
        body = render_to_string('bookings/email_request_received_v126.txt', context)
        _send('Reservation request received — awaiting approval', body,
              [reservation.email], reservation.code)

    hut = _hut(reservation)
    recipients = set()
    if hut:
        recipients.update(
            email for email in hut.managers.exclude(email='').values_list('email', flat=True)
            if email
        )
    if settings.BOOKING_NOTIFY_EMAIL:
        recipients.add(settings.BOOKING_NOTIFY_EMAIL)
    recipients.discard(reservation.email)
    if recipients:
        manager_url = request.build_absolute_uri(reverse('bookings:approval_dashboard'))
        body = (
            f'New reservation request awaiting your approval.\n\n'
            f'Hut: {context["hut_name"]}\n'
            f'Guest: {reservation.name}\n'
            f'Arrival: {reservation.check_in}\nDeparture: {reservation.check_out}\n'
            f'Beds: {reservation.total_beds}\nReference: {reservation.code}\n\n'
            f'Review in SummitDesk: {manager_url}\n'
        )
        _send('New guest reservation request — action required', body,
              sorted(recipients), reservation.code)


def send_guest_request_declined(request, reservation):
    if not reservation.email:
        return
    context = _guest_context(request, reservation)
    body = render_to_string('bookings/email_request_declined_v126.txt', context)
    _send('Reservation request declined or cancelled', body,
          [reservation.email], reservation.code)
