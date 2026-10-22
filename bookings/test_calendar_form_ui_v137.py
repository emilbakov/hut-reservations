"""SummitDesk v137: UI regression coverage for calendar create/edit pages."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Hut, Room, Reservation


class CalendarFormUIV137Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user('v137_manager', password='pw', is_staff=True)
        cls.other = User.objects.create_user('v137_other', password='pw', is_staff=True)
        cls.hut = Hut.objects.create(name='V137 Alpine Hut', slug='v137-alpine')
        cls.private = Hut.objects.create(name='V137 Private Hut', slug='v137-private')
        cls.hut.managers.add(cls.manager)
        cls.private.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name='North Room', capacity=4, price_per_night=20)
        cls.private_room = Room.objects.create(hut=cls.private, name='Hidden Room', capacity=2)
        cls.start = timezone.localdate() + timedelta(days=12)
        cls.end = cls.start + timedelta(days=2)

    def create_url(self):
        return reverse('bookings:calendar_create')

    def payload(self):
        return {
            'check_in': self.start.isoformat(), 'check_out': self.end.isoformat(),
            'room': self.room.pk, 'beds': 2,
            'name': 'Alpine Guest', 'email': 'guest@example.com', 'phone': '', 'notes': '',
        }

    def test_prefill_from_calendar_and_layout(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.create_url(), {
            'check_in': self.start.isoformat(), 'room': self.room.pk, 'hut': self.hut.slug,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SummitDesk v137')
        self.assertContains(response, 'Create a reservation')
        self.assertContains(response, 'Booking overview')
        self.assertContains(response, f'value="{self.start.isoformat()}"')
        self.assertContains(response, 'North Room')
        self.assertContains(response, reverse('bookings:availability_calendar'))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, 'Hidden Room')

    def test_submit_still_uses_existing_booking_logic(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.create_url(), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_invalid_dates_show_errors_without_creating_booking(self):
        self.client.force_login(self.manager)
        payload = self.payload()
        payload['check_out'] = payload['check_in']
        response = self.client.post(self.create_url(), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Departure must be after arrival')
        self.assertFalse(Reservation.objects.exists())

    def test_private_room_not_bookable(self):
        self.client.force_login(self.manager)
        payload = self.payload()
        payload['room'] = self.private_room.pk
        response = self.client.post(self.create_url(), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Reservation.objects.exists())

    def test_edit_guest_details_are_read_only_and_unchanged(self):
        self.client.force_login(self.manager)
        self.client.post(self.create_url(), self.payload())
        reservation = Reservation.objects.get()
        url = reverse('bookings:calendar_edit', args=[reservation.code])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Guest details are read-only')
        self.assertContains(response, 'Alpine Guest')
        self.assertContains(response, 'Save dates and beds')
        payload = self.payload()
        payload['name'] = 'Changed Name'
        payload['email'] = 'changed@example.com'
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.name, 'Alpine Guest')
        self.assertEqual(reservation.email, 'guest@example.com')

    def test_nonstaff_redirect_and_manager_scope(self):
        self.assertEqual(self.client.get(self.create_url()).status_code, 302)
        self.client.force_login(self.other)
        response = self.client.get(self.create_url())
        self.assertNotContains(response, 'North Room')
