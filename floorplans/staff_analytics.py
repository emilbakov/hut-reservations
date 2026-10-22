"""SummitDesk v34 — hut-scoped reservation analytics."""
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from bookings.models import BedClosure, ReservationItem, Room
from .staff_tasks import access

MAX_DAYS = 366


def overlap(start, end, period_start, period_end):
    """All end dates are exclusive."""
    return max(0, (min(end, period_end) - max(start, period_start)).days)


@login_required
@require_GET
def staff_analytics(request, hut_id):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden("Only hut managers may view analytics.")

    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get("from") or today.replace(day=1).isoformat())
        end_day = date.fromisoformat(request.GET.get("to") or today.isoformat())
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Dates must be YYYY-MM-DD")
    if end_day < start or (end_day - start).days >= MAX_DAYS:
        return HttpResponseBadRequest("Date range must be 1 to 366 days")
    end = end_day + timedelta(days=1)
    days = (end - start).days

    # Only currently active rooms are included; capacity is a current snapshot.
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by("position", "pk"))
    room_ids = [r.pk for r in rooms]
    items = ReservationItem.objects.filter(
        room_id__in=room_ids,
        reservation__check_in__lt=end,
        reservation__check_out__gt=start,
    ).select_related("reservation")
    counts = dict(total=0, confirmed=0, pending=0, cancelled=0)
    reservation_ids = set()
    confirmed_by_room = defaultdict(int)
    held_by_room = defaultdict(int)
    daily_confirmed = defaultdict(int)
    for item in items:
        reservation = item.reservation
        if reservation.pk not in reservation_ids:
            reservation_ids.add(reservation.pk)
            counts["total"] += 1
            if reservation.status in counts:
                counts[reservation.status] += 1
        nights = overlap(reservation.check_in, reservation.check_out, start, end)
        if reservation.status == "confirmed":
            confirmed_by_room[item.room_id] += item.beds * nights
            night = max(start, reservation.check_in)
            last = min(end, reservation.check_out)
            while night < last:
                daily_confirmed[night] += item.beds
                night += timedelta(days=1)
        elif reservation.status == "pending":
            held_by_room[item.room_id] += item.beds * nights

    # Deduplicate overlapping maintenance closures on the same bed and night.
    blocked = defaultdict(set)
    closures = BedClosure.objects.filter(
        bed__room_id__in=room_ids, start__lt=end, end__gt=start
    ).values_list("bed__room_id", "bed_id", "start", "end")
    for room_id, bed_id, closure_start, closure_end in closures:
        night = max(start, closure_start)
        last = min(end, closure_end)
        while night < last:
            blocked[room_id].add((bed_id, night))
            night += timedelta(days=1)

    room_stats = []
    total_available = total_occupied = total_held = total_closed = 0
    for room in rooms:
        closed = len(blocked[room.pk])
        available = max(0, room.capacity * days - closed)
        occupied = confirmed_by_room[room.pk]
        held = held_by_room[room.pk]
        room_stats.append({
            "name": room.name, "capacity": room.capacity,
            "available": available, "closed": closed,
            "occupied": occupied, "held": held,
            "rate": round(occupied * 100 / available, 1) if available else 0,
        })
        total_available += available
        total_occupied += occupied
        total_held += held
        total_closed += closed

    trend = []
    night = start
    while night < end:
        trend.append({"day": night.isoformat(), "occupied": daily_confirmed[night]})
        night += timedelta(days=1)
    return render(request, "floorplans/staff_analytics.html", {
        "hut": hut, "start": start.isoformat(), "end": end_day.isoformat(),
        "days": days, "counts": counts, "rooms": room_stats,
        "trend": trend, "total_available": total_available,
        "total_occupied": total_occupied, "total_held": total_held,
        "total_closed": total_closed,
        "occupancy_rate": round(total_occupied * 100 / total_available, 1) if total_available else 0,
    })
