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
from django.core.exceptions import PermissionDenied, ValidationError
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import BookingForm, SearchForm
from .models import GuestStay, Hut, Reservation, ReservationItem, Room
from .services import NotAvailable, create_reservation, free_beds, modify_reservation

logger = logging.getLogger(__name__)

def hut_list(request):
    """Homepage showing all active mountain huts."""
    huts = Hut.objects.filter(is_active=True).order_by("name")

    return render(
        request,
        "bookings/hut_list.html",
        {"huts": huts},
    )
def hut_detail(request, slug):
    """Booking page for one selected mountain hut."""
    hut = get_object_or_404(
        Hut,
        slug=slug,
        is_active=True,
    )

    return book(request, hut=hut)


def book(request, hut=None):
    """Pick dates, see available beds and book a selected hut."""

    params = request.POST if request.method == "POST" else request.GET
    has_dates = "check_in" in params
    search = SearchForm(params if has_dates else None)

    context = {
        "search": search,
        "hut": hut,
    }

    if has_dates and search.is_valid():
        check_in = search.cleaned_data["check_in"]
        check_out = search.cleaned_data["check_out"]

        rooms_query = Room.objects.filter(is_active=True)

        if hut is not None:
            rooms_query = rooms_query.filter(hut=hut)

        rooms = list(rooms_query)

        def booking_form():
            return BookingForm(
                request.POST if request.method == "POST" else None,
                rooms=rooms,
                free=free_beds(rooms, check_in, check_out),
            )

        booking = booking_form()

        if request.method == "POST" and booking.is_valid():
            guest = {
                key: booking.cleaned_data[key]
                for key in ("name", "email", "phone", "notes")
            }

            try:
                reservation = create_reservation(
                    check_in=check_in,
                    check_out=check_out,
                    beds_by_room=booking.beds_by_room(),
                    **guest,
                )

            except ValidationError as exc:
                booking.add_error(None, "; ".join(exc.messages))

            except NotAvailable:
                booking = booking_form()

                if booking.is_valid():
                    booking.add_error(
                        None,
                        "Those beds were just taken. Please try again.",
                    )

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



def permitted_hut_selection(request):
    """Superusers see all huts; assigned staff see only their own huts."""
    slug = request.GET.get("hut", "").strip()
    if request.user.is_superuser:
        huts = Hut.objects.all().order_by("name")
        selected = get_object_or_404(huts, slug=slug) if slug else None
        return huts, selected, slug

    huts = Hut.objects.filter(managers=request.user).order_by("name")
    if not huts.exists():
        raise PermissionDenied("No hut is assigned to your account.")
    if slug:
        selected = get_object_or_404(huts, slug=slug)
    elif huts.count() == 1:
        selected = huts.first()
    else:
        # Never expose aggregate data across multiple huts to a manager.
        selected = huts.first()
    return huts, selected, selected.slug


