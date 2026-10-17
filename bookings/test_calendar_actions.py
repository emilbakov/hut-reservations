from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Hut, Room, Reservation, ReservationItem

class CalendarActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('action_manager', password='pw', is_staff=True)
        self.other = User.objects.create_user('action_other', password='pw', is_staff=True)
        self.hut = Hut.objects.create(name='Action Hut', slug='action-hut')
        self.private = Hut.objects.create(name='Other Hut', slug='action-other')
        self.hut.managers.add(self.manager)
        self.private.managers.add(self.other)
        self.room = Room.objects.create(hut=self.hut, name='Bunks', capacity=2, price_per_night=20)
        self.other_room = Room.objects.create(hut=self.private, name='Other', capacity=2)
        self.start = timezone.localdate() + timedelta(days=10)
        self.end = self.start + timedelta(days=2)
        self.create_url = reverse('bookings:calendar_create')

    def data(self, room=None, beds=1):
        return {'check_in': self.start.isoformat(), 'check_out': self.end.isoformat(),
                'room': room or self.room.pk, 'beds': beds,
                'name': 'Calendar Guest', 'email': 'calendar@example.com'}

    def test_anonymous_redirect(self):
        self.assertEqual(self.client.get(self.create_url).status_code, 302)

    def test_staff_can_create(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.create_url, self.data()).status_code, 302)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_other_hut_room_rejected(self):
        self.client.force_login(self.manager)
        self.client.post(self.create_url, self.data(self.other_room.pk))
        self.assertEqual(Reservation.objects.count(), 0)

    def test_overbooking_rejected(self):
        self.client.force_login(self.manager)
        self.client.post(self.create_url, self.data(beds=2))
        response = self.client.post(self.create_url, self.data(beds=1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_edit_dates_uses_existing_service(self):
        self.client.force_login(self.manager)
        self.client.post(self.create_url, self.data())
        reservation = Reservation.objects.get()
        url = reverse('bookings:calendar_edit', args=[reservation.code])
        data = self.data()
        data['check_out'] = (self.end + timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post(url, data).status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.check_out, self.end + timedelta(days=1))

    def test_other_manager_cannot_edit(self):
        self.client.force_login(self.manager)
        self.client.post(self.create_url, self.data())
        reservation = Reservation.objects.get()
        self.client.force_login(self.other)
        url = reverse('bookings:calendar_edit', args=[reservation.code])
        self.assertEqual(self.client.post(url, self.data()).status_code, 404)

    def test_edit_does_not_change_guest_identity(self):
        self.client.force_login(self.manager)
        self.client.post(self.create_url, self.data())
        reservation = Reservation.objects.get()
        url = reverse('bookings:calendar_edit', args=[reservation.code])
        payload = self.data()
        payload['name'] = 'Intruder'
        self.client.post(url, payload)
        reservation.refresh_from_db()
        self.assertEqual(reservation.name, 'Calendar Guest')

    def test_invalid_dates_do_not_create(self):
        self.client.force_login(self.manager)
        data = self.data()
        data['check_out'] = self.start.isoformat()
        self.assertEqual(self.client.post(self.create_url, data).status_code, 200)
        self.assertFalse(Reservation.objects.exists())
