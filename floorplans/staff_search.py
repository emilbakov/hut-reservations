"""V30 read-only reservation search, restricted to managed huts."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET
from bookings.models import ReservationItem
from .staff_tasks import access

@login_required
@require_GET
def staff_search(request, hut_id):
    hut, manager, cleaner = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers can search reservations.')
    query = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', 'all')
    if status not in ('all', 'pending', 'confirmed', 'cancelled'):
        status = 'all'
    results = []
    if query:
        items = ReservationItem.objects.filter(room__hut=hut).filter(
            Q(reservation__name__icontains=query) |
            Q(reservation__code__icontains=query) |
            Q(reservation__email__icontains=query)
        )
        if status != 'all':
            items = items.filter(reservation__status=status)
        items = items.select_related('reservation', 'room').order_by('-reservation__check_in', '-pk')
        seen = {}
        for item in items[:251]:
            reservation = item.reservation
            if reservation.pk not in seen:
                if len(seen) >= 50:
                    break
                seen[reservation.pk] = {'reservation': reservation, 'rooms': []}
            if item.room.name not in seen[reservation.pk]['rooms']:
                seen[reservation.pk]['rooms'].append(item.room.name)
        results = list(seen.values())
    return render(request, 'floorplans/staff_search.html', {
        'hut': hut, 'query': query, 'status': status, 'results': results,
    })
