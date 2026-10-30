from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_delete
from .models import PaymentTransaction, Reservation, ReservationItem


def payment_recorded(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from .deposit_flow_v180 import reconcile_payment
        reconcile_payment(instance.reservation_id)


def protect_hold_items(sender, instance, **kwargs):
    if Reservation.objects.filter(pk=instance.reservation_id, status='pending',
                                   deposit_request__state__in=['awaiting', 'review']).exists():
        raise ValidationError('Withdraw the deposit request before removing reserved rooms.')


def register():
    post_save.connect(payment_recorded, sender=PaymentTransaction, dispatch_uid='deposit_payment_v180')
    pre_delete.connect(protect_hold_items, sender=ReservationItem, dispatch_uid='deposit_items_v180')
