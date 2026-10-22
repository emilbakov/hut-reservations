"""Manager-only review queue for public reservation requests.

Uses the same hut isolation as the existing reservation management workflow.
No new database fields or status transitions are introduced here.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import Reservation
from .views import manageable_reservations, permitted_hut_selection


@login_required
@require_GET
def approval_dashboard(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    scoped = manageable_reservations(request.user).filter(guest_request=True)
    if selected_hut is not None:
        scoped = scoped.filter(items__room__hut=selected_hut)
    scoped = scoped.distinct()

    counts = {
        'pending': scoped.filter(status=Reservation.Status.PENDING).count(),
        'confirmed': scoped.filter(status=Reservation.Status.CONFIRMED).count(),
        'cancelled': scoped.filter(status=Reservation.Status.CANCELLED).count(),
    }

    status = request.GET.get('status', 'pending').strip()
    if status not in {'pending', 'confirmed', 'cancelled', 'all'}:
        status = 'pending'
    query = request.GET.get('q', '').strip()[:120]
    results = scoped
    if status != 'all':
        results = results.filter(status=status)
    if query:
        results = results.filter(
            Q(name__icontains=query) | Q(email__icontains=query)
            | Q(code__icontains=query) | Q(phone__icontains=query)
        )

    if status == 'pending':
        results = results.order_by('created', 'pk')  # Oldest waiting requests first.
    else:
        results = results.order_by('-created', '-pk')

    page = Paginator(
        results.prefetch_related('items__room__hut'), 12
    ).get_page(request.GET.get('page'))

    # Presentation-only information; the POST action performs authorization
    # and locking again. Never trust a button's presence as authorization.
    for reservation in page.object_list:
        hut_ids = {item.room.hut_id for item in reservation.items.all()}
        reservation.reviewable_here = (
            reservation.status == Reservation.Status.PENDING
            and len(hut_ids) == 1 and None not in hut_ids
        )

    return render(request, 'bookings/approval_dashboard_v127.html', {
        'page': page, 'huts': huts, 'selected_hut': selected_hut,
        'selected_slug': selected_slug,
        'manager_mode': not request.user.is_superuser,
        'counts': counts, 'status_filter': status, 'q': query,
    })
