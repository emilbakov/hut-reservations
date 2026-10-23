"""v167: explicit, audited admin cancellation and manual deposit settlement.

No payment gateway is called. A refund entry is only a record of an external
refund that the operator has already completed and confirmed.
"""
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import CancellationSettlement, GuestStay, PaymentTransaction, Reservation


class CancellationSettlementForm(forms.Form):
    outcome = forms.ChoiceField(
        choices=CancellationSettlement.Outcome.choices,
        label="Deposit / received funds decision",
        widget=forms.RadioSelect,
    )
    refund_amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"),
        required=False, label="Refund amount",
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
    )
    refund_method = forms.ChoiceField(
        choices=[("", "Select method")] + list(PaymentTransaction.Method.choices),
        required=False, label="Refund method",
    )
    note = forms.CharField(
        max_length=500, required=False, label="Reason / reference",
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
    )
    refund_completed = forms.BooleanField(
        required=False,
        label="I confirm this refund has already been made outside SummitDesk",
    )
    confirm_cancel = forms.BooleanField(
        required=True,
        label="I confirm the reservation should be cancelled and beds released",
    )

    def __init__(self, *args, net_received=Decimal("0.00"), **kwargs):
        super().__init__(*args, **kwargs)
        self.net_received = net_received

    def clean(self):
        data = super().clean()
        outcome = data.get("outcome")
        amount = data.get("refund_amount")
        if self.net_received < 0:
            raise forms.ValidationError("The ledger has a negative balance. Review the payment history first.")
        if outcome == CancellationSettlement.Outcome.NO_FUNDS:
            if self.net_received != 0:
                self.add_error("outcome", "Funds were received. Choose retain or refund.")
            if amount is not None:
                self.add_error("refund_amount", "No refund is allowed for this choice.")
        elif outcome == CancellationSettlement.Outcome.RETAIN:
            if self.net_received <= 0:
                self.add_error("outcome", "No funds are available to retain.")
            if amount is not None:
                self.add_error("refund_amount", "Choose refund to enter an amount.")
            if not data.get("note", "").strip():
                self.add_error("note", "Explain why the received funds are retained.")
        elif outcome == CancellationSettlement.Outcome.REFUND:
            if self.net_received <= 0:
                self.add_error("outcome", "There is no received balance to refund.")
            if amount is None:
                self.add_error("refund_amount", "Enter the amount actually refunded.")
            elif amount > self.net_received:
                self.add_error("refund_amount", "Refund cannot exceed the net amount received.")
            if not data.get("refund_method"):
                self.add_error("refund_method", "Choose how the refund was made.")
            if not data.get("refund_completed"):
                self.add_error("refund_completed", "Confirm that the external refund is complete.")
            if amount is not None and amount < self.net_received and not data.get("note", "").strip():
                self.add_error("note", "Explain the retained balance for a partial refund.")
        return data


def ledger_totals(reservation):
    """Ledger amounts; refunds reduce the available balance."""
    sums = dict(reservation.payment_transactions.values("kind").annotate(total=Sum("amount")).values_list("kind", "total"))
    zero = Decimal("0.00")
    deposits = sums.get(PaymentTransaction.Kind.DEPOSIT, zero)
    payments = sums.get(PaymentTransaction.Kind.PAYMENT, zero)
    refunded = sums.get(PaymentTransaction.Kind.REFUND, zero)
    return {"deposits": deposits, "payments": payments, "refunded": refunded,
            "net": deposits + payments - refunded}


def cancellation_view(model_admin, request, object_id):
    """Admin-only, single-booking cancellation with explicit financial choice."""
    # The admin wrapper verifies site access. Enforce per-object change access too.
    try:
        reservation = Reservation.objects.get(pk=object_id)
    except (Reservation.DoesNotExist, ValueError, TypeError):
        raise Http404
    if not model_admin.has_change_permission(request, reservation):
        raise PermissionDenied

    change_url = reverse("admin:bookings_reservation_change", args=[reservation.pk])
    settlement = CancellationSettlement.objects.filter(reservation=reservation).first()
    if settlement is not None:
        messages.info(request, "Cancellation settlement was already recorded. Review its audit entry.")
        return redirect(change_url)

    if request.method == "POST":
        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
            if not model_admin.has_change_permission(request, reservation):
                raise PermissionDenied
            if CancellationSettlement.objects.filter(reservation=reservation).exists():
                messages.warning(request, "This cancellation has already been settled.")
                return redirect(change_url)
            amounts = ledger_totals(reservation)
            form = CancellationSettlementForm(request.POST, net_received=amounts["net"])
            if (reservation.status != Reservation.Status.CANCELLED and
                    GuestStay.objects.filter(reservation=reservation,
                        checked_in_at__isnull=False, checked_out_at__isnull=True).exists()):
                form.add_error(None, "Guest is currently checked in. Record checkout before cancelling.")
            if form.is_valid():
                outcome = form.cleaned_data["outcome"]
                refund = (form.cleaned_data["refund_amount"]
                          if outcome == CancellationSettlement.Outcome.REFUND
                          else Decimal("0.00"))
                if reservation.status != Reservation.Status.CANCELLED:
                    reservation.status = Reservation.Status.CANCELLED
                    reservation.save(update_fields=["status"])
                if refund:
                    PaymentTransaction.objects.create(
                        reservation=reservation, kind=PaymentTransaction.Kind.REFUND,
                        method=form.cleaned_data["refund_method"], amount=refund,
                        note=("Cancellation refund: " + form.cleaned_data["note"].strip())[:500],
                        recorded_by=request.user,
                    )
                CancellationSettlement.objects.create(
                    reservation=reservation, outcome=outcome,
                    net_received_at_cancellation=amounts["net"],
                    refunded_at_cancellation=refund,
                    retained_at_cancellation=amounts["net"] - refund,
                    method=form.cleaned_data["refund_method"] if refund else "",
                    note=form.cleaned_data["note"].strip(), recorded_by=request.user,
                )
                messages.success(request, "Reservation cancelled and deposit decision recorded. Beds released.")
                return redirect(change_url)
    else:
        amounts = ledger_totals(reservation)
        form = CancellationSettlementForm(net_received=amounts["net"])

    context = {
        **model_admin.admin_site.each_context(request),
        "title": "Cancel reservation and handle deposit",
        "opts": model_admin.model._meta,
        "original": reservation,
        "reservation": reservation,
        "form": form,
        "amounts": amounts,
        "currency": settings.BOOKING_CURRENCY,
        "change_url": change_url,
        "already_cancelled": reservation.status == Reservation.Status.CANCELLED,
        "has_payment": amounts["net"] > 0,
    }
    return render(request, "admin/bookings/reservation/cancel_deposit.html", context)
