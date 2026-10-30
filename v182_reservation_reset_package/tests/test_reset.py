"""Synthetic database coverage. Run with Django DiscoverRunner, never production."""
import importlib.util
from pathlib import Path
from datetime import timedelta
import json
import os
import tempfile
from unittest.mock import patch
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, CHANGE
from django.db import connection, transaction, models
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from bookings.models import (Hut, Room, Bed, Reservation, ReservationItem, ReservationDepositRequest,
    PaymentTransaction, CancellationSettlement, PublicBookingSubmission, HutExpense, BedClosure,
    HutDepositPolicy, PublicWebsiteSettings, EmailSyncState, ReservationNotification, BedAssignment)
from floorplans.reservation_history import ReservationHistoryEvent
from floorplans.housekeeping_events import BedCleaningEvent
from floorplans.housekeeping_models import BedHousekeeping
spec=importlib.util.spec_from_file_location('reset182',Path(__file__).resolve().parents[1]/'reset_reservations.py')
reset=importlib.util.module_from_spec(spec);spec.loader.exec_module(reset)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ResetTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('reset-manager',is_staff=True)
        self.hut=Hut.objects.create(name='Synthetic Hut',slug='reset-test')
        self.hut.managers.add(self.user)
        self.other=Hut.objects.create(name='Other Hut',slug='reset-other')
        self.room=Room.objects.create(hut=self.hut,name='Dorm',capacity=4,price_per_night=20)
        self.bed=Bed.objects.create(room=self.room,number=1)
        self.today=timezone.localdate()
        self.r=Reservation.objects.create(name='Synthetic Guest',email='test@example.test',status='pending',check_in=self.today+timedelta(days=3),check_out=self.today+timedelta(days=4))
        self.item=ReservationItem.objects.create(reservation=self.r,room=self.room,beds=1,price_per_night=20)
        self.hold=ReservationDepositRequest.objects.create(reservation=self.r,state='awaiting',amount=6,due_at=timezone.now()+timedelta(days=1),reminder_at=timezone.now(),origin='https://example.test')
        Reservation.objects.filter(pk=self.r.pk).update(deposit_request=self.hold)
        PaymentTransaction.objects.bulk_create([PaymentTransaction(reservation=self.r,kind='deposit',amount=2,method='bank')])
        ReservationNotification.objects.create(reservation=self.r,dedupe_key='reset-test',kind='deposit_request_guest',recipient='test@example.test',subject='Synthetic',body='Synthetic')
        CancellationSettlement.objects.create(reservation=self.r,outcome='retain',net_received_at_cancellation=2,retained_at_cancellation=2)
        PublicBookingSubmission.objects.create(key='reset-key',payload_hash='hash',reservation=self.r,expires_at=timezone.now()+timedelta(days=1))
        PublicBookingSubmission.objects.create(key='reset-orphan',payload_hash='hash',reservation=None,expires_at=timezone.now()+timedelta(days=1))
        BedAssignment.objects.create(bed=self.bed,item=self.item)
        BedCleaningEvent.objects.create(bed=self.bed,action='checkout',reservation=self.r)
        self.cleaning=BedCleaningEvent.objects.create(bed=self.bed,action='ready')
        BedHousekeeping.objects.create(bed=self.bed,state='ready')
        ReservationHistoryEvent.objects.create(hut=self.hut,reservation_code='old-detached',kind='updated',description='Old detached history')
        self.expense=HutExpense.objects.create(hut=self.hut,category='food',expense_date=self.today,amount=10)
        BedClosure.objects.create(bed=self.bed,start=self.today,end=self.today+timedelta(days=1))
        HutDepositPolicy.objects.create(hut=self.hut,percentage=30)
        PublicWebsiteSettings.objects.create(main_hut=self.hut)
        EmailSyncState.objects.create(mailbox='test@example.test',last_uid=123)
        for model in (Reservation,PaymentTransaction,apps.get_model('bookings.DepositEntry'),Hut):
            LogEntry.objects.create(user=self.user,content_type=ContentType.objects.get_for_model(model,for_concrete_model=False),object_id='1',object_repr='Synthetic',action_flag=CHANGE)
    def perform(self):
        with transaction.atomic():reset.reset_rows(connection)
    def test_active_hold_and_protected_payment_delete_without_signals_or_email(self):
        from django.core import mail
        before=len(mail.outbox)
        self.perform()
        self.assertTrue(all(n==0 for n in reset.counts(connection).values()))
        self.assertEqual(len(mail.outbox),before)
    def test_preserves_configuration_finances_users_housekeeping_and_mail_cursor(self):
        self.perform()
        for model,number in [(Hut,2),(Room,1),(Bed,1),(get_user_model(),1),(HutExpense,1),(BedClosure,1),(HutDepositPolicy,1),(PublicWebsiteSettings,1),(BedHousekeeping,1),(EmailSyncState,1)]:
            self.assertEqual(model.objects.count(),number,model._meta.label)
        self.assertEqual(EmailSyncState.objects.get().last_uid,123)
        self.assertTrue(self.hut.managers.filter(pk=self.user.pk).exists())
        self.assertEqual(list(BedCleaningEvent.objects.values_list('pk',flat=True)),[self.cleaning.pk])
        self.assertEqual(LogEntry.objects.count(),1)
        self.assertEqual(LogEntry.objects.get().content_type.model,'hut')
    def test_preview_counts_do_not_modify_rows(self):
        original=list(Reservation.objects.values())
        self.assertEqual(reset.counts(connection)['bookings.Reservation'],1)
        self.assertEqual(list(Reservation.objects.values()),original)
        self.assertEqual(PaymentTransaction.objects.count(),1)
    def test_failure_rolls_back_entire_reset_and_pointer(self):
        real_counts=reset.counts
        with patch.object(reset,'counts',side_effect=RuntimeError('injected verification failure')):
            with self.assertRaises(RuntimeError):self.perform()
        self.assertEqual(Reservation.objects.get().deposit_request_id,self.hold.pk)
        self.assertEqual(PaymentTransaction.objects.count(),1)
        self.assertEqual(PublicBookingSubmission.objects.count(),2)
        self.assertTrue(any(real_counts(connection).values()))
    def test_idempotent_reset_and_fresh_booking_still_work(self):
        self.perform();self.perform()
        from bookings.services import create_reservation,free_beds
        r=create_reservation(check_in=self.today+timedelta(days=3),check_out=self.today+timedelta(days=4),beds_by_room={self.room.pk:1},name='New guest',email='new@example.test')
        self.assertGreater(r.pk,self.r.pk)
        self.assertEqual(Reservation.objects.count(),1)
        self.assertEqual(free_beds([self.room],r.check_in,r.check_out)[self.room.pk],3)
    def test_all_statuses_and_all_huts_are_cleared(self):
        other_room=Room.objects.create(hut=self.other,name='Other room',capacity=4,price_per_night=10)
        for status in ('pending','confirmed','cancelled'):
            r=Reservation.objects.create(name='Other guest',status=status,check_in=self.today+timedelta(days=5),check_out=self.today+timedelta(days=6))
            ReservationItem.objects.create(reservation=r,room=other_room,beds=1,price_per_night=10)
        self.assertEqual(Reservation.objects.count(),4)
        self.perform()
        self.assertEqual(Reservation.objects.count(),0)
        self.assertEqual(Hut.objects.count(),2)
        self.assertEqual(Room.objects.count(),2)
    def test_preflight_rejects_sqlite_before_any_reset(self):
        with self.assertRaisesRegex(RuntimeError,'PostgreSQL'):reset.preflight(connection)
        self.assertEqual(Reservation.objects.count(),1)
    def test_dump_failure_prevents_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(reset,'lock_database'),patch.object(reset,'target_identity',return_value=['test','test',None,None]),patch.object(reset,'pg_environment',return_value={}),patch.object(reset,'run_pg',side_effect=RuntimeError('dump failed')):
                with self.assertRaisesRegex(RuntimeError,'dump failed'):reset.execute_reset(Path(directory),connection)
            self.assertEqual(Reservation.objects.count(),1)
            self.assertEqual(PaymentTransaction.objects.count(),1)
    def test_archive_verified_and_private_before_successful_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_pg(args,env):
                if args[0]=='pg_dump':
                    path=Path(next(a.split('=',1)[1] for a in args if a.startswith('--file=')))
                    path.write_bytes(b'Synthetic backup archive content'*30)
                    self.assertEqual(Reservation.objects.count(),1)
                    return b''
                self.assertEqual(Reservation.objects.count(),1)
                return b'123; TABLE DATA bookings reservation'
            with patch.object(reset,'lock_database'),patch.object(reset,'target_identity',return_value=['test','test',None,None]),patch.object(reset,'pg_environment',return_value={}),patch.object(reset,'run_pg',side_effect=fake_pg):
                reset.execute_reset(Path(directory),connection)
            self.assertEqual(Reservation.objects.count(),0)
            backup=next((Path(directory)/'summitdesk_backups').iterdir())
            self.assertEqual((backup/'database.dump').stat().st_mode&0o777,0o600)
            self.assertEqual((backup/'manifest.json').stat().st_mode&0o777,0o600)
            self.assertEqual(backup.stat().st_mode&0o777,0o700)
            metadata=json.loads((backup/'manifest.json').read_text())
            self.assertEqual(metadata['removed_rows']['bookings.Reservation'],1)
            self.assertEqual(metadata['database_sha256'],reset.sha256(backup/'database.dump'))
    def test_invalid_archive_listing_never_removes_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_pg(args,env):
                if args[0]=='pg_dump':
                    Path(next(a.split('=',1)[1] for a in args if a.startswith('--file='))).write_bytes(b'x'*300)
                return b'not a valid table data archive'
            with patch.object(reset,'lock_database'),patch.object(reset,'target_identity',return_value=['test']),patch.object(reset,'pg_environment',return_value={}),patch.object(reset,'run_pg',side_effect=fake_pg):
                with self.assertRaisesRegex(RuntimeError,'archive is incomplete'):reset.execute_reset(Path(directory),connection)
            self.assertEqual(Reservation.objects.count(),1)
    def test_corrupt_or_wrong_target_restore_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);backup=root/'summitdesk_backups'/'reservation_reset_v182_test';backup.mkdir(parents=True)
            dump=backup/'database.dump';dump.write_bytes(b'synthetic')
            metadata={'format':'summitdesk-reset-v182','target':['a'],'migrations':reset.applied_migrations(connection),'database_sha256':'wrong'}
            (backup/'manifest.json').write_text(json.dumps(metadata))
            with patch.object(reset,'target_identity',return_value=['b']):
                with self.assertRaisesRegex(RuntimeError,'target'):reset.validate_restore(root,backup,connection)
            with patch.object(reset,'target_identity',return_value=['a']):
                with self.assertRaisesRegex(RuntimeError,'checksum'):reset.validate_restore(root,backup,connection)
    def test_migration_changes_block_full_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);backup=root/'summitdesk_backups'/'reservation_reset_v182_test';backup.mkdir(parents=True)
            dump=backup/'database.dump';dump.write_bytes(b'synthetic')
            metadata={'format':'summitdesk-reset-v182','target':['a'],'migrations':[],'database_sha256':reset.sha256(dump)}
            (backup/'manifest.json').write_text(json.dumps(metadata))
            with patch.object(reset,'target_identity',return_value=['a']):
                with self.assertRaisesRegex(RuntimeError,'migrations'):reset.validate_restore(root,backup,connection)

class SchemaGuardTests(TransactionTestCase):
    def test_unknown_foreign_key_blocks_reset(self):
        class UnknownReservationRelation(models.Model):
            reservation=models.ForeignKey(Reservation,on_delete=models.CASCADE)
            class Meta:app_label='tests';db_table='reset182_unknown_reference'
        with connection.schema_editor() as editor:editor.create_model(UnknownReservationRelation)
        try:
            with self.assertRaisesRegex(RuntimeError,'Unexpected related table'):reset.models_and_guard(connection)
        finally:
            with connection.schema_editor() as editor:editor.delete_model(UnknownReservationRelation)
