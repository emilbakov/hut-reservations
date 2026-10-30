"""Regression tests for SummitDesk's admin cancellation and payment audit flow.

Run with Django's isolated test database; no real payments/refunds are made.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin_cancellation_v167 import ledger_totals
from .models import (
    CancellationSettlement,
    GuestStay,
    Hut,
    PaymentTransaction,
    Reservation,
    ReservationItem,
    Room,
)
from .services import free_beds


class FinancialCancellationTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="financial-cancel-admin",
            email="financial-cancel-admin@example.com",
            password="test-password-not-for-production",
        )
        self.client.force_login(self.admin_user)
        self.hut = Hut.objects.create(name="Financial Test Hut", slug="financial-test-hut")
        self.room = Room.objects.create(hut=self.hut, name="Dormitory", capacity=4)
        self.check_in = timezone.localdate() + timedelta(days=7)
        self.check_out = self.check_in + timedelta(days=2)
        self.reservation = Reservation.objects.create(
            name="Financial Test Guest",
            check_in=self.check_in,
            check_out=self.check_out,
            status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(
            reservation=self.reservation,
            room=self.room,
            beds=2,
            price_per_night=Decimal("20.00"),
        )
        self.url = reverse(
            "admin:bookings_reservation_cancel_deposit", args=[self.reservation.pk]
        )

    def payment(self, kind, amount):
        return PaymentTransaction.objects.create(
            reservation=self.reservation,
            kind=kind,
            method=PaymentTransaction.Method.BANK,
            amount=Decimal(amount),
            recorded_by=self.admin_user,
        )

    def cancel(self, outcome, **fields):
        data = {
            "outcome": outcome,
            "confirm_cancel": "on",
            **fields,
        }
        return self.client.post(self.url, data, secure=True)

    def assert_active(self):
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(
            free_beds([self.room], self.check_in, self.check_out)[self.room.pk], 2
        )
        self.assertFalse(
            CancellationSettlement.objects.filter(reservation=self.reservation).exists()
        )

    def assert_cancelled(self):
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CANCELLED)
        self.assertEqual(
            free_beds([self.room], self.check_in, self.check_out)[self.room.pk], 4
        )

    def test_no_funds_cancels_without_creating_refund(self):
        response = self.cancel(CancellationSettlement.Outcome.NO_FUNDS)
        self.assertEqual(response.status_code, 302)
        self.assert_cancelled()
        settlement = CancellationSettlement.objects.get(reservation=self.reservation)
        self.assertEqual(settlement.outcome, CancellationSettlement.Outcome.NO_FUNDS)
        self.assertEqual(settlement.net_received_at_cancellation, Decimal("0.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("0.00"))
        self.assertEqual(settlement.retained_at_cancellation, Decimal("0.00"))
        self.assertEqual(PaymentTransaction.objects.filter(reservation=self.reservation).count(), 0)

    def test_retain_deposit_and_payment_preserves_ledger(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "60.00")
        self.payment(PaymentTransaction.Kind.PAYMENT, "40.00")
        response = self.cancel(CancellationSettlement.Outcome.RETAIN, note="Non-refundable terms")
        self.assertEqual(response.status_code, 302)
        self.assert_cancelled()
        settlement = CancellationSettlement.objects.get(reservation=self.reservation)
        self.assertEqual(settlement.net_received_at_cancellation, Decimal("100.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("0.00"))
        self.assertEqual(settlement.retained_at_cancellation, Decimal("100.00"))
        self.assertEqual(PaymentTransaction.objects.filter(reservation=self.reservation).count(), 2)
        self.assertEqual(ledger_totals(self.reservation)["net"], Decimal("100.00"))

    def test_full_refund_creates_one_ledger_entry(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "100.00")
        response = self.cancel(
            CancellationSettlement.Outcome.REFUND,
            refund_amount="100.00",
            refund_method=PaymentTransaction.Method.BANK,
            refund_completed="on",
        )
        self.assertEqual(response.status_code, 302)
        self.assert_cancelled()
        settlement = CancellationSettlement.objects.get(reservation=self.reservation)
        self.assertEqual(settlement.net_received_at_cancellation, Decimal("100.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("100.00"))
        self.assertEqual(settlement.retained_at_cancellation, Decimal("0.00"))
        refunds = PaymentTransaction.objects.filter(
            reservation=self.reservation, kind=PaymentTransaction.Kind.REFUND
        )
        self.assertEqual(refunds.count(), 1)
        self.assertEqual(refunds.get().amount, Decimal("100.00"))
        self.assertEqual(ledger_totals(self.reservation)["net"], Decimal("0.00"))

    def test_partial_refund_retains_correct_balance(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "100.00")
        response = self.cancel(
            CancellationSettlement.Outcome.REFUND,
            refund_amount="40.00",
            refund_method=PaymentTransaction.Method.CASH,
            refund_completed="on",
            note="Retain 60 under cancellation policy",
        )
        self.assertEqual(response.status_code, 302)
        self.assert_cancelled()
        settlement = CancellationSettlement.objects.get(reservation=self.reservation)
        self.assertEqual(settlement.net_received_at_cancellation, Decimal("100.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("40.00"))
        self.assertEqual(settlement.retained_at_cancellation, Decimal("60.00"))
        self.assertEqual(ledger_totals(self.reservation)["net"], Decimal("60.00"))

    def test_repeat_submission_does_not_duplicate_refund_or_settlement(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "100.00")
        payload = {
            "refund_amount": "100.00",
            "refund_method": PaymentTransaction.Method.BANK,
            "refund_completed": "on",
        }
        first = self.cancel(CancellationSettlement.Outcome.REFUND, **payload)
        second = self.cancel(CancellationSettlement.Outcome.REFUND, **payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assert_cancelled()
        self.assertEqual(CancellationSettlement.objects.filter(reservation=self.reservation).count(), 1)
        self.assertEqual(PaymentTransaction.objects.filter(
            reservation=self.reservation, kind=PaymentTransaction.Kind.REFUND
        ).count(), 1)

    def test_refund_larger_than_net_is_rejected_without_changes(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "50.00")
        response = self.cancel(
            CancellationSettlement.Outcome.REFUND,
            refund_amount="50.01",
            refund_method=PaymentTransaction.Method.BANK,
            refund_completed="on",
        )
        self.assertEqual(response.status_code, 200)
        self.assert_active()
        self.assertEqual(PaymentTransaction.objects.filter(reservation=self.reservation).count(), 1)

    def test_refund_requires_external_completion_confirmation(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "50.00")
        response = self.cancel(
            CancellationSettlement.Outcome.REFUND,
            refund_amount="50.00",
            refund_method=PaymentTransaction.Method.BANK,
        )
        self.assertEqual(response.status_code, 200)
        self.assert_active()
        self.assertFalse(PaymentTransaction.objects.filter(
            reservation=self.reservation, kind=PaymentTransaction.Kind.REFUND
        ).exists())

    def test_no_funds_choice_rejected_when_deposit_exists(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "50.00")
        response = self.cancel(CancellationSettlement.Outcome.NO_FUNDS)
        self.assertEqual(response.status_code, 200)
        self.assert_active()

    def test_cannot_cancel_currently_checked_in_guest(self):
        GuestStay.objects.create(
            reservation=self.reservation,
            checked_in_at=timezone.now(),
        )
        response = self.cancel(CancellationSettlement.Outcome.NO_FUNDS)
        self.assertEqual(response.status_code, 200)
        self.assert_active()

    def test_existing_refunds_reduce_balance_available_for_cancellation(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "100.00")
        self.payment(PaymentTransaction.Kind.REFUND, "25.00")
        response = self.cancel(
            CancellationSettlement.Outcome.REFUND,
            refund_amount="75.00",
            refund_method=PaymentTransaction.Method.BANK,
            refund_completed="on",
        )
        self.assertEqual(response.status_code, 302)
        self.assert_cancelled()
        settlement = CancellationSettlement.objects.get(reservation=self.reservation)
        self.assertEqual(settlement.net_received_at_cancellation, Decimal("75.00"))
        self.assertEqual(settlement.refunded_at_cancellation, Decimal("75.00"))
        self.assertEqual(settlement.retained_at_cancellation, Decimal("0.00"))
        self.assertEqual(ledger_totals(self.reservation)["net"], Decimal("0.00"))
        self.assertEqual(PaymentTransaction.objects.filter(
            reservation=self.reservation, kind=PaymentTransaction.Kind.REFUND
        ).count(), 2)

    def test_missing_cancel_confirmation_rejects_request(self):
        response = self.client.post(
            self.url,
            {"outcome": CancellationSettlement.Outcome.NO_FUNDS},
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assert_active()

    def test_admin_delete_protects_reservation_with_payment(self):
        self.payment(PaymentTransaction.Kind.DEPOSIT, "50.00")
        delete_url = reverse("admin:bookings_reservation_delete", args=[self.reservation.pk])
        response = self.client.get(delete_url, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Reservation.objects.filter(pk=self.reservation.pk).exists())
        self.assertEqual(PaymentTransaction.objects.filter(reservation=self.reservation).count(), 1)
