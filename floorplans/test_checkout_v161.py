"""v161: PostgreSQL-safe locking on the floorplan arrivals/checkout POST."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import (
    Bed, BedAssignment, GuestStay, Hut, Reservation, ReservationItem, Room,
)
from floorplans.housekeeping_events import BedCleaningEvent
from floorplans.housekeeping_models import BedHousekeeping


class FloorplanCheckoutV161Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(
            username='v161_manager', password='test', is_staff=True
        )
        cls.outsider = get_user_model().objects.create_user(
            username='v161_outsider', password='test', is_staff=True
        )
        cls.hut = Hut.objects.create(name='V161 Hut', slug='v161-hut')
        cls.other_hut = Hut.objects.create(name='V161 Other', slug='v161-other')
        cls.hut.managers.add(cls.manager)
        cls.room_a = Room.objects.create(hut=cls.hut, name='Room A', capacity=2)
        cls.room_b = Room.objects.create(hut=cls.hut, name='Room B', capacity=2)
        cls.other_room = Room.objects.create(hut=cls.other_hut, name='Private', capacity=2)
        cls.reservation = Reservation.objects.create(
            name='V161 Guest', check_in=timezone.localdate(),
            check_out=timezone.localdate() + timedelta(days=2),
            status=Reservation.Status.CONFIRMED,
        )
        cls.item_a = ReservationItem.objects.create(
            reservation=cls.reservation, room=cls.room_a, beds=1
        )
        cls.item_b = ReservationItem.objects.create(
            reservation=cls.reservation, room=cls.room_b, beds=1
        )
        cls.bed_a = Bed.objects.create(room=cls.room_a, number=1)
        cls.bed_b = Bed.objects.create(room=cls.room_b, number=1)
        BedAssignment.objects.create(item=cls.item_a, bed=cls.bed_a)
        BedAssignment.objects.create(item=cls.item_b, bed=cls.bed_b)

    def setUp(self):
        self.client.force_login(self.manager)
        self.url = reverse('floorplans:staff_arrivals', args=[self.hut.pk])

    def post_action(self, action, reservation=None):
        return self.client.post(self.url, {
            'action': action,
            'reservation_id': (reservation or self.reservation).pk,
        }, secure=True)

    def test_post_uses_postgresql_compatible_lock_without_distinct(self):
        # SQLite silently accepts the old query; check its shape explicitly.
        with patch('floorplans.staff_arrivals.get_object_or_404', wraps=get_object_or_404) as getter:
            response = self.post_action('check_in')
        self.assertEqual(response.status_code, 302)
        queryset = getter.call_args.args[0]
        self.assertTrue(queryset.query.select_for_update)
        self.assertFalse(queryset.query.distinct)
        self.assertNotIn('bookings_reservationitem', [
            join.table_name for alias, join in queryset.query.alias_map.items()
            if alias != queryset.query.base_table
        ])

    def test_multi_room_checkout_marks_assigned_beds_dirty(self):
        self.assertEqual(self.post_action('check_in').status_code, 302)
        self.assertEqual(self.post_action('check_out').status_code, 302)
        stay = GuestStay.objects.get(reservation=self.reservation)
        self.assertIsNotNone(stay.checked_in_at)
        self.assertIsNotNone(stay.checked_out_at)
        self.assertEqual(stay.checked_out_by, self.manager)
        self.assertEqual(BedHousekeeping.objects.filter(
            bed__in=[self.bed_a, self.bed_b], state='needs_cleaning'
        ).count(), 2)
        self.assertEqual(BedCleaningEvent.objects.filter(
            reservation=self.reservation, action='checkout'
        ).count(), 2)

    def test_repeat_checkout_does_not_create_duplicate_cleaning_events(self):
        self.post_action('check_in')
        self.post_action('check_out')
        self.assertEqual(self.post_action('check_out').status_code, 302)
        self.assertEqual(BedCleaningEvent.objects.filter(
            reservation=self.reservation, action='checkout'
        ).count(), 2)

    def test_other_hut_reservation_cannot_be_checked_out(self):
        other = Reservation.objects.create(
            name='Other Hut Guest', check_in=timezone.localdate(),
            check_out=timezone.localdate() + timedelta(days=1),
            status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(reservation=other, room=self.other_room, beds=1)
        response = self.post_action('check_out', other)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(GuestStay.objects.filter(reservation=other).exists())

    def test_cleaning_failure_rolls_back_checkout(self):
        self.post_action('check_in')
        with patch('floorplans.staff_arrivals.mark_checkout_beds_dirty',
                   side_effect=RuntimeError('simulated housekeeping failure')):
            with self.assertRaisesMessage(RuntimeError, 'simulated housekeeping failure'):
                self.post_action('check_out')
        stay = GuestStay.objects.get(reservation=self.reservation)
        self.assertIsNone(stay.checked_out_at)
