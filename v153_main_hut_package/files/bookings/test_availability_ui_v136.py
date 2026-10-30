"""SummitDesk v136 — focused regression tests for the monthly availability UI."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Hut, Room, Reservation, ReservationItem


class AvailabilityUIV136Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user('v136_manager', password='pw', is_staff=True)
        cls.other = User.objects.create_user('v136_other', password='pw', is_staff=True)
        cls.hut = Hut.objects.create(name='Summit Hut', slug='summit-v136')
        cls.other_hut = Hut.objects.create(name='Other Private Hut', slug='private-v136')
        cls.hut.managers.add(cls.manager)
        cls.other_hut.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name='Alpine Room', capacity=4)
        cls.other_room = Room.objects.create(hut=cls.other_hut, name='Secret Room', capacity=2)
        cls.first = timezone.localdate().replace(day=1)

    def url(self, **kwargs):
        return reverse('bookings:availability_calendar')

    def test_calendar_renders_new_ui_and_existing_links(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.first.year, 'month': self.first.month})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SummitDesk v136')
        self.assertContains(response, 'Bed availability')
        self.assertContains(response, 'Weekly timeline')
        self.assertContains(response, 'Apply filters')
        self.assertContains(response, 'Over-capacity nights')
        self.assertContains(response, 'Alpine Room')
        self.assertContains(response, 'name="month"')
        self.assertContains(response, 'name="year"')
        self.assertContains(response, 'name="hut"')
        self.assertContains(response, reverse('bookings:calendar_create'))
        self.assertContains(response, reverse('bookings:calendar_timeline'))

    def test_manager_scope_is_preserved(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url())
        self.assertNotContains(response, 'Other Private Hut')
        self.assertNotContains(response, 'Secret Room')
        self.assertEqual(self.client.get(self.url(), {'hut': self.other_hut.slug}).status_code, 404)
        self.assertEqual(self.client.get(self.url(), {'room': self.other_room.pk}).status_code, 404)

    def test_booking_details_and_availability_are_visible(self):
        reservation = Reservation.objects.create(
            name='Alpine Guest', email='alpine@example.com',
            check_in=self.first, check_out=self.first + timedelta(days=1),
            status=Reservation.Status.CONFIRMED,
        )
        ReservationItem.objects.create(reservation=reservation, room=self.room, beds=2)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.first.year, 'month': self.first.month})
        self.assertContains(response, '2 booked')
        self.assertContains(response, reservation.code)
        self.assertContains(response, reverse('bookings:calendar_edit', args=[reservation.code]))
        self.assertContains(response, 'Alpine Guest')
        self.assertContains(response, '2</strong><span class="sd136-free">free', html=False)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)

    def test_previous_next_and_today_keep_hut_selection(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'hut': self.hut.slug, 'year': 2026, 'month': 10})
        self.assertContains(response, 'year=2026&amp;month=9&amp;hut=summit-v136', html=False)
        self.assertContains(response, 'year=2026&amp;month=11&amp;hut=summit-v136', html=False)
        self.assertContains(response, '?hut=summit-v136', html=False)

    def test_anonymous_still_redirected(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_guest_name_escaped(self):
        reservation = Reservation.objects.create(
            name='<script>alert(1)</script>', email='x@example.com',
            check_in=self.first, check_out=self.first + timedelta(days=1),
            status=Reservation.Status.PENDING,
        )
        ReservationItem.objects.create(reservation=reservation, room=self.room, beds=1)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.first.year, 'month': self.first.month})
        self.assertNotContains(response, '<script>alert(1)</script>', html=False)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;', html=False)
