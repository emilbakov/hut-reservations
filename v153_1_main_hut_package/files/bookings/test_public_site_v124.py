"""Regression tests for public hut discovery and booking-date handoff."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room


class PublicSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut = Hut.objects.create(name="Rila Lodge", slug="rila-lodge", location="Rila", is_active=True)
        from .models import PublicWebsiteSettings
        PublicWebsiteSettings.objects.create(main_hut=cls.hut)
        cls.other = Hut.objects.create(name="Pirin Refuge", slug="pirin-refuge", location="Pirin", is_active=True)
        cls.hidden = Hut.objects.create(name="Private Hut", slug="private-hut", is_active=False)
        cls.room = Room.objects.create(hut=cls.hut, name="Dorm", capacity=4, price_per_night=Decimal("25.00"))
        cls.room2 = Room.objects.create(hut=cls.other, name="Room", capacity=2, price_per_night=Decimal("35.00"))
        cls.start = timezone.localdate() + timedelta(days=12)
        cls.end = cls.start + timedelta(days=2)

    def search(self, **extra):
        params = {"check_in": self.start.isoformat(), "check_out": self.end.isoformat(), "beds": "1"}
        params.update(extra)
        return self.client.get(reverse("bookings:public_home"), params)

    def test_homepage_and_staff_entry(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rila Lodge")
        self.assertContains(response, "All huts")
        self.assertContains(response, "Rila Lodge")
        self.assertNotContains(response, "Private Hut")
        self.assertContains(response, reverse("bookings:staff_login"))
        self.assertEqual(reverse("bookings:role_landing"), "/welcome/")

    def test_directory_search_by_location(self):
        response = self.client.get(reverse("bookings:hut_list"), {"q": "Pirin"})
        self.assertContains(response, "Pirin Refuge")
        self.assertEqual([card["hut"].pk for card in response.context["cards"]], [self.other.pk])

    def test_dates_show_real_capacity_and_preserve_handoff(self):
        response = self.search()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "4 available for your stay")
        self.assertNotContains(response, "Pirin Refuge")
        self.assertContains(response, 'action="/" id="ph-date-form"')

    def test_pending_and_confirmed_reduce_availability(self):
        for status, beds in [(Reservation.Status.PENDING, 2), (Reservation.Status.CONFIRMED, 1)]:
            reservation = Reservation.objects.create(
                name="Test", email="test@example.com", check_in=self.start, check_out=self.end, status=status,
            )
            ReservationItem.objects.create(reservation=reservation, room=self.room, beds=beds, price_per_night=25)
        response = self.search(beds="2")
        self.assertContains(response, "1 available for your stay")
        self.assertNotContains(response, "Pirin Refuge")

    def test_cancelled_does_not_reduce_availability(self):
        reservation = Reservation.objects.create(
            name="Test", check_in=self.start, check_out=self.end, status=Reservation.Status.CANCELLED,
        )
        ReservationItem.objects.create(reservation=reservation, room=self.room, beds=4, price_per_night=25)
        self.assertContains(self.search(beds="4"), "Rila Lodge")

    def test_bed_closure_reduces_available_beds(self):
        bed = Bed.objects.create(room=self.room, number=1)
        BedClosure.objects.create(bed=bed, start=self.start, end=self.end)
        self.assertContains(self.search(beds="4"), "3 available for your stay")
        self.assertContains(self.search(beds="3"), "Rila Lodge")

    def test_invalid_dates_do_not_claim_availability(self):
        response = self.client.get(reverse("bookings:public_home"), {"check_in": self.end, "check_out": self.start})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Departure must be after arrival")
        self.assertNotContains(response, "beds free for your stay")

    def test_no_booking_writes(self):
        before = Reservation.objects.count()
        self.search(beds="2")
        self.assertEqual(Reservation.objects.count(), before)
