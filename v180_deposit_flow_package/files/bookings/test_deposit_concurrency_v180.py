"""Real row-lock checks. Run with an isolated PostgreSQL test database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Event
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.db import connection, connections, close_old_connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Hut, Room, Reservation, ReservationDepositRequest, PaymentTransaction
from .services import create_reservation
from .deposit_flow_v180 import approve_deposit, expire_hold, process_holds
from .payments import payment_token

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOOKING_NOTIFY_EMAIL='')
class DepositConcurrency180Tests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL row locks; SQLite cannot verify payment/expiry races')
        self.hut=Hut.objects.create(name='PG deposit hut',slug='pg-deposit')
        self.room=Room.objects.create(hut=self.hut,name='Last bed',capacity=1,price_per_night=40)
        self.user=get_user_model().objects.create_user('pg-deposit-manager',is_staff=True)
        self.hut.managers.add(self.user)
        start=timezone.localdate()+timedelta(days=5)
        self.r=create_reservation(check_in=start,check_out=start+timedelta(days=2),beds_by_room={self.room.pk:1},name='Race guest',email='synthetic@example.test',status='pending',guest_request=True)
        req=SimpleNamespace(user=self.user,build_absolute_uri=lambda path='':'https://testserver'+path)
        with transaction.atomic():
            r=Reservation.objects.select_for_update().get(pk=self.r.pk)
            approve_deposit(req,r,{'deposit_amount':'24','deposit_due_at':timezone.localtime(timezone.now()+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),'instructions_en':'TEST BANK ONLY'})
        self.r.refresh_from_db()
    def worker(self,fn):
        close_old_connections()
        try:
            with connections['default'].cursor() as cursor:cursor.execute("SET lock_timeout = '8s'")
            return fn()
        finally:connections['default'].close()
    def test_timely_payment_commit_wins_against_waiting_expiry(self):
        entered=Event();release=Event()
        due=self.r.deposit_request.due_at
        def payment():
            with transaction.atomic():
                r=Reservation.objects.select_for_update().get(pk=self.r.pk)
                PaymentTransaction.objects.create(reservation=r,kind='deposit',method='bank',amount=24)
                entered.set();self.assertTrue(release.wait(8))
        def expiry():
            self.assertTrue(entered.wait(8));release.set()
            return process_holds(now=due+timedelta(seconds=1))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.worker,payment),pool.submit(self.worker,expiry)]
            for future in futures:future.result(timeout=15)
        self.r.refresh_from_db();self.assertEqual(self.r.status,'confirmed');self.assertEqual(self.r.deposit_request.state,'paid')
        self.assertEqual(self.r.delivery_notifications.filter(kind='confirmation_guest').count(),1)
    def test_expiry_commit_wins_and_late_payment_does_not_resurrect(self):
        ReservationDepositRequest.objects.filter(pk=self.r.deposit_request_id).update(due_at=timezone.now()-timedelta(seconds=1))
        entered=Event();release=Event()
        def expiry():
            with transaction.atomic():
                r=Reservation.objects.select_for_update().get(pk=self.r.pk)
                hold=ReservationDepositRequest.objects.select_for_update().get(pk=r.deposit_request_id)
                self.assertTrue(expire_hold(r,hold,defer_delivery=True));entered.set();self.assertTrue(release.wait(8))
        def payment():
            self.assertTrue(entered.wait(8));release.set()
            with transaction.atomic():
                r=Reservation.objects.select_for_update().get(pk=self.r.pk)
                PaymentTransaction.objects.create(reservation=r,kind='deposit',method='bank',amount=24)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.worker,expiry),pool.submit(self.worker,payment)]
            for future in futures:future.result(timeout=15)
        self.r.refresh_from_db();self.assertEqual(self.r.status,'cancelled');self.assertEqual(self.r.payment_transactions.get().amount,Decimal('24'))
        self.assertFalse(self.r.delivery_notifications.filter(kind='confirmation_guest').exists())
    def test_simultaneous_replay_of_payment_form_adds_one_ledger_entry(self):
        from threading import Barrier
        gate=Barrier(2,timeout=8)
        token=payment_token(self.r,self.user)
        def payment():
            client=Client();client.force_login(self.user);gate.wait()
            return client.post(reverse('bookings:reservation_payments',args=[self.r.code]),{'kind':'deposit','method':'bank','amount':'24','recording_token':token}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.worker,payment),pool.submit(self.worker,payment)]
            self.assertEqual([f.result(timeout=15) for f in futures],[302,302])
        self.assertEqual(self.r.payment_transactions.count(),1);self.r.refresh_from_db();self.assertEqual(self.r.status,'confirmed')
