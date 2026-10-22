"""Deposit lifecycle: warning-only default, opt-in automatic cancellations."""
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .deposits import deposit_summary, single_hut_id
from .models import Hut, HutDepositPolicy, Reservation, ReservationLifecycleEvent
from .views import manageable_reservations, permitted_hut_selection

DEFAULT_GRACE_DAYS = 2

def lifecycle_state(reservation, today=None):
    summary = deposit_summary(reservation, today=today)
    if summary is None:
        return None
    policy = HutDepositPolicy.objects.filter(hut_id=summary["hut_id"]).first()
    grace = policy.grace_days if policy else DEFAULT_GRACE_DAYS
    cancel_enabled = policy.auto_cancel_enabled if policy else False
    today = today or timezone.localdate()
    cancellation_date = summary["due_date"] + timedelta(days=grace)
    eligible = bool(summary["active"] and summary["remaining"] > 0
                    and today > cancellation_date and today < reservation.check_in)
    return {**summary, "grace_days": grace, "cancellation_date": cancellation_date,
            "auto_cancel_enabled": cancel_enabled, "eligible": eligible}

@staff_member_required
@require_http_methods(["GET", "POST"])
def lifecycle_dashboard(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    if request.method == "POST":
        hut = get_object_or_404(huts, pk=request.POST.get("hut_id"))
        if selected_hut and hut.pk != selected_hut.pk:
            return HttpResponseBadRequest("Hut does not match selected scope.")
        try:
            grace_days = int(request.POST.get("grace_days", ""))
            if not 0 <= grace_days <= 365:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Grace period must be 0–365 days.")
        else:
            # Safety: enabling cancellation requires a superuser plus explicit
            # confirmation phrase, not just a checkbox.
            enable = request.POST.get("auto_cancel_enabled") == "on"
            if enable and not request.user.is_superuser:
                raise PermissionDenied("Only administrators may enable automatic cancellation.")
            if enable and request.POST.get("confirm_enable", "").strip() != "ENABLE AUTO CANCEL":
                messages.error(request, "Type ENABLE AUTO CANCEL to enable cancellations.")
            else:
                with transaction.atomic():
                    policy, _ = HutDepositPolicy.objects.select_for_update().get_or_create(hut=hut)
                    policy.grace_days = grace_days
                    if request.user.is_superuser:
                        policy.auto_cancel_enabled = enable
                    policy.save(update_fields=["grace_days", "auto_cancel_enabled"] if request.user.is_superuser else ["grace_days"])
                messages.success(request, "Lifecycle policy saved.")
                return redirect("bookings:lifecycle_dashboard")
    qs = manageable_reservations(request.user).filter(status__in=Reservation.HOLDING)
    if selected_hut:
        qs = qs.filter(items__room__hut=selected_hut)
    rows = []
    for reservation in qs.distinct().prefetch_related("items__room", "payment_transactions").order_by("check_in", "pk"):
        state = lifecycle_state(reservation)
        if state and state["remaining"] > 0:
            rows.append(state)
    rows.sort(key=lambda row: (not row["overdue"], row["cancellation_date"], row["reservation"].check_in))
    policy = HutDepositPolicy.objects.filter(hut=selected_hut).first() if selected_hut else None
    events = ReservationLifecycleEvent.objects.filter(
        reservation__in=manageable_reservations(request.user)
    )
    if selected_hut:
        events = events.filter(reservation__items__room__hut=selected_hut).distinct()
    return render(request, "bookings/lifecycle_dashboard.html", {
        "rows": rows[:200], "overdue_count": sum(r["overdue"] for r in rows),
        "events": events.select_related("reservation")[:50],
        "huts": huts, "selected_hut": selected_hut, "selected_slug": selected_slug,
        "manager_mode": not request.user.is_superuser, "policy": policy,
        "currency": settings.BOOKING_CURRENCY,
    })

def process_lifecycle(*, dry_run=False, allow_cancellation=False, today=None, output=None):
    """Idempotent and lock-protected. No emails; existing reminder job handles email."""
    today = today or timezone.localdate()
    warned = cancelled = skipped = 0
    candidates = Reservation.objects.filter(status__in=Reservation.HOLDING).values_list("pk", flat=True)
    for pk in candidates.iterator():
        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().get(pk=pk)
            state = lifecycle_state(reservation, today=today)
            if not state or not state["overdue"]:
                skipped += 1
                continue
            has_warning = ReservationLifecycleEvent.objects.filter(
                reservation=reservation, event_type="warning", due_date=state["due_date"]
            ).exists()
            if not has_warning:
                warned += 1
                if not dry_run:
                    ReservationLifecycleEvent.objects.create(
                        reservation=reservation, event_type="warning",
                        due_date=state["due_date"], details="Deposit overdue; manager review required.")
                if output:
                    output(f'Warning: {reservation.code}')
            # Cancellation requires explicit CLI flag AND per-hut opt-in.
            # Never cancel on arrival date or after, and never without a
            # previously recorded warning.
            if (allow_cancellation and state["auto_cancel_enabled"] and state["eligible"]
                    and has_warning):
                already = ReservationLifecycleEvent.objects.filter(
                    reservation=reservation, event_type="cancelled", due_date=state["due_date"]
                ).exists()
                if not already:
                    cancelled += 1
                    if not dry_run:
                        reservation.status = Reservation.Status.CANCELLED
                        reservation.save(update_fields=["status"])
                        ReservationLifecycleEvent.objects.create(
                            reservation=reservation, event_type="cancelled",
                            due_date=state["due_date"],
                            details="Cancelled after overdue deposit and grace period.")
                    if output:
                        output(f'Auto-cancel: {reservation.code}')
    return {"warnings": warned, "cancellations": cancelled, "skipped": skipped}
