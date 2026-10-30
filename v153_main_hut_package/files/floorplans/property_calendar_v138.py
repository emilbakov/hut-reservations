"""v138 selected-hut monthly availability. Read-only; existing booking services own writes."""
from calendar import monthrange
from datetime import date, timedelta

from django.http import Http404
from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

from bookings.models import BedClosure, Reservation, ReservationItem, Room
from bookings.views import manageable_reservations


def month_rows(first, rooms, visible_ids=None):
    """Room-night availability including distinct maintenance-closed beds.

    Reservation details are only included when the reservation is manageable.
    visible_ids=None is intended for unit tests only; live view always passes a set.
    """
    rooms = list(rooms)
    end = first + timedelta(days=monthrange(first.year, first.month)[1])
    days = [first + timedelta(days=n) for n in range((end - first).days)]
    ids = [room.pk for room in rooms]
    bookings = list(ReservationItem.objects.filter(
        room_id__in=ids, reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lt=end, reservation__check_out__gt=first,
    ).select_related('reservation').order_by('reservation__check_in', 'pk'))
    occupancy = {room.pk: {} for room in rooms}
    for item in bookings:
        day = max(first, item.reservation.check_in)
        until = min(end, item.reservation.check_out)
        while day < until:
            occupancy[item.room_id].setdefault(day, []).append(item)
            day += timedelta(days=1)
    closed = {room.pk: {} for room in rooms}
    for room_id, bed_id, begin, finish in BedClosure.objects.filter(
        bed__room_id__in=ids, start__lt=end, end__gt=first,
    ).values_list('bed__room_id', 'bed_id', 'start', 'end'):
        day = max(first, begin)
        until = min(end, finish)
        while day < until:
            closed[room_id].setdefault(day, set()).add(bed_id)
            day += timedelta(days=1)
    rows = []
    for room in rooms:
        cells = []
        for day in days:
            active = occupancy[room.pk].get(day, [])
            booked = sum(item.beds for item in active)
            blocked = len(closed[room.pk].get(day, ()))
            remaining = room.capacity - booked - blocked
            available = max(0, remaining) if room.is_active else 0
            cells.append({
                'day': day, 'booked': booked, 'blocked': blocked,
                'available': available, 'full': available == 0,
                'overbooked': remaining < 0, 'inactive': not room.is_active,
                'reservations': [
                    {'code': item.reservation.code, 'guest': item.reservation.name,
                     'beds': item.beds, 'status': item.reservation.status,
                     'check_in': item.reservation.check_in, 'check_out': item.reservation.check_out}
                    for item in active
                    if visible_ids is None or item.reservation_id in visible_ids
                ],
            })
        rows.append({'room': room, 'days': cells})
    return rows


def render_property_month(request, hut, quickstay_form=None, quickstay_initial=None, quickstay_arrival=None):
    """Called only after staff_member_required and permitted_hut authorization."""
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if year < 2000 or year > 2100:
            raise ValueError
        first = date(year, month, 1)
    except (ValueError, TypeError, OverflowError):
        first = today.replace(day=1)
    if quickstay_arrival and 2000 <= quickstay_arrival.year <= 2100:
        first = quickstay_arrival.replace(day=1)
    # The property URL fixes the hut; do not allow hut/room query parameters to expand scope.
    rooms = list(Room.objects.filter(hut=hut).order_by('position', 'pk'))
    item_ids = ReservationItem.objects.filter(room__in=rooms).values_list('reservation_id', flat=True)
    visible_ids = set(manageable_reservations(request.user).filter(
        pk__in=item_ids,
    ).values_list('pk', flat=True))
    # Mixed-hut reservations are not editable in this property's reservation view.
    cross_hut_ids = set(ReservationItem.objects.filter(
        reservation_id__in=item_ids,
    ).exclude(room__hut=hut).values_list('reservation_id', flat=True))
    visible_ids.difference_update(cross_hut_ids)
    rows = month_rows(first, rooms, visible_ids=visible_ids)
    # Show 14 days beyond month-end so a full permitted stay can be selected
    # entirely by clicking the calendar, even when it crosses into next month.
    next_first = first + timedelta(days=monthrange(first.year, first.month)[1])
    following_rows = month_rows(next_first, rooms, visible_ids=visible_ids)
    for row, following in zip(rows, following_rows):
        row['days'].extend(following['days'][:14])
    prev_month = first - timedelta(days=1)
    next_month = first.replace(day=monthrange(first.year, first.month)[1]) + timedelta(days=1)
    return render(request, 'floorplans/property_calendar_v138.html', {
        'hut': hut, 'selected_hut': hut, 'selected_slug': hut.slug,
        'first': first, 'prev_month': prev_month, 'next_month': next_month,
        'days': [first + timedelta(days=n) for n in range(monthrange(first.year, first.month)[1] + 14)],
        'rows': rows, 'today': today, 'currency': settings.BOOKING_CURRENCY,
        'max_nights': settings.BOOKING_MAX_NIGHTS,
        'latest_arrival': today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD),
        'quickstay_form': quickstay_form, 'quickstay_initial': quickstay_initial or {},
        'total_beds': sum(room.capacity for room in rooms if room.is_active),
        'occupied_bed_nights': sum(cell['booked'] for row in rows for cell in row['days']),
        'blocked_bed_nights': sum(cell['blocked'] for row in rows for cell in row['days']),
        'overbooked_room_nights': sum(cell['overbooked'] for row in rows for cell in row['days']),
    })
