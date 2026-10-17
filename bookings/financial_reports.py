"""Staff financial dashboard: cash movements by transaction date, balances by arrival month."""
import csv
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import PaymentTransaction, Reservation
from .views import manageable_reservations, permitted_hut_selection

ZERO = Decimal("0.00")

def report_scope(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        first = date(year, month, 1)
        if not 2000 <= year <= 2100:
            raise ValueError
    except (TypeError, ValueError):
        return None
    end = first + timedelta(days=monthrange(year, month)[1])
    huts, hut, slug = permitted_hut_selection(request)
    # Exclude mixed-hut reservations even for superusers; financial attribution
    # would otherwise be ambiguous.
    allowed = manageable_reservations(request.user).filter(items__room__hut__isnull=False).annotate(
        financial_hut_count=Count("items__room__hut", distinct=True)
    ).filter(financial_hut_count=1).distinct()
    if hut:
        allowed = allowed.filter(items__room__hut=hut).distinct()
    return first, end, huts, hut, slug, allowed

def summary_for(first, end, allowed):
    # Transactions are selected by their recorded date (not arrival date).
    start_dt = timezone.make_aware(datetime.combine(first, time.min))
    end_dt = timezone.make_aware(datetime.combine(end, time.min))
    transactions = PaymentTransaction.objects.filter(
        reservation__in=allowed, created__gte=start_dt, created__lt=end_dt
    ).select_related("reservation", "recorded_by").order_by("created", "pk")
    receipts = transactions.filter(kind__in=[PaymentTransaction.Kind.PAYMENT, PaymentTransaction.Kind.DEPOSIT]).aggregate(
        total=Coalesce(Sum("amount"), Value(ZERO), output_field=DecimalField(max_digits=14, decimal_places=2))
    )["total"]
    deposits = transactions.filter(kind=PaymentTransaction.Kind.DEPOSIT).aggregate(
        total=Coalesce(Sum("amount"), Value(ZERO), output_field=DecimalField(max_digits=14, decimal_places=2))
    )["total"]
    refunds = transactions.filter(kind=PaymentTransaction.Kind.REFUND).aggregate(
        total=Coalesce(Sum("amount"), Value(ZERO), output_field=DecimalField(max_digits=14, decimal_places=2))
    )["total"]
    # Balance is a current snapshot for reservations arriving in the month,
    # excluding cancelled bookings; payment history remains unchanged.
    arrival_bookings = allowed.filter(
        check_in__gte=first, check_in__lt=end
    ).exclude(status=Reservation.Status.CANCELLED).prefetch_related("items", "payment_transactions")
    booked = ZERO
    paid_for_arrivals = ZERO
    outstanding = ZERO
    overpaid = ZERO
    count = 0
    for reservation in arrival_bookings:
        count += 1
        price = Decimal(reservation.total_price)
        net = sum(
            (t.amount if t.kind != PaymentTransaction.Kind.REFUND else -t.amount
             for t in reservation.payment_transactions.all()), ZERO
        )
        booked += price
        paid_for_arrivals += net
        outstanding += max(price - net, ZERO)
        overpaid += max(net - price, ZERO)
    return {
        "receipts": receipts, "deposits": deposits, "refunds": refunds,
        "net_cash": receipts - refunds, "booked": booked,
        "paid_for_arrivals": paid_for_arrivals, "outstanding": outstanding,
        "overpaid": overpaid, "arrival_count": count, "transactions": transactions,
    }

@staff_member_required
@require_GET
def financial_dashboard(request):
    scope = report_scope(request)
    if scope is None:
        return HttpResponseBadRequest("Invalid report month.")
    first, end, huts, hut, slug, allowed = scope
    data = summary_for(first, end, allowed)
    return render(request, "bookings/financial_dashboard.html", {
        **data, "month": first, "month_options": [(i, date(2000,i,1).strftime("%B")) for i in range(1,13)], "huts": huts, "selected_slug": slug,
        "manager_mode": not request.user.is_superuser,
        "currency": settings.BOOKING_CURRENCY,
        "previous": first - timedelta(days=1), "next": end,
    })

@staff_member_required
@require_GET
def financial_export(request):
    scope = report_scope(request)
    if scope is None:
        return HttpResponseBadRequest("Invalid report month.")
    first, end, _, _, _, allowed = scope
    data = summary_for(first, end, allowed)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="financial-{first:%Y-%m}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Recorded at", "Reservation", "Guest", "Hut", "Type", "Method", "Amount", "Signed amount", "Currency", "Recorded by", "Note"])
    for tx in data["transactions"]:
        # Financial report only covers single-hut reservations.
        hut_name = tx.reservation.items.first().room.hut.name
        sign = -1 if tx.kind == PaymentTransaction.Kind.REFUND else 1
        def safe(s):
            s = str(s or "")
            return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s
        writer.writerow([
            timezone.localtime(tx.created).isoformat(), safe(tx.reservation.code),
            safe(tx.reservation.name), safe(hut_name), tx.kind, tx.method,
            str(tx.amount), str(tx.amount * sign), settings.BOOKING_CURRENCY,
            safe(tx.recorded_by), safe(tx.note),
        ])
    writer.writerow([])
    writer.writerow(["Metric", "Value", "Currency"])
    for label, key in [
        ("Payments and deposits received", "receipts"), ("Deposits included in receipts", "deposits"),
        ("Refunds issued", "refunds"), ("Net cash received", "net_cash"),
        ("Current value of active bookings arriving this month", "booked"),
        ("Current net payments for those bookings", "paid_for_arrivals"),
        ("Current outstanding for those bookings", "outstanding"),
        ("Current overpayments for those bookings", "overpaid"),
    ]:
        writer.writerow([label, data[key], settings.BOOKING_CURRENCY])
    writer.writerow(["Active reservations arriving this month", data["arrival_count"], ""])
    return response
