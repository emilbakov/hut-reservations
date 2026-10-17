
"""Manager-only secure guest access link controls.

Never render or log tokens in staff pages. Guest links go only to booking email.
"""
import secrets

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .deposits import single_hut_id
from .models import GuestAccessLink, Reservation
from .views import manageable_reservations, permitted_hut_selection


def guest_portal_url(reservation, request):
    """Issue a link for the existing guest email; never include in staff notifications."""
    from .self_service import issue_guest_link
    return request.build_absolute_uri(issue_guest_link(reservation))


def append_guest_portal_to_confirmation(request, reservation, body):
    """Append guest-only access instructions to the guest confirmation body."""
    if not reservation.email or single_hut_id(reservation) is None:
        return body
    url = guest_portal_url(reservation, request)
    return body + ("\n\nManage your reservation securely:\n" + url +
                   "\nKeep this link private; anyone with it can view your booking.\n")


def _send_access_email(reservation, url):
    send_mail(
        f"Your private reservation link — {reservation.code}",
        "Hello " + reservation.name + ",\n\n" +
        "Use this private link to view your reservation or request changes:\n" +
        url + "\n\nKeep this link private.\n",
        None, [reservation.email], fail_silently=False,
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def guest_link_controls(request):
    try:
        huts, selected_hut, selected_slug = permitted_hut_selection(request)
    except PermissionDenied:
        # Do not reveal whether a reservation belongs to another hut.
        raise Http404 from None

    allowed = manageable_reservations(request.user)

    if request.method == "POST":
        reservation = get_object_or_404(allowed, pk=request.POST.get("reservation_id"))
        hut_id = single_hut_id(reservation)

        if hut_id is None or (selected_hut and selected_hut.pk != hut_id):
            raise Http404

        action = request.POST.get("action")
        if action not in ("resend", "revoke", "reissue"):
            raise Http404

        if action in ("resend", "reissue") and not reservation.email:
            messages.error(request, "Reservation has no guest email address.")
            return redirect("bookings:guest_link_controls")

        if action == "revoke":
            with transaction.atomic():
                access = GuestAccessLink.objects.select_for_update().filter(
                    reservation=reservation
                ).first()

                if access and not access.revoked_at:
                    access.revoked_at = timezone.now()
                    access.save(update_fields=["revoked_at"])

            messages.success(
                request,
                "Guest access revoked. The previous link no longer works."
            )
        else:
            # Serialize issuance, rotation and send against other manager actions.
            with transaction.atomic():
                locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
                access = GuestAccessLink.objects.select_for_update().filter(
                    reservation=locked
                ).first()

                if action == "resend" and access and access.revoked_at:
                    messages.error(
                        request,
                        "Access is revoked. Choose Reissue to create a new link."
                    )
                    return redirect("bookings:guest_link_controls")

                if action == "reissue" and access:
                    access.token = secrets.token_urlsafe(32)
                    access.revoked_at = None
                    access.save(update_fields=["token", "revoked_at"])
                elif not access:
                    access = GuestAccessLink.objects.create(reservation=locked)

                url = request.build_absolute_uri(
                    reverse("bookings:guest_self_service", args=[access.token])
                )

                try:
                    _send_access_email(locked, url)
                except Exception:
                    messages.error(
                        request,
                        "Email delivery failed. Check SMTP configuration and retry."
                    )
                else:
                    messages.success(
                        request,
                        "Private access link emailed to the booking's guest address."
                    )

        return redirect("bookings:guest_link_controls")

    reservations = (
        allowed.order_by("-created_at")
        if hasattr(Reservation, "created_at")
        else allowed.order_by("-pk")
    )

    if selected_hut:
        reservations = reservations.filter(
            items__room__hut=selected_hut
        ).distinct()

    return render(request, "bookings/guest_link_controls.html", {
        "reservations": reservations[:100],
        "huts": huts,
        "selected_hut": selected_hut,
        "selected_slug": selected_slug,
    })
