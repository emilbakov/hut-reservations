"""Persist notifications before delivery; retry failures without changing bookings."""
import hashlib
import logging
import re
from datetime import timedelta

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import ReservationNotification

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def queue_notification(reservation, kind, subject, body, recipient, *, event=''):
    if not recipient:
        return None
    key = hashlib.sha256(f'{reservation.pk}:{kind}:{recipient}:{event}'.encode()).hexdigest()
    item, created = ReservationNotification.objects.get_or_create(dedupe_key=key, defaults={
        'reservation': reservation, 'kind': kind, 'recipient': recipient,
        'subject': subject[:255], 'body': body})
    if created:
        transaction.on_commit(lambda pk=item.pk: deliver_notification(pk), robust=True)
    return item


def deliver_notification(pk, *, manual=False):
    # One row lock serializes automatic and manual retries. SMTP delivery is
    # at-least-once: an SMTP acceptance followed by a process crash can repeat.
    with transaction.atomic():
        item = ReservationNotification.objects.select_for_update().get(pk=pk)
        now = timezone.now()
        if item.status in ('sent', 'skipped') or (not manual and (item.attempts >= MAX_ATTEMPTS or item.next_attempt_at > now)):
            return item.status
        from .models import Reservation
        current_status = Reservation.objects.values_list('status', flat=True).get(pk=item.reservation_id)
        if ((item.kind.startswith('request_') and current_status != 'pending') or
                (item.kind.startswith('confirmation_') and current_status != 'confirmed')):
            item.status = 'skipped'
            item.last_error = ''
            item.save(update_fields=['status', 'last_error'])
            return item.status
        item.attempts += 1
        item.last_attempt_at = now
        try:
            from django.conf import settings
            if not settings.DEBUG and settings.EMAIL_BACKEND in {
                'django.core.mail.backends.console.EmailBackend',
                'django.core.mail.backends.dummy.EmailBackend',
                'django.core.mail.backends.filebased.EmailBackend',
            }:
                raise RuntimeError('A real email delivery backend is required in production')
            if '/guest/manage/' in item.body:
                from .models import GuestAccessLink
                access = GuestAccessLink.objects.filter(reservation_id=item.reservation_id, revoked_at__isnull=True).first()
                if not access:
                    item.status = 'skipped'
                    item.last_error = ''
                    item.save(update_fields=['status', 'last_error'])
                    return item.status
                # Retried messages must use the current token after reissue.
                item.body = re.sub(r'(?<=/guest/manage/)[A-Za-z0-9_-]+(?=/)', access.token, item.body)
            if send_mail(item.subject, item.body, None, [item.recipient], fail_silently=False) != 1:
                raise RuntimeError('Email backend did not accept the message')
        except Exception:
            # SMTP exceptions can contain credentials or message contents;
            # neither is stored or rendered in the staff delivery screen.
            logger.warning('Reservation notification %s could not be delivered', item.pk)
            item.status = 'failed'
            item.last_error = 'Delivery failed. Check SMTP settings or retry later.'
            item.next_attempt_at = now + timedelta(minutes=min(60, 5 * (2 ** min(item.attempts - 1, 4))))
        else:
            item.status = 'sent'
            item.sent_at = now
            item.last_error = ''
        item.save(update_fields=['status', 'attempts', 'last_attempt_at', 'next_attempt_at', 'sent_at', 'last_error', 'body'])
        return item.status


def guest_delivery_delayed(reservation):
    return reservation.delivery_notifications.filter(kind__endswith='_guest', status='failed').exists()


def supersede_request_notifications(reservation):
    reservation.delivery_notifications.filter(kind__startswith='request_', status__in=['pending', 'failed']).update(status='skipped', last_error='')


def queue_request_received(request, reservation):
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.urls import reverse
    from .guest_requests_v126 import _guest_context, _hut
    context = _guest_context(request, reservation)
    queue_notification(reservation, 'request_guest', 'Reservation request received — awaiting approval',
                       render_to_string('bookings/email_request_received_v126.txt', context), reservation.email)
    hut = _hut(reservation)
    recipients = set(hut.managers.exclude(email='').values_list('email', flat=True)) if hut else set()
    if settings.BOOKING_NOTIFY_EMAIL:
        recipients.add(settings.BOOKING_NOTIFY_EMAIL)
    recipients.discard(reservation.email)
    body = (f'New reservation request awaiting your approval.\n\nHut: {context["hut_name"]}\n'
            f'Guest: {reservation.name}\nArrival: {reservation.check_in}\nDeparture: {reservation.check_out}\n'
            f'Beds: {reservation.total_beds}\nReference: {reservation.code}\n\n'
            f'Review in SummitDesk: {request.build_absolute_uri(reverse("bookings:approval_dashboard"))}\n')
    for recipient in sorted(recipients):
        queue_notification(reservation, 'request_manager', 'New guest reservation request — action required', body, recipient)
