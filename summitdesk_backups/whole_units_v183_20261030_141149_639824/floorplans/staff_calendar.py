"""V11 staff dashboard and 14-day reservation calendar. Read-only."""
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET
from bookings.models import Room, ReservationItem, BedClosure, Bed, BedAssignment
from .bed_management import permitted_hut

@staff_member_required
@require_GET
def staff_calendar(request, hut_id):
    hut = permitted_hut(request, hut_id)
    # v138: selected-hut monthly overview by default; original timeline is preserved.
    if request.GET.get('view') != 'timeline':
        from .property_calendar_v138 import render_property_month
        return render_property_month(request, hut)
    today = timezone.localdate()
    raw = request.GET.get('start', '')
    try:
        start = date.fromisoformat(raw) if raw else today
    except ValueError:
        start = today
    # Bound requests so arbitrary dates cannot trigger unreasonable queries.
    if abs((start - today).days) > 3660:
        start = today
    try:
        window = int(request.GET.get('days', '14'))
    except (ValueError, TypeError):
        window = 14
    if window not in (7, 14, 28):
        window = 14
    search = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', 'all')
    if status not in ('all', 'pending', 'confirmed'):
        status = 'all'
    try:
        room_filter = int(request.GET.get('room', '0'))
    except (ValueError, TypeError):
        room_filter = 0
    end = start + timedelta(days=window)
    days = [start + timedelta(days=i) for i in range(window)]
    all_rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('position', 'pk'))
    rooms = [r for r in all_rooms if not room_filter or r.pk == room_filter]
    items = list(ReservationItem.objects.filter(
        room__in=rooms, reservation__status__in=['pending', 'confirmed'],
        reservation__check_in__lt=end, reservation__check_out__gt=start,
    ).select_related('reservation', 'room').order_by('reservation__check_in', 'pk')) if rooms else []
    if status != 'all':
        items = [i for i in items if i.reservation.status == status]
    if search:
        term = search.casefold()
        items = [i for i in items if term in i.reservation.name.casefold() or term in str(i.reservation.code).casefold()]
    # Heatmap is independent of search/status filters and reflects all holding bookings.
    availability_items = list(ReservationItem.objects.filter(
        room__in=rooms, reservation__status__in=['pending', 'confirmed'],
        reservation__check_in__lt=end, reservation__check_out__gt=start,
    ).select_related('reservation')) if rooms else []
    demand_by_room = {r.pk: [0] * window for r in rooms}
    for item in availability_items:
        first = max(0, (item.reservation.check_in - start).days)
        last = min(window, (item.reservation.check_out - start).days)
        for idx in range(first, last):
            demand_by_room[item.room_id][idx] += item.beds
    # One physical bed may have multiple adjacent closure records; count it once/night.
    closed_by_room = {r.pk: [set() for _ in range(window)] for r in rooms}
    closures = BedClosure.objects.filter(
        bed__room__in=rooms, start__lt=end, end__gt=start,
    ).values_list('bed__room_id', 'bed_id', 'start', 'end') if rooms else []
    for room_id, bed_id, closure_start, closure_end in closures:
        for idx in range(max(0, (closure_start - start).days),
                         min(window, (closure_end - start).days)):
            closed_by_room[room_id][idx].add(bed_id)
    # Numbered-bed occupancy is derived from explicit assignments, not room demand.
    physical_beds = list(Bed.objects.filter(room__in=rooms).order_by('room_id', 'number', 'pk'))
    bed_ids = [b.pk for b in physical_beds]
    beds_by_room = {r.pk: [] for r in rooms}
    for bed in physical_beds:
        beds_by_room[bed.room_id].append(bed)
    assignments = list(BedAssignment.objects.filter(
        bed_id__in=bed_ids, item__reservation__status__in=['pending', 'confirmed'],
        item__reservation__check_in__lt=end, item__reservation__check_out__gt=start,
    ).select_related('item__reservation')) if bed_ids else []
    assignments_by_bed = {}
    for assignment in assignments:
        assignments_by_bed.setdefault(assignment.bed_id, []).append(assignment)
    closures_by_bed = {}
    for bed_id, close_start, close_end in (BedClosure.objects.filter(
        bed_id__in=bed_ids, start__lt=end, end__gt=start,
    ).values_list('bed_id', 'start', 'end') if bed_ids else []):
        closures_by_bed.setdefault(bed_id, []).append((close_start, close_end))
    by_room = {r.pk: [] for r in rooms}
    for item in items:
        by_room[item.room_id].append(item)
    room_rows = []
    booked_per_day = [0] * window
    total_capacity = sum(r.capacity for r in rooms)
    arrivals = 0
    departures = 0
    pending = 0
    for room in rooms:
        occupancy = [0] * window
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
                'top': 5 + lane * 31, 'room_name': room.name,
            })
            if reservation.check_in == today:
                arrivals += item.beds
            if reservation.check_out == today:
                departures += item.beds
            if reservation.status == 'pending' and reservation.check_in <= today < reservation.check_out:
                pending += item.beds
        heat_cells = []
        for idx, day in enumerate(days):
            demand = demand_by_room[room.pk][idx]
            closed = len(closed_by_room[room.pk][idx])
            remaining = room.capacity - demand - closed
            # Room-level quantities may not correspond to assigned physical beds.
            # This is a conservative capacity indicator, not a per-bed guarantee.
            heat_cells.append({
                'day': day, 'booked': demand, 'closed': closed,
                'free': max(0, remaining), 'over': remaining < 0,
                'full': remaining == 0, 'low': 0 < remaining <= max(1, room.capacity // 4),
            })
        bed_rows = []
        for bed in beds_by_room[room.pk]:
            cells = []
            for day in days:
                assigned = [a for a in assignments_by_bed.get(bed.pk, [])
                            if a.item.reservation.check_in <= day < a.item.reservation.check_out]
                closed = any(a <= day < b for a, b in closures_by_bed.get(bed.pk, []))
                state = 'conflict' if len(assigned) > 1 or (assigned and closed) else ('closed' if closed else ('assigned' if assigned else 'unassigned'))
                cells.append({'state': state, 'guest': ', '.join(a.item.reservation.name for a in assigned),
                              'code': str(assigned[0].item.reservation.code) if len(assigned) == 1 else '',
                              'date': day})
            bed_rows.append({'bed': bed, 'cells': cells})
        room_rows.append({
            'bed_rows': bed_rows,
            'room': room, 'events': events,
            'cells': heat_cells,
            'height': max(54, 12 + 31 * len(lane_ends)),
        })
    # Today's KPIs must not change with calendar filters or date navigation.
    today_items = ReservationItem.objects.filter(
        room__hut=hut, room__is_active=True,
        reservation__status__in=['pending', 'confirmed'],
    ).select_related('reservation')
    today_items = list(today_items.filter(Q(reservation__check_in__lte=today, reservation__check_out__gt=today) | Q(reservation__check_in=today) | Q(reservation__check_out=today)))
    occupied_today = sum(i.beds for i in today_items if i.reservation.check_in <= today < i.reservation.check_out)
    total_capacity = sum(r.capacity for r in all_rooms)
    arrivals = sum(i.beds for i in today_items if i.reservation.check_in == today)
    departures = sum(i.beds for i in today_items if i.reservation.check_out == today)
    pending = sum(i.beds for i in today_items if i.reservation.status == 'pending' and i.reservation.check_in <= today < i.reservation.check_out)
    occupancy_pct = round(100 * occupied_today / total_capacity) if total_capacity else None
    return render(request, 'floorplans/staff_calendar.html', {
        'hut': hut, 'days': days, 'rows': room_rows, 'start': start,
        'previous': (start - timedelta(days=window)).isoformat(),
        'next': end.isoformat(), 'today': today, 'capacity': total_capacity,
        'occupied_today': occupied_today, 'occupancy_pct': occupancy_pct,
        'arrivals': arrivals, 'departures': departures, 'pending': pending,
        'room_count': len(rooms), 'all_rooms': all_rooms, 'room_filter': room_filter,
        'window': window, 'search': search, 'status_filter': status,
    })
