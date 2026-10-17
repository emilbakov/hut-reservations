from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .guest_links import append_guest_portal_to_confirmation
from .models import GuestAccessLink, Hut, Reservation, ReservationItem, Room
from .self_service import issue_guest_link


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GuestLinksTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('link_manager', password='pw', is_staff=True)
        self.other = User.objects.create_user('link_other', password='pw', is_staff=True)
        self.hut = Hut.objects.create(name='Link Hut', slug='link-hut')
        self.hut.managers.add(self.manager)
        room = Room.objects.create(hut=self.hut, name='A', capacity=2)
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(
            name='Guest', email='guest@example.com', status=Reservation.Status.CONFIRMED,
            check_in=today + timedelta(days=8), check_out=today + timedelta(days=9))
        ReservationItem.objects.create(reservation=self.reservation, room=room,
                                       beds=1, price_per_night=Decimal('60'))
        self.url = reverse('bookings:guest_link_controls')
        self.client.force_login(self.manager)

    def test_confirmation_includes_link(self):
        request = self.client.request().wsgi_request
        request.META['HTTP_HOST'] = 'testserver'
        body = append_guest_portal_to_confirmation(request, self.reservation, 'Hello')
        self.assertIn('/guest/manage/', body)
        self.assertEqual(GuestAccessLink.objects.count(), 1)

    def test_resend_emails_booking_address(self):
        response = self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'resend'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox[-1].to, ['guest@example.com'])
        self.assertIn('/guest/manage/', mail.outbox[-1].body)

    def test_resend_keeps_existing_token(self):
        original = issue_guest_link(self.reservation)
        self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'resend'})
        self.assertEqual(issue_guest_link(self.reservation), original)

    def test_revoke_disables_link(self):
        old = issue_guest_link(self.reservation)
        self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'revoke'})
        self.assertEqual(self.client.get(old).status_code, 404)

    def test_reissue_rotates_token(self):
        old = issue_guest_link(self.reservation)
        self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'reissue'})
        new = issue_guest_link(self.reservation)
        self.assertNotEqual(old, new)
        self.assertEqual(self.client.get(old).status_code, 404)
        self.assertEqual(self.client.get(new).status_code, 200)

    def test_resend_revoked_does_not_restore(self):
        issue_guest_link(self.reservation)
        self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'revoke'})
        self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'resend'})
        self.assertIsNotNone(GuestAccessLink.objects.get().revoked_at)

    def test_other_manager_denied(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'resend'})
        self.assertEqual(response.status_code, 404)

    def test_get_does_not_expose_token(self):
        token = GuestAccessLink.objects.create(reservation=self.reservation).token
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, token)

    def test_email_failure_does_not_claim_success(self):
        with patch('bookings.guest_links.send_mail', side_effect=RuntimeError('smtp')):
            response = self.client.post(self.url, {'reservation_id': self.reservation.pk, 'action': 'resend'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
