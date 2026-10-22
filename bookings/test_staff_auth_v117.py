"""Focused tests for the SummitDesk staff sign-in release."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from bookings.models import Hut
from floorplans.hut_staff import HutCleaner


@override_settings(SECURE_SSL_REDIRECT=False)
class StaffAuthTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username='sd_manager', password='Test-pass-123!', is_staff=True)
        self.cleaner = User.objects.create_user(username='sd_cleaner', password='Test-pass-123!', is_staff=False)
        self.outsider = User.objects.create_user(username='sd_outsider', password='Test-pass-123!')
        self.hut = Hut.objects.create(name='Test Hut', slug='test-hut', is_active=True)
        self.hut.managers.add(self.manager)
        HutCleaner.objects.create(user=self.cleaner, hut=self.hut)

    def test_login_page(self):
        response = self.client.get(reverse('bookings:staff_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome back')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_manager_goes_to_dashboard(self):
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_manager', 'password': 'Test-pass-123!',
        })
        self.assertRedirects(response, reverse('bookings:dashboard'), fetch_redirect_response=False)
        self.assertEqual(str(self.client.session['_auth_user_id']), str(self.manager.pk))

    def test_cleaner_goes_to_hut_workspace(self):
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_cleaner', 'password': 'Test-pass-123!',
        })
        self.assertRedirects(response, reverse('floorplans:staff_home'), fetch_redirect_response=False)

    def test_unassigned_user_is_denied(self):
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_outsider', 'password': 'Test-pass-123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_hut_membership_denied(self):
        self.hut.is_active = False
        self.hut.save(update_fields=['is_active'])
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_cleaner', 'password': 'Test-pass-123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_unsafe_redirect_ignored(self):
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_manager', 'password': 'Test-pass-123!',
            'next': 'https://evil.example/phishing',
        })
        self.assertRedirects(response, reverse('bookings:dashboard'), fetch_redirect_response=False)

    def test_safe_staff_next_preserved(self):
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_manager', 'password': 'Test-pass-123!',
            'next': '/staff/reservations/?hut=test-hut',
        })
        self.assertRedirects(response, '/staff/reservations/?hut=test-hut', fetch_redirect_response=False)

    def test_cleaner_global_next_falls_back_to_workspace(self):
        response = self.client.post(reverse('bookings:staff_login'), {
            'username': 'sd_cleaner', 'password': 'Test-pass-123!',
            'next': '/staff/dashboard/',
        })
        self.assertRedirects(response, reverse('floorplans:staff_home'), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('bookings:staff_logout'))
        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('bookings:staff_logout'))
        self.assertRedirects(response, reverse('bookings:staff_login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_login_for_staff_redirects(self):
        response = self.client.get('/admin/login/', {'next': '/staff/dashboard/'})
        self.assertRedirects(response, '/staff/login/?next=%2Fstaff%2Fdashboard%2F', fetch_redirect_response=False)

    def test_admin_login_still_accessible(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)

    def test_login_required_cleaner_redirect(self):
        response = self.client.get(reverse('floorplans:staff_home'))
        self.assertRedirects(response, '/staff/login/?next=%2Fstaff%2Ffloorplans%2F', fetch_redirect_response=False)
