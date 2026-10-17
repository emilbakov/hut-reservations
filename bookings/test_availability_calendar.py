from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .availability_calendar import build_month
from .models import Hut, Room, Reservation, ReservationItem


class AvailabilityCalendarTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('calendar_manager', password='pw', is_staff=True)
        self.other = User.objects.create_user('calendar_other', password='pw', is_staff=True)
        self.superuser = User.objects.create_superuser('calendar_admin', 'admin@example.com', 'pw')
        self.hut = Hut.objects.create(name='Calendar Hut', slug='calendar-hut')
        self.private = Hut.objects.create(name='Private Hut', slug='private-calendar-hut')
        self.hut.managers.add(self.manager)
        self.private.managers.add(self.other)
        self.room = Room.objects.create(hut=self.hut, name='Bunks', capacity=3)
        self.private_room = Room.objects.create(hut=self.private, name='Private room', capacity=2)
        self.first = timezone.localdate().replace(day=1)
        self.url = reverse('bookings:availability_calendar')

    def reserve(self, room, start, end, beds, status=Reservation.Status.CONFIRMED):
        reservation = Reservation.objects.create(name='Test Guest', email='guest@example.com',
            check_in=start, check_out=end, status=status)
        ReservationItem.objects.create(reservation=reservation, room=room, beds=beds)
        return reservation

    def test_empty_month_has_all_capacity(self):
        rows = build_month(self.first, [self.room])
        self.assertTrue(all(cell['available'] == 3 for cell in rows[0]['days']))

    def test_checkout_day_is_not_occupied(self):
        self.reserve(self.room, self.first, self.first + timedelta(days=2), 2)
        cells = build_month(self.first, [self.room])[0]['days']
        self.assertEqual([cells[i]['booked'] for i in range(3)], [2, 2, 0])

    def test_pending_counts_cancelled_excluded(self):
        self.reserve(self.room, self.first, self.first + timedelta(days=1), 1, Reservation.Status.PENDING)
        self.reserve(self.room, self.first, self.first + timedelta(days=1), 2, Reservation.Status.CANCELLED)
        self.assertEqual(build_month(self.first, [self.room])[0]['days'][0]['booked'], 1)

    def test_overbooking_is_flagged(self):
        self.reserve(self.room, self.first, self.first + timedelta(days=1), 2)
        self.reserve(self.room, self.first, self.first + timedelta(days=1), 2)
        cell = build_month(self.first, [self.room])[0]['days'][0]
        self.assertEqual(cell['available'], 0)
        self.assertTrue(cell['overbooked'])

    def test_cross_month_stay_is_counted(self):
        self.reserve(self.room, self.first - timedelta(days=2), self.first + timedelta(days=1), 1)
        self.assertEqual(build_month(self.first, [self.room])[0]['days'][0]['booked'], 1)

    def test_anonymous_user_redirected(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_manager_only_sees_assigned_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calendar Hut')
        self.assertNotContains(response, 'Private Hut')
        self.assertEqual(self.client.get(self.url, {'hut': self.private.slug}).status_code, 404)

    def test_other_room_filter_is_not_visible(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url, {'room': self.private_room.pk}).status_code, 404)

    def test_superuser_sees_both_huts(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Private Hut')

    def test_invalid_month_falls_back_to_current(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url, {'month': '13', 'year': '9999999999999999999'})
        self.assertEqual(response.status_code, 200)

    def test_calendar_get_does_not_modify_booking(self):
        reservation = self.reserve(self.room, self.first, self.first + timedelta(days=1), 1)
        self.client.force_login(self.manager)
        self.client.get(self.url)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
