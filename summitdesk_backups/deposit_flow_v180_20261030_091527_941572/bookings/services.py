
"""Availability and booking logic for the multi-hut reservation system."""

from collections import defaultdict
from datetime import timedelta
from numbers import Integral

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import BedClosure, Reservation, ReservationItem, Room


class NotAvailable(Exception):
    """Raised when requested beds are no longer available."""

    def __init__(self, shortages):
        self.shortages = shortages
        super().__init__(
            ", ".join(
                f"{room}: {left} left"
                for room, left in shortages.items()
            )
        )


def free_beds(rooms, check_in, check_out, exclude=None):
    """
    Return available beds for every night of the requested stay.

    check_out is exclusive.
    """

    items = ReservationItem.objects.filter(
        room__in=rooms,
        reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lt=check_out,
        reservation__check_out__gt=check_in,
    ).select_related("reservation")

    if exclude is not None:
        items = items.exclude(reservation=exclude)

    booked = defaultdict(lambda: defaultdict(int))

    for item in items:
        night = max(item.reservation.check_in, check_in)
        last = min(item.reservation.check_out, check_out)

        while night < last:
            booked[item.room_id][night] += item.beds
            night += timedelta(days=1)

    # Maintenance closures reduce physical capacity on each night, not merely
    # the number of unassigned beds. Preserve the original quantity booking model.
    room_list = list(rooms)
    closures = BedClosure.objects.filter(
        bed__room__in=room_list, start__lt=check_out, end__gt=check_in,
    ).values_list('bed__room_id', 'bed_id', 'start', 'end')
    blocked = defaultdict(lambda: defaultdict(set))
    for room_id, bed_id, start, end in closures:
        night = max(start, check_in)
        last = min(end, check_out)
        while night < last:
            blocked[room_id][night].add(bed_id)
            night += timedelta(days=1)
    result = {}
    for room in room_list:
        available = room.capacity
        night = check_in
        while night < check_out:
            available = min(available, room.capacity - booked[room.pk][night] - len(blocked[room.pk][night]))
            night += timedelta(days=1)
        result[room.pk] = max(available, 0)
    return result


def lock_rooms(room_ids):
    """Lock rooms in a stable order to prevent concurrent overbooking."""

    return list(
        Room.objects.select_for_update()
        .filter(pk__in=room_ids)
        .order_by("pk")
    )


def validate_single_hut(rooms):
    """
    Ensure all selected rooms belong to exactly one hut.

    Returns the hut ID.
    """
    hut_ids = {room.hut_id for room in rooms}

    if not rooms or None in hut_ids or len(hut_ids) != 1:
        raise ValidationError(
            "All selected rooms must belong to the same hut."
        )

    return next(iter(hut_ids))


@transaction.atomic
def create_reservation(
    *,
    check_in,
    check_out,
    beds_by_room,
    status=None,
    **guest,
):
    """Validate availability and create a reservation atomically."""

    today = timezone.localdate()

    if (
        not check_in
        or not check_out
        or check_in < today
        or check_out <= check_in
        or check_in > today + timedelta(
            days=settings.BOOKING_MAX_DAYS_AHEAD
        )
        or (check_out - check_in).days > settings.BOOKING_MAX_NIGHTS
    ):
        raise ValidationError(
            "Invalid booking dates or stay duration."
        )

    if status is not None and status not in Reservation.HOLDING:
        raise ValidationError(
            "New reservations must hold beds."
        )

    if any(
        not isinstance(beds, Integral)
        or isinstance(beds, bool)
        or beds < 0
        for beds in beds_by_room.values()
    ):
        raise ValidationError(
            "Bed quantities must be non-negative whole numbers."
        )

    beds_by_room = {
        int(pk): beds
        for pk, beds in beds_by_room.items()
        if beds
    }

    if not beds_by_room:
        raise ValueError("No beds requested.")

    rooms = [
        room
        for room in lock_rooms(beds_by_room)
        if room.is_active
    ]

    if len(rooms) != len(beds_by_room):
        raise NotAvailable({})

    validate_single_hut(rooms)

    free = free_beds(
        rooms,
        check_in,
        check_out,
    )

    shortages = {
        room: free[room.pk]
        for room in rooms
        if beds_by_room[room.pk] > free[room.pk]
    }

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

    # Individual saves emit post_save signals for reservation audit history.
    for room in rooms:
        ReservationItem.objects.create(
            reservation=reservation,
            room=room,
            beds=beds_by_room[room.pk],
            price_per_night=room.price_per_night,
        )

    return reservation


