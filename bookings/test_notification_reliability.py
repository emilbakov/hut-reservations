"""SummitDesk notification delivery regression tests (v145 workflow).

Runs only against Django's isolated test database. Email delivery is mocked,
so no SMTP messages are sent and no production data is modified.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import GuestAccessLink, Reservation, ReservationNotification
from .notifications_v145 import (
    MAX_ATTEMPTS,
    deliver_notification,
    queue_notification,
    supersede_request_notifications,
)


@override_settings(
    DEBUG=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class NotificationReliabilityTests(TestCase):
    def setUp(self):
        start = timezone.localdate() + timedelta(days=8)
        self.reservation = Reservation.objects.create(
            name="Notification Test Guest",
            email="guest@example.com",
            check_in=start,
            check_out=start + timedelta(days=2),
            status=Reservation.Status.PENDING,
        )

    def notification(self, *, kind="request_guest", body="Test notification", **kwargs):
        defaults = dict(
            reservation=self.reservation,
            dedupe_key=f"test-{ReservationNotification.objects.count()}-{kind}",
            kind=kind,
            recipient="guest@example.com",
            subject="Test subject",
            body=body,
        )
        defaults.update(kwargs)
        return ReservationNotification.objects.create(**defaults)

    def test_queued_message_is_deduplicated_for_same_event(self):
        with patch("bookings.notifications_v145.deliver_notification") as deliver:
            with self.captureOnCommitCallbacks(execute=True):
                first = queue_notification(
                    self.reservation, "request_guest", "Subject", "Body",
                    "guest@example.com", event="created",
                )
                second = queue_notification(
                    self.reservation, "request_guest", "Subject", "Changed body",
                    "guest@example.com", event="created",
                )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ReservationNotification.objects.count(), 1)
        deliver.assert_called_once_with(first.pk)

    def test_different_events_create_distinct_notifications(self):
        with self.captureOnCommitCallbacks(execute=False):
            first = queue_notification(
                self.reservation, "request_guest", "Subject", "Body",
                "guest@example.com", event="first",
            )
            second = queue_notification(
                self.reservation, "request_guest", "Subject", "Body",
                "guest@example.com", event="second",
            )
        self.assertNotEqual(first.pk, second.pk)

    def test_missing_recipient_is_not_queued(self):
        self.assertIsNone(queue_notification(
            self.reservation, "request_guest", "Subject", "Body", "",
        ))
        self.assertEqual(ReservationNotification.objects.count(), 0)

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_successful_delivery_is_sent_only_once(self, send_mail):
        item = self.notification()
        self.assertEqual(deliver_notification(item.pk), "sent")
        self.assertEqual(deliver_notification(item.pk), "sent")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 1)
        self.assertIsNotNone(item.sent_at)
        send_mail.assert_called_once()

    @patch("bookings.notifications_v145.send_mail", side_effect=RuntimeError("SECRET SMTP PASSWORD"))
    def test_failure_is_saved_without_exposing_smtp_exception(self, send_mail):
        item = self.notification()
        self.assertEqual(deliver_notification(item.pk), "failed")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 1)
        self.assertGreater(item.next_attempt_at, timezone.now())
        self.assertNotIn("SECRET", item.last_error)
        self.assertEqual(item.last_error, "Delivery failed. Check SMTP settings or retry later.")

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_failed_message_waits_until_retry_due(self, send_mail):
        item = self.notification(
            status="failed", attempts=1,
            next_attempt_at=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(deliver_notification(item.pk), "failed")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 1)
        send_mail.assert_not_called()

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_manual_retry_can_bypass_backoff(self, send_mail):
        item = self.notification(
            status="failed", attempts=1,
            next_attempt_at=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(deliver_notification(item.pk, manual=True), "sent")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 2)
        send_mail.assert_called_once()

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_automatic_retry_stops_at_max_attempts(self, send_mail):
        item = self.notification(
            status="failed", attempts=MAX_ATTEMPTS,
            next_attempt_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(deliver_notification(item.pk), "failed")
        item.refresh_from_db()
        self.assertEqual(item.attempts, MAX_ATTEMPTS)
        send_mail.assert_not_called()

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_cancelled_reservation_skips_old_request_email(self, send_mail):
        item = self.notification()
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=["status"])
        self.assertEqual(deliver_notification(item.pk), "skipped")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 0)
        send_mail.assert_not_called()

    def test_superseded_request_emails_are_marked_skipped(self):
        pending = self.notification(kind="request_guest")
        failed = self.notification(kind="request_manager", status="failed")
        sent = self.notification(kind="request_guest", status="sent")
        supersede_request_notifications(self.reservation)
        for item in (pending, failed, sent):
            item.refresh_from_db()
        self.assertEqual(pending.status, "skipped")
        self.assertEqual(failed.status, "skipped")
        self.assertEqual(sent.status, "sent")

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_reissued_guest_link_replaces_old_token_before_sending(self, send_mail):
        access = GuestAccessLink.objects.create(reservation=self.reservation)
        item = self.notification(body="Visit https://example.com/guest/manage/oldtoken/ to manage")
        self.assertEqual(deliver_notification(item.pk), "sent")
        item.refresh_from_db()
        self.assertIn(f"/guest/manage/{access.token}/", item.body)
        self.assertNotIn("/guest/manage/oldtoken/", item.body)
        send_mail.assert_called_once()

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_missing_guest_link_skips_message(self, send_mail):
        item = self.notification(body="Visit https://example.com/guest/manage/oldtoken/")
        self.assertEqual(deliver_notification(item.pk), "skipped")
        send_mail.assert_not_called()

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_retry_command_defaults_to_dry_run(self, send_mail):
        item = self.notification()
        output = StringIO()
        call_command("retry_reservation_notifications", stdout=output)
        item.refresh_from_db()
        self.assertEqual(item.status, "pending")
        self.assertEqual(item.attempts, 0)
        self.assertIn("DRY RUN", output.getvalue())
        send_mail.assert_not_called()

    @patch("bookings.notifications_v145.send_mail", return_value=1)
    def test_retry_command_apply_sends_only_due_notifications(self, send_mail):
        due = self.notification()
        future = self.notification(next_attempt_at=timezone.now() + timedelta(hours=1))
        output = StringIO()
        call_command("retry_reservation_notifications", "--apply", stdout=output)
        due.refresh_from_db()
        future.refresh_from_db()
        self.assertEqual(due.status, "sent")
        self.assertEqual(future.status, "pending")
        self.assertEqual(future.attempts, 0)
        self.assertIn("Sent: 1", output.getvalue())
        send_mail.assert_called_once()

    @override_settings(DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_production_console_backend_is_rejected(self):
        item = self.notification()
        self.assertEqual(deliver_notification(item.pk), "failed")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 1)
        self.assertIn("Delivery failed", item.last_error)
