"""V31 automatic, actor-neutral audit of model changes.

Signal handlers do not guess which user initiated a change. An actor may be
explicitly supplied to log_event by future views.
"""
from django.apps import apps
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from bookings.models import Reservation, ReservationItem
from .reservation_history import ReservationHistoryEvent
from .audit_actor import current_actor
from datetime import date, datetime
from decimal import Decimal


SENSITIVE = {'email', 'phone', 'notes', 'name'}

def _safe(value):
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)

def _changes(old, instance, fields):
    result = {}
    for field in fields:
        before, after = old.get(field), getattr(instance, field)
        if before != after:
            result[field] = {'before': '[redacted]' if field in SENSITIVE and before is not None else _safe(before),
                             'after': '[redacted]' if field in SENSITIVE and after is not None else _safe(after)}
    return result

def log_event(reservation, hut, kind, description, actor=None, changes=None):
    return ReservationHistoryEvent.objects.create(
        hut=hut, reservation=reservation, reservation_code=reservation.code,
        kind=kind, description=str(description)[:500], actor=actor, changes=changes or {},
    )


def _huts(reservation):
    return list(reservation.items.values_list('room__hut_id', flat=True).distinct())


def _record(reservation, kind, description, hut_ids=None, changes=None):
    for hut_id in (hut_ids if hut_ids is not None else _huts(reservation)):
        ReservationHistoryEvent.objects.create(
            hut_id=hut_id, reservation=reservation, reservation_code=reservation.code,
            kind=kind, description=str(description)[:500],
            actor=current_actor(), changes=changes or {},
        )


@receiver(pre_save, sender=Reservation, dispatch_uid='v31_reservation_before')
def reservation_before(sender, instance, **kwargs):
    instance._v31_previous = None
    if instance.pk:
        instance._v31_previous = sender.objects.filter(pk=instance.pk).values(
            'name', 'email', 'phone', 'notes', 'check_in', 'check_out', 'status'
        ).first()


@receiver(post_save, sender=Reservation, dispatch_uid='v31_reservation_after')
def reservation_after(sender, instance, created, **kwargs):
    # On initial creation the reservation usually has no room items yet.
    # ReservationItem creation below records the booking for each hut.
    if created:
        return
    old = getattr(instance, '_v31_previous', None)
    if old is None:
        return
    changes = _changes(old, instance, old.keys())
    if not changes:
        return
    kind = 'cancelled' if old['status'] != 'cancelled' and instance.status == 'cancelled' else 'updated'
    _record(instance, kind, 'Reservation updated: ' + ', '.join(changes), changes=changes)


@receiver(pre_save, sender=ReservationItem, dispatch_uid='v31_item_before')
def item_before(sender, instance, **kwargs):
    instance._v31_previous = None
    if instance.pk:
        instance._v31_previous = sender.objects.filter(pk=instance.pk).values(
            'room_id', 'beds', 'price_per_night', 'reservation_id'
        ).first()


@receiver(post_save, sender=ReservationItem, dispatch_uid='v31_item_after')
def item_after(sender, instance, created, **kwargs):
    old = getattr(instance, '_v31_previous', None)
    if created:
        _record(instance.reservation, 'created', f'Room reservation added: room #{instance.room_id}, {instance.beds} bed place(s)', [instance.room.hut_id], {'room_id': {'before': None, 'after': instance.room_id}, 'beds': {'before': None, 'after': instance.beds}})
    elif old:
        changes = _changes(old, instance, ('room_id', 'beds', 'price_per_night'))
        if changes:
            hut_ids = {instance.room.hut_id}
            if old['room_id'] != instance.room_id:
                Room = apps.get_model('bookings', 'Room')
                old_hut = Room.objects.filter(pk=old['room_id']).values_list('hut_id', flat=True).first()
                if old_hut:
                    hut_ids.add(old_hut)
            kind = 'transfer' if 'room_id' in changes else 'updated'
            _record(instance.reservation, kind, 'Room allocation changed: ' + ', '.join(changes), hut_ids, changes=changes)


@receiver(pre_delete, sender=ReservationItem, dispatch_uid='v31_item_deleted')
def item_deleted(sender, instance, **kwargs):
    # Do not block cascading deletion if the reservation is already gone.
    if Reservation.objects.filter(pk=instance.reservation_id).exists():
        _record(instance.reservation, 'updated', f'Room allocation removed: room #{instance.room_id}', [instance.room.hut_id])


def register_optional_signals():
    """Record actual check-in/out transitions when GuestStay exposes these fields."""
    try:
        GuestStay = apps.get_model('bookings', 'GuestStay')
    except LookupError:
        return
    names = {field.name for field in GuestStay._meta.fields}
    if not {'reservation', 'checked_in_at', 'checked_out_at'}.issubset(names):
        return

    def before(sender, instance, **kwargs):
        instance._v31_stay_previous = None
        if instance.pk:
            instance._v31_stay_previous = sender.objects.filter(pk=instance.pk).values('checked_in_at', 'checked_out_at').first()

    def after(sender, instance, created, **kwargs):
        old = getattr(instance, '_v31_stay_previous', None) or {}
        if instance.checked_in_at and not old.get('checked_in_at'):
            _record(instance.reservation, 'check_in', 'Guest checked in')
        if instance.checked_out_at and not old.get('checked_out_at'):
            _record(instance.reservation, 'check_out', 'Guest checked out')

    pre_save.connect(before, sender=GuestStay, weak=False, dispatch_uid='v31_stay_before')
    post_save.connect(after, sender=GuestStay, weak=False, dispatch_uid='v31_stay_after')
