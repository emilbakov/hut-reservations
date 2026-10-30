"""PostgreSQL concurrency regression tests for SummitDesk reservations.

Run with Django's PostgreSQL test database (not the live database).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room
from .services import NotAvailable, create_reservation, free_beds


@override_settings(
    BOOKING_INITIAL_STATUS=Reservation.Status.CONFIRMED,
    BOOKING_MAX_DAYS_AHEAD=365,
    BOOKING_MAX_NIGHTS=30,
)
class ConcurrentBookingTests(TransactionTestCase):
    """TransactionTestCase permits independent transactions in worker threads."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Row-lock concurrency tests require PostgreSQL")
        hut = Hut.objects.create(name="Concurrency test hut", slug="concurrency-test-hut")
        self.room = Room.objects.create(hut=hut, name="One bed", capacity=1)
        self.start = timezone.localdate() + timedelta(days=7)
        self.end = self.start + timedelta(days=2)

    def _attempt(self, barrier, guest_name, start, end):
        # A thread must use its own DB connection. All workers begin together.
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                reservation = create_reservation(
                    check_in=start,
                    check_out=end,
                    beds_by_room={self.room.pk: 1},
                    name=guest_name,
                )
                return ("booked", reservation.pk)
            except NotAvailable:
                return ("unavailable", None)
        finally:
            connections.close_all()

    def _race(self, dates):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self._attempt, barrier, f"Guest {i}", start, end)
                for i, (start, end) in enumerate(dates, start=1)
            ]
            return [future.result(timeout=25) for future in futures]

    def test_simultaneous_requests_for_last_bed_cannot_overbook(self):
        results = self._race([(self.start, self.end), (self.start, self.end)])
        self.assertCountEqual(
            [outcome for outcome, _ in results],
            ["booked", "unavailable"],
        )
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(ReservationItem.objects.filter(room=self.room).count(), 1)
        self.assertEqual(free_beds([self.room], self.start, self.end)[self.room.pk], 0)

    def test_simultaneous_nonoverlapping_stays_both_succeed(self):
        second_start = self.end
        second_end = second_start + timedelta(days=2)
        results = self._race([
            (self.start, self.end),
            (second_start, second_end),
        ])
        self.assertEqual([outcome for outcome, _ in results].count("booked"), 2)
        self.assertEqual(Reservation.objects.count(), 2)
        self.assertEqual(ReservationItem.objects.filter(room=self.room).count(), 2)
        self.assertEqual(free_beds([self.room], self.start, self.end)[self.room.pk], 0)
        self.assertEqual(free_beds([self.room], second_start, second_end)[self.room.pk], 0)
