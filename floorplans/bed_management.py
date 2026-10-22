"""Staff-only individual bed management; installs alongside existing floorplan views."""
import json
from datetime import date, timedelta
from collections import defaultdict
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from bookings.models import Hut, Room, Reservation, ReservationItem, Bed, BedAssignment, BedClosure


def permitted_hut(request, hut_id):
    qs = Hut.objects.filter(is_active=True)
    if not request.user.is_superuser:
        qs = qs.filter(managers=request.user)
    return get_object_or_404(qs, pk=hut_id)


def dates(request):
    try:
        start = date.fromisoformat(request.GET['check_in'])
        end = date.fromisoformat(request.GET['check_out'])
        today = timezone.localdate()
        if start < today or end <= start or start > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD) or (end-start).days > settings.BOOKING_MAX_NIGHTS:
            raise ValueError()
        return start, end
    except (KeyError, ValueError):
        return None


def room_for(request, hut_id, room_id):
    hut = permitted_hut(request, hut_id)
    return hut, get_object_or_404(Room, pk=room_id, hut=hut, is_active=True)


def overlap_items(room, start, end):
    return list(ReservationItem.objects.filter(room=room, reservation__status__in=Reservation.HOLDING, reservation__check_in__lt=end, reservation__check_out__gt=start).select_related('reservation').prefetch_related('bed_assignments'))


def conflict_for_bed(bed, item):
    """Only overlapping holding reservations conflict; checkout is exclusive."""
    r = item.reservation
    return BedAssignment.objects.filter(bed=bed, item__reservation__status__in=Reservation.HOLDING, item__reservation__check_in__lt=r.check_out, item__reservation__check_out__gt=r.check_in).exclude(item=item).exists()


def capacity_safe(room, start, end):
    """Validate each night including room-level unassigned bookings and closures."""
    items = overlap_items(room, start, end)
    closures = list(BedClosure.objects.filter(bed__room=room, start__lt=end, end__gt=start))
    day = start
    while day < end:
        booked = sum(i.beds for i in items if i.reservation.check_in <= day < i.reservation.check_out)
        closed = len({c.bed_id for c in closures if c.start <= day < c.end})
        if booked + closed > room.capacity:
            return False
        day += timedelta(days=1)
    return True


@staff_member_required
@ensure_csrf_cookie
@require_GET
def bed_manager(request, hut_id):
    hut = permitted_hut(request, hut_id)
    return render(request, 'floorplans/bed_manager.html', {'hut': hut, 'today_iso': timezone.localdate().isoformat()})


@staff_member_required
@require_GET
def bed_data(request, hut_id, room_id):
    hut, room = room_for(request, hut_id, room_id)
    period = dates(request)
    if period is None:
        return JsonResponse({'error':'Invalid dates'}, status=400)
    start, end = period
    items = overlap_items(room, start, end)
    beds = list(Bed.objects.filter(room=room).order_by('number'))
    assignments = BedAssignment.objects.filter(bed__in=beds, item__reservation__status__in=Reservation.HOLDING, item__reservation__check_in__lt=end, item__reservation__check_out__gt=start).select_related('item__reservation')
    by_bed = defaultdict(list)
    for a in assignments:
        by_bed[a.bed_id].append({'item_id':a.item_id, 'guest':a.item.reservation.name, 'check_in':a.item.reservation.check_in.isoformat(), 'check_out':a.item.reservation.check_out.isoformat()})
    closures = BedClosure.objects.filter(bed__in=beds, start__lt=end, end__gt=start)
    by_closed = defaultdict(list)
    for c in closures:
        by_closed[c.bed_id].append({'id':c.pk, 'start':c.start.isoformat(), 'end':c.end.isoformat(), 'reason':c.reason})
    return JsonResponse({'room':{'id':room.pk,'name':room.name,'capacity':room.capacity}, 'beds':[{'id':b.pk,'number':b.number,'assignments':by_bed[b.pk],'closures':by_closed[b.pk]} for b in beds], 'items':[{'id':i.pk,'guest':i.reservation.name,'status':i.reservation.get_status_display(),'check_in':i.reservation.check_in.isoformat(),'check_out':i.reservation.check_out.isoformat(),'beds':i.beds,'assigned':i.bed_assignments.count()} for i in items], 'warning':'Unassigned reservation quantities still occupy capacity. Blank beds are not guaranteed available.'})


