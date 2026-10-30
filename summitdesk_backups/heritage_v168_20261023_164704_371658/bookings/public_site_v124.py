"""The main hut's booking homepage and the information-only hut directory.

Public reservation writes are delegated to the existing validated booking flow.
"""
from django.db.models import Prefetch, Q
from django.shortcuts import render

from .models import Hut, Room


def _directory(request, *, homepage):
    query = request.GET.get("q", "").strip()[:100]
    huts_qs = Hut.objects.filter(is_active=True)
    if query:
        huts_qs = huts_qs.filter(Q(name__icontains=query) | Q(location__icontains=query))
    huts = list(huts_qs.order_by("name").prefetch_related(
        Prefetch("rooms", queryset=Room.objects.filter(is_active=True).order_by("position", "name"), to_attr="public_rooms_v124")
    ))

    from .main_hut_v153 import main_hut
    main = main_hut(request)
    cards = []
    for hut in huts:
        rooms = hut.public_rooms_v124
        cards.append({'hut':hut, 'room_count':len(rooms), 'capacity':sum(room.capacity for room in rooms),
                      'bookable':bool(main and main.pk == hut.pk), 'free':None,
                      'starting_price':min((room.price_per_night for room in rooms if room.price_per_night > 0),default=None)})
    return render(request, "bookings/public_directory_v124.html", {
        "cards":cards, "query":query, "dates_valid":False, "has_search":bool(query),
        "homepage":False, "total_huts":len(huts),
    })



def public_home(request):
    from .main_hut_v153 import main_hut
    from .views import book
    hut = main_hut(request)
    if hut is not None:
        return book(request, hut=hut, template_name='bookings/public_hut_v125.html', homepage=True)
    if request.method == 'POST':
        return render(request, 'bookings/public_unavailable_v153.html', status=403)
    return _directory(request, homepage=False)


def public_huts(request):
    return _directory(request, homepage=False)
