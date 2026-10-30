from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Hut, Room, Reservation, ReservationItem, Bed, BedClosure, PublicWebsiteSettings
from .services import create_reservation, modify_reservation, free_beds, NotAvailable
from .availability_v147 import nightly_availability

@override_settings(BOOKING_UNIT='room', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOOKING_NOTIFY_EMAIL='')
class WholeUnitTests(TestCase):
    def setUp(self):
        self.hut=Hut.objects.create(name='Unit Hut',slug='unit-hut')
        self.room=Room.objects.create(hut=self.hut,name='Studio',capacity=4,price_per_night=80)
        self.other=Room.objects.create(hut=self.hut,name='Apartment',capacity=6,price_per_night=120)
        self.start=timezone.localdate()+timedelta(days=10);self.end=self.start+timedelta(days=2)
        self.manager=get_user_model().objects.create_user('unit-manager',is_staff=True);self.hut.managers.add(self.manager)
        PublicWebsiteSettings.objects.create(main_hut=self.hut)
    def make(self,guests=1,room=None,**kw):
        return create_reservation(check_in=self.start,check_out=self.end,beds_by_room={(room or self.room).pk:guests},name='Synthetic guest',email='unit@example.test',**kw)
    def test_one_guest_pays_room_price_and_blocks_every_bed(self):
        r=self.make();self.assertEqual(r.total_price,Decimal('160'));self.assertEqual(r.total_beds,1)
        self.assertEqual(r.items.get().pricing_unit,'room');self.assertEqual(free_beds([self.room],self.start,self.end)[self.room.pk],0)
        with self.assertRaises(NotAvailable):self.make()
    def test_guest_count_does_not_multiply_price(self):
        r=self.make(4);self.assertEqual(r.total_price,160)
        modify_reservation(code=r.code,check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:2})
        r.refresh_from_db();self.assertEqual(r.total_price,160);self.assertEqual(r.total_beds,2)
    def test_each_selected_unit_is_charged_once(self):
        r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:2,self.other.pk:3},name='Synthetic')
        self.assertEqual(r.total_price,400)
    def test_capacity_is_still_enforced(self):
        with self.assertRaises(NotAvailable):self.make(5)
    def test_checkout_day_can_be_booked_by_another_guest(self):
        self.make();self.start=self.end;self.end=self.start+timedelta(days=1)
        self.assertEqual(self.make().total_price,80)
    def test_cancelled_releases_entire_unit(self):
        r=self.make();r.status='cancelled';r.save(update_fields=['status']);self.make(4)
    def test_closure_blocks_unit_and_nightly_calendar_agrees(self):
        bed=Bed.objects.create(room=self.room,number=1);BedClosure.objects.create(bed=bed,start=self.start,end=self.end)
        self.assertEqual(free_beds([self.room],self.start,self.end)[self.room.pk],0)
        self.assertEqual(nightly_availability([self.room],self.start,self.end)[self.start][self.room.pk],0)
    def test_nightly_and_property_calendar_never_offer_spare_beds(self):
        self.make()
        self.assertEqual(nightly_availability([self.room],self.start,self.end)[self.start][self.room.pk],0)
        from floorplans.property_calendar_v138 import month_rows
        row=month_rows(self.start.replace(day=1),[self.room])[0]
        cell=next(d for d in row['days'] if d['day']==self.start);self.assertEqual(cell['available'],0)
    def test_staff_manual_booking_uses_exclusive_service(self):
        self.make();self.client.force_login(self.manager)
        result=self.client.post(reverse('bookings:manual_booking'),{'hut':self.hut.pk,'check_in':self.start,'check_out':self.end,'name':'Other','phone':'+359888123456',f'beds_{self.room.pk}':1})
        self.assertEqual(result.status_code,200);self.assertEqual(Reservation.objects.count(),1)
    def test_public_preview_and_post_use_whole_room_price(self):
        params={'check_in':self.start.isoformat(),'check_out':self.end.isoformat(),'beds':2}
        page=self.client.get(reverse('bookings:book'),params)
        self.assertEqual(page.status_code,200);self.assertContains(page,'per unit / night')
        data={**params,'submission_token':page.context['submission_token'],'name':'Synthetic','email':'unit@example.test',f'room_{self.room.pk}':2}
        result=self.client.post(reverse('bookings:book'),data)
        self.assertEqual(result.status_code,302);r=Reservation.objects.get();self.assertEqual(r.total_price,160)
        self.assertEqual(free_beds([self.room],self.start,self.end)[self.room.pk],0)
    def test_model_item_write_cannot_bypass_exclusivity(self):
        self.make();r=Reservation.objects.create(name='Other',check_in=self.start,check_out=self.end)
        with self.assertRaises(ValidationError):ReservationItem.objects.create(reservation=r,room=self.room,beds=1,price_per_night=80)
    def test_admin_date_change_cannot_bypass_exclusivity(self):
        self.make();r=create_reservation(check_in=self.end,check_out=self.end+timedelta(days=2),beds_by_room={self.room.pk:1},name='Later')
        r.check_in=self.start
        with self.assertRaises(ValidationError):r.save()
    def test_legacy_totals_and_approved_terms_are_not_repriced(self):
        with override_settings(BOOKING_UNIT='bed'):r=self.make(3)
        self.assertEqual(r.total_price,480);self.assertEqual(r.items.get().pricing_unit,'bed')
        self.assertEqual(free_beds([self.room],self.start,self.end)[self.room.pk],0)
    def test_price_snapshot_survives_room_rate_change(self):
        r=self.make();self.room.price_per_night=200;self.room.save();self.assertEqual(r.total_price,160)
    def test_receipt_renders_whole_unit_without_guest_multiplier(self):
        r=self.make(3);self.client.force_login(self.manager)
        page=self.client.get(reverse('bookings:reservation',args=[r.code]));self.assertEqual(page.status_code,200)
        self.assertContains(page,'Whole unit');self.assertContains(page,'160.00')
    def test_deposit_terms_use_unit_total(self):
        from .deposit_flow_v180 import default_terms
        r=self.make(3);self.assertEqual(default_terms(r)['deposit_amount'],48)

