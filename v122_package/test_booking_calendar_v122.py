"""Regression tests to run with the server's Django test database."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.booking_calendar_v122 import booking_month
from bookings.models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room
from bookings.services import free_beds


@override_settings(BOOKING_MAX_DAYS_AHEAD=365, BOOKING_MAX_NIGHTS=30)
class StaffBookingCalendarTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username='v122manager', password='test-password', is_staff=False)
        self.hut = Hut.objects.create(name='Alpine hut', slug='v122-alpine')
        self.hut.managers.add(self.manager)
        self.room1 = Room.objects.create(hut=self.hut, name='Dorm', capacity=4, price_per_night=20)
        self.room2 = Room.objects.create(hut=self.hut, name='Twin', capacity=2, price_per_night=30)
        self.other_hut = Hut.objects.create(name='Private hut', slug='v122-private')
        self.other_room = Room.objects.create(hut=self.other_hut, name='Secret', capacity=50)
        self.start = (timezone.localdate().replace(day=28) + timedelta(days=4)).replace(day=1) + timedelta(days=4)
        self.end = self.start + timedelta(days=2)
        self.manual = reverse('bookings:manual_booking')
        self.property = reverse('floorplans:staff_new_booking', args=[self.hut.pk])

    def _day(self, month_data, value):
        return next(day for week in month_data['weeks'] for day in week
                    if day and day['date'] == value.isoformat())

    def test_daily_counts_match_booking_service_including_closures(self):
        booking = Reservation.objects.create(name='Existing', check_in=self.start,
            check_out=self.end, status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=booking, room=self.room1, beds=2, price_per_night=20)
        bed = Bed.objects.create(room=self.room2, number=1)
        BedClosure.objects.create(bed=bed, start=self.start, end=self.end, reason='Maintenance')
        # A second closure for the same numbered bed must not reduce capacity twice.
        BedClosure.objects.create(bed=bed, start=self.start, end=self.end, reason='Inspection')
        other_booking = Reservation.objects.create(name='Other hut', check_in=self.start,
            check_out=self.end, status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=other_booking, room=self.other_room, beds=50)
        result = booking_month([self.room1, self.room2], self.start, self.end,
                               today=timezone.localdate())
        self.assertEqual(self._day(result, self.start)['free'], 3)
        for offset in (0, 1):
            day = self.start + timedelta(days=offset)
            expected = sum(free_beds([self.room1, self.room2], day, day + timedelta(days=1)).values())
            self.assertEqual(self._day(result, day)['free'], expected)
        self.assertTrue(self._day(result, self.start)['in_stay'])
        self.assertTrue(self._day(result, self.start)['is_checkin'])
        self.assertTrue(self._day(result, self.end)['is_checkout'])
        self.assertFalse(self._day(result, self.end)['in_stay'])

    def test_cancelled_reservation_does_not_block_and_pending_does(self):
        pending = Reservation.objects.create(name='Pending', check_in=self.start,
            check_out=self.end, status=Reservation.Status.PENDING)
        ReservationItem.objects.create(reservation=pending, room=self.room1, beds=2)
        cancelled = Reservation.objects.create(name='Cancelled', check_in=self.start,
            check_out=self.end, status=Reservation.Status.CANCELLED)
        ReservationItem.objects.create(reservation=cancelled, room=self.room2, beds=2)
        result = booking_month([self.room1, self.room2], self.start, self.end,
                               today=timezone.localdate())
        self.assertEqual(self._day(result, self.start)['free'], 4)

    def test_both_booking_urls_display_same_month_and_counts(self):
        self.client.force_login(self.manager)
        params = {'check_in': self.start.isoformat(), 'check_out': self.end.isoformat()}
        for url, query in ((self.manual, {'hut': self.hut.pk, **params}),
                           (self.property, params)):
            with self.subTest(url=url):
                response = self.client.get(url, query)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Daily bed availability calendar')
                self.assertContains(response, 'Beds free per night')
                self.assertEqual(self._day(response.context['booking_calendar'], self.start)['free'], 6)

    def test_calendar_month_is_bounded_and_navigation_keeps_dates(self):
        self.client.force_login(self.manager)
        params = {'hut': self.hut.pk, 'check_in': self.start.isoformat(),
                  'check_out': self.end.isoformat(), 'cal_month': '9999-99'}
        response = self.client.get(self.manual, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['booking_calendar']['month'], self.start.strftime('%Y-%m'))
        response = self.client.get(self.manual, {**params, 'cal_month': '2999-01'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['booking_calendar']['next'])
        self.assertContains(response, 'cal_month=')

    def test_unauthorized_hut_still_denied(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.manual, {'hut': self.other_hut.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse('floorplans:staff_new_booking', args=[self.other_hut.pk])).status_code, 404)
