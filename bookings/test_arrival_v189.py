from datetime import timedelta,time
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone,translation
from django.template.loader import render_to_string
from django.test import RequestFactory
from .models import Hut,Room,Reservation,HutMessageTemplate,ReservationNotification
from .services import create_reservation
from .booking_flow_v150 import hut_information
from .arrival_v189 import arrival_email_text,ArrivalForm,reservation_arrival_email
from .communications import render_message,message_candidates
from .views import send_confirmation
from .self_service import issue_guest_link

@override_settings(BOOKING_UNIT='room',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class Arrival189Tests(TestCase):
    def setUp(self):
        self.hut=Hut.objects.create(name='Synthetic arrival hut',slug='arrival189',public_phone='+359 888 123456',
            public_email='hut@example.test',directions_url='https://example.test/hut-map',location='Synthetic location')
        self.other=Hut.objects.create(name='Other hut',slug='other-arrival189')
        self.room=Room.objects.create(hut=self.hut,name='Studio',capacity=4,price_per_night=30,summer_price=40,winter_price=70)
        self.manager=get_user_model().objects.create_user('arrival-manager',is_staff=True);self.hut.managers.add(self.manager)
        self.client.force_login(self.manager);self.url=reverse('bookings:arrival_settings')
        self.start=timezone.localdate()+timedelta(days=2);self.end=self.start+timedelta(days=2)
        self.r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:3},
                                  name='Synthetic guest',email='guest@example.test',status='confirmed')

    def data(self,**extra):
        return {'hut_id':self.hut.pk,'public_phone':'+359 888 123456','public_email':'hut@example.test',
            'directions_url':'https://example.test/hut-map','check_in_from':'14:00','check_in_until':'20:00','check_out_until':'11:00',
            'arrival_directions_en':'Follow the synthetic trail.','arrival_directions_bg':'Тестова пътека.',
            'parking_en':'Synthetic parking instructions.','parking_bg':'Тестови указания за паркиране.',
            'arrival_notes_en':'Call before a late arrival.','arrival_notes_bg':'Обадете се при късно пристигане.',**extra}

    def configure(self):
        self.assertEqual(self.client.post(self.url,self.data()).status_code,302);self.hut.refresh_from_db()

    def test_unknown_arrival_fields_are_blank_and_no_times_are_invented(self):
        info=hut_information(self.hut)
        self.assertFalse(info['arrival_available']);self.assertEqual(info['arrival_sections'],[])
        html=render_to_string('bookings/arrival_info_v189.html',{'hut_info':info,'reservation':self.r})
        self.assertNotIn('Parking',html);self.assertNotIn('Check-out by',html);self.assertNotIn('14:00',html)
        self.assertIn('tel:+359888123456',html)

    def test_manager_saves_actual_info_without_repricing_or_sending_mail(self):
        total=self.r.total_price
        self.configure();self.assertEqual(self.hut.check_in_from,time(14));self.assertEqual(self.hut.check_out_until,time(11))
        self.r.refresh_from_db();self.room.refresh_from_db();self.assertEqual(self.r.total_price,total)
        self.assertEqual(self.room.summer_price,40);self.assertEqual(self.room.winter_price,70)
        self.assertFalse(ReservationNotification.objects.exists())

    def test_other_hut_get_and_post_are_refused(self):
        self.assertEqual(self.client.get(self.url,{'hut':self.other.slug}).status_code,404)
        self.assertEqual(self.client.post(self.url,self.data(hut_id=self.other.pk)).status_code,404)
        self.other.refresh_from_db();self.assertEqual(self.other.parking_en,'')

    def test_anonymous_and_unassigned_staff_cannot_edit(self):
        self.client.logout();self.assertEqual(self.client.post(self.url,self.data()).status_code,302)
        user=get_user_model().objects.create_user('arrival-unassigned',is_staff=True);self.client.force_login(user)
        self.assertEqual(self.client.post(self.url,self.data()).status_code,403)

    def test_csrf_is_required(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.manager)
        self.assertEqual(client.post(self.url,self.data()).status_code,403)

    def test_superuser_can_choose_and_edit_all_huts(self):
        owner=get_user_model().objects.create_superuser('arrival-owner','owner@example.test','test-only');self.client.force_login(owner)
        page=self.client.get(self.url);self.assertEqual(page.status_code,200);self.assertContains(page,'Other hut')
        self.assertEqual(self.client.post(self.url,self.data(hut_id=self.other.pk)).status_code,302)

    def test_invalid_url_phone_and_time_do_not_partially_save(self):
        for changes in [{'directions_url':'javascript:alert(1)'},{'public_phone':'not a phone'},{'check_in_from':'25:80'}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post(self.url,self.data(**changes)).status_code,200)
                self.hut.refresh_from_db();self.assertEqual(self.hut.parking_en,'');self.assertIsNone(self.hut.check_in_from)

    def test_injected_payment_and_name_changes_are_ignored(self):
        self.client.post(self.url,self.data(payment_instructions_en='Injected',name='Changed'))
        self.hut.refresh_from_db();self.assertEqual(self.hut.name,'Synthetic arrival hut');self.assertEqual(self.hut.payment_instructions_en,'')

    def test_guest_receipt_displays_directions_parking_times_and_contacts(self):
        self.configure();page=self.client.get(self.r.get_absolute_url())
        for value in ['Arrival information','Synthetic parking instructions.','14:00','20:00','11:00','Follow the synthetic trail.',
                      'Call before a late arrival.','tel:+359888123456','mailto:hut@example.test','https://example.test/hut-map']:
            self.assertContains(page,value)

    def test_private_guest_portal_has_the_same_arrival_information(self):
        self.configure();url=issue_guest_link(self.r);self.client.logout()
        page=self.client.get(url);self.assertEqual(page.status_code,200);self.assertContains(page,'Synthetic parking instructions.')
        self.assertContains(page,'14:00');self.assertContains(page,'11:00')

    def test_cancelled_receipt_keeps_contact_but_hides_arrival_instructions(self):
        self.configure();self.r.status='cancelled';self.r.save(update_fields=['status'])
        page=self.client.get(self.r.get_absolute_url());self.assertContains(page,'tel:+359888123456')
        self.assertNotContains(page,'Synthetic parking instructions.');self.assertNotContains(page,'Call before a late arrival.')

    def test_bulgarian_and_english_fallback_are_marked_with_actual_language(self):
        self.configure();self.hut.parking_en=''
        with translation.override('bg'):
            info=hut_information(self.hut);self.assertEqual(info['arrival_sections'][1]['text'],'Тестови указания за паркиране.')
        with translation.override('en'):
            info=hut_information(self.hut);self.assertEqual(info['arrival_sections'][1]['lang'],'bg')

    def test_midnight_and_only_one_checkin_boundary_are_supported(self):
        self.hut.check_in_from=time(0);self.hut.check_out_until=time(0)
        info=hut_information(self.hut);self.assertEqual(info['check_in_window'],'From 00:00');self.assertEqual(info['check_out_time'],'00:00')
        self.hut.check_in_from=None;self.hut.check_in_until=time(20)
        self.assertEqual(hut_information(self.hut)['check_in_window'],'Until 20:00')

    def test_plain_text_is_escaped_on_guest_page_and_unsafe_map_is_hidden(self):
        self.hut.parking_en='<script>alert(1)</script>';self.hut.directions_url='javascript:alert(1)'
        html=render_to_string('bookings/arrival_info_v189.html',{'hut_info':hut_information(self.hut),'reservation':self.r})
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html);self.assertNotIn('href="javascript:',html)

    def test_confirmation_queue_contains_arrival_info_without_duplicates(self):
        self.configure();request=RequestFactory().get('/');request.user=self.manager
        send_confirmation(request,self.r,defer_delivery=True)
        item=ReservationNotification.objects.get(kind='confirmation_guest')
        for value in ['Synthetic parking instructions.','14:00','11:00','https://example.test/hut-map','hut@example.test']:
            self.assertIn(value,item.body)
        self.assertEqual(item.body.count('Arrival information'),1)

    def test_custom_confirmation_retains_its_copy_and_appends_arrival_info_once(self):
        self.configure();HutMessageTemplate.objects.create(hut=self.hut,message_type='confirmation',subject='Custom {code}',body='Custom booking text {guest}.')
        request=RequestFactory().get('/');request.user=self.manager;send_confirmation(request,self.r,defer_delivery=True)
        item=ReservationNotification.objects.get(kind='confirmation_guest')
        self.assertIn('Custom booking text Synthetic guest.',item.body)
        self.assertEqual(item.body.count('Arrival information'),1)
        self.assertIn('Synthetic parking instructions.',item.body)

    def test_prearrival_email_uses_configured_details_and_only_confirmed_bookings(self):
        self.configure();subject,body=render_message(self.r,self.hut,'prearrival')
        self.assertIn('Synthetic parking instructions.',body);self.assertIn('14:00',body)
        self.assertIn('prearrival',[kind for kind,day,summary in message_candidates(self.r,timezone.localdate())])
        self.r.status='pending';self.r.save(update_fields=['status'])
        self.assertNotIn('prearrival',[kind for kind,day,summary in message_candidates(self.r,timezone.localdate())])

    def test_custom_prearrival_template_still_gets_arrival_details(self):
        self.configure();HutMessageTemplate.objects.create(hut=self.hut,message_type='prearrival',subject='Your trip',body='Personal text for {hut}.')
        subject,body=render_message(self.r,self.hut,'prearrival')
        self.assertEqual(subject,'Your trip');self.assertIn('Personal text for Synthetic arrival hut.',body);self.assertIn('14:00',body)

    def test_email_text_preserves_active_language_and_has_no_invented_values(self):
        with translation.override('bg'):
            text=arrival_email_text(self.hut);self.assertEqual(translation.get_language(),'bg')
        self.assertIn('hut@example.test',text);self.assertNotIn('14:00',text);self.assertNotIn('Parking:',text)

    def test_updating_facts_does_not_resend_or_change_already_queued_email(self):
        self.configure();request=RequestFactory().get('/');request.user=self.manager;send_confirmation(request,self.r,defer_delivery=True)
        queued=ReservationNotification.objects.get(kind='confirmation_guest');body=queued.body
        self.client.post(self.url,self.data(parking_en='New synthetic parking.'))
        queued.refresh_from_db();self.assertEqual(queued.body,body);self.assertEqual(ReservationNotification.objects.count(),1)
        self.assertContains(self.client.get(self.r.get_absolute_url()),'New synthetic parking.')