from unittest import skipUnless
from django.db import connection, close_old_connections, connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

@skipUnless(connection.vendor=='postgresql','Real row-lock test requires PostgreSQL')
@override_settings(BOOKING_UNIT='room')
class PostgreSQLWholeUnitTests(TransactionTestCase):
    def test_two_guests_cannot_share_a_four_person_unit_concurrently(self):
        hut=Hut.objects.create(name='Concurrent',slug='concurrent-unit')
        room=Room.objects.create(hut=hut,name='Apartment',capacity=4,price_per_night=100)
        start=timezone.localdate()+timedelta(days=10);end=start+timedelta(days=2);barrier=Barrier(2)
        def attempt():
            close_old_connections()
            try:
                with connection.cursor() as cursor:cursor.execute("SET lock_timeout = '12s'")
                barrier.wait(timeout=15)
                try:
                    create_reservation(check_in=start,check_out=end,beds_by_room={room.pk:1},name='Synthetic concurrent guest')
                    return 'created'
                except NotAvailable:return 'blocked'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(attempt),pool.submit(attempt)]
            result=[future.result(timeout=30) for future in futures]
        self.assertCountEqual(result,['created','blocked'])
        self.assertEqual(Reservation.objects.count(),1)
        self.assertEqual(Reservation.objects.get().total_price,200)

@override_settings(BOOKING_UNIT='room', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOOKING_NOTIFY_EMAIL='')
class WholeUnitDepositTests(TestCase):
    setUp = WholeUnitTests.setUp
    make = WholeUnitTests.make
    # Additional room-mode lifecycle coverage; parent scenarios are intentionally
    # inherited to verify the same fixture with the live-deposit settings.
    def test_deposit_approval_then_payment_confirms_exclusive_unit(self):
        r=self.make(3,status='pending',guest_request=True);self.client.force_login(self.manager)
        data={'action':'confirm','deposit_amount':'48','deposit_due_at':timezone.localtime(timezone.now()+timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),'instructions_en':'Synthetic bank instructions','instructions_bg':''}
        response=self.client.post(reverse('bookings:manager_reservation_action',args=[r.code]),data)
        self.assertEqual(response.status_code,302);r.refresh_from_db();self.assertEqual(r.deposit_request.amount,48)
        from .models import PaymentTransaction
        PaymentTransaction.objects.create(reservation=r,kind='deposit',method='bank',amount=48)
        r.refresh_from_db();self.assertEqual(r.status,'confirmed');self.assertEqual(r.total_price,160)
        with self.assertRaises(NotAvailable):self.make()
    def test_expired_deposit_releases_full_unit(self):
        self.test_deposit_approval_then_payment_confirms_exclusive_unit()
        # A separate unit allows an unpaid expiry fixture without altering paid terms.
        r=self.make(1,room=self.other,status='pending',guest_request=True)
        from .models import ReservationDepositRequest as Hold
        from .deposit_flow_v180 import process_holds
        hold=Hold.objects.create(reservation=r,state='awaiting',amount=36,due_at=timezone.now()-timedelta(seconds=1),reminder_at=timezone.now()-timedelta(hours=1),origin='https://example.test')
        Reservation.objects.filter(pk=r.pk).update(deposit_request=hold)
        self.assertEqual(free_beds([self.other],self.start,self.end)[self.other.pk],6)
        process_holds();r.refresh_from_db();self.assertEqual(r.status,'cancelled')
