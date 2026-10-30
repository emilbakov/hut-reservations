
"""Per-hut guest emails, safe rendering, deduplication and audit history."""

from datetime import timedelta
from string import Formatter

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .deposits import deposit_summary
from .models import (
    GuestMessageLog,
    Hut,
    HutMessageTemplate,
    Reservation,
)
from .views import manageable_reservations, permitted_hut_selection


DEFAULTS = {
    "confirmation": (
        "Reservation {code} confirmed at {hut}",
        "Hello {guest},\n\n"
        "Your reservation {code} at {hut} is confirmed.\n"
        "Arrival: {check_in}; departure: {check_out}.\n"
        "Total: {total} {currency}.\n",
    ),
    "deposit_due": (
        "Deposit due for reservation {code}",
        "Hello {guest},\n\n"
        "Your deposit for {hut} reservation {code} is "
        "{remaining} {currency}, due {due_date}. "
        "Please contact the hut to arrange payment.\n",
    ),
    "deposit_overdue": (
        "Overdue deposit for reservation {code}",
        "Hello {guest},\n\n"
        "Your deposit for {hut} reservation {code} is overdue. "
        "Outstanding: {remaining} {currency}; "
        "due date: {due_date}. Please contact the hut.\n",
    ),
    "prearrival": (
        "Your upcoming stay at {hut}",
        "Hello {guest},\n\n"
        "We look forward to your arrival at {hut} on {check_in}. "
        "Your reservation reference is {code}. "
        "Contact the hut for arrival instructions.\n",
    ),
    "cancellation": (
        "Reservation {code} cancelled",
        "Hello {guest},\n\n"
        "Your reservation {code} at {hut} has been cancelled. "
        "Please contact the hut if you have questions "
        "about any payments.\n",
    ),
}

FIELDS = {
    "guest",
    "hut",
    "code",
    "check_in",
    "check_out",
    "total",
    "currency",
    "remaining",
    "due_date",
}

TYPES = tuple(DEFAULTS)


def validate_text(text):
    if len(text) > 10000:
        raise ValueError("Template too long.")

    for _, field, spec, conversion in Formatter().parse(text):
        if field is not None:
            if field not in FIELDS or spec or conversion:
                raise ValueError(
                    "Only simple supported placeholders are allowed."
                )


def render_message(reservation, hut, kind, summary=None):
    template = HutMessageTemplate.objects.filter(
        hut=hut,
        message_type=kind,
        enabled=True,
    ).first()

    if template:
        subject, body = template.subject, template.body
    else:
        subject, body = DEFAULTS[kind]

    validate_text(subject)
    validate_text(body)

    values = {
        "guest": reservation.name,
        "hut": hut.name,
        "code": reservation.code,
        "check_in": str(reservation.check_in),
        "check_out": str(reservation.check_out),
        "total": str(reservation.total_price),
        "currency": getattr(settings, "BOOKING_CURRENCY", "EUR"),
        "remaining": str(summary["remaining"]) if summary else "0",
        "due_date": str(summary["due_date"]) if summary else "",
    }

    return subject.format_map(values), body.format_map(values)


def message_candidates(reservation, today):
    """Find messages eligible for this reservation."""

    if not reservation.email or reservation.check_in < today:
        return []

    summary = deposit_summary(reservation, today=today)

    if not summary:
        return []

    events = []

    if reservation.status == Reservation.Status.CANCELLED:
        events.append(
            ("cancellation", reservation.check_in, summary)
        )
        return events

    if reservation.status not in Reservation.HOLDING:
        return events

    if reservation.check_in == today + timedelta(days=2):
        events.append(
            ("prearrival", reservation.check_in, summary)
        )

    if summary["remaining"] > 0 and summary["reminders_enabled"]:
        if today == summary["due_date"]:
            events.append(
                ("deposit_due", summary["due_date"], summary)
            )

        if summary["overdue"]:
            events.append(
                ("deposit_overdue", summary["due_date"], summary)
            )

    return events


