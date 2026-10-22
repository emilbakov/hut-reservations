"""V32 manager-only, hut-scoped reservation audit timeline with filters."""
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
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
    qs = ReservationHistoryEvent.objects.filter(hut=hut, reservation_code=code)
    kinds = list(qs.order_by().values_list('kind', flat=True).distinct())
    selected_kind = request.GET.get('kind', '').strip()
    if selected_kind:
        if selected_kind not in kinds:
            return HttpResponseBadRequest('Invalid event type')
        qs = qs.filter(kind=selected_kind)
    selected_actor = request.GET.get('actor', '').strip()
    if selected_actor:
        if not selected_actor.isdecimal():
            return HttpResponseBadRequest('Invalid actor')
        qs = qs.filter(actor_id=int(selected_actor))
    start = request.GET.get('from', '').strip()
    end = request.GET.get('to', '').strip()
    try:
        if start:
            qs = qs.filter(created_at__date__gte=date.fromisoformat(start))
        if end:
            qs = qs.filter(created_at__date__lte=date.fromisoformat(end))
    except ValueError:
        return HttpResponseBadRequest('Invalid date')
    actors = (ReservationHistoryEvent.objects.filter(hut=hut, reservation_code=code, actor__isnull=False)
              .order_by('actor__username').values('actor_id', 'actor__username').distinct())
    events = qs.select_related('actor')[:200]
    return render(request, 'floorplans/staff_history.html', {
        'hut': hut, 'reservation': reservation, 'events': events, 'kinds': sorted(kinds),
        'actors': actors, 'selected_kind': selected_kind, 'selected_actor': selected_actor,
        'start': start, 'end': end,
    })
