"""v165: read-only payment history must not block reservation admin POSTs."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Room, Reservation, ReservationItem


class ReservationDepositInlineSaveTests(TestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name="V165 hut", slug="v165-hut")
        self.room = Room.objects.create(hut=self.hut, name="Dorm", capacity=4)
        self.user = get_user_model().objects.create_superuser(
            "v165admin", "v165@example.test", "password"
        )
        self.client.force_login(self.user)
        self.start = timezone.localdate() + timedelta(days=2)
        self.end = self.start + timedelta(days=2)

    def test_add_reservation_without_payment_formset(self):
        response = self.client.post(reverse("admin:bookings_reservation_add"), {
            "name": "V165 guest", "email": "guest@example.test", "status": "confirmed",
            "check_in": self.start.isoformat(), "check_out": self.end.isoformat(),
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-0-room": str(self.room.pk), "items-0-beds": "1",
            "items-0-price_per_night": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservation.objects.filter(name="V165 guest").count(), 1)

    def test_edit_reservation_without_payment_formset(self):
        reservation = Reservation.objects.create(
            name="Before edit", status="confirmed", check_in=self.start,
            check_out=self.end,
        )
        item = ReservationItem.objects.create(
            reservation=reservation, room=self.room, beds=1, price_per_night="0"
        )
        response = self.client.post(
            reverse("admin:bookings_reservation_change", args=[reservation.pk]), {
                "name": "After edit", "email": "guest@example.test", "status": "confirmed",
                "check_in": self.start.isoformat(), "check_out": self.end.isoformat(),
                "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
                "items-0-id": str(item.pk), "items-0-reservation": str(reservation.pk),
                "items-0-room": str(self.room.pk), "items-0-beds": "1",
                "items-0-price_per_night": "0",
            }
        )
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.name, "After edit")

    def test_payment_history_visible_on_change_get(self):
        reservation = Reservation.objects.create(
            name="Guest", status="confirmed", check_in=self.start,
            check_out=self.end,
        )
        ReservationItem.objects.create(
            reservation=reservation, room=self.room, beds=1, price_per_night="0"
        )
        response = self.client.get(
            reverse("admin:bookings_reservation_change", args=[reservation.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payments and deposits")
