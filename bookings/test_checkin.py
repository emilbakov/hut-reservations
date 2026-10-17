"""Tests for manager guest arrival/departure tracking."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import GuestStay, Hut, Reservation, ReservationItem, Room


class ManagerStayTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="stay-manager", password="test", is_staff=True)
        self.other_manager = User.objects.create_user(username="stay-other", password="test", is_staff=True)
        self.admin = User.objects.create_superuser(username="stay-admin", email="admin@example.com", password="test")
        self.hut = Hut.objects.create(name="Stay Hut", slug="stay-hut")
        self.other_hut = Hut.objects.create(name="Other Stay Hut", slug="other-stay-hut")
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other_manager)
        self.room = Room.objects.create(hut=self.hut, name="Dorm", capacity=5)
        self.other_room = Room.objects.create(hut=self.other_hut, name="Dorm", capacity=5)
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(
            name="Alice", email="alice@example.com", check_in=today,
            check_out=today + timedelta(days=2), status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(reservation=self.reservation, room=self.room, beds=2)
        self.other = Reservation.objects.create(
            name="Bob", email="bob@example.com", check_in=today,
            check_out=today + timedelta(days=1), status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(reservation=self.other, room=self.other_room, beds=1)

    def act(self, reservation, action):
        return self.client.post(
            reverse("bookings:manager_stay_action", args=[reservation.code]),
            {"action": action},
        )

    def test_manager_sees_only_assigned_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("bookings:manager_stays"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice")
        self.assertNotContains(response, "Bob")

    def test_checkin_checkout_and_repeat_blocked(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.act(self.reservation, "check_out").status_code, 409)
        self.assertEqual(self.act(self.reservation, "check_in").status_code, 302)
        stay = GuestStay.objects.get(reservation=self.reservation)
        self.assertIsNotNone(stay.checked_in_at)
        self.assertEqual(stay.checked_in_by, self.manager)
        self.assertEqual(self.act(self.reservation, "check_in").status_code, 409)
        self.assertEqual(self.act(self.reservation, "check_out").status_code, 302)
        stay.refresh_from_db()
        self.assertIsNotNone(stay.checked_out_at)
        self.assertEqual(stay.checked_out_by, self.manager)
        self.assertEqual(self.act(self.reservation, "check_out").status_code, 409)

    def test_other_hut_denied(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.act(self.other, "check_in").status_code, 404)
        self.assertFalse(GuestStay.objects.filter(reservation=self.other).exists())

    def test_future_arrival_blocked(self):
        self.reservation.check_in += timedelta(days=1)
        self.reservation.check_out += timedelta(days=1)
        self.reservation.save()
        self.client.force_login(self.manager)
        self.assertEqual(self.act(self.reservation, "check_in").status_code, 409)

    def test_pending_booking_blocked(self):
        self.reservation.status = Reservation.Status.PENDING
        self.reservation.save(update_fields=["status"])
        self.client.force_login(self.manager)
        self.assertEqual(self.act(self.reservation, "check_in").status_code, 409)

    def test_get_cannot_modify(self):
        self.client.force_login(self.manager)
        url = reverse("bookings:manager_stay_action", args=[self.reservation.code])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_unassigned_staff_denied(self):
        user = get_user_model().objects.create_user(username="stay-unassigned", password="test", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("bookings:manager_stays")).status_code, 403)

    def test_superuser_can_see_all(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("bookings:manager_stays"))
        self.assertContains(response, "Alice")
        self.assertContains(response, "Bob")

    def test_mixed_hut_booking_denied(self):
        ReservationItem.objects.create(reservation=self.reservation, room=self.other_room, beds=1)
        self.client.force_login(self.manager)
        self.assertEqual(self.act(self.reservation, "check_in").status_code, 404)
