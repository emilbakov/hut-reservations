import json
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from bookings.models import Hut, Room
from bookings.services import free_beds
from .models import RoomPlacement, FloorFeature

GRID_W, GRID_H = 16, 12

def permitted_hut(request, hut_id):
    qs = Hut.objects.filter(is_active=True)
    if not request.user.is_superuser:
        qs = qs.filter(managers=request.user)
    return get_object_or_404(qs, pk=hut_id)

def serialize_rooms(hut):
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by("position", "pk").select_related("floor_placement"))
    result = []
    for i, room in enumerate(rooms):
        try:
            p = room.floor_placement
        except RoomPlacement.DoesNotExist:
            p = None
        result.append({"id": room.pk, "name": room.name, "capacity": room.capacity,
                       "floor": p.floor if p else 0, "x": p.x if p else (i % 7) * 2,
                       "y": p.y if p else (i // 7) * 2, "width": p.width if p else 2,
                       "height": p.height if p else 2, "beds": p.bed_positions if p else []})
    return result

@staff_member_required
@ensure_csrf_cookie
@require_GET
def editor(request, hut_id):
    hut = permitted_hut(request, hut_id)
    return render(request, "floorplans/editor.html", {"hut": hut})

@staff_member_required
@require_GET
def data(request, hut_id):
    hut = permitted_hut(request, hut_id)
    return JsonResponse({"hut": hut.name, "rooms": serialize_rooms(hut), "width": GRID_W, "height": GRID_H, "features": list(FloorFeature.objects.filter(hut=hut).values("floor", "kind", "x", "y", "width", "height"))})

@staff_member_required
@require_POST
@transaction.atomic
def save(request, hut_id):
    hut = permitted_hut(request, hut_id)
    try:
        payload = json.loads(request.body)
        placements = payload["rooms"]
        if not isinstance(placements, list) or len(placements) > 200:
            raise ValueError
        permitted = set(Room.objects.filter(hut=hut, is_active=True).values_list("pk", flat=True))
        if {item["id"] for item in placements} != permitted or len(placements) != len(permitted):
            raise ValueError
        features = payload.get("features", [])
        if not isinstance(features, list) or len(features) > 150:
            raise ValueError
        validated_features = []
        for item in features:
            if not isinstance(item, dict) or item.get("kind") not in {"stairs", "corridor", "door"}:
                raise ValueError
            vals = [item[k] for k in ("floor", "x", "y", "width", "height")]
            if any(type(v) is not int for v in vals):
                raise ValueError
            f, x, y, w, h = vals
            if not (-2 <= f <= 10 and 0 <= x < GRID_W and 0 <= y < GRID_H and 1 <= w <= 8 and 1 <= h <= 6 and x+w <= GRID_W and y+h <= GRID_H):
                raise ValueError
            validated_features.append((item["kind"], f, x, y, w, h))
        # Visual bed coordinates are not reservation assignments. Booking remains
        # room-level until the underlying reservation schema supports bed IDs.
        capacities = dict(Room.objects.filter(hut=hut, is_active=True).values_list("pk", "capacity"))
        bed_layouts = {}
        for item in placements:
            rid = item.get("id")
            if type(rid) is not int or rid not in capacities:
                raise ValueError
            positions = item.get("beds", [])
            if not isinstance(positions, list) or len(positions) > capacities[rid]:
                raise ValueError
            seen = set()
            for bed in positions:
                if not isinstance(bed, dict) or set(bed) != {"x", "y"}:
                    raise ValueError
                x, y = bed["x"], bed["y"]
                if type(x) is not int or type(y) is not int or not (0 <= x < 8 and 0 <= y < 6) or (x, y) in seen:
                    raise ValueError
                seen.add((x, y))
            bed_layouts[rid] = positions
        validated = []
        for item in placements:
            vals = [item[k] for k in ("id", "floor", "x", "y", "width", "height")]
            if any(type(v) is not int for v in vals):
                raise ValueError
            rid, floor, x, y, w, h = vals
            if not (-2 <= floor <= 10 and 0 <= x < GRID_W and 0 <= y < GRID_H and 1 <= w <= 6 and 1 <= h <= 5 and x+w <= GRID_W and y+h <= GRID_H):
                raise ValueError
            validated.append((rid, floor, x, y, w, h))
        for i, (_, f, x, y, w, h) in enumerate(validated):
            for _, f2, x2, y2, w2, h2 in validated[i+1:]:
                if f == f2 and x < x2+w2 and x+w > x2 and y < y2+h2 and y+h > y2:
                    return JsonResponse({"error": "Rooms cannot overlap on the same floor."}, status=400)
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"error": "Invalid floor plan."}, status=400)
    for rid, floor, x, y, w, h in validated:
        RoomPlacement.objects.update_or_create(room_id=rid, defaults={"floor":floor,"x":x,"y":y,"width":w,"height":h,"bed_positions":bed_layouts[rid]})
    FloorFeature.objects.filter(hut=hut).delete()
    FloorFeature.objects.bulk_create([FloorFeature(hut=hut, kind=k, floor=f, x=x, y=y, width=w, height=h) for k,f,x,y,w,h in validated_features])
    return JsonResponse({"ok": True})

@staff_member_required
@require_GET
def availability(request, hut_id):
    hut = permitted_hut(request, hut_id)
    try:
        start, end = date.fromisoformat(request.GET["check_in"]), date.fromisoformat(request.GET["check_out"])
        today = timezone.localdate()
        if start < today or end <= start or start > today+timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD) or (end-start).days > settings.BOOKING_MAX_NIGHTS:
            raise ValueError
    except (ValueError, KeyError):
        return JsonResponse({"error": "Invalid dates"}, status=400)
    rooms = list(Room.objects.filter(hut=hut, is_active=True))
    free = free_beds(rooms, start, end)
    return JsonResponse({"rooms": {str(r.pk): free[r.pk] for r in rooms}})


@staff_member_required
@require_GET
def availability_map(request, hut_id):
    hut = permitted_hut(request, hut_id)
    return render(request, "floorplans/availability_map.html", {
        "hut": hut,
        "today_iso": timezone.localdate().isoformat(),
    })
