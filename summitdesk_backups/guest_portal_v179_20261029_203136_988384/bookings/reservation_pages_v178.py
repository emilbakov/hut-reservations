"""A private-link guide for the bare /r/ URL; no booking lookup or mutation."""
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@never_cache
@require_safe
def reservation_entry(request):
    return render(request, 'bookings/private_link_v145.html', {'reservation_entry': True})
