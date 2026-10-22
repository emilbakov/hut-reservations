"""Call only when a GuestStay changes from not checked out to checked out.

Room-level bookings without BedAssignment have no physical bed identity and are
intentionally not auto-marked dirty.
"""
from django.db import transaction
from bookings.models import BedAssignment, Bed
from .housekeeping_models import BedHousekeeping
from .housekeeping_events import BedCleaningEvent


def mark_checkout_beds_dirty(reservation, actor=None):
    """Return count of uniquely assigned physical beds marked dirty."""
    with transaction.atomic():
        bed_ids = list(BedAssignment.objects.filter(item__reservation=reservation)
                       .values_list('bed_id', flat=True).distinct())
        if not bed_ids:
            return 0
        beds = list(Bed.objects.select_for_update().filter(pk__in=bed_ids).order_by('pk'))
        for bed in beds:
            BedHousekeeping.objects.update_or_create(
                bed=bed, defaults={'state': 'needs_cleaning', 'updated_by': actor,
                                   'note': 'Checkout: %s' % reservation.code})
            BedCleaningEvent.objects.create(
                bed=bed, action='checkout', actor=actor, reservation=reservation,
                note='Automatically marked dirty on recorded checkout')
        return len(beds)
