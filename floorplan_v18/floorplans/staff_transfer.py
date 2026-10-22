"""V18: review-before-commit room transfers from the calendar."""
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from bookings.models import Room, Reservation, ReservationItem, BedAssignment
from bookings.services import modify_reservation, NotAvailable
from .bed_management import permitted_hut

@staff_member_required
@require_http_methods(['GET', 'POST'])
def review_transfer(request, hut_id, code):
    hut = permitted_hut(request, hut_id)
    reservation = get_object_or_404(Reservation.objects.filter(items__room__hut=hut).distinct(), code=code)
    if ReservationItem.objects.filter(reservation=reservation).exclude(room__hut=hut).exists():
        raise Http404('Multi-hut reservations cannot be transferred here')
    items = list(ReservationItem.objects.filter(reservation=reservation).select_related('room'))
    # Only single-room reservations are supported to prevent accidentally moving other items.
    if len(items) != 1:
        raise Http404('Only single-room reservations can be transferred here')
    item = items[0]
    try:
        target_id = int(request.POST.get('target') if request.method == 'POST' else request.GET.get('target', ''))
    except (TypeError, ValueError):
        raise Http404('Invalid destination room')
    target = get_object_or_404(Room, pk=target_id, hut=hut, is_active=True)
    error = None
    if target.pk == item.room_id:
        error = 'Select a different room.'
    elif item.beds > target.capacity:
        error = 'Destination room capacity is too small.'
    elif reservation.status not in Reservation.HOLDING:
        error = 'Only active reservations can be transferred.'
    elif BedAssignment.objects.filter(item=item).exists():
        error = 'Unassign numbered beds before transferring this reservation.'
    if request.method == 'POST' and not error:
        try:
            with transaction.atomic():
                locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
                current = list(ReservationItem.objects.select_for_update().filter(reservation=locked))
                if locked.status not in Reservation.HOLDING or len(current) != 1 or current[0].room_id != item.room_id or current[0].beds != item.beds:
                    raise ValidationError('Reservation changed; refresh the calendar and try again.')
                if BedAssignment.objects.filter(item__reservation=locked).exists():
                    raise ValidationError('Numbered beds are assigned; unassign them first.')
                modify_reservation(code=locked.code, check_in=locked.check_in,
                                   check_out=locked.check_out, beds_by_room={target.pk: current[0].beds})
        except (ValidationError, NotAvailable, ValueError) as exc:
            error = str(exc)
        else:
            return redirect(reverse('floorplans:staff_reservation', args=[hut.pk, reservation.code]) + '?updated=1')
    return render(request, 'floorplans/staff_transfer.html', {
        'hut': hut, 'reservation': reservation, 'item': item, 'target': target, 'error': error,
    })
