"""Public hut detail regression tests: presentation, real availability, booking writes."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room


class PublicHutDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut = Hut.objects.create(name="Rila Mountain Lodge", slug="rila-mountain-lodge", location="Rila Mountains", description="A welcoming hut on the trail.")
        cls.room = Room.objects.create(hut=cls.hut, name="Shared dorm", capacity=4, price_per_night=Decimal("24.00"))
        cls.other_room = Room.objects.create(hut=cls.hut, name="Double room", capacity=2, price_per_night=Decimal("39.00"))
        cls.inactive = Room.objects.create(hut=cls.hut, name="Closed room", capacity=3, is_active=False)
        cls.hidden = Hut.objects.create(name="Hidden Hut", slug="hidden-hut", is_active=False)
        cls.start = timezone.localdate() + timedelta(days=14)
        cls.end = cls.start + timedelta(days=2)

    def url(self):
        return reverse("bookings:hut_detail", kwargs={"slug": self.hut.slug})

    def dates(self):
        return {"check_in": self.start.isoformat(), "check_out": self.end.isoformat()}

    def test_hut_page_uses_public_layout_and_only_active_rooms(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "bookings/public_hut_v125.html")
        self.assertContains(response, "Rila Mountain Lodge")
        self.assertContains(response, "Shared dorm")
        self.assertContains(response, "Double room")
        self.assertNotContains(response, "Closed room")
        self.assertContains(response, "Check dates for availability")
        self.assertNotContains(response, "4 available for your stay")
        self.assertNotContains(response, "ph-reservation-form")

    def test_inactive_hut_not_public(self):
        response = self.client.get(reverse("bookings:hut_detail", kwargs={"slug": self.hidden.slug}))
        self.assertEqual(response.status_code, 404)

    def test_date_handoff_shows_live_availability(self):
        response = self.client.get(self.url(), self.dates())
        self.assertContains(response, "4 available for your stay")
        self.assertContains(response, "2 available for your stay")
        self.assertContains(response, 'name="check_in"', html=False)
        self.assertContains(response, 'name="check_out"', html=False)
        self.assertContains(response, "Your details")
        self.assertContains(response, "Request reservation")

    def test_pending_reservations_and_closures_reduce_free_beds(self):
        res = Reservation.objects.create(name="Other guest", check_in=self.start, check_out=self.end, status=Reservation.Status.PENDING)
        ReservationItem.objects.create(reservation=res, room=self.room, beds=2, price_per_night=Decimal("24.00"))
        bed = Bed.objects.create(room=self.room, number=1)
        BedClosure.objects.create(bed=bed, start=self.start, end=self.end)
        response = self.client.get(self.url(), self.dates())
        self.assertContains(response, "1 available for your stay")
        self.assertNotContains(response, "4 available for your stay")

    def test_invalid_dates_do_not_display_fake_availability(self):
        response = self.client.get(self.url(), {"check_in": self.end.isoformat(), "check_out": self.start.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Departure must be after arrival")
        self.assertNotContains(response, "available for your stay")
        self.assertNotContains(response, "ph-reservation-form")

    def test_guest_can_book_selected_room(self):
        payload = {**self.dates(), "name": "Guest Test", "email": "guest@example.com", "phone": "", "notes": "", f"room_{self.room.pk}": "2", f"room_{self.other_room.pk}": "0"}
        response = self.client.post(self.url(), payload)
        self.assertEqual(response.status_code, 302)
        reservation = Reservation.objects.get(name="Guest Test")
        self.assertEqual(reservation.check_in, self.start)
        self.assertEqual(reservation.check_out, self.end)
        self.assertEqual(reservation.items.get(room=self.room).beds, 2)
        self.assertEqual(reservation.items.count(), 1)

    def test_booking_form_rejects_more_beds_than_free(self):
        payload = {**self.dates(), "name": "Guest Test", "email": "guest@example.com", f"room_{self.room.pk}": "9"}
        response = self.client.post(self.url(), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only 4 left")
        self.assertFalse(Reservation.objects.filter(name="Guest Test").exists())

    def test_legacy_book_page_keeps_existing_template(self):
        response = self.client.get(reverse("bookings:book"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "bookings/book.html")
