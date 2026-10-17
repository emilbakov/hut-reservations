from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Hut, Room, Reservation, ReservationItem, PaymentTransaction

class FinancialReportTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.manager = U.objects.create_user(username="fin_manager", password="pass", is_staff=True)
        self.other = U.objects.create_user(username="fin_other", password="pass", is_staff=True)
        self.hut = Hut.objects.create(name="Finance Hut", slug="finance-hut")
        self.other_hut = Hut.objects.create(name="Other Hut", slug="other-finance-hut")
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other)
        self.room = Room.objects.create(hut=self.hut, name="Main", capacity=3)
        self.other_room = Room.objects.create(hut=self.other_hut, name="Other", capacity=3)
        today = timezone.localdate()
        self.res = Reservation.objects.create(name="Finance Guest", check_in=today, check_out=today+timedelta(days=1))
        ReservationItem.objects.create(reservation=self.res, room=self.room, beds=2, price_per_night=Decimal("50.00"))
        self.url = reverse("bookings:financial_dashboard")
        self.export = reverse("bookings:financial_export")
        self.client.force_login(self.manager)

    def add(self, kind, amount, reservation=None):
        return PaymentTransaction.objects.create(
            reservation=reservation or self.res, kind=kind, method="cash",
            amount=Decimal(amount), recorded_by=self.manager
        )

    def test_summary_receipts_refunds_and_outstanding(self):
        self.add("deposit", "30.00")
        self.add("payment", "20.00")
        self.add("refund", "10.00")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["receipts"], Decimal("50.00"))
        self.assertEqual(response.context["deposits"], Decimal("30.00"))
        self.assertEqual(response.context["net_cash"], Decimal("40.00"))
        self.assertEqual(response.context["outstanding"], Decimal("60.00"))

    def test_csv_exports_signed_refunds(self):
        self.add("refund", "5.00")
        response = self.client.get(self.export)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"-5.00", response.content)
        self.assertIn(b"Net cash received", response.content)

    def test_outsider_cannot_access(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url + "?hut=finance-hut").status_code, 404)
        self.assertEqual(self.client.get(self.export + "?hut=finance-hut").status_code, 404)

    def test_staff_cannot_see_other_hut_transactions(self):
        other_res = Reservation.objects.create(name="Private Guest", check_in=timezone.localdate(), check_out=timezone.localdate()+timedelta(days=1))
        ReservationItem.objects.create(reservation=other_res, room=self.other_room, beds=1, price_per_night=Decimal("500.00"))
        self.add("payment", "400.00", reservation=other_res)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Private Guest")
        self.assertEqual(response.context["receipts"], Decimal("0.00"))

    def test_cancelled_reservation_not_outstanding(self):
        self.res.status = Reservation.Status.CANCELLED
        self.res.save(update_fields=["status"])
        response = self.client.get(self.url)
        self.assertEqual(response.context["outstanding"], Decimal("0.00"))

    def test_invalid_month(self):
        self.assertEqual(self.client.get(self.url + "?month=13").status_code, 400)

    def test_report_is_read_only(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
