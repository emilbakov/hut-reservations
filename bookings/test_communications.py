from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .communications import deliver, render_message, run_communications, validate_text
from .models import (GuestMessageLog, Hut, HutDepositPolicy, HutMessageTemplate,
                     Reservation, ReservationItem, Room)

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class GuestCommunicationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user("com_mgr", password="pw", is_staff=True)
        self.other = User.objects.create_user("com_other", password="pw", is_staff=True)
        self.hut = Hut.objects.create(name="Communication Hut", slug="communication-hut")
        self.other_hut = Hut.objects.create(name="Elsewhere", slug="elsewhere")
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other)
        room = Room.objects.create(hut=self.hut, name="A", capacity=2)
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(
            name="Test Guest", email="test@example.com",
            check_in=today + timedelta(days=2),
            check_out=today + timedelta(days=3),
            status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=self.reservation, room=room,
                                       beds=1, price_per_night=Decimal("100"))
        HutDepositPolicy.objects.create(hut=self.hut, percentage=30, due_days=3)
        self.url = reverse("bookings:communications_dashboard")
        self.client.force_login(self.manager)

    def test_preview_does_not_send(self):
        counts = run_communications(dry_run=True)
        self.assertEqual(counts["preview"], 1)
        self.assertFalse(GuestMessageLog.objects.exists())

    def test_prearrival_sends_once(self):
        from django.core import mail
        self.assertEqual(run_communications(dry_run=False)["sent"], 1)
        self.assertEqual(run_communications(dry_run=False)["duplicate"], 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_custom_template(self):
        HutMessageTemplate.objects.create(
            hut=self.hut, message_type="prearrival",
            subject="Hello {guest}", body="Welcome to {hut}, booking {code}.")
        subject, body = render_message(self.reservation, self.hut, "prearrival")
        self.assertEqual(subject, "Hello Test Guest")
        self.assertIn(self.reservation.code, body)

    def test_reject_template_attribute_access(self):
        with self.assertRaises(ValueError):
            validate_text("{guest.__class__}")

    def test_manager_cannot_edit_other_hut(self):
        response = self.client.post(self.url, {
            "hut_id": self.other_hut.pk, "message_type": "prearrival",
            "subject": "Hi", "body": "Hi", "enabled": "on"})
        self.assertEqual(response.status_code, 404)

    def test_manager_can_save_template(self):
        response = self.client.post(self.url, {
            "hut_id": self.hut.pk, "message_type": "prearrival",
            "subject": "Hi {guest}", "body": "Hello {guest}", "enabled": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(HutMessageTemplate.objects.filter(hut=self.hut).count(), 1)

    def test_nonstaff_cannot_open(self):
        User = get_user_model()
        guest = User.objects.create_user("com_guest", password="pw")
        self.client.force_login(guest)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_failure_logged_and_retry(self):
        with patch("bookings.communications.send_mail", side_effect=RuntimeError("smtp")):
            self.assertEqual(run_communications(dry_run=False)["failed"], 1)
        self.assertEqual(GuestMessageLog.objects.get().status, "failed")
        self.assertEqual(run_communications(dry_run=False)["sent"], 1)
        self.assertEqual(GuestMessageLog.objects.get().status, "sent")

    def test_cancelled_reservation_not_prearrival(self):
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=["status"])
        self.assertEqual(run_communications(dry_run=True)["preview"], 0)

    def test_cancellation_opt_in(self):
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=["status"])
        self.assertEqual(run_communications(dry_run=True, include_cancellations=True)["preview"], 1)
