"""Staff-only manual payment ledger."""
from decimal import Decimal, InvalidOperation
import hashlib
import secrets
from django.core import signing
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import PaymentTransaction, Reservation
from .views import manageable_reservations, get_locked_manageable_reservation


def payment_token(reservation, user):
    return signing.dumps({'reservation': reservation.pk, 'user': user.pk, 'nonce': secrets.token_hex(16)},
                         salt='payment-entry-v180')


def balance(reservation):
    entries = reservation.payment_transactions.all()
    paid = sum((t.amount for t in entries if t.kind != PaymentTransaction.Kind.REFUND), Decimal('0.00'))
    refunded = sum((t.amount for t in entries if t.kind == PaymentTransaction.Kind.REFUND), Decimal('0.00'))
    net = paid - refunded
    due = Decimal(reservation.total_price) - net
    status = ('unpaid' if net <= 0 else 'overpaid' if due < 0 else 'paid' if due == 0 else 'partial')
    return {'paid': paid, 'refunded': refunded, 'net': net, 'due': due, 'status': status}


@login_required
@require_http_methods(['GET', 'POST'])
def reservation_payments(request, code):
    from .deposit_flow_v180 import deposit_context
    reservation = get_object_or_404(manageable_reservations(request.user).prefetch_related('items', 'payment_transactions'), code=code)
    hut_ids = set(reservation.items.values_list('room__hut_id', flat=True))
    if len(hut_ids) != 1 or None in hut_ids:
        raise PermissionDenied('Payments require a single-hut reservation.')
    if request.method == 'POST':
        kind = request.POST.get('kind', '')
        method = request.POST.get('method', '')
        amount_raw = request.POST.get('amount', '')
        if kind not in PaymentTransaction.Kind.values or method not in PaymentTransaction.Method.values:
            messages.error(request, 'Choose a valid transaction type and payment method.')
        else:
            try:
                amount = Decimal(amount_raw)
                if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount > Decimal('99999999.99'):
                    raise ValueError
            except (ValueError, ArithmeticError, InvalidOperation):
                messages.error(request, 'Enter a positive amount with at most two decimal places.')
            else:
                with transaction.atomic():
                    locked = get_locked_manageable_reservation(request.user, pk=reservation.pk)
                    token = request.POST.get('recording_token', '')
                    key = None
                    if token or locked.deposit_request_id:
                        try:
                            identity = signing.loads(token, salt='payment-entry-v180', max_age=86400)
                            if identity.get('reservation') != locked.pk or identity.get('user') != request.user.pk:
                                raise signing.BadSignature
                        except signing.BadSignature:
                            messages.error(request, 'This payment form expired or is invalid. Reload it before recording funds.')
                            return redirect('bookings:reservation_payments', code=code)
                        key = hashlib.sha256(token.encode()).hexdigest()
                        previous = PaymentTransaction.objects.filter(recording_key=key).first()
                        if previous:
                            messages.info(request, 'This transaction was already recorded; no duplicate entry was added.')
                            return redirect('bookings:reservation_payments', code=code)
                    current = balance(locked)
                    if kind == PaymentTransaction.Kind.REFUND and amount > current['net']:
                        messages.error(request, 'Refund cannot exceed the net amount received.')
                    else:
                        PaymentTransaction.objects.create(
                            reservation=locked, kind=kind, method=method, amount=amount,
                            note=request.POST.get('note', '')[:500], recorded_by=request.user,
                            recording_key=key,
                        )
                        locked.refresh_from_db()
                        if locked.deposit_request_id and locked.status == 'cancelled':
                            messages.warning(request, 'Payment is recorded, but this booking is cancelled. Review availability and any refund manually.')
                        messages.success(request, 'Transaction recorded.')
                        return redirect('bookings:reservation_payments', code=code)
    reservation.refresh_from_db()
    transactions = list(reservation.payment_transactions.select_related('recorded_by').order_by('-created', '-pk'))
    return render(request, 'bookings/reservation_payments.html', {
        'recording_token': payment_token(reservation, request.user),
        'deposit180': deposit_context(reservation),
        'reservation': reservation, 'transactions': transactions,
        'summary': balance(reservation), 'kinds': PaymentTransaction.Kind.choices,
        'methods': PaymentTransaction.Method.choices, 'currency': settings.BOOKING_CURRENCY,
    })
