from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, Room


@override_settings(BOOKING_MAX_DAYS_AHEAD=365, BOOKING_MAX_NIGHTS=30)
class ManualBookingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="manual-manager", password="test", is_staff=True)
        self.other = User.objects.create_user(username="other-manager", password="test", is_staff=True)
        self.hut = Hut.objects.create(name="First hut", slug="manual-first")
        self.hut.managers.add(self.manager)
        self.other_hut = Hut.objects.create(name="Other hut", slug="manual-other")
        self.other_hut.managers.add(self.other)
        self.room = Room.objects.create(hut=self.hut, name="A", capacity=3, price_per_night=20)
        self.other_room = Room.objects.create(hut=self.other_hut, name="B", capacity=3, price_per_night=20)
        self.url = reverse("bookings:manual_booking")
        start = timezone.localdate() + timedelta(days=2)
        self.data = {
            "hut": str(self.hut.pk), "check_in": start.isoformat(),
            "check_out": (start + timedelta(days=2)).isoformat(),
            "name": "Walk-in guest", "email": "", "phone": "+359888123456",
            f"beds_{self.room.pk}": "2",
        }

    def test_anonymous_cannot_open(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_manager_can_create_without_email(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 302)
        booking = Reservation.objects.get(name="Walk-in guest")
        self.assertEqual(booking.email, "")
        self.assertEqual(booking.status, Reservation.Status.CONFIRMED)
        self.assertEqual(booking.items.get().room, self.room)
        self.assertEqual(booking.items.get().beds, 2)

    def test_other_hut_is_forbidden(self):
        self.client.force_login(self.manager)
        data = {**self.data, "hut": str(self.other_hut.pk), f"beds_{self.other_room.pk}": "2"}
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_no_contact_rejected(self):
        self.client.force_login(self.manager)
        data = {**self.data, "phone": ""}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_overbooking_rejected(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_nonstaff_denied(self):
        user = get_user_model().objects.create_user(username="regular-manual", password="test")
        self.client.force_login(user)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertEqual(Reservation.objects.count(), 0)
