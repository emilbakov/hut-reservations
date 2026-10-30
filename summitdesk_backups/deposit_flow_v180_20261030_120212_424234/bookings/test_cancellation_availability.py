"""Regression tests: cancelling a booking must release its room capacity.

Run with:
    python manage.py test bookings.test_cancellation_availability
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room
from .services import create_reservation, free_beds


class CancellationAvailabilityTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username="availability-manager", password="test-pass", is_staff=True
        )
        self.hut = Hut.objects.create(name="Availability test hut", slug="availability-test-hut")
        self.hut.managers.add(self.manager)
        self.room = Room.objects.create(
            hut=self.hut, name="Three-bed room", capacity=3, price_per_night="10.00"
        )
        self.check_in = timezone.localdate() + timedelta(days=4)
        self.check_out = self.check_in + timedelta(days=2)

        self.to_cancel = Reservation.objects.create(
            name="Guest to cancel",
            check_in=self.check_in,
            check_out=self.check_out,
            status=Reservation.Status.PENDING,
        )
        ReservationItem.objects.create(
            reservation=self.to_cancel, room=self.room, beds=2, price_per_night="10.00"
        )

        self.other_guest = Reservation.objects.create(
            name="Guest keeping booking",
            check_in=self.check_in,
            check_out=self.check_out,
            status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(
            reservation=self.other_guest, room=self.room, beds=1, price_per_night="10.00"
        )

    def available(self):
        return free_beds([self.room], self.check_in, self.check_out)[self.room.pk]

    def test_manager_cancellation_releases_beds_and_allows_rebooking(self):
        """Test the real manager action, availability, and booking service together."""
        self.assertEqual(self.available(), 0)
        self.client.force_login(self.manager)

        # Confirm the booking first, as in the existing manager workflow.
        url = reverse("bookings:manager_reservation_action", args=[self.to_cancel.code])
        response = self.client.post(url, {"action": "confirm", 'deposit_amount': '0'}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.to_cancel.refresh_from_db()
        self.assertEqual(self.to_cancel.status, Reservation.Status.CONFIRMED)
        self.assertEqual(self.available(), 0)

        response = self.client.post(url, {"action": "cancel"}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.to_cancel.refresh_from_db()
        self.assertEqual(self.to_cancel.status, Reservation.Status.CANCELLED)
        self.assertEqual(self.available(), 2)

        # Cancellation must not change or remove a different guest's booking.
        self.other_guest.refresh_from_db()
        self.assertEqual(self.other_guest.status, Reservation.Status.CONFIRMED)
        self.assertEqual(self.other_guest.items.get(room=self.room).beds, 1)
        self.assertEqual(self.to_cancel.items.get(room=self.room).beds, 2)

        replacement = create_reservation(
            check_in=self.check_in,
            check_out=self.check_out,
            beds_by_room={self.room.pk: 2},
            status=Reservation.Status.CONFIRMED,
            name="Replacement guest",
        )
        self.assertEqual(replacement.items.get(room=self.room).beds, 2)
        self.assertEqual(self.available(), 0)

        # The cancelled booking is retained for history; it is not deleted.
        self.assertTrue(Reservation.objects.filter(pk=self.to_cancel.pk).exists())

    def test_pending_cancellation_also_releases_beds(self):
        """Pending bookings must release their capacity when cancelled."""
        self.assertEqual(self.available(), 0)
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("bookings:manager_reservation_action", args=[self.to_cancel.code]),
            {"action": "cancel"},
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.to_cancel.refresh_from_db()
        self.assertEqual(self.to_cancel.status, Reservation.Status.CANCELLED)
        self.assertEqual(self.available(), 2)
