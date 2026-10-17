from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room

from .services import (
    NotAvailable, create_reservation, expire_pending, free_beds,
    modify_reservation,
)


def day(offset):
    return timezone.localdate() + timedelta(days=offset)


GUEST = {"name": "Ana", "email": "ana@example.com"}


def make_hut(slug="test-hut"):
    return Hut.objects.create(name=slug.replace("-", " ").title(), slug=slug)


class AvailabilityTests(TestCase):
    def setUp(self):
        self.hut = make_hut()
        self.room = Room.objects.create(hut=self.hut, name="Dorm", capacity=4, price_per_night="10.00")

    def book(self, start, end, beds, **kwargs):
        return create_reservation(
            check_in=day(start), check_out=day(end), beds_by_room={self.room.pk: beds},
            **GUEST, **kwargs,
        )

    def free(self, start, end):
        return free_beds([self.room], day(start), day(end))[self.room.pk]

    def test_empty_room_is_fully_free(self):
        self.assertEqual(self.free(1, 3), 4)

    def test_booked_beds_are_subtracted(self):
        self.book(1, 3, 3)
        self.assertEqual(self.free(1, 3), 1)
        self.assertEqual(self.free(2, 5), 1)

    def test_check_out_day_is_free_for_new_arrivals(self):
        self.book(1, 3, 4)
        self.assertEqual(self.free(3, 5), 4)
        self.assertEqual(self.free(0, 1), 4)

    def test_busiest_night_decides(self):
        # Two stays on different nights do not add up.
        self.book(1, 2, 3)
        self.book(2, 3, 3)
        self.assertEqual(self.free(1, 3), 1)

    def test_overbooking_is_refused(self):
        self.book(1, 3, 3)
        with self.assertRaises(NotAvailable):
            self.book(2, 4, 2)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_exact_fit_is_allowed(self):
        self.book(1, 3, 3)
        self.book(2, 4, 1)
        self.assertEqual(self.free(2, 3), 0)

    def test_cancelled_reservation_frees_beds(self):
        reservation = self.book(1, 3, 4)
        reservation.status = Reservation.Status.CANCELLED
        reservation.save()
        self.assertEqual(self.free(1, 3), 4)

    def test_pending_holds_beds_until_expired(self):
        reservation = self.book(1, 3, 4, status="pending")
        self.assertEqual(self.free(1, 3), 0)
        Reservation.objects.filter(pk=reservation.pk).update(
            created=timezone.now() - timedelta(hours=1)
        )
        self.assertEqual(expire_pending(), 1)
        self.assertEqual(self.free(1, 3), 4)

    def test_inactive_room_cannot_be_booked(self):
        self.room.is_active = False
        self.room.save()
        with self.assertRaises(NotAvailable):
            self.book(1, 3, 1)

    def test_price_is_snapshotted(self):
        reservation = self.book(1, 3, 2)
        self.room.price_per_night = "99.00"
        self.room.save()
        self.assertEqual(reservation.total_price, 40)  # 2 beds x 2 nights x 10


class BookingPageTests(TestCase):
    def setUp(self):
        self.hut = make_hut()
        self.dorm = Room.objects.create(hut=self.hut, name="Dorm", capacity=4, price_per_night="10.00")
        self.small = Room.objects.create(hut=self.hut, name="Small", capacity=2, price_per_night="20.00")
        self.url = reverse("bookings:hut_detail", args=[self.hut.slug])

    def post(self, start=1, end=3, **beds):
        data = {
            "check_in": day(start).isoformat(),
            "check_out": day(end).isoformat(),
            "name": "Ana",
            "email": "ana@example.com",
            f"room_{self.dorm.pk}": beds.get("dorm", 0),
            f"room_{self.small.pk}": beds.get("small", 0),
        }
        return self.client.post(self.url, data)

    def test_search_shows_rooms(self):
        response = self.client.get(
            self.url, {"check_in": day(1).isoformat(), "check_out": day(3).isoformat()}
        )
        self.assertContains(response, "Dorm")
        self.assertContains(response, "4 of 4")

    def test_booking_is_saved_and_emailed(self):
        response = self.post(dorm=2, small=1)
        reservation = Reservation.objects.get()
        self.assertRedirects(response, reservation.get_absolute_url())
        self.assertEqual(reservation.total_beds, 3)
        self.assertEqual(reservation.total_price, 80)  # (2x10 + 1x20) x 2 nights
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(reservation.code, mail.outbox[0].body)
        self.assertContains(self.client.get(reservation.get_absolute_url()), "Confirmed")

    def test_too_many_beds_is_rejected(self):
        response = self.post(dorm=5)
        self.assertContains(response, "Only 4 left in Dorm")
        self.assertFalse(Reservation.objects.exists())

    def test_full_room_cannot_be_booked(self):
        self.post(small=2)
        response = self.post(small=1)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertContains(response, "Full")

    def test_no_beds_is_rejected(self):
        response = self.post()
        self.assertContains(response, "Choose at least one bed")
        self.assertFalse(Reservation.objects.exists())

    def test_past_and_backwards_dates_are_rejected(self):
        self.assertContains(self.post(start=-2, end=1, dorm=1), "cannot be in the past")
        self.assertContains(self.post(start=3, end=3, dorm=1), "must be after arrival")
        self.assertFalse(Reservation.objects.exists())

    def test_guest_can_cancel(self):
        self.post(small=2)
        reservation = Reservation.objects.get()
        self.client.post(reverse("bookings:cancel", args=[reservation.code]))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "cancelled")
        self.assertEqual(free_beds([self.small], day(1), day(3))[self.small.pk], 2)


