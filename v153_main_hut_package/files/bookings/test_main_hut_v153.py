"""The main-hut policy must hold across every public reservation entry point."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (Hut, Room, Reservation, PublicWebsiteSettings, PublicBookingSubmission,
                     PublicBookingRateBucket, ReservationNotification)
from .main_hut_v153 import main_hut
from .services import create_reservation


class MainHut153Tests(TestCase):
    def setUp(self):
        self.hut=Hut.objects.create(name='Main mountain hut',slug='main-hut',description='Our main hut.',location='Rhodope Mountains')
        self.other=Hut.objects.create(name='Optional hut',slug='optional-hut',description='Visit this other hut.')
        self.hidden=Hut.objects.create(name='Private hut',slug='not-public',is_active=False)
        self.room=Room.objects.create(hut=self.hut,name='Main Dorm',capacity=4,price_per_night=20)
        self.other_room=Room.objects.create(hut=self.other,name='Optional Dorm',capacity=4,price_per_night=15)
        self.profile=PublicWebsiteSettings.objects.create(main_hut=self.hut)
        self.start=timezone.localdate()+timedelta(days=5)
        self.end=self.start+timedelta(days=2)

    def payload(self,room=None):
        return {'check_in':self.start.isoformat(),'check_out':self.end.isoformat(),'beds':'1',
                'name':'Main Guest','email':'guest@example.test',f'room_{(room or self.room).pk}':'1'}

    def assert_no_booking_writes(self):
        for model in [Reservation,PublicBookingSubmission,PublicBookingRateBucket,ReservationNotification]:
            self.assertFalse(model.objects.exists(),model.__name__)

    def test_root_opens_selected_hut_and_forms_stay_at_root(self):
        page=self.client.get('/',{'check_in':self.start,'check_out':self.end})
        self.assertEqual(page.status_code,200)
        self.assertEqual(page.context['hut'],self.hut)
        self.assertTrue(page.context['homepage'])
        self.assertContains(page,'Main Dorm')
        self.assertContains(page,'All huts')
        self.assertContains(page,'action="/#sd150-errors"')
        self.assertContains(page,'action="/" id="ph-date-form"')
        self.assertContains(page,'rel="canonical" href="http://testserver/"')
        self.assertNotContains(page,'Optional Dorm')

    def test_root_post_creates_only_main_hut_pending_request(self):
        response=self.client.post('/',self.payload())
        self.assertEqual(response.status_code,302)
        reservation=Reservation.objects.get()
        self.assertEqual(reservation.status,'pending')
        self.assertTrue(reservation.guest_request)
        self.assertEqual(reservation.items.get().room,self.room)

    def test_new_root_booking_entry_requires_csrf(self):
        response=Client(enforce_csrf_checks=True).post('/',self.payload())
        self.assertEqual(response.status_code,403)
        self.assert_no_booking_writes()

    def test_main_slug_remains_compatible_and_canonical_is_root(self):
        url=reverse('bookings:hut_detail',args=[self.hut.slug])
        self.assertContains(self.client.get(url),'rel="canonical" href="http://testserver/"')
        self.assertEqual(self.client.post(url,self.payload()).status_code,302)

    def test_other_hut_has_information_contacts_and_no_booking_form(self):
        self.other.public_phone='+359 888 123 456';self.other.save(update_fields=['public_phone'])
        page=self.client.get(reverse('bookings:hut_detail',args=[self.other.slug]),self.payload(self.other_room))
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'Optional Dorm')
        self.assertContains(page,'Online booking unavailable')
        self.assertContains(page,'tel:+359888123456')
        self.assertNotContains(page,'ph-date-form')
        self.assertNotContains(page,'ph-reservation-form')
        self.assertNotContains(page,'name="submission_token"')
        self.assertNotContains(page,'id="ph-request-submit"')

    def test_direct_other_hut_post_is_forbidden_without_any_booking_writes(self):
        response=self.client.post(reverse('bookings:hut_detail',args=[self.other.slug]),self.payload(self.other_room))
        self.assertEqual(response.status_code,403)
        self.assert_no_booking_writes()

    def test_legacy_book_form_lists_only_main_hut_and_cannot_book_another_hut(self):
        page=self.client.get(reverse('bookings:book'),{'check_in':self.start,'check_out':self.end,'hut':self.other.slug})
        self.assertContains(page,'Main Dorm')
        self.assertNotContains(page,'Optional Dorm')
        page=self.client.post(reverse('bookings:book'),self.payload(self.other_room))
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'These rooms are not available for online booking.')
        self.assert_no_booking_writes()

    def test_forged_extra_room_is_rejected_even_with_valid_main_room(self):
        payload=self.payload();payload[f'room_{self.other_room.pk}']='1'
        self.assertContains(self.client.post('/',payload),'These rooms are not available for online booking.')
        self.assert_no_booking_writes()

    def test_directory_keeps_other_huts_informational_and_never_shows_private_huts(self):
        page=self.client.get(reverse('bookings:hut_list'),self.payload())
        self.assertContains(page,self.hut.name)
        self.assertContains(page,self.other.name)
        self.assertContains(page,'Information only · online booking unavailable')
        self.assertNotContains(page,self.hidden.name)
        self.assertNotContains(page,'beds free for your stay')
        self.assert_no_booking_writes()

    def test_public_availability_is_scoped_to_main_hut(self):
        data={'year':self.start.year,'month':self.start.month}
        page=self.client.get(reverse('bookings:calendar'),data)
        self.assertEqual(page.status_code,200)
        self.assertEqual(self.client.get(reverse('bookings:calendar'),{**data,'hut':self.other.slug}).status_code,404)
        self.assert_no_booking_writes()

    def test_main_change_invalidates_old_public_page(self):
        self.client.get(reverse('bookings:hut_detail',args=[self.hut.slug]),self.payload())
        self.profile.main_hut=self.other;self.profile.save(update_fields=['main_hut'])
        response=self.client.post(reverse('bookings:hut_detail',args=[self.hut.slug]),self.payload())
        self.assertEqual(response.status_code,403)
        self.assert_no_booking_writes()

    def test_policy_is_rechecked_inside_submission_transaction(self):
        from .reliability_v145 import create_public_submission
        def switch(identity,save):
            PublicWebsiteSettings.objects.filter(pk=1).update(main_hut=self.other)
            return create_public_submission(identity,save)
        with patch('bookings.views.create_public_submission',side_effect=switch):
            response=self.client.post('/',self.payload())
        self.assertEqual(response.status_code,403)
        self.assert_no_booking_writes()

    def test_retiring_main_hut_does_not_enable_a_different_hut(self):
        self.hut.is_active=False;self.hut.save(update_fields=['is_active'])
        self.assertIsNone(main_hut())
        self.assertEqual(self.client.post('/',self.payload(self.other_room)).status_code,403)
        self.assertEqual(self.client.post(reverse('bookings:hut_detail',args=[self.other.slug]),self.payload(self.other_room)).status_code,403)
        self.assert_no_booking_writes()

    def test_main_hut_is_protected_from_accidental_deletion(self):
        with self.assertRaises(ProtectedError):self.hut.delete()

    def test_admin_validation_refuses_inactive_main_hut(self):
        self.profile.main_hut=self.hidden
        with self.assertRaises(ValidationError) as caught:self.profile.full_clean()
        self.assertIn('main_hut',caught.exception.message_dict)

    def test_unconfigured_multiple_huts_accept_no_public_reservations(self):
        self.profile.main_hut=None;self.profile.save(update_fields=['main_hut'])
        self.assertIsNone(main_hut())
        self.assertContains(self.client.get('/'),'Browse our huts. Online booking will be available soon.')
        self.assertEqual(self.client.post('/',self.payload()).status_code,403)
        self.assert_no_booking_writes()

    def test_sole_active_hut_is_safe_default_before_explicit_selection(self):
        self.profile.main_hut=None;self.profile.save(update_fields=['main_hut'])
        self.other.is_active=False;self.other.save(update_fields=['is_active'])
        self.assertEqual(main_hut(),self.hut)
        self.assertEqual(self.client.post('/',self.payload()).status_code,302)

    def test_existing_other_hut_bookings_remain_accessible_to_staff(self):
        reservation=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.other_room.pk:1},
            name='Existing guest',status='pending')
        manager=get_user_model().objects.create_user('other-manager',is_staff=True)
        self.other.managers.add(manager);self.client.force_login(manager)
        response=self.client.post(reverse('bookings:manager_reservation_action',args=[reservation.code]),{'action':'confirm'})
        self.assertEqual(response.status_code,302)
        reservation.refresh_from_db();self.assertEqual(reservation.status,'confirmed')

    def test_bulgarian_information_only_notice(self):
        self.client.cookies['django_language']='bg'
        page=self.client.get(reverse('bookings:hut_detail',args=[self.other.slug]))
        self.assertContains(page,'Онлайн резервации не се приемат')
