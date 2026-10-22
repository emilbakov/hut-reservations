from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bookings.models import PreArrivalReminder, Reservation


class Command(BaseCommand):
    help = "Send pre-arrival reminders three days before check-in."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Send emails instead of performing a dry run.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]

        today = timezone.localdate()
        arrival_date = today + timedelta(days=3)

        reservations = (
            Reservation.objects.filter(
                status=Reservation.Status.CONFIRMED,
                guest_request=False,
                check_in=arrival_date,
            )
            .exclude(email="")
            .exclude(pre_arrival_reminder__sent_at__isnull=False)
            .order_by("id")
        )

        self.stdout.write(
            f"Mode: {'SEND' if apply else 'DRY RUN'}"
        )
        self.stdout.write(f"Today: {today}")
        self.stdout.write(f"Target arrival date: {arrival_date}")
        self.stdout.write(
            f"Eligible reservations: {reservations.count()}"
        )

        failed = 0
        sent = 0

        for reservation in reservations:
            if not apply:
                self.stdout.write(
                    f"Would email reservation {reservation.code} "
                    f"to {reservation.email}"
                )
                continue

            # Lock the reservation to prevent concurrent command
            # instances from sending the same reminder.
            with transaction.atomic():
                locked = (
                    Reservation.objects
                    .select_for_update()
                    .get(pk=reservation.pk)
                )

                # Recheck eligibility after obtaining the lock.
                if (
                    locked.status != Reservation.Status.CONFIRMED
                    or locked.guest_request
                    or locked.check_in != arrival_date
                    or not locked.email
                ):
                    continue

                reminder, _ = (
                    PreArrivalReminder.objects.get_or_create(
                        reservation=locked
                    )
                )

                if reminder.sent_at is not None:
                    continue

                subject = (
                    f"[Booking {locked.code}] "
                    "Your upcoming hut stay"
                )

                body = (
                    f"Hello {locked.name},\n\n"
                    "We look forward to welcoming you!\n\n"
                    f"Reservation: {locked.code}\n"
                    f"Arrival: {locked.check_in}\n"
                    f"Departure: {locked.check_out}\n\n"
                    "Please contact the hut if you have questions "
                    "about your arrival or need to update your plans.\n\n"
                    "Best regards,\n"
                    "The Hut Team"
                )

                try:
                    send_mail(
                        subject,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [locked.email],
                        fail_silently=False,
                    )

                except Exception as exc:
                    failed += 1

                    self.stderr.write(
                        self.style.ERROR(
                            f"Failed reservation "
                            f"{locked.code}: {exc}"
                        )
                    )
                    continue

                reminder.sent_at = timezone.now()
                reminder.save(update_fields=["sent_at"])

                sent += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Sent reminder for {locked.code}"
                    )
                )

        self.stdout.write(
            f"Finished. Sent: {sent}, Failed: {failed}"
        )

        # Return a non-zero exit status if any email failed.
        # This allows systemd to detect synchronization errors.
        if failed:
            raise CommandError(
                f"{failed} pre-arrival reminder(s) failed to send."
            )