class AdminTests(TestCase):
    def setUp(self):
        self.hut = make_hut()
        self.room = Room.objects.create(hut=self.hut, name="Dorm", capacity=4)
        user = get_user_model().objects.create_superuser("keeper", "k@example.com", "pw")
        self.client.force_login(user)
        create_reservation(
            check_in=day(1), check_out=day(3), beds_by_room={self.room.pk: 3}, **GUEST
        )

    def add(self, beds):
        return self.client.post(
            reverse("admin:bookings_reservation_add"),
            {
                "name": "Boris", "email": "b@example.com", "status": "confirmed",
                "check_in": day(2).isoformat(), "check_out": day(4).isoformat(),
                "items-TOTAL_FORMS": 1, "items-INITIAL_FORMS": 0,
                "items-0-room": self.room.pk, "items-0-beds": beds,
                "items-0-price_per_night": "0",
            },
        )

    def test_admin_refuses_overbooking(self):
        response = self.add(2)
        self.assertContains(response, "only 1 free")
        self.assertEqual(Reservation.objects.count(), 1)

    def test_admin_allows_what_fits(self):
        self.assertEqual(self.add(1).status_code, 302)
        self.assertEqual(Reservation.objects.count(), 2)

class ServiceValidationTests(TestCase):
    def setUp(self):
        self.hut = make_hut()
        self.room = Room.objects.create(hut=self.hut, name="Validation dorm", capacity=3, price_per_night="12.00")

    def reserve(self, start=1, end=2, beds=1, **kwargs):
        return create_reservation(
            check_in=day(start), check_out=day(end),
            beds_by_room={self.room.pk: beds}, **GUEST, **kwargs,
        )

    def test_direct_service_refuses_past_dates(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.reserve(start=-1, end=2)
        self.assertFalse(Reservation.objects.exists())

    def test_direct_service_refuses_excessive_stay(self):
        from django.conf import settings
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.reserve(start=1, end=settings.BOOKING_MAX_NIGHTS + 2)

    def test_direct_service_refuses_negative_and_fractional_beds(self):
        from django.core.exceptions import ValidationError
        for beds in (-1, 1.5, True):
            with self.subTest(beds=beds), self.assertRaises(ValidationError):
                self.reserve(beds=beds)

    def test_direct_service_refuses_cancelled_initial_status(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.reserve(status="cancelled")

    def test_staff_dashboard_requires_authentication(self):
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_dashboard_shows_occupancy(self):
        user = get_user_model().objects.create_superuser("staff", password="pass")
        self.reserve(beds=2)
        self.client.force_login(user)
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertContains(response, "Occupancy calendar")
        self.assertContains(response, "Upcoming arrivals")


class CalendarAndModificationTests(TestCase):
    def setUp(self):
        self.hut = make_hut()
        self.room = Room.objects.create(hut=self.hut, name="Calendar Dorm", capacity=3, price_per_night="20.00")
        self.reservation = create_reservation(check_in=day(2), check_out=day(4),
            beds_by_room={self.room.pk: 2}, **GUEST)

    def test_calendar_does_not_expose_guests(self):
        target = day(2)
        response = self.client.get(reverse("bookings:calendar"),
            {"year": target.year, "month": target.month})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ana@example.com", response.content.decode())
        row = next(x for x in response.json()["days"] if x["date"] == target.isoformat())
        self.assertEqual(row["free_beds"], 1)

    def test_calendar_rejects_bad_month(self):
        self.assertEqual(self.client.get(reverse("bookings:calendar"),
            {"year": "bad", "month": 13}).status_code, 400)

    def test_guest_can_change_dates_and_beds(self):
        response = self.client.post(reverse("bookings:modify", args=[self.reservation.code]), {
            "check_in": day(5).isoformat(), "check_out": day(7).isoformat(),
            f"room_{self.room.pk}": 3,
        })
        self.assertEqual(response.status_code, 302)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.check_in, day(5))
        self.assertEqual(self.reservation.total_beds, 3)
        self.assertEqual(free_beds([self.room], day(2), day(4))[self.room.pk], 3)

    def test_failed_modification_keeps_original(self):
        create_reservation(check_in=day(5), check_out=day(7),
            beds_by_room={self.room.pk: 3}, name="Other", email="other@example.com")
        response = self.client.post(reverse("bookings:modify", args=[self.reservation.code]), {
            "check_in": day(5).isoformat(), "check_out": day(7).isoformat(),
            f"room_{self.room.pk}": 2,
        })
        self.assertEqual(response.status_code, 200)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.check_in, day(2))
        self.assertEqual(self.reservation.total_beds, 2)

    def test_cancelled_reservation_cannot_be_modified(self):
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save()
        response = self.client.get(reverse("bookings:modify", args=[self.reservation.code]))
        self.assertEqual(response.status_code, 302)

