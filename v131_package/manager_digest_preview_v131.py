"""Read-only, private preview of the logged-in manager's next digest.

Never sends mail, updates preferences, or consumes the daily send log.
Counts follow the v129 single-hut authorization rules exactly.
"""
import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .manager_digest_v129 import (
    DigestConfigurationError, collect_pending_summaries, render_digest,
    validated_base_url,
)
from .models import Hut, ManagerDigestPreference, ManagerRequestDigestLog


@login_required
@require_GET
@never_cache
def manager_digest_preview(request):
    """Show only this manager's own digest eligibility and text preview."""
    user = request.user
    assigned = Hut.objects.filter(is_active=True, managers=user).exists()
    if not (user.is_active and (assigned or user.is_superuser)):
        raise PermissionDenied('Only active hut managers can preview reminders.')

    now = timezone.now()
    today = timezone.localdate(now)
    preference = ManagerDigestPreference.objects.filter(manager=user).first()
    enabled = preference.enabled if preference else True
    urgent_only = preference.urgent_only if preference else False
    already_sent = ManagerRequestDigestLog.objects.filter(
        manager=user, digest_date=today,
    ).exists()
    summaries = collect_pending_summaries(user, now=now, today=today)
    total = sum(item['pending'] for item in summaries)
    waiting = sum(item['waiting24'] for item in summaries)
    arriving = sum(item['arrival48'] for item in summaries)

    # Match the order of the v130 digest_manager checks, without sending.
    if not user.email or not user.email.strip():
        status = 'missing_email'
    elif not enabled:
        status = 'disabled'
    elif already_sent:
        status = 'already_sent'
    elif not summaries:
        status = 'empty'
    elif urgent_only and not (waiting or arriving):
        status = 'not_urgent'
    else:
        status = 'ready'

    # This page never relies on the SMTP configuration and never sends mail.
    # Prefer the same configured origin as the timer. The web worker may not
    # have that environment variable, so use a validated request origin only
    # for the on-screen preview; otherwise show relative links with a notice.
    configured_url = os.environ.get('SUMMITDESK_BASE_URL', '')
    link_notice = ''
    try:
        base_url = validated_base_url(configured_url or request.build_absolute_uri('/'))
        if not configured_url:
            link_notice = (
                'Preview links use this website address. The scheduled email '
                'uses the URL configured for the daily digest service.'
            )
    except DigestConfigurationError:
        base_url = ''
        link_notice = (
            'Links are relative in this preview. Configure a trusted HTTPS '
            'SUMMITDESK_BASE_URL for the scheduled email service.'
        )

    subject, body = render_digest(summaries, base_url=base_url, today=today) if summaries else ('', '')
    return render(request, 'bookings/manager_digest_preview_v131.html', {
        'digest_status': status,
        'digest_enabled': enabled,
        'urgent_only': urgent_only,
        'total': total,
        'waiting24': waiting,
        'arrival48': arriving,
        'summaries': summaries,
        'email_subject': subject,
        'email_body': body,
        'link_notice': link_notice,
        'today': today,
    })
