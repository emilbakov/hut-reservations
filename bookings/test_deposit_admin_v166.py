"""v166: Deposits have their own read-only admin list without ledger duplication."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DepositEntry, Hut, PaymentTransaction, Reservation, ReservationItem, Room


class DepositListAdminV166Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superuser = User.objects.create_superuser(
            username="v166_admin", email="v166@example.test", password="test-password"
        )
        cls.manager = User.objects.create_user(
            username="v166_manager", password="test-password", is_staff=True
        )
        cls.hut = Hut.objects.create(name="Deposit list hut", slug="deposit-list-hut")
        cls.hut.managers.add(cls.manager)
        room = Room.objects.create(hut=cls.hut, name="Room", capacity=2)
        today = timezone.localdate()
        cls.reservation = Reservation.objects.create(
            name="Deposit guest", check_in=today + timedelta(days=7),
            check_out=today + timedelta(days=8), status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(
            reservation=cls.reservation, room=room, beds=1,
            price_per_night=Decimal("100.00"),
        )
        cls.deposit = PaymentTransaction.objects.create(
            reservation=cls.reservation, kind=PaymentTransaction.Kind.DEPOSIT,
            method=PaymentTransaction.Method.BANK, amount=Decimal("40.00"),
            recorded_by=cls.superuser,
        )
        cls.payment = PaymentTransaction.objects.create(
            reservation=cls.reservation, kind=PaymentTransaction.Kind.PAYMENT,
            method=PaymentTransaction.Method.CASH, amount=Decimal("15.00"),
            recorded_by=cls.superuser,
        )

    def test_admin_has_separate_deposits_page(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:bookings_depositentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "40.00")
        self.assertContains(response, "Deposit guest")
        self.assertContains(response, self.reservation.code)
        self.assertContains(response, "Deposit list hut")
        self.assertNotContains(response, "15.00")
        self.assertEqual(list(response.context["cl"].queryset.values_list("pk", flat=True)), [self.deposit.pk])

    def test_deposit_admin_is_read_only(self):
        model_admin = admin.site._registry[DepositEntry]
        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.client.force_login(self.superuser)
        detail = self.client.get(reverse("admin:bookings_depositentry_change", args=[self.deposit.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, 'name="_save"')

    def test_hut_manager_cannot_access_admin_deposit_list(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("admin:bookings_depositentry_changelist"))
        self.assertNotEqual(response.status_code, 200)

    def test_deposits_are_same_ledger_records_and_protect_reservation(self):
        self.assertEqual(DepositEntry.objects.get(pk=self.deposit.pk).amount, Decimal("40.00"))
        self.assertEqual(PaymentTransaction.objects.count(), 2)
        with self.assertRaises(ProtectedError):
            self.reservation.delete()
