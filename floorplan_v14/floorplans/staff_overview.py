"""V14 read-only hut operations overview. No migrations required."""
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from bookings.models import Room, ReservationItem
from .bed_management import permitted_hut


@staff_member_required
@require_GET
def staff_overview(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    horizon = today + timedelta(days=7)
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('position', 'pk'))
    capacity = sum(r.capacity for r in rooms)
    items = list(ReservationItem.objects.filter(
        room__hut=hut, room__is_active=True,
        reservation__status__in=('confirmed', 'pending'),
    ).filter(Q(reservation__check_in__lt=horizon, reservation__check_out__gt=today)
             | Q(reservation__check_out=today))
        .select_related('reservation', 'room')
        .order_by('reservation__check_in', 'reservation__name', 'pk'))

    occupied = sum(i.beds for i in items if i.reservation.check_in <= today < i.reservation.check_out)
    pending = sum(i.beds for i in items if i.reservation.status == 'pending' and i.reservation.check_in <= today < i.reservation.check_out)
    arrivals = [i for i in items if i.reservation.check_in == today]
    departures = [i for i in items if i.reservation.check_out == today]
    upcoming = [i for i in items if today < i.reservation.check_in < horizon]
    continuing = [i for i in items if i.reservation.check_in < today and i.reservation.check_out > tomorrow]

    # Room-level quantities, not physical bed assignments. Departure is exclusive.
    days = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        booked = sum(i.beds for i in items if i.reservation.check_in <= day < i.reservation.check_out)
        days.append({'date': day, 'booked': booked,
                     'percentage': min(100, round(booked * 100 / capacity)) if capacity else 0,
                     'over': booked > capacity})

    return render(request, 'floorplans/staff_overview.html', {
        'hut': hut, 'today': today, 'capacity': capacity, 'occupied': occupied,
        'occupancy_pct': round(100 * occupied / capacity) if capacity else None,
        'pending': pending, 'arrivals': arrivals, 'departures': departures,
        'upcoming': upcoming[:12], 'continuing_count': sum(i.beds for i in continuing),
        'arrival_beds': sum(i.beds for i in arrivals),
        'departure_beds': sum(i.beds for i in departures),
        'room_count': len(rooms), 'days': days,
    })
