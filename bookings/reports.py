"""Hut-scoped historical stay reporting; no model changes required."""
import csv
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import GuestStay, Reservation, ReservationItem, Room
from .views import manageable_reservations, permitted_hut_selection


def _filters(request):
    huts, hut, slug = permitted_hut_selection(request)
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        first = date(year, month, 1)
        if not 2000 <= year <= 2100:
            raise ValueError
    except (TypeError, ValueError):
        return None
    end = first + timedelta(days=monthrange(year, month)[1])
    query = request.GET.get('q', '').strip()[:120]
    # The complete-booking scope prevents managers from seeing mixed-hut records.
    allowed = manageable_reservations(request.user)
    if hut:
        allowed = allowed.filter(items__room__hut=hut)
    allowed = allowed.distinct()
    stays = (GuestStay.objects.filter(reservation__in=allowed)
             .select_related('reservation', 'checked_in_by', 'checked_out_by')
             .filter(Q(checked_in_at__date__gte=first, checked_in_at__date__lt=end) |
                     Q(checked_out_at__date__gte=first, checked_out_at__date__lt=end)))
    if query:
        stays = stays.filter(Q(reservation__name__icontains=query) |
                             Q(reservation__email__icontains=query) |
                             Q(reservation__code__icontains=query))
    stays = stays.order_by('-checked_in_at', '-pk')
    return huts, hut, slug, first, end, query, stays, allowed


@staff_member_required
@require_GET
def stay_history(request):
    data = _filters(request)
    if data is None:
        return JsonResponse({'error': 'Invalid year or month.'}, status=400)
    huts, hut, slug, first, end, query, stays, allowed = data
    # Monthly event counts are independent of text search.
    events = GuestStay.objects.filter(reservation__in=allowed)
    arrivals = events.filter(checked_in_at__date__gte=first, checked_in_at__date__lt=end).count()
    departures = events.filter(checked_out_at__date__gte=first, checked_out_at__date__lt=end).count()
    # Booked bed-nights are based on confirmed reservations overlapping the month,
    # not measured actual nights stayed. Historical room capacity may differ.
    bookings = (Reservation.objects.filter(pk__in=allowed, status=Reservation.Status.CONFIRMED,
                  check_in__lt=end, check_out__gt=first).distinct())
    items = ReservationItem.objects.filter(reservation__in=bookings).select_related('reservation', 'room')
    if hut:
        items = items.filter(room__hut=hut)
    bed_nights = sum(item.beds * (min(item.reservation.check_out, end) -
                                 max(item.reservation.check_in, first)).days for item in items)
    capacity = Room.objects.filter(is_active=True)
    if hut:
        capacity = capacity.filter(hut=hut)
    total_capacity = sum(room.capacity for room in capacity)
    total_possible = total_capacity * (end - first).days
    occupancy = round(100 * bed_nights / total_possible) if total_possible else 0
    page = Paginator(stays, 25).get_page(request.GET.get('page'))
    return render(request, 'bookings/stay_history.html', {
        'huts': huts, 'selected_hut': hut, 'selected_slug': slug,
        'manager_mode': not request.user.is_superuser,
        'month': first, 'year': first.year, 'month_number': first.month,
        'q': query, 'page': page, 'arrivals': arrivals, 'departures': departures,
        'booked_bed_nights': bed_nights, 'occupancy': occupancy,
        'capacity': total_capacity,
    })


def _safe_csv(value):
    value = str(value or '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


@staff_member_required
@require_GET
def stay_history_export(request):
    data = _filters(request)
    if data is None:
        return JsonResponse({'error': 'Invalid year or month.'}, status=400)
    _, _, _, first, _, _, stays, _ = data
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="stay-history-{first:%Y-%m}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Reference', 'Guest', 'Email', 'Scheduled arrival', 'Scheduled departure',
                     'Actual check-in', 'Checked in by', 'Actual check-out', 'Checked out by'])
    for stay in stays.iterator(chunk_size=200):
        reservation = stay.reservation
        writer.writerow([
            _safe_csv(reservation.code), _safe_csv(reservation.name), _safe_csv(reservation.email),
            reservation.check_in, reservation.check_out,
            timezone.localtime(stay.checked_in_at).isoformat() if stay.checked_in_at else '',
            _safe_csv(stay.checked_in_by.get_username()) if stay.checked_in_by else '',
            timezone.localtime(stay.checked_out_at).isoformat() if stay.checked_out_at else '',
            _safe_csv(stay.checked_out_by.get_username()) if stay.checked_out_by else '',
        ])
    return response
