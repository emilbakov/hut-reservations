"""Compact, read-only monthly bed availability for the two staff booking forms.

This never reserves or assigns a numbered bed. Values are per-night quantities,
calculated with the same holding statuses and maintenance semantics as free_beds.
"""
import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings

from .models import BedClosure, Reservation, ReservationItem


def booking_month(rooms, selected_start, selected_end, *, today, month_value=None):
    """Build a month of per-night free-bed counts with two scoped DB queries.

    Calendar browsing is bounded to the same allowed check-in horizon as bookings.
    check-out remains exclusive, so its date is not highlighted as occupied.
    """
    latest = today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD)
    first_allowed = today.replace(day=1)
    last_allowed = latest.replace(day=1)
    fallback = selected_start if selected_start and today <= selected_start <= latest else today
    target = fallback.replace(day=1)
    if month_value:
        try:
            # Strict YYYY-MM; malformed/oversized inputs do not reach the ORM.
            if len(month_value) != 7 or month_value[4] != '-':
                raise ValueError('Invalid month')
            year, month = int(month_value[:4]), int(month_value[5:])
            if f'{year:04d}-{month:02d}' != month_value:
                raise ValueError('Invalid month')
            target = date(year, month, 1)
        except (TypeError, ValueError, OverflowError):
            target = fallback.replace(day=1)
    target = min(max(target, first_allowed), last_allowed)
    year, month = target.year, target.month
    days_in_month = calendar.monthrange(year, month)[1]
    last_day = date(year, month, days_in_month)
    window_start = max(target, today)
    window_end = min(last_day + timedelta(days=1), latest + timedelta(days=1))

    room_list = list(rooms)
    capacities = {room.pk: room.capacity for room in room_list}
    booked = defaultdict(lambda: defaultdict(int))
    blocked = defaultdict(lambda: defaultdict(set))
    if capacities and window_start < window_end:
        items = (ReservationItem.objects.filter(
            room_id__in=capacities,
            reservation__status__in=Reservation.HOLDING,
            reservation__check_in__lt=window_end,
            reservation__check_out__gt=window_start,
        ).values_list('room_id', 'beds', 'reservation__check_in', 'reservation__check_out'))
        for room_id, beds, start, end in items:
            night = max(start, window_start)
            while night < min(end, window_end):
                booked[room_id][night] += beds
                night += timedelta(days=1)
        closures = (BedClosure.objects.filter(
            bed__room_id__in=capacities,
            start__lt=window_end, end__gt=window_start,
        ).values_list('bed__room_id', 'bed_id', 'start', 'end'))
        for room_id, bed_id, start, end in closures:
            night = max(start, window_start)
            while night < min(end, window_end):
                blocked[room_id][night].add(bed_id)
                night += timedelta(days=1)

    cells = []
    for day_number in range(1, days_in_month + 1):
        day = date(year, month, day_number)
        enabled = today <= day <= latest
        available = None
        if enabled:
            available = sum(max(0, capacity - booked[room_id][day] - len(blocked[room_id][day]))
                            for room_id, capacity in capacities.items())
        cells.append({
            'date': day.isoformat(), 'next_date': (day + timedelta(days=1)).isoformat(), 'number': day_number,
            'free': available, 'enabled': enabled,
            'is_checkin': day == selected_start,
            'is_checkout': day == selected_end,
            'in_stay': bool(selected_start and selected_end and selected_start <= day < selected_end),
            'tone': ('disabled' if not enabled else 'full' if available == 0 else
                     'low' if available <= 2 else 'open'),
        })
    padded = [None] * target.weekday() + cells
    padded.extend([None] * (-len(padded) % 7))
    weeks = [padded[i:i + 7] for i in range(0, len(padded), 7)]
    prev_month = (target - timedelta(days=1)).replace(day=1)
    next_month = (last_day + timedelta(days=1)).replace(day=1)
    return {
        'label': target.strftime('%B %Y'), 'month': target.strftime('%Y-%m'),
        'weeks': weeks,
        'prev': prev_month.strftime('%Y-%m') if prev_month >= first_allowed else None,
        'next': next_month.strftime('%Y-%m') if next_month <= last_allowed else None,
        'capacity': sum(capacities.values()),
    }
