"""Staff-only manual bookings; use the same locked booking service as public reservations."""
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Hut, Reservation, Room
from .services import NotAvailable, create_reservation, free_beds


class ManualBookingForm(forms.Form):
    hut = forms.ModelChoiceField(queryset=Hut.objects.none(), empty_label="Choose a hut")
    check_in = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    check_out = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    name = forms.CharField(max_length=100)
    email = forms.EmailField(required=False, help_text="Optional for walk-in or telephone bookings")
    phone = forms.CharField(max_length=30, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        huts = Hut.objects.filter(is_active=True)
        if not user.is_superuser:
            huts = huts.filter(managers=user)
        self.fields["hut"].queryset = huts.order_by("name")
        if not user.is_superuser and not huts.exists():
            raise PermissionDenied("No active hut is assigned to your account.")
        self.room_fields = []
        # Room quantities are intentionally not Django dynamic fields: they are
        # read only after validating the selected hut, preventing cross-hut POSTs.

    def clean(self):
        data = super().clean()
        start, end = data.get("check_in"), data.get("check_out")
        if start and end:
            today = timezone.localdate()
            if (start < today or end <= start or
                start > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD) or
                (end - start).days > settings.BOOKING_MAX_NIGHTS):
                raise forms.ValidationError("Invalid dates or stay duration.")
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError("Enter at least a phone number or email address.")
        return data


@staff_member_required
def manual_booking(request):
    """Create a confirmed booking within the manager's authorized hut."""
    form = ManualBookingForm(request.POST if request.method == "POST" else None, user=request.user)
    huts = form.fields["hut"].queryset
    chosen = None
    hut_id = request.POST.get("hut") if request.method == "POST" else request.GET.get("hut")
    if hut_id:
        # Never use a raw hut id without applying the authorized queryset.
        chosen = huts.filter(pk=hut_id).first() if str(hut_id).isdigit() else None
        if chosen is None:
            raise PermissionDenied("Hut not permitted.")
    elif huts.count() == 1:
        chosen = huts.first()
        form.fields["hut"].initial = chosen.pk

    rooms = list(Room.objects.filter(hut=chosen, is_active=True).order_by("position", "name")) if chosen else []
    room_rows = []
    start = end = None
    date_form_valid = form.is_valid() if request.method == "POST" else False
    if date_form_valid:
        start, end = form.cleaned_data["check_in"], form.cleaned_data["check_out"]
    elif request.method == "GET":
        try:
            start = forms.DateField().clean(request.GET.get("check_in"))
            end = forms.DateField().clean(request.GET.get("check_out"))
            if start < timezone.localdate() or end <= start or start > timezone.localdate() + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD) or (end-start).days > settings.BOOKING_MAX_NIGHTS:
                start = end = None
        except (forms.ValidationError, TypeError):
            start = end = None

    free = free_beds(rooms, start, end) if rooms and start and end else {}
    for room in rooms:
        raw = request.POST.get(f"beds_{room.pk}", "0") if request.method == "POST" else "0"
        room_rows.append({"room": room, "free": free.get(room.pk), "requested": raw})

    if request.method == "POST" and date_form_valid:
        quantities = {}
        invalid = False
        for row in room_rows:
            raw = row["requested"]
            try:
                count = int(raw)
                if str(count) != raw.strip() or count < 0 or count > row["room"].capacity:
                    raise ValueError
            except (ValueError, TypeError):
                invalid = True
                break
            if count:
                quantities[row["room"].pk] = count
        if invalid:
            form.add_error(None, "Bed quantities must be whole numbers within room capacity.")
        elif not quantities:
            form.add_error(None, "Select at least one bed.")
        elif any(quantities.get(row["room"].pk, 0) > free[row["room"].pk] for row in room_rows):
            form.add_error(None, "Not enough beds available for these dates.")
        else:
            try:
                reservation = create_reservation(
                    check_in=start, check_out=end, beds_by_room=quantities,
                    status=Reservation.Status.CONFIRMED,
                    name=form.cleaned_data["name"],
                    email=form.cleaned_data.get("email", ""),
                    phone=form.cleaned_data.get("phone", ""),
                    notes=form.cleaned_data.get("notes", ""),
                )
            except (NotAvailable, ValidationError, ValueError):
                form.add_error(None, "Booking could not be saved. Check availability and dates.")
            else:
                messages.success(request, f"Manual booking {reservation.code} created.")
                return redirect("bookings:manager_reservations")

    return render(request, "bookings/manual_booking.html", {
        "form": form, "selected_hut": chosen, "room_rows": room_rows,
        "today": timezone.localdate(),
        "dates_ready": bool(start and end),
        "CURRENCY": settings.BOOKING_CURRENCY,
    })
