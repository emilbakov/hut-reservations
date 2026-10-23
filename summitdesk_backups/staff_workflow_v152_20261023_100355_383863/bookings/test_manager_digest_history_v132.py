"""Targeted v132 history permissions, period filtering, and CSV safety tests."""
import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, ManagerRequestDigestLog


class ManagerDigestHistoryV132Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('v132-manager', email='manager@example.com', password='x')
        self.other = User.objects.create_user('v132-other', email='other@example.com', password='x')
        self.outsider = User.objects.create_user('v132-outsider', email='outsider@example.com', password='x', is_staff=True)
        self.hut = Hut.objects.create(name='History Hut', slug='history-hut')
        self.hut.managers.add(self.manager)
        self.other_hut = Hut.objects.create(name='Other Hut', slug='other-history-hut')
        self.other_hut.managers.add(self.other)
        self.url = reverse('bookings:manager_digest_history')
        self.today = timezone.localdate()

    def add_log(self, manager=None, days_ago=0, requests=2, huts=1, recipient=None):
        manager = manager or self.manager
        return ManagerRequestDigestLog.objects.create(
            manager=manager, digest_date=self.today - timedelta(days=days_ago),
            recipient=recipient if recipient is not None else manager.email,
            hut_count=huts, request_count=requests,
        )

    def view(self, query=''):
        self.client.force_login(self.manager)
        return self.client.get(self.url + query)

    def test_only_own_history_is_shown(self):
        own = self.add_log(days_ago=1, requests=3)
        self.add_log(self.other, days_ago=1, requests=99, recipient='private@example.com')
        response = self.view()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['record_count'], 1)
        self.assertEqual(response.context['total_requests'], 3)
        self.assertNotContains(response, 'private@example.com')
        self.assertEqual([entry.pk for entry in response.context['page']], [own.pk])
        # A random CSRF token can contain "99"; inspect the rendered cell.
        self.assertNotContains(response, '<td>99</td>', html=True)

    def test_period_boundary_and_totals(self):
        self.add_log(days_ago=6, requests=2, huts=1)
        self.add_log(days_ago=7, requests=8, huts=2)
        response = self.view('?days=7')
        self.assertEqual(response.context['record_count'], 1)
        self.assertEqual(response.context['total_huts'], 1)
        self.assertEqual(response.context['total_requests'], 2)
        self.assertEqual(self.view('?days=30').context['record_count'], 2)

    def test_all_period_includes_old_records(self):
        self.add_log(days_ago=370)
        self.assertEqual(self.view().context['record_count'], 0)
        self.assertEqual(self.view('?days=all').context['record_count'], 1)

    def test_invalid_period_and_format_rejected(self):
        self.assertEqual(self.view('?days=5').status_code, 400)
        self.assertEqual(self.view('?days=-1').status_code, 400)
        self.assertEqual(self.view('?days=7&format=json').status_code, 400)

    def test_csv_export_contains_only_own_filtered_rows(self):
        self.add_log(days_ago=1, requests=3)
        self.add_log(days_ago=40, requests=8)
        self.add_log(self.other, days_ago=1, requests=90, recipient='private@example.com')
        response = self.view('?days=7&format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('text/csv', response['Content-Type'])
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0], ['Date', 'Recorded at (local)', 'Recipient', 'Huts', 'Requests'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][2:], ['manager@example.com', '1', '3'])
        self.assertNotIn('private@example.com', response.content.decode('utf-8-sig'))

    def test_csv_formula_injection_is_escaped(self):
        self.add_log(recipient='=HYPERLINK("https://bad.example")')
        rows = list(csv.reader(StringIO(self.view('?format=csv').content.decode('utf-8-sig'))))
        self.assertEqual(rows[1][2], '\'=HYPERLINK("https://bad.example")')

    def test_csv_has_header_when_empty(self):
        rows = list(csv.reader(StringIO(self.view('?format=csv').content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 1)

    def test_paginated_history_preserves_period(self):
        for i in range(25):
            self.add_log(days_ago=i)
        response = self.view('?days=90')
        self.assertEqual(len(response.context['page'].object_list), 20)
        self.assertContains(response, '?days=90&amp;page=2')
        response2 = self.view('?days=90&page=2')
        self.assertEqual(len(response2.context['page'].object_list), 5)
        self.assertEqual(response2.context['page'].number, 2)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_unassigned_user_forbidden(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url + '?format=csv').status_code, 403)

    def test_inactive_hut_revokes_access(self):
        self.hut.is_active = False
        self.hut.save(update_fields=['is_active'])
        self.assertEqual(self.view().status_code, 403)

    def test_non_staff_assigned_manager_allowed(self):
        self.add_log()
        self.assertEqual(self.view().status_code, 200)

    def test_superuser_can_see_only_own_records(self):
        admin = get_user_model().objects.create_superuser('v132-admin', email='admin@example.com', password='x')
        self.add_log()
        self.client.force_login(admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['record_count'], 0)

    def test_post_not_allowed(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_read_only_and_no_store(self):
        self.add_log()
        self.view()
        self.view('?format=csv')
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 1)
        self.assertIn('no-store', self.view().headers.get('Cache-Control', ''))
        self.assertIn('no-store', self.view('?format=csv').headers.get('Cache-Control', ''))

    def test_navigation_from_settings_and_preview(self):
        self.client.force_login(self.manager)
        settings_page = self.client.get(reverse('bookings:manager_digest_preferences'))
        preview_page = self.client.get(reverse('bookings:manager_digest_preview'))
        self.assertContains(settings_page, self.url)
        self.assertContains(preview_page, self.url)
