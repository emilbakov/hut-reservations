from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import GuestStay, Hut, Reservation, ReservationItem, Room


class StayHistoryAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username='history_manager', password='test', is_staff=True)
        self.other = User.objects.create_user(username='other_manager', password='test', is_staff=True)
        self.hut = Hut.objects.create(name='History Hut A', slug='history-hut-a')
        self.other_hut = Hut.objects.create(name='History Hut B', slug='history-hut-b')
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other)
        self.room = Room.objects.create(hut=self.hut, name='Dorm A', capacity=5)
        other_room = Room.objects.create(hut=self.other_hut, name='Dorm B', capacity=5)
        today = timezone.localdate()
        self.booking = Reservation.objects.create(name='Allowed Guest', email='allowed@example.com',
            check_in=today - timedelta(days=1), check_out=today + timedelta(days=1))
        ReservationItem.objects.create(reservation=self.booking, room=self.room, beds=2)
        self.hidden = Reservation.objects.create(name='Hidden Guest', email='hidden@example.com',
            check_in=today - timedelta(days=1), check_out=today + timedelta(days=1))
        ReservationItem.objects.create(reservation=self.hidden, room=other_room, beds=1)
        GuestStay.objects.create(reservation=self.booking, checked_in_at=timezone.now(), checked_in_by=self.manager)
        GuestStay.objects.create(reservation=self.hidden, checked_in_at=timezone.now(), checked_in_by=self.other)

    def test_manager_sees_only_assigned_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('bookings:stay_history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Allowed Guest')
        self.assertNotContains(response, 'Hidden Guest')

    def test_manager_csv_is_scoped(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('bookings:stay_history_export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Allowed Guest', response.content)
        self.assertNotIn(b'Hidden Guest', response.content)

    def test_manager_cannot_select_other_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('bookings:stay_history'), {'hut': self.other_hut.slug})
        self.assertEqual(response.status_code, 404)

    def test_unassigned_staff_forbidden(self):
        User = get_user_model()
        user = User.objects.create_user(username='unassigned_history', password='test', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('bookings:stay_history')).status_code, 403)

    def test_superuser_can_see_all(self):
        User = get_user_model()
        user = User.objects.create_superuser(username='history_admin', password='test', email='admin@example.com')
        self.client.force_login(user)
        response = self.client.get(reverse('bookings:stay_history'))
        self.assertContains(response, 'Allowed Guest')
        self.assertContains(response, 'Hidden Guest')