class DashboardPhaseFourTests(TestCase):
    def test_dashboard_requires_staff(self):
        from django.urls import reverse
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_csv_export_requires_staff(self):
        from django.urls import reverse
        response = self.client.get(reverse("bookings:dashboard_export"))
        self.assertEqual(response.status_code, 302)

    def test_csv_export_rejects_invalid_month_for_staff(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        user = get_user_model().objects.create_user(username="phase4staff", password="test-password", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse("bookings:dashboard_export"), {"year": "2026", "month": "13"})
        self.assertEqual(response.status_code, 400)

    def test_dashboard_displays_month_for_staff(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        user = get_user_model().objects.create_superuser(username="phase4viewer", password="test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("bookings:dashboard"), {"year": "2026", "month": "10"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Occupancy calendar")


class MultiHutTests(TestCase):
    def setUp(self):
        self.first_hut = make_hut("first-hut")
        self.second_hut = make_hut("second-hut")
        self.first_room = Room.objects.create(
            hut=self.first_hut, name="Dorm", capacity=4, price_per_night="10.00"
        )
        self.second_room = Room.objects.create(
            hut=self.second_hut, name="Dorm", capacity=4, price_per_night="15.00"
        )

    def test_same_room_name_allowed_in_different_huts(self):
        self.assertNotEqual(self.first_room.hut_id, self.second_room.hut_id)
        self.assertEqual(self.first_room.name, self.second_room.name)

    def test_service_rejects_rooms_from_different_huts(self):
        with self.assertRaises(ValidationError):
            create_reservation(
                check_in=day(1), check_out=day(3),
                beds_by_room={self.first_room.pk: 1, self.second_room.pk: 1},
                **GUEST,
            )
        self.assertFalse(Reservation.objects.exists())

    def test_service_rejects_room_without_hut(self):
        unassigned = Room.objects.create(
            name="Unassigned", capacity=2, price_per_night="10.00"
        )
        with self.assertRaises(ValidationError):
            create_reservation(
                check_in=day(1), check_out=day(3),
                beds_by_room={unassigned.pk: 1}, **GUEST,
            )

    def test_hut_booking_page_only_shows_its_rooms(self):
        response = self.client.get(
            reverse("bookings:hut_detail", args=[self.first_hut.slug]),
            {"check_in": day(1).isoformat(), "check_out": day(3).isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_hut.name)
        self.assertContains(response, f'name="room_{self.first_room.pk}"')
        self.assertNotContains(response, f'name="room_{self.second_room.pk}"')

    def test_calendar_filters_by_hut(self):
        create_reservation(
            check_in=day(2), check_out=day(4),
            beds_by_room={self.first_room.pk: 4}, **GUEST,
        )
        target = day(2)
        url = reverse("bookings:calendar")
        params = {"year": target.year, "month": target.month}
        first = self.client.get(url, {**params, "hut": self.first_hut.slug})
        second = self.client.get(url, {**params, "hut": self.second_hut.slug})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_day = next(x for x in first.json()["days"] if x["date"] == target.isoformat())
        second_day = next(x for x in second.json()["days"] if x["date"] == target.isoformat())
        self.assertEqual(first_day["free_beds"], 0)
        self.assertEqual(second_day["free_beds"], 4)

    def test_modification_cannot_move_reservation_to_another_hut(self):
        reservation = create_reservation(
            check_in=day(1), check_out=day(3),
            beds_by_room={self.first_room.pk: 1}, **GUEST,
        )
        with self.assertRaises(ValidationError):
            modify_reservation(
                code=reservation.code, check_in=day(2), check_out=day(4),
                beds_by_room={self.second_room.pk: 1},
            )
        reservation.refresh_from_db()
        self.assertEqual(reservation.check_in, day(1))
        self.assertEqual(
            list(reservation.items.values_list("room_id", flat=True)),
            [self.first_room.pk],
        )
