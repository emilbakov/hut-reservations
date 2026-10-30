"""Read-only range availability; no cached inventory or reservation writes."""
from collections import defaultdict
from datetime import timedelta

from .models import BedClosure, Reservation, ReservationItem


def nightly_availability(rooms, start, end):
    """Return {night: {room_id: free}} with two queries for the whole range.

    Mirrors free_beds: checkout is exclusive, holding bookings consume beds,
    overlapping closures for the same physical bed count only once, and each
    room is clamped to zero independently before any aggregation.
    The caller bounds the public booking window and supplies authorized rooms.
    """
    rooms = list(rooms)
    if start >= end or not rooms:
        return {}
    capacities = {room.pk: room.capacity for room in rooms}
    booked = defaultdict(lambda: defaultdict(int))
    blocked = defaultdict(lambda: defaultdict(set))
    items = ReservationItem.objects.filter(
        room_id__in=capacities,
        reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lt=end,
        reservation__check_out__gt=start,
    ).order_by().values_list(
        'room_id', 'beds', 'reservation__check_in', 'reservation__check_out',
    )
    for room_id, beds, arrival, departure in items:
        night = max(start, arrival)
        while night < min(end, departure):
            booked[night][room_id] += beds
            night += timedelta(days=1)
    closures = BedClosure.objects.filter(
        bed__room_id__in=capacities, start__lt=end, end__gt=start,
    ).order_by().values_list('bed__room_id', 'bed_id', 'start', 'end')
    for room_id, bed_id, arrival, departure in closures:
        night = max(start, arrival)
        while night < min(end, departure):
            blocked[night][room_id].add(bed_id)
            night += timedelta(days=1)
    result = {}
    night = start
    while night < end:
        result[night] = {
            room_id: max(0, capacity - booked[night][room_id] - len(blocked[night][room_id]))
            for room_id, capacity in capacities.items()
        }
        night += timedelta(days=1)
    return result
