"""Regression and authorization tests for the public request review queue."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room
from .services import free_beds


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ApprovalDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username='approval-manager', email='manager@example.com', password='test')
        self.other_manager = User.objects.create_user(username='approval-other', password='test')
        self.unassigned = User.objects.create_user(username='approval-unassigned', password='test', is_staff=True)
        self.admin = User.objects.create_superuser(username='approval-admin', email='admin@example.com', password='test')
        self.hut = Hut.objects.create(name='Approval Hut', slug='approval-hut')
        self.other_hut = Hut.objects.create(name='Hidden Hut', slug='hidden-hut')
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other_manager)
        self.room = Room.objects.create(hut=self.hut, name='Dorm', capacity=4, price_per_night=Decimal('20.00'))
        self.other_room = Room.objects.create(hut=self.other_hut, name='Private', capacity=3, price_per_night=Decimal('30.00'))
        self.start = timezone.localdate() + timedelta(days=6)
        self.url = reverse('bookings:approval_dashboard')

    def make_request(self, room=None, name='Pending Guest', status=Reservation.Status.PENDING, guest_request=True):
        room = room or self.room
        reservation = Reservation.objects.create(
            name=name, email='guest@example.com', phone='123456', notes='Vegetarian meal',
            check_in=self.start, check_out=self.start + timedelta(days=2),
            status=status, guest_request=guest_request,
        )
        ReservationItem.objects.create(reservation=reservation, room=room, beds=2, price_per_night=room.price_per_night)
        return reservation

    def test_anonymous_redirects_to_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_unassigned_user_is_forbidden(self):
        self.client.force_login(self.unassigned)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_manager_only_sees_assigned_hut(self):
        own = self.make_request(name='Own Pending')
        self.make_request(self.other_room, name='Secret Pending')
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own.name)
        self.assertNotContains(response, 'Secret Pending')
        self.assertContains(response, 'Vegetarian meal')
        self.assertContains(response, '80.00')
        self.assertContains(response, 'Approve')
        self.assertContains(response, 'Decline')
        self.assertEqual(response.context['counts']['pending'], 1)
        self.assertEqual(self.client.get(self.url, {'hut': self.other_hut.slug}).status_code, 404)

    def test_staff_reservations_excluded_from_public_queue(self):
        self.make_request(name='Public Pending')
        self.make_request(name='Staff Pending', guest_request=False)
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertContains(response, 'Public Pending')
        self.assertNotContains(response, 'Staff Pending')

    def test_status_tabs_and_search(self):
        self.make_request(name='Waiting Guest')
        self.make_request(name='Approved Guest', status=Reservation.Status.CONFIRMED)
        self.make_request(name='Declined Guest', status=Reservation.Status.CANCELLED)
        self.client.force_login(self.manager)
        pending = self.client.get(self.url)
        self.assertContains(pending, 'Waiting Guest')
        self.assertNotContains(pending, 'Approved Guest')
        self.assertEqual(pending.context['counts'], {'pending': 1, 'confirmed': 1, 'cancelled': 1})
        approved = self.client.get(self.url, {'status': 'confirmed', 'q': 'Approved'})
        self.assertContains(approved, 'Approved Guest')
        self.assertNotContains(approved, 'Waiting Guest')
        self.assertContains(self.client.get(self.url, {'status': 'cancelled'}), 'Declined Guest')

    def test_approval_from_queue_confirms_and_sends_email(self):
        reservation = self.make_request()
        self.client.force_login(self.manager)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('bookings:manager_reservation_action', args=[reservation.code]),
                {'action': 'confirm', 'source': 'approvals'},
            )
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        self.assertTrue(any('guest@example.com' in message.to for message in mail.outbox))

    def test_decline_from_queue_releases_beds_and_sends_email(self):
        reservation = self.make_request()
        self.client.force_login(self.manager)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('bookings:manager_reservation_action', args=[reservation.code]),
                {'action': 'cancel', 'source': 'approvals'},
            )
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)
        self.assertEqual(free_beds([self.room], self.start, self.start + timedelta(days=2))[self.room.pk], 4)
        self.assertTrue(any('declined' in message.subject.lower() for message in mail.outbox))

    def test_other_hut_approval_still_forbidden(self):
        reservation = self.make_request(self.other_room, name='Other Request')
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('bookings:manager_reservation_action', args=[reservation.code]),
            {'action': 'confirm', 'source': 'approvals'},
        )
        self.assertEqual(response.status_code, 404)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_superuser_can_filter_by_hut(self):
        self.make_request(name='Hut A')
        self.make_request(self.other_room, name='Hut B')
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {'hut': self.other_hut.slug})
        self.assertContains(response, 'Hut B')
        self.assertNotContains(response, 'Hut A')

    def test_mixed_hut_request_not_actionable_for_manager(self):
        reservation = self.make_request(name='Mixed Request')
        ReservationItem.objects.create(reservation=reservation, room=self.other_room, beds=1, price_per_night=Decimal('30.00'))
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Mixed Request')
