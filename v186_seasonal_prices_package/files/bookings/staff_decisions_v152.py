"""Capacity-aware staff decisions; all writes retain the existing hut scope."""
import hashlib
import json
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import GuestStay, Reservation, ReservationDecision
from .services import free_beds, lock_rooms

UNDO_WINDOW = timedelta(minutes=5)


def fingerprint(reservation):
    data = [reservation.check_in.isoformat(), reservation.check_out.isoformat(),
            reservation.name, reservation.email, reservation.phone, reservation.notes, reservation.guest_request,
            reservation.staff_history.order_by('-pk').values_list('pk', flat=True).first(),
            list(reservation.items.order_by('pk').values_list('pk', 'room_id', 'beds', 'price_per_night', 'seasonal_rates')),
            reservation.deposit_request_id,
            reservation.deposit_request.state if reservation.deposit_request_id else None,
            reservation.payment_transactions.order_by('-pk').values_list('pk', flat=True).first()]
    return hashlib.sha256(json.dumps(data, default=str, ensure_ascii=False).encode()).hexdigest()


def availability(reservation, *, locked=False):
    items = list(reservation.items.select_related('room__hut'))
    rooms = {item.room_id: item.room for item in items}
    if locked:
        rooms = {room.pk: room for room in lock_rooms(rooms)}
    free = free_beds(list(rooms.values()), reservation.check_in, reservation.check_out, exclude=reservation)
    wanted = {}
    for item in items:
        wanted[item.room_id] = wanted.get(item.room_id, 0) + item.beds
    rows = [{'room': room, 'requested': wanted[pk], 'available': free[pk],
             'remaining': max(0, free[pk] - wanted[pk]),
             'conflict': not room.is_active or free[pk] < wanted[pk]}
            for pk, room in rooms.items()]
    return rows, bool(rows) and not any(row['conflict'] for row in rows)


def decorate_requests(reservations):
    for reservation in reservations:
        hut_ids = {item.room.hut_id for item in reservation.items.all()}
        reservation.last_decision = reservation.staff_decisions.order_by('-pk').first() if reservation.status == 'cancelled' else None
        from .deposit_flow_v180 import awaiting, deposit_context
        reservation.deposit180 = deposit_context(reservation)
        reservation.reviewable_here = reservation.status == 'pending' and not awaiting(reservation) and len(hut_ids) == 1 and None not in hut_ids
        if reservation.reviewable_here and reservation.guest_request:
            from .deposit_forms_v180 import DepositApprovalForm
            reservation.deposit_form = DepositApprovalForm(reservation)
        # A manager never receives names/details belonging to another hut here.
        reservation.capacity_rows, reservation.capacity_ok = availability(reservation) if reservation.reviewable_here else ([], False)
    return reservations


def undo_context(request, scoped):
    decision_id = request.session.get('staff_decision_v152')
    if not isinstance(decision_id, int):
        return None
    decision = (ReservationDecision.objects.select_related('reservation')
            .filter(pk=decision_id, actor=request.user, undone_at__isnull=True,
                    created_at__gte=timezone.now()-UNDO_WINDOW,
                    reservation__in=scoped, before='pending').first())
    if decision and deposit_undo_allowed(decision.reservation) and decision.reservation.status == decision.after and fingerprint(decision.reservation) == decision.fingerprint:
        return decision
    return None


def deposit_undo_allowed(reservation):
    if not reservation.deposit_request_id:
        return True
    hold = reservation.deposit_request
    return hold.state in ('awaiting', 'waived', 'withdrawn') and not reservation.payment_transactions.filter(created__gte=hold.approved_at).exists()


def destination(request):
    route = {'approvals': 'approval_dashboard', 'dashboard': 'dashboard'}.get(request.POST.get('source'), 'manager_reservations')
    url = reverse('bookings:'+route)
    hut = request.POST.get('return_hut', '').strip()[:100]
    return url + ('?' + urlencode({'hut': hut}) if hut else '')


def supersede_decisions(reservation):
    reservation.delivery_notifications.filter(
        kind__in=['confirmation_guest', 'confirmation_manager', 'declined_guest', 'decision_undo_guest'],
        status__in=['pending', 'failed']).update(status='skipped', last_error='')


