from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, PublicWebsiteSettings, Reservation, ReservationItem, ReservationNotification, Room
from .self_service import issue_guest_link


class ReservationPresentationV178Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut = Hut.objects.create(name='Studenets Test Hut', slug='studenets-test',
            location='Test location', public_phone='+359 888 123 456', public_email='hut@example.test',
            payment_instructions_en='Payment on arrival, as agreed.', reply_time_en='During staffed hours.')
        PublicWebsiteSettings.objects.update_or_create(pk=1, defaults={'main_hut': cls.hut})
        room = Room.objects.create(hut=cls.hut, name='Panorama dorm', capacity=8, price_per_night='18.00')
        cls.booking = Reservation.objects.create(name='Synthetic Private Guest', email='private@example.test',
            check_in=timezone.localdate()+timedelta(days=5), check_out=timezone.localdate()+timedelta(days=7),
            status='pending', guest_request=True)
        ReservationItem.objects.create(reservation=cls.booking, room=room, beds=2, price_per_night='18.00')
        cls.manager = get_user_model().objects.create_user('receipt-manager', is_staff=True)
        cls.hut.managers.add(cls.manager)
        cls.other_manager = get_user_model().objects.create_user('receipt-other-manager', is_staff=True)
        cls.receipt = cls.booking.get_absolute_url()

    def guest(self, strict=False):
        browser = Client(enforce_csrf_checks=strict)
        browser.get(issue_guest_link(self.booking))
        return browser

    def test_pending_confirmed_and_cancelled_receipts_keep_correct_meaning_and_totals(self):
        client = self.guest()
        for status, heading, label in [('pending', 'Request received.', 'Estimated total'),
                ('confirmed', 'See you in the mountains.', 'Total price'),
                ('cancelled', 'Reservation cancelled.', 'Original booking total')]:
            Reservation.objects.filter(pk=self.booking.pk).update(status=status)
            response = client.get(self.receipt)
            for text in [heading, label, '72.00', self.hut.name, 'Panorama dorm']:
                self.assertContains(response, text)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertContains(response, 'noindex, nofollow, noarchive')
            self.assertNotContains(response, 'fonts.googleapis.com')
            self.assertTemplateUsed(response, 'bookings/reservation_base_v178.html')
            if status == 'cancelled':
                self.assertNotContains(response, 'Request a change or cancellation')
                self.assertNotContains(response, 'Payment on arrival, as agreed.')

    def test_guests_have_request_links_only_before_start_and_staff_keep_authorized_forms(self):
        client = self.guest()
        page = client.get(self.receipt)
        self.assertContains(page, 'href="' + issue_guest_link(self.booking) + '"')
        self.assertNotContains(page, 'action="' + reverse('bookings:cancel', args=[self.booking.code]) + '"')
        Reservation.objects.filter(pk=self.booking.pk).update(check_in=timezone.localdate())
        self.assertNotContains(client.get(self.receipt), 'Request a change or cancellation')
        client.force_login(self.manager)
        staff = client.get(self.receipt)
        self.assertContains(staff, 'action="' + reverse('bookings:cancel', args=[self.booking.code]) + '"')
        self.assertContains(staff, 'href="' + reverse('bookings:modify', args=[self.booking.code]) + '"')
        self.assertContains(staff, 'Confirm cancellation')

    def test_recovery_does_not_expose_reservation_data_and_staff_are_hut_scoped(self):
        for account in [None, self.other_manager]:
            browser = Client()
            if account:
                browser.force_login(account)
            page = browser.get(self.receipt)
            self.assertContains(page, 'Email my private link')
            for private in [self.booking.name, self.booking.email, 'Panorama dorm', '72.00']:
                self.assertNotContains(page, private)
            self.assertIn('no-store', page['Cache-Control'])
            self.assertContains(page, 'noindex, nofollow, noarchive')

    def test_recovery_form_is_csrf_protected_and_repeated_sends_keep_the_existing_limit(self):
        browser = Client(enforce_csrf_checks=True)
        browser.get(self.receipt)
        self.assertEqual(browser.post(self.receipt).status_code, 403)
        token = browser.cookies['csrftoken'].value
        for _ in range(2):
            response = browser.post(self.receipt, {'csrfmiddlewaretoken': token})
            self.assertRedirects(response, self.receipt, fetch_redirect_response=False)
        queued = ReservationNotification.objects.filter(reservation=self.booking, kind='access_guest')
        self.assertEqual(queued.count(), 1)
        self.assertEqual(queued.get().recipient, self.booking.email)

    def test_bulgarian_switch_preserves_private_route_and_guest_session(self):
        client = self.guest(strict=True)
        client.get(self.receipt)
        response = client.post(reverse('set_language'), {'language': 'bg', 'next': self.receipt,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertRedirects(response, self.receipt, fetch_redirect_response=False)
        page = client.get(self.receipt)
        self.assertContains(page, '<html lang="bg">')
        self.assertContains(page, self.booking.name)
        self.assertContains(page, 'ДАННИ НА ГОСТА')
        self.assertContains(page, self.hut.reply_time_en)

    def test_delivery_warning_and_payment_wording_remain_honest(self):
        client = self.guest()
        with patch('bookings.notifications_v145.guest_delivery_delayed', return_value=True):
            page = client.get(self.receipt)
        self.assertContains(page, 'Email delivery is delayed.')
        self.assertContains(page, 'Booking total, not a payment receipt.')
        self.assertContains(page, self.hut.payment_instructions_en)
        self.assertContains(page, 'tel:+359888123456')

    def test_bare_r_is_a_private_read_only_guide_without_recovery_submission(self):
        page = self.client.get('/r/')
        self.assertContains(page, 'Open your private reservation link')
        self.assertContains(page, 'Open the reservation email')
        self.assertContains(page, 'noindex, nofollow, noarchive')
        self.assertNotContains(page, 'Email my private link')
        self.assertNotContains(page, self.booking.email)
        self.assertIn('no-store', page['Cache-Control'])
        self.assertEqual(self.client.head('/r/').status_code, 200)
        self.assertEqual(self.client.post('/r/').status_code, 405)
        self.assertFalse(ReservationNotification.objects.exists())
