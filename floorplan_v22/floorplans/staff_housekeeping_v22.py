"""V22 housekeeping page: daily task list and history; uses V21 view for writes."""
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
from .housekeeping_events import BedCleaningEvent

@staff_member_required
@require_http_methods(['GET','POST'])
def staff_housekeeping(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    try:
        day = date.fromisoformat(request.GET.get('day', today.isoformat()))
    except ValueError:
        return HttpResponseBadRequest('Invalid date')
    if abs((day-today).days)>3660:
        return HttpResponseBadRequest('Date outside allowed range')
    if request.method == 'POST':
        action = request.POST.get('state')
        if action not in ('ready','needs_cleaning'):
            return HttpResponseBadRequest('Invalid housekeeping state')
        try:
            bed_id = int(request.POST.get('bed_id', ''))
        except (TypeError,ValueError):
            return HttpResponseBadRequest('Invalid bed ID')
        with transaction.atomic():
            bed = get_object_or_404(Bed.objects.select_related('room'), pk=bed_id, room__hut=hut, room__is_active=True)
            Room.objects.select_for_update().get(pk=bed.room_id)
            note = request.POST.get('note', '').strip()[:240]
            BedHousekeeping.objects.update_or_create(bed=bed, defaults={
                'state':action, 'updated_by':request.user, 'note':note})
            BedCleaningEvent.objects.create(bed=bed, action=action, actor=request.user, note=note)
        return redirect(f'{request.path}?day={day.isoformat()}')
    rooms = list(Room.objects.filter(hut=hut,is_active=True).order_by('position','pk'))
    beds = list(Bed.objects.filter(room__in=rooms).select_related('room').order_by('room__position','room_id','number'))
    bed_ids = [b.pk for b in beds]
    states = {r.bed_id:r for r in BedHousekeeping.objects.filter(bed_id__in=bed_ids)}
    closures = set(BedClosure.objects.filter(bed_id__in=bed_ids,start__lte=day,end__gt=day).values_list('bed_id',flat=True))
    assignments = {a.bed_id:a for a in BedAssignment.objects.filter(
        bed_id__in=bed_ids,item__reservation__status__in=['pending','confirmed'],
        item__reservation__check_in__lte=day,item__reservation__check_out__gt=day
    ).select_related('item__reservation')}
    demand = {}
    for item in ReservationItem.objects.filter(room__in=rooms,reservation__status__in=['pending','confirmed'],reservation__check_in__lte=day,reservation__check_out__gt=day):
        demand[item.room_id]=demand.get(item.room_id,0)+item.beds
    grouped=[]
    for room in rooms:
        rows=[]
        for bed in beds:
            if bed.room_id != room.pk: continue
            state=states.get(bed.pk)
            rows.append({'bed':bed,'state':state.state if state else 'unknown',
                         'note':state.note if state else '', 'updated_at':state.updated_at if state else None,
                         'closed':bed.pk in closures,'assignment':assignments.get(bed.pk)})
        grouped.append({'room':room,'beds':rows,'reserved':demand.get(room.pk,0)})
    history=list(BedCleaningEvent.objects.filter(bed__room__hut=hut).select_related('bed__room','actor','reservation')[:50])
    tasks=[r for g in grouped for r in g['beds'] if r['state']!='ready']
    return render(request,'floorplans/staff_housekeeping.html',{
        'hut':hut,'day':day,'grouped':grouped,'history':history,'tasks':tasks,
        'ready_count':sum(r['state']=='ready' for g in grouped for r in g['beds']),
        'dirty_count':sum(r['state']=='needs_cleaning' for g in grouped for r in g['beds']),
        'closed_count':sum(r['closed'] for g in grouped for r in g['beds']),
    })
