from datetime import timedelta
from decimal import Decimal
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError,transaction
from django.urls import reverse
from django.utils import timezone,translation
from django.template.loader import render_to_string
from .models import Hut,Room,PublicWebsiteSettings,Reservation
from .room_details_v184 import RoomDetailsForm
from .services import create_reservation,free_beds,NotAvailable

@override_settings(BOOKING_UNIT='room',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class RoomTypes184Tests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user('types-manager',is_staff=True)
  self.hut=Hut.objects.create(name='Types Hut',slug='types-hut');self.hut.managers.add(self.user)
  self.foreign=Hut.objects.create(name='Other Hut',slug='other-types')
  self.normal=Room.objects.create(hut=self.hut,name='Room 1',capacity=3,price_per_night=30)
  self.studio=Room.objects.create(hut=self.hut,name='Studio 1',room_type='studio',capacity=4,price_per_night=80,extras_en='Synthetic kitchenette\nSynthetic balcony',extras_bg='Тестов кухненски бокс\nТестова тераса')
  self.other=Room.objects.create(hut=self.foreign,name='Private room',capacity=2,price_per_night=20)
  PublicWebsiteSettings.objects.create(main_hut=self.hut)
  self.client.force_login(self.user);self.start=timezone.localdate()+timedelta(days=10);self.end=self.start+timedelta(days=2)
 def test_existing_default_is_normal_and_no_extras_are_invented(self):
  self.assertEqual(self.normal.room_type,'normal');self.assertEqual(self.normal.extra_features,[])
 def test_two_types_reject_invalid_type_in_form_and_database(self):
  form=RoomDetailsForm({'room_type':'presidential','extras_en':'','extras_bg':''},instance=self.normal)
  self.assertFalse(form.is_valid());self.assertIn('room_type',form.errors)
  with self.assertRaises(IntegrityError),transaction.atomic():Room.objects.filter(pk=self.normal.pk).update(room_type='invalid')
 def test_manager_can_edit_type_and_bilingual_extras_without_changing_price(self):
  r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.normal.pk:2},name='Synthetic guest')
  data={'room_type':'studio','extras_en':'Kitchenette\nBalcony','extras_bg':'Кухненски бокс\nТераса','price_per_night':'1','capacity':'99'}
  response=self.client.post(reverse('bookings:room_details',args=[self.normal.pk]),data)
  self.assertEqual(response.status_code,302);self.normal.refresh_from_db();r.refresh_from_db()
  self.assertEqual(self.normal.room_type,'studio');self.assertEqual(self.normal.price_per_night,30);self.assertEqual(self.normal.capacity,3);self.assertEqual(r.total_price,60)
 def test_other_hut_is_not_readable_or_editable(self):
  url=reverse('bookings:room_details',args=[self.other.pk])
  self.assertEqual(self.client.get(url).status_code,404);self.assertEqual(self.client.post(url,{'room_type':'studio'}).status_code,404)
 def test_unassigned_staff_and_guest_cannot_edit(self):
  self.client.force_login(get_user_model().objects.create_user('unassigned-types',is_staff=True))
  url=reverse('bookings:room_details',args=[self.normal.pk]);self.assertEqual(self.client.get(url).status_code,404)
  self.client.logout();self.assertEqual(self.client.post(url,{'room_type':'studio'}).status_code,302)
 def test_superuser_can_edit_foreign_hut(self):
  self.client.force_login(get_user_model().objects.create_superuser('type-owner','owner@example.test','test-only'))
  self.assertEqual(self.client.get(reverse('bookings:room_details',args=[self.other.pk])).status_code,200)
 def test_superuser_can_edit_a_room_without_a_hut(self):
  self.client.force_login(get_user_model().objects.create_superuser("unassigned-owner","owner@example.test","test-only"))
  room=Room.objects.create(name="Unassigned",capacity=2,price_per_night=20)
  self.assertEqual(self.client.get(reverse("bookings:room_details",args=[room.pk])).status_code,200)
 def test_csrf_and_length_validation(self):
  client=Client(enforce_csrf_checks=True);client.force_login(self.user)
  self.assertEqual(client.post(reverse('bookings:room_details',args=[self.normal.pk]),{'room_type':'studio'}).status_code,403)
  form=RoomDetailsForm({'room_type':'normal','extras_en':'x'*1001,'extras_bg':''},instance=self.normal);self.assertFalse(form.is_valid())
 def test_public_page_displays_types_and_actual_english_extras(self):
  self.client.logout();response=self.client.get(reverse('bookings:book'),{'check_in':self.start,'check_out':self.end,'beds':1})
  self.assertEqual(response.status_code,200)
  for text in ['Normal room','Studio','Synthetic kitchenette','Synthetic balcony']:self.assertContains(response,text)
 def test_bulgarian_extras_and_english_fallback(self):
  with translation.override('bg'):self.assertEqual(self.studio.extra_features,['Тестов кухненски бокс','Тестова тераса'])
  self.studio.extras_bg=''
  with translation.override('bg'):self.assertEqual(self.studio.extra_features,['Synthetic kitchenette','Synthetic balcony']);self.assertEqual(self.studio.extras_language,'en')
 def test_extras_are_escaped(self):
  self.studio.extras_en='<script>alert(1)</script>'
  page=render_to_string('bookings/room_type_v184.html',{'room':self.studio})
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
 def test_both_types_are_exclusive_and_charge_once_per_night(self):
  for room in [self.normal,self.studio]:
   r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={room.pk:1},name='Synthetic guest')
   self.assertEqual(r.total_price,room.price_per_night*2);self.assertEqual(free_beds([room],self.start,self.end)[room.pk],0)
   with self.assertRaises(NotAvailable):create_reservation(check_in=self.start,check_out=self.end,beds_by_room={room.pk:1},name='Another guest')
