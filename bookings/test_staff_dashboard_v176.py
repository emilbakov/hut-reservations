"""Staff locale return targets, standalone assets and preserved hut permissions."""
from datetime import timedelta
from html import escape

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from floorplans.hut_staff import HutCleaner
from .models import Hut, Reservation, ReservationItem, Room


class StaffDashboardV176Tests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user('staff176-manager', is_staff=True)
        self.cleaner = get_user_model().objects.create_user('staff176-cleaner')
        self.hut = Hut.objects.create(name='Studenets Staff Test', slug='studenets-staff176')
        self.hut.managers.add(self.manager)
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self.room = Room.objects.create(hut=self.hut, name='Dorm', capacity=6, price_per_night='18.00')
        self.client.force_login(self.manager)

    def test_standalone_hub_language_form_returns_to_same_hut_and_query(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.manager)
        target = reverse('floorplans:staff_hub', args=[self.hut.pk]) + '?range=7&source=overview'
        page = browser.get(target)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'value="' + escape(target, quote=True) + '"')
        self.assertContains(page, 'bookings/staff-v176/controls.css')
        response = browser.post(reverse('set_language'), {
            'language': 'bg', 'next': target,
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, target)
        translated = browser.get(response.url)
        self.assertContains(translated, '<html lang="bg">')
        self.assertContains(translated, 'ПРЕГЛЕД НА ХИЖАТА')
        self.assertContains(translated, 'Следващите 7 нощувки')
        self.assertContains(translated, 'value="bg" lang="bg" aria-label="Български" aria-pressed="true"')
        self.assertEqual(int(browser.session['_auth_user_id']), self.manager.pk)

    def test_dashboard_language_form_preserves_month_and_hut(self):
        target = reverse('bookings:dashboard') + '?hut=' + self.hut.slug + '&year=2026&month=11'
        page = self.client.get(target)
        self.assertContains(page, 'value="' + escape(target, quote=True) + '"')
        self.assertContains(page, 'bookings/staff-v176/dashboard.css')
        self.assertContains(page, 'bookings/staff-v176/controls.css')
        self.assertContains(page, 'year=2026&amp;month=10&amp;hut=' + self.hut.slug)
        self.assertContains(page, 'year=2026&amp;month=12&amp;hut=' + self.hut.slug)

    def test_other_standalone_staff_pages_load_language_controls(self):
        for name in ['staff_tasks', 'staff_calendar']:
            with self.subTest(route=name):
                target = reverse('floorplans:' + name, args=[self.hut.pk])
                page = self.client.get(target)
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, 'bookings/staff-v176/controls.css')
                self.assertContains(page, 'value="' + target + '"')

    def test_cleaner_gets_styled_language_control_without_manager_actions(self):
        self.client.force_login(self.cleaner)
        page = self.client.get(reverse('floorplans:staff_hub', args=[self.hut.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'bookings/staff-v176/controls.css')
        self.assertContains(page, 'My cleaning tasks')
        self.assertNotContains(page, 'New reservation')
        self.assertNotContains(page, 'Estimated booking value tonight')
        self.assertNotEqual(self.client.get(reverse('bookings:dashboard')).status_code, 200)

    def test_dashboard_keeps_hut_scope_and_existing_decision_form_contract(self):
        start = timezone.localdate() + timedelta(days=4)
        pending = Reservation.objects.create(name='Visible Request', check_in=start,
            check_out=start + timedelta(days=2), status='pending', guest_request=True)
        ReservationItem.objects.create(reservation=pending, room=self.room, beds=2, price_per_night='18.00')
        other = Hut.objects.create(name='Private Staff Hut', slug='private-staff176')
        other_room = Room.objects.create(hut=other, name='Private dorm', capacity=3)
        hidden = Reservation.objects.create(name='Foreign Private Guest', check_in=start,
            check_out=start + timedelta(days=2), status='pending', guest_request=True)
        ReservationItem.objects.create(reservation=hidden, room=other_room, beds=1, price_per_night='18.00')
        page = self.client.get(reverse('bookings:dashboard'))
        self.assertEqual(page.context['pending_count'], 1)
        self.assertContains(page, 'Visible Request')
        self.assertNotContains(page, 'Foreign Private Guest')
        self.assertContains(page, reverse('bookings:manager_reservation_action', args=[pending.code]))
        self.assertContains(page, 'name="source" value="dashboard"')
        self.assertContains(page, 'name="return_hut" value="' + self.hut.slug + '"')
        self.assertContains(page, 'Capacity check')

    def test_dashboard_empty_state_and_bulgarian_copy(self):
        self.client.cookies['django_language'] = 'bg'
        page = self.client.get(reverse('bookings:dashboard'))
        self.assertContains(page, 'Няма заявки, очакващи Вашето решение.')
        self.assertContains(page, 'Нуждаят се от решение')
        self.assertContains(page, 'ДНЕВЕН ПРЕГЛЕД')
        self.assertEqual(page.context['pending_count'], 0)
        self.assertEqual(page.context['capacity'], 6)

    def test_language_switch_still_requires_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.manager)
        target = reverse('floorplans:staff_hub', args=[self.hut.pk])
        browser.get(target)
        self.assertEqual(browser.post(reverse('set_language'), {'language': 'bg', 'next': target}).status_code, 403)
