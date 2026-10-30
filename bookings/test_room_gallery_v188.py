from datetime import timedelta
from io import BytesIO
from pathlib import Path
import tempfile
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from .models import Hut,Room,RoomPhoto,PublicWebsiteSettings,Bed
from .services import create_reservation


def image(name='synthetic.png'):
    out=BytesIO();Image.new('RGB',(32,20),'#457066').save(out,format='PNG')
    return SimpleUploadedFile(name,out.getvalue(),content_type='image/png')

@override_settings(BOOKING_UNIT='room',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BOOKING_NOTIFY_EMAIL='')
class RoomGallery188Tests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory();self.addCleanup(self.media.cleanup)
        settings=override_settings(MEDIA_ROOT=self.media.name);settings.enable();self.addCleanup(settings.disable)
        self.hut=Hut.objects.create(name='Synthetic gallery hut',slug='gallery188')
        self.room=Room.objects.create(hut=self.hut,name='Studio',capacity=4,price_per_night=30,summer_price=40,winter_price=70)
        PublicWebsiteSettings.objects.create(main_hut=self.hut)
        self.manager=get_user_model().objects.create_user('gallery-manager',is_staff=True);self.hut.managers.add(self.manager)
        self.client.force_login(self.manager);self.url=reverse('bookings:room_details',args=[self.room.pk])
        self.start=timezone.localdate()+timedelta(days=5);self.end=self.start+timedelta(days=2)

    def photo(self,**kw):
        return RoomPhoto.objects.create(room=kw.pop('room',self.room),image=image(),**kw)

    def post(self,rows,**extra):
        initial=sum(bool(row.get('id')) for row in rows)
        data={'room_type':'studio','summer_price':'40','winter_price':'70','extras_en':'','extras_bg':'',
            'gallery-TOTAL_FORMS':str(len(rows)),'gallery-INITIAL_FORMS':str(initial),
            'gallery-MIN_NUM_FORMS':'0','gallery-MAX_NUM_FORMS':'1000',**extra}
        for index,row in enumerate(rows):
            for key,value in row.items():data[f'gallery-{index}-{key}']=value
        return self.client.post(self.url,data)

    def test_gallery_is_empty_until_photos_are_added(self):
        self.assertEqual(self.room.photos.count(),0);self.assertEqual(self.room.booking_photos,[])

    def test_existing_main_photo_stays_first_then_ordered_gallery(self):
        self.room.image=image('main.png');self.room.save(update_fields=['image'])
        late=self.photo(caption='Later',position=4);early=self.photo(caption='Earlier',position=1)
        self.assertEqual([p['url'] for p in self.room.booking_photos],[self.room.image.url,early.image.url,late.image.url])

    def test_gallery_works_without_a_main_photo(self):
        photo=self.photo(caption='Interior')
        self.assertEqual(self.room.booking_photos,[{'url':photo.image.url,'caption':'Interior'}])

    def test_upload_two_images_preserves_prices_capacity_and_booking_total(self):
        r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:3},name='Synthetic')
        total=r.total_price
        response=self.post([{'image':image('one.png'),'caption':'Bedroom','position':1},
                            {'image':image('two.png'),'caption':'Sitting area','position':2}])
        self.assertEqual(response.status_code,302);self.assertEqual(self.room.photos.count(),2)
        for photo in self.room.photos.all():
            self.assertTrue(photo.image.name.startswith('rooms/gallery/'));self.assertTrue(Path(photo.image.path).exists())
        self.room.refresh_from_db();r.refresh_from_db()
        self.assertEqual(self.room.capacity,4);self.assertEqual(self.room.summer_price,40);self.assertEqual(self.room.winter_price,70)
        self.assertEqual(r.total_price,total)

    def test_caption_order_and_deletion_update_only_scoped_rows(self):
        first=self.photo(caption='First');second=self.photo(caption='Second');old_path=Path(second.image.path)
        response=self.post([{'id':first.pk,'caption':'Updated','position':3},
                            {'id':second.pk,'caption':'Second','position':0,'DELETE':'on'}])
        self.assertEqual(response.status_code,302);first.refresh_from_db()
        self.assertEqual(first.caption,'Updated');self.assertEqual(first.position,3)
        self.assertFalse(RoomPhoto.objects.filter(pk=second.pk).exists());self.assertTrue(old_path.exists())

    def test_foreign_photo_id_cannot_be_updated_or_deleted(self):
        other=Room.objects.create(hut=self.hut,name='Other',capacity=2,price_per_night=20)
        foreign=self.photo(room=other,caption='Protected')
        response=self.post([{'id':foreign.pk,'caption':'Stolen','position':1,'DELETE':'on'}])
        self.assertEqual(response.status_code,200);foreign.refresh_from_db();self.assertEqual(foreign.caption,'Protected')
        self.assertEqual(self.room.photos.count(),0)

    def test_foreign_hut_manager_cannot_upload(self):
        outsider=get_user_model().objects.create_user('gallery-outsider',is_staff=True)
        self.client.force_login(outsider)
        self.assertEqual(self.post([{'image':image(),'position':0}]).status_code,404)
        self.assertEqual(self.room.photos.count(),0)

    def test_invalid_gallery_file_blocks_all_changes_and_writes(self):
        bad=SimpleUploadedFile('fake.png',b'not a photo',content_type='image/png')
        response=self.post([{'image':image(),'position':0},{'image':bad,'position':1}],summer_price='999')
        self.assertEqual(response.status_code,200);self.room.refresh_from_db()
        self.assertEqual(self.room.summer_price,40);self.assertEqual(self.room.photos.count(),0)
        self.assertEqual(list(Path(self.media.name).rglob('*')),[])

    def test_missing_management_form_rejects_gallery_upload(self):
        response=self.client.post(self.url,{'room_type':'studio','summer_price':'999','gallery-0-image':image()})
        self.assertEqual(response.status_code,200);self.room.refresh_from_db()
        self.assertEqual(self.room.summer_price,40);self.assertEqual(self.room.photos.count(),0)

    def test_older_metadata_post_keeps_existing_gallery(self):
        photo=self.photo(caption='Keep')
        response=self.client.post(self.url,{'room_type':'studio','summer_price':'40','winter_price':'70','extras_en':'','extras_bg':''})
        self.assertEqual(response.status_code,302);self.assertTrue(RoomPhoto.objects.filter(pk=photo.pk).exists())

    def test_room_options_render_gallery_controls_and_escaped_captions(self):
        first=self.photo(caption='<script>bad()</script>',position=0);second=self.photo(caption='Interior',position=1)
        response=self.client.get('/book/',{'check_in':self.start,'check_out':self.end,'beds':3})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,first.image.url);self.assertContains(response,second.image.url)
        self.assertContains(response,'data-gallery-prev');self.assertContains(response,'data-gallery-next')
        self.assertContains(response,'data-gallery-index="1"');self.assertContains(response,'&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response,'alt="<script>')

    def test_gallery_does_not_appear_on_homepage_or_hut_directory(self):
        photo=self.photo()
        for path in ['/',reverse('bookings:hut_list')]:
            response=self.client.get(path);self.assertEqual(response.status_code,200)
            self.assertNotContains(response,photo.image.url);self.assertNotContains(response,'room188-gallery')

    def test_prefetch_avoids_per_room_gallery_queries(self):
        self.photo();room=Room.objects.prefetch_related('photos').get(pk=self.room.pk)
        with self.assertNumQueries(0):self.assertEqual(len(room.booking_photos),1)

    def test_staff_editor_has_management_add_and_empty_form(self):
        response=self.client.get(self.url)
        self.assertContains(response,'name="gallery-TOTAL_FORMS"')
        self.assertContains(response,'id="room188-empty-form"');self.assertContains(response,'id="room188-add-photo"')
        self.assertContains(response,'enctype="multipart/form-data"')

    def test_native_admin_room_has_gallery_inline(self):
        owner=get_user_model().objects.create_superuser('gallery-owner','test@example.test','test-only');self.client.force_login(owner)
        response=self.client.get(reverse('admin:bookings_room_change',args=[self.room.pk]))
        self.assertEqual(response.status_code,200);self.assertContains(response,'name="photos-TOTAL_FORMS"')

    def test_unused_room_deletion_allows_gallery_and_retains_file(self):
        photo=self.photo();path=Path(photo.image.path)
        Bed.objects.create(room=self.room,number=1)
        owner=get_user_model().objects.create_superuser('gallery-delete-owner','test@example.test','test-only');self.client.force_login(owner)
        response=self.client.post(reverse('admin:bookings_room_changelist'),{
            'action':'delete_unused_rooms','_selected_action':[self.room.pk],'confirm_unused_room_delete':'yes'})
        self.assertEqual(response.status_code,302);self.assertFalse(Room.objects.filter(pk=self.room.pk).exists())
        self.assertFalse(RoomPhoto.objects.filter(pk=photo.pk).exists());self.assertTrue(path.exists())

    def test_booking_history_still_blocks_room_and_gallery_deletion(self):
        photo=self.photo()
        r=create_reservation(check_in=self.start,check_out=self.end,beds_by_room={self.room.pk:1},name='Synthetic')
        owner=get_user_model().objects.create_superuser('gallery-protected-owner','test@example.test','test-only');self.client.force_login(owner)
        self.client.post(reverse('admin:bookings_room_changelist'),{
            'action':'delete_unused_rooms','_selected_action':[self.room.pk],'confirm_unused_room_delete':'yes'})
        self.assertTrue(Room.objects.filter(pk=self.room.pk).exists())
        self.assertTrue(RoomPhoto.objects.filter(pk=photo.pk).exists())
        self.assertEqual(r.items.count(),1)
