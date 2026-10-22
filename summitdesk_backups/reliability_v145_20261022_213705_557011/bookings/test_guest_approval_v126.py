"""Guest approval: pending holds, review, notification, hut isolation, expiry."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, Room
from .services import create_reservation, expire_pending, free_beds


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    BOOKING_NOTIFY_EMAIL='',
)
class GuestApprovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut = Hut.objects.create(name='Summit Hut', slug='summit-hut')
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=3, price_per_night=Decimal('22.00'))
        cls.start = timezone.localdate() + timedelta(days=8)
        cls.end = cls.start + timedelta(days=2)
        cls.manager = get_user_model().objects.create_user(
            username='hutmanager126', email='manager@example.com', password='not-real-test-secret'
        )
        cls.hut.managers.add(cls.manager)
        cls.outside_manager = get_user_model().objects.create_user(username='outside126', password='not-real-test-secret')
        other = Hut.objects.create(name='Other hut', slug='other-hut')
        other.managers.add(cls.outside_manager)
        cls.cleaner = get_user_model().objects.create_user(username='cleaner126', password='not-real-test-secret')

    def guest_payload(self, beds=2):
        return {
            'check_in': self.start.isoformat(),
            'check_out': self.end.isoformat(),
            'name': 'Guest Example', 'email': 'guest@example.com',
            'phone': '', 'notes': '', f'room_{self.room.pk}': str(beds),
        }

    def submit(self, beds=2):
        return self.client.post(
            reverse('bookings:hut_detail', kwargs={'slug': self.hut.slug}),
            self.guest_payload(beds),
        )

    def test_guest_request_not_confirmed_and_manager_notified(self):
        response = self.submit()
        reservation = Reservation.objects.get(name='Guest Example')
        self.assertRedirects(response, reservation.get_absolute_url())
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertTrue(reservation.guest_request)
        self.assertEqual(reservation.total_beds, 2)
        self.assertEqual(free_beds([self.room], self.start, self.end)[self.room.pk], 1)
        self.assertContains(self.client.get(reservation.get_absolute_url()), 'Awaiting hut approval')
        self.assertEqual(len(mail.outbox), 2)
        guest_mail = next(message for message in mail.outbox if message.to == ['guest@example.com'])
        manager_mail = next(message for message in mail.outbox if message.to == ['manager@example.com'])
        self.assertIn('awaiting approval', guest_mail.subject.lower())
        self.assertIn(reservation.get_absolute_url(), guest_mail.body)
        self.assertNotIn(reservation.get_absolute_url(), manager_mail.body)
        self.assertIn('action required', manager_mail.subject.lower())

    def test_guest_request_not_auto_expired(self):
        self.submit(beds=3)
        reservation = Reservation.objects.get()
        Reservation.objects.filter(pk=reservation.pk).update(created=timezone.now() - timedelta(hours=2))
        self.assertEqual(expire_pending(), 0)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertEqual(free_beds([self.room], self.start, self.end)[self.room.pk], 0)

    def test_payment_hold_still_expires(self):
        reservation = create_reservation(
            check_in=self.start, check_out=self.end,
            beds_by_room={self.room.pk: 1}, status=Reservation.Status.PENDING,
            name='Payment hold', email='payment@example.com',
        )
        self.assertFalse(reservation.guest_request)
        Reservation.objects.filter(pk=reservation.pk).update(created=timezone.now() - timedelta(hours=2))
        self.assertEqual(expire_pending(), 1)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

    def test_manager_approval_sends_real_confirmation(self):
        self.submit()
        reservation = Reservation.objects.get()
        mail.outbox.clear()
        self.client.force_login(self.manager)  # Manager need not have is_staff=True.
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                reverse('bookings:manager_reservation_action', args=[reservation.code]),
                {'action': 'confirm'},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(callbacks), 1)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        self.assertTrue(any('confirmed' in m.body.lower() for m in mail.outbox if 'guest@example.com' in m.to))

    def test_manager_decline_releases_beds_and_emails_guest(self):
        self.submit()
        reservation = Reservation.objects.get()
        mail.outbox.clear()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('bookings:manager_reservation_action', args=[reservation.code]),
                {'action': 'cancel'},
            )
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)
        self.assertEqual(free_beds([self.room], self.start, self.end)[self.room.pk], 3)
        self.assertTrue(any('declined' in m.subject.lower() for m in mail.outbox))

    def test_property_staff_reservation_confirmation_sends_email(self):
        self.submit()
        reservation = Reservation.objects.get()
        mail.outbox.clear()
        self.manager.is_staff = True
        self.manager.save(update_fields=['is_staff'])
        self.client.force_login(self.manager)
        url = reverse('floorplans:staff_reservation', args=[self.hut.pk, reservation.code])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {'action': 'status', 'status': 'confirmed'})
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        self.assertTrue(any('confirmed' in m.body.lower() for m in mail.outbox if 'guest@example.com' in m.to))

    def test_deposit_auto_cancellation_skips_unapproved_request(self):
        from .lifecycle import process_lifecycle
        self.submit()
        reservation = Reservation.objects.get()
        result = process_lifecycle(today=self.start - timedelta(days=1), allow_cancellation=True)
        self.assertEqual(result['cancellations'], 0)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_unauthorized_users_cannot_approve(self):
        self.submit()
        reservation = Reservation.objects.get()
        url = reverse('bookings:manager_reservation_action', args=[reservation.code])
        self.assertEqual(self.client.post(url, {'action': 'confirm'}).status_code, 302)
        self.client.force_login(self.outside_manager)
        self.assertEqual(self.client.post(url, {'action': 'confirm'}).status_code, 404)
        self.client.force_login(self.cleaner)
        self.assertEqual(self.client.post(url, {'action': 'confirm'}).status_code, 403)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_second_request_cannot_overbook_held_beds(self):
        self.submit(beds=3)
        response = self.submit(beds=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_staff_created_reservation_default_unchanged(self):
        reservation = create_reservation(
            check_in=self.start, check_out=self.end,
            beds_by_room={self.room.pk: 1}, name='Staff booking', email='staffbooking@example.com',
        )
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        self.assertFalse(reservation.guest_request)

    def test_public_form_explains_approval_before_submission(self):
        response = self.client.get(
            reverse('bookings:hut_detail', kwargs={'slug': self.hut.slug}),
            {'check_in': self.start.isoformat(), 'check_out': self.end.isoformat()},
        )
        self.assertContains(response, 'Request reservation')
        self.assertNotContains(response, 'Confirm reservation')
        self.assertContains(response, 'not confirmed until they approve it')
