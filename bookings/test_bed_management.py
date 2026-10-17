from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Bed, BedAssignment, BedClosure, Hut, Reservation, ReservationItem, Room
from .services import free_beds


class BedManagementTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate() + timedelta(days=2)
        self.manager = get_user_model().objects.create_user(username='bedmanager', password='testpassword', is_staff=True)
        self.other = get_user_model().objects.create_user(username='otherbedmanager', password='testpassword', is_staff=True)
        self.hut = Hut.objects.create(name='Test hut', slug='bed-test-hut')
        self.hut.managers.add(self.manager)
        self.room = Room.objects.create(hut=self.hut, name='Dorm', capacity=3)
        self.res = Reservation.objects.create(name='Test guest', check_in=self.today, check_out=self.today + timedelta(days=2), status=Reservation.Status.CONFIRMED)
        self.item = ReservationItem.objects.create(reservation=self.res, room=self.room, beds=2)
        self.url = reverse('bookings:bed_management', args=[self.room.pk]) + '?day=' + self.today.isoformat()
        self.client.force_login(self.manager)

    def test_get_creates_beds(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Bed.objects.filter(room=self.room).count(), 3)

    def test_other_manager_cannot_view(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_assign_and_prevent_duplicate(self):
        self.client.get(self.url)
        bed = Bed.objects.get(room=self.room, number=1)
        payload = {'action': 'assign', 'bed_id': bed.pk, 'item_id': self.item.pk}
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(BedAssignment.objects.count(), 1)
        self.client.post(self.url, payload)
        self.assertEqual(BedAssignment.objects.count(), 1)

    def test_maintenance_reduces_booking_availability(self):
        self.client.get(self.url)
        bed = Bed.objects.get(room=self.room, number=3)
        payload = {'action': 'close', 'bed_id': bed.pk, 'start': self.today.isoformat(), 'end': (self.today + timedelta(days=2)).isoformat(), 'reason': 'Broken'}
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(BedClosure.objects.count(), 1)
        self.assertEqual(free_beds([self.room], self.today, self.today + timedelta(days=2))[self.room.pk], 0)

    def test_maintenance_cannot_remove_reserved_capacity(self):
        self.client.get(self.url)
        for number in (1, 2):
            bed = Bed.objects.get(room=self.room, number=number)
            self.client.post(self.url, {'action': 'close', 'bed_id': bed.pk, 'start': self.today.isoformat(), 'end': (self.today + timedelta(days=2)).isoformat()})
        self.assertEqual(BedClosure.objects.count(), 1)

    def test_assignment_cannot_exceed_quantity(self):
        self.client.get(self.url)
        for bed in Bed.objects.filter(room=self.room):
            self.client.post(self.url, {'action': 'assign', 'bed_id': bed.pk, 'item_id': self.item.pk})
        self.assertEqual(BedAssignment.objects.count(), 2)
