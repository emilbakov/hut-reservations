"""HTTP booking journeys with real commits and a captured in-memory mail backend.

Only the isolated test database is used. No SMTP connection or real email send
is made. Booking forms include CSRF and signed submission tokens.
"""
import re
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from urllib.parse import urlsplit
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import DatabaseError
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (GuestChangeRequest, Hut, PublicWebsiteSettings, Reservation,
                     ReservationDecision, ReservationNotification, Room)
from .services import free_beds


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    BOOKING_NOTIFY_EMAIL='', BOOKING_EMAIL_LIMIT=50,
    BOOKING_BROWSER_LIMIT=50, BOOKING_IP_LIMIT=1000,
)
class BookingJourneyV175Tests(TransactionTestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name='Studenets Journey Hut', slug='studenets-journey')
        PublicWebsiteSettings.objects.update_or_create(pk=1, defaults={'main_hut': self.hut})
        self.room = Room.objects.create(hut=self.hut, name='Journey dorm', capacity=3,
                                       price_per_night=Decimal('18.00'))
        self.manager = get_user_model().objects.create_user(
            username='journey-manager', email='keeper175@example.test',
            password='isolated-journey-test', is_staff=True)
        self.hut.managers.add(self.manager)
        self.guest = Client(enforce_csrf_checks=True)
        self.staff = Client(enforce_csrf_checks=True)
        self.staff.force_login(self.manager)
        self.start = timezone.localdate() + timedelta(days=14)
        self.end = self.start + timedelta(days=2)
        self.book_url = reverse('bookings:book')

    def post(self, client, url, data):
        if 'csrftoken' not in client.cookies:
            client.get(self.book_url, secure=True)
        return client.post(url, data, secure=True,
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value,
            HTTP_ORIGIN='https://testserver')

    def form(self, client=None, **extra):
        client = client or self.guest
        dates = {'check_in': self.start.isoformat(), 'check_out': self.end.isoformat(), 'beds': '2'}
        response = client.get(self.book_url, dates, secure=True)
        self.assertEqual(response.status_code, 200)
        return {**dates, 'name': 'Journey Guest', 'email': 'guest175@example.test',
            'phone': '+359888000175', 'notes': 'Synthetic test booking',
            'submission_token': response.context['submission_token'],
            f'room_{self.room.pk}': '2', **extra}

    def book(self, client=None, **extra):
        client = client or self.guest
        payload = self.form(client, **extra)
        response = self.post(client, self.book_url, payload)
        self.assertEqual(response.status_code, 302)
        reservation = Reservation.objects.get(code=response.url.rstrip('/').split('/')[-1])
        return reservation, payload

    def available(self):
        return free_beds([self.room], self.start, self.end)[self.room.pk]

    def action(self, reservation, action, **extra):
        return self.post(self.staff,
            reverse('bookings:manager_reservation_action', args=[reservation.code]),
            {'action': action, 'deposit_amount':'0', **extra})

    def guest_portal(self, reservation):
        item = reservation.delivery_notifications.filter(kind='request_guest').get()
        match = re.search(r'https?://[^\s]+/guest/manage/[A-Za-z0-9_-]+/', item.body)
        self.assertIsNotNone(match)
        return urlsplit(match.group()).path

    def cancellation_request(self, reservation):
        url = self.guest_portal(reservation)
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.get(url, secure=True).status_code, 200)
        response = self.post(browser, url, {'request_type': 'cancellation', 'details': 'Please cancel'})
        self.assertEqual(response.status_code, 302)
        return GuestChangeRequest.objects.get(reservation=reservation, status='pending')

    def review(self, change, decision='approved'):
        return self.post(self.staff, reverse('bookings:guest_requests_dashboard'),
            {'request_id': str(change.pk), 'decision': decision, 'manager_note': 'Synthetic manager review'})

    def retry_due(self):
        ReservationNotification.objects.filter(status='failed').update(
            next_attempt_at=timezone.now() - timedelta(seconds=1))
        call_command('retry_reservation_notifications', apply=True, stdout=StringIO())

    def test_full_booking_approval_guest_cancellation_and_rebooking(self):
        reservation, payload = self.book()
        self.assertEqual(reservation.status, 'pending')
        self.assertEqual(reservation.total_price, Decimal('72.00'))
        self.assertEqual(self.available(), 1)
        self.assertEqual({m.to[0] for m in mail.outbox},
                         {'guest175@example.test', 'keeper175@example.test'})
        manager_mail = next(m for m in mail.outbox if m.to == ['keeper175@example.test'])
        self.assertNotIn('/guest/manage/', manager_mail.body)
        receipt = self.guest.get(reservation.get_absolute_url(), secure=True)
        self.assertContains(receipt, '72.00')
        self.assertContains(receipt, self.hut.name)
        self.assertEqual(self.action(reservation, 'confirm').status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'confirmed')
        self.assertEqual(self.available(), 1)
        change = self.cancellation_request(reservation)
        self.assertEqual(self.review(change).status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'confirmed')
        self.assertEqual(self.available(), 1)  # Review requires a separate booking update.
        self.assertEqual(self.action(reservation, 'cancel', reason='Cancellation requested by guest').status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'cancelled')
        self.assertEqual(self.available(), 3)
        replacement, _ = self.book(Client(enforce_csrf_checks=True), email='replacement175@example.test')
        self.assertNotEqual(reservation.pk, replacement.pk)
        self.assertEqual(replacement.total_price, Decimal('72.00'))
        self.assertEqual(self.available(), 1)

    def test_signed_form_retry_and_repeated_manager_actions_are_idempotent(self):
        reservation, payload = self.book()
        count = len(mail.outbox)
        self.assertEqual(self.post(self.guest, self.book_url, payload).url, reservation.get_absolute_url())
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(len(mail.outbox), count)
        self.action(reservation, 'confirm')
        count = len(mail.outbox)
        self.action(reservation, 'confirm')
        self.assertEqual(len(mail.outbox), count)
        self.assertEqual(ReservationDecision.objects.count(), 1)
        self.action(reservation, 'cancel', reason='No longer travelling')
        count = len(mail.outbox)
        self.action(reservation, 'cancel', reason='Repeated click')
        self.assertEqual(len(mail.outbox), count)
        self.assertEqual(ReservationDecision.objects.count(), 2)
        self.assertEqual(self.available(), 3)

    def test_capacity_conflict_between_two_loaded_forms_does_not_overbook(self):
        second = Client(enforce_csrf_checks=True)
        stale_form = self.form(second, email='second175@example.test')
        reservation, _ = self.book()
        count = ReservationNotification.objects.count()
        response = self.post(second, self.book_url, stale_form)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_errors'])
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(ReservationNotification.objects.count(), count)
        self.assertEqual(self.available(), 1)

    def test_decline_reason_is_emailed_and_beds_can_be_rebooked(self):
        reservation, _ = self.book()
        mail.outbox.clear()
        reason = 'The hut cannot accommodate this arrival.'
        self.action(reservation, 'cancel', reason=reason)
        self.assertEqual(self.available(), 3)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(reason, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['guest175@example.test'])
        replacement, _ = self.book(Client(enforce_csrf_checks=True), email='replacement175@example.test')
        self.assertEqual(replacement.total_price, Decimal('72.00'))

    def test_mail_outage_does_not_lose_booking_and_due_retry_sends_once(self):
        with patch('bookings.notifications_v145.send_mail', side_effect=OSError('Synthetic SMTP outage')):
            with self.assertLogs('bookings.notifications_v145', level='WARNING'):
                reservation, _ = self.book()
        self.assertEqual(reservation.status, 'pending')
        self.assertEqual(self.available(), 1)
        self.assertEqual(reservation.delivery_notifications.filter(status='failed').count(), 2)
        self.retry_due()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(reservation.delivery_notifications.filter(status='sent').count(), 2)
        self.retry_due()
        self.assertEqual(len(mail.outbox), 2)

    def test_approval_supersedes_failed_request_emails(self):
        with patch('bookings.notifications_v145.send_mail', side_effect=OSError('Synthetic SMTP outage')):
            with self.assertLogs('bookings.notifications_v145', level='WARNING'):
                reservation, _ = self.book()
        self.action(reservation, 'confirm')
        self.assertEqual(reservation.delivery_notifications.filter(kind__startswith='request_', status='skipped').count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('confirmed', mail.outbox[0].body.lower())
        self.retry_due()
        self.assertEqual(len(mail.outbox), 1)

    def test_failed_guest_request_review_email_is_persisted_and_retryable(self):
        reservation, _ = self.book()
        self.action(reservation, 'confirm')
        change = self.cancellation_request(reservation)
        mail.outbox.clear()
        with patch('django.core.mail.backends.locmem.EmailBackend.send_messages',
                   side_effect=OSError('Synthetic SMTP outage')):
            with self.assertLogs('bookings.notifications_v145', level='WARNING'):
                self.assertEqual(self.review(change).status_code, 302)
        change.refresh_from_db()
        self.assertEqual(change.status, 'approved')
        failed = reservation.delivery_notifications.filter(kind='change_review_guest', status='failed')
        self.assertEqual(failed.count(), 1, 'A committed review must retain its failed guest notification for retry.')
        self.retry_due()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('processed manually', mail.outbox[0].body)
        self.assertIn('Synthetic manager review', mail.outbox[0].body)
        self.review(change)
        self.retry_due()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(reservation.delivery_notifications.filter(kind='change_review_guest').count(), 1)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'confirmed')
        self.assertEqual(self.available(), 1)

    def test_distinct_guest_request_reviews_have_separate_deduplicated_emails(self):
        reservation, _ = self.book()
        self.action(reservation, 'confirm')
        mail.outbox.clear()
        first = self.cancellation_request(reservation)
        self.review(first, 'rejected')
        second = self.cancellation_request(reservation)
        self.review(second, 'approved')
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('rejected', mail.outbox[0].body)
        self.assertIn('approved for manual processing', mail.outbox[1].body)
        self.review(first, 'approved')
        self.review(second, 'rejected')
        self.retry_due()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(reservation.delivery_notifications.filter(kind='change_review_guest').count(), 2)

    def test_review_and_notification_roll_back_together_on_database_failure(self):
        reservation, _ = self.book()
        self.action(reservation, 'confirm')
        change = self.cancellation_request(reservation)
        mail.outbox.clear()
        count = ReservationNotification.objects.count()
        with patch('bookings.notifications_v145.queue_notification', side_effect=DatabaseError('Synthetic database failure')):
            with self.assertRaises(DatabaseError):
                self.review(change)
        change.refresh_from_db()
        self.assertEqual(change.status, 'pending')
        self.assertIsNone(change.reviewed_at)
        self.assertEqual(ReservationNotification.objects.count(), count)
        self.assertFalse(mail.outbox)

    def test_bulgarian_guest_receipt_and_server_owned_price(self):
        self.guest.cookies['django_language'] = 'bg'
        reservation, _ = self.book(price_per_night='0.01', total_price='0.04')
        self.assertEqual(reservation.total_price, Decimal('72.00'))
        self.assertEqual(reservation.items.get().price_per_night, Decimal('18.00'))
        receipt = self.guest.get(reservation.get_absolute_url(), secure=True)
        self.assertContains(receipt, 'Заявката е получена.')
        self.assertContains(receipt, '72,00')
        guest_mail = next(m for m in mail.outbox if m.to == ['guest175@example.test'])
        self.assertIn('ОЧАКВА ОДОБРЕНИЕ', guest_mail.body)

    def test_csrf_and_other_hut_manager_cannot_change_inventory(self):
        payload = self.form()
        self.assertEqual(self.guest.post(self.book_url, payload, secure=True).status_code, 403)
        self.assertFalse(Reservation.objects.exists())
        reservation, _ = self.book()
        other_hut = Hut.objects.create(name='Other Journey Hut', slug='other-journey')
        outsider = get_user_model().objects.create_user('journey-outsider', is_staff=True)
        other_hut.managers.add(outsider)
        other = Client(enforce_csrf_checks=True)
        other.force_login(outsider)
        response = self.post(other, reverse('bookings:manager_reservation_action', args=[reservation.code]), {'action': 'confirm', 'deposit_amount': '0'})
        self.assertEqual(response.status_code, 404)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'pending')
        self.assertEqual(self.available(), 1)
