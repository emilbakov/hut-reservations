"""V16 hut-scoped staff reservation detail and guest contact editor.

Date, quantity, status, payment and physical-bed changes remain delegated to
existing validated workflows; this view does not change inventory.
"""
from django import forms
from django.core.exceptions import ValidationError
from bookings.services import modify_reservation, NotAvailable
from bookings.models import Room, BedAssignment
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from bookings.models import Reservation, ReservationItem
from .bed_management import permitted_hut


class GuestContactForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ("name", "email", "phone", "notes")
        widgets = {
            "name": forms.TextInput(attrs={"class": "field"}),
            "email": forms.EmailInput(attrs={"class": "field"}),
            "phone": forms.TextInput(attrs={"class": "field"}),
            "notes": forms.Textarea(attrs={"class": "field", "rows": 3}),
        }




class StayEditForm(forms.Form):
    check_in = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "field"}))
    check_out = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "field"}))
    # A room transfer can be achieved by setting the previous room to 0 and another room to >0.
    def __init__(self, *args, rooms, **kwargs):
        super().__init__(*args, **kwargs)
        for room in rooms:
            self.fields[f"room_{room.pk}"] = forms.IntegerField(
                min_value=0, max_value=room.capacity, required=True,
                label=f"{room.name} (capacity {room.capacity})",
                widget=forms.NumberInput(attrs={"class": "field", "min": 0, "max": room.capacity}),
            )


def has_physical_assignments(reservation):
    return BedAssignment.objects.filter(item__reservation=reservation).exists()

@staff_member_required
@require_http_methods(["GET", "POST"])
def staff_reservation(request, hut_id, code):
    hut = permitted_hut(request, hut_id)
    # Scope through items to prevent cross-hut reservation disclosure.
    reservation = get_object_or_404(
        Reservation.objects.filter(items__room__hut=hut).distinct(), code=code
    )
    # A reservation can span huts in older data; never display/edit it in one hut's workspace.
    if ReservationItem.objects.filter(reservation=reservation).exclude(room__hut=hut).exists():
        raise Http404("Reservation spans multiple huts; use the existing reservation workflow.")

    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by("position", "pk"))
    saved = request.GET.get("saved") == "1"
    updated = request.GET.get("updated") == "1"
    status_changed = request.GET.get("status_changed") == "1"
    form = GuestContactForm(request.POST if request.POST.get("action") == "contact" else None, instance=reservation)
    stay_initial = {"check_in": reservation.check_in, "check_out": reservation.check_out}
    stay_initial.update({f"room_{room.pk}": 0 for room in rooms})
    stay_initial.update({f"room_{item.room_id}": item.beds for item in reservation.items.all()})
    stay_form = StayEditForm(request.POST if request.POST.get("action") == "stay" else None, rooms=rooms, initial=stay_initial)
    error_message = None
    if request.method == "POST" and request.POST.get("action") == "contact" and form.is_valid():
        with transaction.atomic():
            locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
            for field in form.Meta.fields:
                setattr(locked, field, form.cleaned_data[field])
            locked.save(update_fields=list(form.Meta.fields))
        return redirect(reverse("floorplans:staff_reservation", args=[hut.pk, reservation.code]) + "?saved=1")
    if request.method == "POST" and request.POST.get("action") == "stay" and stay_form.is_valid():
        if has_physical_assignments(reservation):
            error_message = "This booking has numbered-bed assignments. Remove those assignments in Bed Management before changing dates or room quantities."
        elif reservation.status not in Reservation.HOLDING:
            error_message = "Only active pending or confirmed reservations can be changed."
        else:
            quantities = {room.pk: stay_form.cleaned_data[f"room_{room.pk}"] for room in rooms}
            try:
                with transaction.atomic():
                    # The service locks the reservation and affected rooms, and checks availability.
                    # Assignment guard is repeated after locking the reservation to reduce race windows.
                    locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
                    if has_physical_assignments(locked):
                        raise ValidationError("Numbered-bed assignments exist; remove them before editing the stay.")
                    modify_reservation(code=locked.code, check_in=stay_form.cleaned_data["check_in"],
                                       check_out=stay_form.cleaned_data["check_out"], beds_by_room=quantities)
            except (ValidationError, NotAvailable, ValueError) as exc:
                error_message = str(exc)
            else:
                return redirect(reverse("floorplans:staff_reservation", args=[hut.pk, reservation.code]) + "?updated=1")
    if request.method == "POST" and request.POST.get("action") == "status":
        target = request.POST.get("status")
        if target not in ("pending", "confirmed", "cancelled"):
            error_message = "Invalid status."
        else:
            with transaction.atomic():
                locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
                if locked.status == "cancelled" and target != "cancelled":
                    error_message = "Cancelled bookings cannot be reopened here; create a new reservation with availability validation."
                elif target == "cancelled" and has_physical_assignments(locked):
                    error_message = "Remove numbered-bed assignments before cancelling this reservation."
                else:
                    previous_status = locked.status
                    locked.status = target
                    locked.save(update_fields=["status"])
                    if locked.guest_request and previous_status != target:
                        if target == "confirmed":
                            from bookings.views import send_confirmation
                            transaction.on_commit(
                                lambda locked=locked: send_confirmation(request, locked)
                            )
                        elif target == "cancelled":
                            from bookings.guest_requests_v126 import send_guest_request_declined
                            transaction.on_commit(
                                lambda locked=locked: send_guest_request_declined(request, locked)
                            )
            if not error_message:
                return redirect(reverse("floorplans:staff_reservation", args=[hut.pk, reservation.code]) + "?status_changed=1")
    items = list(reservation.items.select_related("room").filter(room__hut=hut).order_by("room__position", "pk"))
    transactions = list(reservation.payment_transactions.all().order_by("-created", "-pk"))
    received = sum((t.amount for t in transactions if t.kind in ("payment", "deposit")), start=0)
    refunds = sum((t.amount for t in transactions if t.kind == "refund"), start=0)
    return render(request, "floorplans/staff_reservation.html", {
        "hut": hut, "reservation": reservation, "form": form, "items": items,
        "transactions": transactions, "received": received, "refunds": refunds,
        "net_paid": received - refunds, "saved": saved, "updated": updated,
        "status_changed": status_changed, "stay_form": stay_form, "error_message": error_message,
    })