@staff_member_required
def dashboard(request):
    """Staff overview, optionally scoped to one hut."""
    from calendar import monthrange
    from datetime import date
    from decimal import Decimal
    from django.db.models import Prefetch

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        first = date(year, month, 1)
        if not 2000 <= year <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        first = today.replace(day=1)

    last = first.replace(day=monthrange(first.year, first.month)[1])
    after = last + timedelta(days=1)
    prev_month = first - timedelta(days=1)
    next_month = after

    huts, selected_hut, selected_slug = permitted_hut_selection(request)

    room_queryset = Room.objects.filter(is_active=True)
    if selected_hut:
        room_queryset = room_queryset.filter(hut=selected_hut)
    rooms = list(room_queryset)
    capacity = sum(room.capacity for room in rooms)

    # Use only the relevant reservation items, not the reservation's overall
    # bed count or price (which may include other huts in historical data).
    item_queryset = ReservationItem.objects.select_related("room")
    if selected_hut:
        item_queryset = item_queryset.filter(room__hut=selected_hut)

    active = Reservation.objects.filter(status__in=Reservation.HOLDING)
    if selected_hut:
        active = active.filter(items__room__hut=selected_hut).distinct()

    reservations = list(
        active.filter(check_in__lt=after, check_out__gt=first)
        .prefetch_related(Prefetch("items", queryset=item_queryset, to_attr="dashboard_items"))
        .order_by("check_in", "name")
    )

    daily = []
    revenue = Decimal("0")
    booked_nights = 0
    for day_number in range(1, last.day + 1):
        current_day = first.replace(day=day_number)
        occupants = []
        occupied = 0
        day_revenue = Decimal("0")
        for reservation in reservations:
            if reservation.check_in <= current_day < reservation.check_out:
                beds = sum(item.beds for item in reservation.dashboard_items)
                price = sum((item.beds * item.price_per_night for item in reservation.dashboard_items), Decimal("0"))
                if beds:
                    occupied += beds
                    day_revenue += price
                    occupants.append({"reservation": reservation, "beds": beds})
        booked_nights += occupied
        revenue += day_revenue
        daily.append({
            "date": current_day, "occupied": occupied,
            "free": max(capacity - occupied, 0),
            "revenue": day_revenue, "reservations": occupants,
        })

    occupancy = round(booked_nights * 100 / (capacity * len(daily))) if capacity and daily else 0
    upcoming_reservations = list(
        active.filter(check_in__gte=today)
        .prefetch_related(Prefetch("items", queryset=item_queryset, to_attr="dashboard_items"))
        .order_by("check_in", "name")[:20]
    )
    upcoming = [
        {"reservation": reservation, "beds": sum(item.beds for item in reservation.dashboard_items)}
        for reservation in upcoming_reservations
    ]
    today_items = ReservationItem.objects.filter(
        reservation__status__in=Reservation.HOLDING,
        reservation__check_in__lte=today,
        reservation__check_out__gt=today,
    )
    if selected_hut:
        today_items = today_items.filter(room__hut=selected_hut)
    today_occupied = today_items.aggregate(beds=Sum("beds"))["beds"] or 0

    return render(request, "bookings/dashboard.html", {
        "today": today, "huts": huts, "manager_mode": not request.user.is_superuser, "selected_hut": selected_hut,
        "selected_slug": selected_slug,
        "rooms": rooms, "capacity": capacity, "occupied": today_occupied,
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
    """Export reservations for the selected month and optional hut."""
    import csv
    from calendar import monthrange
    from datetime import date
    from decimal import Decimal
    from django.db.models import Prefetch
    from django.http import HttpResponse

    try:
        year = int(request.GET.get("year", timezone.localdate().year))
        month = int(request.GET.get("month", timezone.localdate().month))
        first = date(year, month, 1)
        if not 2000 <= year <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid month"}, status=400)

    _, selected_hut, selected_slug = permitted_hut_selection(request)
    end = first + timedelta(days=monthrange(year, month)[1])

    item_queryset = ReservationItem.objects.select_related("room")
    queryset = Reservation.objects.filter(
        check_in__lt=end, check_out__gt=first
    )
    if selected_hut:
        item_queryset = item_queryset.filter(room__hut=selected_hut)
        queryset = queryset.filter(items__room__hut=selected_hut).distinct()
    queryset = queryset.prefetch_related(
        Prefetch("items", queryset=item_queryset, to_attr="export_items")
    ).order_by("check_in", "pk")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reservations-{year}-{month:02d}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Reference", "Guest", "Email", "Phone", "Arrival", "Departure",
        "Status", "Beds", "Total price", "Currency",
    ])

    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

    for reservation in queryset:
        beds = sum(item.beds for item in reservation.export_items)
        nights = (reservation.check_out - reservation.check_in).days
        total = sum(
            (item.beds * item.price_per_night * nights for item in reservation.export_items),
            Decimal("0"),
        )
        writer.writerow([
            reservation.code, safe(reservation.name), safe(reservation.email),
            safe(reservation.phone), reservation.check_in, reservation.check_out,
            reservation.status, beds, total, settings.BOOKING_CURRENCY,
        ])
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
    custom_confirmation_subject = None
    custom_confirmation_body = None
    from .deposits import single_hut_id
    from .models import HutMessageTemplate, Hut
    from .communications import render_message
    hut_id = single_hut_id(reservation)
    if hut_id and HutMessageTemplate.objects.filter(
        hut_id=hut_id, message_type="confirmation", enabled=True
    ).exists():
        custom_confirmation_subject, custom_confirmation_body = render_message(
            reservation, Hut.objects.get(pk=hut_id), "confirmation"
        )
    body = render_to_string(
        "bookings/email_confirmation.txt",
        {
            "reservation": reservation,
            "link": request.build_absolute_uri(reservation.get_absolute_url()),
            "HUT_NAME": settings.HUT_NAME,
            "CURRENCY": settings.BOOKING_CURRENCY,
        },
    )
    if custom_confirmation_body is not None:
        body = custom_confirmation_body
    recipients = [reservation.email]
    if settings.BOOKING_NOTIFY_EMAIL:
        recipients.append(settings.BOOKING_NOTIFY_EMAIL)
    from .guest_links import append_guest_portal_to_confirmation
    guest_body = append_guest_portal_to_confirmation(request, reservation, body)
    for recipient in recipients:
        try:
            send_mail(custom_confirmation_subject or f"Your reservation at {settings.HUT_NAME}", (guest_body if recipient == reservation.email else body), None, [recipient])
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
    rooms_query = Room.objects.filter(is_active=True)

    hut_slug = request.GET.get("hut")

    if hut_slug:
        hut = get_object_or_404(
            Hut,
            slug=hut_slug,
            is_active=True,
        )
        rooms_query = rooms_query.filter(hut=hut)

    rooms = list(rooms_query)
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
    """Allow changes within the reservation's original hut only."""
    reservation = get_object_or_404(
        Reservation.objects.prefetch_related("items__room"), code=code
    )
    if reservation.status not in Reservation.HOLDING:
        messages.error(request, "Cancelled reservations cannot be modified.")
        return redirect(reservation)

    existing_items = list(reservation.items.all())
    hut_ids = {item.room.hut_id for item in existing_items}
    if len(hut_ids) != 1 or None in hut_ids:
        messages.error(request, "Reservation rooms must belong to one hut. Contact the hut keeper.")
        return redirect(reservation)

    hut_id = next(iter(hut_ids))
    hut = get_object_or_404(Hut, pk=hut_id)
    params = request.POST if request.method == "POST" else request.GET
    initial = {"check_in": reservation.check_in, "check_out": reservation.check_out}
    search = SearchForm(params if "check_in" in params else initial)
    context = {"reservation": reservation, "search": search, "hut": hut}

    if search.is_valid():
        start = search.cleaned_data["check_in"]
        end = search.cleaned_data["check_out"]
        rooms = list(Room.objects.filter(is_active=True, hut_id=hut_id))
        free = free_beds(rooms, start, end, exclude=reservation)
        existing = {item.room_id: item.beds for item in existing_items}
        initial_beds = {f"room_{room.pk}": existing.get(room.pk, 0) for room in rooms}

        # The modification form normally submits dates and beds, not guest details.
        # Populate required BookingForm guest fields from the existing reservation.
        form_data = None
        if request.method == "POST":
            form_data = request.POST.copy()
            for field_name in ("name", "email", "phone", "notes"):
                form_data[field_name] = getattr(reservation, field_name, "") or ""

        booking = BookingForm(
            form_data,
            rooms=rooms,
            free=free,
            initial=initial_beds,
        )

        if request.method == "POST" and booking.is_valid():
            try:
                modify_reservation(
                    code=code,
                    check_in=start,
                    check_out=end,
                    beds_by_room=booking.beds_by_room(),
                )
            except (NotAvailable, ValidationError) as exc:
                booking.add_error(None, "Availability changed or dates are invalid. Please try again.")
            else:
                messages.success(request, "Reservation updated successfully.")
                return redirect(reservation)

        context.update(
            booking=booking,
            check_in=start,
            check_out=end,
            nights=(end - start).days,
            any_free=any(free.values()),
        )

    return render(request, "bookings/modify.html", context)

