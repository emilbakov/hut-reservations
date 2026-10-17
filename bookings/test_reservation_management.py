"""Security tests for the hut manager reservation workflow."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Room, Reservation, ReservationItem


class ManagerReservationWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="workflow-manager", password="test-pass", is_staff=True)
        self.outsider = User.objects.create_user(username="workflow-outsider", password="test-pass", is_staff=True)
        self.admin = User.objects.create_superuser(username="workflow-admin", email="admin@example.com", password="test-pass")
        self.a = Hut.objects.create(name="A", slug="workflow-a")
        self.b = Hut.objects.create(name="B", slug="workflow-b")
        self.a.managers.add(self.manager)
        self.b.managers.add(self.outsider)
        self.room_a = Room.objects.create(hut=self.a, name="A room", capacity=5)
        self.room_b = Room.objects.create(hut=self.b, name="B room", capacity=5)
        start = timezone.localdate() + timedelta(days=4)
        self.res_a = Reservation.objects.create(name="Alice", email="alice@example.com", check_in=start, check_out=start + timedelta(days=2), status=Reservation.Status.PENDING)
        self.res_b = Reservation.objects.create(name="Bob", email="bob@example.com", check_in=start, check_out=start + timedelta(days=2), status=Reservation.Status.PENDING)
        ReservationItem.objects.create(reservation=self.res_a, room=self.room_a, beds=1, price_per_night="10.00")
        ReservationItem.objects.create(reservation=self.res_b, room=self.room_b, beds=1, price_per_night="10.00")

    def action(self, reservation, action):
        return self.client.post(reverse("bookings:manager_reservation_action", args=[reservation.code]), {"action": action})

    def test_manager_only_sees_own_reservations(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("bookings:manager_reservations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice")
        self.assertNotContains(response, "Bob")

    def test_manager_cannot_change_other_hut(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.action(self.res_b, "cancel").status_code, 404)
        self.res_b.refresh_from_db()
        self.assertEqual(self.res_b.status, Reservation.Status.PENDING)

    def test_confirm_then_cancel_own_reservation(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.action(self.res_a, "confirm").status_code, 302)
        self.res_a.refresh_from_db()
        self.assertEqual(self.res_a.status, Reservation.Status.CONFIRMED)
        self.assertEqual(self.action(self.res_a, "cancel").status_code, 302)
        self.res_a.refresh_from_db()
        self.assertEqual(self.res_a.status, Reservation.Status.CANCELLED)

    def test_action_get_is_not_allowed(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("bookings:manager_reservation_action", args=[self.res_a.code]))
        self.assertEqual(response.status_code, 405)

    def test_unassigned_staff_is_denied(self):
        user = get_user_model().objects.create_user(username="workflow-unassigned", password="test-pass", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("bookings:manager_reservations")).status_code, 403)

    def test_superuser_can_see_all(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("bookings:manager_reservations"))
        self.assertContains(response, "Alice")
        self.assertContains(response, "Bob")

    def test_mixed_hut_reservation_is_not_manager_editable(self):
        ReservationItem.objects.create(reservation=self.res_a, room=self.room_b, beds=1, price_per_night="10.00")
        self.client.force_login(self.manager)
        response = self.client.get(reverse("bookings:manager_reservations"))
        self.assertNotContains(response, "alice@example.com")
        self.assertEqual(self.action(self.res_a, "cancel").status_code, 404)
