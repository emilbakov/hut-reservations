import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import BookingForm, SearchForm
from .models import Reservation, Room
from .services import NotAvailable, create_reservation, free_beds, modify_reservation

logger = logging.getLogger(__name__)


def book(request):
    """One page: pick dates, see what is free, choose beds and book."""
    params = request.POST if request.method == "POST" else request.GET
    has_dates = "check_in" in params
    search = SearchForm(params if has_dates else None)
    context = {"search": search}

    if has_dates and search.is_valid():
        check_in = search.cleaned_data["check_in"]
        check_out = search.cleaned_data["check_out"]
        rooms = list(Room.objects.filter(is_active=True))

        def booking_form():
            return BookingForm(
                request.POST if request.method == "POST" else None,
                rooms=rooms,
                free=free_beds(rooms, check_in, check_out),
            )

        booking = booking_form()
        if request.method == "POST" and booking.is_valid():
            guest = {k: booking.cleaned_data[k] for k in ("name", "email", "phone", "notes")}
            try:
                reservation = create_reservation(
                    check_in=check_in,
                    check_out=check_out,
                    beds_by_room=booking.beds_by_room(),
                    **guest,
                )
            except NotAvailable:
                # Someone else booked in the meantime: show what is left now.
                booking = booking_form()
                if booking.is_valid():
                    booking.add_error(None, "Those beds were just taken. Please try again.")
            else:
                send_confirmation(request, reservation)
                return redirect(reservation)

        context.update(
            booking=booking,
            check_in=check_in,
            check_out=check_out,
            nights=(check_out - check_in).days,
            any_free=any(booking.free.values()),
        )

    return render(request, "bookings/book.html", context)


@staff_member_required
def dashboard(request):
    """Operational overview; all monetary figures use stored booking prices."""
    from calendar import monthrange
    from datetime import date
    from decimal import Decimal
    from django.db.models import Prefetch

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        first = date(year, month, 1)
    except (ValueError, TypeError):
        first = today.replace(day=1)
    if first.year < 2000 or first.year > 2100:
        first = today.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])
    after = last + timedelta(days=1)
    prev_month = first - timedelta(days=1)
    next_month = after
    rooms = list(Room.objects.filter(is_active=True))
    active = Reservation.objects.filter(status__in=Reservation.HOLDING)
    reservations = list(active.filter(check_in__lt=after, check_out__gt=first)
                        .prefetch_related("items__room").order_by("check_in", "name"))
    daily = []
    revenue = Decimal("0")
    booked_nights = 0
    for day_number in range(1, last.day + 1):
        day = first.replace(day=day_number)
        occupants = []
        occupied = 0
        day_revenue = Decimal("0")
        for reservation in reservations:
            if reservation.check_in <= day < reservation.check_out:
                beds = reservation.total_beds
                occupied += beds
                day_revenue += sum(item.beds * item.price_per_night for item in reservation.items.all())
                occupants.append(reservation)
        booked_nights += occupied
        revenue += day_revenue
        daily.append({"date": day, "occupied": occupied,
                      "free": max(sum(r.capacity for r in rooms) - occupied, 0),
                      "revenue": day_revenue, "reservations": occupants})
    capacity = sum(r.capacity for r in rooms)
    occupancy = round(booked_nights * 100 / (capacity * len(daily))) if capacity and daily else 0
    upcoming = list(active.filter(check_in__gte=today).prefetch_related("items__room")
                    .order_by("check_in", "name")[:20])
    today_occupied = active.filter(check_in__lte=today, check_out__gt=today).aggregate(
        beds=Sum("items__beds"))["beds"] or 0
    return render(request, "bookings/dashboard.html", {
        "today": today, "rooms": rooms, "capacity": capacity, "occupied": today_occupied,
        "arrival_count": active.filter(check_in=today).count(),
        "departure_count": active.filter(check_out=today).count(),
        "pending_count": active.filter(status=Reservation.Status.PENDING).count(),
        "upcoming": upcoming, "daily": daily, "month": first,
        "previous_year": prev_month.year, "previous_month": prev_month.month,
        "next_year": next_month.year, "next_month": next_month.month,
        "revenue": revenue, "occupancy": occupancy,
        "reservation_count": len(reservations), "booked_nights": booked_nights,
        "currency": settings.BOOKING_CURRENCY,
    })


