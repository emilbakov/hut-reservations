from datetime import timedelta
from pathlib import Path
from django.test import TestCase,override_settings
from django.utils import timezone
from django.template.loader import render_to_string
from .models import Hut,Room,Reservation,ReservationItem,Bed,BedClosure
from .services import create_reservation
from floorplans.property_calendar_v138 import month_rows,availability_overview

@override_settings(BOOKING_UNIT='room')
class CalendarMergeTests(TestCase):
 def setUp(self):
  self.hut=Hut.objects.create(name='Merged planner',slug='merged-planner')
  self.room=Room.objects.create(hut=self.hut,name='Studio',capacity=4,price_per_night=80)
  self.other=Room.objects.create(hut=self.hut,name='Apartment',capacity=6,price_per_night=120)
  self.inactive=Room.objects.create(hut=self.hut,name='Inactive',capacity=10,price_per_night=150,is_active=False)
  self.day=timezone.localdate()+timedelta(days=3);self.end=self.day+timedelta(days=2)
 def reserve(self):
  return create_reservation(check_in=self.day,check_out=self.end,beds_by_room={self.room.pk:1},name='Synthetic guest')
 def overview(self):
  rows=month_rows(self.day.replace(day=1),[self.room,self.other,self.inactive],visible_ids=set())
  days=[cell['day'] for cell in rows[0]['days']]
  with self.assertNumQueries(0):result=availability_overview(rows,days,self.day)
  return rows,result
 def test_overview_counts_exclusive_units_and_excludes_inactive_rooms(self):
  self.reserve();rows,data=self.overview();focus=data['focus']
  self.assertEqual((focus['capacity'],focus['booked'],focus['available'],focus['blocked'],focus['occupancy_pct']),(2,1,1,0,50))
  cell=next(c for c in rows[0]['days'] if c['day']==self.day)
  self.assertEqual(cell['available'],0);self.assertEqual(cell['reservations'],[])
 def test_maintenance_blocks_an_entire_unit_in_overview(self):
  bed=Bed.objects.create(room=self.room,number=1);BedClosure.objects.create(bed=bed,start=self.day,end=self.end)
  rows,data=self.overview();self.assertEqual((data['focus']['available'],data['focus']['blocked']),(1,1))
 def test_legacy_shared_records_raise_a_conflict_even_below_bed_capacity(self):
  with override_settings(BOOKING_UNIT='bed'):
   self.reserve();self.reserve()
  rows,data=self.overview();self.assertEqual(data['focus']['overbooked_rooms'],1)
 def test_bed_mode_keeps_uploaded_overview_calculations(self):
  with override_settings(BOOKING_UNIT='bed'):
   self.reserve();rows,data=self.overview()
   self.assertEqual((data['focus']['capacity'],data['focus']['booked'],data['focus']['available']),(10,1,9))
 def test_uploaded_css_and_filter_markup_are_preserved(self):
  root=Path(__file__).resolve().parents[1]
  template=(root/'floorplans/templates/floorplans/property_calendar_v138.html').read_text()
  for marker in ['property_availability_overview_v1.css','property_available_filter_v3.css','sd148-available-only','sd148-visible-count','overview.days']:
   self.assertIn(marker,template)
  script=(root/'floorplans/static/floorplans/property_planner_v147.js').read_text()
  self.assertIn('function applyAvailabilityRoomFilter()',script)
  self.assertIn("r.dataset.room===room.value||available(r,a,b,q)",script)
