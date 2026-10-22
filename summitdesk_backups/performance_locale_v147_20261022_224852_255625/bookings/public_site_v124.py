"""Guest-facing hut discovery pages.

This module deliberately reuses the booking service's availability rules.
No reservation writes or new permission rules are introduced here.
"""
from django.db.models import Prefetch, Q
from django.shortcuts import render

from .forms import SearchForm
from .models import Hut, Room
from .services import free_beds


def _directory(request, *, homepage):
    query = request.GET.get("q", "").strip()[:100]
    dates_requested = "check_in" in request.GET or "check_out" in request.GET
    date_form = SearchForm(request.GET if dates_requested else None)
    dates_valid = dates_requested and date_form.is_valid()

    raw_beds = request.GET.get("beds", "1")
    try:
        beds = int(raw_beds)
        if not 1 <= beds <= 30:
            raise ValueError
        beds_error = ""
    except (TypeError, ValueError):
        beds = 1
        beds_error = "Choose between 1 and 30 beds."

    huts_qs = Hut.objects.filter(is_active=True)
    if query:
        huts_qs = huts_qs.filter(Q(name__icontains=query) | Q(location__icontains=query))
    huts = list(huts_qs.order_by("name").prefetch_related(
        Prefetch("rooms", queryset=Room.objects.filter(is_active=True).order_by("position", "name"), to_attr="public_rooms_v124")
    ))

    available_by_room = {}
    if dates_valid:
        rooms = [room for hut in huts for room in hut.public_rooms_v124]
        if rooms:
            available_by_room = free_beds(
                rooms,
                date_form.cleaned_data["check_in"],
                date_form.cleaned_data["check_out"],
            )

    cards = []
    for hut in huts:
        rooms = hut.public_rooms_v124
        capacity = sum(room.capacity for room in rooms)
        free = sum(available_by_room.get(room.pk, 0) for room in rooms) if dates_valid else None
        if dates_valid and not beds_error and free < beds:
            continue
        cards.append({
            "hut": hut,
            "room_count": len(rooms),
            "capacity": capacity,
            "free": free,
            "starting_price": min((room.price_per_night for room in rooms if room.price_per_night > 0), default=None),
        })

    has_search = bool(query or dates_requested or "beds" in request.GET)
    if homepage and not has_search:
        cards = cards[:6]

    return render(request, "bookings/public_home_v124.html" if homepage else "bookings/public_directory_v124.html", {
        "cards": cards,
        "search": date_form,
        "query": query,
        "beds": beds,
        "beds_error": beds_error,
        "dates_valid": dates_valid,
        "dates_requested": dates_requested,
        "check_in": date_form.cleaned_data["check_in"] if dates_valid else None,
        "check_out": date_form.cleaned_data["check_out"] if dates_valid else None,
        "has_search": has_search,
        "homepage": homepage,
        "total_huts": len(huts),
    })


def public_home(request):
    return _directory(request, homepage=True)


def public_huts(request):
    return _directory(request, homepage=False)
