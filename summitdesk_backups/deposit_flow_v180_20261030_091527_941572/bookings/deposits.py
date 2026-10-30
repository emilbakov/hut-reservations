"""Deposit policy and overdue reporting; never changes the payment ledger."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import Hut, HutDepositPolicy, PaymentTransaction, Reservation
from .views import manageable_reservations, permitted_hut_selection


def single_hut_id(reservation):
    hut_ids = set(reservation.items.values_list('room__hut_id', flat=True))
    return next(iter(hut_ids)) if len(hut_ids) == 1 and None not in hut_ids else None


def deposit_summary(reservation, today=None):
    """Compute deposit target and net paid using the reservation's current price.

    Booking modifications can change the target; the due date stays anchored to
    creation. All payments count toward the deposit, refunds reduce net paid.
    """
    hut_id = single_hut_id(reservation)
    if hut_id is None:
        return None
    policy = HutDepositPolicy.objects.filter(hut_id=hut_id).first()
    percentage = policy.percentage if policy else 30
    days = policy.due_days if policy else 3
    due_date = timezone.localtime(reservation.created).date() + timedelta(days=days)
    total = Decimal(reservation.total_price)
    target = (total * Decimal(percentage) / Decimal(100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net = sum((t.amount if t.kind != PaymentTransaction.Kind.REFUND else -t.amount
               for t in reservation.payment_transactions.all()), Decimal('0.00'))
    remaining = max(target - net, Decimal('0.00'))
    today = today or timezone.localdate()
    active = reservation.status in Reservation.HOLDING
    overdue = active and remaining > 0 and today > due_date
    return {'reservation': reservation, 'hut_id': hut_id, 'percentage': percentage,
            'due_date': due_date, 'target': target, 'net_paid': net,
            'remaining': remaining, 'overdue': overdue, 'active': active,
            'reminders_enabled': policy.reminders_enabled if policy else True}


@staff_member_required
@require_http_methods(['GET', 'POST'])
def deposit_dashboard(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    if request.method == 'POST':
        hut = get_object_or_404(huts, pk=request.POST.get('hut_id'))
        if selected_hut and hut.pk != selected_hut.pk:
            return HttpResponseBadRequest('Selected hut does not match the form.')
        try:
            percentage = int(request.POST.get('percentage', ''))
            due_days = int(request.POST.get('due_days', ''))
            if not 0 <= percentage <= 100 or not 0 <= due_days <= 365:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Percentage must be 0–100 and deadline 0–365 days.')
        else:
            HutDepositPolicy.objects.update_or_create(
                hut=hut, defaults={'percentage': percentage, 'due_days': due_days,
                                   'reminders_enabled': request.POST.get('reminders_enabled') == 'on'})
            messages.success(request, 'Deposit policy updated.')
            return redirect('bookings:deposit_dashboard')

    qs = manageable_reservations(request.user).filter(status__in=Reservation.HOLDING)
    if selected_hut:
        qs = qs.filter(items__room__hut=selected_hut)
    qs = qs.distinct().prefetch_related('items__room', 'payment_transactions').order_by('check_in', 'pk')
    rows = []
    for reservation in qs:
        summary = deposit_summary(reservation)
        if summary is not None and summary['remaining'] > 0:
            rows.append(summary)
    rows.sort(key=lambda x: (not x['overdue'], x['due_date'], x['reservation'].check_in))
    policy = HutDepositPolicy.objects.filter(hut=selected_hut).first() if selected_hut else None
    return render(request, 'bookings/deposit_dashboard.html', {
        'rows': rows[:200], 'total_awaiting': len(rows),
        'overdue_count': sum(row['overdue'] for row in rows),
        'huts': huts, 'selected_hut': selected_hut, 'selected_slug': selected_slug,
        'manager_mode': not request.user.is_superuser, 'policy': policy,
        'currency': settings.BOOKING_CURRENCY,
    })
