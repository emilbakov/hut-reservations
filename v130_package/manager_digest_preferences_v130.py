"""Authenticated manager preferences for the v129 daily email digest.

Preferences apply to the signed-in manager only. No guest data is exposed.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Hut, ManagerDigestPreference, ManagerRequestDigestLog


@login_required
@require_http_methods(['GET', 'POST'])
def manager_digest_preferences(request):
    # v129 digests are addressed to users assigned to active huts, regardless
    # of is_staff. Match that scope so every recipient can opt out.
    assigned = Hut.objects.filter(is_active=True, managers=request.user).exists()
    if not (request.user.is_active and (assigned or request.user.is_superuser)):
        raise PermissionDenied('Only active hut managers can edit email reminders.')

    if request.method == 'POST':
        if request.POST.get('action') != 'save':
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest('Invalid reminder preferences action.')
        for key in ('enabled', 'urgent_only'):
            if request.POST.get(key, '') not in ('', 'on'):
                from django.http import HttpResponseBadRequest
                return HttpResponseBadRequest('Invalid reminder preference value.')
        enabled = request.POST.get('enabled') == 'on'
        urgent_only = request.POST.get('urgent_only') == 'on'
        # Serialize against v129's user-row lock while it is sending a digest.
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            ManagerDigestPreference.objects.update_or_create(
                manager_id=request.user.pk,
                defaults={'enabled': enabled, 'urgent_only': urgent_only},
            )
        messages.success(request, 'Email reminder preferences saved.')
        return redirect('bookings:manager_digest_preferences')

    preference = ManagerDigestPreference.objects.filter(manager=request.user).first()
    history = (ManagerRequestDigestLog.objects.filter(manager=request.user)
               .order_by('-digest_date', '-sent_at')[:10])
    return render(request, 'bookings/manager_digest_preferences_v130.html', {
        'digest_enabled': preference.enabled if preference else True,
        'urgent_only': preference.urgent_only if preference else False,
        'history': history,
        'assigned_huts': Hut.objects.filter(is_active=True, managers=request.user).count(),
    })