# --- Hut manager reservation management ---
from django.db import transaction
from django.db.models import F, Q


def manageable_reservations(user):
    """Only complete single-hut bookings in a manager's permitted huts."""
    qs = Reservation.objects.all()
    if user.is_superuser:
        return qs
    if not user.is_staff:
        raise PermissionDenied("Staff access required.")
    allowed = Hut.objects.filter(managers=user)
    if not allowed.exists():
        raise PermissionDenied("No hut is assigned to your account.")
    # A historic booking spanning multiple huts must not be editable by
    # a manager who sees only one part of it.
    return (qs.annotate(
        manager_total=Count("items", distinct=True),
        manager_allowed=Count(
            "items", filter=Q(items__room__hut__in=allowed), distinct=True
        ),
    ).filter(manager_total__gt=0, manager_total=F("manager_allowed")))


@staff_member_required
def manager_reservations(request):
    """Searchable bookings scoped to the selected authorized hut."""
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    qs = manageable_reservations(request.user)
    if selected_hut:
        qs = qs.filter(items__room__hut=selected_hut)
    qs = qs.distinct().prefetch_related("items__room__hut").order_by("-check_in", "-created")

    search = request.GET.get("q", "").strip()[:120]
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(email__icontains=search)
            | Q(code__icontains=search)
        )
    status = request.GET.get("status", "").strip()
    if status in dict(Reservation.Status.choices):
        qs = qs.filter(status=status)
    else:
        status = ""

    from django.core.paginator import Paginator
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "bookings/manager_reservations.html", {
        "page": page, "huts": huts, "selected_hut": selected_hut,
        "selected_slug": selected_slug, "manager_mode": not request.user.is_superuser,
        "q": search, "status_filter": status,
        "statuses": Reservation.Status.choices,
    })


