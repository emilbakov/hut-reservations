"""Stable physical bed positions, scoped to a manager's hut."""
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from bookings.models import Bed, Room
from .bed_management import permitted_hut
from .models import BedMarker, RoomPlacement

@staff_member_required
@require_GET
def layout_page(request, hut_id):
    return render(request, 'floorplans/bed_layout.html', {'hut': permitted_hut(request, hut_id)})

@staff_member_required
@require_GET
def markers(request, hut_id, room_id):
    hut = permitted_hut(request, hut_id)
    room = get_object_or_404(Room, hut=hut, pk=room_id, is_active=True)
    beds = list(Bed.objects.filter(room=room).order_by('number', 'pk').select_related('floor_marker'))
    result = []
    for bed in beds:
        try:
            marker = bed.floor_marker
            position = {'x': marker.x, 'y': marker.y}
        except BedMarker.DoesNotExist:
            position = None
        result.append({'id': bed.pk, 'number': bed.number, 'position': position})
    return JsonResponse({'room': room.name, 'capacity': room.capacity, 'beds': result})

@staff_member_required
@require_POST
@transaction.atomic
def save_markers(request, hut_id, room_id):
    hut = permitted_hut(request, hut_id)
    room = get_object_or_404(Room.objects.select_for_update(), hut=hut, pk=room_id, is_active=True)
    try:
        payload = json.loads(request.body)
        positions = payload['positions']
        if not isinstance(positions, list) or len(positions) > room.capacity:
            raise ValueError
        allowed = set(Bed.objects.filter(room=room).values_list('pk', flat=True))
        ids, coords = set(), set()
        for p in positions:
            if not isinstance(p, dict) or set(p) != {'bed_id', 'x', 'y'}:
                raise ValueError
            bed_id, x, y = p['bed_id'], p['x'], p['y']
            if any(type(v) is not int for v in (bed_id, x, y)) or bed_id not in allowed or not (0 <= x < 8 and 0 <= y < 6) or bed_id in ids or (x, y) in coords:
                raise ValueError
            ids.add(bed_id); coords.add((x, y))
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid bed positions or duplicate markers.'}, status=400)
    # Preserve bed records, reservations, assignments and closures.
    BedMarker.objects.filter(bed__room=room).exclude(bed_id__in=ids).delete()
    for p in positions:
        BedMarker.objects.update_or_create(bed_id=p['bed_id'], defaults={'x': p['x'], 'y': p['y']})
    # Keep legacy editor markers in sync, but stable identity lives in BedMarker.
    placement = RoomPlacement.objects.filter(room=room).first()
    if placement:
        ordered = {p['bed_id']: p for p in positions}
        placement.bed_positions = [{'x': ordered[b.pk]['x'], 'y': ordered[b.pk]['y']} for b in Bed.objects.filter(room=room).order_by('number','pk') if b.pk in ordered]
        placement.save(update_fields=['bed_positions'])
    return JsonResponse({'ok': True})
