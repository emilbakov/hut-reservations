"""Run with python manage.py test bookings.test_room_calendar"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room


class RoomCalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(username='calendar_manager', password='test', is_staff=True)
        cls.other = User.objects.create_user(username='calendar_other', password='test', is_staff=True)
        cls.hut = Hut.objects.create(name='Calendar hut', slug='calendar-hut')
        cls.other_hut = Hut.objects.create(name='Other hut', slug='other-calendar-hut')
        cls.hut.managers.add(cls.manager)
        cls.other_hut.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=4)
        cls.other_room = Room.objects.create(hut=cls.other_hut, name='Other dorm', capacity=3)
        cls.day = timezone.localdate() + timedelta(days=2)
        cls.reservation = Reservation.objects.create(
            name='Visible Guest', email='guest@example.com',
            check_in=cls.day, check_out=cls.day + timedelta(days=2),
            status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(reservation=cls.reservation, room=cls.room, beds=2)

    def url(self, **kwargs):
        return reverse('bookings:room_calendar')

    def test_anonymous_is_redirected(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_manager_sees_own_hut_and_correct_beds(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'hut': self.hut.slug, 'year': self.day.year, 'month': self.day.month})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible Guest')
        self.assertContains(response, 'Dorm')
        self.assertEqual(response.context['rows'][0]['cells'][self.day.day - 1]['free'], 2)

    def test_manager_cannot_select_other_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'hut': self.other_hut.slug})
        self.assertEqual(response.status_code, 404)

    def test_unassigned_staff_denied(self):
        User = get_user_model()
        staff = User.objects.create_user(username='calendar_unassigned', password='test', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_cancelled_reservations_do_not_use_beds(self):
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=['status'])
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.day.year, 'month': self.day.month})
        self.assertEqual(response.context['rows'][0]['cells'][self.day.day - 1]['free'], 4)

    def test_invalid_month_returns_400(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url(), {'year': '2026', 'month': '13'}).status_code, 400)

    def test_mixed_hut_reservation_uses_capacity_without_exposing_guest(self):
        mixed = Reservation.objects.create(name='Hidden Mixed Guest', email='mixed@example.com',
            check_in=self.day, check_out=self.day + timedelta(days=1), status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=mixed, room=self.room, beds=1)
        ReservationItem.objects.create(reservation=mixed, room=self.other_room, beds=1)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.day.year, 'month': self.day.month})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['rows'][0]['cells'][self.day.day - 1]['free'], 1)
        self.assertNotContains(response, 'Hidden Mixed Guest')
