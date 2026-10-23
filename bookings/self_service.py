"""Token-based guest booking view and manager-reviewed change requests.

Approval records a decision; it NEVER changes inventory, dates, payment or status.
Managers must apply approved requests using existing reservation tools.
"""
import secrets
from datetime import date, timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from .deposits import deposit_summary, single_hut_id
from .models import GuestAccessLink, GuestChangeRequest, GuestConversationMessage, Hut, Reservation
from .views import manageable_reservations, permitted_hut_selection
from .booking_flow_v150 import hut_information

def issue_guest_link(reservation, request=None):
    """Return a newly created or existing URL. Never expose token in staff listings."""
    access, _ = GuestAccessLink.objects.get_or_create(reservation=reservation)
    if access.revoked_at:
        raise PermissionDenied('Private access is revoked. A manager must explicitly reissue it.')
    path = reverse("bookings:guest_self_service", args=[access.token])
    return request.build_absolute_uri(path) if request else path

def guest_reservation(token):
    access = get_object_or_404(
        GuestAccessLink.objects.select_related("reservation"),
        token=token, revoked_at__isnull=True)
    return access.reservation

@never_cache
@require_http_methods(["GET", "POST"])
def guest_self_service(request, token):
    reservation = guest_reservation(token)
    from .reliability_v145 import grant_guest_access
    from .notifications_v145 import guest_delivery_delayed
    grant_guest_access(request, reservation, token=token)
    hut_id = single_hut_id(reservation)
    if not hut_id:
        raise Http404("Booking cannot be managed online.")
    hut = get_object_or_404(Hut, pk=hut_id)
    summary = deposit_summary(reservation)
    if request.method == "POST":
        if reservation.status not in Reservation.HOLDING or reservation.check_in <= timezone.localdate():
            messages.error(request, "This reservation can no longer accept change requests.")
            return redirect("bookings:guest_self_service", token=token)
        kind = request.POST.get("request_type")
        if kind not in ("change", "cancellation"):
            raise Http404
        details = request.POST.get("details", "").strip()
        if len(details) > 2000:
            messages.error(request, "Please limit your message to 2000 characters.")
            return redirect("bookings:guest_self_service", token=token)
        requested_in = requested_out = None
        if kind == "change":
            try:
                requested_in = date.fromisoformat(request.POST.get("requested_check_in", ""))
                requested_out = date.fromisoformat(request.POST.get("requested_check_out", ""))
                if requested_in < timezone.localdate() or requested_out <= requested_in:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, "Enter valid arrival and departure dates.")
                return redirect("bookings:guest_self_service", token=token)
        with transaction.atomic():
            locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
            if not GuestAccessLink.objects.select_for_update().filter(reservation=locked, token=token, revoked_at__isnull=True).exists():
                raise Http404('Private reservation access is unavailable.')
            if locked.status not in Reservation.HOLDING or locked.check_in <= timezone.localdate():
                messages.error(request, "This reservation can no longer accept requests.")
                return redirect("bookings:guest_self_service", token=token)
            if GuestChangeRequest.objects.filter(reservation=locked, status=GuestChangeRequest.Status.PENDING).exists():
                messages.error(request, "A request is already awaiting manager review.")
                return redirect("bookings:guest_self_service", token=token)
            GuestChangeRequest.objects.create(
                reservation=locked, request_type=kind, details=details,
                requested_check_in=requested_in, requested_check_out=requested_out)
        messages.success(request, "Request received. The hut manager will review it.")
        return redirect("bookings:guest_self_service", token=token)
    return render(request, "bookings/guest_self_service.html", {
        "reservation": reservation, "hut": hut, "summary": summary,
        "email_delivery_delayed": guest_delivery_delayed(reservation),
        "items": reservation.items.select_related("room").all(),
        "requests": reservation.guest_change_requests.all()[:20],
        "conversation_messages": list(reversed(list(
            GuestConversationMessage.objects.filter(reservation=reservation, hut=hut)
            .order_by("-created_at")[:100]))),
        "can_message": reservation.check_out >= timezone.localdate() - timedelta(days=7),
        "guest_token": token,
        "can_request": reservation.status in Reservation.HOLDING and reservation.check_in > timezone.localdate(),
        "currency": getattr(settings, "BOOKING_CURRENCY", "EUR"),
        "hut_info": hut_information(hut),
    })

@staff_member_required
@require_http_methods(["GET", "POST"])
def guest_requests_dashboard(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    allowed = manageable_reservations(request.user)
    if request.method == "POST":
        with transaction.atomic():
            change = get_object_or_404(
                GuestChangeRequest.objects.select_for_update().select_related("reservation"),
                pk=request.POST.get("request_id"), reservation__in=allowed)
            if selected_hut and single_hut_id(change.reservation) != selected_hut.pk:
                raise Http404
            if change.status != GuestChangeRequest.Status.PENDING:
                messages.error(request, "This request has already been reviewed.")
                return redirect("bookings:guest_requests_dashboard")
            decision = request.POST.get("decision")
            if decision not in ("approved", "rejected"):
                raise Http404
            change.status = decision
            change.reviewed_by = request.user
            change.reviewed_at = timezone.now()
            change.manager_note = request.POST.get("manager_note", "").strip()[:2000]
            change.save(update_fields=["status", "reviewed_by", "reviewed_at", "manager_note"])
            # Mail delivery is best-effort; a failed SMTP connection must not
            # reverse a recorded decision.
            recipient = change.reservation.email
            reference = change.reservation.code
            status_label = change.get_status_display()
            def notify():
                if not recipient:
                    return
                try:
                    send_mail(
                        f"Reservation request {status_label.lower()} — {reference}",
                        f"Your request for reservation {reference} was {status_label.lower()}.\n"
                        "Approved requests are processed manually by the hut manager.\n"
                        f"Manager note: {change.manager_note}",
                        None, [recipient], fail_silently=False)
                except Exception:
                    pass
            transaction.on_commit(notify)
        messages.success(request, "Decision saved. Approved requests require manual booking updates.")
        return redirect("bookings:guest_requests_dashboard")
    qs = GuestChangeRequest.objects.filter(reservation__in=allowed)
    if selected_hut:
        qs = qs.filter(reservation__items__room__hut=selected_hut).distinct()
    return render(request, "bookings/guest_requests_dashboard.html", {
        "requests": qs.select_related("reservation", "reviewed_by")[:200],
        "huts": huts, "selected_hut": selected_hut, "selected_slug": selected_slug,
    })
