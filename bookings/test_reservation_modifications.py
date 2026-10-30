"""Regression tests for SummitDesk reservation modifications and availability.

Run with Django's isolated test database; production reservations are not changed.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room
from .services import NotAvailable, free_beds, modify_reservation


class ReservationModificationAvailabilityTests(TestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name="Modification Test Hut", slug="modification-test-hut")
        self.other_hut = Hut.objects.create(name="Other Test Hut", slug="modification-other-hut")
        self.room_a = Room.objects.create(hut=self.hut, name="Room A", capacity=3)
        self.room_b = Room.objects.create(hut=self.hut, name="Room B", capacity=2)
        self.room_other = Room.objects.create(hut=self.other_hut, name="Other Room", capacity=3)
        self.start = timezone.localdate() + timedelta(days=10)
        self.end = self.start + timedelta(days=2)
        self.later = self.start + timedelta(days=5)
        self.later_end = self.later + timedelta(days=2)
        self.reservation = self.make_reservation("Original guest", self.room_a, 2, self.start, self.end)

    def make_reservation(self, name, room, beds, check_in, check_out):
        reservation = Reservation.objects.create(
            name=name,
            check_in=check_in,
            check_out=check_out,
            status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(
            reservation=reservation,
            room=room,
            beds=beds,
            price_per_night=room.price_per_night,
        )
        return reservation

    def assert_original_unchanged(self):
        self.reservation.refresh_from_db()
        self.assertEqual((self.reservation.check_in, self.reservation.check_out), (self.start, self.end))
        self.assertEqual(
            list(self.reservation.items.values_list("room_id", "beds")),
            [(self.room_a.pk, 2)],
        )

    def test_increasing_beds_cannot_overbook_and_does_not_change_original(self):
        self.make_reservation("Other guest", self.room_a, 1, self.start, self.end)
        self.assertEqual(free_beds([self.room_a], self.start, self.end)[self.room_a.pk], 0)

        with self.assertRaises(NotAvailable):
            modify_reservation(
                code=self.reservation.code,
                check_in=self.start,
                check_out=self.end,
                beds_by_room={self.room_a.pk: 3},
            )

        self.assert_original_unchanged()
        self.assertEqual(free_beds([self.room_a], self.start, self.end)[self.room_a.pk], 0)

    def test_moving_to_a_full_room_is_rejected_without_losing_original(self):
        self.make_reservation("Room B guest", self.room_b, 2, self.start, self.end)

        with self.assertRaises(NotAvailable):
            modify_reservation(
                code=self.reservation.code,
                check_in=self.start,
                check_out=self.end,
                beds_by_room={self.room_b.pk: 2},
            )

        self.assert_original_unchanged()
        self.assertEqual(free_beds([self.room_a], self.start, self.end)[self.room_a.pk], 1)
        self.assertEqual(free_beds([self.room_b], self.start, self.end)[self.room_b.pk], 0)

    def test_moving_dates_into_a_full_stay_is_rejected(self):
        self.make_reservation("Later guest", self.room_a, 3, self.later, self.later_end)

        with self.assertRaises(NotAvailable):
            modify_reservation(
                code=self.reservation.code,
                check_in=self.later,
                check_out=self.later_end,
                beds_by_room={self.room_a.pk: 2},
            )

        self.assert_original_unchanged()
        self.assertEqual(free_beds([self.room_a], self.later, self.later_end)[self.room_a.pk], 0)

    def test_partial_date_overlap_is_also_rejected(self):
        self.make_reservation("Overlap guest", self.room_a, 3, self.end, self.end + timedelta(days=2))

        with self.assertRaises(NotAvailable):
            modify_reservation(
                code=self.reservation.code,
                check_in=self.start + timedelta(days=1),
                check_out=self.end + timedelta(days=1),
                beds_by_room={self.room_a.pk: 2},
            )

        self.assert_original_unchanged()

    def test_valid_move_changes_room_and_dates_and_releases_old_capacity(self):
        updated = modify_reservation(
            code=self.reservation.code,
            check_in=self.later,
            check_out=self.later_end,
            beds_by_room={self.room_b.pk: 2},
        )

        self.assertEqual(updated.pk, self.reservation.pk)
        self.reservation.refresh_from_db()
        self.assertEqual((self.reservation.check_in, self.reservation.check_out), (self.later, self.later_end))
        self.assertEqual(
            list(self.reservation.items.values_list("room_id", "beds")),
            [(self.room_b.pk, 2)],
        )
        self.assertEqual(free_beds([self.room_a], self.start, self.end)[self.room_a.pk], 3)
        self.assertEqual(free_beds([self.room_b], self.later, self.later_end)[self.room_b.pk], 0)

    def test_cancelled_reservation_cannot_be_modified(self):
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            modify_reservation(
                code=self.reservation.code,
                check_in=self.later,
                check_out=self.later_end,
                beds_by_room={self.room_a.pk: 2},
            )

        self.assert_original_unchanged()
        self.assertEqual(free_beds([self.room_a], self.start, self.end)[self.room_a.pk], 3)

    def test_reservation_cannot_be_moved_to_another_hut(self):
        with self.assertRaises(ValidationError):
            modify_reservation(
                code=self.reservation.code,
                check_in=self.start,
                check_out=self.end,
                beds_by_room={self.room_other.pk: 2},
            )

        self.assert_original_unchanged()
        self.assertEqual(free_beds([self.room_other], self.start, self.end)[self.room_other.pk], 3)
