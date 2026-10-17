"""Availability and booking logic. Everything that decides whether beds are
free lives here, so the public site and the admin follow the same rules."""

from collections import defaultdict
from datetime import timedelta
from numbers import Integral

from django.core.exceptions import ValidationError

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Reservation, ReservationItem, Room


class NotAvailable(Exception):
    """Raised when a request no longer fits. `shortages` maps Room -> beds left."""

    def __init__(self, shortages):
        self.shortages = shortages
        super().__init__(
            ", ".join(f"{room}: {left} left" for room, left in shortages.items())
        )


def free_beds(rooms, check_in, check_out, exclude=None):
    """Return {room.pk: beds free on EVERY night of the stay}.

    check_out is exclusive: a guest leaving on the 10th does not clash with
    one arriving on the 10th. The busiest night of the stay decides the answer.
    """
    items = ReservationItem.objects.filter(
        room__in=rooms,
        reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lt=check_out,
        reservation__check_out__gt=check_in,
    ).select_related("reservation")
    if exclude is not None:
        items = items.exclude(reservation=exclude)

    booked = defaultdict(lambda: defaultdict(int))  # room pk -> night -> beds
    for item in items:
        night = max(item.reservation.check_in, check_in)
        last = min(item.reservation.check_out, check_out)
        while night < last:
            booked[item.room_id][night] += item.beds
            night += timedelta(days=1)

    return {
        room.pk: max(room.capacity - max(booked[room.pk].values(), default=0), 0)
        for room in rooms
    }


def lock_rooms(room_ids):
    """Lock the rooms for the rest of the transaction (always in pk order, to
    avoid deadlocks) so concurrent bookings are checked one at a time."""
    return list(Room.objects.select_for_update().filter(pk__in=room_ids).order_by("pk"))


@transaction.atomic
def create_reservation(*, check_in, check_out, beds_by_room, status=None, **guest):
    """Check availability and save the reservation in one locked transaction.

    beds_by_room is {room pk: number of beds}. Raises NotAvailable if any
    room cannot take the request.
    """
    # Validate direct service calls too, not just browser form submissions.
    today = timezone.localdate()
    if (not check_in or not check_out or check_in < today
            or check_out <= check_in
            or check_in > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD)
            or (check_out - check_in).days > settings.BOOKING_MAX_NIGHTS):
        raise ValidationError("Invalid booking dates or stay duration.")
    if status is not None and status not in Reservation.HOLDING:
        raise ValidationError("New reservations must hold beds.")
    if any(not isinstance(beds, Integral) or isinstance(beds, bool) or beds < 0
           for beds in beds_by_room.values()):
        raise ValidationError("Bed quantities must be non-negative whole numbers.")
    beds_by_room = {pk: beds for pk, beds in beds_by_room.items() if beds}
    if not beds_by_room:
        raise ValueError("No beds requested.")

    rooms = [room for room in lock_rooms(beds_by_room) if room.is_active]
    if len(rooms) != len(beds_by_room):
        raise NotAvailable({})

    free = free_beds(rooms, check_in, check_out)
    shortages = {room: free[room.pk] for room in rooms if beds_by_room[room.pk] > free[room.pk]}
    if shortages:
        raise NotAvailable(shortages)

    reservation = Reservation(
        check_in=check_in,
        check_out=check_out,
        status=status or settings.BOOKING_INITIAL_STATUS,
        **guest,
    )
    reservation.full_clean()
    reservation.save()
    ReservationItem.objects.bulk_create(
        ReservationItem(
            reservation=reservation,
            room=room,
            beds=beds_by_room[room.pk],
            price_per_night=room.price_per_night,
        )
        for room in rooms
    )
    return reservation


def expire_pending():
    """Cancel pending reservations older than BOOKING_PENDING_MINUTES."""
    cutoff = timezone.now() - timedelta(minutes=settings.BOOKING_PENDING_MINUTES)
    return Reservation.objects.filter(
        status=Reservation.Status.PENDING, created__lt=cutoff
    ).update(status=Reservation.Status.CANCELLED)


@transaction.atomic
def modify_reservation(*, code, check_in, check_out, beds_by_room):
    """Atomically replace a guest's dates/beds without losing the original on failure."""
    reservation = Reservation.objects.select_for_update().get(code=code)
    if reservation.status not in Reservation.HOLDING:
        raise ValidationError("Cancelled reservations cannot be modified.")
    today = timezone.localdate()
    if (check_in < today or check_out <= check_in
            or check_in > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD)
            or (check_out - check_in).days > settings.BOOKING_MAX_NIGHTS):
        raise ValidationError("Invalid booking dates or stay duration.")
    if any(not isinstance(v, Integral) or isinstance(v, bool) or v < 0 for v in beds_by_room.values()):
        raise ValidationError("Bed quantities must be non-negative whole numbers.")
    beds_by_room = {int(k): v for k, v in beds_by_room.items() if v}
    if not beds_by_room:
        raise ValidationError("Choose at least one bed.")
    old_room_ids = list(reservation.items.values_list("room_id", flat=True))
    # Lock all relevant rooms in stable order, as create_reservation does.
    rooms = lock_rooms(set(old_room_ids) | set(beds_by_room))
    chosen = [r for r in rooms if r.pk in beds_by_room and r.is_active]
    if len(chosen) != len(beds_by_room):
        raise NotAvailable({})
    free = free_beds(chosen, check_in, check_out, exclude=reservation)
    shortages = {r: free[r.pk] for r in chosen if beds_by_room[r.pk] > free[r.pk]}
    if shortages:
        raise NotAvailable(shortages)
    reservation.check_in, reservation.check_out = check_in, check_out
    reservation.full_clean()
    reservation.save(update_fields=["check_in", "check_out"])
    reservation.items.all().delete()
    ReservationItem.objects.bulk_create([
        ReservationItem(reservation=reservation, room=r, beds=beds_by_room[r.pk],
                        price_per_night=r.price_per_night)
        for r in chosen
    ])
    return reservation
