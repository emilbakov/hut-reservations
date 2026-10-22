
"""Import Gmail replies into SummitDesk reservation conversations.

Default mode: dry run.
Use --apply to import replies and persist Gmail UID synchronization state.
"""

import imaplib
import os
import re

from datetime import timezone as dt_timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bookings.deposits import single_hut_id
from bookings.models import (
    EmailSyncState,
    GuestConversationMessage,
    Hut,
    Reservation,
)


REPLY_SUBJECT = re.compile(
    r"^(?:Re:\s*)+\[Booking ([A-Za-z0-9_-]{1,16})\]\s*(.*)$",
    re.IGNORECASE,
)

MAX_BODY_LENGTH = 4000


def extract_plain_text(message):
    """Extract the plain-text email body, excluding attachments."""

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
    """Return an aware email timestamp."""

    try:
        value = parsedate_to_datetime(str(message["Date"]))

        if value is None:
            return timezone.now()

        if timezone.is_naive(value):
            value = value.replace(tzinfo=dt_timezone.utc)

        return value

    except (TypeError, ValueError, OverflowError):
        return timezone.now()


def get_uidvalidity(connection):
    """Read UIDVALIDITY for the currently selected IMAP mailbox."""

    status, values = connection.response("UIDVALIDITY")

    if (
        status != "UIDVALIDITY"
        or not values
        or not values[0]
    ):
        raise CommandError(
            "Gmail did not provide UIDVALIDITY."
        )

    try:
        value = int(values[0])
    except (TypeError, ValueError) as exc:
        raise CommandError(
            "Invalid Gmail UIDVALIDITY."
        ) from exc

    if value < 1:
        raise CommandError(
            "Gmail returned an invalid UIDVALIDITY value."
        )

    return value


def match_reservation(message):
    """Match a guest reply to an existing SummitDesk conversation."""

    subject = str(message.get("Subject", "")).strip()

    match = REPLY_SUBJECT.match(subject)

    if not match:
        return None

    code, original_subject = match.groups()

    reservation = Reservation.objects.filter(
        code=code
    ).first()

    if reservation is None or not reservation.email:
        return None

    sender = parseaddr(
        str(message.get("From", ""))
    )[1].strip()

    if sender.casefold() != reservation.email.strip().casefold():
        return None

    # Require an existing email sent by a manager
    # with the corresponding original subject.
    previous_message_exists = (
        GuestConversationMessage.objects.filter(
            reservation=reservation,
            sender=GuestConversationMessage.Sender.MANAGER,
            delivery=GuestConversationMessage.Delivery.SENT,
            subject=original_subject.strip(),
        ).exists()
    )

    if not previous_message_exists:
        return None

    return reservation


def fetch_message(connection, uid):
    """Fetch one Gmail message without changing its read status."""

    status, data = connection.uid(
        "FETCH",
        str(uid),
        "(BODY.PEEK[])",
    )

    if status != "OK":
        raise CommandError(
            f"IMAP fetch failed for UID {uid}. "
            "Synchronization progress was not advanced past this UID."
        )

    raw = next(
        (
            item[1]
            for item in data
            if isinstance(item, tuple)
            and isinstance(item[1], bytes)
        ),
        None,
    )

    if raw is None:
        raise CommandError(
            f"IMAP returned no message body for UID {uid}. "
            "Synchronization progress was not advanced past this UID."
        )

    try:
        return BytesParser(
            policy=policy.default
        ).parsebytes(raw)

    except Exception as exc:
        raise CommandError(
            f"Could not parse email at UID {uid}. "
            "Synchronization stopped without skipping it."
        ) from exc


def prepare_message(message, username):
    """Determine whether an email should be imported.

    Returns (reservation, hut, body, message_id), or None
    when the message does not qualify.
    """

    message_id = str(
        message.get("Message-ID", "")
    ).strip()

    # Existing duplicate protection depends on Message-ID.
    if not message_id or len(message_id) > 255:
        return None

    if GuestConversationMessage.objects.filter(
        email_message_id=message_id
    ).exists():
        return None

    reservation = match_reservation(message)

    if reservation is None:
        return None

    hut_id = single_hut_id(reservation)

    if not hut_id:
        return None

    hut = Hut.objects.filter(
        pk=hut_id
    ).first()

    if hut is None:
        return None

    body = extract_plain_text(message)

    if not body or len(body) > MAX_BODY_LENGTH:
        return None

    return reservation, hut, body, message_id


