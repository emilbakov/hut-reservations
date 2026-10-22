"""Security, daily idempotency, and failure regression tests for v129."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .manager_digest_v129 import (
    DigestConfigurationError, collect_pending_summaries, digest_manager,
    render_digest, validated_base_url,
)
from .models import Hut, ManagerRequestDigestLog, Reservation, ReservationItem, Room


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ManagerDigestV129Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('digest-manager', email='manager@example.com', password='x')
        self.other_manager = User.objects.create_user('digest-other', email='other@example.com', password='x')
        self.unassigned = User.objects.create_user('digest-unassigned', email='unassigned@example.com', password='x', is_staff=True)
        self.hut = Hut.objects.create(name='Mountain Alpha', slug='mountain-alpha')
        self.other_hut = Hut.objects.create(name='Mountain Beta', slug='mountain-beta')
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other_manager)
        self.room = Room.objects.create(hut=self.hut, name='Dorm', capacity=6, price_per_night=Decimal('30'))
        self.other_room = Room.objects.create(hut=self.other_hut, name='Private', capacity=6, price_per_night=Decimal('40'))
        self.now = timezone.now()
        self.today = timezone.localdate(self.now)
        self.base_url = 'https://summitdesk.example'

    def make_request(self, *, room=None, guest_request=True, status='pending',
                     created_hours_ago=1, arrival_days=7, name='Test Guest'):
        room = room or self.room
        start = self.today + timedelta(days=arrival_days)
        reservation = Reservation.objects.create(
            name=name, email='private-guest@example.com', check_in=start,
            check_out=start + timedelta(days=2), status=status,
            guest_request=guest_request,
        )
        ReservationItem.objects.create(
            reservation=reservation, room=room, beds=2, price_per_night=room.price_per_night,
        )
        Reservation.objects.filter(pk=reservation.pk).update(
            created=self.now - timedelta(hours=created_hours_ago)
        )
        reservation.refresh_from_db()
        return reservation

    def command(self, **kwargs):
        stdout = StringIO()
        stderr = StringIO()
        call_command('send_manager_request_digest', stdout=stdout, stderr=stderr, **kwargs)
        return stdout.getvalue()

    def test_preview_does_not_send_or_record(self):
        self.make_request()
        output = self.command()
        self.assertIn('preview (1 pending requests)', output)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 0)

    def test_send_once_per_local_day_even_if_repeated(self):
        self.make_request()
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['manager@example.com'])
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 1)
        self.make_request(name='Second Guest')
        output = self.command(send=True, base_url=self.base_url)
        self.assertIn('duplicate', output)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 1)

    def test_next_day_can_send_again(self):
        self.make_request()
        self.assertEqual(digest_manager(self.manager.pk, send=True, base_url=self.base_url, now=self.now)[0], 'sent')
        self.assertEqual(digest_manager(self.manager.pk, send=True, base_url=self.base_url, now=self.now + timedelta(days=1))[0], 'sent')
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_priority_counts_and_dashboard_link(self):
        self.make_request(created_hours_ago=25, arrival_days=1)
        self.make_request(created_hours_ago=1, arrival_days=9)
        summaries = collect_pending_summaries(self.manager, now=self.now, today=self.today)
        self.assertEqual(len(summaries), 1)
        self.assertEqual((summaries[0]['pending'], summaries[0]['waiting24'], summaries[0]['arrival48']), (2, 1, 1))
        subject, body = render_digest(summaries, base_url=self.base_url, today=self.today)
        self.assertIn('2 pending', subject)
        self.assertIn('Waiting over 24 hours: 1', body)
        self.assertIn('Arrivals due within 2 days or overdue: 1', body)
        self.assertIn('https://summitdesk.example/staff/reservations/requests/?hut=mountain-alpha&status=pending', body)

    def test_overdue_arrival_is_urgent(self):
        self.make_request(arrival_days=-1)
        summary = collect_pending_summaries(self.manager, now=self.now, today=self.today)[0]
        self.assertEqual(summary['arrival48'], 1)

    def test_only_public_pending_requests(self):
        self.make_request(name='Public')
        self.make_request(name='Confirmed', status='confirmed')
        self.make_request(name='Staff', guest_request=False)
        self.make_request(name='Cancelled', status='cancelled')
        summary = collect_pending_summaries(self.manager, now=self.now, today=self.today)[0]
        self.assertEqual(summary['pending'], 1)

    def test_manager_isolation_and_no_guest_pii(self):
        self.make_request(name='Secret Alpha')
        self.make_request(room=self.other_room, name='Secret Beta')
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(len(mail.outbox), 2)
        a = next(m for m in mail.outbox if m.to == ['manager@example.com'])
        b = next(m for m in mail.outbox if m.to == ['other@example.com'])
        self.assertIn('Mountain Alpha', a.body)
        self.assertNotIn('Mountain Beta', a.body)
        self.assertIn('Mountain Beta', b.body)
        self.assertNotIn('Mountain Alpha', b.body)
        for message in mail.outbox:
            self.assertNotIn('Secret Alpha', message.body)
            self.assertNotIn('Secret Beta', message.body)
            self.assertNotIn('private-guest@example.com', message.body)
        self.assertNotIn('unassigned@example.com', [m.to[0] for m in mail.outbox])

    def test_multiple_huts_one_digest_per_manager(self):
        self.other_hut.managers.add(self.manager)
        self.make_request()
        self.make_request(room=self.other_room)
        self.command(send=True, base_url=self.base_url, manager_id=self.manager.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Mountain Alpha', mail.outbox[0].body)
        self.assertIn('Mountain Beta', mail.outbox[0].body)
        log = ManagerRequestDigestLog.objects.get(manager=self.manager)
        self.assertEqual((log.hut_count, log.request_count), (2, 2))

    def test_mixed_hut_reservation_not_disclosed_or_counted(self):
        reservation = self.make_request()
        ReservationItem.objects.create(reservation=reservation, room=self.other_room, beds=1, price_per_night=40)
        self.assertEqual(collect_pending_summaries(self.manager, now=self.now, today=self.today), [])
        self.other_hut.managers.add(self.manager)
        self.assertEqual(collect_pending_summaries(self.manager, now=self.now, today=self.today), [])
        self.assertEqual(collect_pending_summaries(self.other_manager, now=self.now, today=self.today), [])

    def test_inactive_huts_and_users_not_emailed(self):
        self.make_request()
        self.hut.is_active = False
        self.hut.save(update_fields=['is_active'])
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(len(mail.outbox), 0)
        self.hut.is_active = True
        self.hut.save(update_fields=['is_active'])
        self.manager.is_active = False
        self.manager.save(update_fields=['is_active'])
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_pending_does_not_create_log(self):
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 0)
        self.make_request()
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 1)

    def test_failed_mail_rolls_back_and_retry_succeeds(self):
        self.make_request()
        with patch('bookings.manager_digest_v129.send_mail', side_effect=OSError('SMTP unavailable')):
            with self.assertRaises(CommandError):
                self.command(send=True, base_url=self.base_url)
        self.assertFalse(ManagerRequestDigestLog.objects.exists())
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ManagerRequestDigestLog.objects.count(), 1)

    def test_backend_returning_zero_is_not_recorded(self):
        self.make_request()
        with patch('bookings.manager_digest_v129.send_mail', return_value=0):
            with self.assertRaises(CommandError):
                self.command(send=True, base_url=self.base_url)
        self.assertFalse(ManagerRequestDigestLog.objects.exists())

    def test_duplicate_db_constraint(self):
        self.make_request()
        self.command(send=True, base_url=self.base_url)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ManagerRequestDigestLog.objects.create(
                    manager=self.manager, digest_date=self.today,
                    recipient='manager@example.com', hut_count=1, request_count=1,
                )

    def test_invalid_base_url_rejected_before_delivery(self):
        self.make_request()
        for url in ['http://insecure.example', 'https://evil.example/path',
                    'https://user:pass@example.com', 'https://example.com?x=1',
                    'javascript:alert(1)', 'https://example.com\nBcc:other@example.com']:
            with override_settings(DEBUG=False):
                with self.assertRaises(DigestConfigurationError, msg=url):
                    validated_base_url(url)
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                self.command(send=True, base_url='http://insecure.example')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_cannot_mark_sent(self):
        self.make_request()
        with self.assertRaises(CommandError):
            self.command(send=True, base_url=self.base_url)
        self.assertFalse(ManagerRequestDigestLog.objects.exists())

    def test_missing_base_url_rejected(self):
        self.make_request()
        with patch.dict('os.environ', {'SUMMITDESK_BASE_URL': ''}):
            with self.assertRaises(CommandError):
                self.command(send=True)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_reservation_status_mutation(self):
        reservation = self.make_request()
        self.command(send=True, base_url=self.base_url)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertEqual(reservation.total_beds, 2)

    def test_explicit_manager_id_scope(self):
        self.make_request()
        self.make_request(room=self.other_room)
        self.command(send=True, base_url=self.base_url, manager_id=self.manager.pk)
        self.assertEqual([m.to for m in mail.outbox], [['manager@example.com']])

    def test_blank_manager_email_not_emailed(self):
        self.make_request()
        self.manager.email = ' '
        self.manager.save(update_fields=['email'])
        self.command(send=True, base_url=self.base_url)
        self.assertEqual(len(mail.outbox), 0)
