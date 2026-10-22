"""V15: staff booking form; delegates all availability and locking to bookings.services."""
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from bookings.forms import BookingForm
from bookings.models import Room
from bookings.services import NotAvailable, create_reservation, free_beds
from bookings.staff_booking_ui_v121 import availability_summary
from bookings.booking_calendar_v122 import booking_month
from .bed_management import permitted_hut

@login_required(login_url="/staff/login/")
@require_http_methods(["GET", "POST"])
def staff_new_booking(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    params = request.POST if request.method == "POST" else request.GET
    raw_start = params.get("check_in", today.isoformat())
    raw_end = params.get("check_out", (today + timedelta(days=1)).isoformat())
    from datetime import date
    try:
        start, end = date.fromisoformat(raw_start), date.fromisoformat(raw_end)
        valid_dates = (today <= start <= today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD)
                       and start < end and (end - start).days <= settings.BOOKING_MAX_NIGHTS)
    except (ValueError, TypeError, OverflowError):
        valid_dates = False
        start = end = None
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by("position", "pk"))
    free = free_beds(rooms, start, end) if valid_dates else {r.pk: 0 for r in rooms}
    form = BookingForm(request.POST if request.method == "POST" and valid_dates else None,
                       rooms=rooms, free=free)
    error = None
    if request.method == "POST":
        if not valid_dates:
            error = "Invalid dates. Check the booking horizon and maximum stay length."
        elif form.is_valid():
            guest = {key: form.cleaned_data[key] for key in ("name", "email", "phone", "notes")}
            try:
                reservation = create_reservation(check_in=start, check_out=end,
                    beds_by_room=form.beds_by_room(), **guest)
            except (ValidationError, NotAvailable, ValueError) as exc:
                error = str(exc)
            else:
                if request.user.is_staff:
                    return redirect("floorplans:staff_calendar", hut_id=hut.pk)
                return redirect("floorplans:staff_hub", hut_id=hut.pk)
    room_rows = []
    for room, available, field in form.rows():
        if field:
            form.fields[form.field_name(room)].widget.attrs["id"] = f"sd-bed-{room.pk}"
        room_rows.append({"room": room, "free": available, "field": field,
                          "unavailable": max(0, room.capacity - available)})
    return render(request, "bookings/staff_booking_v121.html", {
        "hut": hut, "selected_hut": hut, "form": form, "rooms": rooms,
        "room_rows": room_rows, "booking_mode": "property",
        "dates_action": request.path, "booking_action": request.path,
        "check_in_value": raw_start, "check_out_value": raw_end,
        "date_error": error or ("Invalid dates. Check the booking horizon and stay length."
                                if not valid_dates else None),
        "today_iso": today.isoformat(),
        "availability": availability_summary(rooms, free, start if valid_dates else None, end if valid_dates else None),
        "booking_calendar": booking_month(rooms, start if valid_dates else None,
            end if valid_dates else None, today=today,
            month_value=request.POST.get("cal_month") if request.method == "POST" else request.GET.get("cal_month")),
        "currency": settings.BOOKING_CURRENCY,
    })
