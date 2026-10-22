"""Staff-only manual payment ledger."""
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import PaymentTransaction, Reservation
from .views import manageable_reservations, get_locked_manageable_reservation


def balance(reservation):
    entries = reservation.payment_transactions.all()
    paid = sum((t.amount for t in entries if t.kind != PaymentTransaction.Kind.REFUND), Decimal('0.00'))
    refunded = sum((t.amount for t in entries if t.kind == PaymentTransaction.Kind.REFUND), Decimal('0.00'))
    net = paid - refunded
    due = Decimal(reservation.total_price) - net
    status = ('unpaid' if net <= 0 else 'overpaid' if due < 0 else 'paid' if due == 0 else 'partial')
    return {'paid': paid, 'refunded': refunded, 'net': net, 'due': due, 'status': status}


@staff_member_required
@require_http_methods(['GET', 'POST'])
def reservation_payments(request, code):
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
                    current = balance(locked)
                    if kind == PaymentTransaction.Kind.REFUND and amount > current['net']:
                        messages.error(request, 'Refund cannot exceed the net amount received.')
                    else:
                        PaymentTransaction.objects.create(
                            reservation=locked, kind=kind, method=method, amount=amount,
                            note=request.POST.get('note', '')[:500], recorded_by=request.user,
                        )
                        messages.success(request, 'Transaction recorded.')
                        return redirect('bookings:reservation_payments', code=code)
    reservation.refresh_from_db()
    transactions = list(reservation.payment_transactions.select_related('recorded_by').order_by('-created', '-pk'))
    return render(request, 'bookings/reservation_payments.html', {
        'reservation': reservation, 'transactions': transactions,
        'summary': balance(reservation), 'kinds': PaymentTransaction.Kind.choices,
        'methods': PaymentTransaction.Method.choices, 'currency': settings.BOOKING_CURRENCY,
    })
