"""Staff-only bed assignment and maintenance management."""
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import Bed, BedAssignment, BedClosure, Hut, Reservation, ReservationItem, Room
from .views import manageable_reservations


def allowed_rooms(user):
    rooms = Room.objects.select_related('hut')
    return rooms if user.is_superuser else rooms.filter(hut__managers=user)


def ensure_beds(room):
    """Create numbered beds up to room capacity; never silently delete beds."""
    existing = set(room.individual_beds.values_list('number', flat=True))
    Bed.objects.bulk_create([Bed(room=room, number=n) for n in range(1, room.capacity + 1) if n not in existing], ignore_conflicts=True)


def overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


@staff_member_required
@require_http_methods(['GET', 'POST'])
def bed_management(request, room_id):
    room = get_object_or_404(allowed_rooms(request.user), pk=room_id)
    today = timezone.localdate()
    try:
        day = date.fromisoformat(request.GET.get('day', today.isoformat()))
    except ValueError:
        return HttpResponseBadRequest('Invalid date')
    if not 2000 <= day.year <= 2100:
        return HttpResponseBadRequest('Invalid date')
    message = ''
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Serializes all bed management and reservation writes on the room.
                room = Room.objects.select_for_update().get(pk=room.pk)
                ensure_beds(room)
                action = request.POST.get('action')
                bed = get_object_or_404(Bed, pk=request.POST.get('bed_id'), room=room)
                if bed.number > room.capacity:
                    raise ValidationError('This bed is outside the current room capacity.')
                if action == 'assign':
                    item = get_object_or_404(
                        ReservationItem.objects.select_related('reservation'),
                        pk=request.POST.get('item_id'), room=room,
                        reservation__status__in=Reservation.HOLDING,
                    )
                    if not manageable_reservations(request.user).filter(pk=item.reservation_id).exists():
                        raise PermissionDenied('Reservation is not manageable by this user.')
                    reservation = item.reservation
                    if not (reservation.check_in <= day < reservation.check_out):
                        raise ValidationError('The reservation does not cover the selected night.')
                    if BedAssignment.objects.filter(item=item, bed=bed).exists():
                        raise ValidationError('This bed is already assigned to this reservation.')
                    if item.bed_assignments.count() >= item.beds:
                        raise ValidationError('All reserved beds have already been assigned.')
                    if BedClosure.objects.filter(bed=bed, start__lt=reservation.check_out, end__gt=reservation.check_in).exists():
                        raise ValidationError('This bed is out of service during the reservation.')
                    if BedAssignment.objects.filter(
                        bed=bed, item__reservation__status__in=Reservation.HOLDING,
                        item__reservation__check_in__lt=reservation.check_out,
                        item__reservation__check_out__gt=reservation.check_in,
                    ).exists():
                        raise ValidationError('Bed is assigned to another overlapping reservation.')
                    BedAssignment.objects.create(bed=bed, item=item)
                elif action == 'unassign':
                    assignment = get_object_or_404(BedAssignment, bed=bed, pk=request.POST.get('assignment_id'))
                    if not manageable_reservations(request.user).filter(pk=assignment.item.reservation_id).exists():
                        raise PermissionDenied('Reservation is not manageable by this user.')
                    assignment.delete()
                elif action == 'close':
                    start = date.fromisoformat(request.POST.get('start', ''))
                    end = date.fromisoformat(request.POST.get('end', ''))
                    if start < today or end <= start or (end - start).days > 366:
                        raise ValidationError('Choose valid future maintenance dates (maximum 366 nights).')
                    if BedClosure.objects.filter(bed=bed, start__lt=end, end__gt=start).exists():
                        raise ValidationError('This bed already has an overlapping closure.')
                    if BedAssignment.objects.filter(
                        bed=bed, item__reservation__status__in=Reservation.HOLDING,
                        item__reservation__check_in__lt=end,
                        item__reservation__check_out__gt=start,
                    ).exists():
                        raise ValidationError('An existing guest is assigned to this bed during those dates.')
                    # Every night must retain enough physical capacity for current bookings.
                    items = list(ReservationItem.objects.filter(
                        room=room, reservation__status__in=Reservation.HOLDING,
                        reservation__check_in__lt=end, reservation__check_out__gt=start,
                    ).select_related('reservation'))
                    closures = list(BedClosure.objects.filter(
                        bed__room=room, start__lt=end, end__gt=start
                    ).select_related('bed'))
                    current = start
                    while current < end:
                        occupied = sum(i.beds for i in items if i.reservation.check_in <= current < i.reservation.check_out)
                        unavailable = {c.bed_id for c in closures if c.start <= current < c.end}
                        unavailable.add(bed.pk)
                        if occupied + len(unavailable) > room.capacity:
                            raise ValidationError(f'Cannot close this bed: existing bookings require capacity on {current}.')
                        current += timedelta(days=1)
                    BedClosure.objects.create(bed=bed, start=start, end=end, reason=request.POST.get('reason', '')[:200])
                elif action == 'reopen':
                    closure = get_object_or_404(BedClosure, bed=bed, pk=request.POST.get('closure_id'))
                    closure.delete()
                else:
                    return HttpResponseBadRequest('Unknown action')
            return redirect(f'{request.path}?day={day.isoformat()}')
        except (ValidationError, ValueError) as exc:
            message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Invalid date or input.'
    ensure_beds(room)
    beds = list(room.individual_beds.filter(number__lte=room.capacity).order_by('number'))
    reservations = list(ReservationItem.objects.filter(
        room=room, reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lte=day, reservation__check_out__gt=day,
        reservation__in=manageable_reservations(request.user),
    ).select_related('reservation'))
    active_assignments = list(BedAssignment.objects.filter(
        bed__room=room, item__reservation__status__in=Reservation.HOLDING,
        item__reservation__check_in__lte=day, item__reservation__check_out__gt=day,
    ).select_related('item__reservation'))
    active_closures = list(BedClosure.objects.filter(bed__room=room, start__lte=day, end__gt=day))
    assigned_by_bed = {a.bed_id: a for a in active_assignments}
    closed_by_bed = {c.bed_id: c for c in active_closures}
    for bed in beds:
        bed.current_assignment = assigned_by_bed.get(bed.pk)
        bed.current_closure = closed_by_bed.get(bed.pk)
        bed.is_assignable = not bed.current_assignment and not bed.current_closure
    return render(request, 'bookings/bed_management.html', {
        'room': room, 'day': day, 'beds': beds, 'reservations': reservations,
        'message': message, 'today': today,
    })
