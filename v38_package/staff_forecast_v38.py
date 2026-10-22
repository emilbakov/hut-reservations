"""SummitDesk v38: read-only seven-night hut operations forecast."""
from collections import defaultdict
from datetime import timedelta
from django.db.models import Count
from bookings.models import Room, ReservationItem, BedClosure
from .housekeeping_tasks import HousekeepingTask


def build_forecast(hut, today):
    """Return seven days starting today; checkout dates are exclusive."""
    end = today + timedelta(days=7)
    rooms = list(Room.objects.filter(hut=hut, is_active=True).only('id', 'capacity'))
    ids = [r.pk for r in rooms]
    capacity = sum(r.capacity for r in rooms)
    occupied = defaultdict(int)
    pending = defaultdict(int)
    arrivals = defaultdict(int)
    departures = defaultdict(int)
    for item in ReservationItem.objects.filter(
        room_id__in=ids,
        reservation__status__in=('confirmed', 'pending'),
        reservation__check_in__lt=end,
        reservation__check_out__gte=today,
    ).select_related('reservation'):
        r = item.reservation
        # Arrival/departure counts are reserved bed places, not distinct guests.
        if today <= r.check_in < end:
            arrivals[r.check_in] += item.beds if r.status == 'confirmed' else 0
        if today <= r.check_out < end:
            departures[r.check_out] += item.beds if r.status == 'confirmed' else 0
        day = max(today, r.check_in)
        last = min(end, r.check_out)
        target = occupied if r.status == 'confirmed' else pending
        while day < last:
            target[day] += item.beds
            day += timedelta(days=1)

    blocked = defaultdict(set)
    for room_id, bed_id, start, finish in BedClosure.objects.filter(
        bed__room_id__in=ids, start__lt=end, end__gt=today
    ).values_list('bed__room_id', 'bed_id', 'start', 'end'):
        day = max(today, start)
        while day < min(end, finish):
            blocked[day].add(bed_id)
            day += timedelta(days=1)

    task_counts = dict(HousekeepingTask.objects.filter(
        bed__room__hut=hut, day__gte=today, day__lt=end
    ).values('day').annotate(total=Count('pk')).values_list('day', 'total'))

    result = []
    for n in range(7):
        day = today + timedelta(days=n)
        closed = len(blocked[day])
        available_capacity = max(0, capacity - closed)
        booked = occupied[day]
        held = pending[day]
        result.append({
            'day': day, 'capacity': capacity, 'closed': closed,
            'available_capacity': available_capacity,
            'occupied': booked, 'pending': held,
            'free': max(0, available_capacity - booked - held),
            'arrivals': arrivals[day], 'departures': departures[day],
            'tasks': task_counts.get(day, 0),
            'over_capacity': booked + held > available_capacity,
        })
    return result
