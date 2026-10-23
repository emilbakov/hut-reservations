"""v167 admin cancellation: explicit choice, protected money ledger and audit."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .services import free_beds

from .models import (
    CancellationSettlement, GuestStay, Hut, PaymentTransaction, Reservation, ReservationItem, Room,
)


class CancellationDepositAdminV167Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            "v167_superuser", "v167@example.test", "testpass",
        )
        cls.manager = get_user_model().objects.create_user(
            "v167_manager", password="testpass", is_staff=True,
        )
        cls.hut = Hut.objects.create(name="Settlement hut", slug="settlement-hut")
        cls.hut.managers.add(cls.manager)
        cls.room = Room.objects.create(
            hut=cls.hut, name="Room 1", capacity=2,
            price_per_night=Decimal("100.00"),
        )
        today = timezone.localdate()
        cls.reservation = Reservation.objects.create(
            name="Cancellation guest", check_in=today + timedelta(days=4),
            check_out=today + timedelta(days=5), status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(
            reservation=cls.reservation, room=cls.room, beds=1,
            price_per_night=Decimal("100.00"),
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("admin:bookings_reservation_cancel_deposit", args=[self.reservation.pk])

    def add_deposit(self, amount="40.00"):
        return PaymentTransaction.objects.create(
            reservation=self.reservation, kind=PaymentTransaction.Kind.DEPOSIT,
            method=PaymentTransaction.Method.BANK, amount=Decimal(amount),
            recorded_by=self.admin,
        )

    def submit(self, outcome, *, amount="", method="", note="", confirmed=False):
        return self.client.post(self.url, {
            "outcome": outcome, "refund_amount": amount,
            "refund_method": method, "note": note,
            "refund_completed": "on" if confirmed else "",
            "confirm_cancel": "on",
        })

    def test_cancel_without_funds_releases_beds_and_records_audit(self):
        before = free_beds([self.room], self.reservation.check_in, self.reservation.check_out)
        self.assertEqual(before[self.room.pk], 1)
        response = self.submit("no_funds")
        self.assertEqual(response.status_code, 302)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CANCELLED)
        self.assertEqual(self.reservation.cancellation_settlement.outcome, "no_funds")
        self.assertEqual(self.reservation.cancellation_settlement.net_received_at_cancellation, Decimal("0.00"))
        self.assertEqual(PaymentTransaction.objects.count(), 0)
        after = free_beds([self.room], self.reservation.check_in, self.reservation.check_out)
        self.assertEqual(after[self.room.pk], 2)

    def test_retained_deposit_requires_reason_and_preserves_ledger(self):
        self.add_deposit()
        self.assertEqual(self.submit("retain").status_code, 200)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(self.submit("retain", note="Cancellation outside free period").status_code, 302)
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        settlement = self.reservation.cancellation_settlement
        self.assertEqual(settlement.retained_at_cancellation, Decimal("40.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("0.00"))

    def test_full_refund_requires_external_confirmation(self):
        self.add_deposit()
        self.assertEqual(self.submit("refund", amount="40.00", method="bank").status_code, 200)
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(self.submit("refund", amount="40.00", method="bank", confirmed=True).status_code, 302)
        refund = PaymentTransaction.objects.get(kind=PaymentTransaction.Kind.REFUND)
        self.assertEqual(refund.amount, Decimal("40.00"))
        self.assertEqual(refund.method, PaymentTransaction.Method.BANK)
        self.assertEqual(refund.recorded_by, self.admin)
        settlement = self.reservation.cancellation_settlement
        self.assertEqual(settlement.retained_at_cancellation, Decimal("0.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("40.00"))

    def test_partial_refund_records_refund_and_retained_balance(self):
        self.add_deposit("60.00")
        response = self.submit("refund", amount="20.00", method="cash", note="Keep cancellation fee", confirmed=True)
        self.assertEqual(response.status_code, 302)
        settlement = self.reservation.cancellation_settlement
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("20.00"))
        self.assertEqual(settlement.retained_at_cancellation, Decimal("40.00"))
        self.assertEqual(PaymentTransaction.objects.filter(kind="refund").count(), 1)

    def test_refund_cannot_exceed_net_received_or_have_too_many_decimals(self):
        self.add_deposit("40.00")
        for amount in ("40.01", "40.001", "-1", "NaN"):
            with self.subTest(amount=amount):
                response = self.submit("refund", amount=amount, method="bank", confirmed=True)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(CancellationSettlement.objects.exists())
                self.assertFalse(PaymentTransaction.objects.filter(kind="refund").exists())
                self.reservation.refresh_from_db()
                self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)

    def test_paid_reservation_cannot_choose_no_funds(self):
        self.add_deposit()
        self.assertEqual(self.submit("no_funds").status_code, 200)
        self.assertFalse(CancellationSettlement.objects.exists())

    def test_post_is_idempotent(self):
        self.add_deposit()
        self.assertEqual(self.submit("refund", amount="40.00", method="bank", confirmed=True).status_code, 302)
        self.assertEqual(self.submit("refund", amount="40.00", method="bank", confirmed=True).status_code, 302)
        self.assertEqual(CancellationSettlement.objects.count(), 1)
        self.assertEqual(PaymentTransaction.objects.filter(kind="refund").count(), 1)

    def test_already_cancelled_can_settle_deposit(self):
        self.add_deposit()
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=["status"])
        self.assertEqual(self.submit("retain", note="Non-refundable").status_code, 302)
        self.assertEqual(CancellationSettlement.objects.count(), 1)

    def test_cannot_cancel_guest_still_checked_in(self):
        GuestStay.objects.create(reservation=self.reservation, checked_in_at=timezone.now(),
                                 checked_in_by=self.admin)
        response = self.submit("no_funds")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Record checkout before cancelling")
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertFalse(CancellationSettlement.objects.exists())

    def test_manager_cannot_access_django_admin_cancellation(self):
        self.client.force_login(self.manager)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.assertNotEqual(self.submit("no_funds").status_code, 302)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)

    def test_action_for_one_redirects_to_review_not_direct_cancel(self):
        response = self.client.post(reverse("admin:bookings_reservation_changelist"), {
            "action": "cancel_with_deposit", "_selected_action": [str(self.reservation.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("cancel-deposit", response.url)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)

    def test_multiple_selected_do_not_cancel_anything(self):
        second = Reservation.objects.create(
            name="Other guest", check_in=self.reservation.check_in,
            check_out=self.reservation.check_out,
        )
        ReservationItem.objects.create(reservation=second, room=self.room, beds=1)
        response = self.client.post(reverse("admin:bookings_reservation_changelist"), {
            "action": "cancel_with_deposit", "_selected_action": [str(self.reservation.pk), str(second.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservation.objects.filter(status=Reservation.Status.CANCELLED).count(), 0)

    def test_audit_list_is_read_only(self):
        self.submit("no_funds")
        response = self.client.get(reverse("admin:bookings_cancellationsettlement_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.reservation.code)
        change = self.client.get(reverse("admin:bookings_cancellationsettlement_change", args=[self.reservation.cancellation_settlement.pk]))
        self.assertEqual(change.status_code, 200)
        self.assertNotContains(change, 'name="_save"')
