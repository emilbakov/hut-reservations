"""Read-only, hut-scoped manager alerts for SummitDesk v39."""
from datetime import timedelta
from django.db.models import Count
from bookings.models import ReservationItem
from .housekeeping_tasks import HousekeepingTask


def build_alerts(hut, today, forecast):
    """Return actionable alerts, scoped to the selected hut; no writes."""
    alerts = []
    for day in forecast:
        date = day['day']
        demand = day['occupied'] + day['pending']
        capacity = day['available_capacity']
        if demand > capacity:
            alerts.append({
                'level': 'urgent', 'day': date, 'title': 'Capacity exceeded',
                'detail': f'{demand} confirmed/pending bed places versus {capacity} usable places. Review bookings and closures.',
            })
        elif day['closed'] and demand >= capacity and capacity > 0:
            alerts.append({
                'level': 'warning', 'day': date, 'title': 'No spare capacity with closures',
                'detail': f'{day["closed"]} bed(s) closed; all {capacity} remaining places are confirmed or held.',
            })
        if day['arrivals'] and day['tasks']:
            alerts.append({
                'level': 'info', 'day': date, 'title': 'Arrivals and cleaning scheduled',
                'detail': f'{day["arrivals"]} arriving confirmed bed places and {day["tasks"]} housekeeping tasks scheduled. Check readiness.',
            })
    # Pending reservations arriving soon: count reservations, not line items.
    soon = today + timedelta(days=2)
    pending_count = ReservationItem.objects.filter(
        room__hut=hut, room__is_active=True,
        reservation__status='pending',
        reservation__check_in__gte=today,
        reservation__check_in__lt=soon,
    ).values('reservation_id').distinct().count()
    if pending_count:
        alerts.append({
            'level': 'warning', 'day': today, 'title': 'Pending arrivals within 48 hours',
            'detail': f'{pending_count} pending reservation(s) checking in today or tomorrow. Review confirmation status.',
        })
    # Open and in-progress tasks only; avoid reporting completed work as a warning.
    outstanding = HousekeepingTask.objects.filter(
        bed__room__hut=hut, day__gte=today, day__lt=soon,
        status__in=('open', 'in_progress'),
    ).count()
    if outstanding:
        alerts.append({
            'level': 'info', 'day': today, 'title': 'Outstanding housekeeping',
            'detail': f'{outstanding} open/in-progress cleaning task(s) scheduled for today or tomorrow.',
        })
    return alerts[:30]
