from django.test import Client, TestCase
from django.urls import reverse
from .models import Hut, PublicWebsiteSettings, Reservation, Room


class HutPagesV177Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.main = Hut.objects.create(name='Z Main Hut', slug='main', image='huts/main.jpg')
        cls.other = Hut.objects.create(name='A Forest Hut', slug='forest', location='Rhodope',
            description='A real description.', public_phone='+359 888 123 456',
            public_email='hut@example.test', directions_url='https://example.test/forest')
        cls.second = Hut.objects.create(name='B Ridge Hut', slug='ridge')
        cls.hidden = Hut.objects.create(name='Private Hut', slug='private', is_active=False)
        PublicWebsiteSettings.objects.update_or_create(pk=1, defaults={'main_hut': cls.main})
        Room.objects.create(hut=cls.other, name='Public room', capacity=6, price_per_night='99.99')
        Room.objects.create(hut=cls.other, name='Hidden room', capacity=100, is_active=False)

    def test_directory_keeps_search_and_main_priority_without_availability_claims(self):
        response = self.client.get('/huts/')
        self.assertEqual(response.context['cards'][0]['hut'], self.main)
        self.assertNotContains(response, self.hidden.name)
        self.assertNotContains(response, '99.99')
        response = self.client.get('/huts/', {'q': 'Rhodope'})
        self.assertEqual([c['hut'] for c in response.context['cards']], [self.other])
        self.assertContains(response, 'value="Rhodope"')
        self.assertContains(self.client.get('/huts/', {'q': 'no match'}), 'No matching huts found')

    def test_each_secondary_hut_has_information_and_protected_booking_policy(self):
        for hut in [self.other, self.second]:
            url = reverse('bookings:hut_detail', args=[hut.slug])
            page = self.client.get(url)
            self.assertContains(page, '<h1>' + hut.name + '</h1>', html=True)
            self.assertContains(page, 'Online booking unavailable')
            self.assertNotContains(page, 'name="submission_token"')
            self.assertNotContains(page, 'name="check_in"')
            self.assertEqual(self.client.post(url, {'name': 'Test', 'room_1': 1}).status_code, 403)
        self.assertFalse(Reservation.objects.exists())

    def test_details_use_only_public_rooms_and_the_huts_own_contacts(self):
        page = self.client.get('/huts/forest/')
        self.assertEqual(page.context['public_capacity'], 6)
        self.assertContains(page, 'Public room')
        self.assertNotContains(page, 'Hidden room')
        self.assertNotContains(page, '99.99')
        for target in ['tel:+359888123456', 'mailto:hut@example.test', 'https://example.test/forest']:
            self.assertContains(page, 'href="' + target + '"')
        self.assertNotIn(self.hidden, page.context['related_huts'])
        self.assertNotIn(self.other, page.context['related_huts'])
        self.assertContains(self.client.get('/huts/ridge/'), 'Hut photograph coming soon')
        self.assertEqual(self.client.get('/huts/private/').status_code, 404)

    def test_bulgarian_and_csrf_language_switch_keep_secondary_route(self):
        client = Client(enforce_csrf_checks=True)
        url = '/huts/forest/?from=directory'
        page = client.get(url)
        token = client.cookies['csrftoken'].value
        changed = client.post(reverse('set_language'), {'language': 'bg', 'next': url,
            'csrfmiddlewaretoken': token})
        self.assertRedirects(changed, url, fetch_redirect_response=False)
        translated = client.get(url)
        self.assertContains(translated, '<html lang="bg">')
        self.assertContains(translated, 'Контакти и маршрут')
        self.assertContains(client.get('/huts/'), 'Малко по-близо')

    def test_main_homepage_and_booking_still_use_their_existing_templates(self):
        self.assertTemplateUsed(self.client.get('/'), 'bookings/heritage_home_v168.html')
        self.assertTemplateUsed(self.client.get('/book/'), 'bookings/public_hut_v125.html')
