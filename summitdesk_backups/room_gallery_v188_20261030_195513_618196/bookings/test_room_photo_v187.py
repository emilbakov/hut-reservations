from datetime import timedelta
from io import BytesIO
from pathlib import Path
import tempfile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.template.loader import render_to_string
from PIL import Image
from .models import Hut,Room,PublicWebsiteSettings
from .services import create_reservation
from .room_details_v184 import RoomDetailsForm
from .admin import RoomInline


def photo():
    stream=BytesIO();Image.new('RGB',(32,20),'#567060').save(stream,format='PNG')
    return SimpleUploadedFile('synthetic-room.png',stream.getvalue(),content_type='image/png')


@override_settings(BOOKING_UNIT='room',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class RoomPhoto187Tests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory();self.addCleanup(self.media.cleanup)
        settings=override_settings(MEDIA_ROOT=self.media.name);settings.enable();self.addCleanup(settings.disable)
        self.hut=Hut.objects.create(name='Synthetic photo hut',slug='photo187')
        self.room=Room.objects.create(hut=self.hut,name='Studio 1',capacity=4,price_per_night=30,summer_price=40,winter_price=70)
        PublicWebsiteSettings.objects.create(main_hut=self.hut)
        self.user=get_user_model().objects.create_user('photo-manager',is_staff=True);self.hut.managers.add(self.user)
        self.url=reverse('bookings:room_details',args=[self.room.pk])
        self.start=timezone.localdate()+timedelta(days=2);self.end=self.start+timedelta(days=2)

    def data(self,**extra):
        return {'room_type':'studio','summer_price':'40','winter_price':'70','extras_en':'','extras_bg':'',**extra}

    def save_photo(self):
        self.room.image=photo();self.room.save(update_fields=['image']);return self.room.image.url

    def page(self,dates=True):
        return self.client.get(reverse('bookings:book'),{'check_in':self.start,'check_out':self.end,'beds':3} if dates else {})

    def test_new_room_photo_is_optional_and_defaults_blank(self):
        self.assertFalse(self.room.image)
        self.assertTrue(RoomDetailsForm(self.data(),instance=self.room).is_valid())
        self.assertFalse(Path(self.media.name,'rooms').exists())

    def test_booking_cards_without_photo_have_no_image_or_placeholder(self):
        page=self.page();self.assertEqual(page.status_code,200)
        self.assertNotContains(page,'class="room187-photo"')
        self.assertNotContains(page,'/media/rooms/')

    def test_manager_upload_is_saved_under_rooms_and_keeps_prices_and_bookings(self):
        r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:2},name='Synthetic')
        total=r.total_price
        self.client.force_login(self.user)
        page=self.client.post(self.url,self.data(image=photo()))
        self.assertEqual(page.status_code,302);self.room.refresh_from_db();r.refresh_from_db()
        self.assertTrue(self.room.image.name.startswith('rooms/'))
        self.assertTrue(Path(self.room.image.path).is_file())
        self.assertEqual(self.room.capacity,4);self.assertEqual(self.room.summer_price,40);self.assertEqual(self.room.winter_price,70)
        self.assertEqual(r.total_price,total)

    def test_photo_shown_in_booking_options_with_and_without_dates(self):
        url=self.save_photo()
        for dates in [True,False]:
            page=self.page(dates)
            self.assertContains(page,'class="room187-photo"')
            self.assertContains(page,url)
            self.assertContains(page,'alt="Studio 1 at Synthetic photo hut"')
            self.assertContains(page,'loading="lazy"')
            self.assertContains(page,'width="960" height="600"')

    def test_room_photo_never_appears_on_homepage_or_hut_directory(self):
        url=self.save_photo()
        for path in ['/',reverse('bookings:hut_list')]:
            page=self.client.get(path);self.assertEqual(page.status_code,200)
            self.assertNotContains(page,url)
            self.assertNotContains(page,'class="room187-photo"')

    def test_invalid_image_rejected_without_writing_a_file(self):
        self.client.force_login(self.user)
        page=self.client.post(self.url,self.data(image=SimpleUploadedFile('fake.png',b'not an image',content_type='image/png')))
        self.assertEqual(page.status_code,200);self.assertIn('image',page.context['form'].errors)
        self.room.refresh_from_db();self.assertFalse(self.room.image)
        self.assertEqual(list(Path(self.media.name).rglob('*')),[])

    def test_existing_image_is_kept_if_no_new_upload_is_submitted(self):
        self.save_photo();name=self.room.image.name
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url,self.data()).status_code,302)
        self.room.refresh_from_db();self.assertEqual(self.room.image.name,name)

    def test_image_can_be_cleared_without_deleting_the_file_or_room(self):
        self.save_photo();path=Path(self.room.image.path)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url,self.data(**{'image-clear':'on'})).status_code,302)
        self.room.refresh_from_db();self.assertFalse(self.room.image)
        self.assertTrue(path.exists())
        self.assertNotContains(self.page(),'class="room187-photo"')

    def test_foreign_manager_cannot_upload_to_room(self):
        other=get_user_model().objects.create_user('foreign-photo-manager',is_staff=True)
        hut=Hut.objects.create(name='Other synthetic hut',slug='other-photo187');hut.managers.add(other)
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url,self.data(image=photo())).status_code,404)
        self.room.refresh_from_db();self.assertFalse(self.room.image)
        self.assertEqual(list(Path(self.media.name).rglob('*')),[])

    def test_edit_form_supports_files_and_admin_inline_exposes_photo(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url),'enctype="multipart/form-data"')
        self.assertIn('image',RoomInline.fields)

    def test_alt_text_escapes_room_names(self):
        self.save_photo();self.room.name='<img onerror=alert(1)>'
        html=render_to_string('bookings/room_photo_v187.html',{'room':self.room})
        self.assertIn('&lt;img onerror=alert(1)&gt;',html)
        self.assertNotIn('alt="<img',html)
