"""Deposit lifecycle integration tests; all money and guests are synthetic."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import (Hut, Room, Bed, BedClosure, HutDepositPolicy, Reservation,
                     ReservationDepositRequest as Hold, PaymentTransaction, GuestStay)
from .services import create_reservation, free_beds
from .deposit_flow_v180 import process_holds, default_terms
from .payments import payment_token
from .self_service import issue_guest_link
from .notifications_v145 import deliver_notification

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOOKING_NOTIFY_EMAIL='')
class DepositFlow180Tests(TestCase):
    def setUp(self):
        self.hut=Hut.objects.create(name='Deposit Hut',slug='deposit-hut',payment_instructions_en='Bank: TEST BANK; IBAN: TEST-ONLY',payment_instructions_bg='Банка: ТЕСТ')
        self.room=Room.objects.create(hut=self.hut,name='Dorm',capacity=4,price_per_night=20)
        self.manager=get_user_model().objects.create_user('deposit-manager',email='keeper@example.test',is_staff=True)
        self.hut.managers.add(self.manager);self.client.force_login(self.manager)
        self.start=timezone.localdate()+timedelta(days=10);self.end=self.start+timedelta(days=2)
        self.r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:2},name='Deposit Guest',email='deposit@example.test',guest_request=True,status='pending')
    def approval(self,**extra):
        due=timezone.localtime(timezone.now()+timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        data={'action':'confirm','deposit_amount':'24.00','deposit_due_at':due,'instructions_en':self.hut.payment_instructions_en,'instructions_bg':self.hut.payment_instructions_bg,**extra}
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post(reverse('bookings:manager_reservation_action',args=[self.r.code]),data)
        self.r.refresh_from_db();return response
    def pay(self,amount='24',**extra):
        url=reverse('bookings:reservation_payments',args=[self.r.code])
        data={'kind':'deposit','method':'bank','amount':amount,'recording_token':payment_token(self.r,self.manager),**extra}
        with self.captureOnCommitCallbacks(execute=True):response=self.client.post(url,data)
        self.r.refresh_from_db();return response,data
    def shift_deadline(self,delta):
        due=timezone.now()+delta
        Hold.objects.filter(pk=self.r.deposit_request_id).update(due_at=due,reminder_at=due-timedelta(hours=1))
        self.r.refresh_from_db();return due
    def capacity(self):return free_beds([self.room],self.start,self.end)[self.room.pk]
    def test_approval_holds_beds_and_sends_fixed_terms_not_confirmation(self):
        self.assertEqual(self.approval().status_code,302);self.assertEqual(self.r.status,'pending');self.assertEqual(self.capacity(),2)
        self.assertEqual(self.r.deposit_request.state,'awaiting');self.assertEqual(len(mail.outbox),1)
        body=mail.outbox[0].body
        for text in ['24.00','TEST-ONLY','Deadline','Europe/Sofia',self.r.code,'/guest/manage/']:self.assertIn(text,body)
        self.assertFalse(self.r.delivery_notifications.filter(kind__startswith='confirmation').exists())
    def test_partial_then_full_payment_confirms_once_and_has_payment_summary(self):
        self.approval();self.pay('10');self.assertEqual(self.r.status,'pending');self.pay('14');self.assertEqual(self.r.status,'confirmed')
        self.assertEqual(self.r.deposit_request.state,'paid');self.assertEqual(self.r.payment_transactions.count(),2)
        notifications=self.r.delivery_notifications.filter(kind='confirmation_guest');self.assertEqual(notifications.count(),1)
        self.assertIn('56.00',notifications.get().body)
        self.assertEqual(self.capacity(),2)
    def test_duplicate_payment_submission_does_not_add_money(self):
        self.approval();_,data=self.pay()
        self.client.post(reverse('bookings:reservation_payments',args=[self.r.code]),data)
        self.assertEqual(self.r.payment_transactions.count(),1)
    def test_invalid_or_missing_payment_token_cannot_write(self):
        self.approval()
        for token in ['', 'not-signed',payment_token(self.r,get_user_model().objects.create_user('outsider'))]:
            self.pay(recording_token=token)
        self.assertFalse(self.r.payment_transactions.exists());self.assertEqual(self.r.status,'pending')
    def test_zero_deposit_explicitly_waives_and_confirms_without_fake_money(self):
        self.approval(deposit_amount='0',deposit_due_at='',instructions_en='',instructions_bg='')
        self.assertEqual(self.r.status,'confirmed');self.assertEqual(self.r.deposit_request.state,'waived');self.assertFalse(self.r.payment_transactions.exists())
    def test_existing_payment_credit_confirms_on_approval(self):
        PaymentTransaction.objects.create(reservation=self.r,kind='deposit',method='bank',amount=24)
        self.approval(instructions_en='',instructions_bg='');self.assertEqual(self.r.status,'confirmed')
    def test_invalid_terms_preserve_bound_form_and_do_not_approve(self):
        for extra in [{'deposit_amount':'81'},{'deposit_amount':'-1'},{'deposit_due_at':'2000-01-01T12:00'},{'instructions_en':'','instructions_bg':''}]:
            response=self.approval(**extra);self.assertEqual(response.status_code,200);self.assertTrue(response.context['deposit_form'].errors)
            self.assertIsNone(self.r.deposit_request_id)
        self.assertFalse(self.r.delivery_notifications.exists())
    def test_missing_email_and_revoked_private_link_block_approval(self):
        self.r.email='';self.r.save(update_fields=['email']);self.approval();self.assertIsNone(self.r.deposit_request_id)
        self.r.email='deposit@example.test';self.r.save(update_fields=['email'])
        issue_guest_link(self.r)
        from .models import GuestAccessLink
        access=GuestAccessLink.objects.get(reservation=self.r);access.revoked_at=timezone.now();access.save(update_fields=['revoked_at'])
        self.approval();self.assertIsNone(self.r.deposit_request_id)
    def test_approval_repeat_does_not_change_terms_or_email_twice(self):
        self.approval();pk=self.r.deposit_request_id;self.approval(deposit_amount='30')
        self.assertEqual(self.r.deposit_request_id,pk);self.assertEqual(len(mail.outbox),1)
    def test_deadline_releases_capacity_before_job_and_job_cancels_once(self):
        self.approval();self.shift_deadline(timedelta(seconds=-1));self.assertEqual(self.capacity(),4)
        self.assertEqual(process_holds()['expired'],1);self.assertEqual(process_holds()['expired'],0)
        self.r.refresh_from_db();self.assertEqual(self.r.status,'cancelled');self.assertEqual(self.r.deposit_request.state,'expired')
        call_command('deliver_deposit_notifications',stdout=StringIO())
        self.assertIn('Do not send payment',mail.outbox[-1].body)
    def test_partial_payment_remains_recorded_after_expiry(self):
        self.approval();self.pay('10');self.shift_deadline(timedelta(seconds=-1));process_holds();self.r.refresh_from_db()
        self.assertEqual(self.r.status,'cancelled');self.assertEqual(self.r.payment_transactions.get().amount,Decimal('10'))
    def test_late_full_payment_records_funds_but_never_reopens_hold(self):
        self.approval();self.shift_deadline(timedelta(seconds=-1));self.pay()
        self.assertEqual(self.r.status,'cancelled');self.assertEqual(self.r.deposit_request.state,'expired');self.assertEqual(self.capacity(),4)
        self.assertFalse(self.r.delivery_notifications.filter(kind='confirmation_guest').exists())
    def test_timely_full_ledger_is_confirmed_even_if_reconciliation_runs_late(self):
        self.approval();due=self.shift_deadline(timedelta(seconds=-1))
        # Bulk insert represents a committed timely ledger waiting for reconciliation.
        PaymentTransaction.objects.bulk_create([PaymentTransaction(reservation=self.r,kind='deposit',method='bank',amount=24)])
        self.r.payment_transactions.update(created=due-timedelta(seconds=1))
        process_holds();self.r.refresh_from_db();self.assertEqual(self.r.status,'confirmed')
    def test_reminder_is_before_deadline_and_queued_once(self):
        self.approval();Hold.objects.filter(pk=self.r.deposit_request_id).update(reminder_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(process_holds()['reminders'],1);self.assertEqual(process_holds()['reminders'],0)
        reminder=self.r.delivery_notifications.get(kind='deposit_reminder_guest');self.assertEqual(reminder.status,'pending')
        deliver_notification(reminder.pk);reminder.refresh_from_db();self.assertEqual(reminder.status,'sent')
    def test_paid_or_elapsed_hold_skips_stale_payment_email(self):
        self.approval();Hold.objects.filter(pk=self.r.deposit_request_id).update(reminder_at=timezone.now()-timedelta(seconds=1));process_holds()
        item=self.r.delivery_notifications.get(kind='deposit_reminder_guest');self.pay();self.assertEqual(deliver_notification(item.pk),'skipped')
    def test_no_reminder_after_deadline_and_dry_run_has_no_writes(self):
        self.approval();self.shift_deadline(timedelta(seconds=-1));n=self.r.delivery_notifications.count()
        self.assertEqual(process_holds(dry_run=True)['expired'],1);self.r.refresh_from_db();self.assertEqual(self.r.status,'pending')
        self.assertEqual(self.r.delivery_notifications.count(),n);self.assertEqual(process_holds()['reminders'],0)
    def test_snapshot_is_immutable_and_policy_edits_do_not_reprice_it(self):
        self.approval();hold=self.r.deposit_request;hold.amount=30
        with self.assertRaises(ValidationError):hold.save()
        self.hut.payment_instructions_en='NEW BANK';self.hut.save();HutDepositPolicy.objects.create(hut=self.hut,percentage=50,due_days=1)
        self.r.refresh_from_db();self.assertEqual(self.r.deposit_request.amount,24);self.assertIn('TEST-ONLY',self.r.deposit_request.instructions_en)
    def test_approved_stay_items_and_direct_confirmation_are_guarded(self):
        self.approval();self.r.check_out+=timedelta(days=1)
        with self.assertRaises(ValidationError):self.r.save()
        item=self.r.items.get();item.beds=1
        with self.assertRaises(ValidationError):item.save()
        self.r.refresh_from_db();self.r.status='confirmed'
        with self.assertRaises(ValidationError):self.r.save()
    def test_withdrawal_preserves_funds_and_reapproval_uses_new_terms(self):
        self.approval();self.pay('10');old=self.r.deposit_request_id
        url=reverse('bookings:withdraw_deposit',args=[self.r.code])
        with self.captureOnCommitCallbacks(execute=True):self.client.post(url,{'reason':'Change payment deadline'})
        self.r.refresh_from_db();self.assertEqual(self.r.deposit_request.state,'withdrawn');self.assertEqual(self.r.status,'pending')
        self.approval(deposit_amount='10');self.assertEqual(self.r.status,'confirmed');self.assertNotEqual(old,self.r.deposit_request_id)
        self.assertEqual(self.r.deposit_requests.count(),2);self.assertEqual(self.r.payment_transactions.count(),1)
    def test_capacity_conflict_after_payment_requires_review_not_expiry(self):
        self.approval();bed=Bed.objects.create(room=self.room,number=1)
        BedClosure.objects.create(bed=bed,start=self.start,end=self.end)
        # Force a larger closure after approval without touching the held booking.
        self.room.capacity=1;self.room.save(update_fields=['capacity'])
        self.pay();self.assertEqual(self.r.deposit_request.state,'review');self.assertEqual(self.r.status,'pending')
        self.shift_deadline(timedelta(seconds=-1));process_holds();self.r.refresh_from_db();self.assertEqual(self.r.status,'pending')
        self.assertTrue(self.r.delivery_notifications.filter(kind='deposit_review_manager').exists())
    def test_paid_hold_cannot_be_undone_or_expire(self):
        self.approval();self.pay();self.shift_deadline(timedelta(seconds=-1));process_holds();self.r.refresh_from_db();self.assertEqual(self.r.status,'confirmed')
        from .staff_decisions_v152 import deposit_undo_allowed
        self.assertFalse(deposit_undo_allowed(self.r))
    def test_rollback_refuses_unresolved_holds(self):
        self.approval()
        with self.assertRaises(CommandError):call_command('check_deposit_rollback',stdout=StringIO())
        self.pay();call_command('check_deposit_rollback',stdout=StringIO())
    def test_legacy_confirmed_booking_not_enrolled_or_expired(self):
        legacy=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:1},name='Legacy')
        process_holds();legacy.refresh_from_db();self.assertEqual(legacy.status,'confirmed');self.assertIsNone(legacy.deposit_request_id)
    def test_guest_pages_show_terms_and_stop_showing_payment_after_deadline(self):
        self.approval();page=self.client.get(self.r.get_absolute_url());self.assertContains(page,'TEST-ONLY');self.assertContains(page,'Your beds are held.')
        self.assertNotContains(page,'The hut manager will email their decision.');self.assertNotContains(page,'Awaiting approval')
        self.shift_deadline(timedelta(seconds=-1));page=self.client.get(self.r.get_absolute_url());self.assertNotContains(page,'TEST-ONLY');self.assertContains(page,'Do not send payment')
    def test_approved_hold_not_in_needs_decision_counts(self):
        self.approval();page=self.client.get(reverse('bookings:dashboard'));self.assertEqual(page.context['pending_count'],0);self.assertEqual(page.context['awaiting_deposit_count'],1)
    def test_scope_csrf_and_get_do_not_record_payments_or_withdraw(self):
        self.approval();url=reverse('bookings:reservation_payments',args=[self.r.code]);other=get_user_model().objects.create_user('other',is_staff=True)
        self.client.force_login(other);self.assertEqual(self.client.post(url,{'kind':'deposit','method':'bank','amount':'24'}).status_code,403)
        self.client.force_login(self.manager);self.assertEqual(self.client.get(reverse('bookings:withdraw_deposit',args=[self.r.code])).status_code,405)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.manager);self.assertEqual(secure.post(url,{'kind':'deposit','method':'bank','amount':'24'}).status_code,403)
    def test_queued_reminder_recalculates_remainder_after_partial_payment(self):
        self.approval();Hold.objects.filter(pk=self.r.deposit_request_id).update(reminder_at=timezone.now()-timedelta(seconds=1));process_holds()
        item=self.r.delivery_notifications.get(kind='deposit_reminder_guest');self.pay('10');deliver_notification(item.pk);item.refresh_from_db()
        self.assertIn('Remaining deposit / Остатък по депозита: 14.00',item.body)
    def test_nonstaff_assigned_manager_can_record_received_deposit(self):
        self.manager.is_staff=False;self.manager.save(update_fields=['is_staff']);self.approval();self.pay();self.assertEqual(self.r.status,'confirmed')
    def test_expiry_worker_never_delivers_smtp_even_when_it_confirms_funded_hold(self):
        self.approval();PaymentTransaction.objects.bulk_create([PaymentTransaction(reservation=self.r,kind='deposit',method='bank',amount=24)])
        with patch('bookings.notifications_v145.send_mail',side_effect=AssertionError('Expiry worker must not send SMTP')):
            with self.captureOnCommitCallbacks(execute=True):process_holds()
        self.r.refresh_from_db();self.assertEqual(self.r.status,'confirmed')
        self.assertEqual(self.r.delivery_notifications.get(kind='confirmation_guest').status,'pending')
    def test_undo_positive_approval_withdraws_terms_and_partial_payment_blocks_undo(self):
        self.approval();decision=self.r.staff_decisions.latest('pk')
        self.client.post(reverse('bookings:undo_decision',args=[self.r.code,decision.pk]))
        self.r.refresh_from_db();self.assertEqual(self.r.deposit_request.state,'withdrawn');self.assertEqual(self.r.status,'pending')
        self.approval();self.pay('1')
        from .staff_decisions_v152 import deposit_undo_allowed
        self.assertFalse(deposit_undo_allowed(self.r))
    def test_checked_in_stay_is_not_freed_or_cancelled_automatically(self):
        self.approval();GuestStay.objects.create(reservation=self.r,checked_in_at=timezone.now());self.shift_deadline(timedelta(seconds=-1))
        self.assertEqual(self.capacity(),2);self.assertEqual(process_holds()['blocked'],1)
        self.r.refresh_from_db();self.assertEqual(self.r.status,'pending')
    def test_staff_cancellation_closes_approved_hold_and_skips_queued_terms(self):
        self.approval();item=self.r.delivery_notifications.get(kind='deposit_request_guest');item.status='failed';item.next_attempt_at=timezone.now();item.save()
        self.client.post(reverse('bookings:manager_reservation_action',args=[self.r.code]),{'action':'cancel','reason':'Guest cannot travel'})
        self.r.refresh_from_db();self.assertEqual(self.r.status,'cancelled');self.assertEqual(self.r.deposit_request.state,'withdrawn');self.assertEqual(deliver_notification(item.pk),'skipped')
    def test_mail_outage_retains_approval_and_retry_sends_terms_once(self):
        with patch('bookings.notifications_v145.send_mail',side_effect=OSError('Synthetic outage')):
            with self.assertLogs('bookings.notifications_v145',level='WARNING'):self.approval()
        self.assertEqual(self.r.status,'pending');item=self.r.delivery_notifications.get(kind='deposit_request_guest');self.assertEqual(item.status,'failed')
        item.next_attempt_at=timezone.now();item.save();self.assertEqual(deliver_notification(item.pk),'sent');self.assertEqual(deliver_notification(item.pk),'sent')
        self.assertEqual(len(mail.outbox),1)
    def test_queued_reminder_after_deadline_is_skipped(self):
        self.approval();Hold.objects.filter(pk=self.r.deposit_request_id).update(reminder_at=timezone.now()-timedelta(seconds=1));process_holds()
        item=self.r.delivery_notifications.get(kind='deposit_reminder_guest');self.shift_deadline(timedelta(seconds=-1));self.assertEqual(deliver_notification(item.pk),'skipped')
    def test_bulgarian_guest_sees_deposit_instructions(self):
        self.approval();self.client.cookies['django_language']='bg'
        response=self.client.get(self.r.get_absolute_url());self.assertContains(response,'Местата ти са задържани.');self.assertContains(response,'Банка: ТЕСТ')
