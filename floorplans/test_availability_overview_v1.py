"""Regression tests for the read-only SummitDesk property availability overview."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room
from .property_calendar_v138 import availability_overview, month_rows


@override_settings(SECURE_SSL_REDIRECT=False)
class AvailabilityOverviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(
            username='overview_manager', password='test-password', is_staff=True,
        )
        cls.hut = Hut.objects.create(name='Overview Test Hut', slug='overview-test-hut')
        cls.hut.managers.add(cls.manager)
        cls.room = Room.objects.create(hut=cls.hut, name='Active room', capacity=4)
        cls.inactive = Room.objects.create(
            hut=cls.hut, name='Inactive room', capacity=6, is_active=False,
        )
        today = timezone.localdate()
        cls.first = date(today.year + (today.month == 12), today.month % 12 + 1, 1)

    def book(self, room, beds, status=Reservation.Status.CONFIRMED):
        reservation = Reservation.objects.create(
            name='Test Guest', email='guest@example.com',
            check_in=self.first, check_out=self.first + timedelta(days=1),
            status=status,
        )
        ReservationItem.objects.create(reservation=reservation, room=room, beds=beds)
        return reservation

    def overview(self):
        rooms = [self.room, self.inactive]
        rows = month_rows(self.first, rooms, visible_ids=set())
        return availability_overview(rows, [self.first], self.first)

    def test_counts_bookings_closures_and_excludes_cancelled(self):
        self.book(self.room, 2, Reservation.Status.PENDING)
        self.book(self.room, 1, Reservation.Status.CANCELLED)
        bed = Bed.objects.create(room=self.room, number=1)
        BedClosure.objects.create(
            bed=bed, start=self.first, end=self.first + timedelta(days=1),
        )
        summary = self.overview()['focus']
        self.assertEqual((summary['booked'], summary['blocked'], summary['available']), (2, 1, 1))
        self.assertEqual(summary['capacity'], 4)
        self.assertEqual(summary['occupancy_pct'], 50)

    def test_inactive_rooms_do_not_inflate_available_beds(self):
        summary = self.overview()
        self.assertEqual(summary['active_rooms'], 1)
        self.assertEqual(summary['focus']['capacity'], 4)
        self.assertEqual(summary['focus']['available'], 4)

    def test_overbooked_room_is_flagged(self):
        self.book(self.room, 4)
        bed = Bed.objects.create(room=self.room, number=1)
        BedClosure.objects.create(
            bed=bed, start=self.first, end=self.first + timedelta(days=1),
        )
        summary = self.overview()['focus']
        self.assertEqual(summary['overbooked_rooms'], 1)
        self.assertEqual(summary['available'], 0)

    def test_calendar_renders_overview_and_daily_totals_without_writes(self):
        self.book(self.room, 2)
        self.client.force_login(self.manager)
        url = reverse('floorplans:staff_calendar', args=[self.hut.pk])
        response = self.client.get(url, {'year': self.first.year, 'month': self.first.month})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Availability at a glance')
        self.assertContains(response, 'property_availability_overview_v1.css')
        self.assertEqual(response.context['overview']['focus']['available'], 2)
        self.assertEqual(response.context['overview']['days'][0]['booked'], 2)
        self.assertEqual(Reservation.objects.count(), 1)
