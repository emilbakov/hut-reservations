"""Regression tests for calendar moves and booking capacity invariants."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, Room
from .services import NotAvailable, create_reservation, free_beds, modify_reservation


class ReservationConflictTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.start = self.today + timedelta(days=20)
        self.end = self.start + timedelta(days=2)
        self.hut = Hut.objects.create(name='Conflict Test Hut', slug='conflict-test-hut')
        self.other_hut = Hut.objects.create(name='Other Conflict Hut', slug='other-conflict-hut')
        self.a = Room.objects.create(hut=self.hut, name='A', capacity=2, price_per_night=Decimal('25'))
        self.b = Room.objects.create(hut=self.hut, name='B', capacity=1, price_per_night=Decimal('25'))
        self.foreign = Room.objects.create(hut=self.other_hut, name='C', capacity=2, price_per_night=Decimal('25'))
        User = get_user_model()
        self.manager = User.objects.create_user(username='conflict_manager', password='test', is_staff=True)
        self.outsider = User.objects.create_user(username='conflict_outsider', password='test', is_staff=True)
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.outsider)

    def book(self, room=None, beds=1, start=None, end=None):
        return create_reservation(check_in=start or self.start, check_out=end or self.end,
                                  beds_by_room={(room or self.a).pk: beds},
                                  name='Test Guest', email='guest@example.com')

    def assert_original(self, reservation, room, beds, start=None, end=None):
        reservation.refresh_from_db()
        self.assertEqual(reservation.check_in, start or self.start)
        self.assertEqual(reservation.check_out, end or self.end)
        self.assertEqual(list(reservation.items.values_list('room_id', 'beds')), [(room.pk, beds)])

    def test_full_room_rejects_overlapping_booking(self):
        self.book(beds=2)
        with self.assertRaises(NotAvailable):
            self.book(beds=1)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_checkout_is_exclusive(self):
        self.book(beds=2)
        later = self.book(beds=2, start=self.end, end=self.end + timedelta(days=1))
        self.assertIsNotNone(later.pk)

    def test_partial_overlap_is_counted_each_night(self):
        self.book(beds=2)
        free = free_beds([self.a], self.end - timedelta(days=1), self.end + timedelta(days=1))
        self.assertEqual(free[self.a.pk], 0)

    def test_move_into_full_room_preserves_original(self):
        original = self.book(room=self.a, beds=1)
        self.book(room=self.b, beds=1)
        with self.assertRaises(NotAvailable):
            modify_reservation(code=original.code, check_in=self.start, check_out=self.end,
                               beds_by_room={self.b.pk: 1})
        self.assert_original(original, self.a, 1)

    def test_failed_date_move_preserves_original(self):
        original = self.book(room=self.a, beds=2)
        later = self.end + timedelta(days=3)
        self.book(room=self.a, beds=2, start=later, end=later + timedelta(days=2))
        with self.assertRaises(NotAvailable):
            modify_reservation(code=original.code, check_in=later,
                               check_out=later + timedelta(days=2), beds_by_room={self.a.pk: 2})
        self.assert_original(original, self.a, 2)

    def test_cross_hut_move_refused(self):
        original = self.book()
        with self.assertRaises(ValidationError):
            modify_reservation(code=original.code, check_in=self.start, check_out=self.end,
                               beds_by_room={self.foreign.pk: 1})
        self.assert_original(original, self.a, 1)

    def test_move_to_free_room_succeeds(self):
        original = self.book()
        modify_reservation(code=original.code, check_in=self.start, check_out=self.end,
                           beds_by_room={self.b.pk: 1})
        self.assert_original(original, self.b, 1)

    def test_move_cannot_exceed_room_capacity(self):
        original = self.book()
        with self.assertRaises(NotAvailable):
            modify_reservation(code=original.code, check_in=self.start, check_out=self.end,
                               beds_by_room={self.b.pk: 2})
        self.assert_original(original, self.a, 1)

    def test_unauthorized_manager_cannot_move(self):
        original = self.book()
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('bookings:calendar_move'), {
            'code': original.code, 'room': self.b.pk,
            'check_in': str(self.start + timedelta(days=1)), 'confirm': 'yes'})
        self.assertEqual(response.status_code, 404)
        self.assert_original(original, self.a, 1)

    def test_missing_confirmation_cannot_move(self):
        original = self.book()
        self.client.force_login(self.manager)
        response = self.client.post(reverse('bookings:calendar_move'), {
            'code': original.code, 'room': self.b.pk,
            'check_in': str(self.start + timedelta(days=1))})
        self.assertEqual(response.status_code, 404)
        self.assert_original(original, self.a, 1)

    def test_service_error_during_move_does_not_write(self):
        original = self.book()
        self.client.force_login(self.manager)
        with patch('bookings.calendar_drag.modify_reservation', side_effect=NotAvailable({'room': 0})):
            response = self.client.post(reverse('bookings:calendar_move'), {
                'code': original.code, 'room': self.b.pk,
                'check_in': str(self.start + timedelta(days=1)), 'confirm': 'yes'})
        self.assertEqual(response.status_code, 200)
        self.assert_original(original, self.a, 1)
