"""V21 manual bed readiness board; does not alter booking or closure data."""
from datetime import date
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from bookings.models import Bed, BedAssignment, BedClosure, ReservationItem, Room
from .bed_management import permitted_hut
from .housekeeping_models import BedHousekeeping

@staff_member_required
@require_http_methods(['GET', 'POST'])
def staff_housekeeping(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    raw = request.GET.get('day', today.isoformat())
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return HttpResponseBadRequest('Invalid date')
    if abs((day - today).days) > 3660:
        return HttpResponseBadRequest('Date outside allowed range')
    if request.method == 'POST':
        action = request.POST.get('state')
        if action not in ('ready', 'needs_cleaning'):
            return HttpResponseBadRequest('Invalid housekeeping state')
        try:
            bed_id = int(request.POST.get('bed_id', ''))
        except (TypeError, ValueError):
            return HttpResponseBadRequest('Invalid bed ID')
        with transaction.atomic():
            bed = get_object_or_404(Bed.objects.select_related('room'), pk=bed_id, room__hut=hut, room__is_active=True)
            Room.objects.select_for_update().get(pk=bed.room_id)
            record, _ = BedHousekeeping.objects.update_or_create(bed=bed, defaults={
                'state': action, 'updated_by': request.user,
                'note': request.POST.get('note', '').strip()[:240],
            })
        return redirect(f'{request.path}?day={day.isoformat()}')
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('position', 'pk'))
    beds = list(Bed.objects.filter(room__in=rooms).select_related('room').order_by('room__position', 'room_id', 'number'))
    bed_ids = [b.pk for b in beds]
    housekeeping = {r.bed_id: r for r in BedHousekeeping.objects.filter(bed_id__in=bed_ids)}
    closures = {c.bed_id for c in BedClosure.objects.filter(bed_id__in=bed_ids, start__lte=day, end__gt=day)}
    assignments = {a.bed_id: a for a in BedAssignment.objects.filter(
        bed_id__in=bed_ids, item__reservation__status__in=['pending', 'confirmed'],
        item__reservation__check_in__lte=day, item__reservation__check_out__gt=day,
    ).select_related('item__reservation')}
    demand = {}
    for item in ReservationItem.objects.filter(room__in=rooms, reservation__status__in=['pending', 'confirmed'], reservation__check_in__lte=day, reservation__check_out__gt=day):
        demand[item.room_id] = demand.get(item.room_id, 0) + item.beds
    grouped = []
    for room in rooms:
        room_beds = []
        for bed in beds:
            if bed.room_id != room.pk:
                continue
            record = housekeeping.get(bed.pk)
            room_beds.append({'bed': bed, 'state': record.state if record else 'unknown',
                              'note': record.note if record else '', 'updated_at': record.updated_at if record else None,
                              'closed': bed.pk in closures, 'assignment': assignments.get(bed.pk)})
        grouped.append({'room': room, 'beds': room_beds, 'reserved': demand.get(room.pk, 0)})
    return render(request, 'floorplans/staff_housekeeping.html', {
        'hut': hut, 'day': day, 'grouped': grouped,
        'ready_count': sum(b['state'] == 'ready' for g in grouped for b in g['beds']),
        'dirty_count': sum(b['state'] == 'needs_cleaning' for g in grouped for b in g['beds']),
        'closed_count': sum(b['closed'] for g in grouped for b in g['beds']),
    })
