"""Import Gmail replies into SummitDesk reservation conversations."""

import imaplib
import os
import re

from datetime import datetime, timezone as dt_timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bookings.deposits import single_hut_id
from bookings.models import (
    GuestConversationMessage,
    Hut,
    Reservation,
)


REPLY_SUBJECT = re.compile(
    r"^(?:Re:\s*)+\[Booking ([A-Za-z0-9_-]{1,16})\]\s*(.*)$",
    re.IGNORECASE,
)


def extract_plain_text(message):
    """Return the plain-text body, excluding attachments."""

    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue

            if part.get_content_disposition() == "attachment":
                continue

            try:
                return part.get_content().strip()
            except (UnicodeError, LookupError, ValueError):
                continue

        return ""

    if message.get_content_type() != "text/plain":
        return ""

    try:
        return message.get_content().strip()
    except (UnicodeError, LookupError, ValueError):
        return ""


def received_timestamp(message):
    """Parse the email date, falling back to the current time."""

    try:
        value = parsedate_to_datetime(str(message["Date"]))

        if value is None:
            return timezone.now()

        if timezone.is_naive(value):
            value = value.replace(tzinfo=dt_timezone.utc)

        return value

    except (TypeError, ValueError, OverflowError):
        return timezone.now()


def match_reservation(message):
    """Find a reservation with a matching sender and sent thread."""

    subject = str(message.get("Subject", "")).strip()
    match = REPLY_SUBJECT.match(subject)

    if not match:
        return None

    code, original_subject = match.groups()

    reservation = Reservation.objects.filter(code=code).first()

    if reservation is None or not reservation.email:
        return None

    sender = parseaddr(str(message.get("From", "")))[1].strip()

    if sender.casefold() != reservation.email.strip().casefold():
        return None

    # Only accept replies to messages actually sent from SummitDesk.
    previous_message_exists = GuestConversationMessage.objects.filter(
        reservation=reservation,
        sender=GuestConversationMessage.Sender.MANAGER,
        delivery=GuestConversationMessage.Delivery.SENT,
        subject=original_subject.strip(),
    ).exists()

    if not previous_message_exists:
        return None

    return reservation


class Command(BaseCommand):
    help = "Import Gmail guest replies into SummitDesk."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Save matched messages. Without this, perform a dry run.",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of recent inbox messages to examine.",
        )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_EMAIL_USER", "").strip()
        password = os.environ.get("DJANGO_EMAIL_APP_PASSWORD", "")

        if not username or not password:
            raise CommandError(
                "Gmail credentials are not configured."
            )

        limit = options["limit"]

        if limit < 1 or limit > 1000:
            raise CommandError("--limit must be between 1 and 1000.")

        apply_changes = options["apply"]

        self.stdout.write(
            "Mode: " + ("IMPORT" if apply_changes else "DRY RUN")
        )

        connection = imaplib.IMAP4_SSL(
            "imap.gmail.com",
            993,
            timeout=30,
        )

        imported = 0
        matched = 0
        skipped = 0

        try:
            connection.login(username, password)

            # Read-only prevents changing message flags.
            status, _ = connection.select("INBOX", readonly=True)

            if status != "OK":
                raise CommandError("Could not open Gmail inbox.")

            status, results = connection.uid("SEARCH", None, "ALL")

            if status != "OK":
                raise CommandError("Could not search Gmail inbox.")

            uids = results[0].split()[-limit:]

            self.stdout.write(
                f"Checking {len(uids)} recent inbox messages."
            )

            for uid in uids:
                status, data = connection.uid(
                    "FETCH",
                    uid,
                    "(BODY.PEEK[])",
                )

                if status != "OK":
                    skipped += 1
                    continue

                raw = next(
                    (
                        item[1]
                        for item in data
                        if isinstance(item, tuple)
                        and isinstance(item[1], bytes)
                    ),
                    None,
                )

                if not raw:
                    skipped += 1
                    continue

                try:
                    message = BytesParser(
                        policy=policy.default
                    ).parsebytes(raw)
                except Exception:
                    skipped += 1
                    continue

                message_id = str(
                    message.get("Message-ID", "")
                ).strip()

                if not message_id or len(message_id) > 255:
                    skipped += 1
                    continue

                if GuestConversationMessage.objects.filter(
                    email_message_id=message_id
                ).exists():
                    skipped += 1
                    continue

                reservation = match_reservation(message)

                if reservation is None:
                    skipped += 1
                    continue

                hut_id = single_hut_id(reservation)

                if not hut_id:
                    skipped += 1
                    continue

                hut = Hut.objects.filter(pk=hut_id).first()

                if hut is None:
                    skipped += 1
                    continue

                body = extract_plain_text(message)

                if not body or len(body) > 4000:
                    skipped += 1
                    continue

                matched += 1

                if not apply_changes:
                    self.stdout.write(
                        f"Would import reply for reservation "
                        f"{reservation.code}"
                    )
                    continue

                try:
                    with transaction.atomic():
                        GuestConversationMessage.objects.create(
                            reservation=reservation,
                            hut=hut,
                            sender=(
                                GuestConversationMessage.Sender.GUEST
                            ),
                            subject=str(
                                message.get("Subject", "")
                            )[:200],
                            body=body,
                            recipient=username,
                            delivery=(
                                GuestConversationMessage.Delivery.RECEIVED
                            ),
                            email_message_id=message_id,
                            email_received_at=received_timestamp(message),
                        )

                except IntegrityError:
                    skipped += 1
                    continue

                imported += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Imported reply for reservation "
                        f"{reservation.code}"
                    )
                )

        finally:
            try:
                connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Matched: {matched}, "
                f"Imported: {imported}, Skipped: {skipped}"
            )
        )
