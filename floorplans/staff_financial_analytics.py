"""SummitDesk v35: manager-only, hut-scoped booking value analytics.

This is NOT a payments or cash-received report.
"""
import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from bookings.models import ReservationItem, Room
from .staff_tasks import access

MAX_DAYS = 366
ZERO = Decimal('0.00')


def _csv_safe(value):
    value = '' if value is None else str(value)
    if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + value
    return value


def _month_key(day):
    return day.strftime('%Y-%m')


@login_required
@require_GET
def staff_financial_analytics(request, hut_id):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers may view financial analytics.')

    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get('from') or today.replace(day=1).isoformat())
        end_day = date.fromisoformat(request.GET.get('to') or today.isoformat())
    except (ValueError, TypeError):
        return HttpResponseBadRequest('Dates must be YYYY-MM-DD')
    if end_day < start or (end_day - start).days >= MAX_DAYS:
        return HttpResponseBadRequest('Date range must be 1 to 366 days')
    end = end_day + timedelta(days=1)

    export = request.GET.get('export', '')
    if export not in ('', 'csv'):
        return HttpResponseBadRequest('Invalid export format')

    # Current active inventory, consistent with v34; historical inactive rooms are excluded.
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('position', 'pk'))
    room_ids = [room.pk for room in rooms]
    items = ReservationItem.objects.filter(
        room_id__in=room_ids,
        reservation__check_in__lt=end,
        reservation__check_out__gt=start,
    ).select_related('reservation', 'room').order_by('pk')

    confirmed_by_room = defaultdict(lambda: ZERO)
    pending_by_room = defaultdict(lambda: ZERO)
    cancelled_by_room = defaultdict(lambda: ZERO)
    confirmed_by_month = defaultdict(lambda: ZERO)
    pending_by_month = defaultdict(lambda: ZERO)
    confirmed_reservations = set()
    pending_reservations = set()
    cancelled_reservations = set()
    confirmed_nights = 0
    pending_nights = 0

    for item in items.iterator(chunk_size=500):
        reservation = item.reservation
        status = reservation.status
        if status not in ('confirmed', 'pending', 'cancelled'):
            continue
        first = max(reservation.check_in, start)
        last = min(reservation.check_out, end)
        if first >= last:
            continue
        rate = item.price_per_night or ZERO
        per_night = rate * item.beds
        night_count = (last - first).days
        amount = per_night * night_count
        if status == 'confirmed':
            confirmed_reservations.add(reservation.pk)
            confirmed_by_room[item.room_id] += amount
            confirmed_nights += item.beds * night_count
        elif status == 'pending':
            pending_reservations.add(reservation.pk)
            pending_by_room[item.room_id] += amount
            pending_nights += item.beds * night_count
        else:
            cancelled_reservations.add(reservation.pk)
            cancelled_by_room[item.room_id] += amount

        # Allocate value by STAY night, not booking creation date.
        if status in ('confirmed', 'pending'):
            night = first
            target = confirmed_by_month if status == 'confirmed' else pending_by_month
            while night < last:
                target[_month_key(night)] += per_night
                night += timedelta(days=1)

    room_rows = []
    for room in rooms:
        room_rows.append({
            'name': room.name,
            'confirmed': confirmed_by_room[room.pk],
            'pending': pending_by_room[room.pk],
            'cancelled': cancelled_by_room[room.pk],
        })

    months = sorted(set(confirmed_by_month) | set(pending_by_month))
    month_rows = [{
        'month': month,
        'confirmed': confirmed_by_month[month],
        'pending': pending_by_month[month],
    } for month in months]
    confirmed_total = sum(confirmed_by_room.values(), ZERO)
    pending_total = sum(pending_by_room.values(), ZERO)
    cancelled_total = sum(cancelled_by_room.values(), ZERO)

    if export == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="summitdesk_v35_hut_{hut.pk}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['SummitDesk v35 booking value report (not collected payments)'])
        writer.writerow(['Hut', _csv_safe(hut.name)])
        writer.writerow(['From', start.isoformat(), 'To (inclusive)', end_day.isoformat()])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Confirmed booking value', str(confirmed_total)])
        writer.writerow(['Pending booking value', str(pending_total)])
        writer.writerow(['Cancelled booking value (excluded)', str(cancelled_total)])
        writer.writerow(['Confirmed reservations', len(confirmed_reservations)])
        writer.writerow(['Pending reservations', len(pending_reservations)])
        writer.writerow(['Cancelled reservations', len(cancelled_reservations)])
        writer.writerow(['Confirmed bed-nights', confirmed_nights])
        writer.writerow(['Pending bed-nights', pending_nights])
        writer.writerow([])
        writer.writerow(['Month (stay dates)', 'Confirmed booking value', 'Pending booking value'])
        for row in month_rows:
            writer.writerow([row['month'], str(row['confirmed']), str(row['pending'])])
        writer.writerow([])
        writer.writerow(['Room', 'Confirmed booking value', 'Pending booking value', 'Cancelled booking value (excluded)'])
        for row in room_rows:
            writer.writerow([_csv_safe(row['name']), str(row['confirmed']), str(row['pending']), str(row['cancelled'])])
        return response

    return render(request, 'floorplans/staff_financial_analytics.html', {
        'hut': hut, 'start': start.isoformat(), 'end': end_day.isoformat(),
        'confirmed_total': confirmed_total, 'pending_total': pending_total,
        'cancelled_total': cancelled_total,
        'confirmed_count': len(confirmed_reservations),
        'pending_count': len(pending_reservations),
        'cancelled_count': len(cancelled_reservations),
        'confirmed_nights': confirmed_nights, 'pending_nights': pending_nights,
        'rooms': room_rows, 'months': month_rows,
        'filter_query': request.GET.urlencode(),
    })
