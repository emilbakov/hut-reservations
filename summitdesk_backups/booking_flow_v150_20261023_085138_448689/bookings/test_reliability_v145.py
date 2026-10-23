"""Regression coverage for revoked access, review, idempotency and delivery."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (GuestAccessLink, GuestChangeRequest, Hut, PublicBookingSubmission,
                     Reservation, ReservationNotification, Room)
from .notifications_v145 import deliver_notification, queue_notification
from .self_service import issue_guest_link
from .services import create_reservation, free_beds


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOOKING_NOTIFY_EMAIL='')
class ReliabilityV145Tests(TestCase):
    def setUp(self):
        self.start = timezone.localdate() + timedelta(days=8)
        self.end = self.start + timedelta(days=2)
        self.hut = Hut.objects.create(name='Reliability Hut', slug='reliability-hut')
        self.room = Room.objects.create(hut=self.hut, name='Last bed', capacity=1, price_per_night=Decimal('25.50'))
        self.manager = get_user_model().objects.create_user('reliability-manager', email='manager@example.com', is_staff=True)
        self.hut.managers.add(self.manager)
        self.url = reverse('bookings:hut_detail', args=[self.hut.slug])

    def payload(self, **extra):
        return {'check_in':self.start.isoformat(), 'check_out':self.end.isoformat(),
                'name':'Private Test Guest', 'email':'private@example.com',
                f'room_{self.room.pk}':'1', **extra}

    def submit(self, *, execute=True, client=None, **extra):
        with self.captureOnCommitCallbacks(execute=execute):
            return (client or self.client).post(self.url, self.payload(**extra))

    def reserve(self):
        return create_reservation(check_in=self.start, check_out=self.end,
            beds_by_room={self.room.pk:1}, name='Private Test Guest', email='private@example.com')

    def test_reference_alone_shows_recovery_without_guest_details_or_cache(self):
        r=self.reserve()
        response=self.client.get(r.get_absolute_url())
        self.assertContains(response, 'Email my private link')
        self.assertNotContains(response, r.name)
        self.assertNotContains(response, r.email)
        self.assertIn('no-store', response['Cache-Control'])

    def test_reference_alone_cannot_change_or_cancel(self):
        r=self.reserve()
        self.assertEqual(self.client.post(reverse('bookings:modify',args=[r.code]),self.payload()).status_code,404)
        self.assertEqual(self.client.post(reverse('bookings:cancel',args=[r.code])).status_code,404)
        r.refresh_from_db();self.assertEqual(r.status,'confirmed');self.assertEqual(r.check_in,self.start)

    def test_creator_has_revocable_access(self):
        self.submit();r=Reservation.objects.get()
        self.assertContains(self.client.get(r.get_absolute_url()), 'Awaiting hut approval')
        GuestAccessLink.objects.filter(reservation=r).update(revoked_at=timezone.now())
        response=self.client.get(r.get_absolute_url())
        self.assertNotContains(response,r.email)
        self.assertEqual(self.client.post(reverse('bookings:cancel',args=[r.code])).status_code,404)

    def test_revocation_blocks_portal_and_new_recovery_emails(self):
        r=self.reserve();url=issue_guest_link(r)
        access=GuestAccessLink.objects.get(reservation=r);access.revoked_at=timezone.now();access.save()
        self.assertEqual(self.client.get(url).status_code,404)
        with self.captureOnCommitCallbacks(execute=True):self.client.post(r.get_absolute_url())
        self.assertFalse(ReservationNotification.objects.exists())
        access.refresh_from_db();self.assertIsNotNone(access.revoked_at)
        with self.assertRaises(PermissionDenied):issue_guest_link(r)

    def test_portal_rotation_does_not_upgrade_a_stale_grant(self):
        r=self.reserve();old=GuestAccessLink.objects.get_or_create(reservation=r)[0].token
        GuestAccessLink.objects.filter(reservation=r).update(token='new-private-token-with-sufficient-test-length')
        from .reliability_v145 import grant_guest_access
        request=self.client.get('/').wsgi_request
        grant_guest_access(request,r,token=old)
        self.assertFalse(request.session.get('sd145_guest_grants'))

    def test_guest_legacy_actions_redirect_to_review_without_mutating(self):
        self.submit();r=Reservation.objects.get()
        portal=reverse('bookings:guest_self_service',args=[r.guest_access_link.token]) if hasattr(r,'guest_access_link') else issue_guest_link(r)
        response=self.client.post(reverse('bookings:modify',args=[r.code]), self.payload(check_in=(self.start+timedelta(days=1)).isoformat()))
        self.assertEqual(response.status_code,302);self.assertEqual(response.url,portal)
        self.client.post(reverse('bookings:cancel',args=[r.code]))
        r.refresh_from_db();self.assertEqual(r.check_in,self.start);self.assertEqual(r.status,'pending')
        self.assertEqual(GuestChangeRequest.objects.count(),0)
        self.assertEqual(free_beds([self.room],self.start,self.end)[self.room.pk],0)

    def test_secure_guest_cancellation_creates_review_request_only(self):
        self.submit();r=Reservation.objects.get();portal=issue_guest_link(r)
        response=self.client.post(portal,{'request_type':'cancellation','details':'Please cancel'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(GuestChangeRequest.objects.get().request_type,'cancellation')
        r.refresh_from_db();self.assertEqual(r.status,'pending')

    def test_unassigned_staff_cannot_access_private_reference(self):
        r=self.reserve();other=get_user_model().objects.create_user('outside',is_staff=True)
        self.client.force_login(other)
        self.assertNotContains(self.client.get(r.get_absolute_url()),r.email)
        self.assertEqual(self.client.post(reverse('bookings:cancel',args=[r.code])).status_code,404)

    def test_assigned_manager_retains_authorized_detail_access(self):
        r=self.reserve();self.client.force_login(self.manager)
        response=self.client.get(r.get_absolute_url())
        self.assertContains(response,r.email);self.assertNotContains(response,'/guest/manage/')
        self.assertIn('no-store',response['Cache-Control'])

    def test_recovery_sends_only_to_guest_and_throttles_across_repeats(self):
        r=self.reserve()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(r.get_absolute_url());self.client.post(r.get_absolute_url())
        self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,[r.email])
        self.assertIn('/guest/manage/',mail.outbox[0].body)
        self.assertNotContains(self.client.get(r.get_absolute_url()),GuestAccessLink.objects.get(reservation=r).token)

    def test_recovery_requires_csrf(self):
        r=self.reserve();client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(r.get_absolute_url()).status_code,403)
        self.assertFalse(ReservationNotification.objects.exists())

    def test_duplicate_submission_returns_original_even_when_last_bed_taken(self):
        self.client.get(self.url)
        first=self.submit();second=self.submit()
        self.assertEqual(first.status_code,302);self.assertEqual(second.url,first.url)
        self.assertEqual(Reservation.objects.count(),1)
        self.assertEqual(PublicBookingSubmission.objects.count(),1)
        self.assertEqual(ReservationNotification.objects.count(),2)
        self.assertEqual(len(mail.outbox),2)

    def test_signed_form_replay_is_idempotent(self):
        page=self.client.get(self.url)
        token=page.context['submission_token']
        first=self.submit(submission_token=token);second=self.submit(submission_token=token)
        self.assertEqual(first.url,second.url);self.assertEqual(Reservation.objects.count(),1)

    def test_signed_form_cannot_be_used_by_different_browser(self):
        token=self.client.get(self.url).context['submission_token']
        response=self.submit(client=Client(),submission_token=token)
        self.assertContains(response,'form has expired');self.assertFalse(Reservation.objects.exists())

    def test_tampered_token_rejected(self):
        token=self.client.get(self.url).context['submission_token']
        response=self.submit(submission_token=token+'x')
        self.assertContains(response,'form has expired');self.assertFalse(Reservation.objects.exists())

    def test_reusing_nonce_for_different_details_does_not_create_another_booking(self):
        token=self.client.get(self.url).context['submission_token']
        self.submit(submission_token=token)
        response=self.submit(submission_token=token,name='Changed name')
        self.assertContains(response,'already submitted different details')
        self.assertEqual(Reservation.objects.count(),1)

    def test_browser_receipt_does_not_grant_another_reservation(self):
        self.submit();r=Reservation.objects.get()
        stranger=Client();response=stranger.get(r.get_absolute_url())
        self.assertNotContains(response,r.email)

    def test_notifications_wait_for_commit_and_rollback_removes_them(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.client.post(self.url,self.payload())
        self.assertEqual(len(callbacks),2);self.assertEqual(len(mail.outbox),0)
        self.assertEqual(ReservationNotification.objects.filter(status='pending').count(),2)
        other=Room.objects.create(hut=self.hut,name='Other',capacity=1)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={other.pk:1},name='Rolled back')
                queue_notification(r,'request_guest','Receipt','Body','rollback@example.com')
                raise RuntimeError('rollback')
        self.assertFalse(Reservation.objects.filter(name='Rolled back').exists())
        self.assertFalse(ReservationNotification.objects.filter(recipient='rollback@example.com').exists())

    def fail_notifications(self):
        with patch('bookings.notifications_v145.send_mail',side_effect=RuntimeError('secret SMTP credentials must not appear')):
            self.submit()
        return Reservation.objects.get()

    def test_smtp_failure_keeps_booking_and_records_safe_visible_status(self):
        r=self.fail_notifications()
        self.assertEqual(r.status,'pending')
        self.assertEqual(ReservationNotification.objects.filter(status='failed').count(),2)
        self.assertContains(self.client.get(r.get_absolute_url()),'Email delivery is delayed')
        self.assertFalse(ReservationNotification.objects.filter(last_error__contains='credentials').exists())
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse('bookings:approval_dashboard')),'email notifications failed')

    def test_failed_notification_manual_retry_is_scoped_and_sent_once(self):
        r=self.fail_notifications();item=r.delivery_notifications.get(kind='request_guest')
        self.client.force_login(self.manager)
        url=reverse('bookings:notification_deliveries')
        self.client.post(url,{'notification_id':item.pk,'action':'retry'})
        self.client.post(url,{'notification_id':item.pk,'action':'retry'})
        item.refresh_from_db();self.assertEqual(item.status,'sent');self.assertEqual(item.attempts,2)
        self.assertEqual(len(mail.outbox),1)
        other=get_user_model().objects.create_user('outsider',is_staff=True)
        other_hut=Hut.objects.create(name='Elsewhere',slug='elsewhere');other_hut.managers.add(other)
        self.client.force_login(other)
        self.assertEqual(self.client.post(url,{'notification_id':item.pk,'action':'retry'}).status_code,404)

    def test_delivery_page_hides_bodies_and_tokens(self):
        r=self.fail_notifications();token=GuestAccessLink.objects.get(reservation=r).token
        self.client.force_login(self.manager)
        response=self.client.get(reverse('bookings:notification_deliveries'))
        self.assertContains(response,'Failed');self.assertNotContains(response,token)
        self.assertNotContains(response,'SMTP credentials');self.assertIn('no-store',response['Cache-Control'])

    def test_manual_retry_requires_csrf(self):
        r=self.fail_notifications();client=Client(enforce_csrf_checks=True);client.force_login(self.manager)
        self.assertEqual(client.post(reverse('bookings:notification_deliveries'),{'notification_id':r.delivery_notifications.first().pk,'action':'retry'}).status_code,403)

    def test_automatic_retry_is_due_only_and_dry_run_is_safe(self):
        r=self.fail_notifications();item=r.delivery_notifications.get(kind='request_guest')
        call_command('retry_reservation_notifications',apply=True,verbosity=0)
        self.assertEqual(len(mail.outbox),0)
        ReservationNotification.objects.filter(pk=item.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        call_command('retry_reservation_notifications',verbosity=0)
        self.assertEqual(len(mail.outbox),0)
        call_command('retry_reservation_notifications',apply=True,verbosity=0)
        self.assertEqual(len(mail.outbox),1)

    def test_automatic_attempt_limit_and_manual_retry(self):
        r=self.fail_notifications();item=r.delivery_notifications.get(kind='request_guest')
        ReservationNotification.objects.filter(pk=item.pk).update(attempts=5,next_attempt_at=timezone.now()-timedelta(days=1))
        self.assertEqual(deliver_notification(item.pk),'failed');self.assertEqual(len(mail.outbox),0)
        self.assertEqual(deliver_notification(item.pk,manual=True),'sent');self.assertEqual(len(mail.outbox),1)

    def test_retry_does_not_email_revoked_link_or_reactivate_it(self):
        r=self.fail_notifications();item=r.delivery_notifications.get(kind='request_guest')
        GuestAccessLink.objects.filter(reservation=r).update(revoked_at=timezone.now())
        self.assertEqual(deliver_notification(item.pk,manual=True),'skipped')
        self.assertEqual(len(mail.outbox),0)
        self.assertIsNotNone(GuestAccessLink.objects.get(reservation=r).revoked_at)

    def test_retry_uses_reissued_token(self):
        r=self.fail_notifications();item=r.delivery_notifications.get(kind='request_guest')
        access=GuestAccessLink.objects.get(reservation=r);old=access.token
        access.token='reissued-token-for-reliability-regression-test';access.save()
        self.assertEqual(deliver_notification(item.pk,manual=True),'sent')
        self.assertIn(access.token,mail.outbox[0].body);self.assertNotIn(old,mail.outbox[0].body)

    def test_guest_private_link_not_in_manager_email(self):
        self.submit();r=Reservation.objects.get();token=GuestAccessLink.objects.get(reservation=r).token
        guest=next(m for m in mail.outbox if m.to==[r.email])
        manager=next(m for m in mail.outbox if m.to==[self.manager.email])
        self.assertIn(token,guest.body);self.assertNotIn(token,manager.body)

    def test_email_backend_not_accepting_message_is_failure(self):
        with patch('bookings.notifications_v145.send_mail',return_value=0):self.submit()
        self.assertEqual(ReservationNotification.objects.filter(status='failed').count(),2)

    def test_approval_supersedes_failed_request_receipts(self):
        r=self.fail_notifications();self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('bookings:manager_reservation_action',args=[r.code]),{'action':'confirm'})
        self.assertEqual(r.delivery_notifications.filter(kind__startswith='request_',status='skipped').count(),2)
        self.assertEqual(r.delivery_notifications.filter(kind='confirmation_guest',status='sent').count(),1)

    @override_settings(DEBUG=False,EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_does_not_claim_real_production_delivery(self):
        self.submit()
        self.assertEqual(ReservationNotification.objects.filter(status='failed').count(),2)

    def test_different_intent_with_new_form_can_create_another_request(self):
        self.room.capacity=2;self.room.save()
        first=self.client.get(self.url).context['submission_token']
        self.submit(submission_token=first)
        second=self.client.get(self.url).context['submission_token']
        self.submit(submission_token=second)
        self.assertEqual(Reservation.objects.count(),2)

    def test_notification_creation_failure_rolls_back_booking_and_submission(self):
        with patch('bookings.notifications_v145.queue_notification',side_effect=RuntimeError('simulated storage failure')):
            with self.assertRaises(RuntimeError):self.submit()
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(PublicBookingSubmission.objects.exists())
        self.assertFalse(ReservationNotification.objects.exists())

    def test_duplicate_replay_after_revocation_does_not_restore_browser_access(self):
        self.submit();r=Reservation.objects.get()
        GuestAccessLink.objects.filter(reservation=r).update(revoked_at=timezone.now())
        self.submit()
        self.assertEqual(Reservation.objects.count(),1)
        self.assertNotContains(self.client.get(r.get_absolute_url()),r.email)

    def test_private_portal_clearly_states_pending_approval(self):
        self.submit();r=Reservation.objects.get()
        response=self.client.get(issue_guest_link(r))
        self.assertContains(response,'Awaiting hut approval')
        self.assertContains(response,'not confirmed until')


from django.test import TransactionTestCase
from django.db import connection, close_old_connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class PostgreSQLIdempotencyV145Tests(TransactionTestCase):
    def test_concurrent_replay_takes_last_bed_once(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL row locking and independent database connections')
        hut=Hut.objects.create(name='Concurrent request hut',slug='concurrent-request-hut')
        room=Room.objects.create(hut=hut,name='Last bed',capacity=1,price_per_night=25)
        start=timezone.localdate()+timedelta(days=8)
        url=reverse('bookings:hut_detail',args=[hut.slug])
        browser=Client();token=browser.get(url).context['submission_token']
        cookies=browser.cookies.copy()
        payload={'check_in':start.isoformat(),'check_out':(start+timedelta(days=2)).isoformat(),
                 'name':'Concurrent guest','email':'concurrent@example.com',f'room_{room.pk}':'1','submission_token':token}
        barrier=Barrier(2,timeout=15)
        def submit(_):
            close_old_connections()
            try:
                client=Client();client.cookies=cookies.copy()
                barrier.wait()
                response=client.post(url,payload)
                return response.status_code,response.get('Location')
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(submit,range(2)))
        self.assertEqual(outcomes[0],outcomes[1])
        self.assertEqual(outcomes[0][0],302)
        self.assertEqual(Reservation.objects.count(),1)
        self.assertEqual(PublicBookingSubmission.objects.count(),1)