@staff_member_required
@require_POST
def manager_reservation_action(request, code):
    """Confirm/cancel only a booking wholly within the manager's huts."""
    action = request.POST.get("action")
    if action not in {"confirm", "cancel"}:
        return JsonResponse({"error": "Unknown action"}, status=400)

    with transaction.atomic():
        reservation = get_object_or_404(
            manageable_reservations(request.user).select_for_update(), code=code
        )
        # Never change bookings spanning multiple huts from this interface.
        hut_ids = set(reservation.items.values_list("room__hut_id", flat=True))
        if len(hut_ids) != 1 or None in hut_ids:
            raise PermissionDenied("This reservation requires administrator review.")

        if action == "confirm":
            if reservation.status != Reservation.Status.PENDING:
                messages.error(request, "Only pending reservations can be confirmed.")
            else:
                reservation.status = Reservation.Status.CONFIRMED
                reservation.save(update_fields=["status"])
                messages.success(request, "Reservation confirmed.")
        else:
            if reservation.status == Reservation.Status.CANCELLED:
                messages.error(request, "Reservation is already cancelled.")
            else:
                reservation.status = Reservation.Status.CANCELLED
                reservation.save(update_fields=["status"])
                messages.success(request, "Reservation cancelled; beds are available again.")

    # Fixed destination avoids untrusted redirect parameters.
    return redirect("bookings:manager_reservations")


# --- Daily guest arrivals and departures ---
@staff_member_required
@require_GET
def manager_stays(request):
    """Operational arrival/departure list for one authorized hut."""
    from datetime import date
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    raw_date = request.GET.get("date", "")
    try:
        target_date = date.fromisoformat(raw_date) if raw_date else timezone.localdate()
    except ValueError:
        return JsonResponse({"error": "Invalid date"}, status=400)

    qs = manageable_reservations(request.user).filter(
        status=Reservation.Status.CONFIRMED
    )
    if selected_hut:
        qs = qs.filter(items__room__hut=selected_hut)
    qs = qs.distinct().select_related("guest_stay").prefetch_related("items__room")

    # Show scheduled arrivals/departures plus still-in-house guests.
    arriving = list(qs.filter(check_in=target_date).order_by("name"))
    departing = list(qs.filter(check_out=target_date).order_by("name"))
    in_house = list(qs.filter(
        guest_stay__checked_in_at__isnull=False,
        guest_stay__checked_out_at__isnull=True,
    ).order_by("check_out", "name"))
    return render(request, "bookings/manager_stays.html", {
        "huts": huts, "selected_hut": selected_hut, "selected_slug": selected_slug,
        "manager_mode": not request.user.is_superuser,
        "target_date": target_date, "arriving": arriving,
        "departing": departing, "in_house": in_house,
    })


@staff_member_required
@require_POST
def manager_stay_action(request, code):
    """Record actual check-in/out with authorization and concurrency protection."""
    action = request.POST.get("action")
    if action not in {"check_in", "check_out"}:
        return JsonResponse({"error": "Unknown action"}, status=400)

    with transaction.atomic():
        reservation = get_object_or_404(
            manageable_reservations(request.user).select_for_update(), code=code
        )
        hut_ids = set(reservation.items.values_list("room__hut_id", flat=True))
        if len(hut_ids) != 1 or None in hut_ids:
            raise PermissionDenied("This booking needs administrator review.")
        if reservation.status != Reservation.Status.CONFIRMED:
            return JsonResponse({"error": "Only confirmed bookings may be checked in/out."}, status=409)
        now = timezone.now()
        if action == "check_in" and timezone.localdate() < reservation.check_in:
            return JsonResponse({"error": "Cannot check in before the arrival date."}, status=409)
        stay, _ = GuestStay.objects.select_for_update().get_or_create(reservation=reservation)
        if action == "check_in":
            if stay.checked_in_at is not None:
                return JsonResponse({"error": "Already checked in."}, status=409)
            stay.checked_in_at = now
            stay.checked_in_by = request.user
            stay.save(update_fields=["checked_in_at", "checked_in_by"])
            messages.success(request, "Guest checked in.")
        else:
            if stay.checked_in_at is None or stay.checked_out_at is not None:
                return JsonResponse({"error": "Guest must be checked in and not yet checked out."}, status=409)
            stay.checked_out_at = now
            stay.checked_out_by = request.user
            stay.save(update_fields=["checked_out_at", "checked_out_by"])
            messages.success(request, "Guest checked out.")
    return redirect("bookings:manager_stays")
