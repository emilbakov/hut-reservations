"""Daily manager-only summary of pending public guest reservation requests.

Only active hut assignments are considered; a reservation spanning multiple
huts is deliberately excluded because the approval queue cannot approve it
as a single-hut request. No guest details or guest access links are emailed.
"""
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Hut, ManagerRequestDigestLog, Reservation


class DigestConfigurationError(ValueError):
    pass


def validated_base_url(value):
    """Require an explicit trusted HTTPS origin for clickable staff links."""
    value = (value or '').strip()
    if not value:
        raise DigestConfigurationError(
            'Set SUMMITDESK_BASE_URL to your real HTTPS site URL (for example https://hut.example.com).'
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise DigestConfigurationError('Invalid control character in SUMMITDESK_BASE_URL.')
    parsed = urlsplit(value)
    if (not parsed.netloc or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise DigestConfigurationError('SUMMITDESK_BASE_URL must be a site origin without a path or credentials.')
    if parsed.scheme != 'https' and not (settings.DEBUG and parsed.scheme == 'http'):
        raise DigestConfigurationError('SUMMITDESK_BASE_URL must use HTTPS outside development.')
    try:
        parsed.port  # Reject invalid port syntax.
    except ValueError as exc:
        raise DigestConfigurationError('Invalid SUMMITDESK_BASE_URL port.') from exc
    return value.rstrip('/')


def collect_pending_summaries(manager, *, now=None, today=None):
    """Return per-hut counts without crossing manager authorization boundaries."""
    now = now if now is not None else timezone.now()
    today = today if today is not None else timezone.localdate(now)
    huts = list(Hut.objects.filter(is_active=True, managers=manager).order_by('name', 'pk'))
    if not huts:
        return []
    allowed = {hut.pk: hut for hut in huts}
    summaries = {
        hut.pk: {'hut': hut, 'pending': 0, 'waiting24': 0, 'arrival48': 0}
        for hut in huts
    }
    # Explicitly verify *all* items belong to one assigned hut. This prevents
    # a reservation with items in another hut leaking into this email.
    candidates = (Reservation.objects.filter(
        guest_request=True,
        status=Reservation.Status.PENDING,
        items__room__hut_id__in=allowed,
    ).distinct().prefetch_related('items__room'))
    old_cutoff = now - timedelta(hours=24)
    arrival_cutoff = today + timedelta(days=2)
    for reservation in candidates:
        item_huts = {item.room.hut_id for item in reservation.items.all()}
        if len(item_huts) != 1:
            continue
        hut_id = next(iter(item_huts))
        if hut_id not in allowed:
            continue
        bucket = summaries[hut_id]
        bucket['pending'] += 1
        if reservation.created <= old_cutoff:
            bucket['waiting24'] += 1
        if reservation.check_in <= arrival_cutoff:
            bucket['arrival48'] += 1
    return [summary for summary in summaries.values() if summary['pending']]


def render_digest(summaries, *, base_url='', today=None):
    """Generate a concise text-only email; link only to authorized hut views."""
    today = today if today is not None else timezone.localdate()
    total = sum(item['pending'] for item in summaries)
    waiting = sum(item['waiting24'] for item in summaries)
    arrival = sum(item['arrival48'] for item in summaries)
    subject = f'SummitDesk — {total} pending guest reservation request' + ('s' if total != 1 else '')
    lines = [
        f'SummitDesk manager summary — {today:%d %B %Y}',
        '',
        f'Pending guest requests: {total}',
        f'Waiting over 24 hours: {waiting}',
        f'Arrivals due within 2 days or overdue: {arrival}',
        '',
    ]
    for item in summaries:
        hut = item['hut']
        path = reverse('bookings:approval_dashboard') + '?' + urlencode({
            'hut': hut.slug, 'status': 'pending',
        })
        lines.extend([
            f'Hut: {hut.name}',
            f'  Pending: {item["pending"]}',
            f'  Waiting over 24 hours: {item["waiting24"]}',
            f'  Arrival due / overdue: {item["arrival48"]}',
            f'  Review: {base_url}{path}',
            '',
        ])
    lines.extend([
        'Review and approve or decline requests in SummitDesk.',
        'This message does not change any reservation or release any beds.',
        '',
        'You are receiving this summary because you are assigned as a hut manager.',
    ])
    return subject, '\n'.join(lines)


def digest_manager(manager_id, *, send=False, base_url='', now=None):
    """Send at most one digest per manager per local calendar date.

    A user-row lock serializes concurrent invocations on PostgreSQL. The sent
    record is written only after the mail backend confirms one delivery.
    Failure rolls back, allowing a later retry. SMTP delivery itself cannot
    be atomically committed with the database; rare failures after delivery
    but before DB commit may require manual reconciliation.
    """
    now = now if now is not None else timezone.now()
    today = timezone.localdate(now)
    User = get_user_model()
    if not send:
        manager = User.objects.get(pk=manager_id)
        if not manager.is_active or not manager.email or not manager.email.strip():
            return 'ineligible', 0
        if ManagerRequestDigestLog.objects.filter(manager=manager, digest_date=today).exists():
            return 'duplicate', 0
        summaries = collect_pending_summaries(manager, now=now, today=today)
        return ('preview', sum(item['pending'] for item in summaries)) if summaries else ('empty', 0)

    with transaction.atomic():
        manager = User.objects.select_for_update().get(pk=manager_id)
        if not manager.is_active or not manager.email or not manager.email.strip():
            return 'ineligible', 0
        if ManagerRequestDigestLog.objects.filter(manager=manager, digest_date=today).exists():
            return 'duplicate', 0
        summaries = collect_pending_summaries(manager, now=now, today=today)
        if not summaries:
            return 'empty', 0
        total = sum(item['pending'] for item in summaries)
        subject, body = render_digest(summaries, base_url=base_url, today=today)
        sent_count = send_mail(subject, body, None, [manager.email.strip()], fail_silently=False)
        if sent_count != 1:
            raise RuntimeError('Mail backend did not confirm delivery; no digest log was saved.')
        ManagerRequestDigestLog.objects.create(
            manager=manager,
            digest_date=today,
            recipient=manager.email.strip(),
            hut_count=len(summaries),
            request_count=total,
        )
        return 'sent', total
