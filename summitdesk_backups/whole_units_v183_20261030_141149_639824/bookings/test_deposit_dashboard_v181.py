"""Deposit work queue: scope, immutable terms, priorities, history and no GET writes."""
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import (Hut, Room, Reservation, ReservationItem, ReservationDepositRequest as Hold,
                     PaymentTransaction, CancellationSettlement, GuestStay, ReservationNotification, HutDepositPolicy)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class DepositDashboard181Tests(TestCase):
    def setUp(self):
        self.manager=get_user_model().objects.create_user('desk181',is_staff=True)
        self.other=get_user_model().objects.create_user('other181',is_staff=True)
        self.hut=Hut.objects.create(name='Desk Hut',slug='desk181');self.hut.managers.add(self.manager)
        self.foreign=Hut.objects.create(name='Private Hut',slug='private181');self.foreign.managers.add(self.other)
        self.room=Room.objects.create(hut=self.hut,name='Dorm',capacity=200,price_per_night=20)
        self.private=Room.objects.create(hut=self.foreign,name='Secret room',capacity=200,price_per_night=20)
        self.client.force_login(self.manager);self.url=reverse('bookings:deposit_dashboard');self.now=timezone.now()
    def make(self,name='Desk guest',state='awaiting',status='pending',paid=0,hours=48,room=None,guest=True):
        r=Reservation.objects.create(name=name,email='synthetic@example.test',check_in=timezone.localdate()+timedelta(days=8),check_out=timezone.localdate()+timedelta(days=10),guest_request=guest,status='pending')
        ReservationItem.objects.create(reservation=r,room=room or self.room,beds=1,price_per_night=20)
        if state:
            hold=Hold.objects.create(reservation=r,state=state,amount=12,due_at=self.now+timedelta(hours=hours),reminder_at=self.now+timedelta(hours=hours/2),origin='https://example.test',instructions_en='Synthetic bank')
            Reservation.objects.filter(pk=r.pk).update(deposit_request=hold,status=status)
        else:Reservation.objects.filter(pk=r.pk).update(status=status)
        if paid:
            # Ledger fixture represents pre-existing received money, without triggering a transition.
            PaymentTransaction.objects.bulk_create([PaymentTransaction(reservation=r,kind='deposit',amount=paid,method='bank')])
        r.refresh_from_db();return r
    def page(self,**params):return self.client.get(self.url,params)
    def ids(self,response):return [row['reservation'].pk for row in response.context['rows']]
    def test_states_and_overlap_counts_use_fixed_approved_terms(self):
        a=self.make();b=self.make('Soon',hours=2);c=self.make('Partial',paid=4);d=self.make('Paid',state='paid',status='confirmed',paid=12)
        HutDepositPolicy.objects.create(hut=self.hut,percentage=90,due_days=20)
        page=self.page();counts=page.context['counts'];self.assertEqual(counts['awaiting'],3);self.assertEqual(counts['soon'],1);self.assertEqual(counts['partial'],1);self.assertEqual(counts['received'],1)
        self.assertNotIn(d.pk,self.ids(page));self.assertEqual(set(self.ids(self.page(state='partial'))),{c.pk})
        row=self.page(state='partial').context['rows'][0];self.assertEqual(row['target'],12);self.assertEqual(row['remaining'],8)
    def test_expired_with_funds_and_paid_capacity_review_remain_visible(self):
        expired=self.make('Expired funds',state='expired',status='cancelled',paid=4,hours=-1)
        review=self.make('Room review',state='review',paid=12)
        page=self.page(state='review');self.assertEqual(set(self.ids(page)),{expired.pk,review.pk})
        self.assertContains(page,'Expired or cancelled with recorded funds');self.assertContains(page,'Review payments');self.assertNotContains(page,'Record received payment')
    def test_closed_refunded_and_settled_records_remain_in_history(self):
        r=self.make(state='expired',status='cancelled',paid=4)
        PaymentTransaction.objects.bulk_create([PaymentTransaction(reservation=r,kind='refund',method='bank',amount=4)])
        self.assertEqual(self.ids(self.page(state='closed')),[r.pk]);self.assertEqual(self.page().context['counts']['review'],0)
        self.assertContains(self.page(state='closed'),f'/staff/reservations/{r.code}/payments/#payment-history')
    def test_retention_settlement_resolves_review_but_later_funds_reopen_attention(self):
        r=self.make(state='expired',status='cancelled',paid=4)
        CancellationSettlement.objects.create(reservation=r,outcome='retain',net_received_at_cancellation=4,retained_at_cancellation=4)
        self.assertEqual(self.ids(self.page(state='review')),[]);self.assertEqual(self.ids(self.page(state='closed')),[r.pk])
        PaymentTransaction.objects.bulk_create([PaymentTransaction(reservation=r,kind='deposit',method='bank',amount=2)])
        self.assertEqual(self.ids(self.page(state='review')),[r.pk])
    def test_unapproved_and_withdrawn_requests_do_not_get_invented_deadlines(self):
        self.make(state=None);self.make(state='withdrawn');credited=self.make('Preapproval credit',state=None,paid=3)
        page=self.page(state='all');self.assertEqual(self.ids(page),[credited.pk]);row=page.context['rows'][0]
        self.assertIsNone(row['target']);self.assertIsNone(row['due_at']);self.assertTrue(row['flags']['review'])
    def test_legacy_bookings_preserve_policy_calculation_and_mark_legacy(self):
        r=self.make(state=None,status='confirmed',guest=False,paid=2)
        row=self.page(state='legacy').context['rows'][0];self.assertEqual(row['target'],12);self.assertEqual(row['remaining'],10);self.assertTrue(row['legacy'])
        self.assertContains(self.page(state='legacy'),'no automatic hold release')
    def test_foreign_and_mixed_hut_records_do_not_leak(self):
        self.make('Other secret',room=self.private)
        r=self.make('Mixed secret',state=None,guest=False)
        ReservationItem.objects.create(reservation=r,room=self.private,beds=1,price_per_night=20)
        page=self.page(state='all');self.assertNotContains(page,'Other secret');self.assertNotContains(page,'Mixed secret');self.assertEqual(page.context['counts']['all'],0)
        self.assertEqual(self.page(hut=self.foreign.slug).status_code,404)
    def test_search_filter_pagination_and_counts_are_consistent(self):
        for i in range(27):self.make(name=f'Match {i}')
        self.make('Not selected')
        page=self.page(q='Match',state='awaiting');self.assertEqual(page.context['counts']['all'],27);self.assertEqual(len(self.ids(page)),25)
        second=self.page(q='Match',state='awaiting',page=2);self.assertEqual(len(self.ids(second)),2)
        self.assertFalse(set(self.ids(page))&set(self.ids(second)));self.assertIn('state=awaiting',page.context['next_url']);self.assertIn('q=Match',page.context['next_url'])
    def test_deadline_boundary_is_exact_and_overdue_is_prioritized(self):
        future=self.make('Future',hours=48);late=self.make('Elapsed',hours=-1)
        page=self.page();self.assertEqual(self.ids(page)[0],late.pk);self.assertEqual(page.context['overdue_count'],1)
        self.assertEqual(self.ids(self.page(state='overdue')),[late.pk]);self.assertEqual(self.ids(self.page(state='closed')),[])
        self.assertNotContains(self.page(state='overdue'),'Record received payment')
    def test_get_does_not_release_hold_or_send_mail_or_change_ledger(self):
        r=self.make(state='awaiting',paid=4,hours=-1);before=list(Reservation.objects.values());counts=(Hold.objects.count(),PaymentTransaction.objects.count(),ReservationNotification.objects.count())
        self.page();self.assertEqual(list(Reservation.objects.values()),before);self.assertEqual((Hold.objects.count(),PaymentTransaction.objects.count(),ReservationNotification.objects.count()),counts)
    def test_history_has_real_anchor_and_money_actions_remain_on_existing_screen(self):
        r=self.make();page=self.page();self.assertContains(page,f'/staff/reservations/{r.code}/payments/#payment-entry-form')
        pay=self.client.get(reverse('bookings:reservation_payments',args=[r.code]));self.assertContains(pay,'id="payment-history"');self.assertContains(pay,'name="recording_token"')
    def test_policy_post_preserves_selected_hut_and_csrf_scope(self):
        self.hut.managers.add(self.other)
        response=self.client.post(self.url,{'hut_id':self.hut.pk,'percentage':'40','due_days':'2','reminders_enabled':'on'})
        self.assertIn('hut=desk181',response.url);self.assertEqual(HutDepositPolicy.objects.get(hut=self.hut).percentage,40)
        client=Client(enforce_csrf_checks=True);client.force_login(self.manager);self.assertEqual(client.post(self.url,{'hut_id':self.hut.pk,'percentage':40,'due_days':2}).status_code,403)
    def test_staff_scope_login_and_escaping(self):
        r=self.make(name='<script>alert(1)</script>');page=self.page();self.assertContains(page,'&lt;script&gt;');self.assertNotContains(page,'<script>alert(1)</script>')
        self.client.logout();self.assertEqual(self.page().status_code,302)
        self.client.force_login(get_user_model().objects.create_user('unassigned181',is_staff=True));self.assertEqual(self.page().status_code,403)
    def test_checked_in_overdue_hold_requires_review_without_claiming_expiry(self):
        r=self.make(hours=-1);GuestStay.objects.create(reservation=r,checked_in_at=timezone.now())
        page=self.page(state='review');self.assertEqual(self.ids(page),[r.pk]);self.assertContains(page,'Checked in; overdue hold needs review')
    def test_bulgarian_interface_and_reminder_status(self):
        r=self.make();ReservationNotification.objects.create(reservation=r,kind='deposit_reminder_guest',recipient=r.email,subject='Test',body='Test',status='failed',dedupe_key='reminder181')
        self.client.cookies['django_language']='bg';page=self.page();self.assertContains(page,'ПРОСЛЕДЯВАНЕ НА ПЛАЩАНИЯТА');self.assertContains(page,'Неуспешно изпращане на напомнянето')
    def test_query_count_does_not_grow_with_booking_count(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        self.make()
        with CaptureQueriesContext(connection) as first:self.page()
        for i in range(18):self.make(name=f'Extra {i}')
        with CaptureQueriesContext(connection) as many:self.page()
        self.assertLessEqual(len(many),len(first)+1,(len(first),len(many)))
