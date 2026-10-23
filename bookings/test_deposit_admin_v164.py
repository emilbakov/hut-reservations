"""v164: Django admin exposes deposit policy and read-only reservation summaries."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .deposits import deposit_summary
from .models import Hut, HutDepositPolicy, PaymentTransaction, Reservation, ReservationItem, Room


class DepositAdminV164Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superuser = User.objects.create_superuser(
            username="v164_admin", email="admin@example.test", password="test-password"
        )
        cls.manager = User.objects.create_user(
            username="v164_manager", password="test-password", is_staff=True
        )
        cls.hut = Hut.objects.create(name="Admin deposit hut", slug="admin-deposit-hut")
        cls.hut.managers.add(cls.manager)
        cls.room = Room.objects.create(hut=cls.hut, name="Room", capacity=2)
        today = timezone.localdate()
        cls.reservation = Reservation.objects.create(
            name="Admin guest", check_in=today + timedelta(days=7),
            check_out=today + timedelta(days=8), status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(
            reservation=cls.reservation, room=cls.room, beds=1,
            price_per_night=Decimal("100.00"),
        )

    def test_policy_inline_on_hut_and_separate_admin(self):
        self.client.force_login(self.superuser)
        hut_response = self.client.get(reverse("admin:bookings_hut_change", args=[self.hut.pk]))
        self.assertEqual(hut_response.status_code, 200)
        self.assertContains(hut_response, "deposit_policy")
        self.assertContains(hut_response, "auto_cancel_enabled")
        policy_response = self.client.get(reverse("admin:bookings_hutdepositpolicy_changelist"))
        self.assertEqual(policy_response.status_code, 200)

    def test_reservation_admin_shows_computed_deposit_and_ledger(self):
        PaymentTransaction.objects.create(
            reservation=self.reservation, kind=PaymentTransaction.Kind.DEPOSIT,
            method=PaymentTransaction.Method.CASH, amount=Decimal("20.00"),
            recorded_by=self.superuser,
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:bookings_reservation_change", args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deposit information")
        self.assertContains(response, "Deposit remaining")
        self.assertContains(response, "10.00")
        self.assertContains(response, "Payments and deposits")
        self.assertContains(response, "20.00")

    def test_hut_policy_changes_admin_summary(self):
        HutDepositPolicy.objects.create(hut=self.hut, percentage=50, due_days=5)
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:bookings_reservation_change", args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "50%")
        self.assertContains(response, "50.00")
        self.assertEqual(deposit_summary(self.reservation)["target"], Decimal("50.00"))

    def test_manager_cannot_use_policy_admin(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("admin:bookings_hutdepositpolicy_changelist"))
        self.assertNotEqual(response.status_code, 200)

    def test_payment_history_is_not_editable_from_reservation_admin(self):
        model_admin = admin.site._registry[Reservation]
        inline = next(inline for inline in model_admin.inlines if inline.model is PaymentTransaction)
        instance = inline(Reservation, admin.site)
        self.client.force_login(self.superuser)
        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        self.assertFalse(instance.has_add_permission(request, self.reservation))
        self.assertFalse(instance.has_change_permission(request, self.reservation))
        self.assertFalse(instance.has_delete_permission(request, self.reservation))
