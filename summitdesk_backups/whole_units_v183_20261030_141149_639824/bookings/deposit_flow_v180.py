"""Approval -> protected deposit hold -> paid confirmation, or deadline release.

All lifecycle mutations lock the reservation first, then its rooms. Existing
status values remain: awaiting-deposit reservations are still pending holds.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from urllib.parse import urljoin

from django.conf import settings
from django.http import Http404
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import get_language, gettext as _

from .models import (GuestStay, HutDepositPolicy, Reservation, ReservationDecision,
                     ReservationDepositRequest as DepositRequest, ReservationItem)


class DepositTermsError(ValidationError):
    def __init__(self, form):
        self.form = form
        super().__init__(_('Review the deposit amount, deadline and payment instructions.'))


def awaiting(reservation):
    return bool(reservation.deposit_request_id and reservation.deposit_request.state in ('awaiting', 'review')
                and reservation.status == 'pending')


def terms_pending(reservation):
    return bool(getattr(reservation, 'guest_request', False) and reservation.status == 'pending' and
                (not reservation.deposit_request_id or reservation.deposit_request.state == 'withdrawn'))


def unreviewed(qs):
    return qs.filter(status='pending').exclude(deposit_request__state__in=['awaiting', 'review'])


def exclude_elapsed(qs, prefix='reservation__', now=None):
    """Capacity is released at the deadline even before the minute job runs."""
    now = now or timezone.now()
    return qs.exclude(Q(**{prefix+'status': 'pending', prefix+'deposit_request__state': 'awaiting',
                           prefix+'deposit_request__due_at__lte': now}) &
                      ~Q(**{prefix+'guest_stay__checked_in_at__isnull': False,
                            prefix+'guest_stay__checked_out_at__isnull': True}))


def validate_reservation_write(reservation):
    if not reservation.pk:
        if reservation.guest_request and reservation.status == 'confirmed':
            raise ValidationError({'status': _('Create a guest request as pending, then use the approval and deposit workflow.')})
        return
    previous = Reservation.objects.filter(pk=reservation.pk).values(
        'status', 'guest_request', 'deposit_request_id', 'check_in', 'check_out').first()
    if not previous:
        return
    hold = DepositRequest.objects.filter(pk=previous['deposit_request_id']).first() if previous['deposit_request_id'] else None
    if previous['status'] == 'pending' and previous['guest_request'] and reservation.status == 'confirmed':
        current = DepositRequest.objects.filter(pk=reservation.deposit_request_id, reservation_id=reservation.pk).first()
        from .payments import balance
        if not current or current.state not in ('paid', 'waived') or (current.state == 'paid' and balance(reservation)['net'] < current.amount):
            raise ValidationError({'status': _('Approve the guest request and record its required deposit before confirmation.')})
    if hold and hold.state in ('awaiting', 'review') and reservation.deposit_request_id != previous['deposit_request_id']:
        raise ValidationError(_('Withdraw the deposit request before changing the stay or its booking type.'))
    if hold and hold.state in ('awaiting', 'review') and (
        reservation.check_in != previous['check_in'] or reservation.check_out != previous['check_out']
        or reservation.guest_request != previous['guest_request']):
        raise ValidationError(_('Withdraw the deposit request before changing the stay or its booking type.'))
    if reservation.deposit_request_id and not DepositRequest.objects.filter(
            pk=reservation.deposit_request_id, reservation_id=reservation.pk).exists():
        raise ValidationError('Deposit request belongs to another reservation.')


def validate_item_write(item):
    if not item.reservation_id:
        return
    active = Reservation.objects.filter(pk=item.reservation_id, status='pending',
                                        deposit_request__state__in=['awaiting', 'review']).exists()
    if active:
        previous = ReservationItem.objects.filter(pk=item.pk).values('room_id', 'beds', 'price_per_night').first() if item.pk else None
        if previous is None or any(previous[name] != getattr(item, name) for name in previous):
            raise ValidationError(_('Withdraw the deposit request before changing rooms, beds or rates.'))


def close_cancelled_hold(reservation):
    if reservation.deposit_request_id:
        changed = DepositRequest.objects.filter(pk=reservation.deposit_request_id, state__in=['awaiting', 'review']).update(
            state='withdrawn', closed_at=timezone.now(), close_reason='Reservation cancelled by staff.')
        if changed:
            reservation._state.fields_cache.pop('deposit_request', None)


def default_terms(reservation, now=None):
    from .deposits import single_hut_id
    from .models import Hut
    now = now or timezone.now()
    hut = Hut.objects.get(pk=single_hut_id(reservation))
    policy = HutDepositPolicy.objects.filter(hut=hut).first()
    percentage = policy.percentage if policy else 30
    days = policy.due_days if policy else 3
    arrival_end = timezone.make_aware(datetime.combine(reservation.check_in, time(23, 59)))
    day_end = timezone.make_aware(datetime.combine(timezone.localdate(now), time(23, 59)))
    due = min(now + timedelta(days=days) if days else day_end, arrival_end)
    return {'deposit_amount': (Decimal(reservation.total_price)*Decimal(percentage)/100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP),
            'deposit_due_at': timezone.localtime(due).replace(second=0, microsecond=0),
            'instructions_en': hut.payment_instructions_en, 'instructions_bg': hut.payment_instructions_bg}


def guest_link(hold):
    from .reliability_v145 import portal_url
    try:
        path = portal_url(hold.reservation)
    except Http404:
        path = hold.reservation.get_absolute_url()
    return urljoin(hold.origin, path)


def email_origin(hold):
    return SimpleNamespace(build_absolute_uri=lambda path='': urljoin(hold.origin, path))


def queue_hold_email(hold, kind, *, defer_delivery=False):
    from .notifications_v145 import queue_notification
    from .payments import balance
    reservation = hold.reservation
    currency = settings.BOOKING_CURRENCY
    deadline = timezone.localtime(hold.due_at).strftime('%Y-%m-%d %H:%M %z') + ' (' + settings.TIME_ZONE + ')'
    net = balance(reservation)['net']
    remaining = max(hold.amount-net, Decimal('0.00'))
    common = f'Reference / Номер: {reservation.code}\nHut / Хижа: {reservation.items.select_related("room__hut").first().room.hut.name}\n'
    if kind == 'deposit_expired_guest':
        subject = 'Deposit deadline passed / Изтекъл срок за депозит'
        body = ('The deposit deadline passed without the required amount being recorded. The hold has been released and this reservation is cancelled. '
                'Do not send payment for this cancelled booking. Contact the hut to check availability.\n'
                'Срокът за депозита изтече без да е отчетена необходимата сума. Задържаните места са освободени и резервацията е отменена. '
                'Не плащайте по отменената резервация. Свържете се с хижата за свободни места.\n'
                f'Net payments recorded / Отчетени нетни плащания: {net:.2f} {currency}. '
                'Any recorded funds remain in the payment record; refunds require hut review. / Възстановяването на отчетени плащания се разглежда от хижата.\n')
    elif kind == 'deposit_review_guest':
        subject = 'Deposit recorded — hut review / Депозитът е отчетен — преглед от хижата'
        body = ('Your required deposit is recorded, but room availability needs hut review. Your stay is not yet confirmed. '
                'Do not send the deposit again or travel until the hut confirms your stay.\n'
                'Необходимият депозит е отчетен, но наличността на стаите изисква преглед от хижата. Престоят все още не е потвърден. '
                'Не плащайте депозита повторно и не пътувайте преди потвърждение от хижата.\n')
    elif kind == 'deposit_withdrawn_guest':
        subject = 'Deposit request withdrawn / Оттеглена заявка за депозит'
        body = ('The hut withdrew the deposit request. Your booking is awaiting review again; do not pay using the previous terms.\n'
                'Хижата оттегли заявката за депозит. Резервацията отново очаква преглед; не плащайте по предишните условия.\n')
    else:
        reminder = kind == 'deposit_reminder_guest'
        subject = ('Deposit reminder / Напомняне за депозит' if reminder else 'Approved — deposit required / Одобрена заявка — необходим депозит')
        body = ('Your request is approved, but the stay is NOT yet confirmed. Beds are held until the deadline below. '
                'The booking confirms when the hut records the required deposit. An insufficient deposit at the deadline releases the hold.\n'
                'Заявката е одобрена, но престоят все още НЕ е потвърден. Местата се задържат до посочения срок. '
                'Резервацията се потвърждава след отчитане на необходимия депозит. При недостатъчен депозит в срока местата се освобождават.\n'
                f'Deposit required / Необходим депозит: {hold.amount:.2f} {currency}\n'
                f'Already recorded / Вече отчетени: {net:.2f} {currency}\n'
                f'Remaining deposit / Остатък по депозита: {remaining:.2f} {currency}\n'
                f'Deadline / Краен срок: {deadline}\n'
                f'Payment instructions / Указания за плащане:\n{hold.instructions_en or hold.instructions_bg}\n')
        if hold.instructions_bg and hold.instructions_bg != hold.instructions_en:
            body += '\nУказания на български:\n' + hold.instructions_bg + '\n'
        body += f'Use reference / Посочете номер: {reservation.code}\n'
    body += '\n' + common + '\nPrivate status / Личен статус: ' + guest_link(hold) + '\nKeep this link private. / Пазете връзката лична.\n'
    item = queue_notification(reservation, kind, subject, body, reservation.email, event=str(hold.pk), defer_delivery=defer_delivery)
    if kind == 'deposit_review_guest':
        from django.urls import reverse
        hut = reservation.items.select_related('room__hut').first().room.hut
        recipients = set(hut.managers.exclude(email='').values_list('email', flat=True))
        if settings.BOOKING_NOTIFY_EMAIL:
            recipients.add(settings.BOOKING_NOTIFY_EMAIL)
        recipients.discard(reservation.email)
        for recipient in sorted(recipients):
            queue_notification(reservation, 'deposit_review_manager', 'Deposit received — room conflict needs review',
                f'Deposit received for {reservation.code}, but capacity prevented confirmation. '
                'The stay remains held for staff review and will not expire automatically. '
                'Resolve room availability, withdraw the old approval, then approve again using recorded credit.\n' +
                urljoin(hold.origin, reverse('bookings:reservation_payments', args=[reservation.code])),
                recipient, event=str(hold.pk), defer_delivery=defer_delivery)
    return item


def approve_deposit(request, reservation, data):
    """Caller owns reservation and room locks and has checked capacity."""
    from .deposit_forms_v180 import DepositApprovalForm
    from .notifications_v145 import supersede_request_notifications
    from .self_service import issue_guest_link
    if awaiting(reservation):
        raise ValidationError(_('This request is already approved and awaiting its deposit.'))
    if reservation.check_in < timezone.localdate():
        raise ValidationError(_('A past stay cannot start a new deposit hold.'))
    if not reservation.email:
        raise ValidationError(_('Add the guest email before approving a deposit request.'))
    form = DepositApprovalForm(reservation, data)
    if not form.is_valid():
        raise DepositTermsError(form)
    from django.core.exceptions import PermissionDenied
    try:
        issue_guest_link(reservation)  # Does not re-enable revoked access.
    except PermissionDenied:
        raise ValidationError(_('Reissue the guest private link before approving this request.'))
    from .staff_decisions_v152 import supersede_decisions
    supersede_decisions(reservation)
    now = timezone.now()
    amount, due = form.cleaned_data['deposit_amount'], form.cleaned_data['deposit_due_at']
    span = due-now
    hold = DepositRequest.objects.create(reservation=reservation, amount=amount, due_at=due,
        approved_at=now, approved_by=request.user, instructions_en=form.cleaned_data['instructions_en'],
        instructions_bg=form.cleaned_data['instructions_bg'], origin=request.build_absolute_uri('/'),
        state='awaiting' if amount else 'waived', reminder_at=max(now+span/2, due-timedelta(hours=24)),
        reminders_enabled=HutDepositPolicy.objects.filter(hut_id=reservation.items.first().room.hut_id,
                                                          reminders_enabled=False).exists() is False)
    reservation.deposit_request = hold
    reservation.save(update_fields=['deposit_request'])
    supersede_request_notifications(reservation)
    if not amount:
        reservation.status = 'confirmed'
        reservation.save(update_fields=['status'])
        from .views import send_confirmation
        send_confirmation(request, reservation, event=f'deposit:{hold.pk}')
    else:
        if not confirm_if_funded(reservation, hold):
            queue_hold_email(hold, 'deposit_request_guest')
    return hold


def confirm_if_funded(reservation, hold, now=None, *, defer_delivery=False):
    from .payments import balance
    from .staff_decisions_v152 import availability, fingerprint
    from .services import lock_rooms
    now = now or timezone.now()
    if hold.state != 'awaiting' or reservation.status != 'pending':
        return False
    if balance(reservation)['net'] < hold.amount:
        return False
    # A payment recorded under the reservation lock before the deadline wins
    # over a timer waiting for that lock, even if commit happens afterwards.
    if now >= hold.due_at:
        timely = reservation.payment_transactions.filter(created__lt=hold.due_at)
        net_at_deadline = sum((p.amount if p.kind != 'refund' else -p.amount for p in timely), Decimal('0.00'))
        if net_at_deadline < hold.amount:
            return False
    lock_rooms(reservation.items.values_list('room_id', flat=True))
    if not availability(reservation)[1]:
        hold.state, hold.paid_at = 'review', timezone.now()
        hold.net_received_at_confirmation = balance(reservation)['net']
        hold.save(update_fields=['state', 'paid_at', 'net_received_at_confirmation'])
        reservation.deposit_request = hold
        queue_hold_email(hold, 'deposit_review_guest', defer_delivery=defer_delivery)
        return True
    hold.state, hold.paid_at = 'paid', timezone.now()
    hold.net_received_at_confirmation = balance(reservation)['net']
    hold.save(update_fields=['state', 'paid_at', 'net_received_at_confirmation'])
    reservation.deposit_request = hold
    reservation.status = 'confirmed'
    reservation.save(update_fields=['status'])
    ReservationDecision.objects.create(reservation=reservation, actor=None, before='pending', after='confirmed',
        reason='Required deposit recorded; automatic confirmation.', fingerprint=fingerprint(reservation))
    from .views import send_confirmation
    send_confirmation(email_origin(hold), reservation, event=f'deposit:{hold.pk}', defer_delivery=defer_delivery)
    return True


def expire_hold(reservation, hold, now=None, *, defer_delivery=False):
    from .services import lock_rooms
    from .staff_decisions_v152 import fingerprint
    now = now or timezone.now()
    if hold.state != 'awaiting' or reservation.status != 'pending' or hold.due_at > now:
        return False
    if GuestStay.objects.filter(reservation=reservation, checked_in_at__isnull=False,
                                checked_out_at__isnull=True).exists():
        return False
    lock_rooms(reservation.items.values_list('room_id', flat=True))
    hold.state, hold.closed_at = 'expired', now
    hold.close_reason = 'Deposit deadline passed without confirmation.'
    hold.save(update_fields=['state', 'closed_at', 'close_reason'])
    reservation.status = 'cancelled'
    reservation.save(update_fields=['status'])
    ReservationDecision.objects.create(reservation=reservation, actor=None, before='pending', after='cancelled',
        reason=hold.close_reason, fingerprint=fingerprint(reservation))
    queue_hold_email(hold, 'deposit_expired_guest', defer_delivery=defer_delivery)
    return True


@transaction.atomic
def reconcile_payment(reservation_id):
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)
    if not reservation.deposit_request_id:
        return
    hold = DepositRequest.objects.select_for_update().get(pk=reservation.deposit_request_id)
    if not confirm_if_funded(reservation, hold):
        expire_hold(reservation, hold)


def process_holds(*, dry_run=False, expire=True, reminders=True, now=None):
    now = now or timezone.now()
    result = {'expired': 0, 'reminders': 0, 'blocked': 0}
    ids = list(DepositRequest.objects.filter(state='awaiting', reservation__status='pending', reservation__deposit_request_id=F('pk')).values_list('reservation_id', flat=True))
    for pk in ids:
        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().get(pk=pk)
            hold = DepositRequest.objects.select_for_update().get(pk=reservation.deposit_request_id)
            if hold.state != 'awaiting' or reservation.status != 'pending':
                continue
            if not dry_run and confirm_if_funded(reservation, hold, now, defer_delivery=True):
                continue
            if hold.due_at <= now:
                if expire:
                    if dry_run:
                        if not GuestStay.objects.filter(reservation=reservation, checked_in_at__isnull=False, checked_out_at__isnull=True).exists():
                            result['expired'] += 1
                        else:
                            result['blocked'] += 1
                    elif expire_hold(reservation, hold, now, defer_delivery=True):
                        result['expired'] += 1
                    else:
                        result['blocked'] += 1
                continue
            if reminders and hold.reminders_enabled and hold.reminder_at <= now and hold.reminder_queued_at is None:
                result['reminders'] += 1
                if not dry_run:
                    queue_hold_email(hold, 'deposit_reminder_guest', defer_delivery=True)
                    hold.reminder_queued_at = now
                    hold.save(update_fields=['reminder_queued_at'])
    return result


def deposit_context(reservation):
    if not getattr(reservation, 'deposit_request_id', None):
        return None
    from .payments import balance
    hold = reservation.deposit_request
    if hold.state == 'withdrawn' and reservation.status == 'cancelled':
        return None
    net = balance(reservation)['net']
    expired = hold.state == 'expired' or (hold.state == 'awaiting' and hold.due_at <= timezone.now())
    lang = 'bg' if (get_language() or 'en').startswith('bg') else 'en'
    instructions = getattr(hold, 'instructions_'+lang) or hold.instructions_en or hold.instructions_bg
    return {'hold': hold, 'review': hold.state == 'review', 'awaiting': hold.state == 'awaiting' and not expired and reservation.status == 'pending',
            'expired': expired, 'paid': hold.state in ('paid', 'waived') and reservation.status == 'confirmed',
            'net': net, 'remaining': max(hold.amount-net, Decimal('0.00')), 'instructions': instructions,
            'balance': max(Decimal(reservation.total_price)-net, Decimal('0.00')),
            'currency': settings.BOOKING_CURRENCY, 'timezone': settings.TIME_ZONE}
