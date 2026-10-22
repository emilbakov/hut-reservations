"""Targeted v131 preview permissions, accuracy, and read-only behavior."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Hut, ManagerDigestPreference, ManagerRequestDigestLog,
    Reservation, ReservationItem, Room,
)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ManagerDigestPreviewV131Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(
            'v131-manager', password='pass', email='v131@example.com', is_staff=True,
        )
        self.other = User.objects.create_user(
            'v131-other', password='pass', email='other@example.com', is_staff=True,
        )
        self.outsider = User.objects.create_user(
            'v131-outsider', password='pass', email='outsider@example.com', is_staff=True,
        )
        self.hut = Hut.objects.create(name='Preview North Hut', slug='preview-north')
        self.other_hut = Hut.objects.create(name='Private South Hut', slug='private-south')
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other)
        self.room = Room.objects.create(
            hut=self.hut, name='North room', capacity=8, price_per_night=Decimal('30'),
        )
        self.other_room = Room.objects.create(
            hut=self.other_hut, name='South room', capacity=8, price_per_night=Decimal('30'),
        )
        self.url = reverse('bookings:manager_digest_preview')
        self.today = timezone.localdate()

    def make_request(self, *, room=None, arrival_days=10, waiting_hours=1, guest='Private guest name'):
        room = room or self.room
        arrival = self.today + timedelta(days=arrival_days)
        reservation = Reservation.objects.create(
            name=guest, email='secret-guest@example.com',
            check_in=arrival, check_out=arrival + timedelta(days=1),
            guest_request=True, status=Reservation.Status.PENDING,
        )
        ReservationItem.objects.create(
            reservation=reservation, room=room, beds=1,
            price_per_night=room.price_per_night,
        )
        Reservation.objects.filter(pk=reservation.pk).update(
            created=timezone.now() - timedelta(hours=waiting_hours),
        )
        return reservation

    def preview(self):
        self.client.force_login(self.manager)
        return self.client.get(self.url)

    def test_ready_preview_uses_same_subject_and_hut_counts(self):
        self.make_request()
        response = self.preview()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['digest_status'], 'ready')
        self.assertEqual(response.context['total'], 1)
        self.assertEqual(response.context['waiting24'], 0)
        self.assertEqual(response.context['arrival48'], 0)
        self.assertIn('1 pending guest reservation request', response.context['email_subject'])
        self.assertIn('Preview North Hut', response.context['email_body'])
        self.assertIn('Manage reminder preferences:', response.context['email_body'])
        self.assertContains(response, 'Eligible for the next daily reminder')

    def test_never_sends_email_or_consumes_daily_log(self):
        self.make_request(waiting_hours=30)
        self.preview()
        self.preview()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 0)
        self.assertEqual(ManagerDigestPreference.objects.count(), 0)

    def test_other_hut_data_not_leaked(self):
        self.make_request()
        self.make_request(room=self.other_room, guest='TOP SECRET SOUTH')
        response = self.preview()
        self.assertEqual(response.context['total'], 1)
        self.assertNotContains(response, 'Private South Hut')
        self.assertNotContains(response, 'TOP SECRET SOUTH')
        self.assertNotContains(response, 'secret-guest@example.com')
        self.assertNotContains(response, self.other_room.name)

    def test_cross_hut_reservation_is_excluded(self):
        reservation = self.make_request()
        ReservationItem.objects.create(
            reservation=reservation, room=self.other_room, beds=1,
            price_per_night=self.other_room.price_per_night,
        )
        response = self.preview()
        self.assertEqual(response.context['total'], 0)
        self.assertEqual(response.context['digest_status'], 'empty')

    def test_disabled_still_shows_preview_but_no_email_sent(self):
        self.make_request()
        ManagerDigestPreference.objects.create(manager=self.manager, enabled=False)
        response = self.preview()
        self.assertEqual(response.context['digest_status'], 'disabled')
        self.assertTrue(response.context['email_subject'])
        self.assertEqual(len(mail.outbox), 0)

    def test_urgent_only_waits_until_old_request(self):
        self.make_request()
        ManagerDigestPreference.objects.create(manager=self.manager, urgent_only=True)
        response = self.preview()
        self.assertEqual(response.context['digest_status'], 'not_urgent')
        self.make_request(waiting_hours=28)
        response = self.preview()
        self.assertEqual(response.context['digest_status'], 'ready')
        self.assertEqual(response.context['waiting24'], 1)
        self.assertEqual(response.context['total'], 2)

    def test_arrival_due_qualifies_for_urgent_mode(self):
        self.make_request(arrival_days=2)
        ManagerDigestPreference.objects.create(manager=self.manager, urgent_only=True)
        response = self.preview()
        self.assertEqual(response.context['digest_status'], 'ready')
        self.assertEqual(response.context['arrival48'], 1)

    def test_already_sent_today_status_and_no_duplicate_log(self):
        self.make_request()
        ManagerRequestDigestLog.objects.create(
            manager=self.manager, digest_date=self.today,
            recipient=self.manager.email, hut_count=1, request_count=1,
        )
        response = self.preview()
        self.assertEqual(response.context['digest_status'], 'already_sent')
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_disabled_precedes_already_sent_status(self):
        self.make_request()
        ManagerDigestPreference.objects.create(manager=self.manager, enabled=False)
        ManagerRequestDigestLog.objects.create(
            manager=self.manager, digest_date=self.today,
            recipient=self.manager.email, hut_count=1, request_count=1,
        )
        self.assertEqual(self.preview().context['digest_status'], 'disabled')

    def test_missing_email_precedes_other_states(self):
        self.make_request()
        self.manager.email = ''
        self.manager.save(update_fields=['email'])
        self.assertEqual(self.preview().context['digest_status'], 'missing_email')

    def test_no_pending_shows_no_email(self):
        response = self.preview()
        self.assertEqual(response.context['digest_status'], 'empty')
        self.assertEqual(response.context['email_subject'], '')
        self.assertContains(response, 'No email preview is available')

    def test_anonymous_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response['Location'])

    def test_unassigned_user_forbidden(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_non_staff_assigned_manager_can_preview(self):
        self.manager.is_staff = False
        self.manager.save(update_fields=['is_staff'])
        self.make_request()
        self.assertEqual(self.preview().status_code, 200)

    def test_post_not_allowed(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)

    def test_no_store_cache_header(self):
        response = self.preview()
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_preview_link_in_preferences(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('bookings:manager_digest_preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.url)

    def test_bad_configured_origin_uses_relative_links_not_untrusted_host(self):
        self.make_request()
        with patch.dict('os.environ', {'SUMMITDESK_BASE_URL': 'https://evil.example/path'}):
            response = self.preview()
        self.assertNotIn('evil.example', response.context['email_body'])
        self.assertIn('Links are relative', response.context['link_notice'])

    def test_superuser_with_no_huts_has_no_access_to_other_managers_huts(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            'v131-admin', password='pass', email='admin@example.com',
        )
        self.make_request()
        self.client.force_login(admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], 0)
        self.assertNotContains(response, 'Preview North Hut')
