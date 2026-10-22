"""V16 hut-scoped staff reservation detail and guest contact editor.

Date, quantity, status, payment and physical-bed changes remain delegated to
existing validated workflows; this view does not change inventory.
"""
from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

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

    saved = request.GET.get("saved") == "1"
    form = GuestContactForm(request.POST or None, instance=reservation)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
            # Update only guest contact fields, never inventory or status.
            for field in form.Meta.fields:
                setattr(locked, field, form.cleaned_data[field])
            locked.save(update_fields=list(form.Meta.fields))
        return redirect(reverse("floorplans:staff_reservation", args=[hut.pk, reservation.code]) + "?saved=1")

    items = list(reservation.items.select_related("room").filter(room__hut=hut).order_by("room__position", "pk"))
    transactions = list(reservation.payment_transactions.all().order_by("-created", "-pk"))
    received = sum((t.amount for t in transactions if t.kind in ("payment", "deposit")), start=0)
    refunds = sum((t.amount for t in transactions if t.kind == "refund"), start=0)
    return render(request, "floorplans/staff_reservation.html", {
        "hut": hut, "reservation": reservation, "form": form, "items": items,
        "transactions": transactions, "received": received, "refunds": refunds,
        "net_paid": received - refunds, "saved": saved,
    })
