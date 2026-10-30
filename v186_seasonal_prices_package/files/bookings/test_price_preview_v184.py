from datetime import timedelta
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.staticfiles import finders
from .models import Hut,Room,PublicWebsiteSettings
from .services import create_reservation

@override_settings(BOOKING_UNIT='room',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class PricePreview184Tests(TestCase):
 def setUp(self):
  hut=Hut.objects.create(name='Preview Hut',slug='preview184');PublicWebsiteSettings.objects.create(main_hut=hut)
  self.room=Room.objects.create(hut=hut,name='Studio',capacity=3,price_per_night=30)
  self.start=timezone.localdate()+timedelta(days=4);self.end=self.start+timedelta(days=2)
 def test_rendered_form_declares_room_pricing_and_loads_a_new_asset(self):
  page=self.client.get(reverse('bookings:book'),{'check_in':self.start,'check_out':self.end,'beds':3})
  self.assertEqual(page.status_code,200)
  self.assertContains(page,'data-pricing-unit="room"')
  self.assertContains(page,'bookings/public_hut_v186.js')
  self.assertNotContains(page,'src="/static/bookings/public_hut_v150.js"')
  self.assertIsNotNone(finders.find('bookings/public_hut_v186.js'))
 def test_invalid_contact_preserves_the_correct_server_total_for_three_guests(self):
  response=self.client.post(reverse('bookings:book'),{'check_in':self.start,'check_out':self.end,'beds':3,'name':'Synthetic','email':'invalid',f'room_{self.room.pk}':3})
  self.assertEqual(response.status_code,200)
  self.assertEqual(response.context['estimated_total'],60)
  self.assertContains(response,'data-pricing-unit="room"')
 def test_one_and_three_guests_have_the_same_saved_total(self):
  r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:1},name='Synthetic one')
  self.assertEqual(r.total_price,60)
  r.status='cancelled';r.save(update_fields=['status'])
  r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:3},name='Synthetic three')
  self.assertEqual(r.total_price,60)
