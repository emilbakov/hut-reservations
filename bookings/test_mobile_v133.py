"""Targeted v133 mobile UI and reservation-workflow smoke tests."""
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room


class MobileAssetsV133Tests(SimpleTestCase):
    def test_mobile_drawer_has_keyboard_and_inert_support(self):
        js = (Path(settings.BASE_DIR) / 'floorplans/static/floorplans/summitdesk_shell_v116.js').read_text()
        css = (Path(settings.BASE_DIR) / 'floorplans/static/floorplans/summitdesk_shell_v116.css').read_text()
        self.assertIn('sidebar.inert', js)
        self.assertIn("event.key !== 'Tab'", js)
        self.assertIn("event.key === 'Escape'", js)
        self.assertIn('/* v133:', css)

    def test_reservation_cards_keep_table_headers_and_actions(self):
        html = (Path(settings.BASE_DIR) / 'bookings/templates/bookings/manager_reservations.html').read_text()
        for label in ('Guest', 'Hut', 'Stay dates', 'Beds', 'Status', 'Actions'):
            self.assertIn(f'data-label="{label}"', html)
        self.assertIn('<thead>', html)
        self.assertIn('csrf_token', html)
        self.assertIn('/* v133:', html)


class MobilePagesV133Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username='v133-manager', password='test-pass', is_staff=True
        )
        cls.manager = user
        cls.hut = Hut.objects.create(name='Mobile Hut', slug='mobile-hut')
        cls.hut.managers.add(user)
        room = Room.objects.create(hut=cls.hut, name='Room A', capacity=4, price_per_night='25.00')
        start = timezone.localdate() + timedelta(days=5)
        cls.reservation = Reservation.objects.create(
            name='Mobile Guest', email='mobile@example.com',
            check_in=start, check_out=start + timedelta(days=2),
            status=Reservation.Status.PENDING, guest_request=True,
        )
        ReservationItem.objects.create(
            reservation=cls.reservation, room=room, beds=2, price_per_night='25.00'
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def test_reservations_have_mobile_labels_and_unchanged_post_actions(self):
        response = self.client.get(reverse('bookings:manager_reservations'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mobile Guest')
        self.assertContains(response, 'data-label="Stay dates"')
        self.assertContains(response, 'data-label="Actions"')
        self.assertContains(response, 'name="action" value="confirm"')
        self.assertContains(response, 'name="action" value="cancel"')

    def test_approval_dashboard_still_shows_review_actions(self):
        response = self.client.get(reverse('bookings:approval_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mobile Guest')
        self.assertContains(response, 'Approve')
        self.assertContains(response, 'Decline')
        self.assertContains(response, '/* v133:')
        self.assertContains(response, 'id="sd116-sidebar"')

    def test_overview_has_compact_mobile_layout(self):
        response = self.client.get(reverse('bookings:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/* v133:')
        self.assertContains(response, 'New reservation')

    def test_calendar_shows_swipe_hint_and_keeps_timeline(self):
        response = self.client.get(reverse('bookings:calendar_timeline'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Swipe sideways to view the full week')
        self.assertContains(response, 'sd-board')
        self.assertContains(response, '/* v133:')

    def test_reminder_settings_use_staff_navigation(self):
        response = self.client.get(reverse('bookings:manager_digest_preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="sd116-sidebar"')

    def test_unassigned_staff_cannot_view_reservations(self):
        other = get_user_model().objects.create_user(
            username='v133-outsider', password='test-pass', is_staff=True
        )
        self.client.force_login(other)
        response = self.client.get(reverse('bookings:manager_reservations'))
        self.assertEqual(response.status_code, 403)
