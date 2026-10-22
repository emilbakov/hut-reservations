"""PostgreSQL-only real transaction tests for concurrent hut reservations.

Uses TransactionTestCase, separate thread-local DB connections, and a barrier.
Run against an isolated PostgreSQL *test* database, never the live DB.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room
from .services import NotAvailable, create_reservation, free_beds, modify_reservation


class PostgreSQLConcurrencyTests(TransactionTestCase):
    """Each worker uses its own DB connection and its own transaction."""

    databases = {"default"}

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL; SQLite does not implement row-level SELECT FOR UPDATE")
        self.today = timezone.localdate()
        self.start = self.today + timedelta(days=10)
        self.end = self.start + timedelta(days=2)
        self.hut = Hut.objects.create(name="Concurrent Test Hut", slug="concurrent-test-hut")
        self.target = Room.objects.create(
            hut=self.hut, name="Last bed", capacity=1, price_per_night=Decimal("30.00")
        )
        self.source_a = Room.objects.create(
            hut=self.hut, name="Source A", capacity=1, price_per_night=Decimal("30.00")
        )
        self.source_b = Room.objects.create(
            hut=self.hut, name="Source B", capacity=1, price_per_night=Decimal("30.00")
        )

    def _parallel(self, actions):
        barrier = Barrier(len(actions), timeout=15)

        def worker(action):
            close_old_connections()
            try:
                # Each worker starts simultaneously with an independent connection.
                # A database lock may serialize subsequent work as intended.
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '12s'")
                barrier.wait()
                try:
                    return ("ok", action())
                except NotAvailable:
                    return ("unavailable", None)
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            futures = [pool.submit(worker, action) for action in actions]
            return [future.result(timeout=30) for future in futures]

    def _book(self, room, guest):
        return create_reservation(
            check_in=self.start, check_out=self.end,
            beds_by_room={room.pk: 1}, name=guest, email="test@example.com"
        )

    def _assert_target_safe(self):
        occupied = sum(
            ReservationItem.objects.filter(
                room=self.target, reservation__status__in=Reservation.HOLDING,
                reservation__check_in__lt=self.end,
                reservation__check_out__gt=self.start,
            ).values_list("beds", flat=True)
        )
        self.assertLessEqual(occupied, self.target.capacity)
        self.assertEqual(free_beds([self.target], self.start, self.end)[self.target.pk], 0)

    def test_two_simultaneous_creations_compete_for_last_bed(self):
        results = self._parallel([
            lambda: self._book(self.target, "Guest One"),
            lambda: self._book(self.target, "Guest Two"),
        ])
        self.assertEqual(sorted(outcome for outcome, _ in results), ["ok", "unavailable"])
        self.assertEqual(Reservation.objects.count(), 1)
        self._assert_target_safe()

    def test_two_simultaneous_moves_compete_for_last_bed(self):
        first = self._book(self.source_a, "Move One")
        second = self._book(self.source_b, "Move Two")
        before = {
            first.pk: (first.check_in, first.check_out, self.source_a.pk),
            second.pk: (second.check_in, second.check_out, self.source_b.pk),
        }

        def move(code):
            return modify_reservation(
                code=code, check_in=self.start, check_out=self.end,
                beds_by_room={self.target.pk: 1},
            )

        results = self._parallel([lambda: move(first.code), lambda: move(second.code)])
        self.assertEqual(sorted(outcome for outcome, _ in results), ["ok", "unavailable"])
        self._assert_target_safe()
        for reservation in (first, second):
            reservation.refresh_from_db()
            room_id = reservation.items.values_list("room_id", flat=True).get()
            if room_id != self.target.pk:
                self.assertEqual(
                    (reservation.check_in, reservation.check_out, room_id),
                    before[reservation.pk],
                )

    def test_failed_concurrent_move_keeps_original_booking(self):
        # One target bed is already occupied. Two competing moves must both fail,
        # and neither original reservation may change.
        self._book(self.target, "Occupant")
        first = self._book(self.source_a, "Move One")
        second = self._book(self.source_b, "Move Two")

        def move(code):
            return modify_reservation(
                code=code, check_in=self.start, check_out=self.end,
                beds_by_room={self.target.pk: 1},
            )

        results = self._parallel([lambda: move(first.code), lambda: move(second.code)])
        self.assertEqual([outcome for outcome, _ in results], ["unavailable", "unavailable"])
        self._assert_target_safe()
        for reservation, original_room in ((first, self.source_a), (second, self.source_b)):
            reservation.refresh_from_db()
            self.assertEqual((reservation.check_in, reservation.check_out), (self.start, self.end))
            self.assertEqual(
                list(reservation.items.values_list("room_id", "beds")),
                [(original_room.pk, 1)],
            )
