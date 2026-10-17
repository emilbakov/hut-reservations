"""Additional isolation tests. Place in bookings/test_manager_access.py."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Hut, Room


class HutManagerAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="hutmanager", password="test-only-pass", is_staff=True)
        self.other = User.objects.create_user(username="othermanager", password="test-only-pass", is_staff=True)
        self.admin = User.objects.create_superuser(username="hutadmin", email="admin@example.com", password="test-only-pass")
        self.hut_a = Hut.objects.create(name="Hut A", slug="hut-a")
        self.hut_b = Hut.objects.create(name="Hut B", slug="hut-b")
        self.hut_a.managers.add(self.manager)
        self.hut_b.managers.add(self.other)
        Room.objects.create(name="Dorm", hut=self.hut_a, capacity=3)
        Room.objects.create(name="Dorm", hut=self.hut_b, capacity=7)

    def test_manager_dashboard_defaults_to_own_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["capacity"], 3)
        self.assertEqual(response.context["selected_hut"], self.hut_a)

    def test_manager_cannot_select_other_hut(self):
        self.client.force_login(self.manager)
        for url in [reverse("bookings:dashboard"), reverse("bookings:dashboard_export")]:
            response = self.client.get(url, {"hut": self.hut_b.slug})
            self.assertEqual(response.status_code, 404)

    def test_manager_export_defaults_to_own_hut(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("bookings:dashboard_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_manager_cannot_access_hut_admin(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("admin:bookings_hut_changelist"))
        self.assertIn(response.status_code, [302, 403, 404])
        self.assertNotEqual(response.status_code, 200)

    def test_superuser_can_see_all_huts(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["capacity"], 10)
