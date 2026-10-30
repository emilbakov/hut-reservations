"""The story-led homepage and the separate, protected reservation flow."""
from datetime import timedelta
from html.parser import HTMLParser

from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Room, Reservation, PublicWebsiteSettings, PublicBookingSubmission, PublicBookingRateBucket


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.images = []
        self.links = []
        self.inputs = []
        self.meta = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img': self.images.append(attrs)
        if tag == 'a': self.links.append(attrs)
        if tag == 'input': self.inputs.append(attrs)
        if tag == 'meta': self.meta[attrs.get('property', attrs.get('name'))] = attrs.get('content')


class HeritageHomepage168Tests(TestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name='Studenets Hut', slug='studenets', location='Pamporovo',
                                      public_phone='+359 888 123 456', public_email='hut@example.test')
        self.room = Room.objects.create(hut=self.hut, name='Main dorm', capacity=4, price_per_night='18.00')
        self.other = Hut.objects.create(name='Optional Hut', slug='optional')
        self.other_room = Room.objects.create(hut=self.other, name='Other dorm', capacity=2, price_per_night='12.00')
        self.profile = PublicWebsiteSettings.objects.create(main_hut=self.hut)
        self.start = timezone.localdate() + timedelta(days=7)
        self.dates = {'check_in': self.start.isoformat(), 'check_out': (self.start + timedelta(days=2)).isoformat()}

    def test_home_has_story_and_separate_booking_links_without_reservation_controls(self):
        response = self.client.get('/', self.dates)
        self.assertTemplateUsed(response, 'bookings/heritage_home_v168.html')
        self.assertContains(response, 'A resort’s heart.')
        self.assertContains(response, 'The original hut')
        self.assertContains(response, '1984')
        self.assertContains(response, 'href="/book/"')
        self.assertContains(response, 'href="/huts/"')
        page = Page(response.content.decode())
        self.assertFalse({'name', 'email', 'check_in', 'check_out', 'submission_token'} & {a.get('name') for a in page.inputs})
        self.assertNotContains(response, 'ph-reservation-form')
        self.assertNotContains(response, 'available for your stay')
        for model in (Reservation, PublicBookingSubmission, PublicBookingRateBucket):
            self.assertFalse(model.objects.exists())

    def test_main_hut_alias_shares_the_story_and_root_canonical(self):
        response = self.client.get(reverse('bookings:hut_detail', args=[self.hut.slug]))
        self.assertTemplateUsed(response, 'bookings/heritage_home_v168.html')
        self.assertContains(response, 'rel="canonical" href="http://testserver/"')
        self.assertNotContains(response, 'ph-date-form')

    def test_date_and_request_forms_submit_only_to_the_booking_page(self):
        response = self.client.get('/book/', self.dates)
        self.assertTemplateUsed(response, 'bookings/public_hut_v125.html')
        self.assertContains(response, 'action="/book/" id="ph-date-form"')
        self.assertContains(response, 'action="/book/#sd150-errors"')
        self.assertContains(response, '4 available for your stay')
        self.assertNotContains(response, 'Other dorm')

    def test_new_booking_route_retains_csrf_and_signed_idempotent_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/')
        page = client.get('/book/', self.dates)
        payload = {**self.dates, 'beds': '1', 'name': 'Test Guest', 'email': 'guest@example.test',
                   f'room_{self.room.pk}': '1', 'submission_token': page.context['submission_token']}
        self.assertEqual(client.post('/book/', payload).status_code, 403)
        self.assertFalse(Reservation.objects.exists())
        payload['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        first = client.post('/book/', payload)
        second = client.post('/book/', payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.url, first.url)
        self.assertEqual(Reservation.objects.count(), 1)
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertTrue(reservation.guest_request)
        self.assertEqual(reservation.items.get().room_id, self.room.pk)

    def test_other_huts_remain_information_only(self):
        response = self.client.get(reverse('bookings:hut_detail', args=[self.other.slug]))
        self.assertTemplateUsed(response, 'bookings/hut_information_v153.html')
        self.assertContains(response, 'Online booking unavailable')
        self.assertNotContains(response, 'h168-hero')
        self.assertNotContains(response, 'ph-reservation-form')

    def test_home_uses_real_hut_contacts_and_does_not_advertise_draft_policies(self):
        self.profile.privacy_en = 'Private draft'
        self.profile.save(update_fields=['privacy_en'])
        response = self.client.get('/')
        self.assertContains(response, 'href="tel:+359888123456"')
        self.assertContains(response, 'href="mailto:hut@example.test"')
        self.assertNotContains(response, 'Private draft')
        self.assertNotContains(response, '/policies/privacy/')
        header = response.content.decode().split('<header', 1)[1].split('</header>', 1)[0]
        self.assertNotIn('/staff/login/', header)

    def test_bulgarian_story_and_booking_links_are_localized(self):
        self.client.cookies['django_language'] = 'bg'
        response = self.client.get('/')
        self.assertContains(response, 'lang="bg"')
        self.assertContains(response, 'Хижа с история.')
        self.assertContains(response, 'Сърцето на курорта.')
        self.assertContains(response, 'Нашата история')
        self.assertContains(response, 'Всички хижи')
        self.assertContains(response, 'Стаи и резервации')
        self.assertNotContains(response, 'Before the resort grew')

    def test_uploaded_photographs_are_served_locally_with_priority_and_archive_credits(self):
        response = self.client.get('/')
        page = Page(response.content.decode())
        hero = next(image for image in page.images if image.get('fetchpriority') == 'high')
        self.assertIn('studenets-today-1280.webp', hero['src'])
        self.assertEqual(hero['width'], '1280')
        self.assertEqual(hero['height'], '714')
        for image in page.images:
            source = image.get('src')
            if source:
                self.assertTrue(source.startswith('/static/'), source)
                self.assertTrue(finders.find(source.removeprefix('/static/')), source)
        self.assertContains(response, 'Bulgarian Visual Archive / Milena Nikolova', count=2)
        self.assertNotContains(response, 'fonts.googleapis.com')

    def test_sharing_metadata_uses_the_hut_photograph_without_guest_query_data(self):
        response = self.client.get('/', {'email': 'private@example.test'}, secure=True)
        meta = Page(response.content.decode()).meta
        self.assertEqual(meta['og:image'], 'https://testserver/static/bookings/heritage-v168/studenets-social.jpg')
        self.assertEqual(meta['og:image:width'], '1280')
        self.assertIn(self.hut.name, meta['og:title'])
        self.assertNotIn('private@example.test', str(meta))

    def test_hut_description_and_name_are_escaped(self):
        self.hut.name = 'Hut <script>bad()</script>'
        self.hut.description = '<script>bad()</script>'
        self.hut.save(update_fields=['name', 'description'])
        response = self.client.get('/')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