class Command(BaseCommand):
    help = (
        "Import Gmail guest replies into SummitDesk "
        "using incremental IMAP UID synchronization."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Import messages and save UID progress. "
                "Without this option, perform a dry run."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help=(
                "Maximum number of new inbox messages "
                "to examine in one run."
            ),
        )

    def handle(self, *args, **options):
        username = os.environ.get(
            "DJANGO_EMAIL_USER", ""
        ).strip()

        password = os.environ.get(
            "DJANGO_EMAIL_APP_PASSWORD", ""
        )

        if not username or not password:
            raise CommandError(
                "Gmail credentials are not configured."
            )

        limit = options["limit"]

        if limit < 1 or limit > 1000:
            raise CommandError(
                "--limit must be between 1 and 1000."
            )

        apply_changes = options["apply"]

        self.stdout.write(
            "Mode: " + (
                "IMPORT" if apply_changes else "DRY RUN"
            )
        )

        mailbox = username.casefold()

        # A dry run must not create or modify sync state.
        if apply_changes:
            sync_state, _ = EmailSyncState.objects.get_or_create(
                mailbox=mailbox,
                defaults={
                    "uidvalidity": 0,
                    "last_uid": 0,
                },
            )
        else:
            sync_state = EmailSyncState.objects.filter(
                mailbox=mailbox
            ).first()

        stored_uidvalidity = (
            sync_state.uidvalidity if sync_state else 0
        )

        stored_last_uid = (
            sync_state.last_uid if sync_state else 0
        )

        connection = None

        matched = 0
        imported = 0
        skipped = 0
        examined = 0

        try:
            connection = imaplib.IMAP4_SSL(
                "imap.gmail.com",
                993,
                timeout=60,
            )

            connection.login(
                username,
                password,
            )

            # Read-only: do not mark messages as read.
            status, _ = connection.select(
                "INBOX",
                readonly=True,
            )

            if status != "OK":
                raise CommandError(
                    "Could not open Gmail inbox."
                )

            current_uidvalidity = get_uidvalidity(
                connection
            )

            self.stdout.write(
                f"Mailbox UIDVALIDITY: {current_uidvalidity}"
            )

            # UID assignments may change if UIDVALIDITY changes.
            # In that case, rescan from the beginning.
            if (
                stored_uidvalidity != current_uidvalidity
            ):
                if stored_uidvalidity:
                    self.stdout.write(
                        self.style.WARNING(
                            "UIDVALIDITY changed. "
                            "Rescanning mailbox from the beginning."
                        )
                    )
                else:
                    self.stdout.write(
                        "First synchronization: scanning "
                        "from the beginning."
                    )

                cursor = 0

                if apply_changes:
                    with transaction.atomic():
                        state = (
                            EmailSyncState.objects
                            .select_for_update()
                            .get(pk=sync_state.pk)
                        )

                        state.uidvalidity = current_uidvalidity
                        state.last_uid = 0
                        state.save(
                            update_fields=[
                                "uidvalidity",
                                "last_uid",
                                "updated_at",
                            ]
                        )
            else:
                cursor = stored_last_uid

            self.stdout.write(
                f"Starting after UID: {cursor}"
            )

            # IMAP UID SEARCH may return the last existing
            # message even when the requested UID is higher.
            # We filter those results explicitly below.
            status, results = connection.uid(
                "SEARCH",
                None,
                "UID",
                f"{cursor + 1}:*",
            )

            if status != "OK":
                raise CommandError(
                    "Could not search Gmail inbox."
                )

            raw_uids = (
                results[0].split()
                if results and results[0]
                else []
            )

            try:
                pending_uids = sorted(
                    int(uid)
                    for uid in raw_uids
                    if int(uid) > cursor
                )
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    "Gmail returned invalid message UIDs."
                ) from exc

            pending_count = len(pending_uids)

            self.stdout.write(
                f"New messages pending: {pending_count}"
            )

            # Process the OLDEST pending messages first.
            # Remaining messages will be processed on later runs.
            uids = pending_uids[:limit]

            self.stdout.write(
                f"Checking {len(uids)} messages this run."
            )

            for uid in uids:
                message = fetch_message(
                    connection,
                    uid,
                )

                prepared = prepare_message(
                    message,
                    username,
                )

                examined += 1

                if prepared is None:
                    skipped += 1

                else:
                    reservation, hut, body, message_id = prepared
                    matched += 1

                    if not apply_changes:
                        self.stdout.write(
                            f"Would import reply for reservation "
                            f"{reservation.code}"
                        )

                if not apply_changes:
                    continue

                # Import and UID progress update are atomic:
                # either both succeed or neither is committed.
                with transaction.atomic():
                    state = (
                        EmailSyncState.objects
                        .select_for_update()
                        .get(pk=sync_state.pk)
                    )

                    if state.uidvalidity != current_uidvalidity:
                        raise CommandError(
                            "Synchronization state changed "
                            "during processing."
                        )

                    if uid <= state.last_uid:
                        continue

                    if prepared is not None:
                        # Recheck duplicates inside the transaction.
                        if not GuestConversationMessage.objects.filter(
                            email_message_id=message_id
                        ).exists():
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
                                email_received_at=received_timestamp(
                                    message
                                ),
                            )

                            imported += 1

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Imported reply for reservation "
                                    f"{reservation.code}"
                                )
                            )

                    state.last_uid = uid
                    state.save(
                        update_fields=[
                            "last_uid",
                            "updated_at",
                        ]
                    )

                cursor = uid

        except (imaplib.IMAP4.error, OSError, TimeoutError) as exc:
            raise CommandError(
                f"Gmail synchronization failed: "
                f"{type(exc).__name__}. "
                "Unprocessed messages will be retried."
            ) from exc

        finally:
            if connection is not None:
                try:
                    connection.logout()
                except (
                    imaplib.IMAP4.error,
                    OSError,
                    TimeoutError,
                ):
                    pass

        remaining = max(
            0,
            pending_count - examined,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. "
                f"Examined: {examined}, "
                f"Matched: {matched}, "
                f"Imported: {imported}, "
                f"Skipped: {skipped}, "
                f"Remaining: {remaining}"
            )
        )

        if apply_changes:
            self.stdout.write(
                f"Last processed UID: {cursor}"
            )
        else:
            self.stdout.write(
                "Dry run: synchronization state unchanged."
            )
