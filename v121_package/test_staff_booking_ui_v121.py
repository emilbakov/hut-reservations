"""Run on the real Django server with the project's configured test database."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room


@override_settings(BOOKING_MAX_DAYS_AHEAD=365, BOOKING_MAX_NIGHTS=30)
class StaffBookingAvailabilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username='v121manager', password='secret', is_staff=False)
        self.other = User.objects.create_user(username='v121other', password='secret', is_staff=False)
        self.cleaner = User.objects.create_user(username='v121cleaner', password='secret', is_staff=False)
        self.hut = Hut.objects.create(name='Summit hut', slug='v121-summit')
        self.hut.managers.add(self.manager)
        self.other_hut = Hut.objects.create(name='Other hut', slug='v121-other')
        self.other_hut.managers.add(self.other)
        self.room1 = Room.objects.create(hut=self.hut, name='Dorm', capacity=4, price_per_night=25)
        self.room2 = Room.objects.create(hut=self.hut, name='Loft', capacity=2, price_per_night=30)
        self.other_room = Room.objects.create(hut=self.other_hut, name='Private', capacity=1)
        self.start = timezone.localdate() + timedelta(days=3)
        self.end = self.start + timedelta(days=2)
        self.dates = {'check_in': self.start.isoformat(), 'check_out': self.end.isoformat()}
        self.manual_url = reverse('bookings:manual_booking')
        self.property_url = reverse('floorplans:staff_new_booking', args=[self.hut.pk])

    def test_both_urls_use_one_template_and_same_availability(self):
        self.client.force_login(self.manager)
        for url, params in (
            (self.manual_url, {'hut': str(self.hut.pk), **self.dates}),
            (self.property_url, self.dates),
        ):
            with self.subTest(url=url):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'bookings/staff_booking_v121.html')
                self.assertEqual(response.context['availability']['free'], 6)
                self.assertEqual(response.context['availability']['rooms_with_space'], 2)
                self.assertContains(response, 'Beds available')
                self.assertContains(response, 'Dorm')
                self.assertContains(response, 'Loft')

    def test_occupied_and_closed_beds_reduce_available_capacity(self):
        reservation = Reservation.objects.create(name='Existing', check_in=self.start,
                                                  check_out=self.end, status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=reservation, room=self.room1,
                                       beds=2, price_per_night=25)
        bed = Bed.objects.create(room=self.room2, number=1)
        BedClosure.objects.create(bed=bed, start=self.start, end=self.end, reason='Repair')
        self.client.force_login(self.manager)
        for url, params in (
            (self.manual_url, {'hut': str(self.hut.pk), **self.dates}),
            (self.property_url, self.dates),
        ):
            with self.subTest(url=url):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['availability']['free'], 3)
                self.assertEqual(response.context['availability']['unavailable'], 3)
                self.assertEqual([r['free'] for r in response.context['room_rows']], [2, 1])

    def test_manager_without_staff_flag_can_create_manual_reservation(self):
        self.client.force_login(self.manager)
        data = {'hut': str(self.hut.pk), **self.dates, 'name': 'Walk in',
                'email': '', 'phone': '123456', f'beds_{self.room1.pk}': '2'}
        response = self.client.post(self.manual_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservation.objects.get(name='Walk in').items.get().beds, 2)

    def test_manager_without_staff_flag_can_create_property_reservation(self):
        self.client.force_login(self.manager)
        data = {**self.dates, 'name': 'Front desk', 'email': 'guest@example.com',
                'phone': '', f'room_{self.room1.pk}': '1'}
        response = self.client.post(self.property_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reservation.objects.get(name='Front desk').items.get().beds, 1)

    def test_missing_contact_keeps_availability_visible(self):
        self.client.force_login(self.manager)
        data = {'hut': str(self.hut.pk), **self.dates, 'name': 'No contact',
                'email': '', 'phone': '', f'beds_{self.room1.pk}': '1'}
        response = self.client.post(self.manual_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['availability']['free'], 6)
        self.assertContains(response, 'Enter at least a phone number or email address')
        self.assertFalse(Reservation.objects.filter(name='No contact').exists())

    def test_authorization_remains_hut_scoped(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.manual_url, {'hut': str(self.other_hut.pk), **self.dates}).status_code, 403)
        self.assertEqual(self.client.get(reverse('floorplans:staff_new_booking', args=[self.other_hut.pk])).status_code, 404)
        self.client.force_login(self.cleaner)
        self.assertEqual(self.client.get(self.manual_url).status_code, 403)
        self.assertEqual(self.client.get(self.property_url).status_code, 404)

    def test_default_dates_show_availability(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.manual_url, {'hut': str(self.hut.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['availability']['ready'])
        self.assertEqual(response.context['availability']['nights'], 1)
