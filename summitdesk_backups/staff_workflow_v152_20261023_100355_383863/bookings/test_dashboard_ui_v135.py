"""SummitDesk v135: focused dashboard UI and permission regression tests."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Hut, Reservation, ReservationItem, Room


class DashboardTemplateV135Tests(SimpleTestCase):
    def test_dashboard_template_preserves_existing_mobile_regression_marker(self):
        from django.conf import settings
        from pathlib import Path
        source = (Path(settings.BASE_DIR) / "bookings/templates/bookings/dashboard.html").read_text()
        self.assertIn("SummitDesk v135", source)
        self.assertIn("/* v133:", source)
        self.assertIn('data-label="Check-in"', source)
        self.assertIn('aria-label="Today\'s operations"', source)


class DashboardPageV135Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(username="v135-manager", password="test-password", is_staff=True)
        cls.other = User.objects.create_user(username="v135-other", password="test-password", is_staff=True)
        cls.hut = Hut.objects.create(name="Summit Test Hut", slug="summit-test-hut")
        cls.other_hut = Hut.objects.create(name="Hidden Test Hut", slug="hidden-test-hut")
        cls.hut.managers.add(cls.manager)
        cls.other_hut.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name="Main Dorm", capacity=8, price_per_night="30.00")
        other_room = Room.objects.create(hut=cls.other_hut, name="Private Dorm", capacity=5, price_per_night="30.00")
        start = timezone.localdate() + timedelta(days=2)
        cls.booking = Reservation.objects.create(name="Visible Guest V135", email="visible@example.test", check_in=start, check_out=start + timedelta(days=1), status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=cls.booking, room=cls.room, beds=2, price_per_night="30.00")
        hidden = Reservation.objects.create(name="Hidden Guest V135", email="hidden@example.test", check_in=start, check_out=start + timedelta(days=1), status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=hidden, room=other_room, beds=3, price_per_night="30.00")

    def setUp(self):
        self.client.force_login(self.manager)

    def test_manager_dashboard_renders_new_layout_and_real_data(self):
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your hut, at a glance.")
        self.assertContains(response, "Visible Guest V135")
        self.assertContains(response, "New reservation")
        self.assertContains(response, "Monthly occupancy")
        self.assertContains(response, 'data-label="Check-in"')
        self.assertContains(response, reverse("bookings:conversation_inbox"))
        self.assertEqual(response.context["capacity"], 8)
        self.assertNotContains(response, "Hidden Guest V135")
        self.assertNotContains(response, "Hidden Test Hut")

    def test_manager_cannot_switch_to_unassigned_hut(self):
        response = self.client.get(reverse("bookings:dashboard"), {"hut": self.other_hut.slug})
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_view_staff_dashboard(self):
        self.client.logout()
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertNotEqual(response.status_code, 200)

    def test_mobile_layout_css_present(self):
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertContains(response, "@media(max-width:600px)")
        self.assertContains(response, "sd135-table")
