from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from .models import Room, Hut, Reservation, ReservationItem, PublicWebsiteSettings
from .services import create_reservation, modify_reservation
from .seasonal_v186 import season, room_rates, attach_quote, validate_snapshot
from .forms import BookingForm
from .deposit_flow_v180 import default_terms


def upcoming(month, day):
    today = timezone.localdate()
    result = date(today.year, month, day)
    return result if result >= today else date(today.year + 1, month, day)


@override_settings(BOOKING_UNIT='room', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOOKING_NOTIFY_EMAIL='')
class Seasonal186Tests(TestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name='Seasonal synthetic hut', slug='season186')
        self.room = Room.objects.create(hut=self.hut, name='Studio', capacity=4, price_per_night=30,
                                        summer_price=40, winter_price=70, room_type='studio')
        PublicWebsiteSettings.objects.create(main_hut=self.hut)
        self.start = upcoming(10, 31)
        self.end = self.start + timedelta(days=2)
        self.manager = get_user_model().objects.create_user('season-manager', is_staff=True)
        self.hut.managers.add(self.manager)

    def make(self, count=1, start=None, end=None):
        return create_reservation(check_in=start or self.start, check_out=end or self.end,
            beds_by_room={self.room.pk: count}, name='Synthetic seasonal guest', email='test@example.test')

    def test_exact_season_boundaries_and_leap_day(self):
        for value, expected in [(date(2028,4,30),'winter'),(date(2028,5,1),'summer'),
                (date(2028,10,31),'summer'),(date(2028,11,1),'winter'),
                (date(2028,2,29),'winter'),(date(2028,12,31),'winter'),(date(2029,1,1),'winter')]:
            with self.subTest(day=value): self.assertEqual(season(value), expected)

    def test_october_crossing_uses_each_night_not_checkout_date(self):
        reservation = self.make()
        self.assertEqual(reservation.total_price,110)
        item = reservation.items.get()
        self.assertEqual(item.nightly_total_on(self.start),40)
        self.assertEqual(item.nightly_total_on(self.start+timedelta(days=1)),70)
        self.assertEqual([line['nights'] for line in item.seasonal_lines],[1,1])

    def test_april_crossing_uses_winter_then_summer(self):
        start = upcoming(4,30)
        self.assertEqual(self.make(start=start,end=start+timedelta(days=2)).total_price,110)

    def test_checkout_is_not_charged(self):
        self.assertEqual(self.make(end=self.start+timedelta(days=1)).total_price,40)

    def test_summer_and_winter_only_stays(self):
        summer = upcoming(5,1)
        r = self.make(start=summer,end=summer+timedelta(days=3))
        self.assertEqual(r.total_price,120)
        winter = upcoming(12,30)
        r = self.make(start=winter,end=winter+timedelta(days=3))
        self.assertEqual(r.total_price,210)

    def test_guest_count_never_multiplies_rates(self):
        r = self.make(count=4)
        self.assertEqual(r.total_price,110)
        modify_reservation(code=r.code,check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:1})
        r.refresh_from_db()
        self.assertEqual(r.total_price,110)

    def test_room_rate_edit_does_not_reprice_saved_reservation(self):
        r = self.make()
        Room.objects.filter(pk=self.room.pk).update(summer_price=400,winter_price=700,price_per_night=999)
        r.refresh_from_db()
        self.assertEqual(r.total_price,110)
        self.assertEqual(r.items.get().seasonal_rates,{'summer':'40.00','winter':'70.00'})

    def test_date_change_keeps_agreed_seasonal_rates(self):
        r = self.make()
        Room.objects.filter(pk=self.room.pk).update(summer_price=400,winter_price=700)
        modify_reservation(code=r.code,check_in=self.start,check_out=self.end+timedelta(days=1),beds_by_room={self.room.pk:1})
        r.refresh_from_db()
        self.assertEqual(r.total_price,180)

    def test_old_flat_booking_keeps_its_price_after_room_rate_change(self):
        r = self.make()
        ReservationItem.objects.filter(reservation=r).update(seasonal_rates={},price_per_night=25)
        Room.objects.filter(pk=self.room.pk).update(summer_price=400,winter_price=700)
        r.refresh_from_db()
        self.assertEqual(r.total_price,50)

    def test_legacy_per_bed_snapshot_is_preserved(self):
        r = self.make(count=3)
        ReservationItem.objects.filter(reservation=r).update(seasonal_rates={},pricing_unit='bed',price_per_night=12)
        r.refresh_from_db()
        self.assertEqual(r.total_price,72)

    def test_null_rates_fall_back_but_zero_is_a_valid_rate(self):
        self.room.summer_price=None; self.room.winter_price=0
        self.assertEqual(room_rates(self.room),{'summer':Decimal(30),'winter':Decimal(0)})
        self.room.save()
        self.assertEqual(self.make().total_price,30)

    def test_rate_validation_and_database_nonnegative_constraint(self):
        self.room.summer_price=-1
        with self.assertRaises(ValidationError):self.room.full_clean()
        with self.assertRaises(IntegrityError),transaction.atomic():Room.objects.filter(pk=self.room.pk).update(winter_price=-1)
        for value in [{'summer':'1'}, {'summer':'NaN','winter':'1'}, {'summer':'1.001','winter':'2'}]:
            with self.assertRaises(ValidationError):validate_snapshot(value)

    def test_agreed_snapshot_is_immutable(self):
        item = self.make().items.get();item.seasonal_rates={'summer':'1','winter':'2'}
        with self.assertRaises(ValidationError):item.save()
        self.assertEqual(ReservationItem.objects.get(pk=item.pk).seasonal_rates,{'summer':'40.00','winter':'70.00'})

    def test_form_uses_exact_stay_total(self):
        form = BookingForm(rooms=[self.room],free={self.room.pk:4},check_in=self.start,check_out=self.end)
        field=form.fields[f'room_{self.room.pk}']
        self.assertEqual(Decimal(field.widget.attrs['data-stay-total']),110)
        self.assertEqual(self.room.quoted_total,110)

    def test_public_preview_and_error_summary_agree(self):
        data={'check_in':self.start,'check_out':self.end,'beds':3}
        page=self.client.get(reverse('bookings:book'),data)
        self.assertContains(page,'Summer');self.assertContains(page,'Winter')
        self.assertContains(page,'data-stay-total="110.00"')
        self.assertContains(page,'public_hut_v186.js')
        data.update({'name':'Synthetic','email':'invalid',f'room_{self.room.pk}':3})
        page=self.client.post(reverse('bookings:book'),data)
        self.assertEqual(page.context['estimated_total'],110)

    def test_manager_can_set_two_rates_without_changing_existing_booking(self):
        r=self.make();self.client.force_login(self.manager)
        response=self.client.post(reverse('bookings:room_details',args=[self.room.pk]),{
            'room_type':'studio','summer_price':'50.50','winter_price':'90.25','extras_en':'','extras_bg':''})
        self.assertEqual(response.status_code,302)
        self.room.refresh_from_db();r.refresh_from_db()
        self.assertEqual(self.room.summer_price,Decimal('50.50'));self.assertEqual(self.room.winter_price,Decimal('90.25'))
        self.assertEqual(r.total_price,110)

    def test_negative_manager_rate_rejected(self):
        self.client.force_login(self.manager)
        response=self.client.post(reverse('bookings:room_details',args=[self.room.pk]),{
            'room_type':'studio','summer_price':'-1','winter_price':'50','extras_en':'','extras_bg':''})
        self.assertEqual(response.status_code,200)
        self.room.refresh_from_db();self.assertEqual(self.room.summer_price,40)

    def test_receipt_shows_agreed_breakdown_and_total(self):
        r=self.make();self.room.summer_price=999;self.room.winter_price=888;self.room.save()
        self.client.force_login(self.manager)
        page=self.client.get(r.get_absolute_url())
        self.assertContains(page,'Summer: 1 × 40.00')
        self.assertContains(page,'Winter: 1 × 70.00')
        self.assertContains(page,'110.00')
        self.assertNotContains(page,'999.00')

    def test_deposit_uses_seasonal_total(self):
        self.assertEqual(default_terms(self.make())['deposit_amount'],Decimal('33.00'))

    def test_partial_reporting_range_uses_its_own_season(self):
        item=self.make().items.get()
        self.assertEqual(item.total_between(self.start,self.start+timedelta(days=1)),40)
        self.assertEqual(item.total_between(self.start+timedelta(days=1),self.end),70)

    def test_real_public_submit_saves_the_previewed_seasonal_total(self):
        data={'check_in':self.start,'check_out':self.end,'beds':4}
        page=self.client.get(reverse('bookings:book'),data)
        data.update({'submission_token':page.context['submission_token'],'name':'Synthetic booking',
                     'email':'test@example.test',f'room_{self.room.pk}':4})
        response=self.client.post(reverse('bookings:book'),data)
        self.assertEqual(response.status_code,302)
        r=Reservation.objects.get()
        self.assertEqual(r.total_price,110)
        self.assertEqual(r.total_beds,4)

    def test_financial_report_allocates_october_and_november_separately(self):
        r=self.make();r.status='confirmed';r.save(update_fields=['status'])
        self.client.force_login(self.manager)
        response=self.client.get(reverse('floorplans:staff_financial_analytics',args=[self.hut.pk]),{
            'from':self.start,'to':self.end-timedelta(days=1)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['confirmed_total'],110)
        self.assertEqual([row['confirmed'] for row in response.context['months']],[40,70])

    def test_staff_booking_renders_both_rates_for_live_seasonal_preview(self):
        self.client.force_login(self.manager)
        response=self.client.get(reverse('bookings:manual_booking'),{
            'hut':self.hut.pk,'check_in':self.start,'check_out':self.end})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-summer-price="40.00"')
        self.assertContains(response,'data-winter-price="70.00"')
        self.assertContains(response,'window.SummitDeskSeasonal.total')

    def test_modification_quote_preserves_agreed_rates_for_existing_unit(self):
        r=self.make();Room.objects.filter(pk=self.room.pk).update(summer_price=400,winter_price=700)
        room=Room.objects.get(pk=self.room.pk)
        form=BookingForm(rooms=[room],free={room.pk:4},check_in=self.start,check_out=self.end,
                         price_items={room.pk:r.items.get()})
        self.assertEqual(Decimal(form.fields[f'room_{room.pk}'].widget.attrs['data-stay-total']),110)

    def test_property_calendar_keeps_overview_and_shows_both_unit_rates(self):
        self.client.force_login(self.manager)
        page=self.client.get(reverse('floorplans:staff_calendar',args=[self.hut.pk]))
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'Availability at a glance')
        self.assertContains(page,'Units under maintenance')
        self.assertContains(page,'Summer')
        self.assertContains(page,'40.00')
        self.assertContains(page,'70.00')
        self.assertContains(page,'property_planner_v186.js')
