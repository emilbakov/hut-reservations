"""Staff-only drag/drop move; all writes delegated to existing booking service."""
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import Reservation, Room
from .services import modify_reservation, NotAvailable
from .views import manageable_reservations, permitted_hut_selection

@staff_member_required
@require_http_methods(['GET', 'POST'])
def calendar_move(request):
    try:
        huts, selected, slug = permitted_hut_selection(request)
    except PermissionDenied:
        raise Http404 from None
    code = request.POST.get('code') if request.method == 'POST' else request.GET.get('code')
    reservation = get_object_or_404(manageable_reservations(request.user).prefetch_related('items__room'), code=code)
    items = list(reservation.items.all())
    if len(items) != 1 or items[0].room.hut_id not in set(huts.values_list('pk', flat=True)):
        raise Http404
    item = items[0]
    if selected and item.room.hut_id != selected.pk:
        raise Http404
    rooms = Room.objects.filter(hut_id=item.room.hut_id, is_active=True).order_by('position', 'pk')
    try:
        target_room = rooms.get(pk=request.POST.get('room') if request.method == 'POST' else request.GET.get('room', item.room_id))
        start = date.fromisoformat(request.POST.get('check_in') if request.method == 'POST' else request.GET.get('check_in', str(reservation.check_in)))
        end = start + (reservation.check_out - reservation.check_in)
    except (ValueError, TypeError, Room.DoesNotExist):
        raise Http404
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            raise Http404
        if reservation.status not in Reservation.HOLDING:
            messages.error(request, 'Only active reservations can be moved.')
        else:
            try:
                modify_reservation(code=reservation.code, check_in=start, check_out=end,
                                   beds_by_room={target_room.pk: item.beds})
            except (ValidationError, NotAvailable, ValueError) as exc:
                messages.error(request, 'Move refused: ' + str(exc))
            else:
                messages.success(request, 'Reservation moved. Review guest notifications separately.')
                return redirect('bookings:calendar_edit', code=reservation.code)
    return render(request, 'bookings/calendar_move.html', {
        'reservation': reservation, 'item': item, 'target_room': target_room,
        'check_in': start, 'check_out': end, 'rooms': rooms, 'selected_slug': slug,
    })