@staff_member_required
@require_GET
def dashboard_export(request):
    """CSV of reservations overlapping the requested month (staff only)."""
    import csv
    from calendar import monthrange
    from datetime import date
    from django.http import HttpResponse
    try:
        year = int(request.GET.get("year", timezone.localdate().year))
        month = int(request.GET.get("month", timezone.localdate().month))
        first = date(year, month, 1)
        if not 2000 <= year <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid month"}, status=400)
    end = first + timedelta(days=monthrange(year, month)[1])
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reservations-{year}-{month:02d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Reference", "Guest", "Email", "Phone", "Arrival", "Departure",
                     "Status", "Beds", "Total price", "Currency"])
    queryset = (Reservation.objects.filter(check_in__lt=end, check_out__gt=first)
                .prefetch_related("items").order_by("check_in", "pk"))
    for reservation in queryset.iterator(chunk_size=200):
        # Prevent spreadsheet formula injection in exported guest-entered fields.
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        writer.writerow([reservation.code, safe(reservation.name), safe(reservation.email),
                         safe(reservation.phone), reservation.check_in, reservation.check_out,
                         reservation.status, reservation.total_beds, reservation.total_price,
                         settings.BOOKING_CURRENCY])
    return response


def reservation_detail(request, code):

    reservation = get_object_or_404(Reservation.objects.prefetch_related("items__room"), code=code)
    return render(request, "bookings/reservation.html", {"reservation": reservation})


@require_POST
def reservation_cancel(request, code):
    reservation = get_object_or_404(Reservation, code=code)
    if reservation.status != Reservation.Status.CANCELLED:
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status"])
        messages.success(request, "Your reservation has been cancelled.")
    return redirect(reservation)


def send_confirmation(request, reservation):
    """Email the guest (and the hut keeper, if configured). A mail failure
    must never lose a booking that is already saved, so errors are logged."""
    body = render_to_string(
        "bookings/email_confirmation.txt",
        {
            "reservation": reservation,
            "link": request.build_absolute_uri(reservation.get_absolute_url()),
            "HUT_NAME": settings.HUT_NAME,
            "CURRENCY": settings.BOOKING_CURRENCY,
        },
    )
    recipients = [reservation.email]
    if settings.BOOKING_NOTIFY_EMAIL:
        recipients.append(settings.BOOKING_NOTIFY_EMAIL)
    for recipient in recipients:
        try:
            send_mail(f"Your reservation at {settings.HUT_NAME}", body, None, [recipient])
        except Exception:
            logger.exception("Could not send confirmation for %s", reservation.code)


@require_GET
def availability_calendar(request):
    """Return per-day available beds; never expose guest information."""
    from datetime import date
    from calendar import monthrange
    try:
        year = int(request.GET.get("year", ""))
        month = int(request.GET.get("month", ""))
        first = date(year, month, 1)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Supply a valid year and month."}, status=400)
    today = timezone.localdate()
    if first > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD) or (year, month) < (today.year, today.month):
        return JsonResponse({"error": "Month outside booking window."}, status=400)
    rooms = list(Room.objects.filter(is_active=True))
    days = []
    for day in range(1, monthrange(year, month)[1] + 1):
        start = date(year, month, day)
        if start < today or start > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD):
            continue
        remaining = free_beds(rooms, start, start + timedelta(days=1))
        days.append({"date": start.isoformat(), "free_beds": sum(remaining.values()),
                     "rooms": {str(r.pk): remaining[r.pk] for r in rooms}})
    return JsonResponse({"days": days, "capacity": sum(r.capacity for r in rooms)})


def reservation_modify(request, code):
    reservation = get_object_or_404(Reservation.objects.prefetch_related("items__room"), code=code)
    if reservation.status not in Reservation.HOLDING:
        messages.error(request, "Cancelled reservations cannot be modified.")
        return redirect(reservation)
    params = request.POST if request.method == "POST" else request.GET
    initial = {"check_in": reservation.check_in, "check_out": reservation.check_out}
    search = SearchForm(params if "check_in" in params else initial)
    context = {"reservation": reservation, "search": search}
    if search.is_valid():
        start, end = search.cleaned_data["check_in"], search.cleaned_data["check_out"]
        rooms = list(Room.objects.filter(is_active=True))
        free = free_beds(rooms, start, end, exclude=reservation)
        existing = {item.room_id: item.beds for item in reservation.items.all()}
        initial_beds = {f"room_{r.pk}": existing.get(r.pk, 0) for r in rooms}
        booking = BookingForm(request.POST if request.method == "POST" else None,
                              rooms=rooms, free=free, initial=initial_beds)
        if request.method == "POST" and booking.is_valid():
            try:
                modify_reservation(code=code, check_in=start, check_out=end,
                                   beds_by_room=booking.beds_by_room())
            except (NotAvailable, ValidationError) as exc:
                booking.add_error(None, "Availability changed or dates are invalid. Please try again.")
            else:
                messages.success(request, "Reservation updated successfully.")
                return redirect(reservation)
        context.update(booking=booking, check_in=start, check_out=end,
                       nights=(end-start).days, any_free=any(free.values()))
    return render(request, "bookings/modify.html", context)
