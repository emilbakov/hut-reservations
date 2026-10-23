from .timeline_helpers_v113 import build_bars
"""Accessible, staff-only room-by-room weekly drag and drop timeline."""
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import Reservation, ReservationItem, Room
from .views import permitted_hut_selection

@staff_member_required
@require_GET
def calendar_timeline(request):
    try:
        huts, selected, slug = permitted_hut_selection(request)
    except PermissionDenied:
        raise Http404 from None
    try:
        start = date.fromisoformat(request.GET.get('start', str(timezone.localdate())))
        if not 2000 <= start.year <= 2100: raise ValueError
    except (ValueError, TypeError):
        raise Http404
    days = [start + timedelta(days=i) for i in range(7)]
    end = start + timedelta(days=7)
    rooms = Room.objects.filter(hut__in=huts).select_related('hut').order_by('hut__name', 'position', 'pk')
    if selected: rooms = rooms.filter(hut=selected)
    room_list = list(rooms)
    items = ReservationItem.objects.filter(room__in=room_list,
        reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lt=end, reservation__check_out__gt=start).select_related('reservation', 'room')
    slots = {(room.pk, day): [] for room in room_list for day in days}
    for item in items:
        for day in days:
            if item.reservation.check_in <= day < item.reservation.check_out:
                slots[item.room_id, day].append(item)
    rows = []
    for room in room_list:
        cells = []
        for day in days:
            booked = slots[room.pk, day]
            cells.append({'day': day, 'items': booked,
                          'free': room.capacity - sum(i.beds for i in booked)})
        # V113_TIMELINE_LAYOUT: booking bars span the nights occupied.
        room_items = [item for item in items if item.room_id == room.pk]
        bars = build_bars(room_items, start, end)
        track_count = max((bar['track'] for bar in bars), default=1)
        rows.append({'room': room, 'cells': cells, 'bars': bars,
                     'track_count': track_count, 'grid_end': track_count + 1})
    return render(request, 'bookings/calendar_timeline.html', {
        'rows': rows, 'days': days, 'start': start, 'today': timezone.localdate(),
        'last_day': days[-1], 'booking_count': sum(len(row['bars']) for row in rows),
        'prev': start - timedelta(days=7), 'next': end,
        'huts': huts, 'selected_slug': slug, 'selected_hut': selected,
    })
