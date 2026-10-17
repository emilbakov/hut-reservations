"""Twelve-month booking performance report (no database migration)."""
import csv
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.utils import timezone

from .models import Reservation, ReservationItem, Room
from .views import permitted_hut_selection


def _yearly_data(request):
    huts, hut, slug = permitted_hut_selection(request)
    try:
        year = int(request.GET.get('year', timezone.localdate().year))
        if not 2000 <= year <= 2100:
            raise ValueError
    except (TypeError, ValueError):
        return None

    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    # A superuser must choose a hut explicitly; avoid inadvertently mixing
    # historical cross-hut reservations or showing misleading total capacity.
    if hut is None:
        return huts, hut, slug, year, [], True

    capacity = sum(Room.objects.filter(hut=hut, is_active=True).values_list('capacity', flat=True))
    scoped_items = ReservationItem.objects.filter(room__hut=hut).select_related('room')
    reservations = (Reservation.objects.filter(
        status=Reservation.Status.CONFIRMED,
        check_in__lt=end, check_out__gt=start,
        items__room__hut=hut,
    ).distinct().prefetch_related(Prefetch('items', queryset=scoped_items, to_attr='report_items')))

    # Do not reveal guest records from historic bookings that span huts:
    # the dashboard aggregates only items belonging to the selected hut.
    rows = []
    for month in range(1, 13):
        first = date(year, month, 1)
        after = first + timedelta(days=monthrange(year, month)[1])
        booked_beds = 0
        revenue = Decimal('0.00')
        reservation_count = 0
        for booking in reservations:
            nights = (min(booking.check_out, after) - max(booking.check_in, first)).days
            if nights <= 0:
                continue
            items = booking.report_items
            if not items:
                continue
            reservation_count += 1
            booked_beds += sum(item.beds * nights for item in items)
            revenue += sum((item.beds * item.price_per_night * nights for item in items), Decimal('0.00'))
        available = capacity * (after - first).days
        occupancy = round(100 * booked_beds / available, 1) if available else 0
        rows.append({'month': first, 'count': reservation_count,
                     'bed_nights': booked_beds, 'capacity_nights': available,
                     'occupancy': occupancy, 'revenue': revenue})
    return huts, hut, slug, year, rows, False


@staff_member_required
@require_GET
def yearly_performance(request):
    data = _yearly_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid year.'}, status=400)
    huts, hut, slug, year, rows, select_hut = data
    max_revenue = max((r['revenue'] for r in rows), default=Decimal('0'))
    for r in rows:
        r['revenue_percent'] = round(100 * r['revenue'] / max_revenue, 1) if max_revenue else 0
    return render(request, 'bookings/yearly_performance.html', {
        'huts': huts, 'selected_hut': hut, 'selected_slug': slug,
        'manager_mode': not request.user.is_superuser,
        'year': year, 'rows': rows, 'select_hut': select_hut,
        'total_bed_nights': sum(r['bed_nights'] for r in rows),
        'total_revenue': sum((r['revenue'] for r in rows), Decimal('0.00')),
        'total_reservations_monthly': sum(r['count'] for r in rows),
        'year_occupancy': round(100 * sum(r['bed_nights'] for r in rows) /
                                sum(r['capacity_nights'] for r in rows), 1)
            if sum(r['capacity_nights'] for r in rows) else 0,
        'currency': settings.BOOKING_CURRENCY,
    })


@staff_member_required
@require_GET
def yearly_performance_export(request):
    data = _yearly_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid year.'}, status=400)
    _, hut, _, year, rows, select_hut = data
    if select_hut:
        return JsonResponse({'error': 'Select a hut.'}, status=400)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="performance-{hut.slug}-{year}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Month', 'Reservations overlapping month', 'Booked bed-nights',
                     'Available bed-nights', 'Occupancy percent', 'Estimated revenue', 'Currency'])
    for row in rows:
        writer.writerow([row['month'].isoformat(), row['count'], row['bed_nights'],
                         row['capacity_nights'], row['occupancy'], row['revenue'],
                         settings.BOOKING_CURRENCY])
    return response
