"""Manager-only review queue for public reservation requests.

Uses the same hut isolation as the existing reservation management workflow.
No new database fields or status transitions are introduced here.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from datetime import timedelta

from django.utils import timezone
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import Reservation
from .request_operations_v128 import (
    filter_requests, get_request_filters, pending_priorities, scoped_public_requests,
)


@login_required
@require_GET
def approval_dashboard(request):
    huts, selected_hut, selected_slug, scoped = scoped_public_requests(request)
    now = timezone.now()
    today = timezone.localdate()
    filters = get_request_filters(request)
    status, query, priority = filters['status'], filters['q'], filters['priority']

    counts = {
        'pending': scoped.filter(status=Reservation.Status.PENDING).count(),
        'confirmed': scoped.filter(status=Reservation.Status.CONFIRMED).count(),
        'cancelled': scoped.filter(status=Reservation.Status.CANCELLED).count(),
    }
    from .models import ReservationNotification
    delivery_failures = ReservationNotification.objects.filter(reservation__in=scoped, status='failed').count()
    priority_counts = pending_priorities(scoped, now=now, today=today)
    results = filter_requests(scoped, filters, now=now, today=today)

    page = Paginator(
        results.prefetch_related('items__room__hut'), 12
    ).get_page(request.GET.get('page'))

    # Presentation-only information; the POST action performs authorization
    # and locking again. Never trust a button's presence as authorization.
    for reservation in page.object_list:
        hut_ids = {item.room.hut_id for item in reservation.items.all()}
        reservation.waiting_over_24h = (
            reservation.status == Reservation.Status.PENDING
            and reservation.created <= now - timedelta(hours=24)
        )
        reservation.arrival_due = (
            reservation.status == Reservation.Status.PENDING
            and reservation.check_in <= today + timedelta(days=2)
        )
        reservation.reviewable_here = (
            reservation.status == Reservation.Status.PENDING
            and len(hut_ids) == 1 and None not in hut_ids
        )

    from .staff_decisions_v152 import decorate_requests, undo_context
    decorate_requests(page.object_list)
    return render(request, 'bookings/approval_dashboard_v127.html', {
        'delivery_failures': delivery_failures, 'undo_decision': undo_context(request, scoped),
        'page': page, 'huts': huts, 'selected_hut': selected_hut,
        'selected_slug': selected_slug,
        'manager_mode': not request.user.is_superuser,
        'counts': counts, 'status_filter': status, 'q': query,
        'priority_counts': priority_counts, 'priority_filter': priority,
    })
