"""v146 booking handoff, reviewed prices, safe alternatives and staff authorization."""
from datetime import timedelta
from decimal import Decimal
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone, translation
from .models import Hut, Room, Bed, BedClosure, Reservation, ReservationItem, PublicBookingSubmission, ReservationNotification
from .ux_v146 import nearby_stays


class Ux146Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut=Hut.objects.create(name='UX Test Lodge',slug='ux-lodge')
        cls.room=Room.objects.create(hut=cls.hut,name='Pine Room',capacity=4,price_per_night=Decimal('24.50'))
        cls.other=Room.objects.create(hut=cls.hut,name='Ridge Room',capacity=2,price_per_night=Decimal('39.25'))
        cls.private_hut=Hut.objects.create(name='Private property',slug='ux-private')
        cls.private=Room.objects.create(hut=cls.private_hut,name='Private room',capacity=8)
        cls.manager=get_user_model().objects.create_user('ux-manager',is_staff=True)
        cls.superuser=get_user_model().objects.create_superuser('ux-admin',email='admin@example.com',password='test-only')
        cls.hut.managers.add(cls.manager,cls.superuser)
        cls.start=timezone.localdate()+timedelta(days=12)
        cls.end=cls.start+timedelta(days=2)

    def url(self):return reverse('bookings:hut_detail',args=[self.hut.slug])
    def dates(self,**extra):return dict(check_in=self.start.isoformat(),check_out=self.end.isoformat(),beds='2',**extra)
    def payload(self):return {**self.dates(),'name':'Kept Guest','email':'kept@example.com','phone':'12345','notes':'Keep my notes',f'room_{self.room.pk}':'2'}

    def test_directory_links_keep_guest_count_and_hut_form_has_summary(self):
        response=self.client.get(reverse('bookings:hut_list'),self.dates())
        self.assertContains(response,f'check_in={self.start.isoformat()}&amp;check_out={self.end.isoformat()}&amp;beds=2')
        page=self.client.get(self.url(),self.dates())
        self.assertEqual(page.context['requested_beds'],2)
        self.assertContains(page,'id="ph-party-size"')
        self.assertContains(page,'Your request summary')
        self.assertNotContains(page,'Private room')

    def test_mismatched_group_is_rejected_and_full_price_is_preserved(self):
        data=self.payload();data['beds']='3'
        page=self.client.post(self.url(),data)
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'Select exactly 3 beds')
        self.assertEqual(page.context['estimated_total'],Decimal('98.00'))
        self.assertEqual(page.context['selected_beds'],2)
        self.assertContains(page,'Kept Guest')
        self.assertFalse(Reservation.objects.exists())

    def test_invalid_party_size_cannot_create(self):
        for size in ('0','31','two'):
            with self.subTest(size=size):
                data=self.payload();data['beds']=size
                self.assertContains(self.client.post(self.url(),data),'Choose between 1 and 30 guests')
                self.assertContains(self.client.get(self.url(),{**self.dates(),'beds':size}),'Choose between 1 and 30 guests')
        self.assertFalse(Reservation.objects.exists())

    def test_native_alternative_preview_keeps_details_without_writing(self):
        data=self.payload();a=self.start+timedelta(days=1);b=self.end+timedelta(days=1)
        data['preview_stay']=a.isoformat()+':'+b.isoformat()
        page=self.client.post(self.url(),data)
        self.assertEqual(page.status_code,200)
        self.assertEqual(page.context['check_in'],a)
        self.assertEqual(page.context['booking']['name'].value(),'Kept Guest')
        self.assertEqual(page.context['booking']['notes'].value(),'Keep my notes')
        self.assertEqual(page.context['selected_beds'],2)
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(PublicBookingSubmission.objects.exists())
        self.assertFalse(ReservationNotification.objects.exists())

    def test_suggestions_respect_pending_and_maintenance_and_exclude_checkout(self):
        booking=Reservation.objects.create(name='Occupied',check_in=self.start,check_out=self.end,status=Reservation.Status.PENDING)
        ReservationItem.objects.create(reservation=booking,room=self.room,beds=3)
        bed=Bed.objects.create(room=self.room,number=1)
        BedClosure.objects.create(bed=bed,start=self.start,end=self.end)
        offers=nearby_stays(self.hut,[self.room],self.start,self.end,4)
        self.assertTrue(offers)
        for offer in offers:
            self.assertTrue(offer['check_in'] >= self.end or offer['check_out'] <= self.start)
            self.assertEqual(offer['free'],4)
        self.assertEqual(offers[0]['check_in'],self.end)

    def test_superuser_hut_assignment_retains_admin_models_and_all_permissions(self):
        self.client.force_login(self.superuser)
        page=self.client.get(reverse('admin:index'))
        request=RequestFactory().get('/admin/');request.user=self.superuser
        for model in (Hut,Room,Reservation):
            registered=admin.site._registry[model]
            self.assertTrue(registered.has_module_permission(request))
            self.assertTrue(all(registered.get_model_perms(request).values()))
            url=reverse('admin:bookings_'+model._meta.model_name+'_changelist')
            self.assertContains(page,url)
            self.assertEqual(self.client.get(url).status_code,200)

    def test_ordinary_manager_remains_restricted_even_with_model_permissions(self):
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label='bookings'))
        self.client.force_login(self.manager)
        for model in ('hut','room','reservation'):
            self.assertEqual(self.client.get(reverse('admin:bookings_'+model+'_changelist')).status_code,403)

    def test_staff_conflict_keeps_month_details_and_currency(self):
        self.client.force_login(self.manager)
        start=(timezone.localdate().replace(day=1)+timedelta(days=70)).replace(day=2)
        data={'room':self.room.pk,'check_in':start.isoformat(),'check_out':(start+timedelta(days=2)).isoformat(),'beds':4,'name':'Kept Staff Guest','notes':'Preserved note'}
        url=reverse('floorplans:quickstay_create',args=[self.hut.pk])
        self.assertEqual(self.client.post(url,data).status_code,302)
        page=self.client.post(url,data)
        self.assertEqual(page.status_code,400)
        self.assertEqual(page.context['first'],start.replace(day=1))
        self.assertContains(page,'Kept Staff Guest',status_code=400)
        self.assertContains(page,'Preserved note',status_code=400)
        self.assertContains(page,'data-currency=',status_code=400)

    def test_staff_preview_has_real_dates_but_mixed_hut_guest_is_hidden(self):
        start=timezone.localdate()+timedelta(days=2);end=start+timedelta(days=3)
        own=Reservation.objects.create(name='Preview Guest',check_in=start,check_out=end,status=Reservation.Status.PENDING)
        ReservationItem.objects.create(reservation=own,room=self.room,beds=1)
        mixed=Reservation.objects.create(name='Hidden Mixed Guest',check_in=start,check_out=end,status=Reservation.Status.CONFIRMED)
        ReservationItem.objects.create(reservation=mixed,room=self.room,beds=1)
        ReservationItem.objects.create(reservation=mixed,room=self.private,beds=1)
        self.client.force_login(self.manager)
        with translation.override('bg'):
            page=self.client.get(reverse('floorplans:staff_calendar',args=[self.hut.pk]))
        self.assertContains(page,'data-price="24.50"')
        self.assertContains(page,f'data-arrival="{start.isoformat()}" data-departure="{end.isoformat()}"')
        self.assertContains(page,'Preview Guest')
        self.assertNotContains(page,'Hidden Mixed Guest')
        self.assertNotContains(page,mixed.code)
        self.assertContains(page,'Monthly stay planner')
        self.assertContains(page,'Booking calendar')
        self.assertNotContains(page,'Django admin')
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(reverse('floorplans:staff_calendar',args=[self.hut.pk])),'Django admin')