def body(request):
    try:
        obj = json.loads(request.body)
        return obj if isinstance(obj, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


@staff_member_required
@require_POST
@transaction.atomic
def initialize_beds(request, hut_id, room_id):
    hut, room = room_for(request, hut_id, room_id)
    room = Room.objects.select_for_update().get(pk=room.pk)
    existing = list(Bed.objects.filter(room=room))
    if len(existing) > room.capacity:
        return JsonResponse({'error':'More bed records than room capacity; resolve manually.'},status=409)
    existing_numbers = {b.number for b in existing}
    # Only fill missing numbers, never delete existing bed records or assignments.
    Bed.objects.bulk_create([Bed(room=room, number=n) for n in range(1,room.capacity+1) if n not in existing_numbers])
    return JsonResponse({'ok':True})


@staff_member_required
@require_POST
@transaction.atomic
def assign_bed(request, hut_id, room_id):
    hut, room = room_for(request, hut_id, room_id)
    data = body(request)
    if not data or type(data.get('bed_id')) is not int or type(data.get('item_id')) is not int:
        return JsonResponse({'error':'Invalid assignment'},status=400)
    room = Room.objects.select_for_update().get(pk=room.pk)
    bed = get_object_or_404(Bed, pk=data['bed_id'], room=room)
    item = get_object_or_404(ReservationItem.objects.select_related('reservation'),pk=data['item_id'],room=room)
    r = item.reservation
    if r.status not in Reservation.HOLDING:
        return JsonResponse({'error':'Reservation is not active'},status=409)
    if BedAssignment.objects.filter(bed=bed,item=item).exists():
        return JsonResponse({'ok':True})
    if BedAssignment.objects.filter(item=item).count() >= item.beds:
        return JsonResponse({'error':'All reserved beds already assigned'},status=409)
    if conflict_for_bed(bed,item):
        return JsonResponse({'error':'Bed is assigned to another overlapping reservation'},status=409)
    if BedClosure.objects.filter(bed=bed,start__lt=r.check_out,end__gt=r.check_in).exists():
        return JsonResponse({'error':'Bed has a maintenance closure during this stay'},status=409)
    if not capacity_safe(room,r.check_in,r.check_out):
        return JsonResponse({'error':'Room capacity conflict; cannot assign'},status=409)
    BedAssignment.objects.create(bed=bed,item=item)
    return JsonResponse({'ok':True})


@staff_member_required
@require_POST
@transaction.atomic
def unassign_bed(request, hut_id, room_id):
    hut, room = room_for(request, hut_id, room_id)
    data = body(request)
    if not data or type(data.get('bed_id')) is not int or type(data.get('item_id')) is not int:
        return JsonResponse({'error':'Invalid assignment'},status=400)
    room = Room.objects.select_for_update().get(pk=room.pk)
    assignment = get_object_or_404(BedAssignment, bed_id=data['bed_id'], item_id=data['item_id'], bed__room=room, item__room=room)
    assignment.delete()
    return JsonResponse({'ok':True})


@staff_member_required
@require_POST
@transaction.atomic
def close_bed(request, hut_id, room_id):
    hut, room = room_for(request, hut_id, room_id)
    data = body(request)
    if not data or type(data.get('bed_id')) is not int or not isinstance(data.get('start'),str) or not isinstance(data.get('end'),str):
        return JsonResponse({'error':'Invalid closure'},status=400)
    try:
        start,end = date.fromisoformat(data['start']),date.fromisoformat(data['end'])
    except ValueError:
        return JsonResponse({'error':'Invalid dates'},status=400)
    if start < timezone.localdate() or end <= start or (end-start).days > 366:
        return JsonResponse({'error':'Invalid closure dates'},status=400)
    room = Room.objects.select_for_update().get(pk=room.pk)
    bed = get_object_or_404(Bed,pk=data['bed_id'],room=room)
    if BedAssignment.objects.filter(bed=bed,item__reservation__status__in=Reservation.HOLDING,item__reservation__check_in__lt=end,item__reservation__check_out__gt=start).exists():
        return JsonResponse({'error':'Bed is assigned during these dates'},status=409)
    if BedClosure.objects.filter(bed=bed,start__lt=end,end__gt=start).exists():
        return JsonResponse({'error':'Overlapping closure already exists'},status=409)
    closure = BedClosure.objects.create(bed=bed,start=start,end=end,reason=str(data.get('reason',''))[:200])
    if not capacity_safe(room,start,end):
        closure.delete()
        return JsonResponse({'error':'Closure would overbook the room on one or more nights'},status=409)
    return JsonResponse({'ok':True,'closure_id':closure.pk})


@staff_member_required
@require_POST
@transaction.atomic
def reopen_bed(request, hut_id, room_id):
    hut, room = room_for(request, hut_id, room_id)
    data = body(request)
    if not data or type(data.get('closure_id')) is not int:
        return JsonResponse({'error':'Invalid closure'},status=400)
    room = Room.objects.select_for_update().get(pk=room.pk)
    closure = get_object_or_404(BedClosure,pk=data['closure_id'],bed__room=room)
    closure.delete()
    return JsonResponse({'ok':True})