def deliver(
    reservation,
    hut,
    kind,
    event_date,
    summary,
    *,
    dry_run=True,
    today=None,
):
    """Send an email once, allowing failed attempts to be retried."""

    already_sent = GuestMessageLog.objects.filter(
        reservation=reservation,
        message_type=kind,
        event_date=event_date,
        status="sent",
    ).exists()

    if already_sent:
        return "duplicate"

    subject, body = render_message(
        reservation,
        hut,
        kind,
        summary,
    )

    if dry_run:
        return "preview"

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(
            pk=reservation.pk
        )

        already_sent = GuestMessageLog.objects.filter(
            reservation=reservation,
            message_type=kind,
            event_date=event_date,
            status="sent",
        ).exists()

        if already_sent:
            return "duplicate"

        current = message_candidates(
            reservation,
            today or timezone.localdate(),
        )

        if (kind, event_date) not in [
            (message_kind, date)
            for message_kind, date, _ in current
        ]:
            return "stale"

        try:
            send_mail(
                subject,
                body,
                None,
                [reservation.email],
                fail_silently=False,
            )

        except Exception as exc:
            GuestMessageLog.objects.update_or_create(
                reservation=reservation,
                message_type=kind,
                event_date=event_date,
                defaults={
                    "hut": hut,
                    "recipient": reservation.email,
                    "subject": subject,
                    "status": "failed",
                    "error": type(exc).__name__,
                },
            )

            return "failed"

        GuestMessageLog.objects.update_or_create(
            reservation=reservation,
            message_type=kind,
            event_date=event_date,
            defaults={
                "hut": hut,
                "recipient": reservation.email,
                "subject": subject,
                "status": "sent",
                "error": "",
            },
        )

    return "sent"


def run_communications(
    *,
    dry_run=True,
    include_cancellations=False,
    today=None,
):
    """Process eligible guest messages."""

    today = today or timezone.localdate()

    counts = {
        "preview": 0,
        "sent": 0,
        "failed": 0,
        "duplicate": 0,
        "stale": 0,
        "skipped": 0,
    }

    qs = (
        Reservation.objects
        .prefetch_related(
            "items__room",
            "payment_transactions",
        )
        .filter(check_in__gte=today)
        .exclude(email="")
    )

    for reservation in qs.iterator(chunk_size=200):
        summary = deposit_summary(
            reservation,
            today=today,
        )

        if not summary:
            counts["skipped"] += 1
            continue

        hut = Hut.objects.get(pk=summary["hut_id"])

        for kind, date, state in message_candidates(
            reservation,
            today,
        ):
            if kind == "cancellation" and not include_cancellations:
                continue

            outcome = deliver(
                reservation,
                hut,
                kind,
                date,
                state,
                dry_run=dry_run,
                today=today,
            )

            counts[outcome] += 1

    return counts


@staff_member_required
@require_http_methods(["GET", "POST"])
def communications_dashboard(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(
        request
    )

    kinds = HutMessageTemplate.TYPES

    if request.method == "POST":
        hut = get_object_or_404(
            huts,
            pk=request.POST.get("hut_id"),
        )

        if selected_hut and selected_hut.pk != hut.pk:
            raise Http404

        kind = request.POST.get("message_type")

        if kind not in TYPES:
            raise Http404

        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()

        try:
            if not subject or not body or len(subject) > 200:
                raise ValueError(
                    "Subject and body are required "
                    "(subject max 200 characters)."
                )

            validate_text(subject)
            validate_text(body)

        except ValueError as exc:
            messages.error(request, str(exc))

        else:
            HutMessageTemplate.objects.update_or_create(
                hut=hut,
                message_type=kind,
                defaults={
                    "subject": subject,
                    "body": body,
                    "enabled": (
                        request.POST.get("enabled") == "on"
                    ),
                },
            )

            messages.success(
                request,
                "Email template saved.",
            )

            return redirect(
                request.path + "?hut=" + hut.slug
            )

    logs = GuestMessageLog.objects.filter(
        reservation__in=manageable_reservations(
            request.user
        )
    )

    templates = HutMessageTemplate.objects.filter(
        hut__in=huts
    )

    if selected_hut:
        logs = logs.filter(hut=selected_hut)
        templates = templates.filter(hut=selected_hut)

    return render(
        request,
        "bookings/communications_dashboard.html",
        {
            "huts": huts,
            "selected_hut": selected_hut,
            "selected_slug": selected_slug,
            "templates": templates.order_by(
                "hut__name",
                "message_type",
            ),
            "logs": logs.select_related(
                "reservation",
                "hut",
            )[:100],
            "kinds": kinds,
            "defaults": DEFAULTS,
        },
    )
