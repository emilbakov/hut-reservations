"""Regression tests for SummitDesk New Booking access and hut isolation."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Hut, Reservation, Room
from floorplans.hut_staff import HutCleaner


@override_settings(BOOKING_MAX_DAYS_AHEAD=365, BOOKING_MAX_NIGHTS=30)
class BookingAccessV118Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username='v118-manager', password='pass', is_staff=False)
        self.staff_manager = User.objects.create_user(username='v118-staff', password='pass', is_staff=True)
        self.other = User.objects.create_user(username='v118-other', password='pass', is_staff=False)
        self.cleaner = User.objects.create_user(username='v118-cleaner', password='pass', is_staff=False)
        self.hut = Hut.objects.create(name='First hut', slug='v118-first')
        self.hut.managers.add(self.manager, self.staff_manager)
        self.other_hut = Hut.objects.create(name='Other hut', slug='v118-other')
        self.other_hut.managers.add(self.other)
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self.room = Room.objects.create(hut=self.hut, name='Room A', capacity=3, price_per_night=20)
        self.other_room = Room.objects.create(hut=self.other_hut, name='Room B', capacity=3, price_per_night=20)
        self.manual_url = reverse('bookings:manual_booking')
        self.property_url = reverse('floorplans:staff_new_booking', args=[self.hut.pk])
        start = timezone.localdate() + timedelta(days=2)
        self.booking_data = {
            'hut': str(self.hut.pk), 'check_in': start.isoformat(),
            'check_out': (start + timedelta(days=2)).isoformat(),
            'name': 'V118 guest', 'email': '', 'phone': '+359888123456',
            f'beds_{self.room.pk}': '2',
        }

    def test_staff_manager_slug_link_opens(self):
        self.client.force_login(self.staff_manager)
        response = self.client.get(self.manual_url, {'hut': self.hut.slug})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_hut'], self.hut)

    def test_numeric_hut_link_still_opens(self):
        self.client.force_login(self.staff_manager)
        response = self.client.get(self.manual_url, {'hut': str(self.hut.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_hut'], self.hut)

    def test_manager_without_django_staff_can_open(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.manual_url, {'hut': self.hut.slug})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_hut'], self.hut)

    def test_manager_without_staff_can_create(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.manual_url, self.booking_data)
        self.assertRedirects(response, reverse('floorplans:staff_hub', args=[self.hut.pk]), fetch_redirect_response=False)
        self.assertEqual(Reservation.objects.filter(name='V118 guest').count(), 1)

    def test_staff_manager_create_keeps_existing_redirect(self):
        self.client.force_login(self.staff_manager)
        response = self.client.post(self.manual_url, self.booking_data)
        self.assertRedirects(response, reverse('bookings:manager_reservations'), fetch_redirect_response=False)

    def test_other_hut_slug_is_forbidden(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.manual_url, {'hut': self.other_hut.slug}).status_code, 403)

    def test_other_hut_post_is_forbidden(self):
        self.client.force_login(self.manager)
        data = {**self.booking_data, 'hut': str(self.other_hut.pk), f'beds_{self.other_room.pk}': '1'}
        self.assertEqual(self.client.post(self.manual_url, data).status_code, 403)
        self.assertFalse(Reservation.objects.exists())

    def test_cleaner_cannot_open_booking(self):
        self.client.force_login(self.cleaner)
        self.assertEqual(self.client.get(self.manual_url, {'hut': self.hut.slug}).status_code, 403)

    def test_anonymous_redirects_to_staff_login(self):
        response = self.client.get(self.manual_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/staff/login/?next='))

    def test_nonstaff_manager_can_open_property_booking(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.property_url).status_code, 200)

    def test_nonstaff_manager_cannot_open_other_property_booking(self):
        self.client.force_login(self.manager)
        other_url = reverse('floorplans:staff_new_booking', args=[self.other_hut.pk])
        self.assertEqual(self.client.get(other_url).status_code, 404)

    def test_cleaner_cannot_open_property_booking(self):
        self.client.force_login(self.cleaner)
        self.assertEqual(self.client.get(self.property_url).status_code, 404)

    def test_nonstaff_manager_can_create_property_booking(self):
        self.client.force_login(self.manager)
        data = {
            'check_in': self.booking_data['check_in'],
            'check_out': self.booking_data['check_out'],
            'name': 'Property booking', 'email': 'guest@example.com',
            'phone': '', 'notes': '', f'room_{self.room.pk}': '1',
        }
        response = self.client.post(self.property_url, data)
        self.assertRedirects(response, reverse('floorplans:staff_hub', args=[self.hut.pk]), fetch_redirect_response=False)
        self.assertEqual(Reservation.objects.filter(name='Property booking').count(), 1)
