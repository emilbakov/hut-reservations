"""Role-aware landing URL for staff and non-admin cleaners."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from bookings.models import Hut
from .hut_staff import HutCleaner

@login_required
@require_GET
def staff_home(request):
    if request.user.is_superuser:
        hut = Hut.objects.filter(is_active=True).order_by('pk').first()
    else:
        managed = Hut.objects.filter(is_active=True, managers=request.user).order_by('pk').first()
        membership = HutCleaner.objects.filter(user=request.user, hut__is_active=True).order_by('hut_id').first()
        hut = managed or (membership.hut if membership else None)
    if hut is None:
        return HttpResponseForbidden('No hut access. Ask a manager to add you to a hut.')
    return redirect('floorplans:staff_hub', hut_id=hut.pk)
