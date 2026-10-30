from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (GuestAccessLink, GuestChangeRequest, GuestConversationMessage,
                     Hut, PaymentTransaction, PublicWebsiteSettings, Reservation, ReservationItem, Room)
from .self_service import issue_guest_link


class GuestPortalV179Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut = Hut.objects.create(name='Test Hut', slug='guest-v179', public_phone='+359 888 123 456')
        PublicWebsiteSettings.objects.update_or_create(pk=1, defaults={'main_hut': cls.hut})
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=8, price_per_night='99.00')
        cls.start = timezone.localdate() + timedelta(days=5)
        cls.res = Reservation.objects.create(name='Private Guest', email='guest@example.test',
            status='confirmed', check_in=cls.start, check_out=cls.start+timedelta(days=2))
        ReservationItem.objects.create(reservation=cls.res, room=cls.room, beds=2, price_per_night='18.00')

    def setUp(self):
        self.url = issue_guest_link(self.res)
        self.token = GuestAccessLink.objects.get(reservation=self.res).token
        self.message_url = reverse('bookings:guest_send_message', args=[self.token])

    def test_all_date_errors_are_visible_and_notes_are_retained_until_valid_resubmission(self):
        page = self.client.post(self.url, {'request_type': 'change', 'details': 'Please keep this note.'})
        self.assertContains(page, 'Choose an arrival date.')
        self.assertContains(page, 'Choose a departure date.')
        self.assertContains(page, 'Please keep this note.')
        self.assertContains(page, 'id="g179-errors"')
        self.assertContains(page, 'aria-invalid="true"')
        self.assertFalse(GuestChangeRequest.objects.exists())
        self.client.post(self.url, {'request_type': 'change', 'details': 'Please keep this note.',
            'requested_check_in': str(self.start+timedelta(days=1)),
            'requested_check_out': str(self.start+timedelta(days=3))})
        change = GuestChangeRequest.objects.get(reservation=self.res)
        self.assertEqual(change.details, 'Please keep this note.')
        self.assertEqual(change.requested_check_in, self.start+timedelta(days=1))
        self.res.refresh_from_db()
        self.assertEqual(self.res.check_in, self.start)
        self.assertEqual(self.res.status, 'confirmed')

    def test_reversed_dates_and_overlong_details_are_reported_together_without_losing_dates(self):
        data = {'request_type': 'change', 'requested_check_in': str(self.start),
            'requested_check_out': str(self.start), 'details': 'a'*2001}
        page = self.client.post(self.url, data)
        self.assertEqual(len(page.context['change_form'].errors), 2)
        self.assertContains(page, 'value="' + str(self.start) + '"', count=2)
        self.assertContains(page, 'a'*2001)
        self.assertFalse(GuestChangeRequest.objects.exists())

    def test_cancellation_ignores_dates_and_pending_request_suppresses_duplicate_form(self):
        response = self.client.post(self.url, {'request_type': 'cancellation',
            'requested_check_in': 'bad', 'requested_check_out': 'bad', 'details': 'Cannot travel.'})
        self.assertRedirects(response, self.url)
        change = GuestChangeRequest.objects.get()
        self.assertIsNone(change.requested_check_in)
        page = self.client.get(self.url)
        self.assertContains(page, 'Your request is with the hut team.')
        self.assertContains(page, 'Cannot travel.')
        self.assertNotContains(page, 'id="gss-request-form"')
        self.client.post(self.url, {'request_type': 'cancellation'})
        self.assertEqual(GuestChangeRequest.objects.count(), 1)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, 'confirmed')

    def test_csrf_revocation_and_stay_cutoffs_still_protect_both_endpoints(self):
        strict = Client(enforce_csrf_checks=True)
        strict.get(self.url)
        self.assertEqual(strict.post(self.url, {'request_type': 'cancellation'}).status_code, 403)
        self.assertEqual(strict.post(self.message_url, {'body': 'Hello'}).status_code, 403)
        GuestAccessLink.objects.filter(reservation=self.res).update(revoked_at=timezone.now())
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.message_url, {'body': 'Hello'}).status_code, 404)
        GuestAccessLink.objects.filter(reservation=self.res).update(revoked_at=None)
        Reservation.objects.filter(pk=self.res.pk).update(check_in=timezone.localdate())
        self.assertNotContains(self.client.get(self.url), 'id="gss-request-form"')
        Reservation.objects.filter(pk=self.res.pk).update(
            check_in=timezone.localdate()-timedelta(days=10),
            check_out=timezone.localdate()-timedelta(days=8))
        self.assertContains(self.client.get(self.url), 'Messaging for this stay is closed.')
        self.client.post(self.message_url, {'body': 'No longer allowed'})
        self.assertFalse(GuestConversationMessage.objects.exists())
        self.assertFalse(GuestChangeRequest.objects.exists())

    def test_bulgarian_switch_preserves_private_link_and_receipt_access(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(self.url)
        self.assertIn('no-store', page['Cache-Control'])
        head = page.content.decode().split('</head>')[0]
        self.assertNotIn(self.token, head)
        self.assertIn('noindex, nofollow, noarchive', head)
        client.post(reverse('set_language'), {'language': 'bg', 'next': self.url,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertContains(client.get(self.url), 'Управлявай престоя си.')
        self.assertContains(client.get(self.res.get_absolute_url()), self.res.name)
        response = client.post(self.message_url, {'body': 'A synthetic question.',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value}, follow=True)
        self.assertContains(response, 'Съобщението е запазено.')

    def test_saved_rates_payment_ledger_and_cancelled_wording_stay_distinct(self):
        PaymentTransaction.objects.create(reservation=self.res, kind='payment', method='cash', amount=Decimal('10.00'))
        page = self.client.get(self.url)
        self.assertContains(page, '72.00')
        self.assertContains(page, '18.00')
        self.assertNotContains(page, '99.00')
        self.assertEqual(page.context['summary']['target'], Decimal('21.60'))
        self.assertEqual(page.context['summary']['remaining'], Decimal('11.60'))
        Reservation.objects.filter(pk=self.res.pk).update(status='cancelled')
        cancelled = self.client.get(self.url)
        self.assertContains(cancelled, 'Original booking total')
        self.assertContains(cancelled, '10.00')
        self.assertNotContains(cancelled, 'Deposit remaining')

    def test_request_history_and_messages_are_escaped_and_scoped_to_the_token(self):
        GuestChangeRequest.objects.create(reservation=self.res, request_type='change', status='approved',
            requested_check_in=self.start+timedelta(days=1), requested_check_out=self.start+timedelta(days=3),
            details='<script>unsafe()</script>', manager_note='Please check your current dates.')
        GuestConversationMessage.objects.create(reservation=self.res, hut=self.hut,
            sender='manager', delivery='in_app', body='Your room is ready.')
        other = Reservation.objects.create(name='Other private guest', check_in=self.start,
            check_out=self.start+timedelta(days=1))
        GuestConversationMessage.objects.create(reservation=other, hut=self.hut,
            sender='guest', delivery='received', body='OTHER-PRIVATE-MESSAGE')
        page = self.client.get(self.url)
        self.assertContains(page, '&lt;script&gt;unsafe()&lt;/script&gt;')
        self.assertNotContains(page, '<script>unsafe()</script>')
        self.assertContains(page, 'Approval does not update the booking automatically.')
        self.assertContains(page, 'Your room is ready.')
        self.assertNotContains(page, 'OTHER-PRIVATE-MESSAGE')
