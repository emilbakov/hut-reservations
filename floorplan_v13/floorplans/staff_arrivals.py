"""V13 arrivals/departures workspace using existing GuestStay records."""
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from bookings.models import Reservation, ReservationItem, GuestStay
from .bed_management import permitted_hut


@staff_member_required
@require_http_methods(['GET', 'POST'])
def staff_arrivals(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ('check_in', 'check_out'):
            messages.error(request, 'Unknown action.')
            return redirect('floorplans:staff_arrivals', hut_id=hut.pk)
        try:
            reservation_id = int(request.POST.get('reservation_id', ''))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid reservation.')
            return redirect('floorplans:staff_arrivals', hut_id=hut.pk)
        with transaction.atomic():
            reservation = get_object_or_404(
                Reservation.objects.select_for_update().filter(items__room__hut=hut).distinct(),
                pk=reservation_id,
            )
            if reservation.status != 'confirmed':
                messages.error(request, 'Only confirmed reservations can be checked in or out.')
            elif action == 'check_in':
                if not (reservation.check_in <= today < reservation.check_out):
                    messages.error(request, 'Check-in is allowed only during the booked stay.')
                else:
                    stay, _ = GuestStay.objects.select_for_update().get_or_create(reservation=reservation)
                    if stay.checked_in_at or stay.checked_out_at:
                        messages.warning(request, 'This reservation already has a recorded stay event.')
                    else:
                        stay.checked_in_at = timezone.now()
                        stay.checked_in_by = request.user
                        stay.save(update_fields=['checked_in_at', 'checked_in_by'])
                        messages.success(request, 'Guest checked in.')
            else:
                stay = GuestStay.objects.select_for_update().filter(reservation=reservation).first()
                if not stay or not stay.checked_in_at:
                    messages.error(request, 'Check in the guest before recording checkout.')
                elif stay.checked_out_at:
                    messages.warning(request, 'Checkout was already recorded.')
                else:
                    stay.checked_out_at = timezone.now()
                    stay.checked_out_by = request.user
                    stay.save(update_fields=['checked_out_at', 'checked_out_by'])
                    messages.success(request, 'Guest checked out.')
        target = request.POST.get('day', '')
        try:
            selected = date.fromisoformat(target)
            if abs((selected - today).days) <= 366:
                return redirect(f"{request.path}?day={selected.isoformat()}")
        except ValueError:
            pass
        return redirect('floorplans:staff_arrivals', hut_id=hut.pk)

    try:
        day = date.fromisoformat(request.GET.get('day', ''))
        if abs((day - today).days) > 366:
            day = today
    except ValueError:
        day = today
    search = request.GET.get('q', '').strip()[:100]
    items = ReservationItem.objects.filter(
        room__hut=hut,
        reservation__status__in=['pending', 'confirmed'],
    ).filter(Q(reservation__check_in=day) | Q(reservation__check_out=day) |
             Q(reservation__check_in__lt=day, reservation__check_out__gt=day))\
        .select_related('room', 'reservation', 'reservation__guest_stay')\
        .order_by('reservation__check_in', 'reservation__name', 'room__position')
    if search:
        items = items.filter(Q(reservation__name__icontains=search) | Q(reservation__code__icontains=search))
    grouped = {}
    for item in items:
        r = item.reservation
        if r.pk not in grouped:
            stay = getattr(r, 'guest_stay', None)
            state = ('Checked out' if stay and stay.checked_out_at else
                     'Checked in' if stay and stay.checked_in_at else
                     'Awaiting arrival')
            grouped[r.pk] = {'reservation': r, 'rooms': [], 'beds': 0, 'state': state,
                             'is_arrival': r.check_in == day, 'is_departure': r.check_out == day,
                             'can_check_in': day == today and r.status == 'confirmed' and
                             r.check_in <= today < r.check_out and state == 'Awaiting arrival',
                             'can_check_out': day == today and r.status == 'confirmed' and
                             state == 'Checked in'}
        grouped[r.pk]['rooms'].append(f'{item.room.name} ({item.beds})')
        grouped[r.pk]['beds'] += item.beds
    records = list(grouped.values())
    arrivals = [r for r in records if r['is_arrival']]
    departures = [r for r in records if r['is_departure']]
    in_house = [r for r in records if not r['is_arrival'] and not r['is_departure']]
    return render(request, 'floorplans/staff_arrivals.html', {
        'hut': hut, 'day': day, 'today': today,
        'previous': day - timedelta(days=1), 'next': day + timedelta(days=1),
        'arrivals': arrivals, 'departures': departures, 'in_house': in_house,
        'arrival_beds': sum(r['beds'] for r in arrivals),
        'departure_beds': sum(r['beds'] for r in departures),
        'in_house_beds': sum(r['beds'] for r in in_house), 'search': search,
    })
