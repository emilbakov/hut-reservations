from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .lifecycle import process_lifecycle
from .models import (Hut, Room, Reservation, ReservationItem, PaymentTransaction,
                     HutDepositPolicy, ReservationLifecycleEvent)

class LifecycleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="life_mgr", password="pass", is_staff=True)
        self.outsider = User.objects.create_user(username="life_other", password="pass", is_staff=True)
        self.admin = User.objects.create_superuser(username="life_admin", email="admin@example.com", password="pass")
        self.hut = Hut.objects.create(name="Lifecycle Hut", slug="lifecycle-hut")
        self.other_hut = Hut.objects.create(name="Other Lifecycle Hut", slug="other-lifecycle-hut")
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.outsider)
        room = Room.objects.create(hut=self.hut, name="A", capacity=3)
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(
            name="Guest", email="guest@example.com", check_in=today + timedelta(days=10),
            check_out=today + timedelta(days=11), status=Reservation.Status.PENDING)
        ReservationItem.objects.create(reservation=self.reservation, room=room, beds=1, price_per_night=Decimal("100"))
        self.policy = HutDepositPolicy.objects.create(
            hut=self.hut, percentage=30, due_days=0, grace_days=0, auto_cancel_enabled=False)
        # created date is now, so simulate overdue using future 'today'
        self.future = today + timedelta(days=2)
        self.url = reverse("bookings:lifecycle_dashboard")
        self.client.force_login(self.manager)

    def test_warning_only_default(self):
        result = process_lifecycle(today=self.future)
        self.assertEqual(result["warnings"], 1)
        self.assertEqual(result["cancellations"], 0)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_warning_idempotent(self):
        process_lifecycle(today=self.future)
        process_lifecycle(today=self.future)
        self.assertEqual(ReservationLifecycleEvent.objects.filter(event_type="warning").count(), 1)

    def test_dry_run_does_not_write(self):
        result = process_lifecycle(today=self.future, dry_run=True)
        self.assertEqual(result["warnings"], 1)
        self.assertFalse(ReservationLifecycleEvent.objects.exists())

    def test_cancel_requires_both_opt_ins_and_previous_warning(self):
        process_lifecycle(today=self.future)
        process_lifecycle(today=self.future, allow_cancellation=True)
        self.reservation.refresh_from_db()
        self.assertNotEqual(self.reservation.status, Reservation.Status.CANCELLED)
        self.policy.auto_cancel_enabled = True
        self.policy.save(update_fields=["auto_cancel_enabled"])
        result = process_lifecycle(today=self.future, allow_cancellation=True)
        self.assertEqual(result["cancellations"], 1)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CANCELLED)

    def test_payment_prevents_cancellation(self):
        self.policy.auto_cancel_enabled = True
        self.policy.save(update_fields=["auto_cancel_enabled"])
        process_lifecycle(today=self.future)
        PaymentTransaction.objects.create(reservation=self.reservation, kind="deposit",
            method="cash", amount=Decimal("30"), recorded_by=self.manager)
        process_lifecycle(today=self.future, allow_cancellation=True)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_cannot_cancel_on_arrival_day(self):
        self.policy.auto_cancel_enabled = True
        self.policy.save(update_fields=["auto_cancel_enabled"])
        process_lifecycle(today=self.future)
        process_lifecycle(today=self.reservation.check_in, allow_cancellation=True)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_manager_cannot_enable_cancellation(self):
        response = self.client.post(self.url, {"hut_id": self.hut.pk, "grace_days": 2,
            "auto_cancel_enabled": "on", "confirm_enable": "ENABLE AUTO CANCEL"})
        self.assertEqual(response.status_code, 403)

    def test_manager_can_change_grace_only(self):
        response = self.client.post(self.url, {"hut_id": self.hut.pk, "grace_days": 5})
        self.assertEqual(response.status_code, 302)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.grace_days, 5)
        self.assertFalse(self.policy.auto_cancel_enabled)

    def test_manager_cannot_edit_other_hut(self):
        response = self.client.post(self.url, {"hut_id": self.other_hut.pk, "grace_days": 5})
        self.assertEqual(response.status_code, 404)

    def test_admin_confirmation_required(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url + "?hut=lifecycle-hut", {
            "hut_id": self.hut.pk, "grace_days": 2, "auto_cancel_enabled": "on"})
        self.assertEqual(response.status_code, 200)
        self.policy.refresh_from_db()
        self.assertFalse(self.policy.auto_cancel_enabled)

    def test_admin_can_enable(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url + "?hut=lifecycle-hut", {
            "hut_id": self.hut.pk, "grace_days": 2, "auto_cancel_enabled": "on",
            "confirm_enable": "ENABLE AUTO CANCEL"})
        self.assertEqual(response.status_code, 302)
        self.policy.refresh_from_db()
        self.assertTrue(self.policy.auto_cancel_enabled)

    def test_read_only_get(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(ReservationLifecycleEvent.objects.exists())
