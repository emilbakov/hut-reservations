"""V11 staff dashboard and 14-day reservation calendar. Read-only."""
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from bookings.models import Room, ReservationItem
from .bed_management import permitted_hut

@staff_member_required
@require_GET
def staff_calendar(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    raw = request.GET.get('start', '')
    try:
        start = date.fromisoformat(raw) if raw else today
    except ValueError:
        start = today
    # Bound requests so arbitrary dates cannot trigger unreasonable queries.
    if abs((start - today).days) > 3660:
        start = today
    end = start + timedelta(days=14)
    days = [start + timedelta(days=i) for i in range(14)]
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('position', 'pk'))
    items = list(ReservationItem.objects.filter(
        room__in=rooms, reservation__status__in=['pending', 'confirmed'],
        reservation__check_in__lt=end, reservation__check_out__gt=start,
    ).select_related('reservation', 'room').order_by('reservation__check_in', 'pk')) if rooms else []
    by_room = {r.pk: [] for r in rooms}
    for item in items:
        by_room[item.room_id].append(item)
    room_rows = []
    booked_per_day = [0] * 14
    total_capacity = sum(r.capacity for r in rooms)
    arrivals = 0
    departures = 0
    pending = 0
    for room in rooms:
        occupancy = [0] * 14
        events = []
        lane_ends = []
        for item in by_room[room.pk]:
            reservation = item.reservation
            left = max(reservation.check_in, start)
            right = min(reservation.check_out, end)
            if right <= left:
                continue
            begin = (left - start).days
            finish = (right - start).days
            for i in range(begin, finish):
                occupancy[i] += item.beds
                booked_per_day[i] += item.beds
            lane = next((i for i, used_until in enumerate(lane_ends) if used_until <= begin), None)
            if lane is None:
                lane = len(lane_ends)
                lane_ends.append(finish)
            else:
                lane_ends[lane] = finish
            events.append({
                'name': reservation.name, 'code': reservation.code,
                'status': reservation.status, 'beds': item.beds,
                'check_in': reservation.check_in, 'check_out': reservation.check_out,
                'column': begin + 1, 'span': finish - begin,
                'top': 5 + lane * 31,
            })
            if reservation.check_in == today:
                arrivals += item.beds
            if reservation.check_out == today:
                departures += item.beds
            if reservation.status == 'pending' and reservation.check_in <= today < reservation.check_out:
                pending += item.beds
        room_rows.append({
            'room': room, 'events': events,
            'cells': [{'day': d, 'booked': n, 'over': n > room.capacity} for d, n in zip(days, occupancy)],
            'height': max(54, 12 + 31 * len(lane_ends)),
        })
    today_index = (today - start).days
    occupied_today = booked_per_day[today_index] if 0 <= today_index < 14 else None
    occupancy_pct = round(100 * occupied_today / total_capacity) if occupied_today is not None and total_capacity else None
    return render(request, 'floorplans/staff_calendar.html', {
        'hut': hut, 'days': days, 'rows': room_rows, 'start': start,
        'previous': (start - timedelta(days=14)).isoformat(),
        'next': end.isoformat(), 'today': today, 'capacity': total_capacity,
        'occupied_today': occupied_today, 'occupancy_pct': occupancy_pct,
        'arrivals': arrivals, 'departures': departures, 'pending': pending,
        'room_count': len(rooms),
    })
