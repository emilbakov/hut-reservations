"""Public homepage selection and the server-side single-hut booking policy."""
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.translation import gettext as _

from .models import Hut, PublicWebsiteSettings, Room


def main_hut(request=None, *, locked=False):
    if not locked and request is not None and hasattr(request, '_main_hut_v153'):
        return request._main_hut_v153
    if locked:
        # Caller is in the public submission transaction. Serialize a selector
        # change with the last policy check before creating the reservation.
        profile, _created = PublicWebsiteSettings.objects.get_or_create(pk=1)
        profile = PublicWebsiteSettings.objects.select_for_update().get(pk=profile.pk)
    elif request is not None:
        from .public_profile_v149 import profile_for
        profile = profile_for(request)
    else:
        profile = PublicWebsiteSettings.objects.filter(pk=1).first() or PublicWebsiteSettings()
    if profile.main_hut_id:
        if locked:
            selected = Hut.objects.select_for_update().filter(pk=profile.main_hut_id, is_active=True).first()
        else:
            selected = profile.main_hut if profile.main_hut.is_active else None
    else:
        # Never guess between multiple huts. Deployment prompts for the choice.
        candidates = list(Hut.objects.filter(is_active=True).order_by('pk')[:2])
        selected = candidates[0] if len(candidates) == 1 else None
        if selected and locked:
            selected = Hut.objects.select_for_update().filter(pk=selected.pk, is_active=True).first()
    if not locked and request is not None:
        request._main_hut_v153 = selected
    return selected


def public_booking_allowed(request, hut, *, locked=False):
    selected = main_hut(request, locked=locked)
    return selected is not None and hut is not None and hut.is_active and selected.pk == hut.pk


def require_public_booking(request, hut):
    if not public_booking_allowed(request, hut, locked=True):
        raise PermissionDenied(_('Online reservation requests are not available for this hut.'))


def hut_information_page(request, hut, *, status=200):
    from .booking_flow_v150 import hut_information
    return render(request, 'bookings/hut_information_v153.html', {
        'hut': hut, 'hut_info': hut_information(hut),
        'public_rooms': Room.objects.filter(hut=hut, is_active=True).order_by('position', 'name'),
    }, status=status)
