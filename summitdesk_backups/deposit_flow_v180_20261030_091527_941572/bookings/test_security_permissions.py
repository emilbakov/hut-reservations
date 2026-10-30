"""SummitDesk authorization regression tests.

Run against Django's isolated PostgreSQL test database. These tests do not
change production data or perform any real financial transactions.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, PaymentTransaction, Reservation, ReservationItem, Room


class StaffSecurityPermissionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager_a = User.objects.create_user(
            username="security-manager-a", password="test-only", is_staff=True
        )
        self.manager_b = User.objects.create_user(
            username="security-manager-b", password="test-only", is_staff=True
        )
        self.unassigned = User.objects.create_user(
            username="security-unassigned", password="test-only", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="security-regular", password="test-only", is_staff=False
        )
        self.superuser = User.objects.create_superuser(
            username="security-admin", email="security-admin@example.com",
            password="test-only",
        )
        self.hut_a = Hut.objects.create(name="Security Hut A", slug="security-hut-a")
        self.hut_b = Hut.objects.create(name="Security Hut B", slug="security-hut-b")
        self.hut_a.managers.add(self.manager_a)
        self.hut_b.managers.add(self.manager_b)
        self.room_a = Room.objects.create(hut=self.hut_a, name="A dorm", capacity=4)
        self.room_b = Room.objects.create(hut=self.hut_b, name="B dorm", capacity=4)
        start = timezone.localdate() + timedelta(days=8)
        end = start + timedelta(days=2)
        self.res_a = Reservation.objects.create(
            name="Guest From Hut A", email="private-a@example.com",
            check_in=start, check_out=end, status=Reservation.Status.PENDING,
        )
        self.res_b = Reservation.objects.create(
            name="Guest From Hut B", email="private-b@example.com",
            check_in=start, check_out=end, status=Reservation.Status.PENDING,
        )
        ReservationItem.objects.create(
            reservation=self.res_a, room=self.room_a,
            beds=1, price_per_night=Decimal("20.00"),
        )
        ReservationItem.objects.create(
            reservation=self.res_b, room=self.room_b,
            beds=1, price_per_night=Decimal("30.00"),
        )

    def url(self, name, *args):
        return reverse(name, args=args or None)

    def test_anonymous_cannot_open_staff_dashboards(self):
        for name in (
            "bookings:dashboard", "bookings:manager_reservations",
            "bookings:financial_dashboard", "bookings:manager_stays",
        ):
            with self.subTest(page=name):
                response = self.client.get(self.url(name), secure=True)
                self.assertNotEqual(response.status_code, 200)

    def test_nonstaff_cannot_open_staff_dashboards(self):
        self.client.force_login(self.regular_user)
        for name in (
            "bookings:dashboard", "bookings:manager_reservations",
            "bookings:financial_dashboard",
        ):
            with self.subTest(page=name):
                response = self.client.get(self.url(name), secure=True)
                self.assertNotEqual(response.status_code, 200)

    def test_unassigned_staff_cannot_access_reservation_management(self):
        self.client.force_login(self.unassigned)
        response = self.client.get(self.url("bookings:manager_reservations"), secure=True)
        self.assertNotEqual(response.status_code, 200)

    def test_manager_reservation_list_does_not_leak_other_hut(self):
        self.client.force_login(self.manager_a)
        response = self.client.get(self.url("bookings:manager_reservations"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.res_a.name)
        self.assertNotContains(response, self.res_b.email)
        self.assertNotContains(response, self.res_b.name)

    def test_manager_cannot_change_another_huts_reservation(self):
        self.client.force_login(self.manager_a)
        response = self.client.post(
            self.url("bookings:manager_reservation_action", self.res_b.code),
            {"action": "confirm"}, secure=True,
        )
        self.assertEqual(response.status_code, 404)
        self.res_b.refresh_from_db()
        self.assertEqual(self.res_b.status, Reservation.Status.PENDING)

    def test_manager_cannot_cancel_another_huts_reservation(self):
        self.client.force_login(self.manager_a)
        response = self.client.post(
            self.url("bookings:manager_reservation_action", self.res_b.code),
            {"action": "cancel"}, secure=True,
        )
        self.assertEqual(response.status_code, 404)
        self.res_b.refresh_from_db()
        self.assertEqual(self.res_b.status, Reservation.Status.PENDING)

    def test_manager_cannot_open_other_huts_payment_ledger(self):
        self.client.force_login(self.manager_a)
        response = self.client.get(
            self.url("bookings:reservation_payments", self.res_b.code), secure=True
        )
        self.assertEqual(response.status_code, 404)

    def test_manager_cannot_record_payment_for_other_hut(self):
        self.client.force_login(self.manager_a)
        before = PaymentTransaction.objects.count()
        response = self.client.post(
            self.url("bookings:reservation_payments", self.res_b.code),
            {"kind": PaymentTransaction.Kind.PAYMENT,
             "method": PaymentTransaction.Method.CASH,
             "amount": "100.00", "note": "Unauthorized test"},
            secure=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(PaymentTransaction.objects.count(), before)

    def test_manager_cannot_select_other_hut_financial_reports(self):
        self.client.force_login(self.manager_a)
        for name in ("bookings:financial_dashboard", "bookings:financial_export"):
            with self.subTest(page=name):
                response = self.client.get(
                    self.url(name), {"hut": self.hut_b.slug}, secure=True
                )
                self.assertEqual(response.status_code, 404)

    def test_manager_financial_report_excludes_other_hut_payments(self):
        PaymentTransaction.objects.create(
            reservation=self.res_b, kind=PaymentTransaction.Kind.PAYMENT,
            method=PaymentTransaction.Method.CASH, amount=Decimal("999.00"),
            recorded_by=self.manager_b,
        )
        self.client.force_login(self.manager_a)
        response = self.client.get(self.url("bookings:financial_dashboard"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.res_b.name)
        self.assertEqual(response.context["receipts"], Decimal("0.00"))

    def test_manager_cannot_access_admin_reservation_or_financial_records(self):
        self.client.force_login(self.manager_a)
        for name in (
            "admin:bookings_reservation_changelist",
            "admin:bookings_depositentry_changelist",
            "admin:bookings_cancellationsettlement_changelist",
        ):
            with self.subTest(page=name):
                response = self.client.get(self.url(name), secure=True)
                self.assertNotEqual(response.status_code, 200)

    def test_manager_cannot_use_admin_cancellation_endpoint(self):
        self.client.force_login(self.manager_a)
        url = self.url("admin:bookings_reservation_cancel_deposit", self.res_a.pk)
        response = self.client.post(
            url, {"outcome": "no_funds", "confirm_cancel": "on"}, secure=True
        )
        self.assertNotEqual(response.status_code, 200)
        self.res_a.refresh_from_db()
        self.assertEqual(self.res_a.status, Reservation.Status.PENDING)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_superuser_can_see_both_huts_reservations(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url("bookings:manager_reservations"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.res_a.name)
        self.assertContains(response, self.res_b.name)

    def test_reservation_action_get_cannot_change_status(self):
        self.client.force_login(self.manager_a)
        response = self.client.get(
            self.url("bookings:manager_reservation_action", self.res_a.code),
            secure=True,
        )
        self.assertEqual(response.status_code, 405)
        self.res_a.refresh_from_db()
        self.assertEqual(self.res_a.status, Reservation.Status.PENDING)