def decide(request, code):
    from .views import get_locked_manageable_reservation, send_confirmation
    from .guest_requests_v126 import send_guest_request_declined
    action = request.POST.get('action')
    reason = request.POST.get('reason', '').strip()
    if len(reason) > 1000:
        messages.error(request, _('Keep the reason within 1,000 characters.'))
        return redirect(destination(request))
    with transaction.atomic():
        reservation = get_locked_manageable_reservation(request.user, code=code)
        hut_ids = set(reservation.items.values_list('room__hut_id', flat=True))
        if len(hut_ids) != 1 or None in hut_ids:
            raise PermissionDenied('This reservation requires administrator review.')
        before = reservation.status
        deposit_approval = False
        if action == 'confirm':
            if before != 'pending':
                messages.error(request, _('Only pending reservations can be confirmed.'))
                return redirect(destination(request))
            capacity_rows, fits = availability(reservation, locked=True)
            if not fits:
                messages.error(request, _('Capacity conflict: approval was not saved. Review rooms or maintenance closures.'))
                return redirect(destination(request))
            if reservation.guest_request:
                from .deposit_flow_v180 import approve_deposit, DepositTermsError
                try:
                    approve_deposit(request, reservation, request.POST)
                except DepositTermsError as exc:
                    return render(request, 'bookings/deposit_approval_v180.html', {
                        'reservation': reservation, 'deposit_form': exc.form, 'source': request.POST.get('source', ''),
                        'selected_slug': request.POST.get('return_hut', ''), 'capacity_rows': capacity_rows})
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                    return redirect(destination(request))
                deposit_approval = True
                after = reservation.status
            else:
                after = 'confirmed'
        elif before == 'cancelled':
            messages.error(request, _('Reservation is already cancelled.'))
            return redirect(destination(request))
        else:
            # Match the room-lock contract used by creation and moves.
            lock_rooms(reservation.items.values_list('room_id', flat=True))
            after = 'cancelled'
        reservation.status = after
        reservation.save(update_fields=['status'])
        decision = ReservationDecision.objects.create(reservation=reservation, actor=request.user,
            before=before, after=after, reason=reason if after == 'cancelled' else '', fingerprint=fingerprint(reservation))
        if not deposit_approval:
            supersede_decisions(reservation)
        if reservation.guest_request and not deposit_approval:
            if after == 'confirmed':
                send_confirmation(request, reservation, event=f'decision:{decision.pk}')
            else:
                send_guest_request_declined(request, reservation, reason=reason, event=f'decision:{decision.pk}')
    request.session['staff_decision_v152'] = decision.pk
    messages.success(request, _('Approved; payment instructions have been queued. The stay awaits its deposit.') if deposit_approval and after == 'pending' else _('Reservation confirmed.') if after == 'confirmed' else _('Reservation cancelled; beds are available again.'))
    return redirect(destination(request))


@login_required
@require_POST
def undo_decision(request, code, decision_id):
    from .views import get_locked_manageable_reservation
    from .notifications_v145 import queue_notification
    from .guest_requests_v126 import _guest_context
    with transaction.atomic():
        reservation = get_locked_manageable_reservation(request.user, code=code)
        decision = get_object_or_404(ReservationDecision.objects.select_for_update(),
                                    pk=decision_id, reservation=reservation, actor=request.user)
        latest = reservation.staff_decisions.order_by('-pk').values_list('pk', flat=True).first()
        valid = (deposit_undo_allowed(reservation) and decision.before == 'pending' and decision.undone_at is None
                 and decision.created_at >= timezone.now()-UNDO_WINDOW and latest == decision.pk
                 and reservation.status == decision.after and fingerprint(reservation) == decision.fingerprint
                 and not GuestStay.objects.filter(reservation=reservation, checked_in_at__isnull=False).exists())
        if not valid:
            messages.error(request, _('This decision can no longer be undone. Review the reservation.'))
            return redirect(destination(request))
        capacity_rows, fits = availability(reservation, locked=True)
        if not fits:
            messages.error(request, _('Beds are no longer available. The decision was not undone.'))
            return redirect(destination(request))
        if reservation.deposit_request_id:
            hold = reservation.deposit_request
            hold.state, hold.closed_at, hold.closed_by = 'withdrawn', timezone.now(), request.user
            hold.close_reason = 'Approval undone by staff.'
            hold.save(update_fields=['state', 'closed_at', 'closed_by', 'close_reason'])
        reservation.status = 'pending'
        reservation.save(update_fields=['status'])
        decision.undone_at = timezone.now()
        decision.save(update_fields=['undone_at'])
        supersede_decisions(reservation)
        if reservation.guest_request and reservation.email:
            context = _guest_context(request, reservation)
            body = (f'Update for {context["hut_name"]}\n\nReference: {reservation.code}\n'
                    f'The hut keeper has withdrawn the previous decision. Your request is awaiting approval again.\n'
                    f'Your stay is not confirmed. Please check the current status here:\n{context["link"]}\n')
            queue_notification(reservation, 'decision_undo_guest', 'Reservation decision updated — awaiting approval',
                               body, reservation.email, event=str(decision.pk))
    request.session.pop('staff_decision_v152', None)
    messages.success(request, _('Decision undone. The request is awaiting approval again.'))
    if reservation.guest_request and reservation.email:
        messages.info(request, _('A guest status correction has been queued.'))
    return redirect(destination(request))
