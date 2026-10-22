"""Guest authorization and idempotent public submissions."""
import json
import secrets
from datetime import timedelta

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import GuestAccessLink, PublicBookingSubmission, Reservation

SALT = 'summitdesk.public-booking.v145'


def browser_secret(request):
    secret = request.session.get('sd145_browser')
    if not secret:
        secret = secrets.token_urlsafe(32)
        request.session['sd145_browser'] = secret
    return secret


def submission_token(request, hut):
    return signing.dumps({'browser': browser_secret(request), 'hut': hut.pk if hut else None,
                          'nonce': secrets.token_urlsafe(24)}, salt=SALT)


def submission_identity(request, hut):
    values = {key: request.POST.get(key, '').strip() for key in request.POST
              if key in ('check_in', 'check_out', 'name', 'email', 'phone', 'notes') or key.startswith('room_')}
    fingerprint = salted_hmac(SALT, json.dumps(values, sort_keys=True), algorithm='sha256').hexdigest()
    raw = request.POST.get('submission_token', '')
    secret = browser_secret(request)
    if raw:
        try:
            token = signing.loads(raw, salt=SALT, max_age=86400)
            if token['browser'] != secret or token['hut'] != (hut.pk if hut else None):
                raise signing.BadSignature()
            nonce = token['nonce']
        except (signing.BadSignature, KeyError, TypeError):
            raise ValueError('This booking form has expired. Reload the page and try again.') from None
        lifetime = timedelta(days=1)
    else:
        # Compatibility for existing integrations: exact retries in the same
        # browser remain safe even when an old form has no hidden token.
        nonce = 'legacy:' + fingerprint
        lifetime = timedelta(minutes=10)
    key = salted_hmac(SALT, secret + ':' + str(hut.pk if hut else None) + ':' + nonce, algorithm='sha256').hexdigest()
    return key, fingerprint, lifetime


def completed_submission(identity):
    key, fingerprint, _ = identity
    item = PublicBookingSubmission.objects.select_related('reservation').filter(key=key, expires_at__gt=timezone.now()).first()
    if item and item.payload_hash != fingerprint:
        raise ValueError('This form already submitted different details. Reload before making another request.')
    return item.reservation if item else None


@transaction.atomic
def create_public_submission(identity, create):
    key, fingerprint, lifetime = identity
    item, _ = PublicBookingSubmission.objects.get_or_create(key=key, defaults={
        'payload_hash': fingerprint, 'expires_at': timezone.now() + lifetime})
    item = PublicBookingSubmission.objects.select_for_update().get(pk=item.pk)
    if item.expires_at > timezone.now():
        if item.payload_hash != fingerprint:
            raise ValueError('This form already submitted different details. Reload before making another request.')
        if item.reservation_id:
            return item.reservation
    reservation = create()
    item.reservation = reservation
    item.payload_hash = fingerprint
    item.expires_at = timezone.now() + lifetime
    item.save(update_fields=['reservation', 'payload_hash', 'expires_at'])
    return reservation


def grant_guest_access(request, reservation, *, token=None):
    link, _ = GuestAccessLink.objects.get_or_create(reservation=reservation)
    if link.revoked_at or (token is not None and link.token != token):
        return
    grants = dict(request.session.get('sd145_guest_grants', {}))
    grants[str(reservation.pk)] = link.token
    request.session['sd145_guest_grants'] = dict(list(grants.items())[-20:])


def can_manage(request, reservation):
    if not request.user.is_authenticated or not request.user.is_active:
        return False
    from .views import manageable_reservations
    try:
        return manageable_reservations(request.user).filter(pk=reservation.pk).exists()
    except PermissionDenied:
        return False


def has_guest_access(request, reservation):
    token = request.session.get('sd145_guest_grants', {}).get(str(reservation.pk))
    return bool(token and GuestAccessLink.objects.filter(reservation=reservation, token=token, revoked_at__isnull=True).exists())


def require_reservation_access(request, reservation):
    staff = can_manage(request, reservation)
    if not staff and not has_guest_access(request, reservation):
        raise Http404('Private reservation access is required.')
    return staff


def portal_url(reservation, request=None):
    from django.urls import reverse
    link = GuestAccessLink.objects.filter(reservation=reservation, revoked_at__isnull=True).first()
    if not link:
        raise Http404('Private reservation access is unavailable.')
    path = reverse('bookings:guest_self_service', args=[link.token])
    return request.build_absolute_uri(path) if request else path
