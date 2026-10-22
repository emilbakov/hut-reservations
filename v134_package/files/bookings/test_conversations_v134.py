"""Targeted v134 permissions, guest messaging, email, quick replies and UI tests."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .conversations_v134 import render_reply
from .models import (GuestAccessLink, GuestConversationMessage, GuestMessageLog,
                     Hut, HutQuickReply, Reservation, ReservationItem, Room)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConversationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('v134_manager', password='secret', is_staff=True)
        self.outsider = User.objects.create_user('v134_other', password='secret', is_staff=True)
        self.guest_user = User.objects.create_user('v134_guest', password='secret')
        self.hut = Hut.objects.create(name='Test Hut', slug='test-v134')
        self.other_hut = Hut.objects.create(name='Other Hut', slug='other-v134')
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.outsider)
        room = Room.objects.create(hut=self.hut, name='A', capacity=4)
        other_room = Room.objects.create(hut=self.other_hut, name='B', capacity=4)
        today = timezone.localdate()
        self.res = Reservation.objects.create(
            name='Test Guest', email='guest@example.org',
            check_in=today + timedelta(days=5), check_out=today + timedelta(days=6))
        ReservationItem.objects.create(reservation=self.res, room=room, beds=1,
                                       price_per_night=Decimal('30.00'))
        self.other_res = Reservation.objects.create(
            name='Other Guest', email='other@example.org',
            check_in=today + timedelta(days=5), check_out=today + timedelta(days=6))
        ReservationItem.objects.create(reservation=self.other_res, room=other_room, beds=1,
                                       price_per_night=Decimal('30.00'))
        self.link = GuestAccessLink.objects.create(reservation=self.res)
        self.thread = reverse('bookings:conversation_thread', args=[self.res.code])
        self.guest_url = reverse('bookings:guest_self_service', args=[self.link.token])
        self.guest_post = reverse('bookings:guest_send_message', args=[self.link.token])

    def test_manager_can_open_thread_and_mobile_form(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.thread)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Communication timeline')
        self.assertContains(response, 'Quick reply')
        self.assertContains(response, 'Send email copy')

    def test_manager_send_email_copy(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.thread, {'subject': 'Hi {guest}', 'body': 'Welcome to {hut}', 'send_email': 'on'})
        self.assertRedirects(response, self.thread)
        item = GuestConversationMessage.objects.get()
        self.assertEqual(item.delivery, 'sent')
        self.assertEqual(item.sent_by, self.manager)
        self.assertEqual(item.subject, 'Hi Test Guest')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['guest@example.org'])
        self.assertIn('Test Hut', mail.outbox[0].body)

    def test_manager_in_app_only(self):
        self.client.force_login(self.manager)
        self.client.post(self.thread, {'subject': 'Question', 'body': 'Hello'})
        self.assertEqual(GuestConversationMessage.objects.get().delivery, 'in_app')
        self.assertEqual(len(mail.outbox), 0)
        self.client.logout()
        self.assertContains(self.client.get(self.guest_url), 'Hello')

    def test_smtp_failure_is_visible_in_app_and_logged(self):
        self.client.force_login(self.manager)
        with patch('bookings.conversations_v134.send_mail', side_effect=OSError('SMTP unavailable')):
            self.client.post(self.thread, {'subject': 'Hello', 'body': 'Try again', 'send_email': 'on'})
        item = GuestConversationMessage.objects.get()
        self.assertEqual(item.delivery, 'failed')
        self.assertEqual(item.error, 'OSError')
        self.client.logout()
        self.assertContains(self.client.get(self.guest_url), 'Try again')

    def test_outsider_cannot_read_or_send(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.thread).status_code, 404)
        self.assertEqual(self.client.post(self.thread, {'subject': 'Bad', 'body': 'Bad'}).status_code, 404)
        self.assertEqual(GuestConversationMessage.objects.count(), 0)

    def test_nonstaff_cannot_open_thread(self):
        self.client.force_login(self.guest_user)
        self.assertNotEqual(self.client.get(self.thread).status_code, 200)

    def test_inbox_scoped_to_manager(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('bookings:conversation_inbox'))
        self.assertContains(response, self.res.code)
        self.assertNotContains(response, self.other_res.code)
        response = self.client.get(reverse('bookings:conversation_inbox') + '?hut=' + self.other_hut.slug)
        self.assertEqual(response.status_code, 404)

    def test_guest_can_send_without_logging_in(self):
        response = self.client.post(self.guest_post, {'body': 'Can we arrive late?'})
        self.assertRedirects(response, self.guest_url)
        entry = GuestConversationMessage.objects.get()
        self.assertEqual(entry.sender, 'guest')
        self.assertEqual(entry.delivery, 'received')
        self.assertEqual(len(mail.outbox), 0)
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.thread), 'Can we arrive late?')

    def test_guest_cannot_send_to_other_reservation(self):
        self.client.post(self.guest_post, {'body': 'Only my booking'})
        self.assertEqual(GuestConversationMessage.objects.get().reservation_id, self.res.pk)
        self.assertNotContains(self.client.get(self.guest_url), 'Other Guest')

    def test_revoked_guest_link_rejected(self):
        self.link.revoked_at = timezone.now()
        self.link.save(update_fields=['revoked_at'])
        self.assertEqual(self.client.post(self.guest_post, {'body': 'No'}).status_code, 404)
        self.assertFalse(GuestConversationMessage.objects.exists())

    def test_guest_rate_limit(self):
        for n in range(5):
            self.assertEqual(self.client.post(self.guest_post, {'body': f'Note {n}'}).status_code, 302)
        self.client.post(self.guest_post, {'body': 'Sixth'})
        self.assertEqual(GuestConversationMessage.objects.count(), 5)

    def test_guest_blank_or_oversize_rejected(self):
        self.client.post(self.guest_post, {'body': ' '})
        self.client.post(self.guest_post, {'body': 'a' * 2001})
        self.assertFalse(GuestConversationMessage.objects.exists())

    def test_guest_message_window(self):
        self.res.check_in = timezone.localdate() - timedelta(days=30)
        self.res.check_out = timezone.localdate() - timedelta(days=29)
        self.res.save(update_fields=['check_in', 'check_out'])
        self.client.post(self.guest_post, {'body': 'Old'})
        self.assertFalse(GuestConversationMessage.objects.exists())

    def test_html_escaped_in_guest_and_staff_thread(self):
        self.client.post(self.guest_post, {'body': '<script>alert(1)</script>'})
        self.assertNotContains(self.client.get(self.guest_url), '<script>alert(1)</script>', html=False)
        self.client.force_login(self.manager)
        self.assertNotContains(self.client.get(self.thread), '<script>alert(1)</script>', html=False)

    def test_custom_reply_saved_and_used(self):
        self.client.force_login(self.manager)
        url = reverse('bookings:quick_replies')
        response = self.client.post(url + '?hut=' + self.hut.slug, {
            'hut_id': self.hut.pk, 'title': 'Meetup', 'subject': 'Hello {guest}',
            'body': 'Meet at {hut} on {check_in}', 'enabled': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(HutQuickReply.objects.count(), 1)
        self.assertContains(self.client.get(self.thread), 'Meetup')
        self.assertContains(self.client.get(self.thread), 'Meet at Test Hut')

    def test_custom_reply_can_be_disabled(self):
        self.client.force_login(self.manager)
        reply = HutQuickReply.objects.create(hut=self.hut, title='Meeting', subject='Hello', body='See you')
        url = reverse('bookings:quick_replies') + '?hut=' + self.hut.slug
        self.client.post(url, {'hut_id': self.hut.pk, 'reply_id': reply.pk, 'title': 'Meeting',
                               'subject': 'Hello', 'body': 'See you'})
        reply.refresh_from_db()
        self.assertFalse(reply.enabled)
        self.assertNotContains(self.client.get(self.thread), 'Meeting')

    def test_other_hut_reply_not_editable(self):
        self.client.force_login(self.manager)
        reply = HutQuickReply.objects.create(hut=self.other_hut, title='Secret', subject='Secret', body='Secret')
        url = reverse('bookings:quick_replies')
        self.assertEqual(self.client.post(url, {'hut_id': self.other_hut.pk, 'reply_id': reply.pk,
                                               'title': 'Changed', 'subject': 'Changed', 'body': 'Changed'}).status_code, 404)
        self.assertEqual(HutQuickReply.objects.get(pk=reply.pk).title, 'Secret')

    def test_reject_unsafe_placeholders_and_subject_newlines(self):
        with self.assertRaises(ValueError):
            render_reply('{guest.__class__}', 'body', self.res, self.hut)
        with self.assertRaises(ValueError):
            render_reply('Hello\nBCC: bad', 'body', self.res, self.hut)
        self.client.force_login(self.manager)
        self.client.post(self.thread, {'subject': '{guest.__class__}', 'body': 'Bad'})
        self.assertFalse(GuestConversationMessage.objects.exists())

    def test_automatic_logs_appear_in_staff_timeline(self):
        GuestMessageLog.objects.create(reservation=self.res, hut=self.hut,
            message_type='prearrival', event_date=timezone.localdate(),
            recipient=self.res.email, subject='Pre-arrival', status='sent')
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.thread), 'Pre-arrival')

    def test_existing_communication_and_reservation_pages_link_to_inbox(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse('bookings:communications_dashboard')), 'Open guest inbox')
        self.assertContains(self.client.get(reverse('bookings:manager_reservations')), 'Messages')

    def test_post_is_csrf_protected(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.guest_post, {'body': 'No csrf'}).status_code, 403)
