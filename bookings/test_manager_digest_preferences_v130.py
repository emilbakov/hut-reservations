"""Focused v130 manager preference, authorization, and digest regression tests."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .manager_digest_v129 import digest_manager
from .models import (
    Hut, ManagerDigestPreference, ManagerRequestDigestLog,
    Reservation, ReservationItem, Room,
)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ManagerDigestPreferencesV130Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(
            'v130-manager', password='pass', email='manager130@example.com', is_staff=True,
        )
        self.other = User.objects.create_user(
            'v130-other', password='pass', email='other130@example.com', is_staff=True,
        )
        self.unassigned = User.objects.create_user(
            'v130-unassigned', password='pass', email='nohut130@example.com', is_staff=True,
        )
        self.hut = Hut.objects.create(name='North Summit', slug='north-summit')
        self.other_hut = Hut.objects.create(name='South Summit', slug='south-summit')
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other)
        self.room = Room.objects.create(
            hut=self.hut, name='Shared', capacity=8, price_per_night=Decimal('35'),
        )
        self.other_room = Room.objects.create(
            hut=self.other_hut, name='Other', capacity=8, price_per_night=Decimal('40'),
        )
        self.today = timezone.localdate()
        self.now = timezone.now()
        self.url = reverse('bookings:manager_digest_preferences')
        self.base_url = 'https://summitdesk.example'

    def request(self, *, room=None, arrival_days=8, created_hours_ago=1):
        room = room or self.room
        start = self.today + timedelta(days=arrival_days)
        reservation = Reservation.objects.create(
            name='v130 Guest', email='private@example.com',
            check_in=start, check_out=start + timedelta(days=1),
            status=Reservation.Status.PENDING, guest_request=True,
        )
        ReservationItem.objects.create(
            reservation=reservation, room=room, beds=1,
            price_per_night=room.price_per_night,
        )
        Reservation.objects.filter(pk=reservation.pk).update(
            created=self.now - timedelta(hours=created_hours_ago),
        )
        return reservation

    def command(self, **kwargs):
        output = StringIO()
        call_command('send_manager_request_digest', stdout=output, **kwargs)
        return output.getvalue()

    def test_default_preferences_preserve_v129_behavior_without_creating_record(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['digest_enabled'])
        self.assertFalse(response.context['urgent_only'])
        self.assertEqual(ManagerDigestPreference.objects.count(), 0)
        self.request()
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('preview', 1))

    def test_manager_can_disable_and_reenable_without_affecting_others(self):
        self.request()
        self.request(room=self.other_room)
        self.client.force_login(self.manager)
        response = self.client.post(self.url, {'action': 'save'})
        self.assertRedirects(response, self.url)
        preference = ManagerDigestPreference.objects.get(manager=self.manager)
        self.assertFalse(preference.enabled)
        self.assertFalse(preference.urgent_only)
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('disabled', 0))
        output = self.command(send=True, base_url=self.base_url)
        self.assertIn('disabled', output)
        self.assertEqual(len(mail.outbox), 1)  # Other manager still receives their digest.
        self.assertEqual(mail.outbox[0].to, ['other130@example.com'])
        self.assertFalse(ManagerRequestDigestLog.objects.filter(manager=self.manager).exists())
        response = self.client.post(self.url, {'action': 'save', 'enabled': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ManagerDigestPreference.objects.get(manager=self.manager).enabled)
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('preview', 1))

    def test_urgent_only_skips_normal_requests_but_does_not_consume_daily_log(self):
        self.request()
        self.client.force_login(self.manager)
        self.client.post(self.url, {'action': 'save', 'enabled': 'on', 'urgent_only': 'on'})
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('not_urgent', 1))
        output = self.command(send=True, base_url=self.base_url, manager_id=self.manager.pk)
        self.assertIn('not_urgent', output)
        self.assertFalse(mail.outbox)
        self.assertFalse(ManagerRequestDigestLog.objects.exists())
        self.request(created_hours_ago=30)
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('preview', 2))
        self.command(send=True, base_url=self.base_url, manager_id=self.manager.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ManagerRequestDigestLog.objects.get(manager=self.manager).request_count, 2)
        self.assertIn('Manage reminder preferences:', mail.outbox[0].body)
        self.assertIn(self.base_url + self.url, mail.outbox[0].body)
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('duplicate', 0))

    def test_arrival_within_two_days_is_urgent(self):
        self.request(arrival_days=2)
        ManagerDigestPreference.objects.create(manager=self.manager, urgent_only=True)
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('preview', 1))

    def test_opted_out_manager_receives_no_mail_even_with_urgent_request(self):
        reservation = self.request(created_hours_ago=48, arrival_days=1)
        ManagerDigestPreference.objects.create(manager=self.manager, enabled=False)
        self.command(send=True, base_url=self.base_url, manager_id=self.manager.pk)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ManagerRequestDigestLog.objects.exists())
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertEqual(reservation.total_beds, 1)

    def test_only_own_delivery_history_visible(self):
        ManagerRequestDigestLog.objects.create(
            manager=self.manager, digest_date=self.today,
            recipient='manager130@example.com', hut_count=1, request_count=2,
        )
        ManagerRequestDigestLog.objects.create(
            manager=self.other, digest_date=self.today,
            recipient='other130@example.com', hut_count=1, request_count=99,
        )
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertContains(response, 'manager130@example.com')
        self.assertNotContains(response, 'other130@example.com')
        self.assertEqual(len(response.context['history']), 1)

    def test_nonmanager_forbidden_and_cannot_write_preferences(self):
        self.client.force_login(self.unassigned)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'action': 'save'}).status_code, 403)
        self.assertFalse(ManagerDigestPreference.objects.exists())

    def test_anonymous_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response['Location'])

    def test_manager_without_staff_flag_can_opt_out_of_existing_digest(self):
        self.manager.is_staff = False
        self.manager.save(update_fields=['is_staff'])
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url, {'action': 'save'}).status_code, 302)
        self.assertFalse(ManagerDigestPreference.objects.get(manager=self.manager).enabled)

    def test_invalid_action_and_value_rejected(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url, {'action': 'delete'}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {'action': 'save', 'enabled': 'yes'}).status_code, 400)
        self.assertFalse(ManagerDigestPreference.objects.exists())

    def test_csrf_required_for_changes(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        self.assertEqual(csrf_client.post(self.url, {'action': 'save'}).status_code, 403)
        self.assertFalse(ManagerDigestPreference.objects.exists())

    def test_preferences_are_per_manager_not_per_hut(self):
        self.hut.managers.add(self.other)
        ManagerDigestPreference.objects.create(manager=self.manager, enabled=False)
        self.request()
        self.assertEqual(digest_manager(self.manager.pk, now=self.now), ('disabled', 0))
        self.assertEqual(digest_manager(self.other.pk, now=self.now), ('preview', 1))
