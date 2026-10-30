"""Whole-unit inventory and snapshot pricing; beds retains the guest quantity."""
from django.conf import settings
from django.core.exceptions import ValidationError


def whole_units():
    return getattr(settings, 'BOOKING_UNIT', 'room') == 'room'


def default_pricing_unit():
    return 'room' if whole_units() else 'bed'


def remaining(capacity, occupied, blocked=0):
    if whole_units():
        return 0 if occupied or blocked else capacity
    return max(0, capacity - occupied - blocked)


def guard_item(item):
    if not whole_units() or not item.reservation_id or not item.room_id:
        return
    from .models import Reservation, Room
    reservation = Reservation.objects.select_for_update().get(pk=item.reservation_id)
    room = Room.objects.select_for_update().get(pk=item.room_id)
    if item.beds < 1 or item.beds > room.capacity:
        raise ValidationError('Guest count exceeds the capacity of this room or apartment.')
    if reservation.status in Reservation.HOLDING:
        from .services import free_beds
        if free_beds([room], reservation.check_in, reservation.check_out, exclude=reservation)[room.pk] < item.beds:
            raise ValidationError('This room or apartment is already reserved or unavailable for these dates.')


def guard_reservation(reservation):
    if not whole_units() or not reservation.pk or reservation.status not in reservation.HOLDING:
        return
    from .models import Reservation, Room
    previous = Reservation.objects.select_for_update().filter(pk=reservation.pk).values('check_in', 'check_out', 'status').first()
    if previous and all(previous[name] == getattr(reservation, name) for name in previous):
        return
    rooms = list(Room.objects.select_for_update().filter(items__reservation=reservation).order_by('pk'))
    if rooms:
        from .services import free_beds
        available = free_beds(rooms, reservation.check_in, reservation.check_out, exclude=reservation)
        if any(available[room.pk] == 0 for room in rooms):
            raise ValidationError('One of these rooms or apartments is already reserved or unavailable for these dates.')