def expire_pending():
    """Cancel expired pending reservations."""

    cutoff = timezone.now() - timedelta(
        minutes=settings.BOOKING_PENDING_MINUTES
    )

    # QuerySet.update() bypasses signals. Save each expired reservation so
    # automatic cancellations appear in the reservation audit history.
    candidate_ids = list(
        Reservation.objects.filter(
            status=Reservation.Status.PENDING,
            guest_request=False,
            created__lt=cutoff,
        ).values_list("pk", flat=True)
    )
    cancelled_count = 0
    for reservation_id in candidate_ids:
        with transaction.atomic():
            reservation = (
                Reservation.objects.select_for_update()
                .filter(
                    pk=reservation_id,
                    status=Reservation.Status.PENDING,
                    guest_request=False,
                    created__lt=cutoff,
                )
                .first()
            )
            if reservation is None:
                continue
            reservation.status = Reservation.Status.CANCELLED
            reservation.save(update_fields=["status"])
            cancelled_count += 1

    return cancelled_count


@transaction.atomic
def modify_reservation(
    *,
    code,
    check_in,
    check_out,
    beds_by_room,
):
    """Modify a reservation without losing the original on failure."""

    reservation = (
        Reservation.objects.select_for_update()
        .get(code=code)
    )

    if reservation.status not in Reservation.HOLDING:
        raise ValidationError(
            "Cancelled reservations cannot be modified."
        )

    today = timezone.localdate()

    if (
        not check_in
        or not check_out
        or check_in < today
        or check_out <= check_in
        or check_in > today + timedelta(
            days=settings.BOOKING_MAX_DAYS_AHEAD
        )
        or (check_out - check_in).days > settings.BOOKING_MAX_NIGHTS
    ):
        raise ValidationError(
            "Invalid booking dates or stay duration."
        )

    if any(
        not isinstance(value, Integral)
        or isinstance(value, bool)
        or value < 0
        for value in beds_by_room.values()
    ):
        raise ValidationError(
            "Bed quantities must be non-negative whole numbers."
        )

    beds_by_room = {
        int(pk): beds
        for pk, beds in beds_by_room.items()
        if beds
    }

    if not beds_by_room:
        raise ValidationError(
            "Choose at least one bed."
        )

    existing_items = list(
        reservation.items.select_related("room").order_by("pk")
    )
    old_room_ids = [item.room_id for item in existing_items]

    rooms = lock_rooms(
        set(old_room_ids) | set(beds_by_room)
    )

    chosen = [
        room
        for room in rooms
        if room.pk in beds_by_room and room.is_active
    ]

    if len(chosen) != len(beds_by_room):
        raise NotAvailable({})

    chosen_hut_id = validate_single_hut(chosen)

    # Keep existing reservations in their original hut.
    original_hut_ids = {
        room.hut_id
        for room in rooms
        if room.pk in old_room_ids
    }

    if (
        len(original_hut_ids) != 1
        or chosen_hut_id not in original_hut_ids
    ):
        raise ValidationError(
            "A reservation cannot be moved to another hut."
        )

    free = free_beds(
        chosen,
        check_in,
        check_out,
        exclude=reservation,
    )

    shortages = {
        room: free[room.pk]
        for room in chosen
        if beds_by_room[room.pk] > free[room.pk]
    }

    if shortages:
        raise NotAvailable(shortages)

    dates_changed = (
        reservation.check_in != check_in
        or reservation.check_out != check_out
    )
    reservation.check_in = check_in
    reservation.check_out = check_out

    reservation.full_clean()
    if dates_changed:
        reservation.save(update_fields=["check_in", "check_out"])

    # Preserve unchanged allocation rows and their related records. Changes
    # to individual rows trigger the existing ReservationItem audit signals.
    existing_by_room = {item.room_id: item for item in existing_items}

    for item in existing_items:
        if item.room_id not in beds_by_room:
            item.delete()

    for room in chosen:
        requested_beds = beds_by_room[room.pk]
        item = existing_by_room.get(room.pk)
        if item is None:
            ReservationItem.objects.create(
                reservation=reservation,
                room=room,
                beds=requested_beds,
                price_per_night=room.price_per_night,
            )
        elif item.beds != requested_beds:
            item.beds = requested_beds
            item.save(update_fields=["beds"])

    return reservation
