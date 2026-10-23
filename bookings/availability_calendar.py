"""Read-only monthly occupancy; checkout day does not consume a bed."""
from calendar import Calendar, monthrange
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import BedClosure, Reservation, ReservationItem, Room
from .views import manageable_reservations, permitted_hut_selection


def build_month(first, rooms, *, visible_ids=None):
    """Return room/day availability, counting closures and all holding items."""
    last_day = monthrange(first.year, first.month)[1]
    end = date(first.year, first.month, last_day) + timedelta(days=1)
    room_list = list(rooms)
    room_ids = [room.pk for room in room_list]
    items = (ReservationItem.objects.filter(
        room_id__in=room_ids,
        reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lt=end,
        reservation__check_out__gt=first,
    ).select_related('reservation', 'room').order_by('reservation__check_in', 'pk'))
    occupancy = {room.pk: {} for room in room_list}
    for item in items:
        booking = item.reservation
        day = max(first, booking.check_in)
        stop = min(end, booking.check_out)
        while day < stop:
            occupancy[item.room_id].setdefault(day, []).append(item)
            day += timedelta(days=1)
    rows = []
    closures = list(BedClosure.objects.filter(bed__room_id__in=room_ids, start__lt=end, end__gt=first)
                    .values_list('bed__room_id', 'bed_id', 'start', 'end'))
    for room in room_list:
        cells = []
        for number in range(1, last_day + 1):
            day = first.replace(day=number)
            active = occupancy[room.pk].get(day, [])
            booked = sum(item.beds for item in active)
            blocked = len({bed for room_id, bed, start, stop in closures if room_id == room.pk and start <= day < stop})
            available = max(room.capacity - booked - blocked, 0) if room.is_active else 0
            cells.append({
                'day': day, 'booked': booked, 'available': available,
                'overbooked': booked + blocked > room.capacity,
                'blocked': blocked, 'full': not room.is_active or booked + blocked >= room.capacity,
                'reservations': [
                    {'code': item.reservation.code, 'guest': item.reservation.name,
                     'beds': item.beds, 'status': item.reservation.status}
                    for item in active if visible_ids is None or item.reservation_id in visible_ids
                ],
            })
        rows.append({'room': room, 'days': cells})
    return rows


@staff_member_required
@require_GET
def availability_calendar(request):
    try:
        huts, selected_hut, selected_slug = permitted_hut_selection(request)
    except PermissionDenied:
        raise Http404 from None
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not 2000 <= year <= 2100:
            raise ValueError
        first = date(year, month, 1)
    except (ValueError, TypeError, OverflowError):
        first = today.replace(day=1)
    # A manager is always scoped to one assigned hut; superusers can view all.
    rooms = Room.objects.filter(hut__in=huts).select_related('hut').order_by('hut__name', 'position', 'pk')
    if selected_hut:
        rooms = rooms.filter(hut=selected_hut)
    requested_room = request.GET.get('room', '').strip()
    if requested_room:
        if not requested_room.isdecimal():
            raise Http404
        rooms = rooms.filter(pk=int(requested_room))
        if not rooms.exists():
            raise Http404
    visible_ids = set(manageable_reservations(request.user).filter(check_in__lt=first+timedelta(days=monthrange(first.year, first.month)[1]), check_out__gt=first).values_list('pk', flat=True))
    rows = build_month(first, rooms, visible_ids=visible_ids)
    prev_month = first - timedelta(days=1)
    next_month = first.replace(day=monthrange(first.year, first.month)[1]) + timedelta(days=1)
    days = [first.replace(day=n) for n in range(1, monthrange(first.year, first.month)[1] + 1)]
    total_beds = sum(row['room'].capacity for row in rows)
    occupancy_days = sum(cell['booked'] for row in rows for cell in row['days'])
    warnings = sum(cell['overbooked'] for row in rows for cell in row['days'])
    return render(request, 'bookings/availability_calendar.html', {
        'huts': huts, 'selected_hut': selected_hut, 'selected_slug': selected_slug,
        'rows': rows, 'days': days, 'first': first, 'prev_month': prev_month,
        'next_month': next_month, 'room_filter': requested_room,
        'total_beds': total_beds, 'occupied_bed_nights': occupancy_days,
        'overbooked_room_nights': warnings,
    })
