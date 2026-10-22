"""v140 quick stay: name-only, room scope, stay conflicts and maintenance."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room


class SecureClient(Client):
    def get(self, *args, **kwargs):
        kwargs.setdefault('secure', True)
        kwargs.setdefault('HTTP_HOST', '127.0.0.1')
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        kwargs.setdefault('secure', True)
        kwargs.setdefault('HTTP_HOST', '127.0.0.1')
        return super().post(*args, **kwargs)


class QuickStayV140Tests(TestCase):
    def setUp(self):
        self.client = SecureClient()

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user('v140manager', password='pw', is_staff=True)
        cls.other = User.objects.create_user('v140other', password='pw', is_staff=True)
        cls.hut = Hut.objects.create(name='Test Lodge', slug='v140-lodge')
        cls.hut.managers.add(cls.manager)
        cls.other_hut = Hut.objects.create(name='Private Lodge', slug='v140-private')
        cls.other_hut.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name='Pine Room', capacity=3, price_per_night=40)
        cls.private = Room.objects.create(hut=cls.other_hut, name='Secret Room', capacity=4)
        cls.inactive = Room.objects.create(hut=cls.hut, name='Inactive', capacity=4, is_active=False)

    def url(self, hut=None):
        return reverse('floorplans:quickstay_create', args=[(hut or self.hut).pk])

    def payload(self, room=None, beds=1, **extra):
        start = timezone.localdate() + timedelta(days=3)
        data = dict(room=(room or self.room).pk, check_in=start.isoformat(),
                    check_out=(start+timedelta(days=2)).isoformat(), beds=beds, name='Guest Only')
        data.update(extra)
        return data

    def test_name_only_booking_is_confirmed(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.url(), self.payload())
        self.assertEqual(response.status_code, 302)
        r = Reservation.objects.get(name='Guest Only')
        self.assertEqual(r.status, Reservation.Status.CONFIRMED)
        self.assertEqual(r.email, '')
        self.assertEqual(r.items.get().room, self.room)

    def test_conflict_does_not_create(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url(), self.payload(beds=3)).status_code, 302)
        self.assertEqual(self.client.post(self.url(), self.payload(beds=1)).status_code, 400)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_other_hut_room_is_rejected(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url(), self.payload(room=self.private)).status_code, 404)
        self.assertFalse(Reservation.objects.exists())

    def test_other_hut_calendar_forbidden(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url(self.other_hut), self.payload()).status_code, 404)

    def test_inactive_room_rejected(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url(), self.payload(room=self.inactive)).status_code, 404)

    def test_requires_login_and_post(self):
        self.assertEqual(self.client.post(self.url(), self.payload()).status_code, 302)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_invalid_dates_and_empty_name(self):
        self.client.force_login(self.manager)
        today = timezone.localdate()
        self.assertEqual(self.client.post(self.url(), self.payload(check_in=today.isoformat(), check_out=today.isoformat())).status_code, 400)
        self.assertEqual(self.client.post(self.url(), self.payload(name='')).status_code, 400)
        self.assertFalse(Reservation.objects.exists())

    def test_maintenance_closure_blocks_capacity(self):
        self.client.force_login(self.manager)
        start = timezone.localdate() + timedelta(days=3)
        bed = Bed.objects.create(room=self.room, number=1)
        BedClosure.objects.create(bed=bed, start=start, end=start+timedelta(days=2))
        self.assertEqual(self.client.post(self.url(), self.payload(beds=3)).status_code, 400)
        self.assertFalse(Reservation.objects.exists())

    def test_calendar_has_inline_form(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('floorplans:staff_calendar', args=[self.hut.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plan a stay')
        self.assertContains(response, self.url())
        self.assertContains(response, 'Detailed timeline')

    def test_month_grid_includes_next_fourteen_days(self):
        from calendar import monthrange
        self.client.force_login(self.manager)
        response = self.client.get(reverse('floorplans:staff_calendar', args=[self.hut.pk]))
        first = timezone.localdate().replace(day=1)
        self.assertEqual(len(response.context['days']), monthrange(first.year, first.month)[1] + 14)
        self.assertEqual(len(response.context['rows'][0]['days']), len(response.context['days']))
