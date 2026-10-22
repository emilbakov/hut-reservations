"""V31 hut-scoped reservation timeline (read only)."""
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from bookings.models import Reservation, ReservationItem
from .staff_tasks import access
from .reservation_history import ReservationHistoryEvent

@login_required
@require_GET
def staff_history(request, hut_id, code):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers may view reservation history.')
    reservation = get_object_or_404(Reservation.objects.filter(items__room__hut=hut).distinct(), code=code)
    if ReservationItem.objects.filter(reservation=reservation).exclude(room__hut=hut).exists():
        raise Http404('Reservation spans multiple huts')
    events = ReservationHistoryEvent.objects.filter(hut=hut, reservation_code=code).select_related('actor')[:200]
    return render(request, 'floorplans/staff_history.html', {'hut': hut, 'reservation': reservation, 'events': events})
